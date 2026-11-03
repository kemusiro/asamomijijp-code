import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {validateGenome,validateSeed,validateCourseProfile} from './physics.mjs';
const allowed=new Set(['--checkpoint','--physics','--repeats','--output']),options={};
for(let i=2;i<process.argv.length;i+=2){if(!allowed.has(process.argv[i])||!process.argv[i+1])throw Error('引数を確認してください');options[process.argv[i]]=process.argv[i+1];}
if(!options['--output'])throw Error('--outputに新しい出力先を指定してください');
const repeats=Number(options['--repeats']??3);if(!Number.isInteger(repeats)||repeats<1||repeats>100)throw Error('repeatsは1〜100です');
const file=options['--checkpoint']?pathToFileURL(path.resolve(options['--checkpoint'])):new URL('./instability-fixture.json',import.meta.url),input=JSON.parse(await fs.readFile(file,'utf8'));
if(!Array.isArray(input.population)||input.population.length<1||input.population.length>120)throw Error('populationは1〜120台です');
input.population.forEach(validateGenome);const seed=input.courseSeed??input.seed,courseProfile=input.courseProfile??'rolling-v1';validateSeed(seed);validateCourseProfile(courseProfile);
const moduleUrl=options['--physics']?pathToFileURL(path.resolve(options['--physics'])):new URL('./physics.mjs',import.meta.url),physics=await import(moduleUrl.href),output=path.resolve(options['--output']);
const reservation=await fs.open(output,'wx');await reservation.close();
const data={startedAt:new Date().toISOString(),node:process.version,v8:process.versions.v8,platform:process.platform,arch:process.arch,physicsSha256:createHash('sha256').update(await fs.readFile(moduleUrl)).digest('hex'),version:physics.VERSION,durationSeconds:physics.DURATION,instabilityPolicy:physics.INSTABILITY_POLICY??null,sourceVersion:input.sourceVersion??input.version,sourceDurationSeconds:input.sourceDurationSeconds??input.durationSeconds??16,seed,courseProfile,repeats,populationSize:input.population.length,completed:0,counts:{},errors:[],unstable:[],replayChecks:[],status:'running'};
const persist=async()=>{await fs.writeFile(output+'.tmp',JSON.stringify(data,null,2)+'\n');await fs.rename(output+'.tmp',output);};
let expected;
for(let repeat=0;repeat<repeats;repeat++) {
  for(let id=0;id<input.population.length;id++) {
    const genome=input.population[id];
    try {
      const r=physics.simulate(genome,{seed,courseProfile});physics.validateResult?.(r);data.counts[r.reason]=(data.counts[r.reason]??0)+1;
      if(r.reason==='unstable'){data.unstable.push({repeat,candidateId:id,genome,...r});expected={genome,result:r};}
    }catch(error){data.errors.push({repeat,candidateId:id,genome,error:error.message});}
    data.completed++;
  }
  await persist();console.log(JSON.stringify({repeat:repeat+1,completed:data.completed,counts:data.counts,errors:data.errors.length}));
}
if(expected) {
  const replay=physics.simulate(expected.genome,{seed,courseProfile,frames:true}),{frames,...result}=replay;
  const finite=frames.every(f=>[...f.body,...f.wheels.flat()].every(Number.isFinite)),sameResult=JSON.stringify(result)===JSON.stringify(expected.result),lastTimeMatches=frames.at(-1).t===replay.elapsed;
  data.replayChecks.push({finite,sameResult,lastTimeMatches,distance:replay.distance,elapsed:replay.elapsed,reason:replay.reason,frames:frames.length});
  if(!finite||!sameResult||!lastTimeMatches)data.errors.push({error:'再生と評価が一致しません'});
}
data.status=data.errors.length?'errors':'complete';data.finishedAt=new Date().toISOString();await persist();
if(data.errors.length)process.exitCode=1;
console.log(JSON.stringify({status:data.status,completed:data.completed,counts:data.counts,errors:data.errors.length,replayChecks:data.replayChecks}));
