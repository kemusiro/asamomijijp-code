#!/usr/bin/env python3
"""Static study audit only; no hardware or protocol implementation."""
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parents[1]
HW = HERE.parent


def read(name):
    return json.loads((HERE / name).read_text())


def audit():
    p = read('plan.json')
    g = read('gpio-proposal.json')
    c = read('cost-inputs.json')
    obs = {x['id']: x for x in read('part-observations.json')['parts']}
    assert not p['hardware_applied'] and not p['firmware_applied']
    assert not g['schematic_applied'] and not g['firmware_applied']
    counts = {}
    for name, available_key in [('base_compact', 'base_compact_usable'),
                                ('base_large', 'base_large_usable'),
                                ('panel', 'panel_exported')]:
        pins = g[name]
        assigned = {x['gpio'] for x in pins}
        available = set(g[available_key])
        assert len(assigned) == len(pins), name
        assert len({x['net'] for x in pins}) == len(pins), name
        assert assigned <= available, name
        spare = available - assigned
        assert spare == set(g[name + '_spare']), name
        counts[name] = {'assigned': len(pins), 'usable': len(available), 'spare': sorted(spare)}
    pico = g['base_pico2']
    ext = [x for x in pico if not x.get('onboard_only')]
    assert {x['gpio'] for x in ext} == set(g['base_pico2_exported'])
    assert len(ext) == len({x['gpio'] for x in ext}) == 26
    assert [x['gpio'] for x in pico if x.get('onboard_only')] == [24]
    assert len({x['gpio'] for x in pico}) == 27
    counts['base_pico2'] = {'assigned': 27, 'exported_used': 26, 'spare': []}
    base = {x['net']: x['gpio'] for x in g['base_compact']}
    panel = {x['net']: x['gpio'] for x in g['panel']}
    for side in ['base_compact', 'base_large', 'base_pico2']:
        pin = {x['net']: x['gpio'] for x in g[side]}
        assert [pin[f'BUS_D{i}'] for i in range(8)] == list(range(8))
        assert [pin[f'MOD_CTL{i}'] for i in range(4)] == list(range(8, 12))
        assert (pin['MOD_ENABLE'], pin['MOD_ALERT_N']) == (12, 13)
        assert (pin['HOST_SDA'], pin['HOST_SCL']) == (20, 21)
        assert [pin[n] for n in ['DAC_I2S_DATA', 'AUDIO_BCK', 'AUDIO_LRCK', 'BASE_ADC_DOUT', 'MOD_I2S_DATA']] == [14, 15, 16, 17, 18]
        assert pin['SERVICE_SDA'] % 4 == 2 and pin['SERVICE_SCL'] == pin['SERVICE_SDA'] + 1
    assert (panel['UPLINK_SDA'], panel['UPLINK_SCL']) == (0, 1)
    assert (panel['EEPROM_SDA'], panel['EEPROM_SCL']) == (2, 3)
    assert (panel['LCD_SCK'], panel['LCD_MOSI']) == (6, 7)
    assert base['BASE_STOP_N'] not in (base['SERVICE_SDA'], base['SERVICE_SCL'])
    assert g['panel_mux']['channels'] == [0, 1, 2, 3]
    assert g['panel_mux']['adc_gpio'] == panel['KNOB_ADC'] == 26
    assert g['panel_mux']['adc_gpio'] in (26, 27, 28)
    assert g['panel_mux']['select_gpio'] == [panel['MUX_A'], panel['MUX_B']]
    assert len(g['panel_mux']['channels']) <= 2 ** len(g['panel_mux']['select_gpio'])
    for pin in g['base_compact']:
        n = pin['gpio']
        assert pin['module_pad'] == (f'J1.{n+2}' if n <= 15 else f'J2.{n-13}')
    addresses = list(p['addresses_service'].values())
    assert len(addresses) == len(set(addresses))
    assert p['panel_link']['address'] in addresses
    assert p['panel_link']['controller_base'] != p['host']['controller']
    assert p['panel_eeprom']['controller'] != p['panel_link']['controller_panel']
    assert p['host'] == {'controller': 0, 'address': 66, 'hz': 100000, 'signature': 'YM22S002', 'lease_ms': 1000, 'fifo_events': 1024, 'push_events': 32, 'request_max_bytes': 208, 'status_bytes': 64}
    assert p['power']['base_aux_budget_ma_including_panel'] <= p['power']['base_aux_rating_ma']
    assert p['power']['no_regulator_output_parallel']
    bits = (p['panel_link']['read_payload_bytes'] + 2) * 9
    occupancy = bits / p['panel_link']['hz'] / (p['panel_link']['poll_period_ms'] / 1000) * 100
    assert occupancy < 20
    assert bits / p['panel_link']['hz'] * 1e6 < p['panel_link']['transaction_timeout_us']
    locks = read('source-lock.json')['files']
    for name, digest in locks.items():
        assert hashlib.sha256((HW / name).read_bytes()).hexdigest() == digest, name
    D = lambda k: Decimal(str(c[k]))
    panel_extra = sum(D(k) for k in ['panel_mcu_jpy', 'panel_mux_jpy', 'panel_socket_and_header_jpy', 'panel_blocking_diode_allowance_jpy', 'panel_decoupling_pullup_filter_stop_allowance_jpy'])
    assert D('base_compact_jpy') == Decimal(str(obs['base_compact']['pack_price_jpy']))
    assert D('panel_mcu_jpy') == Decimal(str(obs['panel_mcu']['pack_price_jpy']))
    assert D('panel_mux_jpy') == Decimal(str(obs['panel_mux']['pack_price_jpy']))
    for connector in ('grove', 'qwiic'):
        total = sum(Decimal(str(obs[connector + '_' + part]['pack_price_jpy'])) for part in ['socket', 'cable'])
        assert D(connector + '_jpy') == total
        s = obs[connector + '_socket']
        assert s['used_qty'] <= s['pack_qty']
    common = D('baseline_parts_jpy') - D('baseline_base_mcu_jpy') - D('baseline_panel_cable_jpy') + panel_extra
    cases = [('LC-A direct panel comparison', D('baseline_parts_jpy'), D('pcb_goods_100mm_jpy')),
             ('LC-B compact base + Grove preferred', common + D('base_compact_jpy') + D('grove_jpy'), D('pcb_goods_100mm_jpy')),
             ('LC-B Pico2 base + Grove conditional', common + D('base_pico2_jpy') + D('base_pico2_socket_header_jpy') + D('base_pico2_power_isolation_allowance_jpy') + D('grove_jpy'), D('pcb_goods_100mm_jpy')),
             ('LC-B 2B base + Grove', common + D('base_large_jpy') + D('grove_jpy'), D('pcb_goods_100mm_jpy')),
             ('LC-B compact base + Qwiic alternative', common + D('base_compact_jpy') + D('qwiic_jpy'), D('pcb_goods_100mm_jpy')),
             ('LC-B compact base + Grove 120mm fallback', common + D('base_compact_jpy') + D('grove_jpy'), D('pcb_goods_120mm_jpy'))]
    scenarios = []
    for name, goods, pcb in cases:
        rounded = int(goods.to_integral_value(rounding=ROUND_CEILING))
        sub = rounded + int(pcb + D('parts_freight_allowance_jpy') + D('pcb_freight_allowance_jpy'))
        scenarios.append({'name': name, 'parts_goods_unrounded_jpy': str(goods), 'parts_goods_jpy': rounded,
                          'pcb_goods_jpy': int(pcb), 'parts_freight_allowance_jpy': c['parts_freight_allowance_jpy'],
                          'pcb_freight_allowance_jpy': c['pcb_freight_allowance_jpy'], 'subtotal_jpy': sub,
                          'reserve_jpy': c['reserve_jpy'], 'with_reserve_jpy': sub + c['reserve_jpy']})
    return ({'status': 'static_study_pass_not_hardware_acceptance', 'gpio': counts,
             'service_addresses': addresses, 'panel_poll_occupancy_percent_excluding_start_stop': occupancy,
             'preserved_files': len(locks), 'new_cad_erc_drc': 'not_run_no_new_cad', 'firmware_and_hardware_tests': 'not_implemented'},
            {'status': 'planning_allowances_not_final_cart_quote', 'panel_extra_jpy': str(panel_extra), 'scenarios': scenarios})


