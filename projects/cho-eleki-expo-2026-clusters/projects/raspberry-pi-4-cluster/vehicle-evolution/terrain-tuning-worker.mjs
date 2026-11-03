import {parentPort,workerData} from 'node:worker_threads';
import {pathToFileURL} from 'node:url';
import {evaluateTrial,TUNING_VERSION} from './terrain-tuning.mjs';
parentPort.on('message',async task=>{
  try {
    const physics=await import(pathToFileURL(workerData.variants[task.condition]).href);
    if(physics.DURATION!==workerData.durationSeconds||physics.VERSION!==TUNING_VERSION)throw Error('測定用の物理モデル・時間が要求と一致しません');
    parentPort.postMessage({id:task.id,result:evaluateTrial(physics,task)});
  }catch(error){parentPort.postMessage({id:task.id,error:error.stack??error.message});}
});
