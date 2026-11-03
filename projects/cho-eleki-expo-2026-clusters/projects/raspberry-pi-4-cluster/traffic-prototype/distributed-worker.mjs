import http from 'node:http';
import os from 'node:os';
import {
  assessTrafficPattern,
  evaluate,
  PATTERN_TRAINING_SEEDS,
  TRAINING_SEEDS,
  validate,
  validateTrafficPattern,
  VERSION,
} from './engine.mjs';

const MAX_BODY_BYTES = 64 * 1024;

function send(response, status, body) {
  const data = JSON.stringify(body);
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(data),
  });
  response.end(data);
}

async function readJson(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > MAX_BODY_BYTES) throw Error('要求が64KiBを超えています');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function checkTask(task) {
  if (!task || typeof task !== 'object') throw Error('要求がJSONオブジェクトではありません');
  if (typeof task.runId !== 'string' || !task.runId || task.runId.length > 128) throw Error('runIdが不正です');
  if (!Number.isInteger(task.taskId) || task.taskId < 0) throw Error('taskIdが不正です');
  const kind=task.kind??'signal';
  if (!['signal','traffic-pattern'].includes(kind)) throw Error('評価種別が不正です');
  if (kind==='traffic-pattern') validateTrafficPattern(task.pattern);
  else {
    if (task.pattern!==undefined) validateTrafficPattern(task.pattern);
    else if (!['eastwest', 'balanced'].includes(task.scenario)) throw Error('交通条件が不正です');
    validate(task.config);
  }
  if (task.seeds !== undefined && (!Array.isArray(task.seeds) || !task.seeds.length || task.seeds.some(seed => !Number.isInteger(seed)))) {
    throw Error('探索シードが不正です');
  }
}

async function defaultEvaluator(task) {
  const started = performance.now();
  if ((task.kind??'signal')==='traffic-pattern') {
    const assessment=assessTrafficPattern(task.pattern,task.seeds??PATTERN_TRAINING_SEEDS);
    return {
      eligible:assessment.eligible,
      score:Number.isFinite(assessment.score)?assessment.score:null,
      details:assessment.eligible?{
        fitness:assessment.fitness,
        robustRatio:assessment.robustRatio,
        medianImprovement:assessment.medianImprovement,
        bestSignal:assessment.best.config,
        bestMeanWait:assessment.best.score,
        baseMeanWait:assessment.bases.reduce((sum,item)=>sum+item.result.meanWait,0)/assessment.bases.length,
      }:{minimumTraffic:assessment.minimumTraffic,meaningfulBaseline:assessment.meaningfulBaseline},
      computeMs:performance.now()-started,
    };
  }
  const score = evaluate(task.config, task.pattern??task.scenario, task.seeds ?? TRAINING_SEEDS);
  return {
    eligible: Number.isFinite(score),
    score: Number.isFinite(score) ? score : null,
    computeMs: performance.now() - started,
  };
}

export function createEvaluationServer({workerId = os.hostname(), evaluator = defaultEvaluator, maxCacheEntries = 2048} = {}) {
  if (!Number.isInteger(maxCacheEntries) || maxCacheEntries < 1) throw Error('キャッシュ件数は1以上の整数で指定してください');
  const cache = new Map();
  return http.createServer(async (request, response) => {
    if (request.method === 'GET' && request.url === '/health') {
      send(response, 200, {status: 'ok', workerId, version: VERSION, cacheEntries: cache.size});
      return;
    }
    if (request.method !== 'POST' || request.url !== '/evaluate') {
      send(response, 404, {error: 'not found'});
      return;
    }
    try {
      const task = await readJson(request);
      checkTask(task);
      const key = `${task.runId}:${task.taskId}`;
      const kind=task.kind??'signal';
      const defaultSeeds=kind==='traffic-pattern'?PATTERN_TRAINING_SEEDS:TRAINING_SEEDS;
      const signature = JSON.stringify([kind,task.scenario,task.pattern,task.seeds ?? defaultSeeds,task.config]);
      const previous = cache.get(key);
      if (previous) {
        if (previous.signature !== signature) {
          send(response, 409, {error: '同じ実行IDと候補IDに異なる内容が指定されました'});
          return;
        }
        send(response, 200, {...previous.result, cached: true});
        return;
      }
      const measured = await evaluator(task);
      const result = {runId: task.runId, taskId: task.taskId, workerId, version: VERSION, ...measured, cached: false};
      if (cache.size >= maxCacheEntries) cache.delete(cache.keys().next().value);
      cache.set(key, {signature, result});
      send(response, 200, result);
    } catch (error) {
      send(response, 400, {error: error.message});
    }
  });
}

export async function listen(server, {host = '127.0.0.1', port = 8787} = {}) {
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, resolve);
  });
  return server.address();
}
