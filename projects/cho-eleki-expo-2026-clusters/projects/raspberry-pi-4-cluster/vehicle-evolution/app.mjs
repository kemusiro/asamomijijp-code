import {DURATION,COURSE_LABELS} from './physics.mjs';
import {drawRace,drawThumbnail} from './draw.mjs';

const RESULT_HOLD_SECONDS=5;
const $=id=>document.getElementById(id),phases={starting:'準備中',evaluating:'探索中',between:'次の世代へ','between-runs':'次の初期集団へ',pausing:'世代の終了待ち',paused:'探索を一時停止',resetting:'最初から準備中',complete:'指定世代の探索完了',error:'探索を停止'};
let state=null,replay=null,pendingReplay=null,received=0,last=0,elapsed=0,resultElapsed=0,connected=false,refreshing=false,controlBusy=false,playing=true,session=null,experimentId=null,settingsEdited=false,selectedCar=null,selectionLoading=false,selectionError='',selectionSerial=0,selectionAbort=null;
const number=(v,digits=0)=>Number.isFinite(v)?v.toLocaleString('ja-JP',{maximumFractionDigits:digits,minimumFractionDigits:digits}):'—';
function notice(text){$('notice').textContent=text;$('notice').hidden=!text;}
function applyReplay(value) {
  replay=value;pendingReplay=null;elapsed=0;resultElapsed=0;
  $('replay-result').hidden=true;$('replay-result').dataset.key='';
  $('replay-title').textContent=value.carId?'初代 vs 選択車（seed '+value.populationSeed+'・第'+value.champion.generation+'世代）':value.champion.generation===0?'初代の最良車を走らせる':'初代 vs 第'+value.champion.generation+'世代の最良車';
  if(!value.carId)$('replay-title').textContent+='（seed '+value.populationSeed+'）';
  $('replay-current-label').textContent=value.carId?'選択した車体':'再生中の試行の最良車';
  $('stage-message').hidden=true;renderReplaySelection();
}
function renderReplaySelection() {
  $('latest').hidden=selectedCar===null&&!pendingReplay;
  $('latest').textContent=selectedCar===null?'新しい最良車で再生':'現在の探索の最良車に戻る';
  $('replay-note').textContent=selectionLoading?'選んだ車体の走行を読み込み中…':selectedCar!==null?'seed '+selectedCar.populationSeed+'・第'+selectedCar.generation+'世代を固定再生 · '+(state?.running?'探索は別に継続':state?.phase==='complete'?'探索は完了':'探索は停止中'):state?.running?'保存した走行を最後まで再生 · 探索は別に継続':state?.phase==='complete'?'探索完了 · 保存した走行を繰り返し再生':'探索は停止中 · 保存した走行を再生';
  if(replay?.champion.reason==='unstable')$('replay-note').textContent+=' · 不安定のため '+number(replay.champion.elapsed,2)+'秒で計算終了';
  if(replay?.initial.reason==='unstable'&&replay.champion.generation!==0)$('replay-note').textContent+=' · 初代は '+number(replay.initial.elapsed,2)+'秒で不安定終了';
  for(const card of $('lineage').children) {
    const selected=card.dataset.carId===selectedCar?.id;
    card.setAttribute('aria-pressed',String(selected));card.setAttribute('aria-busy',String(selected&&selectionLoading));
  }
}
async function selectReplay(car=null) {
  const serial=++selectionSerial,requestedExperiment=experimentId,requestedSession=session,previous=selectedCar;
  selectionAbort?.abort();const abort=new AbortController();selectionAbort=abort;
  selectedCar=car;selectionLoading=true;selectionError='';pendingReplay=null;renderReplaySelection();
  try {
    const query=car?'?car='+encodeURIComponent(car.id)+'&experiment='+encodeURIComponent(requestedExperiment):'';
    const response=await fetch('/api/replay'+query,{cache:'no-store',signal:AbortSignal.any([abort.signal,AbortSignal.timeout(15000)])}),data=await response.json();
    if(serial!==selectionSerial||requestedExperiment!==experimentId||!car&&requestedSession!==session)return;
    if(!response.ok)throw Error(data.error??'HTTP '+response.status);
    if(car?data.carId!==car.id:data?.key?.startsWith(requestedSession+':')!==true)throw Error('探索が切り替わりました。車体一覧から選び直してください');
    applyReplay(data);playing=true;$('play').textContent='再生を止める';
  }catch(error) {
    if(serial!==selectionSerial||abort.signal.aborted)return;
    selectedCar=previous;selectionError='車体の走行を読み込めません：'+error.message;notice(selectionError);
  }finally {
    if(serial===selectionSerial){selectionLoading=false;renderReplaySelection();}
  }
}
const trialColors=['#69e7ce','#79bfff','#ffca7a','#e3a5f7','#ff9ba5','#a8dd85','#d7beff','#ffae7c'];
function renderComparison(value) {
  const comparison=value.comparison??{runIndex:0,totalRuns:1,startPopulationSeed:value.populationSeed??value.seed,results:[]};
  let curves=[...comparison.results];
  if(!curves.some(r=>r.runIndex===comparison.runIndex))curves.push({runIndex:comparison.runIndex,populationSeed:value.populationSeed??value.seed,history:value.history,champion:value.champion,initialProfile:value.initialProfile});
  if(comparison.totalRuns===0)curves=curves.slice(-6);
  const all=curves.flatMap(r=>r.history),maxY=Math.max(20,Math.ceil(Math.max(0,...all.map(h=>h.distance))/20)*20),maxX=Math.max(1,value.generations-1),x=g=>43+g/maxX*340,y=d=>207-d/maxY*175;
  let svg='';
  for(let i=0;i<=4;i++){const v=maxY*i/4,py=y(v);svg+='<line x1="43" y1="'+py+'" x2="383" y2="'+py+'" stroke="#293749"/><text x="35" y="'+(py+4)+'" text-anchor="end" fill="#92a3b6" font-size="11">'+number(v)+'m</text>';}
  if(comparison.totalRuns===1)svg+='<polyline points="'+value.history.map(h=>x(h.generation)+','+y(h.mean)).join(' ')+'" fill="none" stroke="#ffca7a" stroke-width="2" opacity=".65"/>';
  for(const run of curves)svg+='<polyline points="'+run.history.map(h=>x(h.generation)+','+y(h.distance)).join(' ')+'" fill="none" stroke="'+trialColors[run.runIndex%8]+'" stroke-width="'+(run.runIndex===comparison.runIndex?3:2)+'"/>';
  svg+='<text x="43" y="231" fill="#92a3b6" font-size="11">初代</text><text x="383" y="231" text-anchor="end" fill="#92a3b6" font-size="11">第'+(value.generations-1)+'世代</text>';$('history').innerHTML=svg;
  $('chart-legend').innerHTML=curves.map(r=>'<span><i style="background:'+trialColors[r.runIndex%8]+'"></i>seed '+r.populationSeed+'</span>').join('')+(comparison.totalRuns===1?'<span class="mean">集団の平均</span>':'');
  const rows=comparison.totalRuns===0?curves:Array.from({length:comparison.totalRuns},(_,i)=>({runIndex:i,populationSeed:comparison.startPopulationSeed+i}));
  $('trial-results').innerHTML=rows.map(row=>{
    const i=row.runIndex,done=comparison.results.find(r=>r.runIndex===i),current=i===comparison.runIndex,car=done?.champion??(current?value.champion:null),status=done?'完了':current?'探索中':'待機';
    return '<div class="trial-row'+(current?' current-trial':'')+'"><span><i style="background:'+trialColors[i%8]+'"></i>seed '+row.populationSeed+(done?.initialProfile||current&&value.initialProfile?'<small class="profile-label">'+(done?.initialProfile??value.initialProfile).label+'</small>':'')+'</span><strong>'+number(car?.distance,1)+'<small> m</small></strong><span>'+status+'<small>'+(done?value.generations:current?Math.max(0,value.generation+1):0)+' / '+value.generations+'世代</small></span></div>';
  }).join('');
}
function renderWorkers(workers) {
  if($('workers').children.length!==workers.length) {
    $('workers').replaceChildren(...workers.map(w=>{
      const el=document.createElement('article');el.className='worker';el.dataset.id=w.id;
      const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;canvas.setAttribute('aria-hidden','true');
      const div=document.createElement('div'),name=document.createElement('strong'),status=document.createElement('small');name.textContent=w.id;div.append(name,status);el.append(canvas,div);return el;
    }));
    $('workers').style.setProperty('--count',Math.min(6,workers.length));
  }
  workers.forEach((w,i)=>{
    const el=$('workers').children[i];el.querySelector('strong').textContent=w.id;el.classList.toggle('active',w.status==='evaluating');
    el.querySelector('small').textContent=(w.status==='evaluating'?'評価中 #'+(w.candidateId+1):w.status==='done'?number(w.distance,1)+'m':'待機')+' · '+number(w.count)+'台完了';
    drawThumbnail(el.querySelector('canvas'),w.genome,w.status==='evaluating'?'#69e7ce':'#8095aa');
  });
}
function renderRanking(ranking={best:[],worst:[]}) {
  const bestIds=new Set(ranking.best.map(c=>c.id));
  const worst=ranking.worst.filter(c=>!bestIds.has(c.id));
  const entries=[...Array.from({length:3},(_,i)=>({car:worst[i],label:'ワースト'+(i+1),tone:'worst'})),...Array.from({length:3},(_,i)=>({car:ranking.best[i],label:'ベスト'+(i+1),tone:'best'}))];
  const key=entries.map(e=>e.car?.id??e.label).join(',');
  if($('lineage').dataset.key!==key) {
    const children=[...$('lineage').children],focused=document.activeElement,focusIndex=children.indexOf(focused);
    const existing=new Map(children.map(el=>[el.dataset.carId,el]));
    $('lineage').dataset.key=key;
    $('lineage').replaceChildren(...entries.map(({car,label,tone})=>{
      const card=car&&existing.get(car.id)||document.createElement('button');card.type='button';card.className='ancestor '+tone;card.disabled=!car;
      card.dataset.carId=car?.id??'';card.replaceChildren();
      if(car&&!card.dataset.bound){card.addEventListener('click',()=>selectReplay(car));card.dataset.bound='true';}
      card.setAttribute('aria-label',car?label+'の車体を再生（'+number(car.distance,1)+'m、seed '+car.populationSeed+'、第'+car.generation+'世代、候補'+(car.candidateIndex+1)+'）':label+'を集計中');
      const canvas=document.createElement('canvas');canvas.width=210;canvas.height=110;canvas.setAttribute('aria-hidden','true');
      const text=document.createElement('span'),name=document.createElement('span'),strong=document.createElement('strong'),source=document.createElement('small');name.textContent=label;strong.textContent=car?number(car.distance,1)+' m':'—';source.textContent=car?'seed '+car.populationSeed+' · 第'+car.generation+'世代':'評価後に表示';text.append(name,strong,source);card.append(canvas,text);if(car)drawThumbnail(canvas,car.genome,tone==='worst'?'#ffb39e':'#69e7ce');return card;
    }));
    if(focusIndex>=0){const target=[...$('lineage').children].find(el=>el.dataset.carId===focused.dataset.carId)??$('lineage').children[focusIndex];if(!target?.disabled)target?.focus({preventScroll:true});}
  }
  renderReplaySelection();
}
function clearReplay() {
  replay=null;pendingReplay=null;elapsed=0;resultElapsed=0;
  $('replay-result').hidden=true;$('replay-result').dataset.key='';
  $('map-current').style.left='0%';$('map-original').style.left='0%';
  $('stage-message').hidden=false;$('stage-message').textContent='最初の世代を評価しています…';
  $('replay-title').textContent='最初の走行結果を待っています';$('latest').hidden=true;
}
function render(value) {
  state=value;connected=true;received=Date.now();document.body.classList.remove('disconnected');
  const comparison=value.comparison??{id:value.session,runIndex:0,totalRuns:1,startPopulationSeed:value.populationSeed??value.seed};
  if(experimentId!==comparison.id){selectionSerial++;selectionAbort?.abort();selectedCar=null;selectionLoading=false;selectionError='';experimentId=comparison.id;settingsEdited=false;clearReplay();}
  if(session!==value.session){session=value.session;if(selectedCar===null){
    selectionSerial++;selectionAbort?.abort();selectionLoading=false;
    // 試行の切替では再生中の走行と時計を保つ。旧試行の待機結果だけを捨てる。
    pendingReplay=null;
  }}
  if(!settingsEdited){$('course-profile').value=value.courseProfile??'rolling-v1';$('course-seed').value=value.courseSeed??value.seed;$('population-seed').value=comparison.startPopulationSeed;$('run-count').value=comparison.totalRuns;$('generations').value=value.generations;}
  $('condition-note').textContent=COURSE_LABELS[value.courseProfile??'rolling-v1']+' '+(value.courseSeed??value.seed)+'を固定 · '+value.generations+'世代ごとに初期集団を変更'+(comparison.totalRuns===0?'して探索を継続':'して比較')+(value.initialProfile?' · 初期タイプ：'+value.initialProfile.label:'');
  $('mode').textContent=(value.mode==='local'?'このPCで計算 · '+value.workers.length+'並列':'HTTP workerで計算 · '+value.workers.length+'接続')+' · 試行 '+number(comparison.runIndex+1)+(comparison.totalRuns===0?'（連続）':' / '+comparison.totalRuns);
  $('generation').innerHTML=number(value.generation<0?0:value.generation)+'<small>世代</small>';
  $('generation-note').textContent=value.generation<0?'初代を評価しています':'初期集団seed '+(value.populationSeed??value.seed)+' · 第'+value.generation+'世代まで評価済み';
  $('distance').innerHTML=number(value.champion?.distance,1)+'<small>m</small>';
  const record=value.ranking?.best[0];
  $('gain').innerHTML=number(record?.distance,1)+'<small>m</small>';
  $('initial-note').textContent=record?'seed '+record.populationSeed+' · 第'+record.generation+'世代':'全候補を評価してから表示します';
  $('evaluated').innerHTML=number(value.ranking?.evaluated??value.evaluated)+'<small>台</small>';
  $('phase').textContent=phases[value.phase]??value.phase;
  $('progress-note').textContent='試行 '+number(comparison.runIndex+1)+(comparison.totalRuns===0?'（連続）':' / '+comparison.totalRuns)+' · '+value.populationSize+'台 × '+value.generations+'世代';
  const mix=value.searchMix;$('mix-note').textContent=mix?'保存 '+mix.elite+' / 小変異 '+mix.normal+' / 大変異 '+mix.large+' / 新規 '+mix.fresh+(mix.burst?' · 停滞による探索拡大中':''):'';
  if(value.diagnostics?.unstableEvaluations)$('mix-note').textContent+=' · 不安定終了 '+number(value.diagnostics.unstableEvaluations)+'台（直前まで採点）';
  $('ranking-note').textContent='全'+number(value.ranking?.evaluated??0)+'評価から選出 · 同じ形・ワーストの0.0mを除外 · 車体を選んで再生';
  $('progress-text').textContent=number(value.completedCandidates)+' / '+value.populationSize+' 台を評価';
  $('progress-fill').style.width=Math.min(100,value.completedCandidates/value.populationSize*100)+'%';
  $('pause').textContent=value.running?'探索を一時停止':'探索を再開';$('pause').disabled=controlBusy||value.phase==='complete'||value.phase==='pausing'||value.phase==='resetting';
  $('worker-note').textContent=value.mode==='local'?'このPCの実際の評価スロット · Pi 4の実測値ではありません':'接続中のHTTP worker · 候補ごとに独立評価';
  $('updated').textContent=COURSE_LABELS[value.courseProfile??'rolling-v1']+' '+(value.courseSeed??value.seed)+' / 初期集団 '+(value.populationSeed??value.seed)+' · 更新 '+new Date(value.updatedAt).toLocaleTimeString('ja-JP');
  notice(value.error?'探索を停止しました：'+value.error+'。workerを確認して「探索を再開」を押してください。':selectionError);
  renderComparison(value);renderWorkers(value.workers);renderRanking(value.ranking);
}
async function refresh() {
  if(refreshing)return;refreshing=true;
  try {
    const response=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error('HTTP '+response.status);
    const value=await response.json();render(value);
    if(selectedCar===null&&!selectionLoading&&value.replayKey&&value.replayKey!==replay?.key&&value.replayKey!==pendingReplay?.key) {
      const r=await fetch('/api/replay',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error('走行結果 HTTP '+r.status);
      const data=await r.json();if(selectedCar===null&&!selectionLoading&&session===value.session&&data?.key===value.replayKey){if(!replay)applyReplay(data);else{pendingReplay=data;renderReplaySelection();}}
    }
  }catch(error){connected=false;document.body.classList.add('disconnected');notice('表示サーバへ再接続中：'+error.message+'。最後の表示を保持しています。');}
  finally{refreshing=false;}
}
async function control(action,configuration={}) {
  if(controlBusy)return;controlBusy=true;$('pause').disabled=true;$('reset').disabled=true;
  try {
    const r=await fetch('/api/control',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action,...configuration}),signal:AbortSignal.timeout(5000)}),body=await r.json();if(!r.ok)throw Error(body.error);await refresh();
  }catch(error){notice(error.message);}finally{controlBusy=false;$('reset').disabled=false;if(state)$('pause').disabled=state.phase==='complete';}
}
$('pause').addEventListener('click',()=>control(state?.running?'pause':'resume'));
for(const id of ['course-profile','course-seed','population-seed','run-count','generations'])$(id).addEventListener('input',()=>{settingsEdited=true;});
$('reset').addEventListener('click',()=>{
  if(['course-profile','course-seed','population-seed','run-count','generations'].some(id=>!$(id).value.trim()))return notice('比較条件をすべて入力してください');
  const courseSeed=Number($('course-seed').value),populationSeed=Number($('population-seed').value),runs=Number($('run-count').value),generations=Number($('generations').value);
  if(!Number.isInteger(courseSeed)||courseSeed<0||courseSeed>2147483647||!Number.isInteger(populationSeed)||populationSeed<0||populationSeed>2147483647)return notice('seedは0～2147483647の整数で指定してください');
  if(!Number.isInteger(runs)||runs<0||runs>8||runs!==0&&populationSeed+runs-1>2147483647)return notice('試行数は0（連続）～8です。有限試行では初期集団seedの上限を超えないよう指定してください');
  if(!Number.isInteger(generations)||generations<1||generations>1000)return notice('世代数は1～1000で指定してください');
  control('compare',{courseSeed,populationSeed,runs,generations,courseProfile:$('course-profile').value});
});
$('latest').addEventListener('click',()=>{if(selectedCar!==null)selectReplay(null);else if(pendingReplay)applyReplay(pendingReplay);});
$('play').addEventListener('click',()=>{playing=!playing;$('play').textContent=playing?'再生を止める':'再生を再開';});
function renderReplayResult() {
  const result=$('replay-result');result.hidden=!replay||elapsed<DURATION;
  if(result.hidden)return;
  // 探索中のstateではなく、最後まで再生した車体の評価値を表示する。
  if(result.dataset.key!==replay.key) {
    result.dataset.key=replay.key;
    $('result-source').textContent=(replay.carId?'選択車':'最良車')+' · seed '+replay.populationSeed+' · 第'+replay.champion.generation+'世代';
    $('result-distance').textContent=number(replay.champion.distance,1)+' m';
    $('result-baseline').textContent='初代の最良車 '+number(replay.initial?.distance,1)+' m';
  }
  const next='次の再生まで '+Math.max(0,Math.ceil(RESULT_HOLD_SECONDS-resultElapsed))+' 秒';
  if($('result-next').textContent!==next)$('result-next').textContent=next;
}
function animate(now) {
  const delta=last?Math.min(.1,(now-last)/1000):0;last=now;
  if(replay&&playing&&connected&&Date.now()-received<6000) {
    // 最終姿勢とその車体の到達距離を5秒保持してから次へ進む。
    if(elapsed<DURATION)elapsed=Math.min(DURATION,elapsed+delta);
    else if(resultElapsed<RESULT_HOLD_SECONDS) {
      resultElapsed+=delta;
      if(resultElapsed>=RESULT_HOLD_SECONDS-1e-9)resultElapsed=RESULT_HOLD_SECONDS;
    }
    else if(selectedCar===null&&!selectionLoading&&pendingReplay)applyReplay(pendingReplay);
    else {elapsed=0;resultElapsed=0;}
  }
  const positions=drawRace($('race'),replay,elapsed);
  if(positions){$('map-original').style.left=positions.original+'%';$('map-current').style.left=positions.current+'%';}
  renderReplayResult();
  $('replay-clock').textContent=elapsed.toFixed(1)+' / '+DURATION.toFixed(1)+' 秒';
  if(Date.now()-received>=6000&&state){document.body.classList.add('disconnected');notice('状態の更新が止まっています。再生を停止し、最後の表示を保持しています。');}
  requestAnimationFrame(animate);
}
refresh();setInterval(refresh,1000);requestAnimationFrame(animate);
