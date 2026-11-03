import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {pathToFileURL} from 'node:url';
import {World} from './vendor/planck.mjs';
import {simulate,validateResult,VERSION,DURATION,INSTABILITY_POLICY,COURSE_PROFILES} from './physics.mjs';
import {initialPopulation} from './evolution.mjs';
import {frameAt} from './draw.mjs';
import {createPool} from './pool.mjs';

const root=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-instability-')),servers=[],pools=[],controllers=[];
const probe=initialPopulation(2026,6)[5],originalStep=World.prototype.step;
const listen=async server=>{servers.push(server);await new Promise(r=>server.listen(0,'127.0.0.1',r));return 'http://127.0.0.1:'+server.address().port;};
const pool=async options=>{const value=await createPool(options);pools.push(value);return value;};
try {
  // 実エンジンのstep直後へ異常値を注入し、無効なステップが成績/フレームへ入らないことを検査する。
  for(const [bodyIndex,field,value,code] of [[0,'speed',81,'speed-limit'],[0,'height',41,'height-limit'],[0,'x',NaN,'non-finite'],[1,'angle',Infinity,'non-finite'],[2,'angularVelocity',NaN,'non-finite']]) {
    let step=0,before;
    World.prototype.step=function(...args){
      const bodies=[];for(let b=this.getBodyList();b;b=b.getNext())if(b.isDynamic())bodies.push(b);bodies.reverse();
      if(step===13)before={body:[bodies[0].getPosition().x,bodies[0].getPosition().y,bodies[0].getAngle()],wheels:bodies.slice(1).map(b=>[b.getPosition().x,b.getPosition().y,b.getAngle()])};
      originalStep.apply(this,args);
      if(++step===14){const b=bodies[bodyIndex];if(field==='speed'){b.m_linearVelocity.x=value;b.m_xf.p.x=10000;}else if(field==='height')b.m_xf.p.y=value;else if(field==='x')b.m_xf.p.x=value;else if(field==='angle')b.m_sweep.a=value;else b.m_angularVelocity=value;}
    };
    const result=simulate(probe,{frames:true});validateResult(result);
    assert.equal(result.reason,'unstable');assert.equal(result.instability.code,code);assert.equal(result.instability.policy,INSTABILITY_POLICY);
    assert.equal(result.elapsed,13/60);assert.equal(result.instability.detectedAt,14/60);assert.equal(result.score,result.distance);assert.ok(result.distance<160);
    assert.equal(result.frames.at(-1).t,result.elapsed);assert.deepEqual(result.frames.at(-1).body,before.body);assert.deepEqual(result.frames.at(-1).wheels,before.wheels);
    assert.ok(result.frames.every(f=>[...f.body,...f.wheels.flat()].every(Number.isFinite)));
    assert.deepEqual(frameAt(result.frames,30),result.frames.at(-1));
  }
  World.prototype.step=originalStep;
  assert.throws(()=>simulate([]));
  World.prototype.step=()=>{throw Error('engine-bug');};assert.throws(()=>simulate(probe),/engine-bug/);World.prototype.step=originalStep;
  console.log('PASS: 非有限な車体/両車輪・高さ/速度上限を区別し、直前の時刻/距離/姿勢を保持。入力/エンジン例外は隠さない');

  // 同じ本体へ速度異常を注入した一時コピーで、thread/HTTP/controller/checkpointを通す。
  const source=await fs.readFile(new URL('./physics.mjs',import.meta.url),'utf8'),point='world.step(DT,8,3);time=step*DT;';
  assert.equal(source.split(point).length,2);
  await fs.writeFile(path.join(root,'physics.mjs'),source.replace(point,"world.step(DT,8,3);if(genome[0]===0.3&&step===14){chassis.m_linearVelocity.x=81;chassis.m_xf.p.x=10000;}time=step*DT;"));
  await fs.mkdir(path.join(root,'vendor'));await fs.writeFile(path.join(root,'vendor/planck.mjs'),'export * from '+JSON.stringify(new URL('./vendor/planck.mjs',import.meta.url).href)+';');
  for(const file of ['pool.mjs','worker.mjs','evaluator-thread.mjs','controller.mjs','evolution.mjs'])await fs.copyFile(new URL('./'+file,import.meta.url),path.join(root,file));
  const load=file=>import(pathToFileURL(path.join(root,file)).href),physics=await load('physics.mjs'),network=await load('worker.mjs'),threads=await load('pool.mjs'),{EvolutionController}=await load('controller.mjs');
  const bad=[...probe];bad[0]=.3;const population=[bad,...initialPopulation(2027,6).slice(0,5)],expected=population.map(genome=>physics.simulate(genome));
  assert.equal(expected[0].reason,'unstable');
  const local=await threads.createPool({workers:2});pools.push(local);
  const logs=[],url=await listen(network.createWorker({workerId:'injected',log:line=>logs.push(JSON.parse(line))})),remote=await pool({urls:[url]});
  assert.deepEqual(await local.evaluate(population,2026,'thread'),expected);assert.deepEqual(await remote.evaluate(population,2026,'http'),expected);
  assert.equal(logs.length,1);assert.equal(logs[0].candidateId,0);assert.deepEqual(logs[0].genome,bad);assert.equal(logs[0].instability.code,'speed-limit');
  const repeated=await fetch(url+'/evaluate',{method:'POST',body:JSON.stringify({runId:'http',id:0,genome:bad,seed:2026,courseProfile:'rolling-v1',durationSeconds:DURATION})}).then(r=>r.json());
  assert.equal(repeated.cached,true);assert.equal(logs.length,1);assert.deepEqual(repeated.result,expected[0]);
  const invalid=await fetch(url+'/evaluate',{method:'POST',body:JSON.stringify({genome:[]})});assert.equal(invalid.status,400);assert.equal((await invalid.json()).code,'invalid-request');
  const broken=await listen(network.createWorker({workerId:'broken',simulateTask:()=>{throw Error('engine-bug');}}));
  const failed=await fetch(broken+'/evaluate',{method:'POST',body:JSON.stringify({runId:'bug',id:0,genome:probe,seed:2026})});assert.equal(failed.status,500);assert.equal((await failed.json()).code,'evaluation-error');
  const options={pool:local,populationSize:6,generations:3,runs:0,delayMs:3600000,holdMs:3600000,stateFile:path.join(root,'state.json')};
  const controller=new EvolutionController(options);controllers.push(controller);controller.population=population;
  for(let i=0;i<3;i++)await controller.step();
  assert.equal(controller.running,true);assert.equal(controller.phase,'between-runs');assert.equal(controller.ranking.evaluated,18);assert.ok(controller.diagnostics.unstableEvaluations>=1);assert.ok(controller.diagnostics.recent.length<=6);
  const selected=controller.replayForCar(controller.ranking.worst[0]?.id??controller.ranking.best[0].id);assert.ok(selected.champion.frames.every(f=>f.body.every(Number.isFinite)));
  const saved=JSON.parse(await fs.readFile(controller.file));assert.equal(saved.stateSchema,5);assert.equal(saved.instabilityPolicy,INSTABILITY_POLICY);
  const restored=new EvolutionController(options);controllers.push(restored);await restored.restore();assert.deepEqual(restored.diagnostics,controller.diagnostics);assert.equal(restored.comparison.id,controller.comparison.id);
  await restored.step();assert.equal(restored.generation,0);assert.equal(restored.error,null);assert.equal(restored.ranking.evaluated,24);
  const old={...saved,stateSchema:4};delete old.diagnostics;delete old.instabilityPolicy;
  // 既存の正常な形式4を引き継げることは、異常車体を含まない独立保存で確認する。
  const normal=new EvolutionController({...options,stateFile:path.join(root,'normal.json')});controllers.push(normal);await normal.step();
  const legacy=JSON.parse(await fs.readFile(normal.file));legacy.stateSchema=4;delete legacy.instabilityPolicy;delete legacy.diagnostics;await fs.writeFile(normal.file,JSON.stringify(legacy));
  const migration=new EvolutionController({...options,stateFile:normal.file});controllers.push(migration);await migration.restore();assert.equal(migration.comparison.id,normal.comparison.id);assert.equal(migration.diagnostics.unstableEvaluations,0);
  console.log('PASS: 発散を含む直接/thread/HTTP・重複キャッシュ・候補診断・世代/試行継続・形式5保存復帰・旧形式4の引継ぎ');

  const health={status:'ok',workerId:'fake',version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,courseProfiles:COURSE_PROFILES};
  const oldUrl=await listen(http.createServer((req,res)=>res.end(JSON.stringify({...health,instabilityPolicy:undefined}))));await assert.rejects(createPool({urls:[oldUrl]}),/worker/);
  for(const change of [{workerId:'spoofed'},{instabilityPolicy:'unknown'},{result:{...expected[0],instability:{...expected[0].instability,detectedAt:0}}},{result:{...expected[0],distance:NaN}}]){
    const wrong=await listen(http.createServer((req,res)=>{if(req.url==='/health')return res.end(JSON.stringify(health));let raw='';req.on('data',d=>raw+=d);req.on('end',()=>res.end(JSON.stringify({...JSON.parse(raw),...health,result:expected[0],...change})));}));
    const wrongPool=await pool({urls:[wrong]});await assert.rejects(wrongPool.evaluate([bad],2026,'invalid'));
  }
  assert.throws(()=>validateResult({...expected[0],reason:'time'}));assert.throws(()=>validateResult({...expected[0],score:160}));
  console.log('PASS: 旧方針/worker偽装/不正な発散結果は停止し、正当な発散終了だけ継続する');
}finally {
  World.prototype.step=originalStep;for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await Promise.all(pools.map(p=>p.close()));await Promise.all(servers.map(s=>new Promise(r=>{s.closeAllConnections();s.close(r);})));
  await fs.rm(root,{recursive:true,force:true});
}
