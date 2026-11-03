import os from 'node:os';
import {candidates, CANDIDATE_COUNT} from './engine.mjs';
import {compareWorkerCounts} from './distributed.mjs';

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  if (!process.argv[index + 1]) throw Error(`${name}の値が必要です`);
  return process.argv[index + 1];
}

const workerList = option('--workers', '').split(',').map(value => value.trim()).filter(Boolean);
const scenario = option('--scenario', 'eastwest');
const timeoutMs = Number(option('--timeout-ms', '5000'));
const maxRetries = Number(option('--retries', '1'));
const candidateCount = Number(option('--candidates', String(CANDIDATE_COUNT)));
if (workerList.length < 2) throw Error('--workersへカンマ区切りで2台以上を指定してください');
if (!Number.isInteger(timeoutMs) || timeoutMs < 100) throw Error('--timeout-msは100以上の整数で指定してください');
if (!Number.isInteger(candidateCount) || candidateCount < 1 || candidateCount > CANDIDATE_COUNT) throw Error(`--candidatesは1から${CANDIDATE_COUNT}で指定してください`);

const startedAt = new Date().toISOString();
const comparison = await compareWorkerCounts({
  workers: workerList,
  scenario,
  configs: candidates(2026, candidateCount),
  timeoutMs,
  maxRetries,
  runId: `traffic-${Date.now()}`,
  onProgress: ({done, total, workerId}) => console.error(`progress=${done}/${total} worker=${workerId}`),
});
console.log(JSON.stringify({
  startedAt,
  finishedAt: new Date().toISOString(),
  coordinator: os.hostname(),
  node: process.version,
  platform: process.platform,
  arch: process.arch,
  ...comparison,
}, null, 2));
