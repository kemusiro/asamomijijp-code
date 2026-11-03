import {promises as dns} from 'node:dns';
import {promises as fs} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {compareTimeBudgets} from './time-budget-benchmark.mjs';
import {validateTrafficPattern} from './engine.mjs';

const APP_DIR=path.dirname(fileURLToPath(import.meta.url));

function integer(value,name,minimum,maximum) {
  const parsed=Number(value);
  if(!Number.isInteger(parsed)||parsed<minimum||parsed>maximum)throw Error(`${name} must be an integer from ${minimum} to ${maximum}`);
  return parsed;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function validatePatternCatalog(document) {
  if(document?.schemaVersion!==1||!Array.isArray(document.patterns)||document.patterns.length<2) {
    throw Error('交通パターン一覧の形式が不正です');
  }
  const ids=new Set();
  for(const item of document.patterns) {
    if(!item||typeof item.id!=='string'||!/^[a-z0-9-]+$/.test(item.id)||ids.has(item.id))throw Error('交通パターンIDが不正または重複しています');
    if(typeof item.name!=='string'||!item.name.trim()||typeof item.description!=='string'||!item.description.trim())throw Error(`交通パターン ${item.id} の表示情報が不正です`);
    validateTrafficPattern(item.pattern);ids.add(item.id);
  }
  return document.patterns;
}

export async function consumePatternRequest(file,patterns) {
  const consuming=`${file}.consuming`;
  try {
    await fs.rename(file,consuming);
    const request=JSON.parse(await fs.readFile(consuming,'utf8'));
    await fs.unlink(consuming);
    return patterns.find(item=>item.id===request.requestedPatternId)??null;
  } catch(error) {
    if(error.code==='ENOENT')return null;
    if(error instanceof SyntaxError) {
      await fs.unlink(consuming).catch(()=>{});
      return null;
    }
    throw error;
  }
}

export async function atomicWriteJson(file,value) {
  await fs.mkdir(path.dirname(file),{recursive:true});
  const temporary=`${file}.${process.pid}.tmp`;
  await fs.writeFile(temporary,`${JSON.stringify(value,null,2)}\n`);
  await fs.rename(temporary,file);
}

async function fetchHealth(ip,port,fetchImpl,timeoutMs=2000) {
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try {
    const response=await fetchImpl(`http://${ip}:${port}/health`,{signal:controller.signal});
    if(!response.ok)throw Error(`HTTP ${response.status}`);
    const body=await response.json();
    if(body.status!=='ok'||typeof body.workerId!=='string')throw Error('invalid health response');
    return {workerId:body.workerId,url:`http://${ip}:${port}`};
  } finally {
    clearTimeout(timer);
  }
}

export async function discoverWorkers({service,port,expectedWorkers,lookup=dns.lookup,fetchImpl=fetch}) {
  const records=await lookup(service,{all:true,family:4});
  const addresses=[...new Set(records.map(record=>record.address))];
  const probes=await Promise.allSettled(addresses.map(ip=>fetchHealth(ip,port,fetchImpl)));
  const byId=new Map();
  for(const item of probes)if(item.status==='fulfilled')byId.set(item.value.workerId,item.value);
  const workers=[...byId.values()].sort((a,b)=>a.workerId.localeCompare(b.workerId,undefined,{numeric:true}));
  if(workers.length!==expectedWorkers)throw Error(`ワーカ応答数が不足しています: ${workers.length}/${expectedWorkers}`);
  return workers;
}

function summarizeRun(run) {
  if(!run)return null;
  return {
    workerCount:run.workerCount,evaluatedCount:run.evaluatedCount,startedCount:run.startedCount,
    completedGenerations:run.completedGenerations,best:run.best,bestHistory:run.bestHistory??[],
    taskCounts:run.taskCounts??{},drainMs:run.drainMs??0,
  };
}

export function createStatePublisher(file,{write=atomicWriteJson,intervalMs=250}={}) {
  let pending=null,timer=null,chain=Promise.resolve(),lastError=null;
  const enqueue=()=>{
    if(!pending)return;
    const value=pending;pending=null;
    chain=chain.catch(()=>{}).then(async()=>{await write(file,value);lastError=null;}).catch(error=>{lastError=error;});
  };
  return {
    publish(value,{immediate=false}={}) {
      pending=clone(value);
      if(immediate) {
        if(timer)clearTimeout(timer);
        timer=null;enqueue();
      } else if(!timer) {
        timer=setTimeout(()=>{timer=null;enqueue();},intervalMs);
      }
    },
    async flush() {
      if(timer)clearTimeout(timer);
      timer=null;enqueue();await chain;
      if(lastError)throw lastError;
    },
  };
}

async function previousCycle(file) {
  try {
    const state=JSON.parse(await fs.readFile(file,'utf8'));
    return Number.isInteger(state.cycle)?state.cycle:0;
  } catch(error) {
    if(error.code==='ENOENT'||error instanceof SyntaxError)return 0;
    throw error;
  }
}

function liveEvent(event) {
  return {
    candidateId:event.candidateId,generation:event.generation,workerId:event.workerId,
    startedAtMs:event.startedAtMs,finishedAtMs:event.finishedAtMs,
    score:event.score,eligible:event.eligible,
  };
}

export async function runExhibitionMode(options={},dependencies={}) {
  const now=dependencies.now??(()=>Date.now());
  const sleep=dependencies.sleep??(milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds)));
  const discover=dependencies.discover??discoverWorkers;
  const compare=dependencies.compare??compareTimeBudgets;
  const write=dependencies.write??atomicWriteJson;
  const shouldStop=dependencies.shouldStop??(()=>false);
  const readPrevious=dependencies.previousCycle??previousCycle;
  const consumeRequest=dependencies.consumePatternRequest??consumePatternRequest;
  const resultsDir=options.resultsDir??'/results';
  const liveFile=path.join(resultsDir,'exhibition','live.json');
  const controlFile=path.join(resultsDir,'exhibition','control.json');
  const patterns=validatePatternCatalog({schemaVersion:1,patterns:options.patterns});
  let cycle=options.initialCycle;
  while(cycle===undefined&&!shouldStop()) {
    try {
      cycle=(await readPrevious(liveFile))+1;
    } catch(error) {
      console.error(`展示状態を読めません。${options.retryMs}ms後に再試行します: ${error.message}`);
      await sleep(options.retryMs);
    }
  }
  if(cycle===undefined)return {completedCycles:0,nextCycle:null};
  let completedCycles=0;
  const maxCycles=options.maxCycles??Infinity;
  let selected=null,patternSelection='automatic';

  while(!shouldStop()&&completedCycles<maxCycles) {
    if(!selected) {
      try {
        const requested=await consumeRequest(controlFile,patterns);
        selected=requested??patterns[(cycle-1)%patterns.length];
        patternSelection=requested?'requested':'automatic';
      } catch(error) {
        console.error(`交通パターン予約を読めません。${options.retryMs}ms後に再試行します: ${error.message}`);
        await sleep(options.retryMs);continue;
      }
    }
    const pattern=selected.pattern;
    const cycleId=`cycle-${String(cycle).padStart(4,'0')}-${new Date(now()).toISOString().replaceAll(/[:.]/g,'')}`;
    const startedAt=new Date(now()).toISOString();
    const state={
      schemaVersion:1,mode:'automatic',cycle,cycleId,phase:'starting',status:'running',
      startedAt,phaseStartedAt:startedAt,updatedAt:startedAt,budgetMs:options.budgetMs,
      pattern:{id:selected.id,name:selected.name,description:selected.description},
      patternSelection,
      expectedWorkers:options.expectedWorkers,completedCandidates:0,completedGenerations:0,
      taskCounts:{},recentEvents:[],bestHistory:[],best:null,single:null,distributed:null,
    };
    const publisher=createStatePublisher(liveFile,{write,intervalMs:options.publishIntervalMs??250});
    const publish=(immediate=false)=>{
      state.updatedAt=new Date(now()).toISOString();
      publisher.publish(state,{immediate});
    };
    publish(true);
    try {
      const workerRecords=await discover({
        service:options.service,port:options.port,expectedWorkers:options.expectedWorkers,
      });
      state.workers=workerRecords.map(worker=>worker.workerId);
      const onPhase=event=>{
        if(event.status==='started') {
          state.phase=event.phase;state.phaseStartedAt=new Date(now()).toISOString();
          state.completedCandidates=0;state.completedGenerations=0;state.taskCounts={};
          state.recentEvents=[];state.bestHistory=[];state.best=null;
        } else if(event.phase==='single')state.single=summarizeRun(event.result);
        else if(event.phase==='distributed')state.distributed=summarizeRun(event.result);
        publish(true);
      };
      const onProgress=event=>{
        state.completedCandidates=event.completedCandidates;
        state.completedGenerations=event.completedGenerations;
        state.best=event.best;
        state.taskCounts[event.workerId]=(state.taskCounts[event.workerId]??0)+1;
        state.recentEvents.push(liveEvent(event));
        if(state.recentEvents.length>240)state.recentEvents.splice(0,state.recentEvents.length-240);
        const last=state.bestHistory.at(-1);
        if(event.best&&(!last||event.best.score<last.score))state.bestHistory.push({atMs:event.finishedAtMs,score:event.best.score,candidateId:event.best.candidateId,generation:event.best.generation});
        publish();
      };
      const comparison=await compare({
        workers:workerRecords.map(worker=>worker.url),pattern,
        budgetMs:options.budgetMs,populationSize:options.populationSize,seed:options.seedBase,
        timeoutMs:options.timeoutMs,maxRetries:options.maxRetries,runId:cycleId,onPhase,onProgress,
      });
      const finishedAt=new Date(now()).toISOString();
      const report={startedAt,finishedAt,coordinator:process.env.HOSTNAME??'unknown',exhibitionCycle:cycle,
        exhibitionPattern:{id:selected.id,name:selected.name,description:selected.description},...comparison};
      const relativeResult=path.join('exhibition','cycles',`${cycleId}.json`);
      await write(path.join(resultsDir,relativeResult),report);
      state.phase='result';state.status='running';state.phaseStartedAt=finishedAt;state.finishedAt=finishedAt;
      state.holdUntil=new Date(now()+options.resultHoldMs).toISOString();state.result=relativeResult;
      state.single=summarizeRun(comparison.single);state.distributed=summarizeRun(comparison.distributed);
      state.validation=comparison.validation;state.candidateMultiplier=comparison.candidateMultiplier;
      state.qualityImprovement=comparison.qualityImprovement;state.completedCandidates=comparison.distributed.evaluatedCount;
      state.completedGenerations=comparison.distributed.completedGenerations;state.taskCounts=comparison.distributed.taskCounts;
      state.best=comparison.distributed.best;state.bestHistory=comparison.distributed.bestHistory;
      state.recentEvents=comparison.distributed.traces.slice(-240).map(liveEvent);
      publish(true);await publisher.flush();
      completedCycles++;
      if(completedCycles<maxCycles&&!shouldStop())await sleep(options.resultHoldMs);
      cycle++;selected=null;patternSelection='automatic';
    } catch(error) {
      state.phase='recovering';state.status='degraded';state.error=error.message;
      state.phaseStartedAt=new Date(now()).toISOString();state.retryAt=new Date(now()+options.retryMs).toISOString();
      publish(true);
      try {await publisher.flush();} catch(writeError) {console.error(`復旧状態を保存できません: ${writeError.message}`);}
      if(shouldStop())break;
      await sleep(options.retryMs);
    } finally {
      try {await publisher.flush();} catch(writeError) {console.error(`展示状態を保存できません: ${writeError.message}`);}
    }
  }
  return {completedCycles,nextCycle:cycle};
}

