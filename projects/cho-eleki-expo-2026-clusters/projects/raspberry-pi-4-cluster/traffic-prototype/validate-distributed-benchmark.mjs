import fs from 'node:fs';

const EXPECTED_HASHES = {
  eastwest: '06cba11fb15ca1feef43e6f5d09f5dcacd8cbd7e65808d044ec122ec914af174',
  balanced: 'e06d6c11e669622b3795ca46e32f345586ee6b5d75247956f0dc60bf8d90c632',
};

function die(message) {
  console.error(`FAIL: ${message}`);
  process.exit(1);
}

const [path, expectedWorkersText = '12', expectedCandidatesText = '120'] = process.argv.slice(2);
if (!path) die('usage: node validate-distributed-benchmark.mjs RESULT.json [WORKERS] [CANDIDATES]');
const expectedWorkers = Number(expectedWorkersText);
const expectedCandidates = Number(expectedCandidatesText);
if (!Number.isInteger(expectedWorkers) || expectedWorkers < 2) die('WORKERS must be an integer of at least 2');
if (!Number.isInteger(expectedCandidates) || expectedCandidates < 1) die('CANDIDATES must be a positive integer');

let report;
try {
  report = JSON.parse(fs.readFileSync(path, 'utf8'));
} catch (error) {
  die(`cannot read result: ${error.message}`);
}

const {single, distributed, speedup} = report;
const same = report.same ?? report.sameResult;
if (!single || !distributed) die('single or distributed result is missing');
if (same !== true) die('single and distributed results differ');
const scenario = single.scenario ?? distributed.scenario ??
  Object.entries(EXPECTED_HASHES).find(([, hash]) => hash === single.resultHash)?.[0];
if (single.scenario && distributed.scenario && single.scenario !== distributed.scenario) {
  die('scenario differs between runs');
}
if (!EXPECTED_HASHES[scenario]) die(`unknown scenario: ${scenario}`);
if (single.resultHash !== distributed.resultHash) die('result hashes differ');
if (single.resultHash !== EXPECTED_HASHES[scenario]) {
  die(`result hash differs from the Issue #89 baseline: ${single.resultHash}`);
}
if (single.candidateCount !== expectedCandidates || distributed.candidateCount !== expectedCandidates) {
  die(`candidate count differs: single=${single.candidateCount}, distributed=${distributed.candidateCount}`);
}
const workers = distributed.workers ?? Object.keys(distributed.taskCounts).map(workerId => ({workerId, active: true}));
if (workers.length !== expectedWorkers) {
  die(`worker count differs: ${workers.length}/${expectedWorkers}`);
}
if (new Set(workers.map(worker => worker.workerId)).size !== expectedWorkers) {
  die('worker IDs are not unique');
}
if (workers.some(worker => !worker.active)) die('an inactive worker remains in a normal benchmark');
const taskTotal = Object.values(distributed.taskCounts).reduce((sum, count) => sum + count, 0);
if (taskTotal !== expectedCandidates) die(`distributed task total differs: ${taskTotal}/${expectedCandidates}`);
if (distributed.retries !== 0 || distributed.duplicatesIgnored !== 0) {
  die(`unexpected retry or duplicate: retries=${distributed.retries}, duplicates=${distributed.duplicatesIgnored}`);
}
if (!Number.isFinite(speedup) || speedup <= 0) die(`invalid speedup: ${speedup}`);

console.log(JSON.stringify({
  status: 'PASS',
  path,
  scenario,
  candidateCount: expectedCandidates,
  workerCount: expectedWorkers,
  resultHash: single.resultHash,
  best: single.best,
  singleElapsedMs: single.elapsedMs,
  distributedElapsedMs: distributed.elapsedMs,
  speedup,
  taskCounts: distributed.taskCounts,
  estimatedCommunicationMs: distributed.timing.estimatedCommunicationMs,
}, null, 2));
