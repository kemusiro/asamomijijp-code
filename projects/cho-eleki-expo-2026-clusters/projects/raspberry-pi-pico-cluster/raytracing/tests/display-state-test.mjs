import assert from 'node:assert/strict';
import {imageForState,elapsedForState} from '../display/display-state.mjs';
const now=Date.parse('2026-10-12T00:00:00Z');
assert.equal(imageForState({mode:'waiting_for_manual_recovery',live_image_url:'/old.png'}),null);
assert.equal(imageForState({mode:'waiting_for_workers',live_image_url:'/old.png'}),null);
assert.equal(imageForState({mode:'rendering',live_image_url:'/new.png',image_width:320,image_height:180}),'/new.png');
assert.equal(imageForState({mode:'recovering',result_image_url:'/complete.png'}),'/complete.png');
assert.deepEqual(elapsedForState({mode:'waiting_for_manual_recovery',phase_started_at:'2026-10-11T00:00:00Z'},now,false),{text:'—',label:'計算停止'});
assert.equal(elapsedForState({mode:'result',result:{e2e_ms:29000}},now,true).text,'29.0');
assert.equal(elapsedForState({mode:'rendering',phase_started_at:new Date(now-10000).toISOString(),updated_at:new Date(now-5000).toISOString()},now,true).text,'5.0');
console.log('PASS: 前job画像の排除・保持画像・停止時計・確定所要時間');

const {sceneForState,sceneDetails}=await import('../display/display-state.mjs');
const car={type:'vehicle',source:{courseProfile:'obstacles-v1',courseSeed:2026,populationSeed:2028,generation:7,distanceM:105.7}};
assert.equal(sceneForState({mode:'waiting_for_workers',scene:car,held_result:{scene:{type:'sphere'}}}).type,'sphere');
assert.equal(sceneForState({mode:'rendering',image_width:160,image_height:90,scene:car}).type,'vehicle');
assert.equal(sceneForState({mode:'holding_previous_result',scene:{type:'sphere'},held_result:{scene:car}}),car);
assert.match(sceneDetails(car),/2028.*第7世代.*105.7m/);
console.log('PASS: 描画対象と保持画像の出所を分離し、車体のseed・世代・距離を表示');

const worst={type:'vehicle',role:'worst',label:'車体ワースト1（0.0m除外）',source:{...car.source,selection:'ranking-worst-nonzero-v1',distanceM:.050038}};
assert.equal(sceneForState({mode:'waiting_for_workers',scene:car,held_result:{scene:worst}}).role,'worst');
assert.equal(sceneForState({mode:'rendering',image_width:320,image_height:180,scene:car,held_result:{scene:worst}}),car);
assert.match(sceneDetails(worst),/0.1m/);
console.log('PASS: ワースト保持画像をベストと誤表示せず、0.05mを0.1m表示');

assert.match(sceneDetails({...car,source:{...car.source,courseProfile:'obstacles-55-7p5-v1'}}),/台地55°・谷7.5m/);
