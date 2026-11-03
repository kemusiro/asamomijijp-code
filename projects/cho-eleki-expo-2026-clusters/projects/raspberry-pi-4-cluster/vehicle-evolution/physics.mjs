import {World,Vec2,Edge,Polygon,Circle,WheelJoint} from './vendor/planck.mjs';

export const VERSION='vehicle-2';
export const INSTABILITY_POLICY='finite-prefix-v1';
export const COURSE_PROFILES=['rolling-v1','obstacles-v1','obstacles-55-7p5-v1'];
export const COURSE_LABELS={'rolling-v1':'起伏コース','obstacles-v1':'急坂・深い谷コース','obstacles-55-7p5-v1':'台地55°・谷7.5mコース'};
export const DT=1/60, DURATION=30, FINISH=160, FRAME_STEP=6;
// 8方向の車体半径、後/前輪の半径、車軸の左右位置、車軸高さ、ばね周波数。
export const BOUNDS=[...Array.from({length:8},()=>[.3,1.65]),[.18,.95],[.18,.95],[.65,1.45],[-.8,-.25],[2,7]];
export const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
export function random(seed) {
  let state=seed>>>0;
  const next=()=>{state=(state+0x6d2b79f5)>>>0;let t=state;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
  next.state=()=>state;return next;
}
export function validateGenome(genome) {
  if(!Array.isArray(genome)||genome.length!==BOUNDS.length||genome.some((v,i)=>!Number.isFinite(v)||v<BOUNDS[i][0]||v>BOUNDS[i][1]))throw Error('車体遺伝子が範囲外です');
}
export function validateSeed(seed) {
  if(!Number.isInteger(seed)||seed<0||seed>2147483647)throw Error('seedは0～2147483647の整数で指定してください');
}
export function bodyVertices(genome) {
  return genome.slice(0,8).map((r,i)=>[r*Math.cos(i*Math.PI/4),r*Math.sin(i*Math.PI/4)]);
}
export function validateCourseProfile(profile) {
  if(!COURSE_PROFILES.includes(profile))throw Error('コース種別が不正です');
}
export function makeCourse(seed=2026,profile='rolling-v1') {
  validateCourseProfile(profile);
  validateSeed(seed);const rng=random(seed),points=[[-8,0],[0,0],[6,0]];
  for(let x=9;x<=FINISH+12;x+=3) {
    const ramp=Math.min(1,(x-6)/28);
    const y=ramp*(3.1*Math.sin(x*.18)+1.4*Math.sin(x*.53)+(rng()-.5)*1.6);
    points.push([x,y]);
  }
  if(profile==='obstacles-v1') {
    // 24–39m: 高さ4.5mの台地、42–57m: 深さ6mの窪地。最大勾配45度。
    // seedの起伏を両端でつなぎ、底も含め連続する地面として評価する。
    const heights=new Map([[21,-.5],[24,0],[27,3],[30,4.5],[33,4.5],[36,1.5],[39,0],[42,0],[45,-3],[48,-6],[51,-6],[54,-3],[57,0],[60,0]]);
    for(const point of points)if(heights.has(point[0]))point[1]=heights.get(point[0]);
  }
  if(profile==='obstacles-55-7p5-v1') {
    // #141の測定と同じ点列。台地の最大勾配55度、谷の斜面は約51.34度。
    const slope=Math.tan(55*Math.PI/180);
    const tunedHeights=new Map([[21,-.5],[24,0],[27,3*slope],[30,4.5*slope],[33,4.5*slope],[36,1.5*slope],[39,0],[42,0],[45,-3.75],[48,-7.5],[51,-7.5],[54,-3.75],[57,0],[60,0]]);
    for(const point of points)if(tunedHeights.has(point[0]))point[1]=tunedHeights.get(point[0]);
  }
  return points;
}
export function validateInstability(value,elapsed) {
  if(!value||value.policy!==INSTABILITY_POLICY||!['non-finite','height-limit','speed-limit'].includes(value.code)||!['chassis','rear-wheel','front-wheel'].includes(value.body)||typeof value.component!=='string'||value.component.length>32||typeof value.value!=='string'||value.value.length>32||!Number.isFinite(value.detectedAt)||value.detectedAt<=elapsed||value.detectedAt>DURATION)throw Error('発散診断が不正です');
}
export function validateResult(result) {
  if(!Number.isFinite(result?.score)||result.score<0||result.score>FINISH+DURATION*.1||!Number.isFinite(result.distance)||result.distance<0||result.distance>FINISH||!Number.isFinite(result.elapsed)||result.elapsed<0||result.elapsed>DURATION||!['time','finish','stalled','fell','unstable'].includes(result.reason))throw Error('評価値が不正です');
  if(result.reason==='unstable') {validateInstability(result.instability,result.elapsed);if(result.score!==result.distance)throw Error('発散した車体の採点が不正です');}
  else if(result.instability!==undefined)throw Error('終了理由と発散診断が一致しません');
}
function instabilityFor(bodies,time) {
  for(let i=0;i<bodies.length;i++) {
    const b=bodies[i],p=b.getPosition(),v=b.getLinearVelocity();
    let component,value;
    if(!Number.isFinite(p.x)){component='position.x';value=p.x;}
    else if(!Number.isFinite(p.y)){component='position.y';value=p.y;}
    else if(!Number.isFinite(b.getAngle())){component='angle';value=b.getAngle();}
    else if(!Number.isFinite(v.x)){component='velocity.x';value=v.x;}
    else if(!Number.isFinite(v.y)){component='velocity.y';value=v.y;}
    else if(!Number.isFinite(b.getAngularVelocity())){component='angularVelocity';value=b.getAngularVelocity();}
    else continue;
    return {policy:INSTABILITY_POLICY,code:'non-finite',body:['chassis','rear-wheel','front-wheel'][i],component,value:String(value),detectedAt:time};
  }
  const p=bodies[0].getPosition(),v=bodies[0].getLinearVelocity();
  if(Math.abs(p.y)>40||Math.abs(v.x)>80) {
    const height=Math.abs(p.y)>40;
    return {policy:INSTABILITY_POLICY,code:height?'height-limit':'speed-limit',body:'chassis',component:height?'position.y':'velocity.x',value:String(height?p.y:v.x),detectedAt:time};
  }
  return null;
}
export function simulate(genome,{seed=2026,frames=false,motor=true,courseProfile='rolling-v1'}={}) {
  validateGenome(genome);validateSeed(seed);
  const course=makeCourse(seed,courseProfile),world=new World({gravity:Vec2(0,-9.8)}),ground=world.createBody();
  for(let i=1;i<course.length;i++)ground.createFixture(new Edge(Vec2(...course[i-1]),Vec2(...course[i])),{friction:.9});
  const chassis=world.createDynamicBody({position:Vec2(0,2),angularDamping:.15});
  const vertices=bodyVertices(genome);
  for(let i=0;i<8;i++)chassis.createFixture(new Polygon([Vec2(0,0),Vec2(...vertices[i]),Vec2(...vertices[(i+1)%8])]),{density:1,friction:.6,filterGroupIndex:-1});
  const wheels=[-1,1].map((side,i)=>{
    const anchor=chassis.getWorldPoint(Vec2(side*genome[10],genome[11]));
    const wheel=world.createDynamicBody({position:anchor});
    wheel.createFixture(new Circle(genome[8+i]),{density:1,friction:1.1,restitution:0,filterGroupIndex:-1});
    world.createJoint(new WheelJoint({enableMotor:motor,motorSpeed:-13,maxMotorTorque:24,frequencyHz:genome[12],dampingRatio:.75},chassis,wheel,anchor,Vec2(0,1)));
    return wheel;
  });
  let best=0,lastProgress=0,time=0,reason='time',instability=null,lastSafe=null;const recorded=[],bodies=[chassis,...wheels];
  const snapshot=()=>({t:time,body:[chassis.getPosition().x,chassis.getPosition().y,chassis.getAngle()],wheels:wheels.map(w=>[w.getPosition().x,w.getPosition().y,w.getAngle()]),distance:best});
  if(frames){lastSafe=snapshot();recorded.push(lastSafe);}
  for(let step=1;step<=Math.round(DURATION/DT);step++) {
    const previousTime=time;world.step(DT,8,3);time=step*DT;
    instability=instabilityFor(bodies,time);
    // 閾値を超えた状態は記録せず、直前の検査済み時刻・距離・姿勢を保持する。
    if(instability){reason='unstable';time=previousTime;break;}
    const p=chassis.getPosition();
    if(p.x>best+.05){best=Math.min(p.x,FINISH);lastProgress=time;}
    if(frames){lastSafe=snapshot();if(step%FRAME_STEP===0)recorded.push(lastSafe);}
    if(p.x>=FINISH){reason='finish';break;}
    if(time-lastProgress>4){reason='stalled';break;}
    if(p.y< -8){reason='fell';break;}
  }
  if(frames&&recorded.at(-1)?.t!==time)recorded.push(lastSafe);
  return {distance:best,elapsed:time,reason,score:best+(reason==='finish'?(DURATION-time)*.1:0),...(instability?{instability}:{}),...(frames?{frames:recorded}:{})};
}
