import fs from 'node:fs';

const [path,workersText='12',budgetText='15000']=process.argv.slice(2);
function die(message){console.error(`FAIL: ${message}`);process.exit(1);}
if(!path)die('usage: node validate-time-budget.mjs RESULT.json [WORKERS] [BUDGET_MS]');
const expectedWorkers=Number(workersText),expectedBudget=Number(budgetText);
let report;
try{report=JSON.parse(fs.readFileSync(path,'utf8'));}catch(error){die(`result cannot be read: ${error.message}`);}
if(report.kind!=='time-budget-comparison')die('kind differs');
if(report.budgetMs!==expectedBudget)die(`budget differs: ${report.budgetMs}/${expectedBudget}`);
if(report.single?.workerCount!==1||report.distributed?.workerCount!==expectedWorkers)die('worker count differs');
if(!report.fairness?.sameInitialPopulation||!report.fairness?.sameSeed||!report.fairness?.completedByDeadlineOnly)die('fairness metadata is missing');
for(const [name,run] of [['single',report.single],['distributed',report.distributed]]) {
  if(!Number.isInteger(run.evaluatedCount)||run.evaluatedCount<1)die(`${name} evaluated count is invalid`);
  if(run.traces.filter(trace=>trace.withinBudget).length!==run.evaluatedCount)die(`${name} trace count differs`);
  if(run.traces.some(trace=>!Number.isFinite(trace.startedAtMs)||!Number.isFinite(trace.finishedAtMs)||trace.startedAtMs>trace.finishedAtMs))die(`${name} trace time is invalid`);
  if(run.traces.some(trace=>trace.withinBudget&&trace.finishedAtMs>expectedBudget))die(`${name} counted a late candidate`);
  if(!run.best?.config||!Number.isFinite(run.best.score))die(`${name} best result is invalid`);
}
if(report.distributed.evaluatedCount<=report.single.evaluatedCount)die('12 nodes did not evaluate more candidates');
if(typeof report.validation?.single?.eligible!=='boolean'||typeof report.validation?.distributed?.eligible!=='boolean')die('held-out validation is missing');
console.log(JSON.stringify({
  status:'PASS',budgetMs:expectedBudget,
  single:{candidates:report.single.evaluatedCount,generations:report.single.completedGenerations,meanWait:report.validation.single.meanWait},
  distributed:{candidates:report.distributed.evaluatedCount,generations:report.distributed.completedGenerations,meanWait:report.validation.distributed.meanWait},
  candidateMultiplier:report.candidateMultiplier,qualityImprovement:report.qualityImprovement,
},null,2));
