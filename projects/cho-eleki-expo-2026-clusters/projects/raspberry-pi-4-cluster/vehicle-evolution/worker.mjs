import http from 'node:http';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {VERSION,DURATION,INSTABILITY_POLICY,simulate,validateGenome,validateSeed,COURSE_PROFILES,validateCourseProfile} from './physics.mjs';

export async function readJson(request) {
  const chunks=[];let bytes=0;
  for await(const chunk of request){bytes+=chunk.length;if(bytes>65536)throw Error('要求は64KiB以下にしてください');chunks.push(chunk);}
  return JSON.parse(Buffer.concat(chunks).toString());
}
export function send(response,status,body) {
  response.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store'});response.end(JSON.stringify(body));
}
export function createWorker({workerId=os.hostname(),simulateTask=simulate,log=console.error}={}) {
  const cache=new Map();
  const server=http.createServer(async(request,response)=>{
    if(request.method==='GET'&&request.url==='/health')return send(response,200,{status:'ok',workerId,version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,courseProfiles:COURSE_PROFILES});
    if(request.method!=='POST'||request.url!=='/evaluate')return send(response,404,{error:'not found'});
    let evaluating=false,task;
    try {
      task=await readJson(request);validateGenome(task.genome);validateSeed(task.seed);const courseProfile=task.courseProfile??'rolling-v1';validateCourseProfile(courseProfile);
      if(typeof task.runId!=='string'||!task.runId||task.runId.length>128||!Number.isInteger(task.id)||task.id<0||task.id>119)throw Error('評価IDが不正です');
      if(task.durationSeconds!==undefined&&task.durationSeconds!==DURATION)throw Error('評価時間が一致しません');
      const key=task.runId+':'+task.id,signature=JSON.stringify([task.seed,task.genome,courseProfile,DURATION]),old=cache.get(key);
      if(old&&old.signature!==signature)return send(response,409,{error:'同じ評価IDに異なる遺伝子・seed・コースが指定されました'});
      evaluating=true;
      const result=old?.result??simulateTask(task.genome,{seed:task.seed,courseProfile});
      if(!old&&result.instability)log(JSON.stringify({event:'vehicle-instability',workerId,version:VERSION,durationSeconds:DURATION,runId:task.runId,candidateId:task.id,seed:task.seed,courseProfile,genome:task.genome,distance:result.distance,elapsed:result.elapsed,instability:result.instability,node:process.version,arch:process.arch}));
      if(!old){if(cache.size>=512)cache.delete(cache.keys().next().value);cache.set(key,{signature,result});}
      send(response,200,{version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,workerId,runId:task.runId,id:task.id,courseProfile,result,cached:Boolean(old)});
    }catch(error){if(evaluating)log(JSON.stringify({event:'vehicle-evaluation-error',workerId,runId:task.runId,candidateId:task.id,seed:task.seed,genome:task.genome,error:error.message,node:process.version,arch:process.arch}));send(response,evaluating?500:400,{error:error.message,code:evaluating?'evaluation-error':'invalid-request'});}
  });
  server.requestTimeout=10000;server.headersTimeout=10000;return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const value=(name,fallback)=>{const i=process.argv.indexOf(name);return i<0?fallback:process.argv[i+1];};
  const port=Number(value('--port','8790')),host=value('--host','127.0.0.1');
  if(!Number.isInteger(port)||port<1||port>65535)throw Error('portが不正です');
  const server=createWorker({workerId:value('--id',os.hostname())});
  server.on('error',e=>{console.error('workerを起動できません: '+e.message);process.exitCode=1;});
  server.listen(port,host,()=>console.log('車体評価worker http://'+host+':'+port));
  for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{server.close();server.closeAllConnections();});
}
