import assert from 'node:assert/strict';
import {baseline, candidates} from './engine.mjs';
import {createEvaluationServer, listen} from './distributed-worker.mjs';
import {compareWorkerCounts, ResultCollector, runDistributed} from './distributed.mjs';

async function start(workerId, evaluator) {
  const server = createEvaluationServer({workerId, evaluator});
  const address = await listen(server, {host: '127.0.0.1', port: 0});
  return {server, url: `http://127.0.0.1:${address.port}`};
}

async function stop(...servers) {
  await Promise.all(servers.map(server => new Promise(resolve => {
    server.closeAllConnections?.();
    server.close(resolve);
  })));
}

const realA = await start('real-a');
const realB = await start('real-b');
try {
  const comparison = await compareWorkerCounts({
    workers: [realA.url, realB.url],
    scenario: 'eastwest',
    configs: candidates(2026, 6),
    timeoutMs: 5000,
    maxRetries: 1,
    runId: 'distributed-test-real',
  });
  assert.equal(comparison.same, true);
  assert.equal(comparison.single.candidateCount, 6);
  assert.equal(comparison.distributed.candidateCount, 6);
  assert.deepEqual(comparison.single.best, comparison.distributed.best);

  const task = {runId: 'cache-test', taskId: 0, scenario: 'eastwest', config: baseline, seeds: [101]};
  const first = await fetch(`${realA.url}/evaluate`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(task)}).then(response => response.json());
  const second = await fetch(`${realA.url}/evaluate`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(task)}).then(response => response.json());
  assert.equal(first.cached, false);
  assert.equal(second.cached, true);

  const expired=await runDistributed({
    workers:[realA.url],scenario:'eastwest',configs:candidates(2026,1),
    timeoutMs:5000,maxRetries:0,dispatchDeadlineAt:performance.now()-1,allowPartial:true,runId:'expired-deadline-test',
  });
  assert.equal(expired.candidateCount,0);
  assert.equal(expired.best,null);
} finally {
  await stop(realA.server, realB.server);
}

const collector = new ResultCollector('duplicate-test');
assert.equal(collector.accept({runId: 'duplicate-test', taskId: 1}), true);
assert.equal(collector.accept({runId: 'duplicate-test', taskId: 1}), false);
assert.equal(collector.results.size, 1);
assert.equal(collector.duplicates, 1);

const slow = await start('slow', async () => {
  await new Promise(resolve => setTimeout(resolve, 150));
  return {eligible: true, score: 2, computeMs: 150};
});
const healthy = await start('healthy', async task => ({eligible: true, score: task.taskId, computeMs: 0}));
try {
  const recovered = await runDistributed({
    workers: [slow.url, healthy.url],
    scenario: 'balanced',
    configs: candidates(2026, 4),
    timeoutMs: 50,
    maxRetries: 1,
    runId: 'retry-test',
  });
  assert.equal(recovered.results.length, 4);
  assert.equal(recovered.retries, 1);
  assert.match(recovered.failures[0].error, /タイムアウト/);
  assert.equal(recovered.workers.find(worker => worker.workerId === 'slow').active, false);
  assert.equal(recovered.taskCounts.healthy, 4);

  await assert.rejects(runDistributed({
    workers: [slow.url],
    scenario: 'balanced',
    configs: candidates(2026, 1),
    timeoutMs: 50,
    maxRetries: 0,
    runId: 'retry-limit-test',
  }), /1回失敗/);
} finally {
  await stop(slow.server, healthy.server);
}

console.error('PASS: 分散結果一致、重複排除、キャッシュ、絶対期限、タイムアウト、上限付き再試行、別ワーカへの再割り当て');
