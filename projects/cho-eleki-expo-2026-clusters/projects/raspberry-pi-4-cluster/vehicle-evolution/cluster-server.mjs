import {resolve4} from 'node:dns/promises';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {VERSION,DURATION,INSTABILITY_POLICY,COURSE_PROFILES} from './physics.mjs';

// Pod IPは再作成で変わるため、起動ごとにheadless Serviceから取り直す。
export async function discoverWorkers({service,expected=12,port=8790,waitMs=90000,lookup=resolve4,request=fetch,signal}={}) {
  if(!service||!/^[a-z0-9.-]+$/.test(service)||!Number.isInteger(expected)||expected<1||expected>12)throw Error('worker Serviceまたは期待台数が不正です');
  const deadline=Date.now()+waitMs;let last='worker未検出';
  while(Date.now()<deadline) {
    signal?.throwIfAborted();
    try {
      const ips=[...new Set(await lookup(service))].sort();
      if(ips.length!==expected)throw Error('worker数 '+ips.length+'/'+expected);
      const workers=await Promise.all(ips.map(async ip=>{
        const url='http://'+ip+':'+port,response=await request(url+'/health',{signal:AbortSignal.any([AbortSignal.timeout(5000),...(signal?[signal]:[])])}),body=await response.json();
        if(!response.ok||body.status!=='ok'||body.version!==VERSION||body.durationSeconds!==DURATION||body.instabilityPolicy!==INSTABILITY_POLICY||typeof body.workerId!=='string'||!body.workerId||!COURSE_PROFILES.every(p=>body.courseProfiles?.includes(p)))throw Error(ip+'のhealth不正');
        return {id:body.workerId,url};
      }));
      if(new Set(workers.map(w=>w.id)).size!==expected)throw Error('worker ID重複');
      return workers.sort((a,b)=>a.id.localeCompare(b.id)).map(w=>w.url);
    }catch(error){last=error.message;}
    await new Promise((resolve,reject)=>{
      const done=()=>{clearTimeout(timer);signal?.removeEventListener('abort',abort);resolve();};
      const abort=()=>{clearTimeout(timer);reject(signal.reason);};
      const timer=setTimeout(done,Math.min(2000,Math.max(0,deadline-Date.now())));signal?.addEventListener('abort',abort,{once:true});
    });
  }
  throw Error('workerを確認できません: '+last+'。workerを復旧してcoordinatorを再起動してください');
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const abort=new AbortController();let child;
  for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{abort.abort(Error('停止要求'));child?.kill(signal);});
  try {
    const urls=await discoverWorkers({service:process.env.WORKER_SERVICE,expected:Number(process.env.EXPECTED_WORKERS??12),signal:abort.signal});
    console.log('接続worker: '+urls.join(','));
    child=spawn(process.execPath,[new URL('./server.mjs',import.meta.url).pathname,'--worker-urls',urls.join(','),...process.argv.slice(2)],{stdio:'inherit'});
    child.once('error',error=>{console.error(error.message);process.exitCode=1;});
    child.once('exit',(code,signal)=>{process.exitCode=code??(signal==='SIGTERM'||signal==='SIGINT'?0:1);});
  }catch(error){console.error('クラスタ表示を起動できません: '+error.message);process.exitCode=abort.signal.aborted?0:1;}
}
