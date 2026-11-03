import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
import {Worker} from 'node:worker_threads';
import * as original from './physics.mjs';
import {initialPopulation} from './evolution.mjs';
import {obstaclePoints,writeVariant,evaluateTrial,describe,summarize,hash,TUNING_VERSION} from './terrain-tuning.mjs';
const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'terrain-tuning-test-'));
const execute=args=>new Promise(resolve=>{const child=spawn(process.execPath,[new URL('./terrain-tuning-benchmark.mjs',import.meta.url).pathname,...args]);let out='',err='';child.stdout.on('data',s=>out+=s);child.stderr.on('data',s=>err+=s);child.on('exit',code=>resolve({code,out,err}));});
try {
  const before=await fs.readFile(new URL('./physics.mjs',import.meta.url),'utf8');
  const baseline=await writeVariant(temporary,{id:'base',angle:45,depth:6},{durationSeconds:30}),physics=await import(pathToFileURL(baseline.path).href);
  for(const seed of [0,2026,2147483647])assert.deepEqual(physics.makeCourse(seed,'obstacles-v1'),original.makeCourse(seed,'obstacles-v1'));
  for(const genome of initialPopulation(2026,6,{strategy:'profile-v2'}))assert.deepEqual(physics.simulate(genome,{seed:2026,courseProfile:'obstacles-v1'}),original.simulate(genome,{seed:2026,courseProfile:'obstacles-v1'}));
  assert.equal(physics.DURATION,30);assert.equal(physics.VERSION,TUNING_VERSION);
  const short=await writeVariant(temporary,{id:'short',angle:45,depth:6},{durationSeconds:16}),legacy=await import(pathToFileURL(short.path).href);
  assert.equal(legacy.DURATION,16);assert.equal(short.durationSeconds,16);assert.equal(short.sourceDurationSeconds,30);
  const longRunner=initialPopulation(2026,36,{strategy:'profile-v2'}).find(g=>physics.simulate(g,{courseProfile:'obstacles-v1'}).elapsed>16);
  assert.ok(longRunner,'16秒を超える比較用の車体');
  assert.equal(legacy.simulate(longRunner,{courseProfile:'obstacles-v1'}).elapsed,16);
  assert.notDeepEqual(legacy.simulate(longRunner,{courseProfile:'obstacles-v1'}),physics.simulate(longRunner,{courseProfile:'obstacles-v1'}));
  await assert.rejects(writeVariant(temporary,{id:'missing',angle:45,depth:6}),/duration-seconds/);
  const mismatched=new Worker(new URL('./terrain-tuning-worker.mjs',import.meta.url),{workerData:{variants:{short:short.path},durationSeconds:30}});
  try {
    const response=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('時間不一致の検査が完了しません')),5000);
      mismatched.once('message',v=>{clearTimeout(timer);resolve(v);});mismatched.once('error',e=>{clearTimeout(timer);reject(e);});
      mismatched.postMessage({id:'mismatched',condition:'short',seed:2026,generations:1});
    });
    assert.match(response.error,/物理モデル・時間/);assert.equal(response.result,undefined);
  }finally{await mismatched.terminate();}
  const points=obstaclePoints(55,8),height=x=>points.find(p=>p[0]===x)[1];
  assert.ok(Math.abs(Math.atan((height(27)-height(24))/3)*180/Math.PI-55)<1e-10);assert.equal(height(48),-8);assert.equal(height(51),-8);assert.equal(height(57),0);
  assert.throws(()=>obstaclePoints(61,8));assert.throws(()=>obstaclePoints(50,5));
  const trial=evaluateTrial(physics,{seed:2026,generations:3,populationSize:6});
  assert.equal(trial.status,'complete');assert.equal(trial.final.count,6);assert.equal(trial.history.length,3);
  assert.equal(trial.final.passed,trial.finalDistances.filter(d=>d>=57).length);
  assert.deepEqual(trial,evaluateTrial(physics,{seed:2026,generations:3,populationSize:6}));
  const failed=evaluateTrial({simulate(){throw Error('synthetic failure');}},{seed:2026,generations:3});
  assert.equal(failed.status,'error');assert.equal(summarize([trial,failed]).failedTrials,1);assert.equal(summarize([trial,failed]).count,6);
  const rows=[{distance:56.99,reason:'time'},{distance:57,reason:'fell'},{distance:80,reason:'stalled'}];
  assert.equal(describe(rows).passed,2);assert.equal(describe(rows).reasons.fell,1);
  assert.equal(hash(await fs.readFile(new URL('./physics.mjs',import.meta.url),'utf8')),hash(before));
  console.log('PASS: 現行点列/評価との完全一致・角度/深さ・固定乱数の決定性・最終評価世代・57m基準・失敗の分離・本番ソース不変');
  const common=['--seeds','2026,2027','--angles','50','--depths','7','--generations','2','--baseline','false'];
  for(const duration of [16,30]){
    for(const workers of [1,2]){
      const r=await execute(['--duration-seconds',String(duration),'--output',path.join(temporary,`d${duration}-w${workers}.json`),'--workers',String(workers),...common]);
      assert.equal(r.code,0,r.err);
    }
    const a=JSON.parse(await fs.readFile(path.join(temporary,`d${duration}-w1.json`))),b=JSON.parse(await fs.readFile(path.join(temporary,`d${duration}-w2.json`)));
    assert.deepEqual(a.trials,b.trials);assert.deepEqual(a.summary,b.summary);
    assert.equal(a.modelVersion,TUNING_VERSION);assert.equal(a.sourceModelVersion,original.VERSION);assert.equal(a.sourceDurationSeconds,30);assert.equal(a.durationSeconds,duration);
    assert.match(a.successDefinition,new RegExp(duration+'秒'));assert.equal(a.evolutionSha256.length,64);assert.equal(a.engineSha256.length,64);
    assert.ok(a.conditions.every(c=>c.durationSeconds===duration&&c.modelVersion===TUNING_VERSION));
    assert.ok(a.trials.every(t=>t.durationSeconds===duration&&t.modelVersion===TUNING_VERSION&&t.champion.elapsed<=duration&&t.finalElapsedSeconds.every(v=>v<=duration)));
  }
  for(const args of [[],['--duration-seconds','15'],['--duration-seconds','0'],['--duration-seconds','NaN']]){
    const output=path.join(temporary,'invalid-'+args.join('-')+'.json');
    const r=await execute(['--output',output,...common,...args]);
    assert.notEqual(r.code,0);assert.match(r.err,/duration-seconds/);await assert.rejects(fs.stat(output),{code:'ENOENT'});
  }
  const sentinel=path.join(temporary,'existing.json');await fs.writeFile(sentinel,'keep');
  assert.notEqual((await execute(['--duration-seconds','16','--output',sentinel,...common])).code,0);assert.equal(await fs.readFile(sentinel,'utf8'),'keep');
  assert.equal(hash(await fs.readFile(new URL('./physics.mjs',import.meta.url),'utf8')),hash(before));
  console.log('PASS: 16/30秒の実評価・時間指定必須/不正値拒否・版/時間メタデータ・両時間の1/2worker一致・本番ソース不変・既存結果の上書き拒否');
}finally{await fs.rm(temporary,{recursive:true,force:true});}
