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
            'structured_control_blocks': 1,
            'control_depth_fallback_blocks': 0,
            'raw_statement_blocks': 2,
            'raw_top_level_blocks': 1,
            'skipped_nodes': 1,
        })
        self.assertEqual(len(root.findall('./block[@type="execute_code_import"]')), 1)
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
