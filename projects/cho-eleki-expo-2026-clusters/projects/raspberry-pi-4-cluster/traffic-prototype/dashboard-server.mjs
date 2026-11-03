import {promises as dns} from 'node:dns';
import {promises as fs} from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const ASSETS = new Map([
  ['/', ['dashboard.html', 'text/html; charset=utf-8']],
  ['/dashboard.html', ['dashboard.html', 'text/html; charset=utf-8']],
  ['/dashboard.mjs', ['dashboard.mjs', 'text/javascript; charset=utf-8']],
  ['/engine.mjs', ['engine.mjs', 'text/javascript; charset=utf-8']],
  ['/dashboard.css', ['dashboard.css', 'text/css; charset=utf-8']],
]);
const SCENARIOS = new Set(['eastwest', 'balanced']);

function nodeNumber(workerId) {
  const match = /^node(\d+)$/.exec(workerId);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}

export function summarizeComparison(report, source, modifiedAt) {
  const {single, distributed} = report ?? {};
  const scenario = distributed?.scenario ?? single?.scenario;
  if (!single || !distributed || !SCENARIOS.has(scenario)) return null;
  if (!Number.isFinite(single.elapsedMs) || !Number.isFinite(distributed.elapsedMs)) return null;
  if (!Number.isInteger(distributed.candidateCount) || !distributed.best?.config) return null;
  const hashesMatch = single.resultHash === distributed.resultHash;
  return {
    scenario,
    source,
    recordedAt: report.finishedAt ?? modifiedAt,
    candidateCount: distributed.candidateCount,
    singleElapsedMs: single.elapsedMs,
    distributedElapsedMs: distributed.elapsedMs,
    speedup: Number.isFinite(report.speedup) ? report.speedup : single.elapsedMs / distributed.elapsedMs,
    same: report.same === true && hashesMatch,
    resultHash: distributed.resultHash,
    best: distributed.best,
    taskCounts: distributed.taskCounts ?? {},
    workerCount: distributed.workers?.length ?? Object.keys(distributed.taskCounts ?? {}).length,
    retries: distributed.retries ?? 0,
    duplicatesIgnored: distributed.duplicatesIgnored ?? 0,
    estimatedCommunicationMs: distributed.timing?.estimatedCommunicationMs ?? null,
  };
}

export function summarizeTimeBudget(report, source, modifiedAt) {
  if(report?.kind!=='time-budget-comparison'||!report.single||!report.distributed)return null;
  const {single,distributed}=report;
  if(!Number.isFinite(report.budgetMs)||!single.best?.config||!distributed.best?.config)return null;
  if(!Array.isArray(single.traces)||!Array.isArray(distributed.traces))return null;
  const summarizeRun=run=>({
    workerCount:run.workerCount,evaluatedCount:run.evaluatedCount,startedCount:run.startedCount,
    completedGenerations:run.completedGenerations,best:run.best,bestHistory:run.bestHistory??[],
    taskCounts:run.taskCounts??{},drainMs:run.drainMs??0,
    traces:run.traces.map(({candidateId,generation,workerId,startedAtMs,finishedAtMs,withinBudget,score,eligible})=>
      ({candidateId,generation,workerId,startedAtMs,finishedAtMs,withinBudget,score,eligible})),
  });
  return {
    source,recordedAt:report.finishedAt??modifiedAt,budgetMs:report.budgetMs,pattern:report.pattern,
    exhibitionPattern:report.exhibitionPattern??null,
    candidateMultiplier:report.candidateMultiplier,qualityImprovement:report.qualityImprovement,
    fairness:report.fairness,validation:report.validation,
    single:summarizeRun(single),distributed:summarizeRun(distributed),
  };
}

async function listJsonFiles(directory, depth = 0) {
  if (depth > 2) return [];
  let entries;
  try {
    entries = await fs.readdir(directory, {withFileTypes: true});
  } catch (error) {
    if (error.code === 'ENOENT') return [];
    throw error;
  }
  const nested = await Promise.all(entries.map(async entry => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return listJsonFiles(target, depth + 1);
    return entry.isFile() && entry.name.endsWith('.json') ? [target] : [];
  }));
  return nested.flat();
}

