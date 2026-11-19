# SPDX-License-Identifier: MIT
"""Cost comparison only: current F cannot mount this module without PCB revision."""
import csv,copy,json
from decimal import Decimal as D
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=json.loads((root/'purchase-plan.json').read_text())
rows=copy.deepcopy(p['rows']);r=next(r for r in rows if r['id']=='U01')
r.update(mpn='AE-Si5351A-B (110679)',supplier='Akizuki',price_jpy_incl='650.00',subtotal_jpy='650.00',url='https://akizukidenshi.com/catalog/g/g110679',availability='在庫あり。通販購入制限10セット、必要1。未引当',evidence='2026-11-20公式商品ページとメーカー回路図',note='次期ベース基板の変更候補。現Fには搭載不可。25MHz/0x60/CL8pF。Y1等の削減をまだ控除しない。',stock_source_url='https://akizukidenshi.com/catalog/g/g110679',stock_observed=None,purchase_limit=10,price_checked='2026-11-20',source_currency='JPY',source_unit_price_excl='591',source_price_incl_is_authoritative=True,minimum_order=1,order_multiple=1,pack_source_url='https://akizukidenshi.com/catalog/g/g110679')
v={}
for r in rows:v[r['supplier']]=v.get(r['supplier'],D(0))+D(r['subtotal_jpy'])
total=sum(v.values())+D(str(p['parts_freight_jpy']))+D(p['pcb_delivered_jpy'])+D(str(p['reserve_jpy']))
option={'date':'2026-11-20','status':'recommended_for_next_CAD_revision_not_mountable_on_current_F','pcb_changed':False,'requires_pcb_revision':True,'requires_crystal_load_initialization_change':True,'host_protocol_changes':False,'gpio_changes':False,'module_price_jpy_incl':'650.00','module_quantity':1,'total_before_crystal_deduction_jpy':str(total),'total_after_X01_deduction_jpy':str(total-D(next(r for r in p['rows'] if r['id']=='X01')['subtotal_jpy'])),'vendors':{k:str(x) for k,x in v.items()},'freight_by_vendor_jpy':p['freight_by_vendor_jpy'],'reserve_jpy':p['reserve_jpy'],'rows':rows}
(root/'stock-priority-option.json').write_text(json.dumps(option,ensure_ascii=False,indent=2)+'\n')
fields=['id','supplier','mpn','used','pack','buy_packs','purchased','price_jpy_incl','subtotal_jpy','availability','url','note']
with (root/'stock-priority-purchase.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
print('STOCK PRIORITY',total)
