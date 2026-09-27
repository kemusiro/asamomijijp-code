"""Best-effort MicroPython -> UiFlow2 project conversion with explicit notes."""

import argparse
import ast
import copy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import textwrap
import xml.etree.ElementTree as ET

from convert import (
    PROFILE,
    TEMPLATE,
    TEMPLATE_SHA,
    ConversionError,
    convert as strict_convert,
)

MAX_CONTROL_DEPTH = 2


class BestEffortError(ValueError):
    pass


class UnsupportedBlock(ValueError):
    """A valid Python subtree that this prototype cannot express as normal blocks."""


@dataclass
class Note:
    severity: str
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    source: str | None = None
    emitted_as: str | None = None
    semantic_difference: str | None = None


def node_location(node):
    return getattr(node, 'lineno', None), (
        getattr(node, 'col_offset', None) + 1
        if getattr(node, 'col_offset', None) is not None else None
    )


def source_text(source, node):
    segment = ast.get_source_segment(source, node, padded=True)
    return textwrap.dedent(segment) if segment is not None else ast.unparse(node)


def call_name(call):
    parts = []
    node = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return '.'.join(reversed(parts))


def is_no_arg_function(node, name):
    if not isinstance(node, ast.FunctionDef) or node.name != name:
        return False
    args = node.args
    return not (
        args.posonlyargs or args.args or args.kwonlyargs or args.vararg
        or args.kwarg or args.defaults or args.kw_defaults
        or node.decorator_list or node.returns or node.type_comment
        or getattr(node, 'type_params', [])
    )


def is_main_guard(node):
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == '__name__'
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Eq)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == '__main__'
    )


def is_profile_bootstrap(node, phase):
    if isinstance(node, ast.Global):
        return set(node.names) <= {'page0', 'rgb_0'}
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        name = call_name(node.value)
        if phase == 'setup' and name in {
            'M5.begin', 'Widgets.setRotation', 'm5ui.init', 'page0.screen_load'
        }:
            return True
        if phase == 'loop' and name == 'M5.update':
            return True
    if phase == 'setup' and isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in {'page0', 'rgb_0'}:
            if isinstance(node.value, ast.Call):
                return call_name(node.value) in {'m5ui.M5Page', 'RGBUnit'}
    return False


def native_operation(node):
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        return None
    call = node.value
    name = call_name(call)
    if name not in {'time.sleep', 'rgb_0.fill_color'}:
        return None
    if call.keywords or len(call.args) != 1 or not isinstance(call.args[0], ast.Constant):
        return None
    value = call.args[0].value
    maximum = 86400 if name == 'time.sleep' else 0xFFFFFF
    if type(value) is not int or not 0 <= value <= maximum:
        return None
    return name, value


def numeric_literal(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) in (int, float)):
        return node.operand.value if isinstance(node.op, ast.UAdd) else -node.operand.value
    return None


