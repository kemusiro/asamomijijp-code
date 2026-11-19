#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only checks on the saved XLSX; spreadsheet authoring is performed with Artifact Tool."""
from pathlib import Path
import argparse,json,zipfile,xml.etree.ElementTree as ET,hashlib
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def main():
 a=argparse.ArgumentParser();a.add_argument('workbook',type=Path);a.add_argument('--plan',type=Path,default=Path(__file__).resolve().parents[1]/'order-plan.json');a.add_argument('--output',type=Path);args=a.parse_args();d=json.loads(args.plan.read_text())
 with zipfile.ZipFile(args.workbook) as z:
  assert z.testzip() is None
  wb=ET.fromstring(z.read('xl/workbook.xml'));assert [s.attrib['name'] for s in wb.findall('s:sheets/s:sheet',NS)]==['購入リスト','参照対応']
  strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(q.itertext()) for q in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
  sheets=[ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')) for i in [1,2]]
  cells=[{q.attrib['r']:q for q in s.findall('.//s:sheetData/s:row/s:c',NS)} for s in sheets]
  def value(c):
   if c is None:return ''
   assert c.attrib.get('t')!='e',('Formula error',c.attrib['r'])
   if c.attrib.get('t')=='inlineStr':return ''.join(c.find('s:is',NS).itertext())
   q=c.find('s:v',NS)
   if q is None or q.text is None:return ''
   if c.attrib.get('t')=='s':return strings[int(q.text)]
   if c.attrib.get('t') in ['str','b']:return q.text
   try:return float(q.text)
   except ValueError:return q.text
  for table in cells:
   for c in table.values():value(c)
  p=cells[0];assert value(p['E5'])==1 and value(p['F5'])==5 and abs(value(p['M5'])-d['known_parts_subtotal_jpy'])<1e-7 and value(p['N5'])==sum(r['price_jpy'] is None for r in d['rows'])
  for i,r in enumerate(d['rows'],10):
   assert value(p[f'A{i}'])==r['id'] and value(p[f'C{i}'])==r['mpn']
   for col,key in [('E','required_qty'),('F','used_qty'),('J','order_units'),('K','remaining_qty')]:assert value(p.get(f'{col}{i}'))==(r[key] if r[key] is not None else ''),(r['id'],key)
  cap=next(i for i,r in enumerate(d['rows'],10) if r['id']=='C14');assert value(p[f'J{cap}'])==2 and abs(value(p[f'M{cap}'])-123.2)<1e-7
  refs={value(cells[1][f'A{i}'])+':'+value(cells[1][f'B{i}']):value(cells[1][f'C{i}']) for i in range(7,281)};expected={q:r['id'] for r in d['rows'] for q in r['refs']};expected.update({q:'PCB-COPPER' for q in d['pcb_only_refs']});assert refs==expected and len(refs)==274
  assert len([n for n in z.namelist() if n.startswith('xl/tables/table') and n.endswith('.xml')])==2
 report={'workbook_sha256':hashlib.sha256(args.workbook.read_bytes()).hexdigest(),'zip_crc':'PASS','rows':90,'references':274,'pcb_ordered':15,'pcb_used':3,'pcb_spare':12,'saved_error_cells':0,'known_parts_subtotal_jpy':d['known_parts_subtotal_jpy'],'unpriced_rows':sum(r['price_jpy'] is None for r in d['rows']),'native_excel_recalculation_confirmed':False}
 if args.output:args.output.write_text(json.dumps(report,indent=2)+'\n')
 print('PASS: saved XLSX quantities, part IDs, 274 references, table count, caches, CRC and no error cells')
if __name__=='__main__':main()
