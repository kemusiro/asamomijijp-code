import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {EvolutionController,comparisonOptions} from './controller.mjs';
import {createPool} from './pool.mjs';
import {makeCourse} from './physics.mjs';
import {createServer,parseOptions} from './server.mjs';

const dir=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-comparison-')),pool=await createPool({workers:2}),controllers=[];
const options={pool,courseSeed:2026,populationSeed:2026,runs:2,populationSize:6,generations:3,strategy:'legacy',delayMs:3600000,holdMs:3600000};
const make=extra=>{const c=new EvolutionController({...options,...extra});controllers.push(c);return c;};
const results=c=>c.comparison.results.map(({evaluationMs,...r})=>r);
let server;
try {
  const a=make(),b=make({populationSeed:2027});
  assert.deepEqual(makeCourse(a.courseSeed),makeCourse(b.courseSeed));assert.notDeepEqual(a.population,b.population);
  assert.equal(a.rng.state(),b.rng.state());assert.equal(a.evolutionSeed,2027);
  for(let i=0;i<3;i++){await a.step();await b.step();assert.equal(a.rng.state(),b.rng.state());assert.deepEqual(a.replay.course,b.replay.course);}
  const c=make({stateFile:path.join(dir,'state.json')});
  for(let i=0;i<3;i++)await c.step();
  assert.equal(c.phase,'between-runs');assert.equal(c.comparison.results.length,1);assert.equal(c.comparison.runIndex,0);
  const checkpoint=await fs.readFile(c.file),first=structuredClone(c.comparison.results[0]);
  c.control('pause');await c.step();assert.equal(c.comparison.runIndex,0);assert.equal(c.phase,'paused');
  c.control('resume');await c.step();assert.equal(c.populationSeed,2027);assert.equal(c.courseSeed,2026);assert.equal(c.generation,0);assert.equal(c.evaluated,6);
  assert.deepEqual(c.comparison.results[0],first);
  for(let i=0;i<2;i++)await c.step();assert.equal(c.phase,'complete');assert.equal(c.comparison.results.length,2);
  assert.ok(c.comparison.results.every(r=>r.generations===3&&r.populationSize===6&&r.courseSeed===2026&&r.evolutionSeed===2027&&r.evaluated===18));
  assert.deepEqual(c.comparison.results.map(r=>r.populationSeed),[2026,2027]);assert.notDeepEqual(c.comparison.results[0].initial.genome,c.comparison.results[1].initial.genome);
  await fs.writeFile(c.file,checkpoint);
  const restored=make({stateFile:c.file,courseSeed:99,populationSeed:99,runs:1,generations:10});await restored.restore();
  assert.equal(restored.phase,'between-runs');assert.equal(restored.limit,3);assert.equal(restored.comparison.totalRuns,2);
  for(let i=0;i<3;i++)await restored.step();assert.equal(restored.phase,'complete');assert.deepEqual(results(restored),results(c));
  // 試行内でも保存した乱数状態から同じ探索へ進む。
  await fs.writeFile(c.file,checkpoint);const mid=make({stateFile:c.file});await mid.restore();await mid.step();const midCheckpoint=await fs.readFile(c.file);await mid.step();await mid.step();
  await fs.writeFile(c.file,midCheckpoint);const resumed=make({stateFile:c.file});await resumed.restore();await resumed.step();await resumed.step();assert.deepEqual(results(mid),results(resumed));
  // 旧形式の単一seed保存を読み込んでも条件と履歴を保つ。
  const legacy=JSON.parse(checkpoint);for(const key of ['stateSchema','courseSeed','populationSeed','limit','comparison','evaluationMs','strategy','stagnation','ranking'])delete legacy[key];
  await fs.writeFile(c.file,JSON.stringify(legacy));const old=make({stateFile:c.file,generations:3});await old.restore();assert.equal(old.courseSeed,2026);assert.equal(old.populationSeed,2026);assert.equal(old.phase,'complete');assert.equal(old.comparison.totalRuns,1);
  const unknown=JSON.parse(checkpoint);unknown.stateSchema=999;await fs.writeFile(c.file,JSON.stringify(unknown));await assert.rejects(make({stateFile:c.file}).restore(),/未対応/);
  const corrupt=JSON.parse(checkpoint);corrupt.comparison.results[0].courseSeed=9;await fs.writeFile(c.file,JSON.stringify(corrupt));await assert.rejects(make({stateFile:c.file}).restore(),/条件/);
  for(const config of [{runs:-1},{runs:9},{populationSeed:2147483647,runs:2},{courseSeed:-1},{generations:0}])assert.throws(()=>comparisonOptions(config));
  assert.equal(parseOptions(['--course-seed','10','--population-seed','20','--runs','3']).populationSeed,20);assert.throws(()=>parseOptions(['--seed','1','--course-seed','2']));
  server=createServer(a);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url='http://127.0.0.1:'+server.address().port;
  const post=body=>fetch(url+'/api/control',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  assert.equal((await post({action:'compare',courseSeed:44,populationSeed:100,runs:2,generations:4})).status,200);await a.step();
  assert.equal(a.courseSeed,44);assert.equal(a.populationSeed,100);assert.equal(a.limit,4);assert.equal(a.comparison.totalRuns,2);
  const session=a.session;assert.equal((await post({action:'compare',courseSeed:1,populationSeed:2147483647,runs:2,generations:4})).status,400);assert.equal(a.session,session);
  console.log('PASS: 固定コース・固定進化乱数・異なる初期集団・同一条件の複数試行・停止再開・試行間/試行内の完全復帰・旧形式移行・不正条件拒否・操作API');
}finally {
  for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await pool.close();if(server)await new Promise(resolve=>{server.closeAllConnections();server.close(resolve);});await fs.rm(dir,{recursive:true,force:true});
}
