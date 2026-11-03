import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {discoverWorkers,runExhibitionMode,validatePatternCatalog} from './exhibition-runner.mjs';

const discovered=await discoverWorkers({
  service:'workers',port:8787,expectedWorkers:2,
  lookup:async()=>[{address:'10.0.0.2'},{address:'10.0.0.1'}],
  fetchImpl:async url=>({ok:true,json:async()=>({status:'ok',workerId:url.includes('.1:')?'node10':'node11'})}),
});
assert.deepEqual(discovered.map(worker=>worker.workerId),['node10','node11']);

const temporary=await mkdtemp(path.join(os.tmpdir(),'traffic-exhibition-'));
let clock=Date.parse('2026-09-25T00:00:00.000Z');
let previousAttempts=0;
const basePattern={platoonSize:5,period:48,spacing:1,jitter:.5,phase:4,reverseRate:.02,crossRate:.04};
const patterns=validatePatternCatalog({schemaVersion:1,patterns:[
  {id:'first',name:'最初',description:'自動選択',pattern:basePattern},
  {id:'second',name:'次',description:'予約選択',pattern:{...basePattern,phase:5}},
]});
const selected=[];
const run=workerCount=>({
  workerCount,evaluatedCount:workerCount*12,startedCount:workerCount*12,completedGenerations:workerCount,
  best:{candidateId:1,generation:0,config:{green:[24,24,24,24],offset:[0,10,20,30]},score:5},
  bestHistory:[{atMs:100,score:5,candidateId:1,generation:0}],taskCounts:{node10:12},drainMs:0,traces:[],
});
try {
  const outcome=await runExhibitionMode({
    resultsDir:temporary,patterns,service:'workers',port:8787,expectedWorkers:2,
    budgetMs:1000,populationSize:12,seedBase:7,timeoutMs:1000,maxRetries:0,
    resultHoldMs:1000,retryMs:1000,publishIntervalMs:50,maxCycles:2,
  },{
    now:()=>clock++,sleep:async()=>{},discover:async()=>discovered,
    previousCycle:async()=>{if(previousAttempts++===0)throw Error('temporary NFS error');return 0;},
    consumePatternRequest:async(_file,available)=>selected.length===1?available[1]:null,
    compare:async options=>{
      assert.equal(options.seed,7);
      selected.push(options.pattern);
      options.onPhase({phase:'single',status:'started'});
      options.onProgress({phase:'single',workerId:'node10',candidateId:0,generation:0,completedCandidates:1,completedGenerations:0,startedAtMs:0,finishedAtMs:100,score:8,eligible:true,best:{candidateId:0,generation:0,config:{green:[23,23,23,23],offset:[0,0,0,0]},score:8}});
      const single=run(1);options.onPhase({phase:'single',status:'completed',result:single});
      options.onPhase({phase:'distributed',status:'started'});
      options.onProgress({phase:'distributed',workerId:'node11',candidateId:0,generation:0,completedCandidates:1,completedGenerations:0,startedAtMs:0,finishedAtMs:50,score:5,eligible:true,best:run(2).best});
      const distributed=run(2);options.onPhase({phase:'distributed',status:'completed',result:distributed});
      options.onPhase({phase:'validation',status:'started'});
      const validation={single:{meanWait:8},distributed:{meanWait:5}};
      options.onPhase({phase:'validation',status:'completed',result:validation});
      return {kind:'time-budget-comparison',version:1,budgetMs:1000,pattern:options.pattern,single,distributed,validation,candidateMultiplier:2,qualityImprovement:3};
    },
  });
  assert.equal(outcome.completedCycles,2);
  assert.equal(previousAttempts,2);
  const state=JSON.parse(await readFile(path.join(temporary,'exhibition','live.json'),'utf8'));
  assert.equal(state.phase,'result');assert.equal(state.cycle,2);assert.equal(state.candidateMultiplier,2);
  assert.equal(state.distributed.evaluatedCount,24);
  const report=JSON.parse(await readFile(path.join(temporary,state.result),'utf8'));
  assert.equal(report.kind,'time-budget-comparison');assert.equal(report.exhibitionCycle,2);assert.equal(report.exhibitionPattern.id,'second');
  assert.deepEqual(selected,[patterns[0].pattern,patterns[1].pattern]);
} finally {
  await rm(temporary,{recursive:true,force:true});
}

console.log('PASS: ワーカ検出、交通パターン自動・予約選択、原子的な状態・結果保存');
