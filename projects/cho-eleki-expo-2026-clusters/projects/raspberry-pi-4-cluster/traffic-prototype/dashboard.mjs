import {baseline,DT,DURATION,PATTERN_VALIDATION_SEEDS,patternDemand,phase,simulate} from './engine.mjs';

const $=id=>document.getElementById(id);
const phaseNames={starting:'ワーカ確認',single:'1台で探索',distributed:'12台で並列探索',validation:'未使用条件で検証',result:'結果を表示',recovering:'自動復旧中'};
const phaseOrder=['single','distributed','validation','result'];
let snapshot=null,refreshing=false,replay=null,replayKey='',replayElapsed=0,lastFrame=0;
let selectingPattern=false;

function number(value,digits=1) {
  return Number.isFinite(value)?value.toFixed(digits):'—';
}

function elapsedSeconds(iso) {
  return iso?Math.max(0,(Date.now()-Date.parse(iso))/1000):0;
}

function completedRun(run) {
  return run&&Number.isFinite(run.evaluatedCount)?run:null;
}

function runForCard(kind,exhibition,latest) {
  if(!exhibition)return latest?.[kind]??null;
  if(kind==='single') {
    if(exhibition.phase==='single')return {evaluatedCount:exhibition.completedCandidates,completedGenerations:exhibition.completedGenerations,best:exhibition.best};
    return completedRun(exhibition.single)??latest?.single??null;
  }
  if(exhibition.phase==='distributed')return {evaluatedCount:exhibition.completedCandidates,completedGenerations:exhibition.completedGenerations,best:exhibition.best};
  return completedRun(exhibition.distributed)??latest?.distributed??null;
}

function renderRunCard(prefix,run) {
  $(prefix+'-count').textContent=run?String(run.evaluatedCount??0):'—';
  $(prefix+'-generation').textContent=run?(run.completedGenerations??0)+'世代を完了':'候補を探索';
  $(prefix+'-quality').textContent=Number.isFinite(run?.best?.score)?'探索中の評価値 '+number(run.best.score)+'秒':'最良値を探索中';
}

function renderPhase(exhibition,budgetMs) {
  const currentPhase=exhibition?.phase??'starting';
  $('cycle-title').textContent=exhibition?'サイクル '+exhibition.cycle+' · '+(exhibition.pattern?.name??'交通条件を準備中'):'自動運転の開始待ち';
  $('phase-name').textContent=phaseNames[currentPhase]??currentPhase;
  $('phase-badge').querySelector('span').textContent=phaseNames[currentPhase]??currentPhase;
  $('phase-badge').classList.toggle('degraded',currentPhase==='recovering'||exhibition?.status==='degraded');
  $('single-card').classList.toggle('active',currentPhase==='single');
  $('multi-card').classList.toggle('active',currentPhase==='distributed');
  const activeIndex=phaseOrder.indexOf(currentPhase);
  for(const item of document.querySelectorAll('.sequence span')) {
    const index=phaseOrder.indexOf(item.dataset.phase);
    item.classList.toggle('active',item.dataset.phase===currentPhase);
    item.classList.toggle('done',activeIndex>index||(currentPhase==='result'&&index<3));
  }
  const elapsed=elapsedSeconds(exhibition?.phaseStartedAt);
  let ratio=0,clock='—',label=phaseNames[currentPhase]??'準備中';
  if(currentPhase==='single'||currentPhase==='distributed') {
    ratio=Math.min(1,elapsed*1000/budgetMs);
    clock=Math.min(budgetMs/1000,elapsed).toFixed(1)+' / '+(budgetMs/1000).toFixed(0)+' 秒';
    label=(currentPhase==='single'?'1台':'12台')+'で候補を評価中';
  } else if(currentPhase==='result'&&exhibition?.holdUntil) {
    const remaining=Math.max(0,(Date.parse(exhibition.holdUntil)-Date.now())/1000);
    const hold=Math.max(1,(Date.parse(exhibition.holdUntil)-Date.parse(exhibition.phaseStartedAt))/1000);
    ratio=1-remaining/hold;clock='次の探索まで '+Math.ceil(remaining)+' 秒';label='結果を自動再生中';
  } else if(currentPhase==='validation') {
    ratio=.97;clock='最終確認';label='探索に使っていない5条件で検証';
  } else if(currentPhase==='recovering') {
    const remaining=exhibition.retryAt?Math.max(0,(Date.parse(exhibition.retryAt)-Date.now())/1000):0;
    clock=Math.ceil(remaining)+' 秒後に再試行';label=exhibition.error??'ワーカを待っています';
  }
  $('phase-clock').textContent=clock;$('progress-label').textContent=label;
  $('progress-value').textContent=(currentPhase==='single'||currentPhase==='distributed')?(exhibition?.completedCandidates??0)+'候補 / '+(exhibition?.completedGenerations??0)+'世代':'';
  $('progress-fill').style.width=Math.max(0,Math.min(100,ratio*100))+'%';
}

