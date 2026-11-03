import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {VERSION,DURATION,INSTABILITY_POLICY,COURSE_PROFILES,simulate} from './physics.mjs';
import {initialPopulation} from './evolution.mjs';
import {createPool} from './pool.mjs';
import {createWorker} from './worker.mjs';
import {EvolutionController} from './controller.mjs';
assert.equal(VERSION,'vehicle-2');assert.equal(DURATION,30);
const profile='obstacles-55-7p5-v1',population=initialPopulation(2026,36,{strategy:'profile-v2'});
let probe,expected;
for(const genome of population){const result=simulate(genome,{courseProfile:profile,frames:true});if(result.reason==='time'){probe=genome;expected=result;break;}}
assert.ok(probe,'30秒まで走る実車体が必要');assert.equal(expected.elapsed,30);assert.equal(expected.frames.at(-1).t,30);
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-duration-')),servers=[],pools=[],controllers=[];
const listen=async server=>{servers.push(server);await new Promise(r=>server.listen(0,'127.0.0.1',r));return 'http://127.0.0.1:'+server.address().port;};
const pool=async opts=>{const p=await createPool(opts);pools.push(p);return p;};
const controller=opts=>{const c=new EvolutionController({populationSize:6,generations:1,courseProfile:profile,delayMs:3600000,stateFile:path.join(dir,'new.json'),...opts});controllers.push(c);return c;};
try {
  const url=await listen(createWorker({workerId:'duration-test'})),health=await fetch(url+'/health').then(r=>r.json());assert.equal(health.durationSeconds,30);assert.equal(health.version,VERSION);
  const local=await pool({workers:1}),remote=await pool({urls:[url]});
  const a=await local.evaluate([probe],2026,'duration-local',()=>{},{courseProfile:profile}),b=await remote.evaluate([probe],2026,'duration-remote',()=>{},{courseProfile:profile});assert.deepEqual(a,b);
  const {frames,...plain}=expected;assert.deepEqual(a,[plain]);
  const response=await fetch(url+'/evaluate',{method:'POST',body:JSON.stringify({runId:'wrong-time',id:0,seed:2026,genome:probe,courseProfile:profile,durationSeconds:16})});assert.equal(response.status,400);
  for(const [version,durationSeconds] of [['vehicle-1',16],[VERSION,16]]) {
    const old=await listen(http.createServer((req,res)=>res.end(JSON.stringify({status:'ok',workerId:'old',version,durationSeconds,courseProfiles:COURSE_PROFILES}))));
    await assert.rejects(createPool({urls:[old]}),/workerを確認できません/);
  }
  const wrong=await listen(http.createServer((req,res)=>{
    if(req.url==='/health')res.end(JSON.stringify({...health,workerId:'wrong'}));
    else {let raw='';req.on('data',d=>raw+=d);req.on('end',()=>res.end(JSON.stringify({...JSON.parse(raw),version:VERSION,durationSeconds:16,result:plain})));}
  }));
  const wrongPool=await pool({urls:[wrong]});await assert.rejects(wrongPool.evaluate([probe],2026,'wrong-response',()=>{},{courseProfile:profile}),/一致しません/);
  console.log('PASS: 30秒実計算・最終フレーム・直接/スレッド/HTTP一致・旧版/異時間worker拒否');
  const c=controller({pool:local});await c.step();clearTimeout(c.timer);c.timer=null;assert.equal(c.error,null);
  assert.equal(c.snapshot().durationSeconds,30);assert.equal(c.replay.durationSeconds,30);assert.equal(c.replay.version,VERSION);
  const saved=JSON.parse(await fs.readFile(c.file,'utf8'));assert.equal(saved.durationSeconds,30);
  const restored=controller({pool:local});await restored.restore();const {key:restoredKey,...restoredReplay}=restored.replay,{key:oldKey,...originalReplay}=c.replay;assert.deepEqual(restoredReplay,originalReplay);
  await fs.writeFile(path.join(dir,'old.json'),JSON.stringify({...saved,version:'vehicle-1',durationSeconds:16}));await assert.rejects(controller({pool:local,stateFile:path.join(dir,'old.json')}).restore(),/走行時間|条件/);
  const legacy={...saved,version:'vehicle-1'};delete legacy.durationSeconds;
  await fs.writeFile(path.join(dir,'legacy.json'),JSON.stringify(legacy));await assert.rejects(controller({pool:local,stateFile:path.join(dir,'legacy.json')}).restore(),/条件/);
  await fs.writeFile(path.join(dir,'wrong.json'),JSON.stringify({...saved,durationSeconds:16}));await assert.rejects(controller({pool:local,stateFile:path.join(dir,'wrong.json')}).restore(),/走行時間/);
  console.log('PASS: 30秒の保存/再生復帰と時間メタデータ・16秒の保存混入拒否');
}finally {
  for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await Promise.all(pools.map(p=>p.close()));await Promise.all(servers.map(s=>new Promise(r=>{s.close(r);s.closeAllConnections();})));await fs.rm(dir,{recursive:true,force:true});
}
