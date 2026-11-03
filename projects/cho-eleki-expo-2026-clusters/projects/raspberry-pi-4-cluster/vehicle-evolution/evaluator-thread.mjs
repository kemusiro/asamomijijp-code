import {parentPort} from 'node:worker_threads';
import {simulate,DURATION} from './physics.mjs';
parentPort.on('message',task=>{
  try {if(task.durationSeconds!==DURATION)throw Error('評価時間が一致しません');parentPort.postMessage({result:simulate(task.genome,{seed:task.seed,courseProfile:task.courseProfile})});}
  catch(error){parentPort.postMessage({error:error.message});}
});
