"""UiFlow2 V2.5.3 Core2 Python -> editable project; never executes input."""
import argparse
import ast
import copy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import tokenize
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / 'fixtures/06-port-a.m5f2'
TEMPLATE_SHA = json.loads((BASE / 'fixtures/SHA256.json').read_text())['06-port-a.m5f2']
PROFILE_SPEC = json.loads((BASE / 'profile.json').read_text())

PROFILE = PROFILE_SPEC['id']
FIRMWARE = PROFILE_SPEC['uiflow']['firmware']
UNIT_SPEC = PROFILE_SPEC['unit']
PROFILE_PORT = UNIT_SPEC['profile_port']
RGB_PINS = tuple(PROFILE_PORT['pins'])
DIRECTIVE_PREFIXES = {
    'convert': '# uiflow2-convert:',
    'unit': '# uiflow2-unit:',
    'page': '# uiflow2-page:',
}


class ConversionError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedProgram:
    operations: dict
    mode: str
    metadata: dict | None = None


def location(node):
    line = getattr(node, 'lineno', '?')
    column = getattr(node, 'col_offset', None)
    return f'line {line}' if column is None else f'line {line}, column {column + 1}'


def fail(node, reason):
    raise ConversionError(f'{location(node)}: {reason}')


def same_ast(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def parse_json_directives(source):
    """Read converter directives from real comments, not strings."""
    found = {kind: [] for kind in DIRECTIVE_PREFIXES}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            for kind, prefix in DIRECTIVE_PREFIXES.items():
                if token.string.startswith(prefix):
                    payload = token.string[len(prefix):].strip()
                    try:
                        value = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        raise ConversionError(
                            f'line {token.start[0]}, column {token.start[1] + 1}: '
                            f'invalid {kind} directive JSON: {exc.msg}') from exc
                    if not isinstance(value, dict):
                        raise ConversionError(
                            f'line {token.start[0]}, column {token.start[1] + 1}: '
                            f'{kind} directive must contain a JSON object')
                    found[kind].append((token, value))
                    break
    except tokenize.TokenError as exc:
        raise ConversionError(f'tokenization failed: {exc}') from exc
    return found


def require_keys(token, value, kind, keys):
    actual = set(value)
    expected = set(keys)
    if actual != expected:
        missing = ', '.join(sorted(expected - actual)) or 'none'
        unknown = ', '.join(sorted(actual - expected)) or 'none'
        raise ConversionError(
            f'line {token.start[0]}, column {token.start[1] + 1}: '
            f'{kind} directive fields differ; missing: {missing}; unknown: {unknown}')


def validate_metadata(directives):
    for kind, values in directives.items():
        if len(values) != 1:
            raise ConversionError(f'generated mode requires exactly one {kind} directive')

    convert_token, convert = directives['convert'][0]
    require_keys(convert_token, convert, 'convert', ('schema', 'profile', 'firmware'))
    if type(convert['schema']) is not int or convert['schema'] != 1:
        raise ConversionError(f'line {convert_token.start[0]}: unsupported metadata schema')
    if convert['profile'] != PROFILE:
        raise ConversionError(f'line {convert_token.start[0]}: profile must be {PROFILE!r}')
    if convert['firmware'] != FIRMWARE:
        raise ConversionError(f'line {convert_token.start[0]}: firmware must be {FIRMWARE!r}')

    unit_token, unit = directives['unit'][0]
    require_keys(unit_token, unit, 'unit', ('name', 'type', 'port', 'leds'))
    expected_unit = {
        'name': 'rgb_0',
        'type': 'rgb',
        'port': PROFILE_PORT['name'],
        'leds': UNIT_SPEC['led_count'],
    }
    if unit != expected_unit:
        raise ConversionError(
            f'line {unit_token.start[0]}: this prototype requires unit metadata {expected_unit}')

    page_token, page = directives['page'][0]
    require_keys(page_token, page, 'page', ('name', 'rotation', 'background'))
    if page['name'] != 'page0':
        raise ConversionError(f'line {page_token.start[0]}: page name must be "page0"')
    if type(page['rotation']) is not int or not 0 <= page['rotation'] <= 3:
        raise ConversionError(f'line {page_token.start[0]}: rotation must be an integer in 0..3')
    if not isinstance(page['background'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', page['background']):
        raise ConversionError(f'line {page_token.start[0]}: background must be #RRGGBB')
    page = dict(page)
    page['background'] = page['background'].lower()
    return {'convert': convert, 'unit': unit, 'page': page}


def validate_function_definition(function):
    if (function.decorator_list or function.returns or function.type_comment
            or getattr(function, 'type_params', [])
            or not same_ast(function.args, ast.parse('def f(): pass').body[0].args)):
        fail(function, 'parameters, annotations and decorators are unsupported')


def parse_operations(statements, phase):
    operations = []
    for statement in statements:
        if isinstance(statement, ast.Pass) and len(statements) == 1:
            continue
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            fail(statement, f'unsupported statement in {phase}; expected a supported call')
        call = statement.value
        if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)):
            fail(call, 'unsupported call target')
        name = call.func.value.id + '.' + call.func.attr
        if name not in ('time.sleep', 'rgb_0.fill_color'):
            fail(call, 'unsupported call: ' + name)
        if call.keywords or len(call.args) != 1 or not isinstance(call.args[0], ast.Constant):
            fail(call, 'exactly one positional literal argument required')
        value = call.args[0].value
        maximum = 86400 if name == 'time.sleep' else 0xffffff
        if type(value) is not int or not 0 <= value <= maximum:
            fail(call, f'argument must be an integer in 0..{maximum}')
        operations.append((name, value))
    return operations


def parse_compact(tree):
    if len(tree.body) != 3 or not same_ast(tree.body[0], ast.parse('import time').body[0]):
        raise ConversionError('expected import time, def setup(), def loop() only')
    result = {}
    for function in tree.body[1:]:
        if not isinstance(function, ast.FunctionDef) or function.name not in ('setup', 'loop'):
            fail(function, 'only setup and loop definitions are supported')
        if function.name in result:
            fail(function, 'duplicate function')
        validate_function_definition(function)
        result[function.name] = parse_operations(function.body, function.name)
    if set(result) != {'setup', 'loop'}:
        raise ConversionError('both setup and loop are required')
    return ParsedProgram(result, 'compact')


GENERATED_IMPORTS = ast.parse('''\
import os, sys, io
import M5
from M5 import *
import m5ui
import lvgl as lv
from unit import RGBUnit
import time
''').body

GENERATED_GLOBALS = ast.parse('''\
page0 = None
rgb_0 = None
''').body

GENERATED_MAIN = ast.parse('''\
if __name__ == '__main__':
  try:
    setup()
    while True:
      loop()
  except (Exception, KeyboardInterrupt) as e:
    try:
      m5ui.deinit()
      from utility import print_error_msg
      print_error_msg(e)
    except ImportError:
      print("please update to latest firmware")
''').body[0]


def require_sequence(actual, expected, label):
    if len(actual) < len(expected):
        raise ConversionError(f'{label} is incomplete')
    for index, (left, right) in enumerate(zip(actual, expected), 1):
        if not same_ast(left, right):
            fail(left, f'{label} differs at statement {index}')


def generated_setup_prefix(metadata):
    rotation = metadata['page']['rotation']
    background = int(metadata['page']['background'][1:], 16)
    pin0, pin1 = RGB_PINS
    leds = UNIT_SPEC['led_count']
    return ast.parse(f'''\
global page0, rgb_0
M5.begin()
Widgets.setRotation({rotation})
m5ui.init()
page0 = m5ui.M5Page(bg_c={background})
rgb_0 = RGBUnit(({pin0}, {pin1}), {leds})
page0.screen_load()
''').body


GENERATED_LOOP_PREFIX = ast.parse('''\
global page0, rgb_0
M5.update()
''').body


def parse_generated(tree, directives):
    metadata = validate_metadata(directives)
    expected_length = len(GENERATED_IMPORTS) + len(GENERATED_GLOBALS) + 3
    if len(tree.body) != expected_length:
        raise ConversionError('generated mode contains missing or extra top-level statements')

    position = 0
    imports = tree.body[position:position + len(GENERATED_IMPORTS)]
    require_sequence(imports, GENERATED_IMPORTS, 'generated import preamble')
    position += len(GENERATED_IMPORTS)
    globals_ = tree.body[position:position + len(GENERATED_GLOBALS)]
    require_sequence(globals_, GENERATED_GLOBALS, 'generated global declarations')
    position += len(GENERATED_GLOBALS)

    setup = tree.body[position]
    loop = tree.body[position + 1]
    main = tree.body[position + 2]
    if not isinstance(setup, ast.FunctionDef) or setup.name != 'setup':
        fail(setup, 'expected generated setup() definition')
    if not isinstance(loop, ast.FunctionDef) or loop.name != 'loop':
        fail(loop, 'expected generated loop() definition')
    validate_function_definition(setup)
    validate_function_definition(loop)
    if not same_ast(main, GENERATED_MAIN):
        fail(main, 'generated main loop differs from the V2.5.3 profile')

    setup_prefix = generated_setup_prefix(metadata)
    require_sequence(setup.body, setup_prefix,
                     'setup bootstrap or metadata-derived Core2/RGB/page configuration')
    require_sequence(loop.body, GENERATED_LOOP_PREFIX, 'loop bootstrap')
    operations = {
        'setup': parse_operations(setup.body[len(setup_prefix):], 'setup'),
        'loop': parse_operations(loop.body[len(GENERATED_LOOP_PREFIX):], 'loop'),
    }
    return ParsedProgram(operations, 'generated', metadata)


def parse_program(source):
    """Parse compact input or an exact V2.5.3 generated-program profile."""
    directives = parse_json_directives(source)
    try:
        tree = ast.parse(source, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno or '?'
        column = exc.offset or '?'
        raise ConversionError(f'line {line}, column {column}: {exc.msg}') from exc
    has_generated_markers = any(
        isinstance(node, (ast.If, ast.Assign))
        or isinstance(node, ast.Import) and any(alias.name in ('M5', 'm5ui', 'lvgl') for alias in node.names)
        or isinstance(node, ast.ImportFrom) and node.module in ('M5', 'unit')
        for node in tree.body
    )
    if has_generated_markers or any(directives.values()):
        return parse_generated(tree, directives)
    return parse_compact(tree)


def parse(source):
    """Backward-compatible operation parser used by the first prototype tests."""
    return parse_program(source).operations


def apply_page_metadata(project, metadata):
    if metadata is None:
        return
    page = metadata['page']
    component = next((item for item in project['components'] if item.get('name') == 'page0'), None)
    screen = next((item for item in project['screen'] if item.get('id') == 'builtin'), None)
    if component is None or screen is None:
        raise ConversionError('verified template lacks the expected page0 or builtin screen')
    component['backgroundColor'] = page['background']
    screen['rotation'] = page['rotation']


def convert(source, template_bytes=None):
    program = parse_program(source)
    raw = TEMPLATE.read_bytes() if template_bytes is None else template_bytes
    if hashlib.sha256(raw).hexdigest() != TEMPLATE_SHA:
        raise ConversionError('unverified template: this prototype accepts only fixtures/06-port-a.m5f2')
    project = json.loads(raw)
    apply_page_metadata(project, program.metadata)
    root = ET.fromstring('<xml>' + project['blockly'] + '</xml>')
    prototypes = {kind: copy.deepcopy(root.find(f'.//block[@type="{kind}"]'))
                  for kind in ('time_sleep_second', 'unit_rgb_set_fill_color')}
    page = root.find('.//block[@type="lvgl_page_screen_load"]')
    update = root.find('.//block[@type="system_m5_update"]')
    for tail in (page, update):
        for following in list(tail.findall('next')):
            tail.remove(following)
    reserved = {e.get('id') for e in root.iter() if e.get('id')}
    serial = 0
    for phase, tail in (('setup', page), ('loop', update)):
        for name, value in program.operations[phase]:
            kind = 'time_sleep_second' if name == 'time.sleep' else 'unit_rgb_set_fill_color'
            block = copy.deepcopy(prototypes[kind])
            for nxt in list(block.findall('next')):
                block.remove(nxt)
            for element in block.iter():
                if 'id' in element.attrib:
                    serial += 1
                    identifier = f'py2blocks_{serial}'
                    if identifier in reserved:
                        raise ConversionError('generated ID collision')
                    reserved.add(identifier)
                    element.set('id', identifier)
            if name == 'time.sleep':
                block.find('./value/shadow/field[@name="NUM"]').text = str(value)
            else:
                block.find('./value/block/field[@name="COLOR"]').text = f'#{value:06x}'
            ET.SubElement(tail, 'next').append(block)
            tail = block
    project['blockly'] = ''.join(ET.tostring(e, encoding='unicode') for e in root)
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        project = convert(args.source.read_text(encoding='utf-8'))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(project, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except ConversionError as exc:
        parser.exit(2, f'error: {args.source}:{exc}\n')
    except OSError as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