export async function findLatestComparisons(resultsDir) {
  const files = await listJsonFiles(resultsDir);
  const details = await Promise.all(files.map(async file => ({file, stat: await fs.stat(file)})));
  details.sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs);
  const latest = {};
  for (const {file, stat} of details.slice(0, 200)) {
    if (stat.size > 5_000_000) continue;
    try {
      const report = JSON.parse(await fs.readFile(file, 'utf8'));
      const source = path.relative(resultsDir, file);
      const timeBudget=summarizeTimeBudget(report,source,stat.mtime.toISOString());
      if(timeBudget&&!latest.timeBudget)latest.timeBudget=timeBudget;
      const summary = summarizeComparison(report, source, stat.mtime.toISOString());
      if (summary && !latest[summary.scenario]) latest[summary.scenario] = summary;
      if (latest.timeBudget&&[...SCENARIOS].every(scenario=>latest[scenario])) break;
    } catch (error) {
      if (error instanceof SyntaxError) continue;
      throw error;
    }
  }
  return latest;
}

export async function readExhibitionState(resultsDir) {
  const file=path.join(resultsDir,'exhibition','live.json');
  try {
    const state=JSON.parse(await fs.readFile(file,'utf8'));
    if(state?.schemaVersion!==1||!Number.isInteger(state.cycle)||typeof state.phase!=='string') {
      throw Error('展示モード状態の形式が不正です');
    }
    return state;
  } catch(error) {
    if(error.code==='ENOENT')return null;
    throw error;
  }
}

export async function readPatternCatalog(patternsFile) {
  const document=JSON.parse(await fs.readFile(patternsFile,'utf8'));
  if(document?.schemaVersion!==1||!Array.isArray(document.patterns)||document.patterns.length<2)throw Error('交通パターン一覧の形式が不正です');
  const ids=new Set();
  return document.patterns.map(item=>{
    if(!item||typeof item.id!=='string'||!/^[a-z0-9-]+$/.test(item.id)||ids.has(item.id)||typeof item.name!=='string'||typeof item.description!=='string')throw Error('交通パターン一覧の項目が不正です');
    ids.add(item.id);return {id:item.id,name:item.name,description:item.description};
  });
}

export async function readPatternRequest(resultsDir) {
  try {
    const request=JSON.parse(await fs.readFile(path.join(resultsDir,'exhibition','control.json'),'utf8'));
    return typeof request.requestedPatternId==='string'?request:null;
  } catch(error) {
    if(error.code==='ENOENT'||error instanceof SyntaxError)return null;
    throw error;
  }
}

export async function requestExhibitionPattern({resultsDir,patternsFile},patternId) {
  const patterns=await readPatternCatalog(patternsFile);
  if(!patterns.some(item=>item.id===patternId))throw Object.assign(Error('unknown pattern'),{statusCode:400});
  const directory=path.join(resultsDir,'exhibition');
  const file=path.join(directory,'control.json'),temporary=`${file}.${process.pid}.tmp`;
  await fs.mkdir(directory,{recursive:true});
  const request={requestedPatternId:patternId,requestedAt:new Date().toISOString()};
  await fs.writeFile(temporary,`${JSON.stringify(request,null,2)}\n`);
  await fs.rename(temporary,file);
  return request;
}

async function fetchHealth(ip, port, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://${ip}:${port}/health`, {signal: controller.signal});
    if (!response.ok) throw Error(`HTTP ${response.status}`);
    const body = await response.json();
    if (body.status !== 'ok' || typeof body.workerId !== 'string') throw Error('invalid response');
    return {workerId: body.workerId, version: body.version, ip, ready: true};
  } finally {
    clearTimeout(timer);
  }
}

export async function probeWorkers({service, port, expectedIds, timeoutMs = 1500}) {
  let addresses = [];
  try {
    const records = await dns.lookup(service, {all: true, family: 4});
    addresses = [...new Set(records.map(record => record.address))];
  } catch {
    // The response still contains every expected worker as unavailable.
  }
  const probes = await Promise.allSettled(addresses.map(ip => fetchHealth(ip, port, timeoutMs)));
  const ready = new Map(probes.filter(item => item.status === 'fulfilled').map(item => [item.value.workerId, item.value]));
  const workers = expectedIds.map(workerId => ready.get(workerId) ?? {workerId, ready: false});
  for (const worker of ready.values()) {
    if (!expectedIds.includes(worker.workerId)) workers.push(worker);
  }
  return workers.sort((a, b) => nodeNumber(a.workerId) - nodeNumber(b.workerId) || a.workerId.localeCompare(b.workerId));
}

