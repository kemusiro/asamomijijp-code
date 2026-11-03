import {phase,baseline,DT,CANDIDATE_COUNT} from './engine.mjs';
const $=id=>document.getElementById(id);
let worker,watchdog,result,scenario='eastwest',paused=false,elapsed=0,last=0,retry=0,mode='calculating';
const names={eastwest:'東西方向に交通集中',balanced:'東西・南北に均等な交通'};
function draw(id,frame,config) {
 const ctx=$(id).getContext('2d'); ctx.clearRect(0,0,700,560);
 const px=x=>60+x*.58, py=y=>25+y*.49, xs=[px(330),px(670)],ys=[py(330),py(670)];
 ctx.fillStyle='#1d3238';
 for(const y of ys)ctx.fillRect(40,y-20,620,40);
 for(const x of xs)ctx.fillRect(x-20,10,40,530);
 ctx.strokeStyle='#607176';ctx.lineWidth=1;ctx.setLineDash([6,8]);
 for(const y of ys){ctx.beginPath();ctx.moveTo(40,y);ctx.lineTo(660,y);ctx.stroke();}
 for(const x of xs){ctx.beginPath();ctx.moveTo(x,10);ctx.lineTo(x,540);ctx.stroke();}ctx.setLineDash([]);
 for(let i=0;i<4;i++) {
  const x=xs[i%2],y=ys[Math.floor(i/2)],states=phase(config,i,frame?.signalTime||0);
  ctx.fillStyle='#233e44';ctx.fillRect(x-20,y-20,40,40);
  states.forEach((s,axis)=>{ctx.fillStyle={green:'#aee4a8',yellow:'#f2ce7e',red:'#e98b7b'}[s];
    ctx.beginPath();ctx.arc(x+(axis?0:-28),y+(axis?-28:0),4,0,Math.PI*2);ctx.fill();});
  ctx.fillStyle='#829da1';ctx.font='11px system-ui';ctx.fillText(String.fromCharCode(65+i),x+25,y-25);
 }
 for(const [lane,pos] of frame?.cars||[]) {
  const axis=lane<4?0:1,line=Math.floor((lane%4)/2),rev=lane%2;
  const coord=rev?1000-pos:pos;
  const x=axis?xs[line]+(rev?7:-7):px(coord),y=axis?py(coord):ys[line]+(rev?-7:7);
  ctx.fillStyle=axis?'#93bdce':'#e8cd90';ctx.fillRect(x-(axis?2:3.5),y-(axis?3.5:2),axis?4:7,axis?7:4);
 }
 ctx.font='11px system-ui';ctx.fillStyle='#9eb5b6';ctx.fillText('東西の車',43,550);ctx.fillStyle='#e8cd90';ctx.fillRect(25,542,10,7);
 ctx.fillStyle='#9eb5b6';ctx.fillText('南北の車',148,550);ctx.fillStyle='#93bdce';ctx.fillRect(130,542,10,7);
 ctx.fillStyle='#9eb5b6';ctx.fillText(`入口で待機：${frame?.queued.reduce((a,b)=>a+b,0)||0}台`,470,550);
 $(id+'-wait').textContent=frame?`${frame.meanWait.toFixed(1)} 秒`:'—';
 $(id+'-count').textContent=frame?`${frame.arrived} / ${frame.generated}`:'—';
 $(id+'-left').textContent=frame?`${frame.generated-frame.arrived} 台`:'—';
 $(id+'-direction').textContent=frame?`方向別の平均待ち：東西 ${frame.direction[0].meanWait.toFixed(1)}秒 / 南北 ${frame.direction[1].meanWait.toFixed(1)}秒`:'方向別の平均待ち：—';
}
function failure(message) {
 clearTimeout(watchdog);worker?.terminate();mode='error';$('phase').textContent='計算エラー';
 $('outcome').textContent=message;$('detail').textContent=retry<1?'一度だけ自動再試行します。':'「次の交通条件」またはページ再読み込みで再開できます。';
 console.error(message);
 if(retry++<1)watchdog=setTimeout(()=>start(false),2000);
}
function start(reset=true) {
 clearTimeout(watchdog);worker?.terminate();if(reset)retry=0;
 result=null;mode='calculating';elapsed=0;$('clock').textContent='シミュレーション 0 / 180 秒';$('settings').textContent=`同じ条件で${CANDIDATE_COUNT}候補を評価`;$('download').disabled=true;
 $('scenario').textContent=names[scenario];$('phase').textContent='候補を評価中';$('progress').textContent='計算を準備しています';
 $('outcome').textContent='探索と異なる乱数で効果を確かめます';$('detail').textContent='Mac内の1ワーカで計算中。分散実行・クラスタ性能の測定ではありません。';
 draw('base',null,baseline);draw('optimized',null,baseline);
 worker=new Worker('./worker.mjs',{type:'module'});watchdog=setTimeout(()=>failure('120秒以内に計算が完了しませんでした'),120000);
 worker.onerror=event=>failure(event.message);
 worker.onmessage=({data})=>{
  if(data.type==='error'){failure(data.message);return;}
  if(data.type==='progress'){$('progress').textContent=`${data.done} / ${data.total} 候補評価済み`;return;}
  clearTimeout(watchdog);worker.terminate();result=data;mode='replay';elapsed=0;
  $('phase').textContent='計算結果の再生 · 4倍速';$('download').disabled=false;
  $('settings').textContent=`東西青：${data.best.green.join('/')}秒 ｜ 時差：${data.best.offset.join('/')}秒`;
  const improvement=data.base.meanWait-data.optimized.meanWait;
  const percent=data.base.meanWait?Math.abs(improvement/data.base.meanWait*100):0;
  const passed=data.validation.filter(v=>v.acceptable).length;
  $('outcome').textContent=`未使用5条件のうち ${passed} 条件で到着数・方向別待ちの条件を満たす`;
  $('detail').textContent=`表示中の180秒結果：待ち時間 ${percent.toFixed(1)}% ${improvement>=0?'減':'増'}・到着 ${data.base.arrived}→${data.optimized.arrived}台 ／ 共通暖機60秒 ／ 探索3条件・検証5条件 ／ 計算 ${(data.elapsed/1000).toFixed(2)}秒`;
  console.info('traffic-result',{scenario,base:data.base.meanWait,optimized:data.optimized.meanWait,elapsedMs:data.elapsed});
 };worker.postMessage({scenario});
}
function next(){scenario=scenario==='eastwest'?'balanced':'eastwest';start();}
$('next').onclick=next;
$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'再開':'一時停止';};
$('download').onclick=()=>{if(!result)return;const {base,optimized,...rest}=result;
 const summary={...rest,base:{...base,frames:undefined},optimized:{...optimized,frames:undefined},recordedAt:new Date().toISOString()};
 const url=URL.createObjectURL(new Blob([JSON.stringify(summary,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download=`traffic-${scenario}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
function tick(now){const dt=last?Math.min((now-last)/1000,.1):0;last=now;
 if(result && !paused){elapsed+=dt;const t=Math.min(180,elapsed*4),index=Math.min(result.base.frames.length-1,Math.max(0,Math.floor(t/DT)-1));
  const f=t<DT?null:result.base.frames[index],g=t<DT?null:result.optimized.frames[index];
  draw('base',f,result.baseline);draw('optimized',g,result.best);$('clock').textContent=`シミュレーション ${Math.floor(t)} / 180 秒`;
  if(elapsed>=45){$('phase').textContent='結果表示 · 次の条件へ自動切替';}
  if(elapsed>=53)next();
 }requestAnimationFrame(tick);}
window.addEventListener('pagehide',()=>{clearTimeout(watchdog);worker?.terminate();});
start();requestAnimationFrame(tick);
