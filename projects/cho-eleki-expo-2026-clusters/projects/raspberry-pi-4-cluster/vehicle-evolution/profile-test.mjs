import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {initialPopulation,initialProfileForSeed,evolutionSeedForTrial,nextPopulation} from './evolution.mjs';
import {random,BOUNDS,validateGenome,makeCourse} from './physics.mjs';
import {EvolutionController} from './controller.mjs';
const strategy='profile-v2',dir=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-profile-')),controllers=[];
const fake={ids:['test'],mode:'synthetic-test',async evaluate(pop){return pop.map(g=>({score:g.reduce((a,b)=>a+b),distance:g.reduce((a,b)=>a+b),elapsed:16,reason:'time'}));},async close(){}};
const make=extra=>{const c=new EvolutionController({pool:fake,populationSize:6,runs:0,generations:2,delayMs:3600000,holdMs:3600000,...extra});c.buildReplay=()=>{};controllers.push(c);return c;};
try {
  for(const seed of [0,1,2026,2147483647]) {
    const rng=random(seed),uniform=Array.from({length:36},()=>BOUNDS.map(([lo,hi])=>lo+rng()*(hi-lo)));
    assert.deepEqual(initialPopulation(seed,36,{strategy:'legacy'}),uniform);assert.deepEqual(initialPopulation(seed,36,{strategy:'diverse-v1'}),uniform);
    for(const size of [6,36,120]){const pop=initialPopulation(seed,size,{strategy});assert.deepEqual(pop,initialPopulation(seed,size,{strategy}));pop.forEach(validateGenome);assert.equal(new Set(pop.map(g=>g.join(','))).size,size);}
  }
  assert.throws(()=>initialPopulation(1,36,{strategy:'unknown'}));
  assert.equal(new Set(Array.from({length:6},(_,i)=>initialProfileForSeed(2026+i,strategy).id)).size,6);
  assert.equal(initialProfileForSeed(2026,'diverse-v1'),null);
  assert.deepEqual(initialProfileForSeed(2026,strategy),initialProfileForSeed(2032,strategy));
  assert.notDeepEqual(initialPopulation(2026,36,{strategy}),initialPopulation(2032,36,{strategy}));
  const mean=(seed,index)=>initialPopulation(seed,36,{strategy}).reduce((sum,g)=>sum+(g[index]-BOUNDS[index][0])/(BOUNDS[index][1]-BOUNDS[index][0]),0)/36;
  assert.ok(mean(2028,0)<.35&&mean(2028,8)>.7,'小型・大径輪の初期傾向');
  assert.ok(mean(2029,0)>.65&&mean(2029,8)<.4,'大型・小径輪の初期傾向');
  assert.ok(mean(2030,8)>mean(2030,9)+.4&&mean(2031,9)>mean(2031,8)+.4,'前後輪の傾向');
  assert.ok(mean(2026,10)>mean(2027,10)+.4,'車軸間隔の傾向');
  const pop=initialPopulation(2028,36,{strategy}),results=pop.map((g,i)=>({score:i})),next=nextPopulation(pop,results,random(123),{strategy});
  assert.deepEqual(next.slice(0,2),[pop[35],pop[34]]);next.forEach(validateGenome);assert.ok(next.slice(-4).some(g=>g[0]>1),'後続の新規車体は初期タイプの狭い分布に制約しない');
  const a=make({stateFile:path.join(dir,'checkpoint.json')}),b=make({populationSeed:2027});
  assert.equal(a.strategy,strategy);assert.notEqual(a.evolutionSeed,b.evolutionSeed);assert.deepEqual(makeCourse(a.courseSeed),makeCourse(b.courseSeed));
  assert.equal(a.evolutionSeed,(2026^0x51ed270b)>>>0);assert.equal(evolutionSeedForTrial(2026,2027,'diverse-v1'),2027);
  await a.step();await a.step();await a.step();assert.equal(a.populationSeed,2027);assert.equal(a.comparison.results[0].initialProfile.id,'wide');assert.equal(a.snapshot().initialProfile.id,'uneven');
  const saved=JSON.parse(await fs.readFile(a.file));const restored=make({stateFile:a.file});await restored.restore();
  assert.equal(restored.evolutionSeed,a.evolutionSeed);assert.deepEqual(restored.snapshot().initialProfile,a.snapshot().initialProfile);assert.deepEqual(restored.population,a.population);assert.deepEqual(restored.ranking,a.ranking);
  await a.step();await restored.step();assert.deepEqual(a.population,restored.population);assert.deepEqual(a.ranking,restored.ranking);assert.equal(a.rng.state(),restored.rng.state());
  saved.comparison.results[0].evolutionSeed++;await fs.writeFile(a.file,JSON.stringify(saved));await assert.rejects(make({stateFile:a.file}).restore(),/比較結果/);
  a.control('compare',undefined,{courseSeed:2026,populationSeed:2028,runs:0,generations:20});await a.step();assert.equal(a.strategy,strategy);assert.equal(a.limit,20);assert.equal(a.snapshot().initialProfile.id,'compact');
  const wrap=make({populationSeed:2147483647,generations:1});await wrap.step();await wrap.step();assert.equal(wrap.populationSeed,0);assert.equal(wrap.evolutionSeed,(0^0x51ed270b)>>>0);assert.equal(wrap.snapshot().initialProfile.id,'compact');
  console.log('PASS: seed別初期タイプ・決定性・全寸法範囲・自由な後続世代・試行別乱数・20世代再計算・保存完全復帰・seed巡回・旧方式不変');
}finally{for(const c of controllers){c.stopped=true;clearTimeout(c.timer);}await fs.rm(dir,{recursive:true,force:true});}
