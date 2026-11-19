"""Read-only checks for the five-PCB/one-fitted-set procurement profile."""
import csv,hashlib,json,math
from decimal import Decimal
from pathlib import Path

def verify(plan,catalog,quotes):
 rows=plan['rows'];ids={r['id']:r for r in rows};original={r['id']:r for r in catalog['rows']}
 assert len(rows)==len(ids)==90 and ids.keys()==original.keys()
 assert plan['profile']['pcb_each']==5 and plan['profile']['fitted_sets']==1
 pcbs=[r for r in rows if r['kind']=='PCB'];assert len(pcbs)==3
 assert sum(r['required_qty'] for r in pcbs)==15 and sum(r['used_qty'] for r in pcbs)==3 and sum(r['remaining_qty'] for r in pcbs)==12
 for r in rows:
  o=original[r['id']];pcb=r['kind']=='PCB'
  assert r['required_qty']==(5 if pcb else o['qty_one']),r['id']
  assert r['used_qty']==o['qty_one'] and r['refs']==o['refs'] and r['mpn']==o['mpn']
  assert r['pack_size']==(5 if pcb else o['pack_size'])
  units=math.ceil(max(0,r['required_qty']+r['spare']-r['stock'])/r['pack_size']) if r['pack_size'] else None
  assert r['order_units']==units
  assert r['remaining_qty']==(units*r['pack_size']+r['stock']-r['used_qty'] if units is not None else None)
 assert ids['J02']['required_qty']==128 and ids['J03']['order_units']==6
 assert ids['M01']['required_qty']==ids['M02']['required_qty']==1
 assert sum(r['known_subtotal_jpy'] or 0 for r in rows if r['supplier']=='秋月')==6290
 assert quotes['quantity']=={'designs':3,'each':5,'total':15,'fitted_sets':1}
 assert quotes['destination']=='Japan' and quotes['fx_assumption_jpy_per_usd']==160
 for v in quotes['vendors']:
  assert sum(Decimal(str(r['price_usd'])) for r in v['boards'])==Decimal(str(v['pcb_total_usd']))
  assert [(r['layers'],r['quantity']) for r in v['boards']]==[(4,5),(4,5),(2,5)]
  for m in v['shipping_methods']:
   if m['available']:
    assert Decimal(str(m['delivered_usd']))==Decimal(str(v['pcb_total_usd']))+Decimal(str(m['cost_usd']))
    assert m['delivered_jpy_at_160']==round(m['delivered_usd']*160)
    assert not m['name'].startswith('My ') and m['cost_usd']>0
 return True

def main():
 root=Path(__file__).resolve().parents[1];p=root/'procurement/order-5pcb-1set'
 catalog_path=root/'procurement/catalog.json';catalog=json.loads(catalog_path.read_text())
 plan=json.loads((p/'order-plan.json').read_text());quotes=json.loads((p/'pcb-quotes.json').read_text())
 assert hashlib.sha256(catalog_path.read_bytes()).hexdigest()==plan['catalog_sha256']
 verify(plan,catalog,quotes)
 for file,n in [('order-bom.csv',90),('akizuki-order.csv',30),('other-suppliers.csv',60)]:
  rows=list(csv.DictReader((p/file).open()));assert len(rows)==n and len({r['id'] for r in rows})==n
 # Regressions reject the three expensive quantity mistakes rather than only
 # checking a repeated implementation formula.
 import copy
 for id,key,bad in [('PCB1','required_qty',1),('M02','required_qty',5),('J02','required_qty',640)]:
  changed=copy.deepcopy(plan);next(r for r in changed['rows'] if r['id']==id)[key]=bad
  try:verify(changed,catalog,quotes)
  except AssertionError:pass
  else:raise AssertionError(('Accepted wrong order',id))
 manifest=p/'manifest.json'
 if manifest.exists():
  for name,sha in json.loads(manifest.read_text())['files'].items():
   assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,('Changed procurement record',name)
 print('PASS: 15 bare PCBs / 3 used / 12 spare; one fitted set; 90 rows; 3 rejected quantity regressions; 2 vendor quotes')

if __name__=='__main__':main()
