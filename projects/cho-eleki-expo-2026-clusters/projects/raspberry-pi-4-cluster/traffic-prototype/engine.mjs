// 描画・通信に依存しない、固定刻みの直進交通モデル。
export const VERSION = '0.5.0';
export const DT = 0.25, DURATION = 180, WARMUP = 60, CYCLE = 60;
export const CANDIDATE_COUNT = 120;
const SPEED = 18, GAP = 15, LENGTH = 1000;
export const baseline = {green: [23,23,23,23], offset: [0,0,0,0]};
export function random(seed) {
  let s = seed >>> 0;
  return () => {s = (Math.imul(s,1664525)+1013904223) >>> 0; return s/4294967296;};
}
export function validate(config) {
  for (const key of ['green','offset']) if (!Array.isArray(config[key]) || config[key].length !== 4) throw Error('信号設定は4交差点分が必要です');
  if (config.green.some(x => !Number.isFinite(x) || x < 10 || x > 36) || config.offset.some(x => !Number.isFinite(x) || x < 0 || x >= 60)) throw Error('信号設定が範囲外です');
}
// 各方向：青、黄3秒、全赤4秒。黄では新規進入しない。
export function phase(config, intersection, t) {
  const p = ((t + config.offset[intersection]) % CYCLE + CYCLE) % CYCLE;
  const g = config.green[intersection];
  if (p < g) return ['green','red'];
  if (p < g+3) return ['yellow','red'];
  if (p < g+7) return ['red','red'];
  if (p < 53) return ['red','green'];
  if (p < 56) return ['red','yellow'];
  return ['red','red'];
}
export function demand(scenario, seed, duration=DURATION+WARMUP) {
  if (!['balanced','eastwest'].includes(scenario)) throw Error('未知の交通条件です');
  const rng = random(seed), events = [];
  for (let step=0; step<duration/DT; step++) for(let lane=0;lane<8;lane++) {
    const rate = scenario === 'balanced' ? 0.13 : lane<4 ? 0.23 : 0.07;
    if (rng() < rate*DT) events.push({t:step*DT,lane});
  }
  return events;
}

export const TRAFFIC_PATTERN_BOUNDS = Object.freeze({
  platoonSize: [3, 8, 1],
  period: [48, 72, 1],
  spacing: [0.5, 1.75, 0.25],
  jitter: [0, 1.5, 0.25],
  phase: [0, 24, 1],
  reverseRate: [0.005, 0.035, 0.005],
  crossRate: [0.02, 0.08, 0.005],
});

function onStep(value, [minimum, maximum, step]) {
  const units = Math.round((value - minimum) / step);
  return Number.isFinite(value) && value >= minimum && value <= maximum && Math.abs(minimum + units * step - value) < 1e-9;
}

export function validateTrafficPattern(pattern) {
  if (!pattern || typeof pattern !== 'object') throw Error('交通条件がJSONオブジェクトではありません');
  for (const [key, bounds] of Object.entries(TRAFFIC_PATTERN_BOUNDS)) {
    if (!onStep(pattern[key], bounds)) throw Error(`交通条件${key}が範囲外または刻み外です`);
  }
  if(pattern.platoonAxis!==undefined&&!['eastwest','northsouth'].includes(pattern.platoonAxis))throw Error('交通条件platoonAxisが不正です');
  if(pattern.slowRate!==undefined&&(!Number.isFinite(pattern.slowRate)||pattern.slowRate<0||pattern.slowRate>0.5))throw Error('交通条件slowRateが範囲外です');
  if(pattern.slowSpeed!==undefined&&(!Number.isFinite(pattern.slowSpeed)||pattern.slowSpeed<8||pattern.slowSpeed>=SPEED))throw Error('交通条件slowSpeedが範囲外です');
  if((pattern.slowRate??0)>0&&pattern.slowSpeed===undefined)throw Error('低速車を含む交通条件にはslowSpeedが必要です');
}

