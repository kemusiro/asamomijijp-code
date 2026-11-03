import fs from 'node:fs/promises';
import os from 'node:os';
import {assess, PATTERN_TRAINING_SEEDS, PATTERN_VALIDATION_SEEDS, random} from './engine.mjs';
import {initialSignalPopulation, nextSignalPopulation} from './genetic.mjs';
import {runDistributed} from './distributed.mjs';

function bestHistory(results) {
  let best=Infinity;
  return results.toSorted((a,b)=>a.finishedAtMs-b.finishedAtMs||a.candidateId-b.candidateId).flatMap(result=>{
    if(!result.eligible||!Number.isFinite(result.score)||result.score>=best)return [];
    best=result.score;
    return [{atMs:result.finishedAtMs,score:result.score,candidateId:result.candidateId,generation:result.generation}];
  });
}

function validation(config,pattern) {
  const result=assess(config,pattern,PATTERN_VALIDATION_SEEDS);
  return {
    eligible:result.eligible,
    meanWait:result.score,
    seeds:PATTERN_VALIDATION_SEEDS,
    pairs:result.pairs.map(({seed,base,candidate})=>({
      seed,
      baseMeanWait:base.meanWait,
      candidateMeanWait:candidate.meanWait,
      baseArrived:base.arrived,
      candidateArrived:candidate.arrived,
    })),
  };
}

export async function runSignalEvolutionBudget({
  workers,
  pattern,
  budgetMs=15000,
  populationSize=12,
  seed=7026,
  timeoutMs=10000,
  maxRetries=1,
  runId=`budget-${Date.now()}`,
  onProgress=()=>{},
}={}) {
  if(!Number.isInteger(budgetMs)||budgetMs<1000||budgetMs>300000)throw Error('時間予算は1000から300000msで指定してください');
  let population=initialSignalPopulation(seed,populationSize);
  const rng=random(seed+1), traces=[];
  let generation=0,completedGenerations=0,candidateBase=0;
  let liveBest=null;
  const started=performance.now();
  while(performance.now()-started<budgetMs) {
    const before=performance.now()-started;
    const result=await runDistributed({
      workers,kind:'signal',pattern,configs:population,seeds:PATTERN_TRAINING_SEEDS,
      timeoutMs,maxRetries,dispatchDeadlineAt:started+budgetMs,allowPartial:true,
      runId:`${runId}-g${generation}`,
      onProgress:event=>{
        const candidateId=candidateBase+event.taskId;
        if(event.eligible&&Number.isFinite(event.score)&&(!liveBest||event.score<liveBest.score)) {
          liveBest={candidateId,generation,config:population[event.taskId],score:event.score};
        }
        const finishedAtMs=performance.now()-started;
        onProgress({
          ...event,generation,candidateId,completedCandidates:candidateBase+event.done,
          completedGenerations:generation+(event.done===population.length?1:0),
          startedAtMs:Math.max(0,finishedAtMs-event.roundTripMs),finishedAtMs,best:liveBest,
        });
      },
    });
    const callElapsed=performance.now()-started-before;
    const probeMs=Math.max(0,callElapsed-result.elapsedMs);
    const traceOffset=before+probeMs;
    const generationTraces=result.results.map(item=>({
      candidateId:candidateBase+item.taskId,generation,index:item.taskId,workerId:item.workerId,
      queuedAtMs:traceOffset+item.queuedAtMs,startedAtMs:traceOffset+item.startedAtMs,finishedAtMs:traceOffset+item.finishedAtMs,
      computeMs:item.computeMs,roundTripMs:item.roundTripMs,eligible:item.eligible,score:item.score,
      config:population[item.taskId],withinBudget:traceOffset+item.finishedAtMs<=budgetMs,
    }));
    traces.push(...generationTraces);
    const generationWithinBudget=generationTraces.length===population.length&&generationTraces.every(item=>item.withinBudget);
    if(!generationWithinBudget)break;
    completedGenerations++;
    population=nextSignalPopulation(population,result.results,rng);
    candidateBase+=result.results.length;
    generation++;
  }
  const elapsedMs=performance.now()-started;
  const accepted=traces.filter(item=>item.withinBudget&&item.eligible&&Number.isFinite(item.score));
  if(!accepted.length)throw Error('時間予算内に採用可能な候補が完了しませんでした');
  const best=accepted.toSorted((a,b)=>a.score-b.score||a.candidateId-b.candidateId)[0];
  const counts={};
  for(const item of traces.filter(item=>item.withinBudget))counts[item.workerId]=(counts[item.workerId]??0)+1;
  return {
    runId,budgetMs,elapsedMs,drainMs:Math.max(0,elapsedMs-budgetMs),workerCount:workers.length,
    populationSize,seed,trainingSeeds:PATTERN_TRAINING_SEEDS,
    evaluatedCount:traces.filter(item=>item.withinBudget).length,
    startedCount:traces.length,completedGenerations,
    best:{candidateId:best.candidateId,generation:best.generation,config:best.config,score:best.score},
    bestHistory:bestHistory(accepted),taskCounts:counts,traces,
  };
}

