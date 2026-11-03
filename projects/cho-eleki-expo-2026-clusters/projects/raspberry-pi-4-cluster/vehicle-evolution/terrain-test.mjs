import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {makeCourse,simulate,random,VERSION,DURATION,INSTABILITY_POLICY,COURSE_PROFILES} from './physics.mjs';
import {initialPopulation} from './evolution.mjs';
import {createPool} from './pool.mjs';
import {createWorker} from './worker.mjs';
import {EvolutionController,comparisonOptions} from './controller.mjs';
import {parseOptions,createServer} from './server.mjs';
import {raceView} from './draw.mjs';
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-terrain-')),pools=[],servers=[],controllers=[];
const listen=async s=>{servers.push(s);await new Promise(r=>s.listen(0,'127.0.0.1',r));return 'http://127.0.0.1:'+s.address().port;};
const pool=async o=>{const p=await createPool(o);pools.push(p);return p;};
const make=o=>{const c=new EvolutionController({pool:o.pool,populationSize:6,generations:3,delayMs:3600000,holdMs:3600000,...o});controllers.push(c);return c;};
try {
  const oldCourse=seed=>{const rng=random(seed),points=[[-8,0],[0,0],[6,0]];for(let x=9;x<=172;x+=3)points.push([x,Math.min(1,(x-6)/28)*(3.1*Math.sin(x*.18)+1.4*Math.sin(x*.53)+(rng()-.5)*1.6)]);return points;};
  for(const seed of [0,2026,2147483647]) {
    assert.deepEqual(makeCourse(seed),oldCourse(seed));
    const road=makeCourse(seed,'obstacles-v1');assert.deepEqual(road,makeCourse(seed,'obstacles-v1'));
    assert.ok(road.every(([x,y],i)=>Number.isFinite(y)&&(!i||x>road[i-1][0])));
    assert.deepEqual(road.filter(([x])=>x<21||x>60),oldCourse(seed).filter(([x])=>x<21||x>60));
    const y=x=>road.find(p=>p[0]===x)[1];assert.equal(y(30),4.5);assert.equal(y(48),-6);assert.equal(y(51),-6);assert.equal((y(27)-y(24))/3,1);assert.equal((y(57)-y(54))/3,1);
    for(const x of [0,20,30,45,49,55,80]) {
      const view=raceView(road,[x,2],[x,-5],1200,420);
      for(const [px,py] of road.filter(([px])=>px>=view.camera&&px<=view.camera+view.span)){
        const screenY=420*.47-(py-view.centerY)*view.scale;assert.ok(screenY>0&&screenY<420,JSON.stringify({x,px,py,screenY}));
      }
    }
  }
  assert.throws(()=>makeCourse(2026,'bad'));assert.throws(()=>comparisonOptions({courseProfile:'bad'}));assert.throws(()=>parseOptions(['--course-profile','bad']));assert.equal(parseOptions(['--course-profile','obstacles-v1']).courseProfile,'obstacles-v1');
  console.log('PASS: 旧地形の完全一致・急坂45度/谷深さ6m・連続地面・谷底の画角・種別検証');
  const local=await pool({workers:2}),url=await listen(createWorker({workerId:'terrain-test'})),remote=await pool({urls:[url]});
  const population=initialPopulation(2026,6,{strategy:'profile-v2'});
  const a=await local.evaluate(population,2026,'terrain-local',()=>{},{courseProfile:'obstacles-v1'});
  const b=await remote.evaluate(population,2026,'terrain-remote',()=>{},{courseProfile:'obstacles-v1'});
  assert.deepEqual(a,b);assert.deepEqual(a,population.map(g=>simulate(g,{seed:2026,courseProfile:'obstacles-v1'})));
  assert.notDeepEqual(a,population.map(g=>simulate(g,{seed:2026})));
  const post=t=>fetch(url+'/evaluate',{method:'POST',body:JSON.stringify(t)}),task={runId:'terrain-cache',id:0,seed:2026,genome:population[0]};
  assert.equal((await post(task)).status,200);assert.equal((await post({...task,courseProfile:'obstacles-v1'})).status,409);assert.equal((await post({...task,runId:'bad',courseProfile:'bad'})).status,400);
  const legacyUrl=await listen(http.createServer((req,res)=>res.end(JSON.stringify({version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,workerId:'old'}))));
  await assert.rejects(createPool({urls:[legacyUrl]}),/workerを確認できません/);
  const wrongUrl=await listen(http.createServer((req,res)=>{res.setHeader('content-type','application/json');if(req.url==='/health')res.end(JSON.stringify({version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,workerId:'wrong',courseProfiles:COURSE_PROFILES}));else{let raw='';req.on('data',d=>raw+=d);req.on('end',()=>res.end(JSON.stringify({...JSON.parse(raw),version:VERSION,durationSeconds:DURATION,workerId:'wrong',instabilityPolicy:INSTABILITY_POLICY,courseProfile:'rolling-v1',result:a[0]})));}}));
  const wrong=await pool({urls:[wrongUrl]});await assert.rejects(wrong.evaluate(population.slice(0,1),2026,'wrong',()=>{},{courseProfile:'obstacles-v1'}),/一致しません/);
  console.log('PASS: 直接/スレッド/HTTPの新地形評価一致・キャッシュ衝突拒否・旧worker/異種別応答の拒否');
  const c=make({pool:local,courseProfile:'obstacles-v1',runs:0,stateFile:path.join(dir,'terrain.json')});await c.step();clearTimeout(c.timer);c.timer=null;
  assert.equal(c.error,null);assert.equal(c.snapshot().courseProfile,'obstacles-v1');assert.deepEqual(c.replay.course,makeCourse(2026,'obstacles-v1'));
  const selected=c.replayForCar(c.ranking.best[0].id);assert.equal(selected.courseProfile,'obstacles-v1');assert.deepEqual(selected.champion.frames,simulate(selected.champion.genome,{seed:2026,courseProfile:'obstacles-v1',frames:true}).frames);
  const restored=make({pool:local,stateFile:c.file});await restored.restore();assert.equal(restored.courseProfile,'obstacles-v1');assert.deepEqual(restored.replay.course,c.replay.course);
  await c.step();clearTimeout(c.timer);c.timer=null;await restored.step();clearTimeout(restored.timer);restored.timer=null;assert.deepEqual(c.population,restored.population);assert.deepEqual(c.history,restored.history);
  const rolling=make({pool:local,stateFile:path.join(dir,'rolling.json')});
  const saveRolling=rolling.save.bind(rolling);rolling.save=async()=>{rolling.control('pause');await saveRolling();};
  await rolling.step();assert.equal(rolling.phase,'paused');assert.equal(rolling.running,false);clearTimeout(rolling.timer);rolling.timer=null;
  const old=JSON.parse(await fs.readFile(rolling.file,'utf8'));old.stateSchema=3;delete old.courseProfile;for(const group of ['best','worst'])for(const car of old.ranking[group])delete car.courseProfile;
  await fs.writeFile(rolling.file,JSON.stringify(old));const oldRestored=make({pool:local,courseProfile:'obstacles-v1',stateFile:rolling.file});await oldRestored.restore();assert.equal(oldRestored.courseProfile,'rolling-v1');assert.deepEqual(oldRestored.replay.course,makeCourse(2026));
  const missing=JSON.parse(await fs.readFile(c.file,'utf8'));delete missing.courseProfile;await fs.writeFile(path.join(dir,'missing.json'),JSON.stringify(missing));await assert.rejects(make({pool:local,stateFile:path.join(dir,'missing.json')}).restore(),/コース種別/);
  const bad=JSON.parse(await fs.readFile(c.file,'utf8'));bad.ranking.best[0].courseProfile='rolling-v1';await fs.writeFile(path.join(dir,'bad.json'),JSON.stringify(bad));await assert.rejects(make({pool:local,stateFile:path.join(dir,'bad.json')}).restore(),/出所/);
  const app=await listen(createServer(c));assert.equal((await fetch(app+'/api/state').then(r=>r.json())).courseProfile,'obstacles-v1');assert.equal((await fetch(app+'/api/control',{method:'POST',body:JSON.stringify({action:'compare',courseProfile:'bad'})})).status,400);
  const experiment=c.comparison.id;c.control('compare',undefined,{courseProfile:'rolling-v1'});await c.step();clearTimeout(c.timer);c.timer=null;assert.equal(c.courseProfile,'rolling-v1');assert.notEqual(c.comparison.id,experiment);assert.equal(c.ranking.evaluated,6);assert.throws(()=>c.replayForCar(selected.carId),/選び直して/);
  console.log('PASS: 新旧保存復帰・再生/ランキングの地形整合・不正出所拒否・コース切替で実験とランキングを更新');
}finally {
  for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await Promise.all(pools.map(p=>p.close()));await Promise.all(servers.map(s=>new Promise(r=>{s.close(r);s.closeAllConnections();})));await fs.rm(dir,{recursive:true,force:true});
}