// 指定軸の順方向2車線へ周期的な車群を流し、逆方向と交差方向には確率的な背景交通を残す。
// 外側探索で「交通がほぼない」条件へ逃げないよう、背景交通率には正の下限を置く。
export function patternDemand(pattern, seed, duration=DURATION+WARMUP) {
  validateTrafficPattern(pattern);
  const rng = random(seed), events = [];
  const primary=pattern.platoonAxis==='northsouth'?[4,6]:[0,2];
  const reverse=pattern.platoonAxis==='northsouth'?[5,7]:[1,3];
  const cross=pattern.platoonAxis==='northsouth'?[0,1,2,3]:[4,5,6,7];
  for (let start=pattern.phase; start<duration; start+=pattern.period) {
    for (const lane of primary) for (let index=0; index<pattern.platoonSize; index++) {
      const t = start + index * pattern.spacing + (rng() * 2 - 1) * pattern.jitter;
      if (t >= 0 && t < duration) events.push({t: Math.round(t / DT) * DT, lane});
    }
  }
  for (let step=0; step<duration/DT; step++) {
    const t = step * DT;
    for (const lane of reverse) if (rng() < pattern.reverseRate * DT) events.push({t,lane});
    for (const lane of cross) if (rng() < pattern.crossRate * DT) events.push({t,lane});
  }
  events.sort((a,b) => a.t-b.t || a.lane-b.lane);
  if((pattern.slowRate??0)<=0)return events;
  const speedRng=random((seed^0x9e3779b9)>>>0);
  return events.map(event=>({...event,speed:speedRng()<pattern.slowRate?pattern.slowSpeed:SPEED}));
}

