import assert from 'node:assert/strict';
import {mkdtemp, mkdir, rm, writeFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createDashboardSnapshot, findLatestComparisons, readExhibitionState, requestExhibitionPattern, summarizeComparison, summarizeTimeBudget} from './dashboard-server.mjs';

function comparison(scenario, elapsed = 1000) {
  const hash = `${scenario}-hash`;
  return {
    finishedAt: '2026-09-24T14:00:00.000Z',
    same: true,
    speedup: 10,
    single: {scenario, elapsedMs: elapsed * 10, resultHash: hash},
    distributed: {
      scenario,
      elapsedMs: elapsed,
      resultHash: hash,
      candidateCount: 120,
      best: {taskId: 5, config: {green: [23, 23, 23, 23], offset: [0, 41, 41, 22]}, score: 1},
      taskCounts: {node10: 60, node11: 60},
      workers: [{workerId: 'node10'}, {workerId: 'node11'}],
      retries: 0,
      duplicatesIgnored: 0,
      timing: {estimatedCommunicationMs: 321},
    },
  };
}

function timeBudget() {
  const run=(workerCount,count)=>({workerCount,evaluatedCount:count,startedCount:count,completedGenerations:Math.floor(count/12),best:{config:{green:[23,23,23,23],offset:[0,20,0,20]},score:4},bestHistory:[{atMs:500,score:4}],taskCounts:{node10:count},traces:[{candidateId:0,generation:0,workerId:'node10',startedAtMs:0,finishedAtMs:500,withinBudget:true,score:4,eligible:true}]});
  return {kind:'time-budget-comparison',finishedAt:'2026-09-25T14:00:00.000Z',budgetMs:10000,pattern:{platoonSize:5,period:60,spacing:1,jitter:.25,phase:0,reverseRate:.005,crossRate:.02},candidateMultiplier:10,qualityImprovement:3,fairness:{sameSeed:true},validation:{single:{meanWait:8},distributed:{meanWait:5}},single:run(1,12),distributed:run(12,120)};
}

const summary = summarizeComparison(comparison('eastwest'), 'run/eastwest.json', 'unused');
assert.equal(summary.scenario, 'eastwest');
assert.equal(summary.same, true);
assert.equal(summary.speedup, 10);
assert.equal(summary.candidateCount, 120);
assert.equal(summary.estimatedCommunicationMs, 321);
assert.equal(summarizeComparison({single: {}}, 'bad.json', 'unused'), null);
const budgetSummary=summarizeTimeBudget(timeBudget(),'run/time-budget.json','unused');
assert.equal(budgetSummary.distributed.evaluatedCount,120);
assert.equal(budgetSummary.single.traces[0].finishedAtMs,500);

const temporary = await mkdtemp(path.join(os.tmpdir(), 'traffic-dashboard-'));
try {
  await mkdir(path.join(temporary, 'older'));
  await mkdir(path.join(temporary, 'latest'));
  await writeFile(path.join(temporary, 'older', 'eastwest.json'), JSON.stringify(comparison('eastwest', 2000)));
  await new Promise(resolve => setTimeout(resolve, 20));
  await writeFile(path.join(temporary, 'latest', 'eastwest.json'), JSON.stringify(comparison('eastwest', 900)));
  await writeFile(path.join(temporary, 'latest', 'balanced.json'), JSON.stringify(comparison('balanced', 700)));
  await writeFile(path.join(temporary, 'latest', 'time-budget.json'), JSON.stringify(timeBudget()));
  await writeFile(path.join(temporary, 'latest', 'partial.json.tmp'), '{');
  await writeFile(path.join(temporary, 'latest', 'invalid.json'), '{');
  await mkdir(path.join(temporary,'exhibition'));
  await writeFile(path.join(temporary,'exhibition','live.json'),JSON.stringify({schemaVersion:1,cycle:3,phase:'distributed'}));
  const patternsFile=path.join(temporary,'exhibition-patterns.json');
  await writeFile(patternsFile,JSON.stringify({schemaVersion:1,patterns:[
    {id:'rush',name:'ラッシュ',description:'集中',pattern:{}},
    {id:'balanced',name:'均等',description:'均等',pattern:{}},
  ]}));

  const latest = await findLatestComparisons(temporary);
  assert.equal(latest.eastwest.distributedElapsedMs, 900);
  assert.equal(latest.balanced.distributedElapsedMs, 700);
  assert.equal(latest.timeBudget.candidateMultiplier,10);
  assert.equal((await readExhibitionState(temporary)).cycle,3);

  const expectedIds = ['node10', 'node11', 'node12'];
  const snapshot = await createDashboardSnapshot({
    resultsDir: temporary,
    patternsFile,
    service: 'unused',
    port: 8787,
    expectedIds,
    probe: async () => expectedIds.map(workerId => ({workerId, ready: workerId !== 'node12'})),
  });
  assert.equal(snapshot.readyWorkers, 2);
  assert.equal(snapshot.expectedWorkers, 3);
  assert.equal(snapshot.results.eastwest.same, true);
  assert.equal(snapshot.exhibition.phase,'distributed');
  assert.deepEqual(snapshot.patterns.map(item=>item.id),['rush','balanced']);
  assert.deepEqual(snapshot.errors, []);
  const queued=await requestExhibitionPattern({resultsDir:temporary,patternsFile},'balanced');
  assert.equal(queued.requestedPatternId,'balanced');
  await assert.rejects(()=>requestExhibitionPattern({resultsDir:temporary,patternsFile},'unknown'),/unknown pattern/);
} finally {
  await rm(temporary, {recursive: true, force: true});
}

console.log('PASS: 最新比較結果、交通パターン予約、ワーカ状態のスナップショット');
