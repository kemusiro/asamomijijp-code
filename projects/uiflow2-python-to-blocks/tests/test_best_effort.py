import json
import unittest
import xml.etree.ElementTree as ET

from best_effort import BestEffortError, best_effort_convert, markdown_report
from convert import BASE, convert


def xml_root(project):
    return ET.fromstring('<xml>' + project['blockly'] + '</xml>')


def chain(root, root_type):
    node = root.find(f'./block[@type="{root_type}"]/statement/block')
    result = []
    while node is not None:
        result.append(node)
        node = node.find('./next/block')
    return result


class BestEffortTests(unittest.TestCase):
    def test_strict_input_uses_existing_converter(self):
        source = (BASE / 'examples/blink.py').read_text()
        project, report = best_effort_convert(source)
        self.assertEqual(project, convert(source))
        self.assertEqual(report['strategy'], 'strict-native')
        self.assertEqual(report['summary']['native_blocks'], 6)
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)

    def test_hybrid_keeps_native_and_raw_statements(self):
        source = '''\
import time
state = 1
def helper(value):
    print(value)
def setup():
    rgb_0.fill_color(0xff0000)
    helper(state)
def loop():
    if state:
        time.sleep_ms(10)
    time.sleep(1)
if __name__ == '__main__':
    setup()
    while True:
        loop()
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        self.assertEqual(report['strategy'], 'hybrid-native-and-raw')
        self.assertEqual(report['summary'], {
            'native_blocks': 2,
            'ui_components': 0,
            'structured_control_blocks': 1,
            'control_depth_fallback_blocks': 0,
            'raw_statement_blocks': 2,
            'raw_top_level_blocks': 1,
            'skipped_nodes': 1,
        })
        self.assertEqual(len(root.findall('./block[@type="execute_code_import"]')), 1)
        self.assertIn(
            'state = 1',
            root.find(
                './block[@type="execute_code_import"]/field[@name="CODE"]'
            ).text,
        )
        setup_types = [node.get('type') for node in chain(root, 'basic_on_setup')]
        loop_types = [node.get('type') for node in chain(root, 'basic_on_loop')]
        self.assertEqual(setup_types[-2:], ['unit_rgb_set_fill_color', 'execute_code'])
        self.assertEqual(loop_types[-2:], ['controls_if', 'time_sleep_second'])
        self.assertIsNotNone(root.find('.//block[@type="controls_if"]//block[@type="execute_code"]'))
        ids = [element.get('id') for element in root.iter()
               if element.tag in {'block', 'shadow', 'variable'} and element.get('id')]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('statement_raw_fallback', {note['code'] for note in report['notes']})

    def test_if_for_and_while_are_structured_through_depth_two(self):
        source = '''\
import time
def setup():
    pass
def loop():
    total = 0
    if total < 2:
        time.sleep(1)
        for i in range(3):
            total += i
    while total < 10:
        total += 1
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        self.assertEqual(report['summary']['structured_control_blocks'], 3)
        self.assertEqual(report['summary']['native_blocks'], 1)
        self.assertEqual(report['summary']['control_depth_fallback_blocks'], 0)
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)
        self.assertEqual(len(root.findall('.//block[@type="controls_if"]')), 1)
        self.assertEqual(len(root.findall('.//block[@type="controls_for_range"]')), 1)
        self.assertEqual(len(root.findall('.//block[@type="controls_whileUntil"]')), 1)
        if_block = root.find('.//block[@type="controls_if"]')
        first = if_block.find('./statement[@name="DO0"]/block')
        self.assertEqual(first.get('type'), 'time_sleep_second')
        self.assertEqual(first.find('./next/block').get('type'), 'controls_for_range')
        self.assertIsNone(first.find('./next/block/next'))
        variables = {node.text for node in root.findall('./variables/variable')}
        self.assertTrue({'total', 'i'} <= variables)

    def test_control_at_depth_three_is_one_raw_block(self):
        source = '''\
def setup():
    pass
def loop():
    if enabled:
        for i in range(2):
            while i < 1:
                i += 1
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        self.assertEqual(report['summary']['structured_control_blocks'], 2)
        self.assertEqual(report['summary']['control_depth_fallback_blocks'], 1)
        self.assertEqual(report['summary']['raw_statement_blocks'], 1)
        raw = root.find('.//block[@type="controls_for_range"]//block[@type="execute_code"]')
        self.assertIsNotNone(raw)
        self.assertIn('while i < 1:', raw.find('./field[@name="CODE"]').text)
        self.assertIn('control_depth_limit', {note['code'] for note in report['notes']})

    def test_elif_is_one_if_block_at_the_same_depth(self):
        source = '''\
