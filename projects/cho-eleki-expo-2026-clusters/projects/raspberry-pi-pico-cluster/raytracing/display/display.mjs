import {imageForState,elapsedForState,sceneForState,sceneDetails} from './display-state.mjs';
const $ = (id) => document.getElementById(id);
let image = $("render-image");
const tileLayer = $("tile-layer");
const workers = $("workers");
const knownTiles = new Set();
let state = { mode: "starting", ready_node_ids: [], worker_tiles: {}, tiles: [] };
let lastImageUrl = "", imageSerial = 0;
let currentJob = "", connectionError = "", polling = false;

function hueFor(name) {
  let hash = 0;
  for (const character of name) hash = ((hash * 31) + character.charCodeAt(0)) >>> 0;
  return (hash * 137.508) % 360;
}

function modeText(mode) {
  return {
    starting: "展示システムを起動中",
    waiting_for_workers: "16台のPicoを接続中",
    rendering: "レイトレーシングを並列計算中",
    recovering: "ワーカを確認して自動復旧中",
    result: "16台で完成しました",
    holding_previous_result: "直前の完成画像を表示中",
    waiting_for_manual_recovery: "スタッフの復旧操作を待っています",
    display_error: "表示データを確認中",
  }[mode] || "状態を確認中";
}

function statusText(current) {
  if (current.mode === "rendering") {
    return "届いた領域から画像が完成していきます。枠の色は計算を担当したPicoです。";
  }
  if (current.mode === "result") {
    const remain = Math.max(0, Math.ceil((current.next_cycle_unix || 0) - Date.now() / 1000));
    return `計算結果を検査済み。${remain}秒後に次の画像計算を始めます。`;
  }
  if (current.mode === "waiting_for_workers") return "管理機が各Picoからの接続を待っています。";
  if (current.mode === "recovering") return "小さな確認画像で16台の復帰を検査しています。";
  if (current.mode === "waiting_for_manual_recovery") return current.result_image_url ? "前回の完成画像を保持しています。スタッフが接続と給電を確認します。" : "計算を停止しています。スタッフが接続と給電を確認します。";
  if (current.mode === "holding_previous_result") return current.message || "一時的な障害から復帰しました。次の計算を待っています。";
  return current.message || "展示プログラムを準備しています。";
}

function showScene(scene) {
  $('scene-title').textContent=scene?.label || '球体のレイトレーシング';
  $('scene-origin').textContent=scene?.type==='vehicle'?sceneDetails(scene)+(scene.terrain?' · 元コースの地形・車体姿勢は展示用の近似':' · 2D形状を立体化した近似模型'):'球面・床・光・反射を並列計算';
  $('validation-note').textContent=scene?.type==='vehicle'?'タイルCRCと全領域受信を検査 · 画像参照CRCは未照合':'完成時に既知CRC・画素を照合';
}
function showImage(current) {
  const chosen = imageForState(current);
  if (!chosen) {
    imageSerial++;image.removeAttribute('src');lastImageUrl='';showScene(null);$('checksum').textContent='';
    $("empty-message").hidden=false;
    $("empty-message").textContent=current.mode==='waiting_for_manual_recovery'?'Picoの復旧を待っています':'Picoの接続を待っています';
    return;
  }
  const url = `${chosen}?v=${encodeURIComponent(current.updated_at || "0")}`;
  if (url === lastImageUrl) return;
  lastImageUrl=url;
  const serial=++imageSerial,scene=sceneForState(current),next=new Image();
  next.id='render-image';next.alt=scene?.type==='vehicle'?`${scene.label || '選択車体'}をPicoでレイトレーシングした画像`:'Picoでレイトレーシングした球体の画像';
  // 新画像の読み込みに成功したときだけ、画像と出所ラベルを同時に交換する。
  next.onload=()=>{if(serial!==imageSerial)return;image.replaceWith(next);image=next;showScene(scene);$('checksum').textContent=chosen===current.live_image_url?'':current.held_result?.checksum32?'CRC '+current.held_result.checksum32:'';$('empty-message').hidden=true;};
  next.onerror=()=>{if(serial===imageSerial)lastImageUrl='';};
  next.src=url;
}

