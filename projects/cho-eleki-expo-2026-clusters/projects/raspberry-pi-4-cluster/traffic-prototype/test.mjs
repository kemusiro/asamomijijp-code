import assert from 'node:assert/strict';
import {baseline,phase,simulate,demand,patternDemand,validateTrafficPattern,candidates,evaluate,assess,acceptable,canEnter,WARMUP,DURATION,VERSION,TRAINING_SEEDS,VALIDATION_SEEDS,CANDIDATE_COUNT} from './engine.mjs';
assert.equal(simulate(baseline,[]).generated,0);
assert.equal(simulate(baseline,[]).meanWait,0);
assert.equal(canEnter('green',370,330,false),false); // 出口+車間は373
assert.equal(canEnter('green',373,330,false),true);
assert.equal(canEnter('green',Infinity,330,true),false);
assert.equal(canEnter('red',Infinity,330,false),false);
for(const config of candidates())for(let i=0;i<4;i++)for(let t=0;t<120;t+=.25){
 const p=phase(config,i,t);assert.ok(!(p[0]==='green'&&p[1]==='green'));
}
const events=demand('eastwest',303);
assert.deepEqual(events,demand('eastwest',303));
const run=simulate(baseline,events,{check:true});
assert.deepEqual(run,simulate(baseline,events,{check:true}));
assert.equal(run.arrived+run.remaining,run.generated);
const dense=Array.from({length:500},(_,i)=>({t:0,lane:i%8}));
const congested=simulate(baseline,dense,{check:true,frames:true});
assert.ok(congested.wait>0);assert.equal(congested.frames.length,720);
assert.ok(congested.blockedEntries>0);
assert.equal(simulate(baseline,[{t:0,lane:0}],{warmup:0,check:true}).arrived,1);
const warm=simulate(baseline,events,{duration:WARMUP,warmup:0});
const measured=simulate(baseline,events,{duration:.25,frames:true});
assert.equal(measured.generated,warm.remaining+events.filter(e=>e.t===WARMUP).length);
assert.equal(measured.frames[0].t,.25);assert.equal(measured.frames[0].signalTime,WARMUP+.25);
assert.ok(measured.wait<=measured.generated*.25); // 暖機中の待ち時間は除外
assert.throws(()=>simulate(baseline,[{t:1,lane:8}]));
assert.throws(()=>simulate(baseline,[{t:1,lane:0},{t:0,lane:0}]));
assert.throws(()=>simulate(baseline,[],{duration:Infinity}));
assert.throws(()=>simulate({green:[60,60,60,60],offset:[0,0,0,0]},[]));
const pattern={platoonSize:4,period:48,spacing:1,jitter:0,phase:4,reverseRate:.01,crossRate:.02};
const northsouth=patternDemand({...pattern,platoonAxis:'northsouth'},101,12);
assert.ok(northsouth.some(event=>event.t===4&&[4,6].includes(event.lane)));
assert.ok(!northsouth.some(event=>event.t===4&&[0,2].includes(event.lane)));
const mixed=patternDemand({...pattern,slowRate:.3,slowSpeed:10},101,120);
assert.deepEqual(mixed,patternDemand({...pattern,slowRate:.3,slowSpeed:10},101,120));
assert.ok(mixed.some(event=>event.speed===10)&&mixed.some(event=>event.speed===18));
const mixedRun=simulate(baseline,mixed,{check:true,frames:true});
assert.ok(mixedRun.frames.some(frame=>frame.cars.some(car=>car[3]===10)));
assert.throws(()=>validateTrafficPattern({...pattern,slowRate:.2}));
const reference={arrived:10,direction:[{meanWait:10},{meanWait:10}]};
assert.equal(acceptable({arrived:9,direction:[{meanWait:0},{meanWait:0}]},reference),false);
assert.equal(acceptable({arrived:11,direction:[{meanWait:0},{meanWait:20}]},reference),false);
assert.equal(acceptable(reference,reference),true);
assert.ok(TRAINING_SEEDS.every(s=>!VALIDATION_SEEDS.includes(s)));
assert.equal(candidates().length,CANDIDATE_COUNT);
assert.deepEqual(candidates(),candidates());
assert.equal(new Set(candidates().map(config=>JSON.stringify(config))).size,CANDIDATE_COUNT);
// 高負荷、全候補、暖機からの切替を通じて占有・車間・保存則を検査。
for(const config of candidates())simulate(config,dense,{check:true});
const report={version:VERSION,warmup:WARMUP,duration:DURATION,trainingSeeds:TRAINING_SEEDS,validationSeeds:VALIDATION_SEEDS,scenarios:[]};
for(const scenario of ['eastwest','balanced']) {
 const ranked=candidates().map(config=>({config,score:evaluate(config,scenario)})).sort((a,b)=>a.score-b.score);
 assert.ok(Number.isFinite(ranked[0].score));assert.ok(ranked[0].score<=evaluate(baseline,scenario));
 const selected=ranked[0].config;
 const validation=assess(selected,scenario,VALIDATION_SEEDS);
 for(const seed of VALIDATION_SEEDS)simulate(selected,demand(scenario,seed),{check:true});
 report.scenarios.push({scenario,selected,eligibleCandidates:ranked.filter(r=>Number.isFinite(r.score)).length,
  validation:validation.pairs.map(({seed,base,candidate})=>({seed,acceptable:acceptable(candidate,base),base:{wait:base.meanWait,arrived:base.arrived,direction:base.direction},candidate:{wait:candidate.meanWait,arrived:candidate.arrived,direction:candidate.direction}}))});
}
if(process.argv.includes('--json'))console.log(JSON.stringify(report,null,2));
else for(const s of report.scenarios)console.log(s.scenario,JSON.stringify(s.validation.map(v=>({seed:v.seed,acceptable:v.acceptable,base:v.base.wait,best:v.candidate.wait,arrived:[v.base.arrived,v.candidate.arrived]}))));
console.error('PASS: 暖機、出口空間、交差点占有、車間、保存則、再現性、到着数・公平性制約、未使用5シード');
