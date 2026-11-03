import {runSearch} from './search.mjs';

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  if (!process.argv[index + 1]) throw Error(`${name}の値が必要です`);
  return process.argv[index + 1];
}

const cycles = Number(option('--cycles', '20'));
if (!Number.isInteger(cycles) || cycles < 1 || cycles > 1000) {
  throw Error('--cyclesは1から1000の整数で指定してください');
}

const startedAt = new Date().toISOString();
const records = [];
for (let cycle = 1; cycle <= cycles; cycle++) {
  const scenario = cycle % 2 ? 'eastwest' : 'balanced';
  const result = runSearch(scenario);
  const record = {
    cycle,
    scenario,
    elapsedMs: result.elapsed,
    candidateCount: result.candidateCount,
    best: result.best,
    bestScore: result.bestScore,
    validationPassed: result.validation.filter(item => item.acceptable).length,
    validationTotal: result.validation.length,
    rssBytes: process.memoryUsage().rss,
    maxRssKiB: process.resourceUsage().maxRSS,
  };
  if (!Number.isFinite(record.bestScore) || record.validationPassed !== record.validationTotal) {
    throw Error(`cycle ${cycle}の探索または検証に失敗しました`);
  }
  records.push(record);
  console.error(
    `cycle=${cycle}/${cycles} scenario=${scenario} elapsed=${record.elapsedMs.toFixed(3)}ms ` +
    `validation=${record.validationPassed}/${record.validationTotal} rss=${record.rssBytes}`,
  );
}

const elapsed = records.map(record => record.elapsedMs);
const byScenario = Object.fromEntries(['eastwest', 'balanced'].map(scenario => {
  const values = records.filter(record => record.scenario === scenario).map(record => record.elapsedMs);
  return [scenario, {
    cycles: values.length,
    minMs: Math.min(...values),
    maxMs: Math.max(...values),
    averageMs: values.reduce((sum, value) => sum + value, 0) / values.length,
  }];
}));

console.log(JSON.stringify({
  startedAt,
  finishedAt: new Date().toISOString(),
  node: process.version,
  platform: process.platform,
  arch: process.arch,
  cycles,
  elapsed: {
    minMs: Math.min(...elapsed),
    maxMs: Math.max(...elapsed),
    averageMs: elapsed.reduce((sum, value) => sum + value, 0) / elapsed.length,
  },
  byScenario,
  peakRssKiB: Math.max(...records.map(record => record.maxRssKiB)),
  records,
}, null, 2));