class ProjectBuilder:
    def __init__(self):
        raw = TEMPLATE.read_bytes()
        if hashlib.sha256(raw).hexdigest() != TEMPLATE_SHA:
            raise BestEffortError('unverified template')
        self.project = json.loads(raw)
        self.root = ET.fromstring('<xml>' + self.project['blockly'] + '</xml>')
        self.page = self.root.find('.//block[@type="lvgl_page_screen_load"]')
        self.update = self.root.find('.//block[@type="system_m5_update"]')
        if self.page is None or self.update is None:
            raise BestEffortError('verified template lacks setup or loop insertion point')
        self.prototypes = {
            kind: copy.deepcopy(self.root.find(f'.//block[@type="{kind}"]'))
            for kind in ('time_sleep_second', 'unit_rgb_set_fill_color')
        }
        for kind, block in self.prototypes.items():
            if block is None:
                raise BestEffortError(f'verified template lacks prototype {kind}')
        for tail in (self.page, self.update):
            for following in list(tail.findall('next')):
                tail.remove(following)
        self.tails = {'setup': self.page, 'loop': self.update}
        self.reserved = {element.get('id') for element in self.root.iter()
                         if element.get('id')}
        self.variables = self.root.find('./variables')
        if self.variables is None:
            self.variables = ET.Element('variables')
            self.root.insert(0, self.variables)
        self.variable_ids = {
            variable.text: variable.get('id')
            for variable in self.variables.findall('variable')
            if variable.text and variable.get('id')
        }
        self.serial = 0
        self.import_y = 700

    def new_id(self):
        while True:
            self.serial += 1
            identifier = f'py2blocks_approx_{self.serial}'
            if identifier not in self.reserved:
                self.reserved.add(identifier)
                return identifier

    def reidentify(self, block):
        for element in block.iter():
            if 'id' in element.attrib:
                element.set('id', self.new_id())

    def variable_id(self, name):
        if name not in self.variable_ids:
            identifier = self.new_id()
            variable = ET.SubElement(self.variables, 'variable', {'id': identifier})
            variable.text = name
            self.variable_ids[name] = identifier
        return self.variable_ids[name]

    def field(self, parent, name, text, **attributes):
        field = ET.SubElement(parent, 'field', {'name': name, **attributes})
        field.text = str(text)
        return field

    def value(self, parent, name, block):
        ET.SubElement(parent, 'value', {'name': name}).append(block)

    def statement(self, parent, name, block):
        if block is not None:
            ET.SubElement(parent, 'statement', {'name': name}).append(block)

    def chain(self, blocks):
        blocks = [block for block in blocks if block is not None]
        for left, right in zip(blocks, blocks[1:]):
            ET.SubElement(left, 'next').append(right)
        return blocks[0] if blocks else None

    def append_statement_block(self, phase, block):
        for following in list(block.findall('next')):
            block.remove(following)
        ET.SubElement(self.tails[phase], 'next').append(block)
        self.tails[phase] = block

    def make_native(self, operation):
        name, value = operation
        kind = 'time_sleep_second' if name == 'time.sleep' else 'unit_rgb_set_fill_color'
        block = copy.deepcopy(self.prototypes[kind])
        for following in list(block.findall('next')):
            block.remove(following)
        self.reidentify(block)
        if name == 'time.sleep':
            block.find('./value/shadow/field[@name="NUM"]').text = str(value)
        else:
            block.find('./value/block/field[@name="COLOR"]').text = f'#{value:06x}'
        return block

    def make_raw_statement(self, code):
        block = ET.Element('block', {'type': 'execute_code', 'id': self.new_id()})
        field = ET.SubElement(block, 'field', {'name': 'CODE'})
        field.text = code
        return block

    def append_raw_top_level(self, code):
        block = ET.Element('block', {
            'type': 'execute_code_import',
            'id': self.new_id(),
            'x': '50',
            'y': str(self.import_y),
        })
        self.import_y += 120
        field = ET.SubElement(block, 'field', {'name': 'CODE'})
        field.text = code
        self.root.append(block)

    def finish(self):
        self.project['blockly'] = ''.join(
            ET.tostring(element, encoding='unicode') for element in self.root
        )
        return self.project


