import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {VERSION,DURATION,INSTABILITY_POLICY,validateResult,random,simulate,makeCourse,validateGenome,validateSeed,validateCourseProfile} from './physics.mjs';
import {initialPopulation,nextPopulation,mutationPlan,STRATEGIES,initialProfileForSeed,evolutionSeedForTrial} from './evolution.mjs';

export const RECENT_RUN_LIMIT=6;
export const WORST_POLICY='nonzero-display-v1';
export const eligibleForWorst=car=>Number.isFinite(car.distance)&&car.distance>=0.05;
export const populationSeedForRun=(start,index)=>(start+index%2147483648)%2147483648;
export function comparisonOptions({courseSeed=2026,populationSeed=2026,runs=0,generations=20,strategy='profile-v2',courseProfile='rolling-v1'}={}) {
  validateSeed(courseSeed);validateSeed(populationSeed);validateCourseProfile(courseProfile);
  if(!Number.isInteger(runs)||runs<0||runs>8)throw Error('比較回数は0（連続）～8です');
  if(runs!==0&&populationSeed+runs-1>2147483647)throw Error('比較する初期集団seedが上限を超えます');
  if(!Number.isInteger(generations)||generations<1||generations>1000)throw Error('世代数は1～1000です');
  if(!STRATEGIES.includes(strategy))throw Error('探索方式が不正です');
  return {courseSeed,populationSeed,runs,generations,strategy,courseProfile};
}
const validateCar=car=>{validateGenome(car?.genome);if(!Number.isFinite(car.distance)||!Number.isFinite(car.score))throw Error('保存された車体の評価値が不正です');if(car.reason==='unstable')validateResult(car);};
const validateHistory=history=>{if(!Array.isArray(history)||history.some((v,i)=>v.generation!==i||!Number.isFinite(v.distance)||!Number.isFinite(v.mean)))throw Error('保存された世代履歴が不正です');};

