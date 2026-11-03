import {Worker} from 'node:worker_threads';
import {VERSION,DURATION,COURSE_PROFILES,validateCourseProfile,INSTABILITY_POLICY,validateResult} from './physics.mjs';

class LocalSlot {
  constructor(id,timeoutMs){this.id=id;this.timeoutMs=timeoutMs;this.spawn();}
  spawn(){this.worker=new Worker(new URL('./evaluator-thread.mjs',import.meta.url),{execArgv:[]});this.worker.on('error',()=>{});}
  async evaluate(task) {
    const worker=this.worker;
    return new Promise((resolve,reject)=>{
      const clean=()=>{clearTimeout(timer);worker.removeListener('message',message);worker.removeListener('error',failure);worker.removeListener('exit',exit);};
      const failure=error=>{clean();if(!this.closed)this.spawn();reject(error);};
      const exit=code=>failure(Error(this.id+'が終了しました（'+code+'）'));
      const message=data=>{clean();data.error?reject(Error(data.error)):resolve(data.result);};
      const timer=setTimeout(()=>{clean();worker.terminate();this.spawn();reject(Error(this.id+'の評価がタイムアウトしました'));},this.timeoutMs);
      worker.once('message',message);worker.once('error',failure);worker.once('exit',exit);worker.postMessage(task);
    });
  }
  async close(){this.closed=true;await this.worker.terminate();}
}

class RemoteSlot {
  constructor(url,id,timeoutMs){this.url=url;this.id=id;this.timeoutMs=timeoutMs;}
  async evaluate(task) {
    let last;
    for(let attempt=0;attempt<2;attempt++) {
      try {
        this.abort=new AbortController();
        const response=await fetch(this.url+'/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(task),signal:AbortSignal.any([this.abort.signal,AbortSignal.timeout(this.timeoutMs)])});
        const body=await response.json();if(!response.ok)throw Error(body.error??'HTTP '+response.status);
        if(body.workerId!==this.id||body.version!==VERSION||body.durationSeconds!==DURATION||body.runId!==task.runId||body.id!==task.id||body.courseProfile!==task.courseProfile||body.instabilityPolicy!==INSTABILITY_POLICY)throw Error('workerのバージョン・走行時間・発散処理・ID・コース種別が一致しません');
        return body.result;
      } catch(error){last=error;if(this.closed)throw error;}
    }
    throw Error(this.id+'の評価に失敗しました: '+last.message);
  }
  async close(){this.closed=true;this.abort?.abort();}
}

export async function createPool({workers=4,urls=[],timeoutMs=15000}={}) {
  if(!Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>120000)throw Error('評価timeoutは100～120000msです');
  let slots=[];
  if(urls.length) {
    if(urls.length>12||new Set(urls.map(u=>u.replace(/\/$/,''))).size!==urls.length)throw Error('worker URLは重複なしで最大12台です');
    for(const raw of urls) {
      const u=new URL(raw);if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.search||u.hash||u.pathname!=='/')throw Error('workerにはhttp(s)のルートURLを指定してください');
      const url=u.origin,response=await fetch(url+'/health',{signal:AbortSignal.timeout(timeoutMs)}),health=await response.json();
      if(!response.ok||health.version!==VERSION||health.durationSeconds!==DURATION||health.instabilityPolicy!==INSTABILITY_POLICY||typeof health.workerId!=='string'||!COURSE_PROFILES.every(p=>health.courseProfiles?.includes(p)))throw Error(url+'のworkerを確認できません。モデル版・走行時間・発散処理・コース対応・IDを確認してください');
      if(slots.some(s=>s.id===health.workerId))throw Error('workerIdが重複しています: '+health.workerId);
      slots.push(new RemoteSlot(url,health.workerId,timeoutMs));
    }
  } else {
    if(!Number.isInteger(workers)||workers<1||workers>12)throw Error('ローカル並列数は1～12です');
    slots=Array.from({length:workers},(_,i)=>new LocalSlot('CPU '+(i+1),timeoutMs));
  }
  let closed=false;
  return {
    mode:urls.length?'remote':'local',ids:slots.map(s=>s.id),
    async evaluate(population,seed,runId,onProgress=()=>{},{deadlineAt=Infinity,courseProfile='rolling-v1'}={}) {
      validateCourseProfile(courseProfile);const results=Array(population.length);let next=0;
      const outcomes=await Promise.allSettled(slots.map(async slot=>{
        while(next<population.length&&!closed&&performance.now()<deadlineAt) {
          const id=next++,genome=population[id];onProgress({workerId:slot.id,id,genome,status:'evaluating'});
          const started=performance.now(),result=await slot.evaluate({runId,id,genome,seed,courseProfile,durationSeconds:DURATION});
          try{validateResult(result);}catch(error){throw Error(slot.id+'の'+error.message);}
          results[id]=result;onProgress({workerId:slot.id,id,genome,status:'done',distance:result.distance,computeMs:performance.now()-started,...(result.instability?{instability:result.instability}:{})});
        }
      }));
      const failed=outcomes.find(r=>r.status==='rejected');if(failed)throw failed.reason;
      return results;
    },
    async close(){closed=true;await Promise.all(slots.map(s=>s.close()));},
  };
}