class FlowConverter:
    """Convert a deliberately small Python control-flow subset to Blockly XML."""

    def __init__(self, builder, source, notes, counts, phase):
        self.builder = builder
        self.source = source
        self.notes = notes
        self.counts = counts
        self.phase = phase

    def block(self, kind):
        return ET.Element('block', {'type': kind, 'id': self.builder.new_id()})

    def number(self, value):
        block = self.block('math_number')
        ET.SubElement(block, 'mutation', {
            'max': 'Infinity', 'min': '-Infinity', 'precision': '0'
        })
        self.builder.field(block, 'NUM', value)
        return block

    def variable_get(self, name):
        block = self.block('variables_get')
        self.builder.field(block, 'VAR', name, id=self.builder.variable_id(name))
        return block

    def expression(self, node):
        literal = numeric_literal(node)
        if literal is not None:
            return self.number(literal)
        if isinstance(node, ast.Constant):
            if type(node.value) is bool:
                block = self.block('logic_boolean')
                self.builder.field(block, 'BOOL', 'TRUE' if node.value else 'FALSE')
                return block
            if isinstance(node.value, str):
                block = self.block('text')
                self.builder.field(block, 'TEXT', node.value)
                return block
            raise UnsupportedBlock('only numeric, Boolean, and string literals are supported')
        if isinstance(node, ast.Name):
            return self.variable_get(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            block = self.block('logic_negate')
            self.builder.value(block, 'BOOL', self.expression(node.operand))
            return block
        if isinstance(node, ast.BinOp):
            operators = {
                ast.Add: 'ADD', ast.Sub: 'MINUS', ast.Mult: 'MULTIPLY',
                ast.Div: 'DIVIDE', ast.Pow: 'POWER',
            }
            if type(node.op) in operators:
                block = self.block('math_arithmetic')
                self.builder.field(block, 'OP', operators[type(node.op)])
                self.builder.value(block, 'A', self.expression(node.left))
                self.builder.value(block, 'B', self.expression(node.right))
                return block
            if isinstance(node.op, ast.Mod):
                block = self.block('math_modulo')
                self.builder.value(block, 'DIVIDEND', self.expression(node.left))
                self.builder.value(block, 'DIVISOR', self.expression(node.right))
                return block
            raise UnsupportedBlock(f'unsupported binary operator: {type(node.op).__name__}')
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise UnsupportedBlock('chained comparisons are unsupported')
            operators = {
                ast.Eq: 'EQ', ast.NotEq: 'NEQ', ast.Lt: 'LT',
                ast.LtE: 'LTE', ast.Gt: 'GT', ast.GtE: 'GTE',
            }
            if type(node.ops[0]) not in operators:
                raise UnsupportedBlock(
                    f'unsupported comparison operator: {type(node.ops[0]).__name__}')
            block = self.block('logic_compare')
            self.builder.field(block, 'OP', operators[type(node.ops[0])])
            self.builder.value(block, 'A', self.expression(node.left))
            self.builder.value(block, 'B', self.expression(node.comparators[0]))
            return block
        if isinstance(node, ast.BoolOp):
            if len(node.values) < 2:
                raise UnsupportedBlock('Boolean expression has fewer than two operands')
            option = 'AND' if isinstance(node.op, ast.And) else 'OR'
            result = self.expression(node.values[0])
            for value in node.values[1:]:
                block = self.block('logic_operation')
                self.builder.field(block, 'OP', option)
                self.builder.value(block, 'A', result)
                self.builder.value(block, 'B', self.expression(value))
                result = block
            return result
        raise UnsupportedBlock(f'unsupported expression: {type(node).__name__}')

    def raw(self, node, code, message, difference, reason_code='statement_raw_fallback'):
        self.counts['raw_statement_blocks'] += 1
        line, column = node_location(node)
        self.notes.append(Note(
            'warning', reason_code, message, line, column,
            source_text(self.source, node), 'execute_code', difference,
        ))
        return self.builder.make_raw_statement(code)

    def unsupported_control(self, node, reason):
        return self.raw(
            node,
            ast.unparse(node),
            f'{type(node).__name__} is kept as one Python code block: {reason}.',
            'The control structure and its complete subtree are editable as Python text rather than ordinary blocks.',
            'unsupported_control_fallback',
        )

    def depth_fallback(self, node, depth):
        self.counts['control_depth_fallback_blocks'] += 1
        return self.raw(
            node,
            ast.unparse(node),
            f'Control depth {depth} exceeds the configured maximum {MAX_CONTROL_DEPTH}.',
            'The complete depth-limited subtree is kept in one Python code block.',
            'control_depth_limit',
        )

    def sequence(self, statements, control_depth):
        return self.builder.chain([
            self.statement(statement, control_depth) for statement in statements
        ])

    def assignment(self, node):
        if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            raise UnsupportedBlock('only assignment to one simple variable is supported')
        target = node.targets[0].id
        block = self.block('variables_set')
        self.builder.field(block, 'VAR', target, id=self.builder.variable_id(target))
        self.builder.value(block, 'VALUE', self.expression(node.value))
        return block

    def augmented_assignment(self, node):
        if not isinstance(node.target, ast.Name):
            raise UnsupportedBlock('augmented assignment target must be a simple variable')
        operators = {
            ast.Add: 'ADD', ast.Sub: 'MINUS', ast.Mult: 'MULTIPLY',
            ast.Div: 'DIVIDE', ast.Pow: 'POWER',
        }
        if type(node.op) not in operators:
            raise UnsupportedBlock(
                f'unsupported augmented assignment operator: {type(node.op).__name__}')
        name = node.target.id
        value = self.block('math_arithmetic')
        self.builder.field(value, 'OP', operators[type(node.op)])
        self.builder.value(value, 'A', self.variable_get(name))
        self.builder.value(value, 'B', self.expression(node.value))
        block = self.block('variables_set')
        self.builder.field(block, 'VAR', name, id=self.builder.variable_id(name))
        self.builder.value(block, 'VALUE', value)
        return block

    def if_block(self, node, depth):
        branches = []
        current = node
        while True:
            branches.append((current.test, current.body))
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                current = current.orelse[0]
                continue
            else_body = current.orelse
            break
        conditions = [self.expression(condition) for condition, _ in branches]
        block = self.block('controls_if')
        mutation_attributes = {}
        if len(branches) > 1:
            mutation_attributes['elseif'] = str(len(branches) - 1)
        if else_body:
            mutation_attributes['else'] = '1'
        if mutation_attributes:
            ET.SubElement(block, 'mutation', mutation_attributes)
        for index, ((_, body), condition) in enumerate(zip(branches, conditions)):
            self.builder.value(block, f'IF{index}', condition)
            self.builder.statement(block, f'DO{index}', self.sequence(body, depth))
        if else_body:
            self.builder.statement(block, 'ELSE', self.sequence(else_body, depth))
        return block

    def while_block(self, node, depth):
        if node.orelse:
            raise UnsupportedBlock('while ... else is outside the supported subset')
        condition = self.expression(node.test)
        block = self.block('controls_whileUntil')
        self.builder.field(block, 'MODE', 'WHILE')
        self.builder.value(block, 'BOOL', condition)
        self.builder.statement(block, 'DO', self.sequence(node.body, depth))
        return block

    def for_block(self, node, depth):
        if node.orelse:
            raise UnsupportedBlock('for ... else is outside the supported subset')
        if not isinstance(node.target, ast.Name):
            raise UnsupportedBlock('for target must be one simple variable')
        name = node.target.id
        variable_id = self.builder.variable_id(name)
        iterator = node.iter
        if (isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name)
                and iterator.func.id == 'range'):
            if iterator.keywords or not 1 <= len(iterator.args) <= 3:
                raise UnsupportedBlock('range() requires one to three positional arguments')
            if len(iterator.args) == 1:
                value = self.expression(iterator.args[0])
                body = self.sequence(node.body, depth)
                block = self.block('controls_for_range')
                self.builder.field(block, 'VAR', name, id=variable_id)
                self.builder.value(block, 'VALUE', value)
                self.builder.statement(block, 'DO', body)
                return block
            start, stop = iterator.args[:2]
            step_value = 1 if len(iterator.args) == 2 else numeric_literal(iterator.args[2])
            if type(step_value) is not int or step_value == 0:
                raise UnsupportedBlock('range() step must be a nonzero integer literal')
            adjustment = ast.Constant(value=-1 if step_value > 0 else 1)
            inclusive_stop = ast.BinOp(left=stop, op=ast.Add(), right=adjustment)
            start_block = self.expression(start)
            stop_block = self.expression(inclusive_stop)
            body = self.sequence(node.body, depth)
            block = self.block('controls_for')
            self.builder.field(block, 'VAR', name, id=variable_id)
            self.builder.value(block, 'FROM', start_block)
            self.builder.value(block, 'TO', stop_block)
            self.builder.value(block, 'BY', self.number(step_value))
            self.builder.statement(block, 'DO', body)
            return block
        iterable = self.expression(iterator)
        body = self.sequence(node.body, depth)
        block = self.block('controls_forEach')
        self.builder.field(block, 'VAR', name, id=variable_id)
        self.builder.value(block, 'LIST', iterable)
        self.builder.statement(block, 'DO', body)
        return block

    def control(self, node, control_depth):
        depth = control_depth + 1
        if depth > MAX_CONTROL_DEPTH:
            return self.depth_fallback(node, depth)
        try:
            if isinstance(node, ast.If):
                block = self.if_block(node, depth)
            elif isinstance(node, ast.For):
                block = self.for_block(node, depth)
            elif isinstance(node, ast.While):
                block = self.while_block(node, depth)
            else:
                raise UnsupportedBlock(f'unsupported control statement: {type(node).__name__}')
        except UnsupportedBlock as exc:
            return self.unsupported_control(node, str(exc))
        self.counts['structured_control_blocks'] += 1
        return block

    def statement(self, node, control_depth):
        if isinstance(node, ast.Pass):
            self.counts['skipped_nodes'] += 1
            return None
        operation = native_operation(node)
        if operation is not None:
            self.counts['native_blocks'] += 1
            return self.builder.make_native(operation)
        if isinstance(node, (ast.If, ast.For, ast.While)):
            return self.control(node, control_depth)
        try:
            if isinstance(node, ast.Assign):
                return self.assignment(node)
            if isinstance(node, ast.AugAssign):
                return self.augmented_assignment(node)
        except UnsupportedBlock as exc:
            return self.raw(
                node, ast.unparse(node),
                f'Unsupported {self.phase} statement is preserved as Python: {exc}.',
                'The statement remains Python text because one of its expressions cannot be represented by the supported ordinary blocks.',
            )
        return self.raw(
            node, ast.unparse(node),
            f'Unsupported {self.phase} statement is preserved as Python in a code block.',
            'The statement is editable as Python text rather than ordinary blocks; formatting and comments are normalized by AST unparsing.',
        )


