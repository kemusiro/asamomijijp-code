import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {Worker} from 'node:worker_threads';
import {VERSION,DURATION} from './physics.mjs';
import {writeVariant,summarize,TARGET_DISTANCE,TUNING_VERSION,validateDuration,hash} from './terrain-tuning.mjs';
const allowed=new Set(['--output','--workers','--seeds','--angles','--depths','--generations','--timeout-ms','--baseline','--duration-seconds']),options={};
for(let i=2;i<process.argv.length;i+=2){if(!allowed.has(process.argv[i])||!process.argv[i+1])throw Error('引数を確認してください');options[process.argv[i]]=process.argv[i+1];}
if(!options['--output'])throw Error('--outputに新しい保存先を指定してください');
const durationSeconds=validateDuration(Number(options['--duration-seconds']));
const list=(key,fallback)=>{const a=(options[key]??fallback).split(',').map(Number);if(!a.length||a.some(n=>!Number.isFinite(n))||new Set(a).size!==a.length)throw Error(key+'の値が不正です');return a;};
const seeds=list('--seeds','2026,2027,2028,2029,2030,2031'),angles=list('--angles','50,52.5,55'),depths=list('--depths','7,7.5,8');
const workers=Number(options['--workers']??4),generations=Number(options['--generations']??20),timeoutMs=Number(options['--timeout-ms']??120000);
if(seeds.length>24||seeds.some(s=>!Number.isInteger(s)||s<0||s>2147483647)||angles.length*depths.length>50||!Number.isInteger(workers)||workers<1||workers>8||!Number.isInteger(generations)||generations<1||generations>1000||!Number.isFinite(timeoutMs)||timeoutMs<1000)throw Error('seed・条件数・workers・世代数・timeoutを確認してください');
if(options['--baseline']&&!['true','false'].includes(options['--baseline']))throw Error('--baselineはtrueまたはfalseです');
const conditions=angles.flatMap(angle=>depths.map(depth=>({id:'a'+angle+'-d'+depth,angle,depth})));
if(options['--baseline']!=='false'&&!conditions.some(c=>c.angle===45&&c.depth===6))conditions.unshift({id:'a45-d6',angle:45,depth:6});
const output=path.resolve(options['--output']),reservation=await fs.open(output,'wx');await reservation.close();
const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'vehicle-terrain-tuning-')),pool=[];let writeQueue=Promise.resolve();
const data={startedAt:new Date().toISOString(),node:process.version,platform:process.platform,arch:process.arch,modelVersion:TUNING_VERSION,sourceModelVersion:VERSION,sourceDurationSeconds:DURATION,durationSeconds,
  evolutionSha256:hash(await fs.readFile(new URL('./evolution.mjs',import.meta.url),'utf8')),
  engineSha256:hash(await fs.readFile(new URL('./vendor/planck.mjs',import.meta.url),'utf8')),
  strategy:'profile-v2',courseSeed:2026,populationSize:36,generations,workers,seeds,targetDistance:TARGET_DISTANCE,targetPassRate:.3,
  successDefinition:'最終評価世代の車体中心の最大到達距離57m以上。'+durationSeconds+'秒終了時の生存率とは異なる。',conditions:[],trials:[],status:'running'};
const persist=async()=>{await fs.writeFile(output+'.tmp',JSON.stringify(data,null,2)+'\n');await fs.rename(output+'.tmp',output);};
try {
  const variants={};
  for(const condition of conditions){const meta=await writeVariant(temporary,condition,{durationSeconds});variants[condition.id]=meta.path;const {path:_,...metadata}=meta;data.conditions.push({...condition,...metadata});}
  const tasks=conditions.flatMap(c=>seeds.map(seed=>({id:c.id+':'+seed,condition:c.id,seed,generations})));let next=0,finished=0;
  await Promise.all(Array.from({length:Math.min(workers,tasks.length)},async()=>{
    const worker=new Worker(new URL('./terrain-tuning-worker.mjs',import.meta.url),{workerData:{variants,durationSeconds}});pool.push(worker);
    while(next<tasks.length){
      const task=tasks[next++];
      const result=await new Promise((resolve,reject)=>{
        const done=()=>{clearTimeout(timer);worker.off('message',message);worker.off('error',error);worker.off('exit',exit);};
        const message=body=>{done();if(body.id!==task.id||body.error)reject(Error(body.error??'trial IDが一致しません'));else resolve(body.result);};
        const error=e=>{done();reject(e);},exit=code=>{done();reject(Error('worker終了: '+code));};
        const timer=setTimeout(()=>{done();reject(Error('trial timeout: '+task.id));},timeoutMs);
        worker.once('message',message);worker.once('error',error);worker.once('exit',exit);worker.postMessage(task);
      });
      data.trials.push({condition:task.condition,...result});finished++;
      console.log(JSON.stringify({finished,total:tasks.length,condition:task.condition,seed:task.seed,status:result.status,passed:result.final?.passed,count:result.final?.count,error:result.error}));
      // 書込は全workerで直列化し、一時ファイル同士の競合を防ぐ。
      writeQueue=writeQueue.then(persist);
      await writeQueue;
    }
  }));
  data.summary=conditions.map(c=>({...c,...summarize(data.trials.filter(t=>t.condition===c.id))}));
  data.status=data.trials.some(t=>t.status!=='complete')?'trial-errors':'complete';
  if(data.status!=='complete')process.exitCode=1;
}catch(error){data.status='error';data.error=error.stack??error.message;process.exitCode=1;console.error(data.error);}
finally{await Promise.all(pool.map(w=>w.terminate()));await writeQueue.catch(()=>{});data.finishedAt=new Date().toISOString();data.trials.sort((a,b)=>a.condition.localeCompare(b.condition)||a.seed-b.seed);await persist();await fs.rm(temporary,{recursive:true,force:true});}
