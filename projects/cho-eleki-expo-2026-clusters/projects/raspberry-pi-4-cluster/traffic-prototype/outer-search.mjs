import os from 'node:os';
import {assess, PATTERN_TRAINING_SEEDS, PATTERN_VALIDATION_SEEDS} from './engine.mjs';
import {evolutionRandom, initialTrafficPopulation, nextTrafficPopulation} from './genetic.mjs';
import {runDistributed} from './distributed.mjs';

function median(values) {
  const sorted=[...values].sort((a,b)=>a-b), middle=Math.floor(sorted.length/2);
  return sorted.length%2?sorted[middle]:(sorted[middle-1]+sorted[middle])/2;
}

function validationSummary(config,pattern,seeds=PATTERN_VALIDATION_SEEDS) {
  const assessment=assess(config,pattern,seeds);
  const pairs=assessment.pairs.map(({seed,base,candidate})=>({
    seed,
    base:{generated:base.generated,arrived:base.arrived,meanWait:base.meanWait,direction:base.direction},
    candidate:{generated:candidate.generated,arrived:candidate.arrived,meanWait:candidate.meanWait,direction:candidate.direction},
    ratio:base.meanWait/Math.max(candidate.meanWait,0.5),
    improvement:base.meanWait-candidate.meanWait,
  }));
  return {
    eligible:assessment.eligible,
    seeds,
    robustRatio:Math.min(...pairs.map(pair=>pair.ratio)),
    medianRatio:median(pairs.map(pair=>pair.ratio)),
    medianImprovement:median(pairs.map(pair=>pair.improvement)),
    pairs,
  };
}

export async function runOuterSearch({
  workers,
  populationSize=12,
  generations=5,
  seed=6026,
  timeoutMs=60000,
  maxRetries=1,
  runId=`outer-${Date.now()}`,
  onProgress=()=>{},
}={}) {
  if(!Number.isInteger(generations)||generations<1||generations>50) throw Error('世代数は1から50で指定してください');
  let population=initialTrafficPopulation(seed,populationSize);
  const rng=evolutionRandom(seed+1), history=[];
  let best;
  const started=performance.now();
  for(let generation=0;generation<generations;generation++) {
    const result=await runDistributed({
      workers,kind:'traffic-pattern',patterns:population,seeds:PATTERN_TRAINING_SEEDS,
      timeoutMs,maxRetries,runId:`${runId}-g${generation}`,
      onProgress:event=>onProgress({...event,generation}),
    });
    const generationBest={...result.best,generation};
    if(!best||generationBest.score<best.score) best=generationBest;
    history.push({
      generation,
      elapsedMs:performance.now()-started,
      best:generationBest,
      taskCounts:result.taskCounts,
      traces:result.results.map(({taskId,workerId,startedAtMs,finishedAtMs,computeMs,score,eligible})=>({taskId,workerId,startedAtMs,finishedAtMs,computeMs,score,eligible})),
    });
    if(generation+1<generations) population=nextTrafficPopulation(population,result.results,rng);
  }
  const validation=validationSummary(best.details.bestSignal,best.pattern);
  return {
    kind:'outer-traffic-search',algorithm:'genetic',runId,version:1,seed,populationSize,generations,
    trainingSeeds:PATTERN_TRAINING_SEEDS,validationSeeds:PATTERN_VALIDATION_SEEDS,
    geneticOperators:{selection:'tournament-3',eliteCount:2,crossover:'uniform',mutation:'bounded step'},
    elapsedMs:performance.now()-started,best,validation,history,
  };
}

function option(name,fallback) {
  const index=process.argv.indexOf(name);
  if(index<0)return fallback;
  if(!process.argv[index+1])throw Error(`${name}の値が必要です`);
  return process.argv[index+1];
}

if(process.argv[1]&&process.argv[1].endsWith('outer-search.mjs')) {
  const workers=option('--workers','').split(',').map(value=>value.trim()).filter(Boolean);
  if(!workers.length)throw Error('--workersへ1台以上を指定してください');
  const startedAt=new Date().toISOString();
  const result=await runOuterSearch({
    workers,
    populationSize:Number(option('--population','12')),
    generations:Number(option('--generations','5')),
    seed:Number(option('--seed','6026')),
    timeoutMs:Number(option('--timeout-ms','60000')),
    maxRetries:Number(option('--retries','1')),
    onProgress:({generation,done,total,workerId})=>console.error(`generation=${generation+1} progress=${done}/${total} worker=${workerId}`),
  });
  console.log(JSON.stringify({startedAt,finishedAt:new Date().toISOString(),coordinator:os.hostname(),node:process.version,...result},null,2));
}
