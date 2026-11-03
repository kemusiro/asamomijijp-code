// 本番physicsを変更せず、一時コピーの障害点列・走行時間を指定して難易度を比較する。
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {random,VERSION,DURATION} from './physics.mjs';
import {initialPopulation,nextPopulation,evolutionSeedForTrial,initialProfileForSeed} from './evolution.mjs';

export const TARGET_DISTANCE=57,TUNING_VERSION='terrain-tuning-v1';
export function validateDuration(durationSeconds) {
  if(![16,30].includes(durationSeconds))throw Error('--duration-secondsで16または30を明示してください');
  return durationSeconds;
}
export const hash=value=>createHash('sha256').update(typeof value==='string'?value:JSON.stringify(value)).digest('hex');
export function obstaclePoints(angle,depth) {
  if(!Number.isFinite(angle)||angle<45||angle>60||!Number.isFinite(depth)||depth<6||depth>12)throw Error('台地角度は45〜60度、谷深さは6〜12mで指定してください');
  const rise=angle===45?1:Math.tan(angle*Math.PI/180);
  return [[21,-.5],[24,0],[27,3*rise],[30,4.5*rise],[33,4.5*rise],[36,1.5*rise],[39,0],
    [42,0],[45,-depth/2],[48,-depth],[51,-depth],[54,-depth/2],[57,0],[60,0]];
}
export async function writeVariant(directory,condition,{durationSeconds}={}) {
  validateDuration(durationSeconds);
  const original=await fs.readFile(new URL('./physics.mjs',import.meta.url),'utf8');
  const expression=/const heights=new Map\(\[.*?\]\);/g;
  if([...original.matchAll(expression)].length!==1)throw Error('physicsの障害点列を特定できません。元のソースを確認してください');
  if(!original.includes("from './vendor/planck.mjs'"))throw Error('物理エンジンのimportを特定できません');
  const durationExpression=/\bDURATION=\d+(?:\.\d+)?/g,versionExpression=/export const VERSION='[^']+';/g;
  if([...original.matchAll(durationExpression)].length!==1||[...original.matchAll(versionExpression)].length!==1)throw Error('physicsの時間・版を特定できません。元のソースを確認してください');
  const points=obstaclePoints(condition.angle,condition.depth);
  const source=original.replace(expression,'const heights=new Map('+JSON.stringify(points)+');')
    .replace(durationExpression,'DURATION='+durationSeconds).replace(versionExpression,"export const VERSION='"+TUNING_VERSION+"';")
    .replace("from './vendor/planck.mjs'","from "+JSON.stringify(new URL('./vendor/planck.mjs',import.meta.url).href));
  if(source.includes("from './vendor/planck.mjs'"))throw Error('物理エンジンの参照を書き換えられません');
  const destination=path.join(directory,condition.id+'.mjs');
  await fs.writeFile(destination,source,{flag:'wx'});
  return {path:destination,modelVersion:TUNING_VERSION,sourceModelVersion:VERSION,sourceDurationSeconds:DURATION,durationSeconds,originalSha256:hash(original),variantSha256:hash(source),points,valleyAngle:Math.atan(condition.depth/6)*180/Math.PI};
}
export function describe(rows) {
  const counts={time:0,finish:0,stalled:0,fell:0,unstable:0};
  for(const row of rows){if(!(row.reason in counts))throw Error('未知の終了理由: '+row.reason);counts[row.reason]++;}
  const distances=rows.map(r=>r.distance),passed=distances.filter(d=>d>=TARGET_DISTANCE).length;
  return {count:rows.length,passed,passRate:passed/rows.length,meanDistance:distances.reduce((a,b)=>a+b,0)/rows.length,
    minDistance:Math.min(...distances),maxDistance:Math.max(...distances),reasons:counts,
    beforeHill:distances.filter(d=>d<39).length,inValley:distances.filter(d=>d>=39&&d<TARGET_DISTANCE).length};
}
export function evaluateTrial(physics,{seed,courseSeed=2026,generations=20,populationSize=36}) {
  const strategy='profile-v2',rng=random(evolutionSeedForTrial(courseSeed,seed,strategy));
  let population=initialPopulation(seed,populationSize,{strategy}),champion=null,stagnation=0;
  const history=[];let initial,final,finalPopulation;
  for(let generation=0;generation<generations;generation++) {
    const rows=[];
    for(let candidate=0;candidate<population.length;candidate++) {
      try {rows.push(physics.simulate(population[candidate],{seed:courseSeed,courseProfile:'obstacles-v1'}));}
      catch(error){return {status:'error',durationSeconds:physics.DURATION,modelVersion:physics.VERSION,seed,initialProfile:initialProfileForSeed(seed,strategy),error:error.message,generation,candidate,history};}
    }
    const summary=describe(rows),bestIndex=rows.reduce((index,row,i)=>row.score>rows[index].score?i:index,0),best=rows[bestIndex];
    if(!champion||best.score>champion.score){champion={...best,genome:[...population[bestIndex]],generation};stagnation=0;}else stagnation++;
    if(generation===0)initial=summary;
    final=summary;finalPopulation={genomes:population.map(g=>[...g]),results:rows};
    history.push({generation,passed:summary.passed,meanDistance:summary.meanDistance,bestDistance:champion.distance});
    population=nextPopulation(population,rows,rng,{strategy,stagnation});
  }
  return {status:'complete',durationSeconds:physics.DURATION,modelVersion:physics.VERSION,seed,initialProfile:initialProfileForSeed(seed,strategy),initial,final,champion,history,
    finalPopulationSha256:hash(finalPopulation),finalDistances:finalPopulation.results.map(r=>r.distance),finalReasons:finalPopulation.results.map(r=>r.reason),finalElapsedSeconds:finalPopulation.results.map(r=>r.elapsed)};
}
export function summarize(trials) {
  const complete=trials.filter(t=>t.status==='complete').sort((a,b)=>a.seed-b.seed),failed=trials.length-complete.length;
  const count=complete.reduce((n,t)=>n+t.final.count,0),passed=complete.reduce((n,t)=>n+t.final.passed,0);
  return {completedTrials:complete.length,failedTrials:failed,count,passed,passRate:count?passed/count:null,
    perSeed:complete.map(t=>({seed:t.seed,passed:t.final.passed,count:t.final.count,passRate:t.final.passRate})),
    reasons:Object.fromEntries(['time','finish','stalled','fell','unstable'].map(reason=>[reason,complete.reduce((n,t)=>n+t.final.reasons[reason],0)]))};
}
