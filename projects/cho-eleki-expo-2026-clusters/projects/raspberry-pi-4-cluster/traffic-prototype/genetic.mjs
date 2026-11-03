import {baseline, random, TRAFFIC_PATTERN_BOUNDS, validate, validateTrafficPattern} from './engine.mjs';

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function quantize(value, [minimum, maximum, step]) {
  return Number((minimum + Math.round((clamp(value, minimum, maximum) - minimum) / step) * step).toFixed(6));
}

function pick(rng, values) {
  return values[Math.floor(rng() * values.length)];
}

export function randomTrafficPattern(rng) {
  const pattern={};
  for (const [key,[minimum,maximum,step]] of Object.entries(TRAFFIC_PATTERN_BOUNDS)) {
    const units=Math.round((maximum-minimum)/step);
    pattern[key]=Number((minimum+Math.floor(rng()*(units+1))*step).toFixed(6));
  }
  validateTrafficPattern(pattern);
  return pattern;
}

export function crossoverTrafficPatterns(left, right, rng) {
  const child={};
  for (const key of Object.keys(TRAFFIC_PATTERN_BOUNDS)) child[key]=rng()<0.5?left[key]:right[key];
  validateTrafficPattern(child);
  return child;
}

export function mutateTrafficPattern(pattern, rng, probability=0.35) {
  const child={...pattern};
  let changed=false;
  for (const [key,bounds] of Object.entries(TRAFFIC_PATTERN_BOUNDS)) if (rng()<probability) {
    const direction=rng()<0.5?-1:1;
    const distance=1+Math.floor(rng()*3);
    child[key]=quantize(child[key]+direction*distance*bounds[2],bounds);
    changed=changed||child[key]!==pattern[key];
  }
  if (!changed) {
    const key=pick(rng,Object.keys(TRAFFIC_PATTERN_BOUNDS)), bounds=TRAFFIC_PATTERN_BOUNDS[key];
    child[key]=quantize(child[key]+(rng()<0.5?-1:1)*bounds[2],bounds);
  }
  validateTrafficPattern(child);
  return child;
}

export function initialTrafficPopulation(seed=6026, size=12) {
  if (!Number.isInteger(size)||size<4||size>120) throw Error('交通条件の集団サイズは4から120で指定してください');
  const rng=random(seed), result=[];
  while(result.length<size) result.push(randomTrafficPattern(rng));
  return result;
}

function tournament(scored, rng, size=3) {
  let winner;
  for(let index=0;index<size;index++) {
    const candidate=pick(rng,scored);
    if (!winner||candidate.score<winner.score) winner=candidate;
  }
  return winner.value;
}

export function nextTrafficPopulation(population, results, rng, eliteCount=2) {
  if (population.length!==results.length) throw Error('交通条件と評価結果の件数が一致しません');
  const scored=population.map((value,index)=>({value,score:results[index].eligible&&Number.isFinite(results[index].score)?results[index].score:Infinity,index}))
    .sort((a,b)=>a.score-b.score||a.index-b.index);
  if (!Number.isFinite(scored[0].score)) throw Error('採用可能な交通条件がありません');
  const next=scored.slice(0,eliteCount).map(item=>structuredClone(item.value));
  while(next.length<population.length) {
    const child=crossoverTrafficPatterns(tournament(scored,rng),tournament(scored,rng),rng);
    next.push(mutateTrafficPattern(child,rng));
  }
  return next;
}

export function randomSignal(rng) {
  const config={
    green:Array.from({length:4},()=>10+Math.floor(rng()*27)),
    offset:Array.from({length:4},()=>Math.floor(rng()*60)),
  };
  validate(config);
  return config;
}

export function initialSignalPopulation(seed=7026, size=12) {
  if (!Number.isInteger(size)||size<4||size>120) throw Error('信号候補の集団サイズは4から120で指定してください');
  const rng=random(seed), result=[structuredClone(baseline)];
  while(result.length<size) result.push(randomSignal(rng));
  return result;
}

export function crossoverSignals(left, right, rng) {
  const child={green:[],offset:[]};
  for(let index=0;index<4;index++) {
    child.green.push(rng()<0.5?left.green[index]:right.green[index]);
    child.offset.push(rng()<0.5?left.offset[index]:right.offset[index]);
  }
  validate(child);
  return child;
}

export function mutateSignal(config, rng, probability=0.25) {
  const child=structuredClone(config);
  let changed=false;
  for(let index=0;index<4;index++) {
    if(rng()<probability) {
      child.green[index]=clamp(child.green[index]+(rng()<0.5?-1:1)*(1+Math.floor(rng()*4)),10,36);
      changed=true;
    }
    if(rng()<probability) {
      child.offset[index]=(child.offset[index]+(rng()<0.5?-1:1)*(1+Math.floor(rng()*7))+60)%60;
      changed=true;
    }
  }
  if(!changed) {
    const index=Math.floor(rng()*4);
    child.offset[index]=(child.offset[index]+1)%60;
  }
  validate(child);
  return child;
}

export function nextSignalPopulation(population, results, rng, eliteCount=2) {
  if(population.length!==results.length) throw Error('信号候補と評価結果の件数が一致しません');
  const scored=population.map((value,index)=>({value,score:results[index].eligible&&Number.isFinite(results[index].score)?results[index].score:Infinity,index}))
    .sort((a,b)=>a.score-b.score||a.index-b.index);
  if(!Number.isFinite(scored[0].score)) throw Error('採用可能な信号候補がありません');
  const next=scored.slice(0,eliteCount).map(item=>structuredClone(item.value));
  while(next.length<population.length) next.push(mutateSignal(crossoverSignals(tournament(scored,rng),tournament(scored,rng),rng),rng));
  return next;
}

export function evolutionRandom(seed) {
  return random(seed);
}
