#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit candidate BOM partitions/catalog evidence; not schematic or order approval."""
import argparse
import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def generate():
    raw=(ROOT/'economic-bom-plan.json').read_bytes()
    plan=json.loads(raw)
    parts=plan['parts']
    board_count=plan['assembled_boards']
    require(board_count==5,'This candidate plan is for five boards')
    allrefs=[ref for row in parts for ref in row['refs']]
    require(len(allrefs)==len(set(allrefs)),'Duplicate candidate designator')
    supplier=[row for row in parts if row['assembly']=='supplier']
    owner=[row for row in parts if row['assembly']=='owner']
    require(len(supplier)+len(owner)==len(parts),'Unknown assembly allocation')
    by_mpn={row['mpn']:row for row in parts if row['mpn']}
    require('SC1631' in by_mpn and 'ICE40UP5K-SG48I' in by_mpn,'Required devices removed')
    for row in supplier:
        require(row['mpn'] and row['jlc_part'] and row['library_economic_listed'], 'Unmatched supplier item')
        require(row['evidence_url'].startswith('https://jlcpcb.com/partdetail/'),'No catalog evidence URL')
        require(row['jlc_category'] in ['Basic','Extended','Preferred Extended'],'Unknown fee category')
        if row['min_terminal_pitch_mm'] is not None:
            require(row['min_terminal_pitch_mm']<2,'Accessible >=2mm candidate left in supplier allocation')
    for row in owner:
        require(row['min_terminal_pitch_mm']>=plan['policy']['owner_minimum_terminal_pitch_mm'], 'Owner pitch below requested threshold')
        require(row['jlc_part'] is None,'Owner item must not leak into supplier BOM')
    supplier_codes={row['jlc_part']:row for row in supplier}
    require(len(supplier_codes)==len(supplier),'Group identical MPNs/parts into one BOM line')
    extended=sum(row['jlc_category']=='Extended' for row in supplier_codes.values())
    basic=sum(row['jlc_category']=='Basic' for row in supplier_codes.values())
    preferred=sum(row['jlc_category']=='Preferred Extended' for row in supplier_codes.values())
    supplier_positions=sum(len(row['refs']) for row in supplier)
    owner_positions=sum(len(row['refs']) for row in owner)
    owner_joints=sum(len(row['refs'])*row['owner_solder_joints_per_item'] for row in owner if not row['conditional_if_unheadered_Pico'])
    extra_joints=sum(len(row['refs'])*row['owner_solder_joints_per_item'] for row in owner if row['conditional_if_unheadered_Pico'])
    raw_rates=(ROOT/'upper-cost-inputs.json').read_bytes()
    # Published rates were already recorded there; use current sibling snapshot for Economic.
    comparison_raw=(ROOT/'socket-cost-inputs.json').read_bytes()
    rates=json.loads(comparison_raw)['published_single_side_rates']
    fee=Decimal(str(rates['economic_setup']))+Decimal(str(rates['economic_stencil']))
    fee+=extended*Decimal(str(rates['economic_feeder_per_charged_extended_type']))
    missing_mpn=[ref for row in parts if row['mpn'] is None for ref in row['refs']]
    ic_positions=sum(len(row['refs']) for row in parts if row['refs'][0].startswith(('U_','A_PICO')))
    report={
        'schema_version':1,'date':plan['date'],'status':'catalog_and_candidate_BOM_audit_only',
        'plan_sha256':hashlib.sha256(raw).hexdigest(),
        'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'fee_snapshot_sha256':hashlib.sha256(comparison_raw).hexdigest(),
        'baseline_budget_snapshot_sha256':hashlib.sha256(raw_rates).hexdigest(),
        'boards':board_count,'candidate_designators':len(allrefs),'grouped_BOM_lines':len(parts),
        'major_IC_or_module_positions':ic_positions,
        'supplier_positions_per_board':supplier_positions,'supplier_placements_for_five':supplier_positions*board_count,
        'supplier_unique_jlc_codes':len(supplier_codes),'supplier_extended_types':extended,
        'supplier_basic_types':basic,'supplier_preferred_types':preferred,
        'supplier_unknown_catalog_codes':0,
        'owner_positions_including_modules_and_optional_headers_per_board':owner_positions,
        'owner_solder_joints_per_board_without_optional_Pico_headers':owner_joints,
        'owner_solder_joints_for_five_without_optional_Pico_headers':owner_joints*board_count,
        'optional_Pico_header_solder_joints_for_five':extra_joints*board_count,
        'minimum_Economic_setup_stencil_and_known_extended_loading_model_usd':float(fee),
        'fee_excludes':'PCB,parts,SMT,Xray,attrition/MOQ,logistics,tax,functional test,connector-anchor handwork and any service-specific fees',
        'owner_or_other_MPN_selection_required_refs':missing_mpn,
        'library_Economic_labels_confirmed_for_selected_supplier_codes':True,
        'live_inventory_and_order_acceptance_confirmed':False,
        'manufacturer_pinouts_reflow_and_mechanics_fully_verified':False,
        'complete_schematic_or_routed_board':False,
        'release_gates':plan['unresolved_release_gates'],
        'manufacturing_release_ready':False,
    }

    def csv_for(selected):
        out=io.StringIO(newline='')
        writer=csv.writer(out,lineterminator='\n')
        writer.writerow(['candidate_designators_NOT_schematic_refs','function','value','manufacturer','candidate_MPN','package','quantity_per_board','placed_quantity_for_five_NOT_purchase_quantity','assembly','min_terminal_pitch_mm_proposed','JLC_part','category','Economic_catalog_label','evidence_URL','status','notes'])
        for row in selected:
            writer.writerow([' '.join(row['refs']),row['function'],row['value'],row['manufacturer'] or '',row['mpn'] or '',row['package'],len(row['refs']),len(row['refs'])*board_count,row['assembly'],row['min_terminal_pitch_mm'] or '',row['jlc_part'] or '',row['jlc_category'] or '',row['library_economic_listed'],row['evidence_url'] or '',row['status'],row['notes']])
        return out.getvalue()

    table=['# Economic候補BOM一覧（生成物）','',
        '正本は`economic-bom-plan.json`。数量は回路図前の予算、refは候補の識別名。購入・発注用BOM／CPLではない。','',
        '| 区分 | 用途 | 型番／仕様 | 個数／枚 | JLC | 部品区分 |',
        '| --- | --- | --- | ---: | --- | --- |']
    for row in parts:
        name=row['mpn'] or ('未選定：'+row['value'])
        code=f"[{row['jlc_part']}]({row['evidence_url']})" if row['jlc_part'] else '自前'
        table.append(f"| {'委託' if row['assembly']=='supplier' else '自前'} | {row['function']} | {name} | {len(row['refs'])} | {code} | {row['jlc_category'] or '—'} |")
    return {
        ROOT/'verification/economic-bom-check.json':json.dumps(report,ensure_ascii=False,indent=2)+'\n',
        ROOT/'economic-smt-candidates.csv':csv_for(supplier),
        ROOT/'owner-assembly-candidates.csv':csv_for(owner),
        ROOT/'economic-candidate-bom.csv':csv_for(parts),
        ROOT/'ECONOMIC-BOM-TABLE.md':'\n'.join(table)+'\n',
    },report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    outputs,report=generate()
    for path,text in outputs.items():
        if args.write:path.write_text(text,encoding='utf-8')
        else:require(path.read_text()==text,f'Stale {path.name}; use --write')
    for key in ['major_IC_or_module_positions','supplier_positions_per_board','supplier_unique_jlc_codes','supplier_extended_types','supplier_basic_types','owner_solder_joints_for_five_without_optional_Pico_headers','minimum_Economic_setup_stencil_and_known_extended_loading_model_usd']:
        print(key,report[key])
    print('PASS: candidate partition, catalog codes, proposed pitch policy and reproducible exports')
    print('NOT a live quote, complete schematic, mechanical/reflow approval or factory-ready BOM')


if __name__=='__main__':main()
