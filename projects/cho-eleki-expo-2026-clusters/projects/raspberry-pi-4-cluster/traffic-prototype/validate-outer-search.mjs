import fs from 'node:fs';

const [path,populationText='12',generationsText='5']=process.argv.slice(2);
function die(message){console.error(`FAIL: ${message}`);process.exit(1);}
if(!path)die('usage: node validate-outer-search.mjs RESULT.json [POPULATION] [GENERATIONS]');
const population=Number(populationText),generations=Number(generationsText);
let report;
try{report=JSON.parse(fs.readFileSync(path,'utf8'));}catch(error){die(`result cannot be read: ${error.message}`);}
if(report.kind!=='outer-traffic-search'||report.algorithm!=='genetic')die('kind or algorithm differs');
if(report.populationSize!==population||report.generations!==generations)die('population or generation count differs');
if(report.history?.length!==generations)die('history count differs');
if(!report.best?.pattern||!report.best?.details?.bestSignal||!Number.isFinite(report.best.details.robustRatio))die('best traffic pattern is missing');
if(!Array.isArray(report.validation?.pairs)||report.validation.pairs.length!==report.validationSeeds?.length)die('held-out validation is missing');
if(report.trainingSeeds.some(seed=>report.validationSeeds.includes(seed)))die('training and validation seeds overlap');
if(report.history.some(item=>item.traces?.length!==population))die('candidate trace count differs');
console.log(JSON.stringify({status:'PASS',population,generations,trainingRatio:report.best.details.robustRatio,validationRatio:report.validation.robustRatio,validationEligible:report.validation.eligible,pattern:report.best.pattern,signal:report.best.details.bestSignal},null,2));