export async function createDashboardSnapshot({resultsDir, patternsFile, service, port, expectedIds, probe = probeWorkers}) {
  const [resultsState, workersState, exhibitionState,patternsState,requestState] = await Promise.allSettled([
    findLatestComparisons(resultsDir),
    probe({service, port, expectedIds}),
    readExhibitionState(resultsDir),
    readPatternCatalog(patternsFile),
    readPatternRequest(resultsDir),
  ]);
  const errors = [];
  if (resultsState.status === 'rejected') errors.push(`結果を読めません: ${resultsState.reason.message}`);
  if (workersState.status === 'rejected') errors.push(`ワーカ状態を取得できません: ${workersState.reason.message}`);
  if (exhibitionState.status === 'rejected') errors.push(`展示モード状態を読めません: ${exhibitionState.reason.message}`);
  if (patternsState.status === 'rejected') errors.push(`交通パターンを読めません: ${patternsState.reason.message}`);
  if (requestState.status === 'rejected') errors.push(`交通パターン予約を読めません: ${requestState.reason.message}`);
  const workers = workersState.status === 'fulfilled'
    ? workersState.value
    : expectedIds.map(workerId => ({workerId, ready: false}));
  return {
    generatedAt: new Date().toISOString(),
    expectedWorkers: expectedIds.length,
    readyWorkers: workers.filter(worker => worker.ready).length,
    workers,
    results: resultsState.status === 'fulfilled' ? resultsState.value : {},
    exhibition: exhibitionState.status === 'fulfilled' ? exhibitionState.value : null,
    patterns: patternsState.status === 'fulfilled' ? patternsState.value : [],
    patternRequest: requestState.status === 'fulfilled' ? requestState.value : null,
    errors,
  };
}

function sendJson(response, status, value) {
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  });
  response.end(JSON.stringify(value));
}

export function createDashboardServer(options) {
  return http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://localhost');
      if(request.method==='POST'&&url.pathname==='/api/exhibition/pattern') {
        let body='',size=0;
        for await(const chunk of request) {
          size+=chunk.length;if(size>4096)throw Object.assign(Error('request too large'),{statusCode:413});
          body+=chunk;
        }
        let value;
        try {value=JSON.parse(body);} catch {throw Object.assign(Error('invalid json'),{statusCode:400});}
        const saved=await requestExhibitionPattern(options,value?.patternId);
        sendJson(response,202,{status:'queued',...saved});return;
      }
      if (request.method !== 'GET') {
        sendJson(response, 405, {error: 'method not allowed'});
        return;
      }
      if (url.pathname === '/health') {
        sendJson(response, 200, {status: 'ok'});
        return;
      }
      if (url.pathname === '/api/dashboard') {
        sendJson(response, 200, await createDashboardSnapshot(options));
        return;
      }
      const asset = ASSETS.get(url.pathname);
      if (!asset) {
        sendJson(response, 404, {error: 'not found'});
        return;
      }
      const [name, contentType] = asset;
      const body = await fs.readFile(path.join(APP_DIR, name));
      response.writeHead(200, {'content-type': contentType, 'cache-control': 'no-store'});
      response.end(body);
    } catch (error) {
      console.error(error);
      sendJson(response, error.statusCode??500, {error:error.statusCode?error.message:'dashboard server error'});
    }
  });
}

function integerEnvironment(name, fallback, minimum, maximum) {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw Error(`${name} must be an integer from ${minimum} to ${maximum}`);
  }
  return value;
}

export function optionsFromEnvironment() {
  const firstWorker = integerEnvironment('FIRST_WORKER', 10, 1, 999);
  const workerCount = integerEnvironment('EXPECTED_WORKERS', 12, 1, 100);
  return {
    resultsDir: process.env.RESULTS_DIR ?? '/results',
    patternsFile: process.env.PATTERNS_FILE ?? path.join(APP_DIR,'exhibition-patterns.json'),
    service: process.env.WORKER_SERVICE ?? 'traffic-workers',
    port: integerEnvironment('WORKER_PORT', 8787, 1, 65535),
    expectedIds: Array.from({length: workerCount}, (_, index) => `node${firstWorker + index}`),
  };
}

if (process.argv[1] && path.basename(process.argv[1]) === 'dashboard-server.mjs') {
  const listenPort = integerEnvironment('PORT', 8080, 1, 65535);
  const server = createDashboardServer(optionsFromEnvironment());
  server.listen(listenPort, '0.0.0.0', () => console.log(`traffic dashboard listening on ${listenPort}`));
  const stop = signal => server.close(() => {
    console.log(`traffic dashboard stopped by ${signal}`);
    process.exit(0);
  });
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
}
