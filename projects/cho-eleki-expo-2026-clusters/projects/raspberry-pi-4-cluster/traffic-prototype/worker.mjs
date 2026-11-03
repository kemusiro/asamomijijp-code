import {runSearch} from './search.mjs';

self.onmessage=({data})=>{
  try {
    const result=runSearch(data.scenario,progress=>self.postMessage({type:'progress',...progress}));
    self.postMessage({type:'result',...result});
  } catch(error) {self.postMessage({type:'error',message:error.message});}
};