function showTiles(current) {
  if (current.mode !== "rendering") {
    tileLayer.replaceChildren();
    knownTiles.clear();
    return;
  }
  const width = current.image_width || 320;
  const height = current.image_height || 180;
  for (const tile of current.tiles || []) {
    const key = `${tile.tile_id}:${tile.node_id}`;
    if (knownTiles.has(key)) continue;
    knownTiles.add(key);
    const element = document.createElement("div");
    element.className = "tile";
    element.style.cssText = `--hue:${hueFor(tile.node_id)};left:${tile.x0 / width * 100}%;top:${tile.y0 / height * 100}%;width:${tile.width / width * 100}%;height:${tile.height / height * 100}%`;
    tileLayer.append(element);
  }
}

function showWorkers(current) {
  const ready = current.ready_node_ids || [];
  const workerTiles = current.worker_tiles || {};
  const names = Array.from(new Set([...ready, ...Object.keys(workerTiles)])).sort();
  while (names.length < (current.expected_workers || 16)) names.push(`pico-${String(names.length + 1).padStart(2, "0")}`);
  workers.replaceChildren(...names.slice(0, 16).map((name) => {
    const element = document.createElement("div");
    const isReady = ready.includes(name);
    element.className = `worker${isReady ? "" : " offline"}`;
    element.style.setProperty("--hue", hueFor(name));
    const label = document.createElement("div");
    label.className = "worker-name";
    label.textContent = name;
    const count = document.createElement("div");
    count.className = "worker-count";
    count.textContent = workerTiles[name] || 0;
    element.append(label, count);
    return element;
  }));
}

function render(current) {
  if (current.job_id !== currentJob) {
    currentJob = current.job_id;
    tileLayer.replaceChildren();knownTiles.clear();
  }
  state = current;
  const completed = current.completed_tiles || 0;
  const total = current.total_tiles || 240;
  const ready = (current.ready_node_ids || []).length;
  const expected=current.expected_workers || 16;
  $('cluster-title').textContent=`${expected}台で、1枚の絵を描く。`;
  $('expected-count').textContent=expected;$('step-workers').textContent=expected;
  $('scene-warning').hidden=!current.scene?.sourceError;
  $('scene-warning').textContent=current.scene?.sourceError?(current.scene.type==='vehicle'?`取得失敗のため前回取得の${current.scene.role==='worst'?'ワースト1':'ベスト1'}を使用。`:'対象車体未取得のため球体を表示。')+current.scene.sourceError:'';
  $("mode-label").textContent = current.mode==='result'?`${expected}台で完成しました`:current.mode==='waiting_for_workers'?`${expected}台のPicoを接続中`:modeText(current.mode);
  $("status-message").textContent = statusText(current);
  $("ready-count").textContent = ready;
  $("progress-text").textContent = `${completed} / ${total} tiles`;
  $("progress-bar").style.width = `${Math.min(100, completed / total * 100)}%`;
  $("cycle").textContent = current.cycle ? `CYCLE ${current.cycle}` : "CYCLE —";
  document.body.classList.toggle("alert", ["recovering", "holding_previous_result", "waiting_for_manual_recovery", "display_error"].includes(current.mode));
  showImage(current);
  showTiles(current);
  showWorkers(current);
}

function updateClock() {
  const updated = Date.parse(state.updated_at || "");
  const deadline = state.mode === "result" ? (state.next_cycle_unix || 0) * 1000 + 15000 : updated + 75000;
  const stale = Number.isFinite(updated) && Date.now() > deadline && state.mode !== "waiting_for_manual_recovery";
  $("freshness").hidden = !stale && !connectionError;
  $("freshness").textContent = connectionError ? "表示サーバへ再接続中。最後に取得した画像を保持しています。" : "計算状態の更新が止まっています。画像と進捗は保存された値です。";
  document.body.classList.toggle("stale", stale || Boolean(connectionError));
  const elapsed=elapsedForState(state,Date.now(),stale || Boolean(connectionError));
  $("elapsed").textContent=elapsed.text;
  $("elapsed-label").textContent=elapsed.label;
  if (state.mode === "result" && Number.isFinite(state.result?.e2e_ms)) {
    $("status-message").textContent = stale || connectionError ? "最後に確認した完成画像と計算結果を表示しています。" : statusText(state);
    return;
  }
  if (state.mode === "result") $("status-message").textContent = statusText(state);
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/api/state", { cache: "no-store", signal: AbortSignal.timeout(3000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    connectionError = "";
    render(await response.json());
  } catch (_error) {
    connectionError = "disconnected";
  } finally {
    polling = false;
    updateClock();
  }
}

showWorkers(state);
setInterval(updateClock, 100);
setInterval(poll, 250);
poll();
