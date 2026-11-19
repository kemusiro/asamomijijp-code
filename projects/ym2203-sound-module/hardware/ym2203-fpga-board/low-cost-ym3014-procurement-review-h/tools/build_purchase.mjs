// SPDX-License-Identifier: MIT
// Targeted edit of the preserved review G workbook using bundled artifact-tool.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sourceArg=process.argv.indexOf('--source-workbook');
const source=sourceArg<0?path.join(root,'..','low-cost-ym3014-manufacturing-review-g','local-output','outputs','review-g','purchase-plan.xlsx'):process.argv[sourceArg+1];
const p=JSON.parse(await fs.readFile(path.join(root,'purchase-plan.json'),'utf8'));
const observations=JSON.parse(await fs.readFile(path.join(root,'price-observations.json'),'utf8'));
const changes=new Set(observations.selected.map(r=>r.id));
const output=path.join(root,'local-output','outputs','review-h');await fs.mkdir(output,{recursive:true});
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const summary=wb.worksheets.getItem('Summary'),detail=wb.worksheets.getItem('Purchase');
const n=p.rows.length+1;
const beforeValues=detail.getRange(`A1:R${n}`).values;
const beforeFormulas=detail.getRange(`A1:R${n}`).formulas;
for(let i=0;i<p.rows.length;i++){
 const r=p.rows[i];if(!changes.has(r.id))continue;
 if(beforeValues[i+1][0]!==r.id)throw Error('Reference row changed '+r.id);
 for(const [column,value] of [['B',r.supplier],['C',r.mpn],['G',r.pack],['K',+r.price_jpy_incl],['M',r.availability],['N',r.evidence],['Q',r.url],['R',r.note]])detail.getRange(`${column}${i+2}`).values=[[value]];
 detail.getRange(`M${i+2}:N${i+2}`).format.fill='#FFFFFF';
 detail.getRange(`M${i+2}:N${i+2}`).format.wrapText=true;
 detail.getRange(`A${i+2}:R${i+2}`).format.rowHeight=54;
 if(r.id==='U07'||r.id==='C_2.2u'||r.id==='C_22u')detail.getRange(`M${i+2}:N${i+2}`).format.fill='#FFF0CF';
}
summary.getRange('A2').values=[['review F 購入見積・追補 H']];
summary.getRange('B5').values=[[p.parts_freight_jpy]];
summary.getRange('C5').values=[['秋月550円＋Mouser別送2500円枠。SS/DigiKeyは同梱で無料。']];
summary.getRange('B11').values=[[p.reserve_jpy]];
summary.getRange('C11').values=[['Gの2500円から2000円へ。今回14行の掲載価格/調達候補を確認。']];
summary.getRange('C12').values=[['送料枠込み概算。Mouser送料と最終カートは未確定。']];
summary.getRange('A21:C21').copyFrom(summary.getRange('A20:C20'),'all');
summary.getRange('A21:C21').values=[['Mouser',null,'少額別送2500円を確保（公開料金の確認値ではない）。']];
summary.getRange('B21').formulas=[[`=SUMIF(Purchase!B2:B${n},A21,Purchase!L2:L${n})`]];
summary.getRange('A29:C32').values=[['確認日','2026-11-19','GとF保存。PCB見積条件を継承。部品14行だけ再確認。'],['在庫確認','3行の調達候補あり','秋月2.2uFは在庫僅少。Mouser掲載在庫/価格はカートで再確認。'],['残る11行の価格','掲載価格確認済み','直接ページ・公式一覧・商品検索収録を区別して記録。'],['価格・数量の変更','Purchaseの青字セル','数量帯単価と送料は注文時に再確認。']];
summary.getRange('A34:C34').values=[['未確定送料','Mouser 2500円枠','6000円未満の少額送料は公開値を取得できず、予算枠を計上。']];
summary.getRange('B30:C31').format.wrapText=true;
summary.getRange('A30:C31').format.rowHeight=38;
summary.getRange('A34:C34').format.fill='#FFF0CF';
summary.getRange('A34:C34').format.rowHeight=38;
summary.getRange('B34:C34').format.wrapText=true;
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
const all=[...afterValues.flat(),...summary.getRange('A1:D35').values.flat()];
if(all.some(v=>typeof v==='string'&&/^#(REF!|DIV\/0!|VALUE!|NAME\?|NUM!|N\/A)/.test(v)))throw Error('Formula error');
const csv=afterValues.map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
await fs.writeFile(path.join(root,'purchase-plan.csv'),csv);
const previews=process.argv.includes('--detail-preview-only')?[['Purchase','A32:N43','capacitors']]:[['Summary','A1:C21','summary'],['Summary','A29:C34','limitations'],['Purchase','A32:N43','capacitors']];
for(const [sheetName,range,name] of previews){
 const preview=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(output,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(output,'purchase-plan.xlsx'));
await fs.writeFile(path.join(root,'purchase-verification.json'),JSON.stringify({rows:p.rows.length,changed_rows:changes.size,untouched_rows_preserved:p.rows.length-changes.size,all_purchase_formulas_preserved:true,formula_totals_match:true,nonnegative_spares:true,total_jpy:total,formula_errors:0},null,2)+'\n');
console.log((await wb.inspect({kind:'region',sheetId:'Summary',range:'A4:B14',maxChars:1800,tableMaxRows:11,tableMaxCols:2})).ndjson);
console.log('PASS: 14 updated rows, 72 preserved rows, all purchase formulas preserved, CSV/XLSX exported');
