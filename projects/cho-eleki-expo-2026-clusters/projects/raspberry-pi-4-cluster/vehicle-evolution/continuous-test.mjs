import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {initialPopulation,nextPopulation,mutationPlan} from './evolution.mjs';
import {random,validateGenome,simulate,makeCourse} from './physics.mjs';
import {EvolutionController,comparisonOptions,RECENT_RUN_LIMIT,populationSeedForRun,eligibleForWorst,WORST_POLICY} from './controller.mjs';
import {createServer,parseOptions} from './server.mjs';
import {createPool} from './pool.mjs';

const dir=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-continuous-')),controllers=[];
const fake={mode:'synthetic-test',ids:['fake'],async evaluate(population,seed,id,progress){return population.map((genome,index)=>{const score=genome.reduce((sum,n)=>sum+n,0);progress?.({workerId:'fake',id:index,status:'done',distance:score,genome});return {score,distance:score,elapsed:16,reason:'time'};});},async close(){}};
const make=({realPhysics=false,...extra}={})=>{
  const c=new EvolutionController({pool:fake,strategy:'diverse-v1',runs:0,populationSize:6,generations:2,delayMs:3600000,holdMs:3600000,...extra});
  // Retention/state-machine cases use synthetic fitness; avoid unrelated real
  // replay physics on every trial. Actual replay/physics is tested separately.
  if(!realPhysics)c.buildReplay=()=>{c.replay={key:c.session+':'+c.champion.generation,course:makeCourse(c.courseSeed),initial:c.initial,champion:c.champion};};
  controllers.push(c);return c;
};
const noTime=c=>c.comparison.results.map(({evaluationMs,...r})=>r);
let server,real;
try {
  const pop=initialPopulation(42,36),scores=pop.map((g,i)=>({score:i}));
  assert.deepEqual(mutationPlan(36),{elite:2,normal:20,large:10,fresh:4,burst:false});
  assert.deepEqual(mutationPlan(36,10),{elite:2,normal:10,large:16,fresh:8,burst:true});
  for(const size of [6,12,36,120])for(const stagnant of [0,10]){const p=mutationPlan(size,stagnant);assert.equal(p.elite+p.normal+p.large+p.fresh,size);assert.ok(p.normal>=0&&p.fresh>0&&p.large>0);}
  const evolved=nextPopulation(pop,scores,random(99),{strategy:'diverse-v1'});
  assert.deepEqual(evolved.slice(0,2),[pop[35],pop[34]]);evolved.forEach(validateGenome);
  assert.deepEqual(evolved,nextPopulation(pop,scores,random(99),{strategy:'diverse-v1'}));
  assert.notDeepEqual(evolved,nextPopulation(pop,scores,random(99)));
  assert.notDeepEqual(evolved,nextPopulation(pop,scores,random(99),{strategy:'diverse-v1',stagnation:10}));
  const controlled=make({populationSize:36,generations:15,pool:{...fake,async evaluate(pop){return pop.map(()=>({score:controlled.generation<10?1:2,distance:controlled.generation<10?1:2,elapsed:16,reason:'time'}));}}});
  for(let i=0;i<11;i++)await controlled.step();assert.equal(controlled.stagnation,10);assert.equal(controlled.snapshot().searchMix.fresh,8);
  assert.equal(new Set([...controlled.ranking.best,...controlled.ranking.worst].map(r=>r.genome.join(','))).size,6,'同成績でも重複しない6形状を表示');
  await controlled.step();assert.equal(controlled.stagnation,0);assert.equal(controlled.snapshot().searchMix.fresh,4);
  // 全評価との突合。保持している極値だけから更新しても全車体からの上位/下位になる。
  // 0.0m表示（丸め前の微小な正距離を含む）はワーストから除外する。
  for(const distance of [0,0.001,0.049999])assert.equal(eligibleForWorst({distance}),false);
  for(const distance of [0.05,0.1,1])assert.equal(eligibleForWorst({distance}),true);
  const distances=[0,0.001,0.049,0.05,0.1,2];
  const filtered=make({pool:{...fake,async evaluate(pop){return pop.map((genome,i)=>({score:distances[i],distance:distances[i],elapsed:16,reason:'time'}));}}});
  await filtered.step();assert.deepEqual(filtered.ranking.worst.map(c=>c.distance),[0.05,0.1,2]);assert.equal(filtered.ranking.evaluated,6);
  const empty=make({pool:{...fake,async evaluate(pop){return pop.map(()=>({score:0,distance:0,elapsed:4,reason:'stalled'}));}}});
  await empty.step();assert.equal(empty.ranking.worst.length,0);assert.equal(empty.ranking.best.length,3);assert.equal(empty.ranking.evaluated,6);
  const sparse=make({pool:{...fake,async evaluate(pop){return pop.map((g,i)=>({score:i===5?1:0,distance:i===5?1:0,elapsed:4,reason:'stalled'}));}}});
  await sparse.step();assert.equal(sparse.ranking.worst.length,1);
  const c=make(),seen=new Map();
  const observe=cars=>{for(const car of cars)if(!seen.has(car.genome.join(',')))seen.set(car.genome.join(','),car);};
  // Controller's tie rule is best lexicographically first, worst last.
  const sorted=(best)=>[...seen.values()].sort((a,b)=>(best?b.score-a.score:a.score-b.score)||((a.genome.join(',')<b.genome.join(',')?-1:a.genome.join(',')>b.genome.join(',')?1:0)*(best?1:-1))).slice(0,3).map(c=>c.genome);
  for(let i=0;i<30;i++) {
    const current=c.nextRun?initialPopulation(populationSeedForRun(c.comparison.startPopulationSeed,c.comparison.runIndex+1),6):structuredClone(c.population);
    observe(current.map(genome=>({genome,score:genome.reduce((sum,n)=>sum+n,0)})));
    await c.step();
    assert.deepEqual(c.ranking.best.map(r=>r.genome),sorted(true));assert.deepEqual(c.ranking.worst.map(r=>r.genome),sorted(false));
    assert.equal(c.ranking.evaluated,(i+1)*6);assert.ok(c.comparison.results.length<=RECENT_RUN_LIMIT);
    assert.ok(c.running);assert.ok(c.recordReplays.size<=8);
  }
  assert.equal(c.comparison.runIndex,14);assert.equal(c.populationSeed,2040);assert.equal(c.phase,'between-runs');
  assert.equal(new Set([...c.ranking.best,...c.ranking.worst].map(r=>r.genome.join(','))).size,6);
  const record=c.ranking.worst[0],selected=c.replayForCar(record.id);
  assert.deepEqual(selected.champion.frames,simulate(record.genome,{seed:c.courseSeed,frames:true}).frames);
  assert.deepEqual(selected.initial.frames,simulate(record.baseline.genome,{seed:c.courseSeed,frames:true}).frames);
  assert.equal(c.replayForCar(record.id),selected);
  await c.step();assert.equal(c.comparison.runIndex,15);assert.equal(c.replayForCar(record.id),selected);
  // Retained replays remain usable even if a card falls off the ranking.
  c.ranking.worst=c.ranking.worst.filter(r=>r.id!==record.id);assert.equal(c.replayForCar(record.id),selected);
  assert.throws(()=>c.replayForCar('old-epoch:0:0:0'));
  // Deterministic continuation, including rankings and stagnation, after trimming archives.
  const persisted=make({stateFile:path.join(dir,'state.json')});for(let i=0;i<17;i++)await persisted.step();
  const checkpoint=await fs.readFile(persisted.file);const resumed=make({stateFile:persisted.file});await resumed.restore();
  assert.deepEqual(resumed.ranking,persisted.ranking);assert.equal(resumed.stagnation,persisted.stagnation);
  for(let i=0;i<4;i++){await persisted.step();await resumed.step();}
  assert.deepEqual(noTime(resumed),noTime(persisted));assert.deepEqual(resumed.population,persisted.population);assert.deepEqual(resumed.ranking,persisted.ranking);
  const oldRanking=JSON.parse(checkpoint);delete oldRanking.ranking.worstPolicy;delete oldRanking.ranking.worstSinceEvaluated;
  await fs.writeFile(persisted.file,JSON.stringify(oldRanking));const migrated=make({stateFile:persisted.file});await migrated.restore();
  assert.deepEqual(migrated.ranking.best,oldRanking.ranking.best);assert.equal(migrated.ranking.worst.length,0);assert.equal(migrated.ranking.worstSinceEvaluated,oldRanking.ranking.evaluated);
  assert.equal(migrated.comparison.id,oldRanking.comparison.id);assert.equal(migrated.ranking.evaluated,oldRanking.ranking.evaluated);
  await migrated.step();assert.ok(migrated.ranking.worst.length>0);assert.ok(migrated.ranking.worst.every(eligibleForWorst));
  const badWorst=JSON.parse(checkpoint);badWorst.ranking.worst[0].distance=0;await fs.writeFile(persisted.file,JSON.stringify(badWorst));await assert.rejects(make({stateFile:persisted.file}).restore(),/ワースト/);
  assert.equal(resumed.ranking.worstPolicy,WORST_POLICY);
  const corrupt=JSON.parse(checkpoint);corrupt.ranking.best[0].populationSeed++;
  await fs.writeFile(persisted.file,JSON.stringify(corrupt));await assert.rejects(make({stateFile:persisted.file}).restore(),/出所/);
  const badCount=JSON.parse(checkpoint);badCount.ranking.evaluated+=6;await fs.writeFile(persisted.file,JSON.stringify(badCount));await assert.rejects(make({stateFile:persisted.file}).restore(),/評価数/);
  const unsupported=JSON.parse(checkpoint);unsupported.strategy='unknown';await fs.writeFile(persisted.file,JSON.stringify(unsupported));await assert.rejects(make({stateFile:persisted.file}).restore(),/方式/);
  const bounded=make({generations:1});for(let i=0;i<12;i++)await bounded.step();const firstBytes=JSON.stringify(bounded.snapshot()).length;
  for(let i=0;i<60;i++)await bounded.step();assert.equal(bounded.comparison.results.length,RECENT_RUN_LIMIT);assert.ok(JSON.stringify(bounded.snapshot()).length<firstBytes+4096);assert.equal(bounded.ranking.evaluated,72*6);
  // Seed rollover is safe and changes the initial population, while course stays fixed.
  const wrap=make({populationSeed:2147483647,generations:1});await wrap.step();await wrap.step();assert.equal(wrap.populationSeed,0);assert.equal(wrap.courseSeed,2026);
  const paused=make({generations:1});await paused.step();paused.control('pause');await paused.step();assert.equal(paused.comparison.runIndex,0);paused.control('resume');await paused.step();assert.equal(paused.comparison.runIndex,1);
  const epoch=c.comparison.id;c.control('compare',undefined,{courseSeed:2026,populationSeed:800,runs:0,generations:40});await c.step();assert.notEqual(c.comparison.id,epoch);assert.equal(c.ranking.evaluated,6);assert.equal(c.comparison.runIndex,0);assert.equal(c.recordReplays.size,0);assert.equal(c.limit,40);assert.equal(c.populationSeed,800);
  assert.equal(parseOptions([]).runs,0);assert.equal(parseOptions([]).generations,20);assert.equal(parseOptions([]).strategy,'profile-v2');assert.throws(()=>comparisonOptions({runs:-1}));
  // Real physics: keep the best while adaptive exploration changes its allocation.
  real=await createPool({workers:2});const physical=make({realPhysics:true,pool:real,populationSize:12,generations:12,runs:1});
  for(let i=0;i<12;i++)await physical.step();assert.equal(physical.phase,'complete');assert.ok(physical.history.every((h,i,a)=>i===0||h.distance>=a[i-1].distance));
  server=createServer(physical);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url='http://127.0.0.1:'+server.address().port;
  const car=physical.ranking.worst[0],response=await fetch(url+'/api/replay?car='+encodeURIComponent(car.id)+'&experiment='+physical.comparison.id);assert.equal(response.status,200);assert.equal((await response.json()).carId,car.id);
  assert.equal((await fetch(url+'/api/replay?car='+encodeURIComponent(car.id)+'&experiment=old')).status,409);
  console.log('PASS: 混合変異・停滞配分・エリート・全候補の重複なし極値・連続試行・保存復帰・履歴上限・seed巡回・試行間停止/再計算・車体走行とAPI');
} finally {
  for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}
  await real?.close();if(server)await new Promise(resolve=>{server.closeAllConnections();server.close(resolve);});await fs.rm(dir,{recursive:true,force:true});
}