export async function compareTimeBudgets(options) {
  const workers=[...new Set(options.workers)];
  if(workers.length<2)throw Error('比較には2台以上のワーカが必要です');
  const baseId=options.runId??`budget-${Date.now()}`;
  const onPhase=options.onPhase??(()=>{}),onProgress=options.onProgress??(()=>{});
  onPhase({phase:'single',status:'started'});
  const single=await runSignalEvolutionBudget({...options,workers:workers.slice(0,1),runId:`${baseId}-single`,onProgress:event=>onProgress({...event,phase:'single'})});
  onPhase({phase:'single',status:'completed',result:single});
  onPhase({phase:'distributed',status:'started'});
  const distributed=await runSignalEvolutionBudget({...options,workers,runId:`${baseId}-distributed`,onProgress:event=>onProgress({...event,phase:'distributed'})});
  onPhase({phase:'distributed',status:'completed',result:distributed});
  onPhase({phase:'validation',status:'started'});
  const singleValidation=validation(single.best.config,options.pattern);
  const distributedValidation=validation(distributed.best.config,options.pattern);
  const comparison={
    kind:'time-budget-comparison',algorithm:'genetic',version:1,budgetMs:options.budgetMs??15000,
    pattern:options.pattern,
    fairness:{sameInitialPopulation:true,samePopulationSize:true,sameSeed:true,completedByDeadlineOnly:true},
    single,distributed,
    validation:{single:singleValidation,distributed:distributedValidation},
    candidateMultiplier:distributed.evaluatedCount/single.evaluatedCount,
    qualityImprovement:singleValidation.meanWait-distributedValidation.meanWait,
  };
  onPhase({phase:'validation',status:'completed',result:comparison.validation});
  return comparison;
}

function option(name,fallback) {
  const index=process.argv.indexOf(name);
  if(index<0)return fallback;
  if(!process.argv[index+1])throw Error(`${name}の値が必要です`);
  return process.argv[index+1];
}

if(process.argv[1]&&process.argv[1].endsWith('time-budget-benchmark.mjs')) {
  const workers=option('--workers','').split(',').map(value=>value.trim()).filter(Boolean);
  if(workers.length<2)throw Error('--workersへ2台以上を指定してください');
  const outerPath=option('--outer-result','');
  if(!outerPath)throw Error('--outer-resultへ外側探索結果JSONを指定してください');
  const outer=JSON.parse(await fs.readFile(outerPath,'utf8'));
  if(outer.kind!=='outer-traffic-search'||!outer.best?.pattern)throw Error('外側探索結果JSONが不正です');
  const startedAt=new Date().toISOString();
  const comparison=await compareTimeBudgets({
    workers,pattern:outer.best.pattern,
    budgetMs:Number(option('--budget-ms','15000')),
    populationSize:Number(option('--population','12')),
    seed:Number(option('--seed','7026')),
    timeoutMs:Number(option('--timeout-ms','10000')),
    maxRetries:Number(option('--retries','1')),
    onProgress:({generation,done,total,workerId})=>console.error(`generation=${generation+1} progress=${done}/${total} worker=${workerId}`),
  });
  console.log(JSON.stringify({startedAt,finishedAt:new Date().toISOString(),coordinator:os.hostname(),node:process.version,outerResult:outerPath,...comparison},null,2));
}