def make_report(source, strategy, strict_error, notes, counts):
    return {
        'schema': 1,
        'converter': 'uiflow2-python-to-blocks-best-effort-v1',
        'profile': PROFILE,
        'max_control_depth': MAX_CONTROL_DEPTH,
        'source_sha256': hashlib.sha256(source.encode('utf-8')).hexdigest(),
        'strategy': strategy,
        'strict_conversion_error': strict_error,
        'summary': counts,
        'notes': [asdict(note) for note in notes],
        'global_limitations': [
            'UiFlow2 and profile bootstrap code may be added or normalized.',
            'Raw-code blocks preserve Python text but are not decomposed into ordinary blocks.',
            f'Control structures are converted to ordinary blocks through depth {MAX_CONTROL_DEPTH}; deeper subtrees become one raw-code block.',
            'Comments, formatting, exact exception timing, and global/local scope may differ.',
            'The Core2 V2.5.3 Web IDE exposes execute_code_import and execute_code blocks, but import and round-trip of this converter output remain to be verified.',
            'The output always includes the verified Core2 page0 and Port A RGB Unit template.',
        ],
    }


def strict_first(source):
    try:
        project = strict_convert(source)
    except ConversionError as exc:
        return None, str(exc)
    root = ET.fromstring('<xml>' + project['blockly'] + '</xml>')
    native_blocks = sum(
        len(root.findall(f'.//block[@type="{kind}"]'))
        for kind in ('time_sleep_second', 'unit_rgb_set_fill_color')
    )
    report = make_report(
        source,
        'strict-native',
        None,
        [Note(
            'info',
            'strict_conversion_succeeded',
            'The existing strict converter accepted the complete input.',
            emitted_as='ordinary UiFlow2 blocks',
            semantic_difference='Profile bootstrap and block layout are normalized.',
        )],
        {
            'native_blocks': native_blocks,
            'structured_control_blocks': 0,
            'control_depth_fallback_blocks': 0,
            'raw_statement_blocks': 0,
            'raw_top_level_blocks': 0,
            'skipped_nodes': 0,
        },
    )
    return (project, report), None