def setup():
    pass
def loop():
    if n == 0:
        pass
    elif n == 1:
        pass
    else:
        n = 2
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        block = root.find('.//block[@type="controls_if"]')
        self.assertEqual(report['summary']['structured_control_blocks'], 1)
        self.assertEqual(block.find('./mutation').get('elseif'), '1')
        self.assertEqual(block.find('./mutation').get('else'), '1')
        self.assertIsNotNone(block.find('./statement[@name="ELSE"]/block[@type="variables_set"]'))

    def test_for_else_falls_back_as_one_control_subtree(self):
        source = '''\
def setup():
    pass
def loop():
    for i in range(3):
        print(i)
    else:
        print("done")
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        raw = root.find('.//block[@type="execute_code"]')
        self.assertEqual(report['summary']['structured_control_blocks'], 0)
        self.assertEqual(report['summary']['raw_statement_blocks'], 1)
        self.assertIn('for i in range(3):', raw.find('./field[@name="CODE"]').text)
        self.assertIn('unsupported_control_fallback', {note['code'] for note in report['notes']})

    def test_range_stop_is_adjusted_for_inclusive_for_block(self):
        source = '''\
def setup():
    pass
def loop():
    for up in range(1, 5):
        pass
    for down in range(5, 0, -1):
        pass
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        blocks = root.findall('.//block[@type="controls_for"]')
        self.assertEqual(report['summary']['structured_control_blocks'], 2)
        self.assertEqual(len(blocks), 2)
        up_to = blocks[0].find('./value[@name="TO"]/block')
        down_to = blocks[1].find('./value[@name="TO"]/block')
        self.assertEqual(up_to.find('./field[@name="OP"]').text, 'ADD')
        self.assertEqual(up_to.find('./value[@name="B"]/block/field[@name="NUM"]').text, '-1')
        self.assertEqual(down_to.find('./value[@name="B"]/block/field[@name="NUM"]').text, '1')
        self.assertEqual(blocks[1].find('./value[@name="BY"]/block/field[@name="NUM"]').text, '-1')

    def test_unknown_module_becomes_one_raw_top_level_block(self):
        source = 'print("a < b & c")\nfor i in range(3):\n    print(i)\n'
        project, report = best_effort_convert(source)
        root = xml_root(project)
        block = root.find('./block[@type="execute_code_import"]')
        self.assertIsNotNone(block)
        self.assertEqual(block.find('./field[@name="CODE"]').text, source.rstrip())
        self.assertEqual(report['strategy'], 'whole-module-raw')
        self.assertEqual(report['summary']['raw_top_level_blocks'], 1)

    def test_generated_bootstrap_is_normalized(self):
        source = '''\
import time
def setup():
    M5.begin()
    Widgets.setRotation(3)
    rgb_0.fill_color(1)
def loop():
    M5.update()
    print("tick")
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        self.assertEqual(report['summary']['native_blocks'], 1)
        self.assertEqual(report['summary']['raw_statement_blocks'], 1)
        self.assertEqual(report['summary']['skipped_nodes'], 3)
        codes = [note['code'] for note in report['notes']]
        self.assertEqual(codes.count('profile_bootstrap_normalized'), 3)

    def test_all_core2_buttons_are_native_condition_blocks(self):
        source = '''\
def setup():
    pass
