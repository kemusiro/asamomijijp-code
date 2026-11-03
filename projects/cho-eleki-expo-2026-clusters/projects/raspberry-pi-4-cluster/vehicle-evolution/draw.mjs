import {bodyVertices,clamp,FINISH} from './physics.mjs';

const FONT_FAMILY='"Noto Sans CJK JP","Noto Sans JP","Hiragino Sans","Yu Gothic",system-ui,sans-serif';

export function frameAt(frames,time) {
  if(time>=frames.at(-1).t)return frames.at(-1);
  const i=Math.min(frames.length-2,Math.floor(time/.1)),a=frames[i],b=frames[i+1],mix=clamp((time-a.t)/(b.t-a.t),0,1);
  const lerp=(x,y)=>x.map((v,j)=>v+(y[j]-v)*mix);
  return {t:time,body:lerp(a.body,b.body),wheels:a.wheels.map((w,j)=>lerp(w,b.wheels[j]))};
}
function vehicle(ctx,genome,frame,project,scale,{color='#69e7ce',ghost=false}={}) {
  const [cx,cy,angle]=frame.body,cos=Math.cos(angle),sin=Math.sin(angle);
  const points=bodyVertices(genome).map(([x,y])=>project(cx+x*cos-y*sin,cy+x*sin+y*cos));
  ctx.save();ctx.globalAlpha=ghost?0.5:1;ctx.lineWidth=ghost?1.5:2;
  if(ghost)ctx.setLineDash([5,4]);
  ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fillStyle=ghost?'#8495a533':'#174c47';ctx.fill();ctx.strokeStyle=color;ctx.stroke();ctx.setLineDash([]);
  if(!ghost){const center=project(cx,cy);ctx.strokeStyle='#69e7ce38';ctx.lineWidth=1;for(const p of points){ctx.beginPath();ctx.moveTo(...center);ctx.lineTo(...p);ctx.stroke();}}
  frame.wheels.forEach(([x,y,a],i)=>{
    const [px,py]=project(x,y),r=genome[8+i]*scale;ctx.beginPath();ctx.arc(px,py,r,0,Math.PI*2);ctx.fillStyle=ghost?'#a7b6c733':'#0c1421';ctx.fill();ctx.strokeStyle=color;ctx.lineWidth=2;ctx.stroke();
    for(let j=0;j<3;j++){const t=a+j*Math.PI*2/3;ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(px+Math.cos(t)*r*.78,py-Math.sin(t)*r*.78);ctx.stroke();}
    ctx.beginPath();ctx.arc(px,py,2.5,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();
  });ctx.restore();
}
export function drawThumbnail(canvas,genome,color) {
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);if(!genome)return;
  const scale=Math.min(w/5,h/3.6),frame={body:[0,.3,0],wheels:[[-genome[10],.3+genome[11],0],[genome[10],.3+genome[11],0]]};
  vehicle(ctx,genome,frame,(x,y)=>[w/2+x*scale,h*.48-y*scale],scale,{color});
}
export function raceView(course,current,original,w,h) {
  const camera=Math.min(current[0],original[0])-7,viewWidth=Math.max(34,Math.abs(current[0]-original[0])+15);
  let scale=w/viewWidth,low,high;
  // 縦方向を収めると横に見える道も増えるため、範囲が安定するまで単調に縮小する。
  for(let i=0;i<=course.length;i++) {
    const heights=[current[1],original[1],...course.filter(([x])=>x>=camera-3&&x<=camera+w/scale+3).map(([,y])=>y)];
    low=Math.min(...heights)-2;high=Math.max(...heights)+3;
    const next=Math.min(scale,(h-100)/(high-low));
    if(next===scale)break;
    scale=next;
  }
  return {scale,span:w/scale,centerY:(low+high)/2,camera};
}
export function drawRace(canvas,replay,time) {
  // CSSの表示寸法で画角を決め、高密度画面でも線や文字の見かけの大きさを保つ。
  const w=canvas.clientWidth||canvas.width,h=canvas.clientHeight||canvas.height,ratio=Math.min(globalThis.devicePixelRatio||1,2);
  const width=Math.round(w*ratio),height=Math.round(h*ratio);
  if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
  const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#0c1421';ctx.fillRect(0,0,w,h);
  if(!replay)return;
  const current=frameAt(replay.champion.frames,time),original=frameAt(replay.initial.frames,time);
  const left=Math.min(current.body[0],original.body[0]);
  // 先の地面も画角に入れ、急坂と谷底が車の高さに隠れて切れないようにする。
  const camera=left-7;
  const {scale,span,centerY}=raceView(replay.course,current.body,original.body,w,h);
  const project=(x,y)=>[(x-camera)*scale,h*.47-(y-centerY)*scale];
  // 背景は装飾。接地線は評価に用いたコースの座標をそのまま描く。
  ctx.strokeStyle='#1b293a';ctx.lineWidth=1;
  for(let x=Math.floor(camera/5)*5;x<camera+span;x+=5){const px=project(x,0)[0];ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,h);ctx.stroke();}
  ctx.beginPath();replay.course.forEach(([x,y],i)=>i?ctx.lineTo(...project(x,y)):ctx.moveTo(...project(x,y)));ctx.lineTo(w,h);ctx.lineTo(0,h);ctx.closePath();
  const fill=ctx.createLinearGradient(0,h*.5,0,h);fill.addColorStop(0,'#c89f6530');fill.addColorStop(1,'#14202d');ctx.fillStyle=fill;ctx.fill();
  ctx.beginPath();replay.course.forEach(([x,y],i)=>i?ctx.lineTo(...project(x,y)):ctx.moveTo(...project(x,y)));ctx.strokeStyle='#d8b17b';ctx.lineWidth=2.5;ctx.stroke();
  ctx.font='12px '+FONT_FAMILY;ctx.fillStyle='#8192a6';
  for(let x=Math.max(0,Math.ceil(camera/10)*10);x<Math.min(FINISH+1,camera+span);x+=10){ctx.fillText(x+'m',project(x,0)[0]+3,h-14);}
  const compare=Boolean(replay.carId)||replay.champion.generation!==0;
  if(compare)vehicle(ctx,replay.initial.genome,original,project,scale,{color:'#a7b6c7',ghost:true});
  vehicle(ctx,replay.champion.genome,current,project,scale);
  for(const [frame,label,color,offset] of [[original,'初代','#a7b6c7',-38],[current,replay.carId?'選択車':'最良','#69e7ce',-60]]) {
    if(label==='初代'&&!compare)continue;
    const [x,y]=project(frame.body[0],frame.body[1]);ctx.font='600 13px '+FONT_FAMILY;ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText(label+' '+Math.max(0,frame.body[0]).toFixed(1)+' m',x,y+offset);
  }
  ctx.textAlign='left';
  if(['obstacles-v1','obstacles-55-7p5-v1'].includes(replay.courseProfile)) {
    ctx.font='12px '+FONT_FAMILY;ctx.fillStyle='#ffca7a';
    ctx.fillText(replay.courseProfile==='obstacles-55-7p5-v1'?'台地：55°  /  谷：深さ7.5m':'急坂：45°  /  谷：深さ6m',14,24);
  }
  return {current:clamp(current.body[0]/FINISH*100,0,100),original:clamp(original.body[0]/FINISH*100,0,100)};
}