export async function optionsFromEnvironment(environment=process.env) {
  const patternsFile=environment.PATTERNS_FILE??path.join(APP_DIR,'exhibition-patterns.json');
  const patternDocument=JSON.parse(await fs.readFile(patternsFile,'utf8'));
  return {
    resultsDir:environment.RESULTS_DIR??'/results',patterns:validatePatternCatalog(patternDocument),
    service:environment.WORKER_SERVICE??'traffic-workers',
    port:integer(environment.WORKER_PORT??8787,'WORKER_PORT',1,65535),
    expectedWorkers:integer(environment.EXPECTED_WORKERS??12,'EXPECTED_WORKERS',2,100),
    budgetMs:integer(environment.BUDGET_MS??15000,'BUDGET_MS',1000,300000),
    populationSize:integer(environment.POPULATION_SIZE??12,'POPULATION_SIZE',4,1000),
    seedBase:integer(environment.SEED_BASE??7026,'SEED_BASE',0,2147483647),
    timeoutMs:integer(environment.WORKER_TIMEOUT_MS??10000,'WORKER_TIMEOUT_MS',1000,300000),
    maxRetries:integer(environment.MAX_RETRIES??1,'MAX_RETRIES',0,10),
    resultHoldMs:integer(environment.RESULT_HOLD_MS??30000,'RESULT_HOLD_MS',1000,3600000),
    retryMs:integer(environment.RETRY_MS??5000,'RETRY_MS',1000,300000),
    publishIntervalMs:integer(environment.PUBLISH_INTERVAL_MS??250,'PUBLISH_INTERVAL_MS',50,5000),
    maxCycles:environment.MAX_CYCLES?integer(environment.MAX_CYCLES,'MAX_CYCLES',1,1000000):Infinity,
  };
}

if(process.argv[1]&&path.basename(process.argv[1])==='exhibition-runner.mjs') {
  let stopping=false;
  const stop=signal=>{stopping=true;console.log(`exhibition runner stopping after current operation: ${signal}`);};
  process.on('SIGINT',stop);process.on('SIGTERM',stop);
  const options=await optionsFromEnvironment();
  await runExhibitionMode(options,{shouldStop:()=>stopping});
}
