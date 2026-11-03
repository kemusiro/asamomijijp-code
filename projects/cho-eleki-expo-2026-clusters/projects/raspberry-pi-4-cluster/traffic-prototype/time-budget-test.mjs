import assert from 'node:assert/strict';
import {createEvaluationServer,listen} from './distributed-worker.mjs';
import {compareTimeBudgets} from './time-budget-benchmark.mjs';

async function start(workerId) {
  const evaluator=async task=>{
    const started=performance.now();
    await new Promise(resolve=>setTimeout(resolve,80));
    return {eligible:true,score:task.config.green.reduce((a,b)=>a+b,0)+task.config.offset.reduce((a,b)=>a+b,0)/100,computeMs:performance.now()-started};
  };
  const server=createEvaluationServer({workerId,evaluator});
  const address=await listen(server,{host:'127.0.0.1',port:0});
  return {server,url:`http://127.0.0.1:${address.port}`};
}

async function stop(workers) {
  await Promise.all(workers.map(({server})=>new Promise(resolve=>{server.closeAllConnections?.();server.close(resolve);})))
}

const workers=await Promise.all(['node10','node11','node12'].map(start));
try {
  const pattern={platoonSize:5,period:60,spacing:1,jitter:0.25,phase:0,reverseRate:0.005,crossRate:0.02};
  const report=await compareTimeBudgets({workers:workers.map(worker=>worker.url),pattern,budgetMs:1000,populationSize:6,seed:7026,timeoutMs:1000,maxRetries:0,runId:'time-budget-test'});
  assert.equal(report.kind,'time-budget-comparison');
  assert.equal(report.fairness.completedByDeadlineOnly,true);
  assert.ok(report.distributed.evaluatedCount>report.single.evaluatedCount);
  for(const run of [report.single,report.distributed]) {
    assert.ok(run.traces.length>=run.evaluatedCount);
    assert.equal(run.traces.filter(item=>item.withinBudget).length,run.evaluatedCount);
    assert.ok(run.traces.every(item=>item.startedAtMs<=item.finishedAtMs));
    assert.ok(run.traces.filter(item=>item.withinBudget).every(item=>item.finishedAtMs<=run.budgetMs));
    assert.ok(run.bestHistory.every(item=>item.atMs<=run.budgetMs));
  }
} finally {
  await stop(workers);
}

console.log('PASS: 同一時間予算、候補開始・終了時刻、期限内集計、1台対複数台の評価件数差');
