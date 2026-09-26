import ast
import json
import unittest
import xml.etree.ElementTree as ET
from convert import (BASE, FIRMWARE, PROFILE, PROFILE_PORT, PROFILE_SPEC, RGB_PINS,
                     TEMPLATE, UNIT_SPEC, ConversionError, convert, parse, parse_program)

SOURCE = (BASE / 'examples/blink.py').read_text()
GENERATED_SOURCE = (BASE / 'examples/blink-uiflow2-generated.py').read_text()


class ConverterTests(unittest.TestCase):
    def test_profile_is_grounded_in_pinned_official_sources(self):
        source = PROFILE_SPEC['official_source']
        self.assertEqual(PROFILE, 'core2-v1.3-uiflow2-v2.5.3')
        self.assertEqual(FIRMWARE, 'v2.5.3-CORE2')
        self.assertEqual(source['tag'], '2.5.3')
        self.assertEqual(source['commit'], '50e440780492aa847378c7d3477ab912f7063bac')
        self.assertEqual(UNIT_SPEC['runtime_class'], 'RGBUnit')
        self.assertEqual(UNIT_SPEC['runtime_base'], 'SK6812')
        self.assertEqual(UNIT_SPEC['standard_port'], {
            'name': 'B',
            'pins': [36, 26],
            'evidence': 'official 2.5.3 rgb_core.m5f2 and rgb_core.py pair',
        })
        self.assertEqual(PROFILE_PORT['name'], 'A')
        self.assertEqual(RGB_PINS, (33, 32))
        self.assertEqual(UNIT_SPEC['led_count'], 3)
        self.assertEqual(UNIT_SPEC['converter_supported_methods'], ['fill_color'])
        self.assertEqual({item['python'] for item in UNIT_SPEC['official_methods']},
                         {'set_brightness', 'fill_color', 'set_color'})
        self.assertTrue(all(len(item['sha256']) == 64 for item in source['files']))

    def test_sequences_and_bootstrap(self):
        project = convert(SOURCE)
        original = json.loads(TEMPLATE.read_text())
        self.assertEqual({k: v for k, v in project.items() if k != 'blockly'},
                         {k: v for k, v in original.items() if k != 'blockly'})
        root = ET.fromstring('<xml>' + project['blockly'] + '</xml>')
        def chain(kind):
            node = root.find(f'./block[@type="{kind}"]/statement/block')
            result = []
            while node is not None:
                result.append(node)
                node = node.find('./next/block')
            return result
        setup = chain('basic_on_setup')
        loop = chain('basic_on_loop')
        self.assertEqual([e.get('type') for e in setup], ['system_m5_begin', 'unit_rgb_init',
            'lvgl_page_screen_load', 'unit_rgb_set_fill_color', 'time_sleep_second'])
        self.assertEqual([e.get('type') for e in loop], ['system_m5_update',
            'unit_rgb_set_fill_color', 'time_sleep_second', 'unit_rgb_set_fill_color', 'time_sleep_second'])
        self.assertEqual(setup[3].find('./value/block/field[@name="COLOR"]').text, '#ff0000')
        self.assertEqual(loop[1].find('./value/block/field[@name="COLOR"]').text, '#33ff33')
        self.assertEqual(loop[3].find('./value/block/field[@name="COLOR"]').text, '#000000')
        self.assertEqual(setup[4].find('./value/shadow/field').text, '2')
        self.assertEqual(project['units'][0]['portType'], 'A')
        ids = [e.get('id') for e in root.iter() if e.get('id')]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(project['units'][0]['initBlockId'], ids)

    def test_observed_uiflow_roundtrip(self):
        before = json.loads((BASE / 'results/blink-port-a.m5f2').read_text())
        after = json.loads((BASE / 'results/roundtrip-port-a.m5f2').read_text())
        self.assertEqual(convert(SOURCE), before)
        self.assertEqual(ET.canonicalize('<xml>' + before['blockly'] + '</xml>'),
                         ET.canonicalize('<xml>' + after['blockly'] + '</xml>'))
        # UiFlow refreshes the unit creation time on import.
        after['units'][0]['createTime'] = before['units'][0]['createTime']
        after['blockly'] = before['blockly']
        self.assertEqual(before, after)
        regenerated = ast.parse((BASE / 'results/roundtrip-port-a.py').read_text())
        expected = ast.parse(SOURCE)
        prefixes = {
            'setup': ast.parse('global page0, rgb_0\nM5.begin()\nWidgets.setRotation(1)\nm5ui.init()\npage0 = m5ui.M5Page(bg_c=0xffffff)\nrgb_0 = RGBUnit((33,32),3)\npage0.screen_load()').body,
            'loop': ast.parse('global page0, rgb_0\nM5.update()').body,
        }
        for fn in [n for n in regenerated.body if isinstance(n, ast.FunctionDef)]:
            original = next(n for n in expected.body if isinstance(n, ast.FunctionDef) and n.name == fn.name)
            self.assertEqual([ast.dump(n) for n in fn.body],
                             [ast.dump(n) for n in prefixes[fn.name] + original.body])

    def test_generated_python_full_input(self):
        parsed = parse_program(GENERATED_SOURCE)
        self.assertEqual(parsed.mode, 'generated')
        self.assertEqual(parsed.operations, parse(SOURCE))
        self.assertEqual(convert(GENERATED_SOURCE), convert(SOURCE))

    def test_generated_page_metadata_is_applied(self):
        source = GENERATED_SOURCE.replace(
            '"rotation":1,"background":"#ffffff"',
            '"rotation":2,"background":"#123456"')
        source = source.replace('Widgets.setRotation(1)', 'Widgets.setRotation(2)')
        source = source.replace('bg_c=0xffffff', 'bg_c=0x123456')
        project = convert(source)
        self.assertEqual(project['components'][0]['backgroundColor'], '#123456')
        self.assertEqual(project['screen'][0]['rotation'], 2)

    def test_generated_metadata_is_required_and_checked(self):
        cases = [
            GENERATED_SOURCE.replace(
                '# uiflow2-unit: {"name":"rgb_0","type":"rgb","port":"A","leds":3}\n', ''),
            GENERATED_SOURCE.replace('"port":"A"', '"port":"B"'),
            GENERATED_SOURCE.replace('"firmware":"v2.5.3-CORE2"', '"firmware":"other"'),
            GENERATED_SOURCE.replace('Widgets.setRotation(1)', 'Widgets.setRotation(2)'),
            GENERATED_SOURCE.replace('rgb_0.fill_color(0xff0000)', 'rgb_0.set_color(0xff0000)'),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ConversionError):
                parse_program(source)

    def test_generated_unknown_code_reports_location(self):
        source = GENERATED_SOURCE.replace(
            '  time.sleep(2)', '  time.sleep(2)\n  value = 1')
        with self.assertRaisesRegex(ConversionError, r'line \d+, column \d+: unsupported statement'):
            parse_program(source)

    def test_observed_editability(self):
        original = json.loads((BASE / 'results/roundtrip.m5f2').read_text())
        edited = json.loads((BASE / 'results/edited-sleep3.m5f2').read_text())
        original['blockly'] = original['blockly'].replace('<field name="NUM">2</field>', '<field name="NUM">3</field>')
        self.assertEqual(original, edited)

    def test_empty_bodies(self):
        self.assertEqual(parse('import time\ndef setup(): pass\ndef loop(): pass'), {'setup': [], 'loop': []})

    def test_unsupported_never_silently_disappears(self):
        for body in ['x = 1', 'time = 3', 'rgb_0 = None', 'import os', 'return',
                     'if True: time.sleep(1)', 'for i in range(3): time.sleep(1)',
                     'time.sleep(x)', 'time.sleep(1 + 1)', 'time.sleep(-1)', 'time.sleep(1.5)',
                     'time.sleep(True)', 'time.sleep(86401)', 'time.sleep(seconds=1)',
                     'rgb_0.fill_color(0x1000000)', 'rgb_1.fill_color(0)', 'eval("1")',
                     'time.sleep(*[1])', 'global rgb_0', 'pass; time.sleep(1)']:
            with self.subTest(body=body), self.assertRaises(ConversionError):
                parse('import time\ndef setup():\n    ' + body + '\ndef loop(): pass')

    def test_module_and_definition_restrictions(self):
        for source in [SOURCE.replace('import time', 'import time as t'),
                       SOURCE.replace('def setup():', 'def setup(x=1):'),
                       SOURCE.replace('def setup():', '@decorator\ndef setup():'),
                       SOURCE.replace('def loop():', 'def setup():'),
                       SOURCE + '\nsetup()\n', SOURCE.replace('def loop():', 'async def loop():')]:
            with self.subTest(source=source), self.assertRaises(ConversionError):
                parse(source)

    def test_unverified_template_rejected(self):
        with self.assertRaises(ConversionError):
            convert(SOURCE, TEMPLATE.read_bytes() + b' ')

    def test_observed_single_changes(self):
        fixtures = BASE / 'fixtures'
        a = json.loads((fixtures / '01-sleep1.m5f2').read_text())
        b = json.loads((fixtures / '02-sleep2.m5f2').read_text())
        a['blockly'] = a['blockly'].replace('<field name="NUM">1</field>', '<field name="NUM">2</field>')
        self.assertEqual(a, b)
        a = json.loads((fixtures / '04-purple.m5f2').read_text())
        b = json.loads((fixtures / '05-red.m5f2').read_text())
        a['blockly'] = a['blockly'].replace('#6600cc', '#ff0000')
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
