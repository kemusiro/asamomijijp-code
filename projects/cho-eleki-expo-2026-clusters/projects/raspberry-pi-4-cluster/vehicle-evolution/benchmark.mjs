import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createPool} from './pool.mjs';
import {initialPopulation,nextPopulation} from './evolution.mjs';
import {random} from './physics.mjs';

export async function runBudget(pool,{budgetMs=5000,seed=2026,courseSeed=seed,populationSeed=seed,populationSize=36}={}) {
  if(!Number.isInteger(budgetMs)||budgetMs<100||budgetMs>300000)throw Error('budget-msは100～300000です');
  let population=initialPopulation(populationSeed,populationSize);const rng=random(courseSeed+1),runId=randomUUID();
  // 全評価スロットを同じ車体でウォームアップ。起動・health取得は探索予算に含めない。
  await pool.evaluate(Array.from({length:pool.ids.length},()=>population[0]),courseSeed,runId+':warmup');
  const started=performance.now(),deadlineAt=started+budgetMs,events=[];let best=null,generation=0,completedGenerations=0;
  while(performance.now()<deadlineAt) {
    const completed=new Map();
    const results=await pool.evaluate(population,courseSeed,runId+':'+generation,event=>{
      if(event.status!=='done')return;
      const finishedAtMs=performance.now()-started,withinBudget=finishedAtMs<=budgetMs;
      events.push({generation,candidateId:event.id,workerId:event.workerId,distance:event.distance,finishedAtMs,withinBudget});
      completed.set(event.id,withinBudget);
    },{deadlineAt});
    for(let i=0;i<results.length;i++) {
      if(completed.get(i)&&results[i]&&(!best||results[i].score>best.score))best={...results[i],genome:population[i],generation};
    }
    if(results.filter(Boolean).length<population.length||[...completed.values()].some(v=>!v))break;
    completedGenerations++;population=nextPopulation(population,results,rng);generation++;
  }
  if(!best)throw Error('時間内に評価を完了できませんでした。予算またはtimeoutを増やしてください');
  return {workers:pool.ids,evaluatedCount:events.filter(e=>e.withinBudget).length,completedGenerations,best,events,elapsedMs:performance.now()-started,drainMs:Math.max(0,performance.now()-deadlineAt)};
}
export async function compareBudgets({workers=4,urls=[],timeoutMs=15000,...options}={}) {
  if(!urls.length&&workers<2||urls.length===1)throw Error('比較には2並列以上が必要です');
  const singlePool=await createPool({workers:1,urls:urls.slice(0,1),timeoutMs});let multiPool;
  try {
    const single=await runBudget(singlePool,options);await singlePool.close();
    multiPool=await createPool({workers,urls,timeoutMs});const multi=await runBudget(multiPool,options);
    return {version:1,mode:urls.length?'remote':'local',seed:options.courseSeed??options.seed??2026,courseSeed:options.courseSeed??options.seed??2026,populationSeed:options.populationSeed??options.seed??2026,evolutionSeed:(options.courseSeed??options.seed??2026)+1,populationSize:options.populationSize??36,budgetMs:options.budgetMs??5000,
      fairness:'同じ初期集団・seed・コース。各構成をウォームアップ後、順番に評価。期限内の完了候補だけ集計。',single,multi,candidateMultiplier:multi.evaluatedCount/single.evaluatedCount};
  }finally{await singlePool.close();await multiPool?.close();}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const allowed=new Set(['--budget-ms','--workers','--worker-urls','--seed','--course-seed','--population-seed','--population','--timeout-ms','--output']),v={};
  for(let i=2;i<process.argv.length;i+=2){if(!allowed.has(process.argv[i])||!process.argv[i+1])throw Error('引数を確認してください: '+process.argv[i]);v[process.argv[i]]=process.argv[i+1];}
  const output=v['--output']??path.join(path.dirname(fileURLToPath(import.meta.url)),'output','benchmark.json');
  try {
    if(v['--workers']&&v['--worker-urls'])throw Error('--workersと--worker-urlsは同時指定できません');
    if(v['--seed']&&(v['--course-seed']||v['--population-seed']))throw Error('--seedと分離したseedは同時指定できません');
    const report=await compareBudgets({budgetMs:Number(v['--budget-ms']??5000),workers:Number(v['--workers']??4),urls:(v['--worker-urls']??'').split(',').filter(Boolean),seed:Number(v['--seed']??2026),courseSeed:Number(v['--course-seed']??v['--seed']??2026),populationSeed:Number(v['--population-seed']??v['--seed']??2026),populationSize:Number(v['--population']??36),timeoutMs:Number(v['--timeout-ms']??15000)});
    await fs.mkdir(path.dirname(output),{recursive:true});await fs.writeFile(output+'.tmp',JSON.stringify(report,null,2));await fs.rename(output+'.tmp',output);
    console.log(JSON.stringify({mode:report.mode,budgetMs:report.budgetMs,singleCandidates:report.single.evaluatedCount,multiCandidates:report.multi.evaluatedCount,candidateMultiplier:report.candidateMultiplier,singleDistance:report.single.best.distance,multiDistance:report.multi.best.distance,output},null,2));
  }catch(error){console.error('比較を完了できません: '+error.message);process.exitCode=1;}
}
