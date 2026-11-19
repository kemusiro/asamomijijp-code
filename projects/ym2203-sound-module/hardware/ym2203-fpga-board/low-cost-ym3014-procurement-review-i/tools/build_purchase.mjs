// SPDX-License-Identifier: MIT
// Targeted edit of the preserved review H workbook using bundled artifact-tool.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sourceArg=process.argv.indexOf('--source-workbook');
const source=sourceArg<0?path.join(root,'..','low-cost-ym3014-procurement-review-h','local-output','outputs','review-h','purchase-plan.xlsx'):process.argv[sourceArg+1];
const p=JSON.parse(await fs.readFile(path.join(root,'purchase-plan.json'),'utf8'));
const observations=JSON.parse(await fs.readFile(path.join(root,'price-observations.json'),'utf8'));
const changes=new Set(observations.selected.map(r=>r.id));
const output=path.join(root,'local-output','outputs','review-i');await fs.mkdir(output,{recursive:true});
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const summary=wb.worksheets.getItem('Summary'),detail=wb.worksheets.getItem('Purchase');
const n=p.rows.length+1;
const beforeValues=detail.getRange(`A1:R${n}`).values;
const beforeFormulas=detail.getRange(`A1:R${n}`).formulas;
for(let i=0;i<p.rows.length;i++){
 const r=p.rows[i];if(!changes.has(r.id))continue;
 if(beforeValues[i+1][0]!==r.id)throw Error('Reference row changed '+r.id);
 for(const [column,value] of [['B',r.supplier],['C',r.mpn],['F',r.order_target],['G',r.pack],['K',+r.price_jpy_incl],['M',r.availability],['N',r.evidence.replace('2026-11-19 indexed_product_page; ','11/19 商品収録 ').replace('2026-11-19 direct_product_page; ','11/19 商品ページ ')],['Q',r.url],['R',r.note]])detail.getRange(`${column}${i+2}`).values=[[value]];
 detail.getRange(`M${i+2}:N${i+2}`).format.fill='#FFFFFF';
 detail.getRange(`M${i+2}:N${i+2}`).format.wrapText=true;
 detail.getRange(`A${i+2}:R${i+2}`).format.rowHeight=72;
 if(r.stock_observed===0)detail.getRange(`M${i+2}:N${i+2}`).format.fill='#FFF0CF';
}
summary.getRange('A2').values=[['review F 購入見積・Mouser集約 I']];
summary.getRange('B5').values=[[p.parts_freight_jpy]];
summary.getRange('C5').values=[['秋月550円。SS無料。Mouserは通常同梱の送料無料条件を適用。']];
summary.getRange('C9').values=[['GのOCS見積を継承。最終CAM・基板輸入諸費用は未確定。']];
summary.getRange('B11').values=[[p.reserve_jpy]];
summary.getRange('C11').values=[['為替・カート単価・輸入諸費用・在庫代替差の予備枠。']];
summary.getRange('C12').values=[['送料・部品税・予備費込み概算。在庫0が3行。確定見積ではない。']];
summary.getRange('A19:C19').values=[['Mouser',null,'税別換算6,707.70円。6,000円超の通常注文で送料0円を想定。']];
summary.getRange('B19').formulas=[[`=SUMIF(Purchase!B2:B${n},A19,Purchase!L2:L${n})`]];
summary.getRange('A21:C21').clear({applyTo:'contents'});
summary.getRange('A29:C34').values=[
 ['確認日','2026-11-19','F/G/Hを保存。海外43行だけ更新。秋月・SS購入分を維持。'],
 ['在庫確認','40行に在庫表示／3行在庫0','U01 Si5351A、U10 4T125、U17 1G32は納期・包装品をカートで確認。'],
 ['価格・販売単位','43行を照合','公開掲載価格。外貨行はUSD160円・EUR200円の予算換算。'],
 ['税と表示価格','消費税10%を計上','日本円DDPでの注文を想定。外貨掲載額は日本円カート見積と異なる。'],
 ['注文条件','カットテープ／少量バルク','有料MouseReel・完全リールを選択しない。全品同じMouser注文へ。'],
 ['未確定事項','在庫・円建て価格・配送','取り寄せ時の分納送料、基板CAM最終額、秋月2.2uF僅少在庫も要確認。']
];
summary.getRange('A29:C34').format.rowHeight=42;
summary.getRange('B29:C34').format.wrapText=true;
summary.getRange('A30:C30').format.fill='#FFF0CF';
await wb.recalculate();
const afterValues=detail.getRange(`A1:R${n}`).values;
const afterFormulas=detail.getRange(`A1:R${n}`).formulas;
for(let i=0;i<p.rows.length;i++){
 const r=p.rows[i],values=afterValues[i+1];
 if(!changes.has(r.id)&&JSON.stringify(beforeValues[i+1])!==JSON.stringify(values))throw Error('Unrelated row changed '+r.id);
 if(JSON.stringify(beforeFormulas[i+1])!==JSON.stringify(afterFormulas[i+1]))throw Error('Formula changed '+r.id);
 if(Math.abs(values[11]-Number(r.subtotal_jpy))>.001||values[9]<0)throw Error('Cost/quantity mismatch '+r.id);
}
const total=summary.getRange('B12').values[0][0];if(Math.abs(total-Number(p.total_jpy))>.001)throw Error('Summary mismatch '+total);
const oldUnit=detail.getRange('K9').values[0][0];
detail.getRange('K9').values=[[oldUnit+10]];await wb.recalculate();
if(Math.abs(summary.getRange('B12').values[0][0]-total-10*p.rows[7].buy_packs)>.001)throw Error('Recalculation probe failed');
detail.getRange('K9').values=[[oldUnit]];await wb.recalculate();
const all=[...afterValues.flat(),...summary.getRange('A1:D35').values.flat()];
if(all.some(v=>typeof v==='string'&&/^#(REF!|DIV\/0!|VALUE!|NAME\?|NUM!|N\/A)/.test(v)))throw Error('Formula error');
const csv=afterValues.map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
await fs.writeFile(path.join(root,'purchase-plan.csv'),csv);
const previews=[['Summary','A1:C20','summary'],['Summary','A29:C34','limitations'],['Purchase','A19:N33','resistors'],['Purchase','A48:N64','semiconductors'],['Purchase','A32:N45','capacitors']];
for(const [sheetName,range,name] of previews){
 const preview=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(output,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(output,'purchase-plan.xlsx'));
await fs.writeFile(path.join(root,'purchase-verification.json'),JSON.stringify({rows:p.rows.length,changed_rows:changes.size,untouched_rows_preserved:p.rows.length-changes.size,all_purchase_formulas_preserved:true,formula_totals_match:true,recalculation_probe_passed:true,nonnegative_spares:true,total_jpy:total,formula_errors:0},null,2)+'\n');
console.log((await wb.inspect({kind:'region',sheetId:'Summary',range:'A4:B14',maxChars:1800,tableMaxRows:11,tableMaxCols:2})).ndjson);
console.log('PASS: 43 updated rows, 43 preserved rows, all purchase formulas preserved, CSV/XLSX exported');