export function demandFor(source, seed, duration=DURATION+WARMUP) {
  return typeof source === 'string' ? demand(source, seed, duration) : patternDemand(source, seed, duration);
}
function crossings(lane) {
  const axis = lane<4 ? 0 : 1, line = Math.floor((lane%4)/2), reverse = lane%2;
  let ids = axis===0 ? [line*2,line*2+1] : [line,line+2];
  if(reverse) ids.reverse();
  return [{at:330,id:ids[0]},{at:670,id:ids[1]}];
}
// 出口に停止可能な空間を予約する。交差点は中心±28の領域とする。
export function canEnter(state, leaderX, center, perpendicularOccupied) {
  return state === 'green' && leaderX >= center+28+GAP && !perpendicularOccupied;
}
export function simulate(config, events, {duration=DURATION, warmup=WARMUP, frames=false, check=false}={}) {
  validate(config);
  if (!Number.isFinite(duration) || !Number.isFinite(warmup) || duration<=0 || warmup<0 || duration%DT || warmup%DT) throw Error('時間は0.25秒刻みで指定してください');
  let prev=-1;
  for(const e of events) {
    if(!Number.isFinite(e.t)||e.t<prev||e.t<0||!Number.isInteger(e.lane)||e.lane<0||e.lane>7||
      (e.speed!==undefined&&(!Number.isFinite(e.speed)||e.speed<8||e.speed>SPEED)))throw Error('交通イベントの時刻順、車線または速度が不正です');
    prev=e.t;
  }
  const lanes=Array.from({length:8},()=>[]),pending=Array.from({length:8},()=>[]);
  let cursor=0, blockedEntries=0;
  let stats=Array.from({length:2},()=>({generated:0,arrived:0,wait:0}));
  const snapshots=[];
  const metrics=()=>{
    const direction=stats.map(s=>({...s,remaining:s.generated-s.arrived,meanWait:s.generated?s.wait/s.generated:0}));
    const generated=stats[0].generated+stats[1].generated,arrived=stats[0].arrived+stats[1].arrived,wait=stats[0].wait+stats[1].wait;
    return {generated,arrived,remaining:generated-arrived,wait,meanWait:generated?wait/generated:0,direction};
  };
  for(let step=0;step<(duration+warmup)/DT;step++) {
    const t=step*DT, measuring=t>=warmup, activeConfig=measuring?config:baseline;
    // 共通の基準設定で暖機し、残存車と入口待ちを含む同じ状態から比較する。
    if(t===warmup) stats=[0,1].map(axis=>({generated:lanes.slice(axis*4,axis*4+4).reduce((n,l)=>n+l.length,0)+pending.slice(axis*4,axis*4+4).reduce((n,l)=>n+l.length,0),arrived:0,wait:0}));
    while(cursor<events.length && events[cursor].t<=t) {
      const event=events[cursor];pending[event.lane].push({id:cursor,x:0,speed:event.speed??SPEED});cursor++;
      stats[event.lane<4?0:1].generated++;
    }
    // 直前の占有と、この刻みで進入する車の予約の両方を見る。
    const occupied=Array.from({length:4},()=>[false,false]);
    for(let lane=0;lane<8;lane++) for(const c of lanes[lane]) for(const cross of crossings(lane))
      if(c.x>cross.at-28 && c.x<cross.at+28) occupied[cross.id][lane<4?0:1]=true;
    for(let lane=0;lane<8;lane++) {
      const axis=lane<4?0:1,cars=lanes[lane],queue=pending[lane];
      if(queue.length&&(!cars.length||cars[cars.length-1].x>=GAP)) cars.push(queue.shift());
      if(measuring)stats[axis].wait+=queue.length*DT;
      for(let i=0;i<cars.length;i++) {
        const c=cars[i],old=c.x,leader=i?cars[i-1].x:Infinity;
        let next=Math.min(old+c.speed*DT,leader-GAP);
        for(const cross of crossings(lane)) {
          const stop=cross.at-28;
          if(old<=stop&&next>stop) {
            // 交差点内の先行車が退出する分も含め、下流の待機空間を予約する。
            const ahead=cars.slice(0,i);
            const inside=ahead.filter(v=>v.x>stop&&v.x<cross.at+28).length;
            const downstream=ahead.filter(v=>v.x>=cross.at+28).at(-1)?.x??Infinity;
            const reservedSpace=downstream-inside*GAP;
            if(!canEnter(phase(activeConfig,cross.id,t)[axis],reservedSpace,cross.at,occupied[cross.id][1-axis])) {
              next=Math.min(next,stop);if(measuring)blockedEntries++;
            } else occupied[cross.id][axis]=true;
          }
        }
        c.x=Math.max(old,next);
        if(measuring&&c.x-old<0.1*DT)stats[axis].wait+=DT;
        if(check&&i&&cars[i-1].x-c.x<GAP-1e-8)throw Error('車間距離違反');
        if(check)for(const cross of crossings(lane))if(old>cross.at-28&&old<cross.at+28&&c.x-old<0.1*DT)throw Error('交差点内停止');
      }
      while(cars.length&&cars[0].x>=LENGTH){cars.shift();stats[axis].arrived++;}
    }
    if(check) {
      const axes=Array.from({length:4},()=>new Set());
      for(let lane=0;lane<8;lane++)for(const c of lanes[lane])for(const cross of crossings(lane))
        if(c.x>cross.at-28&&c.x<cross.at+28)axes[cross.id].add(lane<4?0:1);
      if(axes.some(a=>a.size>1))throw Error('交差方向の占有競合');
      if(metrics().remaining!==lanes.reduce((n,l)=>n+l.length,0)+pending.reduce((n,l)=>n+l.length,0))throw Error('車両数の保存違反');
    }
    if(frames&&measuring)snapshots.push({t:t+DT-warmup,signalTime:t+DT,cars:lanes.flatMap((list,lane)=>list.map(c=>[lane,c.x,c.id,c.speed])),queued:pending.map(q=>q.length),...metrics()});
  }
  return {...metrics(),blockedEntries,frames:snapshots};
}
export function candidates(seed=2026, count=CANDIDATE_COUNT) {
  if (!Number.isInteger(count) || count < 1 || count > 10000) throw Error('候補数は1から10000の整数で指定してください');
  const result=[], seen=new Set(), rng=random(seed);
  const add=config=>{
    if(result.length>=count)return;
    const key=JSON.stringify(config);
    if(!seen.has(key)){seen.add(key);result.push(config);}
  };
  add(baseline);
  for(const green of [14,23,32,36]) for(const offset of [[0,0,0,0],[0,19,19,38],[0,41,41,22]]) add({green:Array(4).fill(green),offset});
  for(let i=0;i<24;i++)add({green:Array.from({length:4},()=>10+Math.floor(rng()*27)),offset:Array.from({length:4},()=>Math.floor(rng()*60))});
  // 探索範囲の境界も含める。極端な青時間が混雑方向へ与える影響を異なる時差で評価する。
  while(result.length<count){
    const green=result.length%2?10:36;
    add({green:Array(4).fill(green),offset:Array.from({length:4},()=>Math.floor(rng()*60))});
  }
  return result;
}
export const TRAINING_SEEDS=[101,202,404];
export const VALIDATION_SEEDS=[303,505,606,707,808];
// 探索シードすべてで到着数を落とさず、各方向の平均待ちの悪化を抑える。
// 許容値は試作の設計値。交通工学上の基準ではない。
export function acceptable(result, reference) {
  return result.arrived>=reference.arrived && result.direction.every((d,i)=>
    d.meanWait<=reference.direction[i].meanWait+Math.max(2,reference.direction[i].meanWait*0.2));
}
export function assess(config, scenario, seeds=TRAINING_SEEDS) {
  const pairs=seeds.map(seed=>{
    const events=demandFor(scenario,seed);
    return {seed,base:simulate(baseline,events),candidate:simulate(config,events)};
  });
  return {eligible:pairs.every(p=>acceptable(p.candidate,p.base)),
    score:pairs.reduce((n,p)=>n+p.candidate.meanWait,0)/pairs.length,pairs};
}
export function evaluate(config, scenario, seeds=TRAINING_SEEDS) {
  const a=assess(config,scenario,seeds);return a.eligible?a.score:Infinity;
}

