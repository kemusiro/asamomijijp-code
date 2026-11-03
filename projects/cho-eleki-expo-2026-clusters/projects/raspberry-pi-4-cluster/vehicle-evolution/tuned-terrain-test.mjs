import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {makeCourse,simulate,COURSE_PROFILES} from './physics.mjs';
import {initialPopulation} from './evolution.mjs';
import {createPool} from './pool.mjs';
import {createWorker} from './worker.mjs';
import {EvolutionController} from './controller.mjs';
import {raceView} from './draw.mjs';
const profile='obstacles-55-7p5-v1',road=makeCourse(2026,profile),heights=new Map(road);
const slope=Math.tan(55*Math.PI/180);
const expected=[[21,-.5],[24,0],[27,3*slope],[30,4.5*slope],[33,4.5*slope],[36,1.5*slope],[39,0],[42,0],[45,-3.75],[48,-7.5],[51,-7.5],[54,-3.75],[57,0],[60,0]];
assert.deepEqual(road.filter(([x])=>x>=21&&x<=60),expected);
assert.ok(Math.abs(Math.atan((heights.get(27)-heights.get(24))/3)*180/Math.PI-55)<1e-12);
assert.deepEqual(makeCourse(2026,'obstacles-v1').filter(([x])=>[30,48,51].includes(x)),[[30,4.5],[48,-6],[51,-6]]);
assert.deepEqual(road.filter(([x])=>x<21||x>60),makeCourse(2026).filter(([x])=>x<21||x>60));
for(const x of [24,30,42,48,51,57]) {
  const view=raceView(road,[x,heights.get(x)+1],[x,heights.get(x)],1200,420);
  for(const [px,py] of road.filter(([px])=>px>=view.camera&&px<=view.camera+view.span)) {
    const y=420*.47-(py-view.centerY)*view.scale;assert.ok(y>0&&y<420);
  }
}
// Pythonがある開発機ではPicoホストの元地形を全点照合。Pi4コンテナでは明示的に省略する。
const python=spawnSync('python3',['-B','-c',"import sys,json;sys.path.insert(0,sys.argv[1]);from course_scene import make_course;print(json.dumps(make_course(2026,sys.argv[2])))",fileURLToPath(new URL('../../raspberry-pi-pico-cluster/raytracing/host',import.meta.url)),profile],{encoding:'utf8'});
if(python.error?.code==='ENOENT')console.log('SKIP: Pi4/Pico元地形照合（Python未導入）');
else {assert.equal(python.status,0,python.stderr);const actual=JSON.parse(python.stdout);assert.equal(actual.length,road.length);actual.forEach((p,i)=>p.forEach((v,j)=>assert.ok(Math.abs(v-road[i][j])<1e-12)));console.log('PASS: Pi4/Pico元地形の全点一致');}
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-tuned-')),worker=createWorker({workerId:'tuned-test'}),pools=[],controllers=[];
const make=(pool,opts={})=>{const c=new EvolutionController({pool,populationSize:6,generations:2,delayMs:3600000,holdMs:3600000,courseProfile:profile,runs:0,stateFile:path.join(dir,'new.json'),...opts});controllers.push(c);return c;};
try {
  await new Promise(r=>worker.listen(0,'127.0.0.1',r));const url='http://127.0.0.1:'+worker.address().port;
  const health=await fetch(url+'/health').then(r=>r.json());assert.deepEqual(health.courseProfiles,COURSE_PROFILES);
  const local=await createPool({workers:1});pools.push(local);const remote=await createPool({urls:[url]});pools.push(remote);
  const population=initialPopulation(2026,6,{strategy:'profile-v2'});
  const a=await local.evaluate(population,2026,'tuned-local',()=>{},{courseProfile:profile});
  assert.deepEqual(await remote.evaluate(population,2026,'tuned-http',()=>{},{courseProfile:profile}),a);
  assert.deepEqual(a,population.map(g=>simulate(g,{courseProfile:profile})));
  const c=make(remote);await c.step();clearTimeout(c.timer);c.timer=null;assert.equal(c.error,null);
  assert.deepEqual(c.replay.course,road);assert.equal(c.snapshot().courseProfile,profile);
  const selected=c.replayForCar(c.ranking.best[0].id);assert.equal(selected.courseProfile,profile);
  assert.deepEqual(selected.champion.frames,simulate(selected.champion.genome,{courseProfile:profile,frames:true}).frames);
  const restored=make(local,{courseProfile:'rolling-v1'});await restored.restore();assert.equal(restored.courseProfile,profile);assert.deepEqual(restored.replay.course,road);
  console.log('PASS: 校正済み点列・旧地形保持・谷の画角・直接/スレッド/HTTP一致・保存/選択再生の新profile一致');
}finally {
  for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await Promise.all(pools.map(p=>p.close()));await new Promise(r=>{worker.close(r);worker.closeAllConnections();});await fs.rm(dir,{recursive:true,force:true});
}