def outputs():
    checks, costs = audit()
    doc = '''# LC-B 費用比較（基板各5枚・部品1セット）

2026-11-19、税込円、YM2203CはRev Cから流用0円、1USD=160円。手実装、PCBAなし。
LC-Aの商品小計23,677円を起点に、ベースMCU・パネル接続だけを置換し、パネル用MCU等を追加する。
LCD・4ノブ・encoder・EEPROM・音源MCU・ADC/DAC・レベル変換・G40・その他の現行部品費を残す。

| 案 | 部品商品 | PCB商品 | 送料枠込み小計 | 予備費6,000円込み |
| --- | ---: | ---: | ---: | ---: |
'''
    for row in costs['scenarios']:
        doc += f"| {row['name']} | {row['parts_goods_jpy']:,}円 | {row['pcb_goods_jpy']:,}円 | {row['subtotal_jpy']:,}円 | {row['with_reserve_jpy']:,}円 |\n"
    doc += '''
## LC-Aとの差分

| 変更 | 差分 |
| --- | ---: |
| base Picossci2B 2,310円→Picossci2A 1,760円 | −550円 |
| PANEL40 550円→Grove購入260円 | −290円 |
| panel Pico | ＋800円 |
| active品TI CD74HC4051E 181円税抜 | ＋199.10円 |
| panel 1×20ソケット2本＋40pin strip追加1本 | ＋135円 |
| panel逆流防止diode | ＋50円（販売品未確定の枠） |
| MUX decoupling・I2C/STOP pull-up・RC等 | ＋120円（販売品未確定の枠） |
| 合計 | ＋464.10円、部品小計は円単位切上げ |

コネクタはGrove10個袋150円を1袋購入して2個使用、150mm cable110円を1本で260円。
Qwiic比較は5個袋200円＋cable150円=350円。使用個数だけを単価換算した過小見積にしない。
panel用pin stripはLC-Aの予備40pinを消費する分を補う1本35円と、1×20female2本100円。
2A direct solderにソケット代を加算しない。Pico2比較ではbase用にも同じ135円を別途加算する。
Pico2は安価だが電源変更仮枠200円込みのため、推奨2A案との差は435円。USB-C部品を削減できるとしても現時点では控除しない。

## 見積の確度

PCBはLC-Aで観測した同寸法・同製造条件の13.30＋5.30＋5.30=23.90USD（3,824円）を再利用した参考枠。
base120×100 fallbackは48.30USD（7,728円）。LC-BのGerberは未作成で、新CAM見積ではない。
主案base100×100/4L、source100×80/2L、panel100×76/2L、各5枚、標準via0.3mm、鉛フリーHASL。
過去LC-Aの矩形配置検討をLC-Bの配置・配線成功とみなさない。100mm配線が無理なら120mm fallbackを使う。

送料枠は部品7,000円＋PCB3,500円を据置。輸入/決済差3,000円＋再設計小物3,000円の予備費を追加する。
これは配送先向け実カートの新送料ではない。MCUやコネクタ削減で送料無料の閾値を割る可能性を吸収するため、以前の大型案の送料をそのまま流用せずLC-Aの余裕ある枠を使う。
新規DigiKey品は既存のDigiKey購入に同梱する想定で、単品海外通販の最低送料をゼロとしない。
部品の実測電流・熱・代替小物・注文時在庫・CAM追加料金・再製作・工具・ケース・手間は確定していない。

推奨案は予備費込み約4.45万円、予算目安4.5万円。I2C化で大幅に値下がりするわけではなく、4線化・処理分離・小型MCU選択が主な効果。
保存済み大型L/K/B案の旧D参考小計85,753円（予備費前）と同じ比較段階のLC-B小計38,466円との差は47,287円。
この大きな差の主因はLC-Aですでに見直したソケット・製造条件・基板面積であり、I2C化だけの削減額として説明しない。

価格観測はpart-observations.json。50円/120円/200円と送料・予備費は意図的な仮枠で、新規購入BOMの確定行ではない。
'''
    return {'verification.json': json.dumps(checks, ensure_ascii=False, indent=2) + '\n',
            'cost-report.json': json.dumps(costs, ensure_ascii=False, indent=2) + '\n', 'COST.md': doc}


if __name__ == '__main__':
    generated = outputs()
    check = '--check' in sys.argv
    for name, contents in generated.items():
        path = HERE / name
        if check:
            assert path.read_text() == contents, f'stale {name}'
        else:
            path.write_text(contents)
    print('PASS: GPIO/mux/address/cost arithmetic and preserved source hashes; static study only')
