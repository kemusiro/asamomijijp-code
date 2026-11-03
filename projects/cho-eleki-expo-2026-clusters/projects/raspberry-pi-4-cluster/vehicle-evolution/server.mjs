import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createPool} from './pool.mjs';
import {EvolutionController} from './controller.mjs';
import {VERSION,DURATION,INSTABILITY_POLICY,validateCourseProfile} from './physics.mjs';
import {STRATEGIES} from './evolution.mjs';
import {readJson,send} from './worker.mjs';

const ROOT=path.dirname(fileURLToPath(import.meta.url));
const assets=new Map([['/',['index.html','text/html']],['/app.mjs',['app.mjs','text/javascript']],['/style.css',['style.css','text/css']],['/draw.mjs',['draw.mjs','text/javascript']],['/physics.mjs',['physics.mjs','text/javascript']],['/vendor/planck.mjs',['vendor/planck.mjs','text/javascript']],['/vendor/PLANCK-LICENSE.txt',['vendor/PLANCK-LICENSE.txt','text/plain']]]);
export function createServer(controller) {
  const server=http.createServer(async(request,response)=>{
    try {
      const url=new URL(request.url,'http://localhost');
      if(request.method==='GET'&&url.pathname==='/health')return send(response,200,{status:'ok',demo:'vehicle-evolution',version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY});
      if(request.method==='GET'&&url.pathname==='/api/state')return send(response,200,controller.snapshot());
      if(request.method==='GET'&&url.pathname==='/api/replay') {
        if(url.searchParams.has('car')) {
          if(url.searchParams.get('experiment')!==controller.comparison.id)return send(response,409,{error:'再計算が始まりました。車体一覧から選び直してください'});
          return send(response,200,controller.replayForCar(url.searchParams.get('car')));
        }
        if(!url.searchParams.has('generation'))return send(response,200,controller.replay);
        if(url.searchParams.get('session')!==controller.session)return send(response,409,{error:'探索が切り替わりました。新しい系譜から選び直してください'});
        const raw=url.searchParams.get('generation');
        if(!raw?.trim())throw Error('世代を指定してください');
        return send(response,200,controller.replayForGeneration(Number(raw)));
      }
      if(request.method==='POST'&&url.pathname==='/api/control') {
        const origin=request.headers.origin;if(origin&&new URL(origin).host!==request.headers.host)return send(response,403,{error:'同じ画面から操作してください'});
        const body=await readJson(request);controller.control(body.action,body.seed,body);return send(response,200,{accepted:true});
      }
      if(request.method!=='GET')return send(response,405,{error:'method not allowed'});
      const asset=assets.get(url.pathname);if(!asset)return send(response,404,{error:'not found'});
      const bytes=await fs.readFile(path.join(ROOT,asset[0]));response.writeHead(200,{'content-type':asset[1]+'; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'});response.end(bytes);
    }catch(error){send(response,400,{error:error.message});}
  });
  server.requestTimeout=10000;server.headersTimeout=10000;return server;
}
export function parseOptions(args) {
  const allowed=new Set(['--port','--host','--workers','--worker-urls','--seed','--course-seed','--population-seed','--runs','--population','--generations','--state-file','--timeout-ms','--generation-delay-ms','--strategy','--course-profile']);const values={};
  for(let i=0;i<args.length;i+=2){if(!allowed.has(args[i])||!args[i+1]||args[i+1].startsWith('--'))throw Error('引数を確認してください: '+args[i]);values[args[i]]=args[i+1];}
  const integer=(key,fallback,min,max)=>{const n=Number(values[key]??fallback);if(!Number.isInteger(n)||n<min||n>max)throw Error(key+'は'+min+'～'+max+'の整数です');return n;};
  const urls=(values['--worker-urls']??'').split(',').filter(Boolean);
  if(urls.length&&values['--workers'])throw Error('--workersと--worker-urlsは同時指定できません');
  if(values['--seed']&&(values['--course-seed']||values['--population-seed']))throw Error('--seedと分離したseedは同時指定できません');
  const strategy=values['--strategy']??'profile-v2';if(!STRATEGIES.includes(strategy))throw Error('--strategyは'+STRATEGIES.join(' / ')+'です');
  const courseProfile=values['--course-profile']??'rolling-v1';validateCourseProfile(courseProfile);
  return {strategy,courseProfile,port:integer('--port',8090,1,65535),host:values['--host']??'127.0.0.1',workers:integer('--workers',4,1,12),urls,
    seed:integer('--seed',2026,0,2147483647),courseSeed:integer('--course-seed',values['--seed']??2026,0,2147483647),populationSeed:integer('--population-seed',values['--seed']??2026,0,2147483647),runs:integer('--runs',0,0,8),populationSize:integer('--population',36,6,120),generations:integer('--generations',20,1,1000),
    delayMs:integer('--generation-delay-ms',100,0,10000),timeoutMs:integer('--timeout-ms',15000,100,120000),stateFile:path.resolve(values['--state-file']??path.join(ROOT,'output','state.json'))};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  let pool,controller,server;
  try {
    const options=parseOptions(process.argv.slice(2));pool=await createPool(options);controller=new EvolutionController({...options,pool});await controller.restore();server=createServer(controller);
    await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(options.port,options.host,resolve);});
    console.log('車体進化 http://'+options.host+':'+options.port+' · '+(options.urls.length?'HTTP worker':'ローカル')+' '+pool.ids.length+'並列');controller.schedule();
    let stopping=false;
    const close=async()=>{if(stopping)return;stopping=true;console.log('探索を終了します。完了済み世代の保存状態は保持します。');server.close();server.closeAllConnections();await controller.close();};
    for(const signal of ['SIGINT','SIGTERM'])process.on(signal,close);
  }catch(error){console.error('車体進化を起動できません: '+error.message);await pool?.close();process.exitCode=1;}
}