def loop():
    if BtnA.wasPressed():
        selected = 1
    if BtnB.wasPressed():
        selected = 2
    if BtnC.wasPressed():
        selected = 3
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        conditions = root.findall(
            './/block[@type="controls_if"]/value[@name="IF0"]/'
            'block[@type="button_was_pressed"]'
        )
        self.assertEqual(
            [condition.find('./field[@name="NAME"]').text
             for condition in conditions],
            ['BtnA', 'BtnB', 'BtnC'],
        )
        self.assertEqual(report['summary']['native_blocks'], 3)
        self.assertEqual(report['summary']['structured_control_blocks'], 3)
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)

    def test_core2_speaker_calls_are_native_blocks(self):
        source = '''\
def setup():
    Speaker.begin()
    Speaker.setVolumePercentage(0.5)
def loop():
    Speaker.tone(880, 150)
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        setup_types = [node.get('type') for node in chain(root, 'basic_on_setup')]
        loop_types = [node.get('type') for node in chain(root, 'basic_on_loop')]
        self.assertEqual(setup_types[-2:], [
            'speaker_begin', 'speaker_set_volume_percentage'
        ])
        self.assertEqual(loop_types[-1], 'speaker_tone')
        volume = root.find(
            './/block[@type="speaker_set_volume_percentage"]/'
            'value[@name="VOLUME"]/shadow/field[@name="NUM"]'
        )
        tone = root.find('.//block[@type="speaker_tone"]')
        self.assertEqual(volume.text, '50')
        self.assertEqual(
            tone.find('./value[@name="FREQ"]/shadow/field[@name="NUM"]').text,
            '880',
        )
        self.assertEqual(
            tone.find('./value[@name="MS"]/shadow/field[@name="NUM"]').text,
            '150',
        )
        self.assertEqual(report['summary']['native_blocks'], 3)
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)

    def test_string_assignments_use_variable_and_text_blocks(self):
        source = '''\
def setup():
    pass
