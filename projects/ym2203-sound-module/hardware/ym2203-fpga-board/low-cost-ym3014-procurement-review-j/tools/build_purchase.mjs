// SPDX-License-Identifier: MIT
// Targeted edit of the preserved review I workbook using bundled artifact-tool.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sourceArg=process.argv.indexOf('--source-workbook');
const source=sourceArg<0?path.join(root,'..','low-cost-ym3014-procurement-review-i','local-output','outputs','review-i','purchase-plan.xlsx'):process.argv[sourceArg+1];
const p=JSON.parse(await fs.readFile(path.join(root,'purchase-plan.json'),'utf8'));
const observations=JSON.parse(await fs.readFile(path.join(root,'price-observations.json'),'utf8'));
const changes=new Set(observations.selected.map(r=>r.id));
const output=path.join(root,'local-output','outputs','review-j');await fs.mkdir(output,{recursive:true});
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const summary=wb.worksheets.getItem('Summary'),detail=wb.worksheets.getItem('Purchase');
const n=p.rows.length+1;
const sourceBoardTable=summary.getRange('A23:D26').values;
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
summary.getRange('A2').values=[['review F 購入見積・代替品調査 J']];
summary.getRange('B5').values=[[p.parts_freight_jpy]];
summary.getRange('C5').values=[['秋月550円。SS無料。Mouserは通常同梱の送料無料条件を適用。']];
summary.getRange('C9').values=[['GのOCS見積を継承。最終CAM・基板輸入諸費用は未確定。']];
summary.getRange('B11').values=[[p.reserve_jpy]];
summary.getRange('C11').values=[['為替・カート単価・輸入諸費用・在庫代替差の予備枠。']];
summary.getRange('C12').values=[['送料・部品税・予備費込み概算。現F維持。在庫0はU01のみ。確定見積ではない。']];
summary.getRange('A19:C19').values=[['Mouser',null,'税別換算7,192.60円。6,000円超の通常注文で送料0円を想定。']];
summary.getRange('B19').formulas=[[`=SUMIF(Purchase!B2:B${n},A19,Purchase!L2:L${n})`]];
summary.getRange('A21:C21').clear({applyTo:'contents'});
summary.getRange('A37:C40').values=[
 ['在庫優先の比較','概算 / 円','ベース基板変更の参考額。現F用の明細とは別案。'],
 ['秋月Si5351Aモジュール',650,'110679。通販在庫あり・購入制限10。必要1セット。'],
 ['モジュール案の総額',null,'U01を置換。水晶等の削減は未控除。CAD・CAM検証前。'],
 ['次期基板の変更範囲','U13・Y1周辺','25MHz・0x60維持。水晶CLは8pF。GPIO・HOSTは維持する要件。']
];
summary.getRange('B39').formulas=[[`=B12-Purchase!L${p.rows.findIndex(r=>r.id==='U01')+2}+B38`]];
summary.getRange('B38:B39').setNumberFormat('#,##0.00');
summary.getRange('A37:C40').format.rowHeight=36;
summary.getRange('A37:C40').format.wrapText=true;
summary.getRange('A29:C34').values=[
 ['確認日','2026-11-20','3行を再調査。残り83行とF/G/H/Iを保存。'],
 ['現F用の在庫','2行代替・1行欠品','U10 Q1品とU17 E4品を選定。Si5351A GT/GTRは欠品。'],
 ['価格・販売単位','少量カットテープ','U10円価格は2日前収録。U17円価格は4か月前、在庫は1週前収録。'],
 ['税と表示価格','部品消費税10%','外貨推計19行を継承。日本円DDPカート・予約在庫ではない。'],
 ['注文条件','通常同梱を想定','有料MouseReel・完全リール不要。秋月・SS優先、海外はMouser。'],
 ['在庫優先の次案','秋月モジュール','約27,454円。基板変更は提案段階。再配線・DRC・最終価格は未実施。']
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
if(JSON.stringify(sourceBoardTable)!==JSON.stringify(summary.getRange('A23:D26').values))throw Error('Original PCB cost table changed');
if(Math.abs(summary.getRange('B39').values[0][0]-27453.52)>.001)throw Error('Module comparison mismatch');
const total=summary.getRange('B12').values[0][0];if(Math.abs(total-Number(p.total_jpy))>.001)throw Error('Summary mismatch '+total);
const oldUnit=detail.getRange('K9').values[0][0];
detail.getRange('K9').values=[[oldUnit+10]];await wb.recalculate();
if(Math.abs(summary.getRange('B12').values[0][0]-total-10*p.rows[7].buy_packs)>.001)throw Error('Recalculation probe failed');
detail.getRange('K9').values=[[oldUnit]];await wb.recalculate();
const all=[...afterValues.flat(),...summary.getRange('A1:D35').values.flat()];
if(all.some(v=>typeof v==='string'&&/^#(REF!|DIV\/0!|VALUE!|NAME\?|NUM!|N\/A)/.test(v)))throw Error('Formula error');
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'final formula error scan'})).ndjson);
const csv=afterValues.map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
await fs.writeFile(path.join(root,'purchase-plan.csv'),csv);
const previews=[['Summary','A1:C20','summary'],['Summary','A29:C34','limitations'],['Summary','A37:C40','stock-priority'],['Purchase','A62:N64','logic-alternatives'],['Purchase','A51:N52','clock']];
for(const [sheetName,range,name] of previews){
 const preview=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(output,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(output,'purchase-plan.xlsx'));
await fs.writeFile(path.join(root,'purchase-verification.json'),JSON.stringify({rows:p.rows.length,changed_rows:changes.size,untouched_rows_preserved:p.rows.length-changes.size,all_purchase_formulas_preserved:true,formula_totals_match:true,recalculation_probe_passed:true,nonnegative_spares:true,total_jpy:total,formula_errors:0},null,2)+'\n');
console.log((await wb.inspect({kind:'region',sheetId:'Summary',range:'A4:B14',maxChars:1800,tableMaxRows:11,tableMaxCols:2})).ndjson);
console.log('PASS: 3 reviewed rows, 83 preserved rows, all purchase formulas preserved, CSV/XLSX exported');
