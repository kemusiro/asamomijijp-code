import {BOUNDS,clamp,random,validateGenome,validateSeed} from './physics.mjs';

export const STRATEGIES=['legacy','diverse-v1','profile-v2'];
const PROFILES=[
  {id:'compact',label:'小型・大径輪',center:[.15,.15,.15,.15,.15,.15,.15,.15,.9,.9,.4,.5,.4]},
  {id:'bulky',label:'大型・小径輪',center:[.8,.8,.8,.8,.8,.8,.8,.8,.15,.15,.8,.5,.4]},
  {id:'rear-wheel',label:'後輪大径',center:[.25,.4,.65,.8,.8,.5,.25,.2,.85,.15,.6,.5,.5]},
  {id:'front-wheel',label:'前輪大径',center:[.8,.8,.65,.4,.25,.2,.25,.5,.15,.85,.6,.5,.5]},
  {id:'wide',label:'横長・広い軸間',center:[.85,.15,.15,.15,.85,.15,.15,.15,.5,.5,.95,.5,.4]},
  {id:'uneven',label:'凹凸・短い軸間',center:[.3,.9,.2,.7,.35,.8,.2,.65,.4,.7,.2,.5,.6]},
];
export function initialProfileForSeed(seed,strategy) {
  validateSeed(seed);const profile=PROFILES[seed%PROFILES.length];
  return strategy==='profile-v2'?{id:profile.id,label:profile.label}:null;
}
export function evolutionSeedForTrial(courseSeed,populationSeed,strategy) {
  validateSeed(courseSeed);validateSeed(populationSeed);
  return strategy==='profile-v2'?(populationSeed^0x51ed270b)>>>0:courseSeed+1;
}
export function initialPopulation(seed=2026,size=36,{strategy='legacy'}={}) {
  validateSeed(seed);
  if(!Number.isInteger(size)||size<6||size>120)throw Error('集団サイズは6～120です');
  if(!STRATEGIES.includes(strategy))throw Error('探索方式が不正です');
  const rng=random(seed);
  if(strategy==='profile-v2') {
    // Only the starting distribution is biased. All later generations retain
    // the shared full bounds, including global immigrants and large mutations.
    const center=PROFILES[seed%PROFILES.length].center.map(n=>clamp(n+(rng()-.5)*.22,0,1));
    return Array.from({length:size},()=>BOUNDS.map(([lo,hi],i)=>lo+clamp(center[i]+(rng()+rng()-1)*.22,0,1)*(hi-lo)));
  }
  return Array.from({length:size},()=>BOUNDS.map(([lo,hi])=>lo+rng()*(hi-lo)));
}
export function mutationPlan(size,stagnation=0,strategy='diverse-v1') {
  if(!STRATEGIES.includes(strategy))throw Error('探索方式が不正です');
  const available=size-2,burst=stagnation>=10&&strategy!=='legacy';
  const fresh=strategy==='legacy'?0:Math.max(1,Math.round(available*(burst?8:4)/34));
  const large=strategy==='legacy'?0:Math.max(1,Math.round(available*(burst?16:10)/34));
  return {elite:2,normal:available-fresh-large,large,fresh,burst};
}
function mutate(child,rng) {
  let mutated=false;
  for(let i=0;i<child.length;i++)if(rng()<.22){const [lo,hi]=BOUNDS[i];child[i]=clamp(child[i]+(rng()+rng()-1)*(hi-lo)*.3,lo,hi);mutated=true;}
  if(!mutated){const i=Math.floor(rng()*child.length),[lo,hi]=BOUNDS[i];child[i]=clamp(child[i]+(rng()-.5)*(hi-lo)*.3,lo,hi);}
  return child;
}
export function nextPopulation(population,results,rng,{strategy='legacy',stagnation=0}={}) {
  if(population.length!==results.length||results.some(r=>!Number.isFinite(r.score)))throw Error('世代の評価結果が不正です');
  const ranked=population.map((genome,i)=>({genome,score:results[i].score,index:i})).sort((a,b)=>b.score-a.score||a.index-b.index);
  const pick=()=>{let best;for(let i=0;i<3;i++){const v=ranked[Math.floor(rng()*ranked.length)];if(!best||v.score>best.score)best=v;}return best.genome;};
  const plan=mutationPlan(population.length,stagnation,strategy),next=ranked.slice(0,2).map(r=>[...r.genome]);
  while(next.length<population.length) {
    if(next.length>=population.length-plan.fresh){next.push(BOUNDS.map(([lo,hi])=>lo+rng()*(hi-lo)));continue;}
    const a=pick(),b=pick(),child=a.map((v,i)=>rng()<.5?v:b[i]);
    if(next.length<2+plan.normal)mutate(child,rng);
    else {
      // Re-sample 1–3 distinct genes across their entire allowed range.
      const count=1+Math.floor(rng()*3),indices=Array.from({length:child.length},(_,i)=>i);
      for(let i=0;i<count;i++){const j=i+Math.floor(rng()*(indices.length-i));[indices[i],indices[j]]=[indices[j],indices[i]];const k=indices[i],[lo,hi]=BOUNDS[k];child[k]=lo+rng()*(hi-lo);}
    }
    validateGenome(child);next.push(child);
  }
  return next;
}