def loop():
    count_text = str(count)
    special_number = count % 3 == 0 or "3" in count_text
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        assignments = {
            block.find('./field[@name="VAR"]').text: block
            for block in root.findall('.//block[@type="variables_set"]')
        }
        count_value = assignments['count_text'].find('./value[@name="VALUE"]/block')
        special_value = assignments['special_number'].find(
            './value[@name="VALUE"]/block'
        )
        self.assertEqual(count_value.get('type'), 'text_convert_str')
        self.assertEqual(special_value.get('type'), 'logic_operation')
        self.assertIsNotNone(special_value.find('.//block[@type="math_modulo"]'))
        replace = special_value.find('.//block[@type="text_replace"]')
        self.assertIsNotNone(replace)
        self.assertEqual(
            replace.find('./value[@name="FROM"]/block/field[@name="TEXT"]').text,
            '3',
        )
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)

    def test_m5ui_page_and_textarea_become_editable_components(self):
        source = '''\
"""UI component example."""
import M5
from M5 import *
import m5ui
import lvgl as lv
BLUE = 0x0050C8
DARK_BLUE = 0x003078
WHITE = 0xFFFFFF
RED = 0xFF0000
def setup():
    app_page = m5ui.M5Page(bg_c=BLUE)
    count_box = m5ui.M5TextArea(
        text="0", x=60, y=70, w=200, h=90,
        font=lv.font_montserrat_48,
        bg_c=DARK_BLUE, border_c=WHITE, text_c=WHITE,
        parent=app_page,
    )
    count_box.set_one_line(True)
    app_page.screen_load()
def loop():
    count_box.set_text(count_text)
    count_box.set_text_color(
        RED, lv.OPA.COVER, lv.PART.MAIN | lv.STATE.DEFAULT
    )
    count_box.set_text_color(
        WHITE, lv.OPA.COVER, lv.PART.MAIN | lv.STATE.DEFAULT
    )
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        page = next(
            component for component in project['components']
            if component['type'] == 'lvgl_page'
        )
        textarea = next(
            component for component in project['components']
            if component['type'] == 'lvgl_textarea'
        )
        self.assertEqual(page['name'], 'app_page')
        self.assertEqual(page['backgroundColor'], '#0050c8')
        self.assertEqual(textarea['name'], 'count_box')
        self.assertEqual(textarea['pageId'], page['id'])
        self.assertEqual(
            (textarea['x'], textarea['y'], textarea['width'], textarea['height']),
            (60, 70, 200, 90),
        )
        self.assertEqual(textarea['text'], '0')
        self.assertEqual(textarea['font'], 'lv.font_montserrat_48')
        self.assertEqual(textarea['backgroundColor'], '#003078')
        self.assertEqual(textarea['borderColor'], '#ffffff')
        self.assertEqual(textarea['color'], '#ffffff')
        setup_types = [node.get('type') for node in chain(root, 'basic_on_setup')]
        self.assertEqual(setup_types[-2:], [
            'lvgl_textarea_set_one_line', 'lvgl_page_screen_load'
        ])
        self.assertEqual(
            root.find('.//block[@type="lvgl_page_screen_load"]/'
                      'field[@name="NAME"]').text,
            'app_page',
        )
        self.assertIsNotNone(
            root.find('.//block[@type="lvgl_textarea_set_text"]/'
                      'field[@name="NAME"]')
        )
        color_blocks = root.findall(
            './/block[@type="lvgl_textarea_set_text_color"]'
        )
        self.assertEqual(len(color_blocks), 2)
        self.assertEqual(
            [block.find('./field[@name="MODE"]').text for block in color_blocks],
            ['DEFAULT', 'DEFAULT'],
        )
        self.assertEqual(
            [
                block.find(
                    './value[@name="COLOR"]/block/field[@name="COLOR"]'
                ).text
                for block in color_blocks
            ],
            ['#ff0000', '#ffffff'],
        )
        self.assertTrue(all(
            block.find(
                './value[@name="OPA"]/shadow/field[@name="NUM"]'
            ).text == '255'
            for block in color_blocks
        ))
        self.assertEqual(report['summary']['ui_components'], 2)
        self.assertEqual(report['summary']['native_blocks'], 4)
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)
        self.assertEqual(report['summary']['raw_top_level_blocks'], 0)
        self.assertEqual(report['strategy'], 'best-effort-native')
        note_codes = [note['code'] for note in report['notes']]
        self.assertEqual(note_codes.count('profile_import_normalized'), 4)
        self.assertEqual(note_codes.count('constant_inlined'), 4)
        self.assertIn('module_docstring_omitted', note_codes)
        self.assertIsNone(root.find('./block[@type="execute_code_import"]'))

    def test_global_declarations_are_derived_from_workspace_variables(self):
        source = '''\
count = 0
def setup():
    global count
    count = 0
def loop():
    global count
    count += 1
'''
        project, report = best_effort_convert(source)
        root = xml_root(project)
        self.assertEqual(
            {variable.text for variable in root.findall('./variables/variable')},
            {'count'},
        )
        self.assertEqual(
            len(root.findall('.//block[@type="variables_set"]')),
            2,
        )
        raw_code = '\n'.join(
            field.text or ''
            for field in root.findall('.//field[@name="CODE"]')
        )
        self.assertNotIn('global count', raw_code)
        self.assertIsNone(root.find('./block[@type="execute_code_import"]'))
        codes = [note['code'] for note in report['notes']]
        self.assertEqual(codes.count('global_declaration_normalized'), 2)
        self.assertIn('top_level_declaration_normalized', codes)
        self.assertEqual(report['summary']['raw_statement_blocks'], 0)
        self.assertEqual(report['summary']['raw_top_level_blocks'], 0)

    def test_invalid_python_is_rejected(self):
        with self.assertRaises(BestEffortError):
            best_effort_convert('def broken(:\n')

    def test_report_is_json_and_markdown_serializable(self):
        _, report = best_effort_convert('print("hello")\n')
        json.dumps(report)
        rendered = markdown_report(report)
        self.assertIn('whole-module-raw', rendered)
        self.assertIn('意味・動作の差', rendered)


if __name__ == '__main__':
    unittest.main()
