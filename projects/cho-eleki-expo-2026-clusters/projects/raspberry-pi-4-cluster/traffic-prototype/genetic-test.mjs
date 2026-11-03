import assert from 'node:assert/strict';
import {assessTrafficPattern, PATTERN_TRAINING_SEEDS, validate, validateTrafficPattern} from './engine.mjs';
import {
  crossoverSignals,crossoverTrafficPatterns,evolutionRandom,initialSignalPopulation,initialTrafficPopulation,
  mutateSignal,mutateTrafficPattern,nextSignalPopulation,nextTrafficPopulation,
} from './genetic.mjs';

const firstPatterns=initialTrafficPopulation(6026,12);
const secondPatterns=initialTrafficPopulation(6026,12);
assert.deepEqual(firstPatterns,secondPatterns);
for(const pattern of firstPatterns)validateTrafficPattern(pattern);

const rng=evolutionRandom(1);
for(let index=0;index<100;index++) {
  validateTrafficPattern(mutateTrafficPattern(firstPatterns[index%12],rng,1));
  validateTrafficPattern(crossoverTrafficPatterns(firstPatterns[index%12],firstPatterns[(index+1)%12],rng));
}

const patternResults=firstPatterns.map((_,index)=>({eligible:true,score:index}));
const nextPatterns=nextTrafficPopulation(firstPatterns,patternResults,evolutionRandom(2));
assert.deepEqual(nextPatterns[0],firstPatterns[0]);
assert.deepEqual(nextPatterns[1],firstPatterns[1]);

const signals=initialSignalPopulation(7026,12);
assert.deepEqual(signals,initialSignalPopulation(7026,12));
for(const signal of signals)validate(signal);
for(let index=0;index<100;index++) {
  validate(mutateSignal(signals[index%12],rng,1));
  validate(crossoverSignals(signals[index%12],signals[(index+1)%12],rng));
}
const signalResults=signals.map((_,index)=>({eligible:true,score:index}));
const nextSignals=nextSignalPopulation(signals,signalResults,evolutionRandom(3));
assert.deepEqual(nextSignals[0],signals[0]);
assert.deepEqual(nextSignals[1],signals[1]);

const known={platoonSize:5,period:60,spacing:1,jitter:0.25,phase:0,reverseRate:0.005,crossRate:0.02};
const assessed=assessTrafficPattern(known,PATTERN_TRAINING_SEEDS);
assert.equal(assessed.eligible,true);
assert.ok(assessed.robustRatio>1.2);
assert.ok(assessed.best.config.offset.some(value=>value!==0));

console.log('PASS: 交通条件・信号の初期集団、選択、交叉、突然変異、境界、決定的再現、外側評価');