export const PATTERN_TRAINING_SEEDS=[1101,1202,1404];
export const PATTERN_VALIDATION_SEEDS=[1303,1505,1606,1707,1808];

export function patternProbeSignals() {
  const result=[baseline];
  for (const green of [23,26,28,32,36]) for (const delay of [20,24,26,28,32,38]) {
    result.push({green:Array(4).fill(green),offset:[0,delay,0,delay]});
  }
  return result;
}

function median(values) {
  const sorted=[...values].sort((a,b)=>a-b), middle=Math.floor(sorted.length/2);
  return sorted.length%2 ? sorted[middle] : (sorted[middle-1]+sorted[middle])/2;
}

// 交通条件ごとに同じ信号候補群を評価する。倍率だけを目的にすると分母がほぼ0の
// 条件を選び得るため、最低交通量、両方向の流入、絶対改善量も適合度へ含める。
export function assessTrafficPattern(pattern, seeds=PATTERN_TRAINING_SEEDS) {
  validateTrafficPattern(pattern);
  if (!Array.isArray(seeds) || !seeds.length) throw Error('交通条件の評価seedがありません');
  const eventsBySeed=seeds.map(seed=>({seed,events:patternDemand(pattern,seed)}));
  const bases=eventsBySeed.map(({seed,events})=>({seed,result:simulate(baseline,events)}));
  const ranked=patternProbeSignals().map(config=>{
    const pairs=eventsBySeed.map(({seed,events},index)=>({seed,base:bases[index].result,candidate:simulate(config,events)}));
    const eligible=pairs.every(({base,candidate})=>acceptable(candidate,base));
    const score=pairs.reduce((sum,pair)=>sum+pair.candidate.meanWait,0)/pairs.length;
    return {config,eligible,score,pairs};
  }).filter(item=>item.eligible).sort((a,b)=>a.score-b.score);
  const minimumTraffic=bases.every(({result})=>result.generated>=45 && result.direction.every(direction=>direction.generated>=8));
  const meaningfulBaseline=bases.every(({result})=>result.meanWait>=5);
  const best=ranked[0];
  if (!minimumTraffic || !meaningfulBaseline || !best) {
    return {eligible:false,score:Infinity,fitness:null,minimumTraffic,meaningfulBaseline,best:null,bases};
  }
  const ratios=best.pairs.map(({base,candidate})=>base.meanWait/Math.max(candidate.meanWait,0.5));
  const improvements=best.pairs.map(({base,candidate})=>base.meanWait-candidate.meanWait);
  const robustRatio=Math.min(...ratios);
  const medianImprovement=median(improvements);
  const fitness=robustRatio+Math.max(0,medianImprovement)*0.02;
  return {eligible:true,score:-fitness,fitness,robustRatio,medianImprovement,best,bases};
}
