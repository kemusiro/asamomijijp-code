// 同じ物理条件で旧一様分布とseed別初期タイプを比較する。時間の速度比は測らない。
import fs from 'node:fs/promises';
import {createPool} from './pool.mjs';
import {initialPopulation,nextPopulation,initialProfileForSeed,evolutionSeedForTrial} from './evolution.mjs';
import {random,VERSION} from './physics.mjs';
const args=process.argv.slice(2),allowed=new Set(['--output','--workers','--runs','--generations']);const options={};
for(let i=0;i<args.length;i+=2){if(!allowed.has(args[i])||!args[i+1])throw Error('引数を確認してください: '+args[i]);options[args[i]]=args[i+1];}
if(!options['--output'])throw Error('--outputに新しいJSON保存先を指定してください');
const integer=(key,value,max)=>{const n=Number(options[key]??value);if(!Number.isInteger(n)||n<1||n>max)throw Error(key+'の範囲を確認してください');return n;};
const runs=integer('--runs',8,8),generations=integer('--generations',20,1000),workers=integer('--workers',4,12);
const file=await fs.open(options['--output'],'wx');await file.close();
let pool;
const data={date:new Date().toISOString(),platform:process.platform,arch:process.arch,node:process.version,modelVersion:VERSION,courseSeed:2026,populationSize:36,generations,workers,startPopulationSeed:2026,runs,results:[]};
try {
  pool=await createPool({workers});
  for(const strategy of ['diverse-v1','profile-v2'])for(let seed=2026;seed<2026+runs;seed++) {
    let population=initialPopulation(seed,36,{strategy}),champion=null,stagnation=0;const history=[],rng=random(evolutionSeedForTrial(2026,seed,strategy));
    for(let generation=0;generation<generations;generation++) {
      const rows=await pool.evaluate(population,2026,strategy+':'+seed+':'+generation),index=rows.reduce((best,r,i)=>r.score>rows[best].score?i:best,0),best=rows[index];
      if(!champion||best.score>champion.score){champion={...best,genome:population[index],generation};stagnation=0;}else stagnation++;
      history.push({generation,distance:champion.distance});population=nextPopulation(population,rows,rng,{strategy,stagnation});
    }
    const result={strategy,populationSeed:seed,evolutionSeed:evolutionSeedForTrial(2026,seed,strategy),initialProfile:initialProfileForSeed(seed,strategy),initialDistance:history[0].distance,champion,history};data.results.push(result);
    await fs.writeFile(options['--output'],JSON.stringify(data,null,2)+'\n');console.log(JSON.stringify({strategy,seed,distance:champion.distance}));
  }
  data.statistics=Object.fromEntries(['diverse-v1','profile-v2'].map(strategy=>{const a=data.results.filter(r=>r.strategy===strategy).map(r=>r.champion.distance),mean=a.reduce((x,y)=>x+y,0)/a.length;return [strategy,{minimum:Math.min(...a),maximum:Math.max(...a),range:Math.max(...a)-Math.min(...a),mean,populationStdDev:Math.sqrt(a.reduce((x,y)=>x+(y-mean)**2,0)/a.length)}];}));
}catch(error){data.error=error.message;throw error;}finally{await fs.writeFile(options['--output'],JSON.stringify(data,null,2)+'\n');await pool?.close();}
