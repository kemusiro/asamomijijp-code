"""Constrained Python body -> UiFlow2 V2.5.3 Core2 project; never executes input."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / 'fixtures/06-port-a.m5f2'
TEMPLATE_SHA = json.loads((BASE / 'fixtures/SHA256.json').read_text())['06-port-a.m5f2']


class ConversionError(ValueError):
    pass


def fail(node, reason):
    raise ConversionError(f'line {getattr(node, "lineno", "?")}: {reason}')


def parse(source):
    """Accept exactly import time + two parameterless functions with literal calls."""
    try:
        tree = ast.parse(source, type_comments=True)
    except SyntaxError as exc:
        raise ConversionError(str(exc)) from exc
    if len(tree.body) != 3 or ast.dump(tree.body[0]) != ast.dump(ast.parse('import time').body[0]):
        raise ConversionError('expected import time, def setup(), def loop() only')
    result = {}
    for function in tree.body[1:]:
        if not isinstance(function, ast.FunctionDef) or function.name not in ('setup', 'loop'):
            fail(function, 'only setup and loop definitions are supported')
        if function.name in result:
            fail(function, 'duplicate function')
        if (function.decorator_list or function.returns or function.type_comment
                or function.type_params
                or ast.dump(function.args) != ast.dump(ast.parse('def f(): pass').body[0].args)):
            fail(function, 'parameters, annotations and decorators are unsupported')
        operations = []
        for statement in function.body:
            if isinstance(statement, ast.Pass) and len(function.body) == 1:
                continue
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                fail(statement, 'expected a supported call with a literal argument')
            call = statement.value
            if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)):
                fail(call, 'unsupported call target')
            name = call.func.value.id + '.' + call.func.attr
            if name not in ('time.sleep', 'rgb_0.fill_color'):
                fail(call, 'unsupported call: ' + name)
            if call.keywords or len(call.args) != 1 or not isinstance(call.args[0], ast.Constant):
                fail(call, 'exactly one positional literal argument required')
            value = call.args[0].value
            # Integer seconds only in this first prototype; bool is not an integer here.
            maximum = 86400 if name == 'time.sleep' else 0xffffff
            if type(value) is not int or not 0 <= value <= maximum:
                fail(call, f'argument must be an integer in 0..{maximum}')
            operations.append((name, value))
        result[function.name] = operations
    if set(result) != {'setup', 'loop'}:
        raise ConversionError('both setup and loop are required')
    return result


def convert(source, template_bytes=None):
    operations = parse(source)
    raw = TEMPLATE.read_bytes() if template_bytes is None else template_bytes
    if hashlib.sha256(raw).hexdigest() != TEMPLATE_SHA:
        raise ConversionError('unverified template: this prototype accepts only fixtures/06-port-a.m5f2')
    project = json.loads(raw)
    root = ET.fromstring('<xml>' + project['blockly'] + '</xml>')
    prototypes = {kind: copy.deepcopy(root.find(f'.//block[@type="{kind}"]'))
                  for kind in ('time_sleep_second', 'unit_rgb_set_fill_color')}
    # Deliberately replace the sample program, retaining the observed bootstrap.
    page = root.find('.//block[@type="lvgl_page_screen_load"]')
    update = root.find('.//block[@type="system_m5_update"]')
    for tail in (page, update):
        for following in list(tail.findall('next')):
            tail.remove(following)
    reserved = {e.get('id') for e in root.iter() if e.get('id')}
    serial = 0
    for phase, tail in (('setup', page), ('loop', update)):
        for name, value in operations[phase]:
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
        # Never overwrite an existing output or input file.
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(project, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except (OSError, ConversionError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
