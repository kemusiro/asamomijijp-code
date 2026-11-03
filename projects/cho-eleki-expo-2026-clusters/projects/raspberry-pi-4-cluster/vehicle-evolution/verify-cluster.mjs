import assert from 'node:assert/strict';
import {validateCourseProfile} from './physics.mjs';
import {createPool} from './pool.mjs';
import {initialPopulation} from './evolution.mjs';
import {randomUUID} from 'node:crypto';

const urls=(process.argv[2]??'').split(',').filter(Boolean);
if(urls.length<1||urls.length>12)throw Error('引数に1～12台のworker URLをカンマ区切りで指定してください');
const courseProfile=process.argv[3]??'rolling-v1';validateCourseProfile(courseProfile);
let local,remote;
try {
  local=await createPool({workers:1});remote=await createPool({urls});
  const population=initialPopulation(2026,36).slice(0,urls.length),used=new Set();
  const expected=await local.evaluate(population,2026,randomUUID(),()=>{},{courseProfile});
  const actual=await remote.evaluate(population,2026,randomUUID(),event=>{if(event.status==='done')used.add(event.workerId);},{courseProfile});
  for(let i=0;i<actual.length;i++)for(const key of ['distance','score','elapsed'])assert.ok(Math.abs(actual[i][key]-expected[i][key])<1e-8,'候補'+i+'の'+key+'が不一致');
  for(let i=0;i<actual.length;i++)assert.equal(actual[i].reason,expected[i].reason);
  assert.equal(used.size,urls.length,'一部のworkerが評価していません');
  console.log(JSON.stringify({status:'pass',node:process.version,arch:process.arch,seed:2026,courseProfile,workers:remote.ids,candidates:actual.length,tolerance:1e-8,results:actual},null,2));
}finally{await local?.close();await remote?.close();}