def best_effort_convert(source):
    try:
        tree = ast.parse(source, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno or '?'
        column = exc.offset or '?'
        raise BestEffortError(f'line {line}, column {column}: {exc.msg}') from exc

    strict_result, strict_error = strict_first(source)
    if strict_result is not None:
        return strict_result

    setup = next((node for node in tree.body if is_no_arg_function(node, 'setup')), None)
    loop = next((node for node in tree.body if is_no_arg_function(node, 'loop')), None)
    builder = ProjectBuilder()
    notes = []
    counts = {
        'native_blocks': 0,
        'structured_control_blocks': 0,
        'control_depth_fallback_blocks': 0,
        'raw_statement_blocks': 0,
        'raw_top_level_blocks': 0,
        'skipped_nodes': 0,
    }

    if setup is None or loop is None:
        builder.append_raw_top_level(source.rstrip() or 'pass')
        counts['raw_top_level_blocks'] += 1
        notes.extend([
            Note(
                'warning',
                'whole_module_raw_fallback',
                'No supported no-argument setup()/loop() pair was found; the complete source is kept in one top-level code block.',
                emitted_as='execute_code_import',
                semantic_difference='The program is not decomposed into ordinary blocks. UiFlow2 bootstrap code is also generated and may be unreachable or may run after the source.',
            ),
            Note(
                'warning',
                'generated_main_coexists',
                'UiFlow2 will still generate its own setup(), loop(), and main loop from the template.',
                emitted_as='profile bootstrap',
                semantic_difference='Definitions or main-loop behavior in the raw source can shadow, block, or coexist with generated code.',
            ),
        ])
        report = make_report(source, 'whole-module-raw', strict_error, notes, counts)
        return builder.finish(), report

    top_level = []
    for node in tree.body:
        if node is setup or node is loop:
            continue
        if is_main_guard(node):
            line, column = node_location(node)
            notes.append(Note(
                'warning',
                'main_guard_replaced',
                'The source __main__ guard is replaced by the fixed UiFlow2 main loop.',
                line,
                column,
                source_text(source, node),
                'profile main loop',
                'Exception handling, loop termination, and calls around setup()/loop() may differ.',
            ))
            counts['skipped_nodes'] += 1
            continue
        top_level.append(source_text(source, node))
    if top_level:
        builder.append_raw_top_level('\n\n'.join(top_level))
        counts['raw_top_level_blocks'] += 1
        first = next(node for node in tree.body
                     if node is not setup and node is not loop and not is_main_guard(node))
        line, column = node_location(first)
        notes.append(Note(
            'warning',
            'top_level_raw_code',
            'Imports, globals, helper definitions, and other module statements are grouped into a top-level code block.',
            line,
            column,
            emitted_as='execute_code_import',
            semantic_difference='Leading comments and exact spacing between top-level statements may be lost; execution order relative to generated imports can differ.',
        ))

    for phase, function in (('setup', setup), ('loop', loop)):
        converter = FlowConverter(builder, source, notes, counts, phase)
        for node in function.body:
            if is_profile_bootstrap(node, phase):
                line, column = node_location(node)
                notes.append(Note(
                    'info',
                    'profile_bootstrap_normalized',
                    f'{phase} bootstrap statement is supplied by the fixed profile.',
                    line,
                    column,
                    source_text(source, node),
                    'profile bootstrap',
                    'Arguments that differ from the fixed Core2/page0/RGB profile are not preserved.',
                ))
                counts['skipped_nodes'] += 1
                continue
            block = converter.statement(node, 0)
            if block is not None:
                builder.append_statement_block(phase, block)

    report = make_report(source, 'hybrid-native-and-raw', strict_error, notes, counts)
    return builder.finish(), report


def markdown_report(report):
    lines = [
        '# Best-effort変換注記',
        '',
        f'- Profile: `{report["profile"]}`',
        f'- Maximum control depth: `{report["max_control_depth"]}`',
        f'- Strategy: `{report["strategy"]}`',
        f'- Source SHA-256: `{report["source_sha256"]}`',
        '',
        '## 集計',
        '',
    ]
    for key, value in report['summary'].items():
        lines.append(f'- `{key}`: `{value}`')
    lines.extend(['', '## 個別注記', ''])
    if not report['notes']:
        lines.append('- なし')
    for index, note in enumerate(report['notes'], 1):
        location = ''
        if note['line'] is not None:
            location = f'（line {note["line"]}'
            if note['column'] is not None:
                location += f', column {note["column"]}'
            location += '）'
        lines.extend([
            f'### {index}. `{note["code"]}` {location}',
            '',
            f'- 重要度: `{note["severity"]}`',
            f'- 内容: {note["message"]}',
        ])
        if note['emitted_as']:
            lines.append(f'- 出力: `{note["emitted_as"]}`')
        if note['semantic_difference']:
            lines.append(f'- 意味・動作の差: {note["semantic_difference"]}')
        if note['source']:
            lines.extend(['- 対象コード:', '', '```python', note['source'], '```'])
        lines.append('')
    lines.extend(['## 全体制約', ''])
    lines.extend(f'- {item}' for item in report['global_limitations'])
    lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--notes-json', type=Path)
    parser.add_argument('--notes-md', type=Path)
    args = parser.parse_args()
    notes_json = args.notes_json or args.output.with_suffix('.notes.json')
    notes_md = args.notes_md or args.output.with_suffix('.notes.md')
    try:
        source = args.source.read_text(encoding='utf-8')
        project, report = best_effort_convert(source)
        outputs = (args.output, notes_json, notes_md)
        existing = [str(path) for path in outputs if path.exists()]
        if existing:
            raise OSError('output already exists: ' + ', '.join(existing))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(project, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        with notes_json.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        notes_md.write_text(markdown_report(report), encoding='utf-8')
    except (BestEffortError, ConversionError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
