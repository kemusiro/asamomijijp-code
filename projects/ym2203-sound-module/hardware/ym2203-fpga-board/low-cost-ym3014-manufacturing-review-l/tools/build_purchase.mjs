// SPDX-License-Identifier: MIT
// Run with the documented bundled artifact-tool runtime; no repo dependencies.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const p=JSON.parse(await fs.readFile(path.join(root,'purchase-plan.json'),'utf8'));
const out=path.join(root,'local-output','outputs','review-l');await fs.mkdir(out,{recursive:true});
const wb=Workbook.create();const summary=wb.worksheets.add('Summary');const detail=wb.worksheets.add('Purchase');
const rows=p.rows,n=rows.length+1;
const headers=['ID','購入先','部品・型番','使用数','手持ち','発注目標','個/包装','包装数','購入個数','余り','税込円/包装','小計円','在庫確認','価格根拠','基板:参照番号','','出典URL','組立・購入メモ'];
detail.getRange('A1:R1').values=[headers];
detail.getRange(`A2:R${n}`).values=rows.map(r=>[r.id,r.supplier,r.mpn,r.used,r.stock,r.order_target,r.pack,null,null,null,+r.price_jpy_incl,null,r.availability,r.evidence,r.refs.join(' '),null,r.url,r.note]);
for(const [col,formula] of [['H','=MAX(0,ROUNDUP((F2-E2)/G2,0))'],['I','=G2*H2'],['J','=E2+I2-D2'],['L','=ROUND(K2*H2,2)']]){
 detail.getRange(`${col}2`).formulas=[[formula]];detail.getRange(`${col}2:${col}${n}`).fillDown();
}
for(const sheet of [summary,detail]){sheet.showGridLines=false;sheet.getRange(sheet===detail?`A1:R${n}`:'A1:D35').format.font={name:'Arial',size:10};sheet.getRange(sheet===detail?`A1:R${n}`:'A1:D35').format.rowHeight=23;}
detail.freezePanes.freezeRows(1);detail.freezePanes.freezeColumns(2);
detail.getRange('A1:O1').format.fill='#24364B';detail.getRange('A1:O1').format.font={name:'Arial',size:10,color:'#FFFFFF',bold:true};
for(const [col,width] of Object.entries({A:15,B:19,C:53,D:10,E:10,F:12,G:12,H:10,I:12,J:10,K:16,L:15,M:53,N:34,O:70,P:3,Q:100,R:110}))detail.getRange(`${col}1:${col}${n}`).format.columnWidth=width;
detail.getRange(`D2:L${n}`).setNumberFormat('#,##0.00;[Red](#,##0.00);–');detail.getRange(`D2:J${n}`).setNumberFormat('0;[Red](0);–');
detail.getRange(`M2:N${n}`).format.wrapText=true;detail.getRange(`M2:N${n}`).format.rowHeight=42;
detail.getRange(`D2:G${n}`).format.font={color:'#2359A8'};detail.getRange(`K2:K${n}`).format.font={color:'#2359A8'};
for(let i=0;i<rows.length;i++)if(/在庫0|差異|不一致|E保存/.test(rows[i].availability+' '+rows[i].evidence))detail.getRange(`M${i+2}:N${i+2}`).format.fill='#FFF0CF';
summary.getRange('A2').values=[['review K 製造・購入見積 L']];summary.getRange('A2').format.font={name:'Arial',size:14,bold:true};
summary.getRange('A3:C3').format.borders={bottom:{style:'thin',color:'#91A0AE'}};
const values=[
 ['部品商品代',null,'3種類の基板に1セット分。276参照番号を照合。'],
 ['部品送料',p.parts_freight_jpy,'秋月550円。SS/Mouserは通常同梱時の送料無料を想定。'],
 ['基板3種類 × 各5枚 / USD',+p.pcb_goods_usd,'4層100×100、2層100×80、2層100×76mm。'],
 ['基板送料 OCS / USD',+p.pcb_shipping_usd,'日本向け1kgの送料シミュレーター。最終カート未確認。'],
 ['予算換算 JPY / USD',p.budget_fx_jpy_per_usd,'市場為替ではなく予算計算用の仮定。'],
 ['基板・配送の円換算',null,'税・輸入取扱・為替差額は下の予備費に含めて確保。'],
 ['商品・送料 小計',null,'実装委託費なし。全て手ハンダ。'],
 ['予備費',p.reserve_jpy,'在庫代替・税・為替・最終見積差額用。'],
 ['予算として確保する合計',null,'カート確定見積ではありません。'],
 ['目標予算',p.budget_jpy,'基板15枚、組立は1セット。'],
 ['目標までの余裕',null,'YM2203C流用、YM3014B-F提供済みを前提。']];
