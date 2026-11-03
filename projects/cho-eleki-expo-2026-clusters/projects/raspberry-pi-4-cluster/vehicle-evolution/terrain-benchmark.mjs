// 同じ初期集団・進化乱数で2コースの20世代探索を比較する。表示成績を加工しない。
import fs from 'node:fs/promises';
import {createPool} from './pool.mjs';
import {initialPopulation,nextPopulation,evolutionSeedForTrial,initialProfileForSeed} from './evolution.mjs';
import {random,VERSION} from './physics.mjs';
const args=process.argv.slice(2),allowed=new Set(['--output','--workers','--runs']);const options={};
for(let i=0;i<args.length;i+=2){if(!allowed.has(args[i])||!args[i+1])throw Error('引数を確認してください: '+args[i]);options[args[i]]=args[i+1];}
if(!options['--output'])throw Error('--outputに新しい保存先を指定してください');
const runs=Number(options['--runs']??6),workers=Number(options['--workers']??4);
if(!Number.isInteger(runs)||runs<1||runs>8||!Number.isInteger(workers)||workers<1||workers>12)throw Error('runsは1～8、workersは1～12です');
const f=await fs.open(options['--output'],'wx');await f.close();let pool;
const data={date:new Date().toISOString(),platform:process.platform,arch:process.arch,node:process.version,modelVersion:VERSION,courseSeed:2026,populationSize:36,generations:20,strategy:'profile-v2',startPopulationSeed:2026,runs,workers,results:[]};
try {
  pool=await createPool({workers});
  for(const courseProfile of ['rolling-v1','obstacles-v1'])for(let seed=2026;seed<2026+runs;seed++) {
    let population=initialPopulation(seed,36,{strategy:data.strategy}),champion=null,stagnation=0;const history=[],rng=random(evolutionSeedForTrial(2026,seed,data.strategy));let initialCounts;
    for(let generation=0;generation<20;generation++) {
      const rows=await pool.evaluate(population,2026,courseProfile+':'+seed+':'+generation,()=>{},{courseProfile}),index=rows.reduce((best,r,i)=>r.score>rows[best].score?i:best,0),best=rows[index];
      if(generation===0)initialCounts={beforeHill:rows.filter(r=>r.distance<30).length,beforeValleyExit:rows.filter(r=>r.distance<57).length,beyondValley:rows.filter(r=>r.distance>=57).length};
      if(!champion||best.score>champion.score){champion={...best,genome:population[index],generation};stagnation=0;}else stagnation++;
      history.push({generation,distance:champion.distance,mean:rows.reduce((s,r)=>s+r.distance,0)/rows.length});population=nextPopulation(population,rows,rng,{strategy:data.strategy,stagnation});
    }
    data.results.push({courseProfile,populationSeed:seed,evolutionSeed:evolutionSeedForTrial(2026,seed,data.strategy),initialProfile:initialProfileForSeed(seed,data.strategy),initialCounts,champion,history});
    await fs.writeFile(options['--output'],JSON.stringify(data,null,2)+'\n');console.log(JSON.stringify({courseProfile,seed,distance:champion.distance}));
  }
  data.statistics=Object.fromEntries(['rolling-v1','obstacles-v1'].map(profile=>{const a=data.results.filter(r=>r.courseProfile===profile).map(r=>r.champion.distance),mean=a.reduce((x,y)=>x+y,0)/a.length;return [profile,{minimum:Math.min(...a),maximum:Math.max(...a),range:Math.max(...a)-Math.min(...a),mean,populationStdDev:Math.sqrt(a.reduce((x,y)=>x+(y-mean)**2,0)/a.length)}];}));
}catch(error){data.error=error.message;throw error;}finally{await fs.writeFile(options['--output'],JSON.stringify(data,null,2)+'\n');await pool?.close();}
