import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import {DURATION,COURSE_LABELS} from './physics.mjs';

// app本体の状態遷移を実行する。DOMと描画だけを代用し、ブラウザ用のimport/bootstrapを外す。
const source=(await fs.readFile(new URL('./app.mjs',import.meta.url),'utf8'))
  .replace(/^import .*;\n/gm,'').replace(/^refresh\(\);setInterval\(refresh,1000\);requestAnimationFrame\(animate\);\s*$/m,'');
class Element {
  constructor(){this.children=[];this.dataset={};this.style={setProperty(){}};this.listeners={};this.classList={add(){},remove(){},toggle(){}};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];}
  setAttribute(name,value){this[name]=value;}
  addEventListener(name,callback){this.listeners[name]=callback;}
}
const state=(session='trial-a',experiment='experiment',extra={})=>({session,comparison:{id:experiment,runIndex:0,startPopulationSeed:2026,totalRuns:0,results:[]},
  seed:2026,populationSeed:2026,generation:4,generations:20,populationSize:36,completedCandidates:0,ranking:{best:[],worst:[],evaluated:36},
  history:[],workers:[],running:true,phase:'evaluating',updatedAt:new Date().toISOString(),...extra});
const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-9,`${actual} ≠ ${expected}`);
const replay=(key='trial-a:4',extra={})=>({key,populationSeed:2026,champion:{generation:4,distance:75.5},initial:{distance:22.8},...extra});
function harness(){
  const elements=new Map(),draws=[],clock={value:1000};
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  class ClockDate extends Date {static now(){return clock.value;}}
  const context=vm.createContext({DURATION,COURSE_LABELS,AbortController,AbortSignal,Date:ClockDate,console,
    document:{getElementById:get,createElement:()=>new Element(),body:new Element(),activeElement:null},
    drawRace:(_canvas,r,t)=>{if(r)draws.push({key:r.key,time:t});return null;},drawThumbnail(){},requestAnimationFrame(){},
    fetch:async()=>{throw Error('unexpected fetch');}});
  vm.runInContext(source+`\nglobalThis.api={render,applyReplay,refresh,selectReplay,animate,
    snapshot:()=>({replay,pendingReplay,elapsed,resultElapsed,session,selectedCar,selectionLoading,connected})};`,context);
  const api=context.api;
  const tick=(seconds,{live=true}={})=>{
    for(let i=0;i<Math.round(seconds*20);i++){
      clock.value+=50;
      // 実際の1秒ポーリングに相当。接続が継続している試験だけ更新する。
      if(live&&i%20===0)vm.runInContext('received=Date.now()',context);
      api.animate(clock.value);
    }
  };
  api.animate(clock.value);
  const respond=(s,r)=>{context.fetch=async url=>({ok:true,json:async()=>url==='/api/state'?s:r});};
  return {api,get,context,tick,respond,draws,clock};
}

