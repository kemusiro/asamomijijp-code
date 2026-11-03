import {
  baseline,
  candidates,
  evaluate,
  simulate,
  demand,
  VERSION,
  TRAINING_SEEDS,
  VALIDATION_SEEDS,
  assess,
  acceptable,
} from './engine.mjs';

export function runSearch(scenario, onProgress = () => {}) {
  const start = performance.now();
  const list = candidates();
  let best = baseline;
  let bestScore = Infinity;

  for (let i = 0; i < list.length; i++) {
    const score = evaluate(list[i], scenario);
    if (score < bestScore) {
      bestScore = score;
      best = list[i];
    }
    onProgress({done: i + 1, total: list.length, score: bestScore});
  }

  const events = demand(scenario, 303);
  return {
    scenario,
    version: VERSION,
    seed: 303,
    trainingSeeds: TRAINING_SEEDS,
    validationSeeds: VALIDATION_SEEDS,
    validation: assess(best, scenario, VALIDATION_SEEDS).pairs.map(({seed, base, candidate}) => ({
      seed,
      acceptable: acceptable(candidate, base),
      base,
      candidate,
    })),
    best,
    baseline,
    base: simulate(baseline, events, {frames: true}),
    optimized: simulate(best, events, {frames: true}),
    elapsed: performance.now() - start,
    candidateCount: list.length,
    bestScore,
  };
}
