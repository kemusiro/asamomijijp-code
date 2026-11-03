import {createHash, randomUUID} from 'node:crypto';
import {candidates, PATTERN_TRAINING_SEEDS, TRAINING_SEEDS, VERSION} from './engine.mjs';

function workerUrl(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol)) throw Error(`ワーカURLの方式が不正です: ${value}`);
  return url.href.replace(/\/$/, '');
}

async function fetchJson(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const started = performance.now();
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    const body = await response.json();
    if (!response.ok) throw Error(`${response.status}: ${body.error ?? response.statusText}`);
    return {body, roundTripMs: performance.now() - started};
  } catch (error) {
    if (error.name === 'AbortError') throw Error(`${timeoutMs}msでタイムアウトしました`);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export class ResultCollector {
  constructor(runId) {
    this.runId = runId;
    this.results = new Map();
    this.duplicates = 0;
  }

  accept(result) {
    if (result.runId !== this.runId || !Number.isInteger(result.taskId)) throw Error('応答の実行IDまたは候補IDが一致しません');
    if (this.results.has(result.taskId)) {
      this.duplicates++;
      return false;
    }
    this.results.set(result.taskId, result);
    return true;
  }
}

export async function probeWorker(url, timeoutMs = 3000) {
  const normalized = workerUrl(url);
  const {body, roundTripMs} = await fetchJson(`${normalized}/health`, {}, timeoutMs);
  if (body.status !== 'ok' || typeof body.workerId !== 'string') throw Error(`${normalized}のヘルス応答が不正です`);
  return {url: normalized, workerId: body.workerId, version: body.version, healthRoundTripMs: roundTripMs, active: true};
}

async function sendTask(worker, task, timeoutMs) {
  const {body, roundTripMs} = await fetchJson(`${worker.url}/evaluate`, {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify(task),
  }, timeoutMs);
  if (body.workerId !== worker.workerId || body.version !== VERSION || body.taskId !== task.taskId) {
    throw Error(`${worker.workerId}の応答内容が一致しません`);
  }
  return {...body, roundTripMs};
}

export async function runDistributed({
  workers,
  scenario,
  configs = candidates(),
  patterns,
  pattern,
  kind = 'signal',
  seeds = TRAINING_SEEDS,
  timeoutMs = 5000,
  maxRetries = 1,
  dispatchDeadlineMs,
  dispatchDeadlineAt,
  allowPartial = false,
  runId = randomUUID(),
  onProgress = () => {},
} = {}) {
  if (!Array.isArray(workers) || !workers.length) throw Error('ワーカを1台以上指定してください');
  if (!['signal','traffic-pattern'].includes(kind)) throw Error('評価種別が不正です');
  if (kind==='signal' && pattern===undefined && !['eastwest', 'balanced'].includes(scenario)) throw Error('交通条件が不正です');
  const items=kind==='traffic-pattern'?patterns:configs;
  if (!Array.isArray(items) || !items.length) throw Error('候補がありません');
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1) throw Error('タイムアウトは1ms以上の整数で指定してください');
  if (!Number.isInteger(maxRetries) || maxRetries < 0 || maxRetries > 10) throw Error('再試行回数は0から10で指定してください');
  if (dispatchDeadlineMs!==undefined && (!Number.isFinite(dispatchDeadlineMs)||dispatchDeadlineMs<=0)) throw Error('配布期限は正の数で指定してください');
  if (dispatchDeadlineAt!==undefined && !Number.isFinite(dispatchDeadlineAt)) throw Error('絶対配布期限が不正です');
  if (dispatchDeadlineMs!==undefined && dispatchDeadlineAt!==undefined) throw Error('相対配布期限と絶対配布期限は同時に指定できません');
  const urls = [...new Set(workers.map(workerUrl))];
  const states = await Promise.all(urls.map(url => probeWorker(url, timeoutMs)));
  if (states.some(worker => worker.version !== VERSION)) throw Error('制御側とワーカのバージョンが一致しません');
  if (new Set(states.map(worker => worker.workerId)).size !== states.length) throw Error('ワーカIDが重複しています');
  const collector = new ResultCollector(runId);
  let pending = items.map((value, taskId) => ({taskId, value, attempts: 0, errors: []}));
  const failures = [];
  const started = performance.now();
  const deadline=dispatchDeadlineAt??(dispatchDeadlineMs===undefined?Infinity:started+dispatchDeadlineMs);
  let deadlineReached=false;

  while (pending.length) {
    const active = states.filter(worker => worker.active);
    if (!active.length) throw Error(`利用可能なワーカがありません: ${failures.map(item => item.error).join(' / ')}`);
    const queue = pending;
    const retry = [];
    let cursor = 0;
    await Promise.all(active.map(async worker => {
      while (worker.active && cursor < queue.length) {
        if (performance.now()>=deadline) { deadlineReached=true; break; }
        const item = queue[cursor++];
        item.attempts++;
        const assignedAtMs=performance.now()-started;
        const task = kind==='traffic-pattern'
          ? {runId,taskId:item.taskId,kind,pattern:item.value,seeds}
          : {runId,taskId:item.taskId,kind,scenario,pattern,config:item.value,seeds};
        try {
          const result = await sendTask(worker, task, timeoutMs);
          collector.accept({...result,attempts:item.attempts,queuedAtMs:0,startedAtMs:assignedAtMs,finishedAtMs:performance.now()-started});
          onProgress({
            done:collector.results.size,total:items.length,workerId:worker.workerId,taskId:item.taskId,
            eligible:result.eligible,score:result.score,computeMs:result.computeMs,roundTripMs:result.roundTripMs,
            startedAtMs:assignedAtMs,finishedAtMs:performance.now()-started,
          });
        } catch (error) {
          const message = `${worker.workerId}: task ${item.taskId}: ${error.message}`;
          item.errors.push(message);
          failures.push({workerId: worker.workerId, taskId: item.taskId, attempt: item.attempts, error: message});
          worker.active = false;
          worker.error = error.message;
          retry.push(item);
        }
      }
    }));
    for (const item of retry) {
      if (item.attempts > maxRetries) throw Error(`候補${item.taskId}は${item.attempts}回失敗しました: ${item.errors.join(' / ')}`);
    }
    if(deadlineReached) break;
    pending = retry;
  }

  const elapsedMs = performance.now() - started;
  const results = [...collector.results.values()].sort((a, b) => a.taskId - b.taskId);
  if (!allowPartial && results.length !== items.length) throw Error(`結果数が一致しません: ${results.length}/${items.length}`);
  if (!results.length) {
    if(!allowPartial)throw Error('期限内に開始できた候補がありません');
    return {
      runId,kind,scenario:scenario??(pattern?'evolved-pattern':undefined),version:VERSION,
      requestedCandidateCount:items.length,candidateCount:0,complete:false,
      dispatchDeadlineMs:dispatchDeadlineMs??null,elapsedMs,resultHash:createHash('sha256').update('[]').digest('hex'),best:null,
      timing:{workerComputeMs:0,roundTripMs:0,estimatedCommunicationMs:0},
      workers:states.map(({url,workerId,version,healthRoundTripMs,active,error})=>({url,workerId,version,healthRoundTripMs,active,error})),
      taskCounts:Object.fromEntries(states.map(worker=>[worker.workerId,0])),retries:failures.length,
      duplicatesIgnored:collector.duplicates,failures,results,
    };
  }
  const eligible = results.filter(result => result.eligible && Number.isFinite(result.score));
  if (!eligible.length) throw Error('採用可能な候補がありません');
  const bestResult = eligible.toSorted((a, b) => a.score - b.score || a.taskId - b.taskId)[0];
  const resultHash = createHash('sha256').update(JSON.stringify(results.map(result => [result.taskId, result.eligible, result.score]))).digest('hex');
  const taskCounts = Object.fromEntries(states.map(worker => [worker.workerId, results.filter(result => result.workerId === worker.workerId).length]));
  const workerComputeMs = results.reduce((sum, result) => sum + result.computeMs, 0);
  const roundTripMs = results.reduce((sum, result) => sum + result.roundTripMs, 0);
  return {
    runId,
    kind,
    scenario:scenario??(pattern?'evolved-pattern':undefined),
    version: VERSION,
    requestedCandidateCount:items.length,
    candidateCount: results.length,
    complete:results.length===items.length,
    dispatchDeadlineMs:dispatchDeadlineMs??null,
    elapsedMs,
    best: {
      taskId:bestResult.taskId,
      ...(kind==='traffic-pattern'?{pattern:items[bestResult.taskId]}:{config:items[bestResult.taskId]}),
      score:bestResult.score,
      details:bestResult.details,
    },
    resultHash,
    timing: {
      workerComputeMs,
      roundTripMs,
      estimatedCommunicationMs: Math.max(0, roundTripMs - workerComputeMs),
    },
    workers: states.map(({url, workerId, version, healthRoundTripMs, active, error}) => ({url, workerId, version, healthRoundTripMs, active, error})),
    taskCounts,
    retries: failures.length,
    duplicatesIgnored: collector.duplicates,
    failures,
    results,
  };
}

export async function compareWorkerCounts(options) {
  const workers = [...new Set(options.workers.map(workerUrl))];
  if (workers.length < 2) throw Error('比較には2台以上のワーカが必要です');
  const single = await runDistributed({...options, workers: workers.slice(0, 1), runId: `${options.runId ?? randomUUID()}-single`});
  const distributed = await runDistributed({...options, workers, runId: `${options.runId ?? randomUUID()}-distributed`});
  const same = single.resultHash === distributed.resultHash &&
    single.best.taskId === distributed.best.taskId && single.best.score === distributed.best.score;
  if (!same) throw Error('1台構成と分散構成の結果が一致しません');
  return {single, distributed, same, speedup: single.elapsedMs / distributed.elapsedMs};
}