summary.getRange('A4:C14').values=values;
summary.getRange('B4').formulas=[[`=SUM(Purchase!L2:L${n})`]];summary.getRange('B9').formulas=[['=ROUND((B6+B7)*B8,2)']];summary.getRange('B10').formulas=[['=B4+B5+B9']];summary.getRange('B12').formulas=[['=B10+B11']];summary.getRange('B14').formulas=[['=B13-B12']];
summary.getRange('A17:C17').values=[['購入先','部品商品代 / 円','配送料の条件']];
for(let i=0;i<3;i++){const vendor=['Akizuki','Mouser','Switch Science'][i];summary.getRange(`A${18+i}:C${18+i}`).values=[[vendor,null,['佐川1個口550円 / 11,000円以上送料無料','6,000円超の通常同梱 / CT指定','小型区分200円・合計3,000円以上送料無料'][i]]];summary.getRange(`B${18+i}`).formulas=[[`=SUMIF(Purchase!B2:B${n},A${18+i},Purchase!L2:L${n})`]];}
summary.getRange('A23:D26').values=[['基板 / 5枚','USD','仕様','価格出典'],['ベース',13.3,'4層100×100 / FR4 Tg135 / 1.6mm','https://cart.jlcpcb.com/quote'],['音源',5.3,'2層100×80 / 1.6mm','https://cart.jlcpcb.com/quote'],['編集パネル',5.3,'2層100×76 / 1.6mm','https://cart.jlcpcb.com/quote']];
summary.getRange('A29:C32').values=[['確認日','2026-11-20','PCB仕様・日本1kg送料を再確認。Gerberはローカル生成・独立照合。'],['部品の確認範囲','K購入表85行を継承','今回85行すべての在庫・単価を再取得したわけではない。'],['価格の未確定','外貨推計18行など','検索収録・予算換算を含む。購入直前に円カートで確認。'],['輸入・最終配送','予備費2,000円','CAM審査・輸入諸費用・重量変更は未確定。']];
summary.getRange('D5').values=[['https://akizukidenshi.com/catalog/pages/buy.aspx']];summary.getRange('D7').values=[['https://jlcpcb.com/shipping']];
summary.getRange('A1:A35').format.columnWidth=45;summary.getRange('B1:B35').format.columnWidth=22;summary.getRange('C1:C35').format.columnWidth=90;summary.getRange('D1:D35').format.columnWidth=90;
summary.getRange('B4:B20').setNumberFormat('#,##0.00;[Red](#,##0.00);–');summary.getRange('B24:B26').setNumberFormat('0.00');
summary.getRange('B5:B8').format.font={color:'#2359A8'};summary.getRange('B11:B13').format.font={color:'#2359A8'};
for(const range of ['A17:C17','A23:D23']){summary.getRange(range).format.fill='#24364B';summary.getRange(range).format.font={name:'Arial',size:10,bold:true,color:'#FFFFFF'};}
summary.getRange('A12:C12').format.fill='#E6EDF4';summary.getRange('A12:C12').format.font={bold:true};summary.getRange('A29:D32').format.rowHeight=42;summary.getRange('B29:C32').format.wrapText=true;
await wb.recalculate();
const detailValues=detail.getRange(`A2:R${n}`).values;
for(let i=0;i<rows.length;i++){if(Math.abs(detailValues[i][11]-Number(rows[i].subtotal_jpy))>.001||detailValues[i][9]<0)throw Error('Purchasing mismatch '+rows[i].id);}
const total=summary.getRange('B12').values[0][0];if(Math.abs(total-Number(p.total_jpy))>.001)throw Error('Summary mismatch '+total);
const baseTotal=total;const original=detail.getRange('K2').values[0][0];detail.getRange('K2').values=[[original+10]];await wb.recalculate();if(Math.abs(summary.getRange('B12').values[0][0]-baseTotal-10*rows[0].buy_packs)>.001)throw Error('Input recalculation failed');detail.getRange('K2').values=[[original]];await wb.recalculate();
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'Final formula error scan'})).ndjson);
const all=[...detailValues.flat(),...summary.getRange('A1:D35').values.flat()];if(all.some(v=>typeof v==='string'&&/^#(REF!|DIV\/0!|VALUE!|NAME\?|NUM!|N\/A)/.test(v)))throw Error('Formula error');
const csv=[headers,...detailValues].map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\n')+'\n';await fs.writeFile(path.join(root,'purchase-plan.csv'),csv);
for(const [sheetName,range,name] of [['Summary','A1:C21','summary'],['Purchase','A1:L14','purchase'],['Summary','A23:C32','assumptions']]){const preview=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await preview.arrayBuffer()));}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(out,'purchase-plan.xlsx'));
await fs.writeFile(path.join(root,'purchase-verification.json'),JSON.stringify({rows:rows.length,installed_refs:276,formula_totals_match:true,recalculation_probe_passed:true,nonnegative_spares:true,total_jpy:total,formula_errors:0},null,2)+'\n');
console.log((await wb.inspect({kind:'region',sheetId:'Summary',range:'A4:B14',maxChars:2000,tableMaxRows:11,tableMaxCols:2})).ndjson);
console.log('PASS: purchase quantities, formula totals, CSV and XLSX exported');