{
  const h=harness(),a=state(),r=replay();h.api.render(a);h.api.applyReplay(r);h.tick(6);
  const before=h.api.snapshot().elapsed;
  const b=state('trial-b','experiment',{populationSeed:2027,replayKey:'trial-b:0'}),next=replay('trial-b:0',{populationSeed:2027,champion:{generation:0}});
  h.respond(b,next);await h.api.refresh();
  assert.equal(h.api.snapshot().replay.key,r.key);assert.equal(h.api.snapshot().elapsed,before);
  assert.equal(h.api.snapshot().pendingReplay.key,next.key);assert.match(h.get('replay-title').textContent,/seed 2026/);
  h.tick(DURATION-6);assert.equal(h.api.snapshot().replay.key,r.key);assert.equal(h.api.snapshot().elapsed,DURATION);
  assert.deepEqual(h.draws.at(-1),{key:r.key,time:DURATION});
  assert.equal(h.get('replay-result').hidden,false);assert.equal(h.get('result-distance').textContent,'75.5 m');
  assert.equal(h.get('result-baseline').textContent,'初代の最良車 22.8 m');
  h.tick(4.95);assert.equal(h.api.snapshot().replay.key,r.key);near(h.api.snapshot().resultElapsed,4.95);
  assert.deepEqual(h.draws.at(-1),{key:r.key,time:DURATION});
  h.tick(.05);assert.equal(h.api.snapshot().replay.key,r.key);near(h.api.snapshot().resultElapsed,5);
  h.tick(.05);assert.equal(h.api.snapshot().replay.key,next.key);assert.equal(h.get('replay-result').hidden,true);assert.equal(h.api.snapshot().elapsed,0);
  assert.match(h.get('replay-title').textContent,/seed 2027/);
  console.log('PASS: 自動試行切替で走行/時計/seedを保持し、30秒の最終姿勢と再生車の距離を5秒保持後に新試行へ切替');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(2);
  for(const [trial,seed] of [['trial-b',2027],['trial-c',2028]]){
    h.respond(state(trial,'experiment',{populationSeed:seed,replayKey:trial+':2'}),replay(trial+':2',{populationSeed:seed}));
    await h.api.refresh();h.tick(1);
  }
  assert.equal(h.api.snapshot().replay.key,'trial-a:4');assert.equal(h.api.snapshot().pendingReplay.key,'trial-c:2');
  h.tick(DURATION+1.05);assert.equal(h.api.snapshot().replay.key,'trial-c:2');
  console.log('PASS: 再生中に複数試行が進んでも最新1件だけを待機し、古い待機結果を再生しない');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(6);
  h.respond(state('trial-b','experiment',{generation:-1,replayKey:null}),null);await h.api.refresh();
  h.tick(DURATION-6);assert.equal(h.api.snapshot().elapsed,DURATION);h.tick(5.05);
  assert.equal(h.api.snapshot().replay.key,'trial-a:4');assert.equal(h.api.snapshot().elapsed,0);
  console.log('PASS: 次試行の走行が未準備でも表示を消さず、30秒と結果5秒を表示して繰り返す');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(6);
  h.get('play').listeners.click();h.api.render(state('trial-b'));h.tick(2);
  near(h.api.snapshot().elapsed,6);h.get('play').listeners.click();h.tick(1);near(h.api.snapshot().elapsed,7);
  h.context.fetch=async()=>{throw Error('test offline');};await h.api.refresh();h.tick(2,{live:false});
  near(h.api.snapshot().elapsed,7);assert.equal(h.api.snapshot().connected,false);
  h.respond(state('trial-b'),null);await h.api.refresh();h.tick(1);near(h.api.snapshot().elapsed,8);
  console.log('PASS: 試行切替中の再生一時停止と接続断・再接続で時計を維持');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(6);
  h.api.render(state('trial-b','new-experiment',{courseProfile:'rolling-v1'}));
  assert.equal(h.api.snapshot().replay,null);assert.equal(h.api.snapshot().pendingReplay,null);assert.equal(h.api.snapshot().elapsed,0);
  assert.equal(h.get('stage-message').hidden,false);
  console.log('PASS: 手動再計算・コース変更による実験切替では古い走行を解除');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());
  const selected={id:'best1',populationSeed:2025,generation:8};
  h.context.fetch=async()=>({ok:true,json:async()=>replay('best1',{carId:'best1',populationSeed:2025})});
  await h.api.selectReplay(selected);h.tick(6);h.api.render(state('trial-b'));
  assert.equal(h.api.snapshot().selectedCar.id,'best1');near(h.api.snapshot().elapsed,6);
  h.tick(DURATION-6);assert.deepEqual(h.draws.at(-1),{key:'best1',time:DURATION});h.tick(5.05);assert.equal(h.api.snapshot().replay.key,'best1');
  h.api.render(state('trial-c','new-experiment'));assert.equal(h.api.snapshot().selectedCar,null);assert.equal(h.api.snapshot().replay,null);
  console.log('PASS: カードの固定再生は試行をまたいで維持し、新実験では解除');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(4);
  h.respond(state('trial-a','experiment',{replayKey:'trial-a:9'}),replay('trial-a:9'));await h.api.refresh();
  h.get('latest').listeners.click();assert.equal(h.api.snapshot().replay.key,'trial-a:9');assert.equal(h.api.snapshot().elapsed,0);
  console.log('PASS: 明示的な「新しい最良車で再生」は待たずに切替');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());
  let resolve;
  h.context.fetch=async url=>({ok:true,json:async()=>url==='/api/state'?state('trial-b','experiment',{replayKey:'trial-b:2'}):await new Promise(r=>resolve=r)});
  const inflight=h.api.refresh();await new Promise(r=>setImmediate(r));
  h.api.render(state('trial-c'));
  resolve(replay('trial-b:2'));await inflight;
  assert.equal(h.api.snapshot().replay.key,'trial-a:4');assert.equal(h.api.snapshot().pendingReplay,null);
  console.log('PASS: 応答待ちに試行が進んだ場合は古い応答を採用しない');
}

{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(DURATION+2);
  near(h.api.snapshot().elapsed,DURATION);near(h.api.snapshot().resultElapsed,2);
  h.get('play').listeners.click();h.tick(3);near(h.api.snapshot().resultElapsed,2);assert.equal(h.get('replay-result').hidden,false);
  h.get('play').listeners.click();h.tick(1);near(h.api.snapshot().resultElapsed,3);
  h.context.fetch=async()=>{throw Error('test offline');};await h.api.refresh();h.tick(3,{live:false});near(h.api.snapshot().resultElapsed,3);
  h.respond(state(),null);await h.api.refresh();h.tick(2);near(h.api.snapshot().resultElapsed,5);h.tick(.05);near(h.api.snapshot().elapsed,0);
  assert.equal(h.get('replay-result').hidden,true);
  console.log('PASS: 結果表示の停止/再開・接続断でも残り5秒を保持');
}
{
  const h=harness();h.api.render(state());h.api.applyReplay(replay());h.tick(DURATION+1);
  h.api.render(state('trial-b','new-experiment'));assert.equal(h.get('replay-result').hidden,true);near(h.api.snapshot().resultElapsed,0);
  h.api.applyReplay(replay('trial-b:3'));h.tick(DURATION+1);assert.equal(h.get('replay-result').hidden,false);
  h.respond(state('trial-b','new-experiment',{replayKey:'trial-b:9'}),replay('trial-b:9'));await h.api.refresh();
  h.get('latest').listeners.click();assert.equal(h.get('replay-result').hidden,true);near(h.api.snapshot().resultElapsed,0);
  console.log('PASS: 結果表示中の手動再計算/最新車への明示切替は待たずに解除');
}

{
  const h=harness();h.api.render(state('trial-a','experiment',{diagnostics:{unstableEvaluations:3,recent:[]}}));
  h.api.applyReplay(replay('trial-a:4',{champion:{generation:4,distance:61.78,elapsed:9.65,reason:'unstable'},initial:{distance:22.8,elapsed:4,reason:'stalled'}}));
  assert.match(h.get('mix-note').textContent,/不安定終了 3台/);assert.match(h.get('replay-note').textContent,/9.65秒で計算終了/);
  h.tick(DURATION);assert.equal(h.api.snapshot().elapsed,DURATION);assert.equal(h.get('replay-result').hidden,false);assert.equal(h.get('result-distance').textContent,'61.8 m');
  console.log('PASS: 不安定終了の台数と時刻を明示し、30秒再生/結果5秒の状態を保つ');
}
