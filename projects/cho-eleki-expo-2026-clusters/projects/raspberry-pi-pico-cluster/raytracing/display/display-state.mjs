// 現在のjobの途中画像、または検査済みの保持画像だけを表示する。
export function imageForState(state) {
  if (state.mode === 'rendering' && state.image_width > 0 && state.image_height > 0) return state.live_image_url || null;
  return state.result_image_url || null;
}

export function elapsedForState(state, now, stale) {
  if (state.mode === 'result' && Number.isFinite(state.result?.e2e_ms)) {
    return {text:(state.result.e2e_ms/1000).toFixed(1),label:'所要秒（実測）'};
  }
  if (['waiting_for_manual_recovery','holding_previous_result'].includes(state.mode)) return {text:'—',label:'計算停止'};
  const started=Date.parse(state.phase_started_at || '');
  const reference=stale?Date.parse(state.updated_at || ''):now;
  if (!Number.isFinite(started)||!Number.isFinite(reference)) return {text:'—',label:'経過秒'};
  const seconds=Math.max(0,(reference-started)/1000);
  return seconds>=1000?{text:(seconds/60).toFixed(1),label:'経過分'}:{text:seconds.toFixed(1),label:'経過秒'};
}

// 待機・復旧時の画像は保持結果のもの。これから計算する車体の出所を重ねない。
export function sceneForState(state) {
  if (state.mode === 'rendering' && state.image_width > 0 && state.image_height > 0) return state.scene || null;
  return state.held_result?.scene || null;
}
export function sceneDetails(scene) {
  if (!scene) return '球体のレイトレーシング';
  if (scene.type !== 'vehicle') return scene.label || '球体のレイトレーシング';
  const s=scene.source;
  if (!s) return '車体の出所を確認中';
  const course={'rolling-v1':'起伏','obstacles-v1':'急坂・深い谷','obstacles-55-7p5-v1':'台地55°・谷7.5m'}[s.courseProfile]||'不明な地形';
  return `${course} ${s.courseSeed} · seed ${s.populationSeed} · 第${s.generation}世代 · ${Number(s.distanceM).toFixed(1)}m`;
}