function validateDiagnostics(value) {
  if(!value||!Number.isSafeInteger(value.unstableEvaluations)||value.unstableEvaluations<0||!Array.isArray(value.recent)||value.recent.length>6||value.recent.length>value.unstableEvaluations)throw Error('保存された発散集計が不正です');
  for(const row of value.recent) {
    validateGenome(row.genome);validateSeed(row.populationSeed);validateCourseProfile(row.courseProfile);validateSeed(row.courseSeed);
    if(typeof row.workerId!=='string'||row.workerId.length>128||!Number.isInteger(row.generation)||row.generation<0||row.generation>999||!Number.isInteger(row.candidateIndex)||row.candidateIndex<0||row.candidateIndex>119)throw Error('保存された発散候補が不正です');
    validateResult({score:row.distance,distance:row.distance,elapsed:row.elapsed,reason:'unstable',instability:row.instability});
  }
}
export class EvolutionController {
  constructor({pool,seed=2026,courseSeed=seed,populationSeed=seed,runs=1,populationSize=36,generations=20,strategy='profile-v2',courseProfile='rolling-v1',stateFile=null,delayMs=350,holdMs=8000}) {
    initialPopulation(populationSeed,populationSize);
    this.pool=pool;this.size=populationSize;this.file=stateFile;this.delay=delayMs;this.hold=holdMs;
    this.running=true;this.phase='starting';this.busy=false;this.stopped=false;this.error=null;
    this.startComparison(comparisonOptions({courseSeed,populationSeed,runs,generations,strategy,courseProfile}));
  }
  startComparison(options) {
    this.diagnostics={unstableEvaluations:0,recent:[]};this.courseProfile=options.courseProfile;this.strategy=options.strategy;this.ranking={best:[],worst:[],evaluated:0,coverage:'since-reset',worstPolicy:WORST_POLICY,worstSinceEvaluated:0};this.recordReplays=new Map();
    this.limit=options.generations;this.comparison={id:randomUUID(),startPopulationSeed:options.populationSeed,totalRuns:options.runs,runIndex:0,results:[]};
    this.resetModel(options.courseSeed,options.populationSeed);
  }
  resetModel(courseSeed,populationSeed=courseSeed) {
    this.seed=courseSeed;this.courseSeed=courseSeed;this.populationSeed=populationSeed;this.evolutionSeed=evolutionSeedForTrial(courseSeed,populationSeed,this.strategy);
    this.session=randomUUID();this.population=initialPopulation(populationSeed,this.size,{strategy:this.strategy});this.rng=random(this.evolutionSeed);
    this.generation=-1;this.stagnation=0;this.evaluated=0;this.evaluationMs=0;this.history=[];this.champion=null;this.initial=null;this.milestones=[];this.replay=null;this.selectedReplays=new Map();this.nextRun=false;this.completedCandidates=0;
    this.workers=this.pool.ids.map(id=>({id,status:'idle',count:0}));this.error=null;
  }
  buildReplay() {
    if(!this.champion)return;
    this.replay={version:VERSION,durationSeconds:DURATION,key:this.session+':'+this.champion.generation,seed:this.courseSeed,courseProfile:this.courseProfile,courseSeed:this.courseSeed,populationSeed:this.populationSeed,course:makeCourse(this.courseSeed,this.courseProfile),
      initial:{...this.initial,...simulate(this.initial.genome,{seed:this.courseSeed,courseProfile:this.courseProfile,frames:true})},
      champion:{...this.champion,...simulate(this.champion.genome,{seed:this.courseSeed,courseProfile:this.courseProfile,frames:true})}};
  }
  replayForGeneration(generation) {
    if(!Number.isInteger(generation)||generation<0)throw Error('世代は0以上の整数で指定してください');
    const car=[this.initial,...this.milestones,this.champion].find(car=>car?.generation===generation);
    if(!car||!this.replay)throw Error('現在の系譜にある世代を選んでください');
    if(generation===this.champion.generation)return this.replay;
    if(this.selectedReplays.has(generation))return this.selectedReplays.get(generation);
    const replay={version:VERSION,durationSeconds:DURATION,key:this.session+':'+generation,seed:this.courseSeed,courseProfile:this.courseProfile,courseSeed:this.courseSeed,populationSeed:this.populationSeed,course:this.replay.course,initial:this.replay.initial,
      champion:generation===0?this.replay.initial:{...car,...simulate(car.genome,{seed:this.courseSeed,courseProfile:this.courseProfile,frames:true})}};
    this.selectedReplays.set(generation,replay);
    while(this.selectedReplays.size>8)this.selectedReplays.delete(this.selectedReplays.keys().next().value);
    return replay;
  }
  updateRanking(cars) {
    const order=(a,b)=>{const x=a.genome.join(','),y=b.genome.join(',');return x<y?-1:x>y?1:0;};
    const unique=new Map([...this.ranking.best,...this.ranking.worst].map(car=>[car.genome.join(','),car]));
    for(const car of cars) {
      const key=car.genome.join(',');
      if(!unique.has(key))unique.set(key,{...car,id:this.comparison.id+':'+this.comparison.runIndex+':'+car.generation+':'+car.candidateIndex,
        runIndex:this.comparison.runIndex,populationSeed:this.populationSeed,courseSeed:this.courseSeed,courseProfile:this.courseProfile,baseline:structuredClone(this.initial)});
    }
    const entries=[...unique.values()];
    this.ranking.best=entries.slice().sort((a,b)=>b.score-a.score||order(a,b)).slice(0,3);
    this.ranking.worst=entries.filter(eligibleForWorst).sort((a,b)=>a.score-b.score||order(b,a)).slice(0,3);
    this.ranking.evaluated+=cars.length;
  }
  replayForCar(id) {
    if(typeof id!=='string'||!id.startsWith(this.comparison.id+':'))throw Error('再計算が始まりました。車体一覧から選び直してください');
    if(this.recordReplays.has(id)){const r=this.recordReplays.get(id);this.recordReplays.delete(id);this.recordReplays.set(id,r);return r;}
    const car=[...this.ranking.best,...this.ranking.worst].find(c=>c.id===id);
    if(!car)throw Error('車体がランキング外になりました。現在の一覧から選んでください');
    const r={version:VERSION,durationSeconds:DURATION,key:id,carId:id,experimentId:this.comparison.id,seed:car.courseSeed,courseProfile:this.courseProfile,courseSeed:car.courseSeed,populationSeed:car.populationSeed,course:makeCourse(car.courseSeed,this.courseProfile),
      initial:{...car.baseline,...simulate(car.baseline.genome,{seed:car.courseSeed,courseProfile:this.courseProfile,frames:true})},
      champion:{...car,...simulate(car.genome,{seed:car.courseSeed,courseProfile:this.courseProfile,frames:true})}};
    this.recordReplays.set(id,r);while(this.recordReplays.size>8)this.recordReplays.delete(this.recordReplays.keys().next().value);
    return r;
  }
  finishRun() {
    if(!this.comparison.results.some(r=>r.runIndex===this.comparison.runIndex))this.comparison.results.push(structuredClone({
      runIndex:this.comparison.runIndex,courseProfile:this.courseProfile,courseSeed:this.courseSeed,populationSeed:this.populationSeed,evolutionSeed:this.evolutionSeed,
      populationSize:this.size,generations:this.limit,evaluated:this.evaluated,evaluationMs:this.evaluationMs,initialProfile:initialProfileForSeed(this.populationSeed,this.strategy),
      history:this.history,initial:this.initial,champion:this.champion,milestones:this.milestones}));
    if(this.comparison.totalRuns===0)this.comparison.results=this.comparison.results.slice(-RECENT_RUN_LIMIT);
    this.nextRun=this.comparison.totalRuns===0||this.comparison.runIndex+1<this.comparison.totalRuns;
    if(!this.nextRun){this.running=false;this.phase='complete';}else this.phase=this.running?'between-runs':'paused';
  }
  async restore() {
    if(!this.file)return;
    let s;try{s=JSON.parse(await fs.readFile(this.file,'utf8'));}catch(e){if(e.code==='ENOENT')return;throw Error('保存状態を読めません。ファイルを退避して再起動してください: '+e.message);}
    if(s.stateSchema!==undefined&&![2,3,4,5].includes(s.stateSchema))throw Error('保存形式が未対応です。ファイルを退避して条件を確認してください');
    if(s.durationSeconds!==undefined&&s.durationSeconds!==DURATION)throw Error('保存された走行時間が一致しません。別の保存先を使用してください');
    if(s.instabilityPolicy!==undefined&&s.instabilityPolicy!==INSTABILITY_POLICY)throw Error('保存された発散処理が未対応です');
    if(s.stateSchema===5&&s.instabilityPolicy!==INSTABILITY_POLICY)throw Error('保存された発散処理が不正です');
    const courseSeed=s.courseSeed??s.seed,populationSeed=s.populationSeed??s.seed,limit=s.limit??this.limit;
    const strategy=s.stateSchema>=3?s.strategy:'legacy',courseProfile=s.stateSchema>=4?s.courseProfile:'rolling-v1';
    validateCourseProfile(courseProfile);
    comparisonOptions({courseSeed,populationSeed,runs:1,generations:limit,strategy,courseProfile});
    if(s.version!==VERSION||s.size!==this.size||!Number.isInteger(s.generation)||s.generation<0||s.generation>=1000||!Array.isArray(s.population)||s.population.length!==this.size||!Array.isArray(s.history)||s.history.length!==s.generation+1||!Number.isInteger(s.evaluated)||s.evaluated!==(s.generation+1)*this.size||!Number.isInteger(s.rngState)||s.rngState<0||s.rngState>4294967295)throw Error('保存状態の条件が一致しません。集団サイズを合わせるかファイルを退避してください');
    s.population.forEach(validateGenome);[s.initial,s.champion,...(s.milestones??[])].forEach(validateCar);validateHistory(s.history);
    let comparison=s.comparison;
    if(comparison) {
      comparisonOptions({courseSeed,populationSeed:comparison.startPopulationSeed,runs:comparison.totalRuns,generations:limit});
      if(typeof comparison.id!=='string'||!comparison.id||comparison.id.length>128||!Number.isInteger(comparison.runIndex)||comparison.runIndex<0||(comparison.totalRuns!==0&&comparison.runIndex>=comparison.totalRuns)||!Number.isSafeInteger(comparison.runIndex)||populationSeed!==populationSeedForRun(comparison.startPopulationSeed,comparison.runIndex)||!Array.isArray(comparison.results)||comparison.results.length>(comparison.totalRuns===0?RECENT_RUN_LIMIT:comparison.runIndex+1)||s.generation>=limit)throw Error('保存された比較条件が不正です');
      const currentFinished=comparison.results.at(-1)?.runIndex===comparison.runIndex;
      const firstIndex=comparison.runIndex+(currentFinished?1:0)-comparison.results.length;
      if(firstIndex<0||(comparison.totalRuns!==0&&firstIndex!==0)||comparison.results.length===0&&comparison.runIndex!==0)throw Error('保存された比較の履歴が不正です');
      for(const [j,r] of comparison.results.entries()) {
        const i=firstIndex+j;
        if(r.runIndex!==i||(r.courseProfile??'rolling-v1')!==courseProfile||r.courseSeed!==courseSeed||r.populationSeed!==populationSeedForRun(comparison.startPopulationSeed,i)||r.evolutionSeed!==evolutionSeedForTrial(courseSeed,r.populationSeed,strategy)||r.populationSize!==this.size||r.generations!==limit||r.evaluated!==limit*this.size||r.history?.length!==limit||!Number.isFinite(r.evaluationMs)||r.evaluationMs<0)throw Error('保存された比較結果の条件が一致しません');
        const expectedProfile=initialProfileForSeed(r.populationSeed,strategy);if(r.initialProfile!==undefined&&(r.initialProfile?.id!==expectedProfile?.id||r.initialProfile?.label!==expectedProfile?.label))throw Error('保存された初期タイプが不正です');
        validateHistory(r.history);[r.initial,r.champion,...(r.milestones??[])].forEach(validateCar);
      }
      if(currentFinished!==(s.generation+1===limit))throw Error('保存された比較の進行状態が不正です');
    }else comparison={id:randomUUID(),startPopulationSeed:populationSeed,totalRuns:1,runIndex:0,results:[]};
    let ranking={best:[],worst:[],evaluated:0,coverage:'since-restore'},stagnation=0;
    if(s.stateSchema>=3) {
      ranking=s.ranking;stagnation=s.stagnation;
      if(!Number.isInteger(stagnation)||stagnation<0||stagnation>s.generation||!ranking||!['since-reset','since-restore'].includes(ranking.coverage)||!Number.isSafeInteger(ranking.evaluated)||ranking.evaluated<0||ranking.evaluated%this.size!==0)throw Error('保存されたランキング集計が不正です');
      if(ranking.coverage==='since-reset'&&ranking.evaluated!==comparison.runIndex*this.size*limit+s.evaluated)throw Error('保存されたランキングの評価数が不正です');
      for(const group of ['best','worst']) {
        if(!Array.isArray(ranking[group])||ranking[group].length>3||new Set(ranking[group].map(car=>car.genome?.join(','))).size!==ranking[group].length)throw Error('保存されたランキングが不正です');
        for(const car of ranking[group]) {
          validateCar(car);validateCar(car.baseline);
          if(!Number.isSafeInteger(car.runIndex)||car.runIndex<0||car.runIndex>comparison.runIndex||!Number.isInteger(car.generation)||car.generation<0||car.generation>=limit||(car.runIndex===comparison.runIndex&&car.generation>s.generation)||car.baseline.generation!==0||!Number.isInteger(car.candidateIndex)||car.candidateIndex<0||car.candidateIndex>=this.size||car.courseSeed!==courseSeed||(car.courseProfile??'rolling-v1')!==courseProfile||car.populationSeed!==populationSeedForRun(comparison.startPopulationSeed,car.runIndex)||car.id!==comparison.id+':'+car.runIndex+':'+car.generation+':'+car.candidateIndex)throw Error('保存されたランキング車体の出所が不正です');
        }
      }
    }
    if(ranking.worstPolicy===undefined) {
      // Old checkpoints discarded positive low scores behind zero-distance cars.
      // Preserve the search and best cars; rebuild only worst from future evaluations.
      ranking.worst=[];ranking.worstPolicy=WORST_POLICY;ranking.worstSinceEvaluated=ranking.evaluated;
    }else if(ranking.worstPolicy!==WORST_POLICY||!Number.isSafeInteger(ranking.worstSinceEvaluated)||ranking.worstSinceEvaluated<0||ranking.worstSinceEvaluated>ranking.evaluated||ranking.worstSinceEvaluated%this.size!==0||ranking.worst.some(car=>!eligibleForWorst(car)))throw Error('保存されたワーストの選出条件が不正です');
    const evaluationMs=s.evaluationMs??0;if(!Number.isFinite(evaluationMs)||evaluationMs<0)throw Error('保存された評価時間が不正です');
    const diagnostics=s.diagnostics??{unstableEvaluations:0,recent:[]};validateDiagnostics(diagnostics);
    Object.assign(this,{diagnostics,seed:courseSeed,courseSeed,courseProfile,populationSeed,evolutionSeed:evolutionSeedForTrial(courseSeed,populationSeed,strategy),limit,strategy,stagnation,ranking,comparison,evaluationMs,population:s.population,generation:s.generation,evaluated:s.evaluated,history:s.history,champion:s.champion,initial:s.initial,milestones:s.milestones??[],rng:random(s.rngState)});
    if(Array.isArray(s.workerCounts)&&s.workerCounts.length===this.workers.length&&s.workerCounts.every(w=>this.workers.some(v=>v.id===w.id)&&Number.isInteger(w.count)&&w.count>=0))for(const worker of this.workers)worker.count=s.workerCounts.find(w=>w.id===worker.id).count;
    this.completedCandidates=this.size;this.buildReplay();if(this.generation+1>=this.limit)this.finishRun();
  }
  snapshot() {
    return {version:VERSION,durationSeconds:DURATION,instabilityPolicy:INSTABILITY_POLICY,diagnostics:this.diagnostics,updatedAt:new Date().toISOString(),session:this.session,seed:this.courseSeed,courseProfile:this.courseProfile,courseSeed:this.courseSeed,populationSeed:this.populationSeed,evolutionSeed:this.evolutionSeed,populationSize:this.size,generation:this.generation,
      generations:this.limit,evaluated:this.evaluated,evaluationMs:this.evaluationMs,strategy:this.strategy,initialProfile:initialProfileForSeed(this.populationSeed,this.strategy),stagnation:this.stagnation,searchMix:mutationPlan(this.size,this.stagnation,this.strategy),ranking:this.ranking,comparison:this.comparison,running:this.running,phase:this.phase,error:this.error,mode:this.pool.mode,
      workers:this.workers,completedCandidates:this.completedCandidates??0,history:this.history,champion:this.champion,initial:this.initial,milestones:this.milestones,replayKey:this.replay?.key??null};
  }
  async save() {
    if(!this.file)return;
    await fs.mkdir(path.dirname(this.file),{recursive:true});
    const data={stateSchema:5,instabilityPolicy:INSTABILITY_POLICY,diagnostics:this.diagnostics,strategy:this.strategy,stagnation:this.stagnation,ranking:this.ranking,version:VERSION,durationSeconds:DURATION,seed:this.courseSeed,courseProfile:this.courseProfile,courseSeed:this.courseSeed,populationSeed:this.populationSeed,limit:this.limit,comparison:this.comparison,evaluationMs:this.evaluationMs,
      size:this.size,generation:this.generation,evaluated:this.evaluated,population:this.population,rngState:this.rng.state(),history:this.history,initial:this.initial,champion:this.champion,milestones:this.milestones,workerCounts:this.workers.map(({id,count})=>({id,count}))};
    const temporary=this.file+'.tmp';await fs.writeFile(temporary,JSON.stringify(data));await fs.rename(temporary,this.file);
  }
  schedule(){if(!this.stopped&&this.running&&!this.timer)this.timer=setTimeout(()=>{this.timer=null;this.inflight=this.step();},this.nextRun&&!this.pendingConfiguration?this.hold:this.delay);}
  async step() {
    if(this.busy||this.stopped)return;
    this.busy=true;
    try {
      if(this.pendingConfiguration){this.startComparison(this.pendingConfiguration);this.pendingConfiguration=null;}
      if(!this.running)return;
      if(this.nextRun){if(!Number.isSafeInteger(this.comparison.runIndex+1))throw Error('試行数の上限です。最初から再計算してください');this.comparison.runIndex++;this.resetModel(this.courseSeed,populationSeedForRun(this.comparison.startPopulationSeed,this.comparison.runIndex));}
      if(this.generation+1>=this.limit){this.finishRun();return;}
      this.phase='evaluating';this.error=null;this.completedCandidates=0;
      for(const worker of this.workers)worker.status='idle';
      const generation=this.generation+1,started=performance.now(),candidateWorkers=new Map();
      const results=await this.pool.evaluate(this.population,this.courseSeed,this.session+':'+generation,event=>{
        const worker=this.workers.find(w=>w.id===event.workerId),{workerId,id,...details}=event;
        candidateWorkers.set(id,workerId);Object.assign(worker,details,{candidateId:id});if(event.status==='done'){worker.count++;this.completedCandidates++;}
      },{courseProfile:this.courseProfile});
      if(this.stopped||this.pendingConfiguration)return;
      this.evaluationMs+=performance.now()-started;
      const cars=results.map((result,i)=>({...result,genome:[...this.population[i]],generation,candidateIndex:i}));
      for(const car of cars.filter(c=>c.reason==='unstable')) {
        const record={workerId:candidateWorkers.get(car.candidateIndex),courseSeed:this.courseSeed,courseProfile:this.courseProfile,populationSeed:this.populationSeed,generation,candidateIndex:car.candidateIndex,genome:car.genome,distance:car.distance,elapsed:car.elapsed,instability:car.instability};
        this.diagnostics.unstableEvaluations++;this.diagnostics.recent=[...this.diagnostics.recent.slice(-5),record];
        console.error(JSON.stringify({event:'vehicle-instability',experimentId:this.comparison.id,...record}));
      }
      const best=cars.slice().sort((a,b)=>b.score-a.score)[0];
      if(!this.initial)this.initial=best;
      if(!this.champion||best.score>this.champion.score){this.champion=best;this.stagnation=0;this.buildReplay();}else this.stagnation++;
      this.updateRanking(cars);
      this.generation=generation;this.evaluated+=results.length;
      this.history.push({generation,distance:this.champion.distance,mean:results.reduce((sum,r)=>sum+r.distance,0)/results.length});
      if([0,1,3,7,15,31,63,127,255,511,999].includes(generation))this.milestones=[...this.milestones.filter(c=>c.generation===0),...this.milestones.filter(c=>c.generation!==0).slice(-4),best];
      this.population=nextPopulation(this.population,results,this.rng,{strategy:this.strategy,stagnation:this.stagnation});
      if(this.generation+1>=this.limit)this.finishRun();else this.phase=this.running?'between':'paused';
      await this.save();
      console.log(JSON.stringify({trial:this.comparison.runIndex+1,courseProfile:this.courseProfile,courseSeed:this.courseSeed,populationSeed:this.populationSeed,generation,distance:Number(this.champion.distance.toFixed(3)),evaluated:this.evaluated,workers:this.workers.length}));
    }catch(error){if(!this.stopped){this.running=false;this.phase='error';this.error=error.message;console.error('探索を一時停止しました: '+error.message);}}
    finally{this.busy=false;if(!this.running&&this.phase==='pausing')this.phase='paused';this.schedule();}
  }
  control(action,seed,options={}) {
    if(action==='pause'){this.running=false;if(this.phase!=='complete')this.phase=this.busy?'pausing':'paused';clearTimeout(this.timer);this.timer=null;}
    else if(action==='resume'){if(this.generation+1>=this.limit&&!this.nextRun)throw Error('指定の比較が完了しました。「最初から再計算」で再探索できます');this.running=true;this.error=null;this.phase='starting';this.schedule();}
    else if(action==='reset'||action==='compare'){
      this.pendingConfiguration=action==='reset'?comparisonOptions({courseSeed:seed,populationSeed:seed,runs:1,generations:this.limit,strategy:this.strategy,courseProfile:this.courseProfile}):comparisonOptions({strategy:this.strategy,courseProfile:this.courseProfile,...options});
      this.running=true;this.phase='resetting';this.error=null;clearTimeout(this.timer);this.timer=null;this.schedule();
    }else throw Error('操作が不正です');
  }
  async close(){this.stopped=true;this.running=false;clearTimeout(this.timer);await this.pool.close();await this.inflight;}
}
