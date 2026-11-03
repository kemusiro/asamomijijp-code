import fs from 'node:fs';

const EXPECTED_HASHES = {
  eastwest: '06cba11fb15ca1feef43e6f5d09f5dcacd8cbd7e65808d044ec122ec914af174',
  balanced: 'e06d6c11e669622b3795ca46e32f345586ee6b5d75247956f0dc60bf8d90c632',
};

function die(message) {
  console.error(`FAIL: ${message}`);
  process.exit(1);
}

const [path, victim = 'node10', expectedWorkersText = '12', expectedCandidatesText = '120'] = process.argv.slice(2);
if (!path) die('usage: node validate-distributed-fault.mjs RESULT.json [VICTIM] [WORKERS] [CANDIDATES]');
const expectedWorkers = Number(expectedWorkersText);
const expectedCandidates = Number(expectedCandidatesText);
let result;
try {
  result = JSON.parse(fs.readFileSync(path, 'utf8'));
} catch (error) {
  die(`cannot read result: ${error.message}`);
}

if (result.candidateCount !== expectedCandidates || result.results?.length !== expectedCandidates) {
  die(`candidate count differs: ${result.candidateCount}/${expectedCandidates}`);
}
if (result.resultHash !== EXPECTED_HASHES[result.scenario]) {
  die(`result hash differs from the Issue #89 baseline: ${result.resultHash}`);
}
if (result.workers?.length !== expectedWorkers) die(`worker count differs: ${result.workers?.length}/${expectedWorkers}`);
const failedWorker = result.workers.find(worker => worker.workerId === victim);
if (!failedWorker || failedWorker.active !== false) die(`${victim} was not recorded as inactive`);
if (result.retries < 1 || !result.failures.some(failure => failure.workerId === victim)) {
  die(`failure and retry for ${victim} were not recorded`);
}
if (result.duplicatesIgnored !== 0) die(`duplicate results were counted: ${result.duplicatesIgnored}`);
const taskTotal = Object.values(result.taskCounts).reduce((sum, count) => sum + count, 0);
if (taskTotal !== expectedCandidates) die(`task total differs: ${taskTotal}/${expectedCandidates}`);

console.log(JSON.stringify({
  status: 'PASS',
  path,
  scenario: result.scenario,
  candidateCount: result.candidateCount,
  resultHash: result.resultHash,
  elapsedMs: result.elapsedMs,
  victim,
  retries: result.retries,
  duplicatesIgnored: result.duplicatesIgnored,
  taskCounts: result.taskCounts,
  failures: result.failures,
}, null, 2));
