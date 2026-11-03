import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {VERSION,DT,DURATION,INSTABILITY_POLICY,BOUNDS,COURSE_PROFILES,random,simulate,makeCourse,validateGenome} from './physics.mjs';
import {initialPopulation,nextPopulation} from './evolution.mjs';
import {createPool} from './pool.mjs';
import {createWorker} from './worker.mjs';
import {EvolutionController} from './controller.mjs';
import {createServer,parseOptions} from './server.mjs';
import {frameAt} from './draw.mjs';
import {runBudget} from './benchmark.mjs';

const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-evolution-test-')),servers=[],pools=[],controllers=[];
async function listen(server){servers.push(server);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));return 'http://127.0.0.1:'+server.address().port;}
async function pool(options){const p=await createPool(options);pools.push(p);return p;}
try {
  const population=initialPopulation(2026,36);assert.deepEqual(population,initialPopulation(2026,36));assert.notDeepEqual(makeCourse(1),makeCourse(2));
  const probe=population[5],a=simulate(probe,{frames:true}),b=simulate(probe,{frames:true});assert.deepEqual(a,b);
  assert.ok(a.frames.length>10);assert.ok(a.frames.every(f=>[...f.body,...f.wheels.flat()].every(Number.isFinite)));
  assert.equal(a.frames[0].body[1],2);assert.ok(a.frames.some(f=>f.body[1]<1.9),'重力で落下して接地する');
  assert.ok(simulate(probe).distance>simulate(probe,{motor:false}).distance+5,'推進力は車輪モーターから得る');
  assert.deepEqual(frameAt(a.frames,100),a.frames.at(-1));assert.ok(Number.isFinite(frameAt(a.frames,.05).body[0]));
  assert.throws(()=>validateGenome(Array(13).fill(NaN)));assert.throws(()=>initialPopulation(1,10000));
  const rng=random(777),r1=rng();const resume=random(rng.state());assert.equal(rng(),resume());assert.ok(Number.isFinite(r1));
  console.log('PASS: 物理の決定性・重力/接地/モーター・遺伝子範囲・再生補間');

  const serial=await pool({workers:1}),parallel=await pool({workers:3}),events=[];
  const one=await serial.evaluate(population.slice(0,9),2026,'serial'),many=await parallel.evaluate(population.slice(0,9),2026,'parallel',e=>events.push(e));
  assert.deepEqual(one,many);assert.equal(events.filter(e=>e.status==='done').length,9);assert.ok(events.every(e=>parallel.ids.includes(e.workerId)));
  const urls=await Promise.all([0,1,2].map(i=>listen(createWorker({workerId:'test-'+i}))));
  const remote=await pool({urls}),network=await remote.evaluate(population.slice(0,9),2026,'network');assert.deepEqual(one,network);
  const task={runId:'cache',id:0,seed:2026,genome:probe};
  const post=body=>fetch(urls[0]+'/evaluate',{method:'POST',body:JSON.stringify(body)});
  assert.equal((await post(task)).status,200);assert.equal((await post(task).then(r=>r.json())).cached,true);
  assert.equal((await post({...task,seed:2})).status,409);assert.equal((await post({...task,genome:[]})).status,400);
  const unavailable=await listen(http.createServer((req,res)=>req.url==='/health'?(res.writeHead(200),res.end(JSON.stringify({workerId:'blocked',version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,courseProfiles:COURSE_PROFILES}))):undefined));
  const blocked=await pool({urls:[unavailable],timeoutMs:100});await assert.rejects(blocked.evaluate([probe],2026,'timeout'),/失敗/);
  console.log('PASS: 1/3スレッド/HTTP評価の一致・正しい候補順・重複排除・不正要求・timeout');
  const budgetMs=Number(process.env.VEHICLE_TEST_BUDGET_MS??500);
  const budget=await runBudget(parallel,{budgetMs,seed:2026,populationSize:12});
  assert.ok(budget.evaluatedCount>0);assert.equal(budget.evaluatedCount,budget.events.filter(e=>e.withinBudget).length);assert.ok(budget.events.filter(e=>e.withinBudget).every(e=>e.finishedAtMs<=budgetMs));
  console.log('PASS: 時間予算内の候補だけを集計・終了時の残評価を分離');

  const options={pool:parallel,seed:2026,populationSize:12,generations:12,delayMs:3600000};
  const c=new EvolutionController({...options,stateFile:path.join(temporary,'state.json')});controllers.push(c);
  await c.step();assert.equal(c.generation,0);assert.equal(c.evaluated,12);assert.equal(c.completedCandidates,12);assert.ok(c.workers.every(w=>parallel.ids.includes(w.id)));
  c.control('pause');await c.step();assert.equal(c.generation,0);assert.equal(c.phase,'paused');
  c.control('resume');await c.step();assert.equal(c.generation,1);
  const checkpoint=await fs.readFile(c.file);await c.step();const expected=structuredClone({population:c.population,history:c.history,champion:c.champion});
  await fs.writeFile(c.file,checkpoint);
  const restored=new EvolutionController({...options,seed:999,stateFile:c.file});controllers.push(restored);await restored.restore();assert.equal(restored.seed,2026);assert.equal(restored.workers.reduce((sum,w)=>sum+w.count,0),24);await restored.step();
  assert.equal(restored.workers.reduce((sum,w)=>sum+w.count,0),36);
  assert.deepEqual({population:restored.population,history:restored.history,champion:restored.champion},expected,'保存と再起動後も同じ探索へ進む');
  for(let i=0;i<9;i++)await c.step();assert.equal(c.phase,'complete');assert.ok(c.history.every((h,i)=>i===0||h.distance>=c.history[i-1].distance));assert.ok(c.champion.distance>c.initial.distance+5,'実際の進化で初代最良から改善する');
  const latestReplay=c.replay,historyBefore=structuredClone(c.history),evaluatedBefore=c.evaluated,oldSession=c.session;
  const selected=c.replayForGeneration(3),ancestor=c.milestones.find(car=>car.generation===3);
  assert.equal(selected.champion.generation,3);assert.deepEqual(selected.champion.genome,ancestor.genome);
  assert.deepEqual(selected.champion.frames,simulate(ancestor.genome,{seed:c.seed,frames:true}).frames);
  assert.equal(c.replayForGeneration(3),selected,'同じ世代は保存フレームを再利用する');
  assert.equal(c.replayForGeneration(0).champion,c.replay.initial);
  assert.equal(c.replay,c.replayForGeneration(c.champion.generation));assert.equal(c.replay,latestReplay);
  assert.deepEqual(c.history,historyBefore);assert.equal(c.evaluated,evaluatedBefore);
  for(const generation of [-1,1.5,2,999,NaN])assert.throws(()=>c.replayForGeneration(generation));
  console.log('PASS: 系譜の世代別走行・フレーム一致・再利用・探索と自動再生への非干渉');
  c.control('reset',2027);await c.step();assert.equal(c.seed,2027);assert.equal(c.generation,0);assert.equal(c.evaluated,12);
  assert.equal(c.selectedReplays.size,0,'seedリセット時に世代別走行を破棄する');
  await fs.writeFile(path.join(temporary,'bad.json'),'invalid');const bad=new EvolutionController({...options,stateFile:path.join(temporary,'bad.json')});await assert.rejects(bad.restore(),/退避/);
  console.log('PASS: 選択/交叉/突然変異/エリート・探索改善・停止/再開/seedリセット・checkpoint完全復帰');

  const app=await listen(createServer(c));
  for(const asset of ['/','/app.mjs','/style.css','/draw.mjs','/physics.mjs','/vendor/planck.mjs','/vendor/PLANCK-LICENSE.txt','/health','/api/state','/api/replay'])assert.equal((await fetch(app+asset)).status,200,asset);
  const selectedResponse=await fetch(app+'/api/replay?generation=0&session='+c.session);assert.equal(selectedResponse.status,200);
  const selectedBody=await selectedResponse.json();assert.equal(selectedBody.champion.generation,0);assert.equal(selectedBody.seed,2027);
  assert.equal((await fetch(app+'/api/replay?generation=0&session='+oldSession)).status,409);
  assert.equal((await fetch(app+'/api/replay?generation=0')).status,409);
  for(const generation of ['','-1','1.5','3','abc'])assert.equal((await fetch(app+'/api/replay?generation='+generation+'&session='+c.session)).status,400);
  assert.equal((await fetch(app+'/unknown')).status,404);
  assert.equal((await fetch(app+'/api/control',{method:'POST',body:'{"action":"wrong"}'})).status,400);
  assert.equal((await fetch(app+'/api/control',{method:'POST',headers:{Origin:'http://unrelated.test'},body:'{"action":"pause"}'})).status,403);
  assert.equal((await fetch(app+'/api/control',{method:'POST',body:'{"action":"pause"}'})).status,200);
  assert.equal((await fetch(app+'/api/state').then(r=>r.json())).running,false);
  assert.throws(()=>parseOptions(['--workers','0']));assert.throws(()=>parseOptions(['--worker-urls','http://a','--workers','2']));
  console.log('PASS: 全表示資材の配信・API操作・同一origin制限・CLI検証');
}finally {
  for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await Promise.all(pools.map(p=>p.close()));
  await Promise.all(servers.map(s=>new Promise(resolve=>{s.closeAllConnections();s.close(resolve);})));
  await fs.rm(temporary,{recursive:true,force:true});
}