async function queuePattern(patternId) {
  if(selectingPattern)return;selectingPattern=true;
  try {
    const response=await fetch('/api/exhibition/pattern',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({patternId})});
    if(!response.ok)throw Error('HTTP '+response.status);
    await refresh();
  } catch(error) {
    $('notice').hidden=false;$('notice').textContent='交通パターンを予約できません: '+error.message;
  } finally {selectingPattern=false;}
}

function renderPatternButtons(data) {
  const active=data.exhibition?.pattern?.id,queued=data.patternRequest?.requestedPatternId;
  $('pattern-buttons').replaceChildren(...data.patterns.map(pattern=>{
    const button=document.createElement('button');button.type='button';button.textContent=pattern.name;button.title=pattern.description;
    button.classList.toggle('active',pattern.id===active);button.classList.toggle('queued',pattern.id===queued);
    if(pattern.id===queued)button.setAttribute('aria-label',pattern.name+'（次回に予約済み）');
    button.addEventListener('click',()=>queuePattern(pattern.id));return button;
  }));
}

function renderRace(events,budgetMs,expectedWorkers) {
  const target=$('live-race');target.replaceChildren();
  const eventWorkers=[...new Set((events??[]).map(item=>item.workerId))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  const workers=eventWorkers.length?eventWorkers:Array.from({length:expectedWorkers},(_,index)=>'node'+(10+index));
  const laneHeight=Math.max(6,Math.min(12,(target.clientHeight-3)/Math.max(1,workers.length)));
  for(const [lane,workerId] of workers.entries()) {
    const label=document.createElement('span');label.className='lane-label';label.textContent=workerId;label.style.top=(lane*laneHeight)+'px';target.append(label);
  }
  for(const event of events??[]) {
    const lane=workers.indexOf(event.workerId);if(lane<0)continue;
    const bar=document.createElement('i');bar.className='candidate';
    bar.style.left=Math.max(0,Math.min(100,event.startedAtMs/budgetMs*100))+'%';
    bar.style.width=Math.max(.35,(Math.min(budgetMs,event.finishedAtMs)-event.startedAtMs)/budgetMs*100)+'%';
    bar.style.top=(lane*laneHeight+1)+'px';
    target.append(bar);
  }
  const deadline=document.createElement('b');deadline.className='deadline';deadline.textContent=(budgetMs/1000).toFixed(0)+'s';target.append(deadline);
}

function renderQuality(history,budgetMs) {
  const svg=$('quality-chart'),ns='http://www.w3.org/2000/svg';svg.replaceChildren();
  if(!history?.length) {
    const text=document.createElementNS(ns,'text');text.setAttribute('x','350');text.setAttribute('y','70');text.setAttribute('text-anchor','middle');text.setAttribute('class','quality-chart-empty');text.textContent='良い候補が見つかるたびに線が下がります';svg.append(text);return;
  }
  const scores=history.map(item=>item.score),minimum=Math.min(...scores),maximum=Math.max(...scores),range=Math.max(1,maximum-minimum);
  const left=12,right=688,top=12,bottom=120;
  const xy=item=>[left+Math.min(1,item.atMs/budgetMs)*(right-left),top+(maximum-item.score)/range*(bottom-top)];
  const points=history.map(xy);
  const axis=document.createElementNS(ns,'path');axis.setAttribute('d','M'+left+' '+top+'V'+bottom+'H'+right);axis.setAttribute('class','chart-axis');svg.append(axis);
  const area=document.createElementNS(ns,'polygon');area.setAttribute('points',left+','+bottom+' '+points.map(point=>point.join(',')).join(' ')+' '+points.at(-1)[0]+','+bottom);area.setAttribute('class','chart-area');svg.append(area);
  const line=document.createElementNS(ns,'polyline');line.setAttribute('points',points.map(point=>point.join(',')).join(' '));line.setAttribute('class','chart-line');svg.append(line);
  for(const [x,y] of points) {const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.setAttribute('r','3');dot.setAttribute('fill','#a8ee9d');svg.append(dot);}
}

function renderWorkers(data,counts) {
  $('workers').replaceChildren(...data.workers.map(worker=>{
    const element=document.createElement('div');element.className='worker '+(worker.ready?'ready':'down');
    const name=document.createElement('span');name.textContent=worker.workerId;
    const count=document.createElement('b');count.textContent=String(counts?.[worker.workerId]??0);
    element.append(name,count);return element;
  }));
}

function draw(canvasId,frame,config) {
  const canvas=$(canvasId),ctx=canvas.getContext('2d'),width=canvas.width,height=canvas.height;
  ctx.clearRect(0,0,width,height);
  const px=x=>55+x*(width-110)/1000,py=y=>18+y*(height-45)/1000;
  const xs=[px(330),px(670)],ys=[py(330),py(670)],road=30;
  ctx.fillStyle='#1a3036';for(const y of ys)ctx.fillRect(30,y-road/2,width-60,road);for(const x of xs)ctx.fillRect(x-road/2,8,road,height-30);
  ctx.strokeStyle='#557076';ctx.lineWidth=1;ctx.setLineDash([5,7]);
  for(const y of ys){ctx.beginPath();ctx.moveTo(30,y);ctx.lineTo(width-30,y);ctx.stroke();}
  for(const x of xs){ctx.beginPath();ctx.moveTo(x,8);ctx.lineTo(x,height-22);ctx.stroke();}ctx.setLineDash([]);
  for(let i=0;i<4;i++) {
    const x=xs[i%2],y=ys[Math.floor(i/2)],states=phase(config,i,frame?.signalTime??0);
    ctx.fillStyle='#203b41';ctx.fillRect(x-road/2,y-road/2,road,road);
    states.forEach((state,axis)=>{ctx.fillStyle={green:'#a8ee9d',yellow:'#f0c976',red:'#ea806f'}[state];ctx.beginPath();ctx.arc(x+(axis?0:-21),y+(axis?-21:0),3.5,0,Math.PI*2);ctx.fill();});
  }
  for(const [lane,position,,speed] of frame?.cars??[]) {
    const axis=lane<4?0:1,line=Math.floor((lane%4)/2),reverse=lane%2,coordinate=reverse?1000-position:position;
    const x=axis?xs[line]+(reverse?5:-5):px(coordinate),y=axis?py(coordinate):ys[line]+(reverse?-5:5);
    ctx.fillStyle=speed<18?'#d78bea':axis?'#79bad0':'#edcc80';ctx.fillRect(x-(axis?2:3.5),y-(axis?3.5:2),axis?4:7,axis?7:4);
  }
  ctx.font='10px system-ui';ctx.fillStyle='#789397';ctx.fillText('入口で待機 '+(frame?.queued.reduce((sum,value)=>sum+value,0)??0)+'台',width-130,height-8);
}

function prepareReplay(result) {
  if(!result?.pattern||!result.distributed?.best?.config)return;
  const key=result.source+':'+JSON.stringify(result.distributed.best.config);if(key===replayKey)return;
  const events=patternDemand(result.pattern,PATTERN_VALIDATION_SEEDS[0]);
  replay={base:simulate(baseline,events,{frames:true}),optimized:simulate(result.distributed.best.config,events,{frames:true}),config:result.distributed.best.config,result};
  replayKey=key;replayElapsed=0;
  $('replay-pattern').textContent=result.exhibitionPattern?.name??'東西ラッシュ';
  $('speed-legend').hidden=!(result.pattern.slowRate>0);
  const change=replay.base.meanWait-replay.optimized.meanWait;
  const percent=replay.base.meanWait?change/replay.base.meanWait*100:0;
  $('traffic-change').textContent=(change>=0?'−':'＋')+Math.abs(percent).toFixed(1)+'%';
  const validationChange=result.validation?.single?.meanWait-result.validation?.distributed?.meanWait;
  const validationEligible=result.validation?.distributed?.eligible===true;
  $('validation-change').textContent=Number.isFinite(validationChange)
    ?(validationEligible?'条件通過 ':'参考値（制約外） ')+(validationChange>=0?'−':'＋')+Math.abs(validationChange).toFixed(1)+' 秒/台'
    :'—';
  $('signal-config').textContent='青 '+replay.config.green.join('/')+'秒 ｜ 時差 '+replay.config.offset.join('/')+'秒';
}

function render(data) {
  snapshot=data;
  const exhibition=data.exhibition,latest=data.results.timeBudget,budgetMs=exhibition?.budgetMs??latest?.budgetMs??15000;
  $('ready-count').textContent=data.readyWorkers+' / '+data.expectedWorkers;
  $('cluster-state').classList.toggle('degraded',data.readyWorkers!==data.expectedWorkers);
  renderPatternButtons(data);
  renderPhase(exhibition,budgetMs);
  const single=runForCard('single',exhibition,latest),multi=runForCard('distributed',exhibition,latest);
  renderRunCard('single',single);renderRunCard('multi',multi);
  const multiplier=exhibition?.phase==='result'?exhibition.candidateMultiplier:latest?.candidateMultiplier;
  $('candidate-multiplier').textContent=Number.isFinite(multiplier)?multiplier.toFixed(1)+' 倍':'—';
  let events=[],history=[],counts={};
  if(exhibition&&(exhibition.phase==='single'||exhibition.phase==='distributed')) {
    events=exhibition.recentEvents??[];history=exhibition.bestHistory??[];counts=exhibition.taskCounts??{};
    $('race-title').textContent=exhibition.phase==='single'?'1台の計算タイムライン':'12台の並列タイムライン';
  } else {
    events=latest?.distributed?.traces??[];history=latest?.distributed?.bestHistory??[];counts=latest?.distributed?.taskCounts??{};
    $('race-title').textContent='直前の12台並列タイムライン';
  }
  renderRace(events,budgetMs,data.expectedWorkers);renderQuality(history,budgetMs);renderWorkers(data,counts);
  prepareReplay(latest);
  const messages=[...data.errors];
  if(data.readyWorkers!==data.expectedWorkers)messages.push((data.expectedWorkers-data.readyWorkers)+'台のワーカが応答していません');
  if(exhibition?.error)messages.push(exhibition.error);
  $('notice').hidden=!messages.length;$('notice').textContent=messages.join(' / ');
  $('updated').textContent='自動更新 '+new Date(data.generatedAt).toLocaleTimeString('ja-JP')+' · '+(latest?.source??'結果待ち');
}

async function refresh() {
  if(refreshing)return;refreshing=true;
  try {
    const response=await fetch('/api/dashboard',{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);
    render(await response.json());
  } catch(error) {
    $('notice').hidden=false;$('notice').textContent='表示データを更新できません: '+error.message;
  } finally {refreshing=false;}
}

function animate(now) {
  const delta=lastFrame?Math.min(.1,(now-lastFrame)/1000):0;lastFrame=now;
  if(replay) {
    replayElapsed=(replayElapsed+delta*6)%DURATION;
    const index=Math.min(replay.base.frames.length-1,Math.floor(replayElapsed/DT));
    const baseFrame=replay.base.frames[index],optimizedFrame=replay.optimized.frames[index];
    draw('base-canvas',baseFrame,baseline);draw('optimized-canvas',optimizedFrame,replay.config);
    $('replay-clock').textContent='シミュレーション '+Math.floor(replayElapsed)+' / '+DURATION+'秒 · 6倍速';
    $('base-wait').textContent=number(baseFrame.meanWait)+' 秒/台';$('optimized-wait').textContent=number(optimizedFrame.meanWait)+' 秒/台';
    $('base-arrived').textContent=baseFrame.arrived+'台';$('optimized-arrived').textContent=optimizedFrame.arrived+'台';
    $('base-remaining').textContent=baseFrame.remaining+'台';$('optimized-remaining').textContent=optimizedFrame.remaining+'台';
  } else {
    draw('base-canvas',null,baseline);draw('optimized-canvas',null,baseline);
  }
  if(snapshot)renderPhase(snapshot.exhibition,snapshot.exhibition?.budgetMs??snapshot.results.timeBudget?.budgetMs??15000);
  requestAnimationFrame(animate);
}

refresh();setInterval(refresh,1000);requestAnimationFrame(animate);
