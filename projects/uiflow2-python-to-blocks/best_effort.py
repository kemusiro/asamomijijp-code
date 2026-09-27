"""Best-effort MicroPython -> UiFlow2 project conversion with explicit notes."""

import argparse
import ast
import copy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import textwrap
import xml.etree.ElementTree as ET

from convert import (
    PROFILE,
    PROFILE_SPEC,
    TEMPLATE,
    TEMPLATE_SHA,
    ConversionError,
    convert as strict_convert,
)

MAX_CONTROL_DEPTH = 2
BUTTON_SPEC = PROFILE_SPEC['hardware']['button']
SUPPORTED_BUTTON_CALLS = {
    f'{button}.{method}'
    for button in BUTTON_SPEC['runtime_objects']
    for method in BUTTON_SPEC['converter_supported_methods']
}


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


def same_ast(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(
        right, include_attributes=False
    )


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
        self.reserved.update(
            component.get('id') for component in self.project.get('components', [])
            if component.get('id')
        )
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
        self.pages = {
            component['name']: component
            for component in self.project.get('components', [])
            if component.get('type') == 'lvgl_page'
        }
        self.textareas = {}
        self.page_configured = False
        self.before_page_tail = next(
            (
                block for block in self.root.iter('block')
                if block.find('./next/block') is self.page
            ),
            None,
        )

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

    def insert_before_page_load(self, block):
        if self.before_page_tail is None:
            raise BestEffortError('verified template lacks page-load predecessor')
        following = self.before_page_tail.find('./next')
        if following is None or following.find('./block') is not self.page:
            raise BestEffortError('page-load insertion point was modified unexpectedly')
        following.remove(self.page)
        following.append(block)
        ET.SubElement(block, 'next').append(self.page)
        self.before_page_tail = block

    def configure_page(self, name, background_color):
        if self.page_configured:
            raise UnsupportedBlock('only one M5Page component is supported')
        components = self.project.get('components', [])
        component = next(
            (item for item in components if item.get('type') == 'lvgl_page'),
            None,
        )
        if component is None:
            raise BestEffortError('verified template lacks an lvgl_page component')
        old_name = component['name']
        component['name'] = name
        component['backgroundColor'] = f'#{background_color:06x}'
        field = self.page.find('./field[@name="NAME"]')
        if field is None:
            raise BestEffortError('verified template page-load block lacks NAME')
        field.text = name
        self.pages.pop(old_name, None)
        self.pages[name] = component
        self.page_configured = True
        return component

    def add_textarea(self, name, properties):
        if name in self.textareas:
            raise UnsupportedBlock(f'duplicate M5TextArea component name: {name}')
        page = self.pages.get(properties['parent'])
        if page is None:
            raise UnsupportedBlock(
                f'M5TextArea parent is not a converted M5Page: {properties["parent"]}')
        components = self.project.setdefault('components', [])
        layer = max((item.get('layer', 0) for item in components), default=0) + 1
        create_time = max(
            (item.get('createTime', 0) for item in components), default=0
        ) + 1
        component = {
            'name': name,
            'type': 'lvgl_textarea',
            'layer': layer,
            'screenId': 'builtin',
            'screenName': '',
            'id': self.new_id(),
            'createTime': create_time,
            'x': properties['x'],
            'y': properties['y'],
            'width': properties['w'],
            'height': properties['h'],
            'color': f'#{properties["text_c"]:06x}',
            'borderColor': f'#{properties["border_c"]:06x}',
            'backgroundColor': f'#{properties["bg_c"]:06x}',
            'text': properties['text'],
            'placeholder': properties['placeholder'],
            'font': properties['font'],
            'pageId': page['id'],
            'isLVGL': True,
            'isSelected': False,
        }
        components.append(component)
        self.textareas[name] = component
        return component

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

    def __init__(
        self, builder, source, notes, counts, phase, constants, managed_globals,
        inlined_constant_nodes,
    ):
        self.builder = builder
        self.source = source
        self.notes = notes
        self.counts = counts
        self.phase = phase
        self.constants = constants
        self.managed_globals = managed_globals
        self.inlined_constant_nodes = inlined_constant_nodes

    def block(self, kind):
        return ET.Element('block', {'type': kind, 'id': self.builder.new_id()})

    def number(self, value):
        block = self.block('math_number')
        ET.SubElement(block, 'mutation', {
            'max': 'Infinity', 'min': '-Infinity', 'precision': '0'
        })
        self.builder.field(block, 'NUM', value)
        return block

    def number_shadow(self, value, kind='math_number', **mutation_attributes):
        shadow = ET.Element('shadow', {'type': kind, 'id': self.builder.new_id()})
        ET.SubElement(shadow, 'mutation', mutation_attributes or {
            'max': 'Infinity', 'min': '-Infinity', 'precision': '0'
        })
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        self.builder.field(shadow, 'NUM', value)
        return shadow

    def text_shadow(self, value='hello M5'):
        shadow = ET.Element('shadow', {
            'type': 'text', 'id': self.builder.new_id()
        })
        self.builder.field(shadow, 'TEXT', value)
        return shadow

    def literal_value(self, node):
        if isinstance(node, ast.Name) and node.id in self.constants:
            self.inlined_constant_nodes.add(id(node))
            return self.constants[node.id]
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError) as exc:
            raise UnsupportedBlock('component property must be a literal or constant') from exc

    def component_note(self, node, kind, name):
        line, column = node_location(node)
        self.notes.append(Note(
            'info',
            'ui_component_converted',
            f'{kind} {name} is represented as an editable UiFlow2 component.',
            line,
            column,
            source_text(self.source, node),
            'components[]',
            'Component ID, layer, and createTime are regenerated.',
        ))
        self.counts['ui_components'] += 1

    def parse_component_call(self, call, parameter_names, defaults):
        if len(call.args) > len(parameter_names):
            raise UnsupportedBlock('too many positional component arguments')
        values = dict(defaults)
        assigned = set()
        for name, argument in zip(parameter_names, call.args):
            values[name] = argument
            assigned.add(name)
        for keyword in call.keywords:
            if keyword.arg is None:
                raise UnsupportedBlock('component **kwargs are unsupported')
            if keyword.arg not in parameter_names:
                raise UnsupportedBlock(
                    f'unsupported component property: {keyword.arg}')
            if keyword.arg in assigned:
                raise UnsupportedBlock(
                    f'duplicate component property: {keyword.arg}')
            values[keyword.arg] = keyword.value
            assigned.add(keyword.arg)
        return values

    def ui_assignment(self, node):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            return False
        target = node.targets[0].id
        call = node.value
        name = call_name(call)
        if name == 'm5ui.M5Page':
            values = self.parse_component_call(
                call,
                ('bg_c',),
                {'bg_c': ast.Constant(value=0xFFFFFF)},
            )
            background = self.literal_value(values['bg_c'])
            if type(background) is not int or not 0 <= background <= 0xFFFFFF:
                raise UnsupportedBlock('M5Page bg_c must be an RGB888 integer')
            self.builder.configure_page(target, background)
            self.component_note(node, 'M5Page', target)
            return True
        if name != 'm5ui.M5TextArea':
            return False
        parameters = (
            'text', 'placeholder', 'x', 'y', 'w', 'h', 'font',
            'bg_c', 'border_c', 'text_c', 'parent',
        )
        defaults = {
            'text': ast.Constant(value=''),
            'placeholder': ast.Constant(value=''),
            'x': ast.Constant(value=0),
            'y': ast.Constant(value=0),
            'w': ast.Constant(value=200),
            'h': ast.Constant(value=100),
            'font': ast.Attribute(
                value=ast.Name(id='lv', ctx=ast.Load()),
                attr='font_montserrat_14',
                ctx=ast.Load(),
            ),
            'bg_c': ast.Constant(value=0xFFFFFF),
            'border_c': ast.Constant(value=0xE0E0E0),
            'text_c': ast.Constant(value=0x212121),
            'parent': ast.Constant(value=None),
        }
        values = self.parse_component_call(call, parameters, defaults)
        properties = {}
        for key in ('text', 'placeholder', 'x', 'y', 'w', 'h',
                    'bg_c', 'border_c', 'text_c'):
            properties[key] = self.literal_value(values[key])
        if not isinstance(properties['text'], str):
            raise UnsupportedBlock('M5TextArea text must be a string')
        if not isinstance(properties['placeholder'], str):
            raise UnsupportedBlock('M5TextArea placeholder must be a string')
        for key in ('x', 'y', 'w', 'h'):
            if type(properties[key]) is not int:
                raise UnsupportedBlock(f'M5TextArea {key} must be an integer')
        if properties['w'] <= 0 or properties['h'] <= 0:
            raise UnsupportedBlock('M5TextArea width and height must be positive')
        for key in ('bg_c', 'border_c', 'text_c'):
            value = properties[key]
            if type(value) is not int or not 0 <= value <= 0xFFFFFF:
                raise UnsupportedBlock(
                    f'M5TextArea {key} must be an RGB888 integer')
        font = ast.unparse(values['font'])
        if not re.fullmatch(r'lv\.font_montserrat_\d+', font):
            raise UnsupportedBlock('M5TextArea font must be an lv.font_montserrat_* value')
        properties['font'] = font
        parent = values['parent']
        if not isinstance(parent, ast.Name):
            raise UnsupportedBlock('M5TextArea parent must name a converted M5Page')
        properties['parent'] = parent.id
        self.builder.add_textarea(target, properties)
        self.component_note(node, 'M5TextArea', target)
        return True

    def ui_statement(self, node):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            return False, None
        call = node.value
        name = call_name(call)
        if name is None or '.' not in name:
            return False, None
        target, method = name.rsplit('.', 1)
        if target in self.builder.pages and method == 'screen_load':
            if call.args or call.keywords:
                raise UnsupportedBlock('M5Page.screen_load() requires no arguments')
            line, column = node_location(node)
            self.notes.append(Note(
                'info',
                'ui_page_load_normalized',
                f'{target}.screen_load() uses the profile page-load block.',
                line,
                column,
                source_text(self.source, node),
                'lvgl_page_screen_load',
                'The page-load Block ID and position are regenerated.',
            ))
            self.counts['skipped_nodes'] += 1
            return True, None
        if target not in self.builder.textareas:
            return False, None
        if method == 'set_one_line':
            if call.keywords or len(call.args) != 1:
                raise UnsupportedBlock('M5TextArea.set_one_line() requires one argument')
            enabled = self.literal_value(call.args[0])
            if type(enabled) is not bool:
                raise UnsupportedBlock('M5TextArea.set_one_line() requires a Boolean')
            block = self.block('lvgl_textarea_set_one_line')
            self.builder.field(block, 'NAME', target)
            value = ET.SubElement(block, 'value', {'name': 'VALUE'})
            shadow = ET.SubElement(value, 'shadow', {
                'type': 'lvgl_textarea_bool_option',
                'id': self.builder.new_id(),
            })
            self.builder.field(shadow, 'VALUE', str(enabled))
            self.counts['native_blocks'] += 1
            if self.phase == 'setup':
                self.builder.insert_before_page_load(block)
                return True, None
            return True, block
        if method == 'set_text':
            if call.keywords or len(call.args) != 1:
                raise UnsupportedBlock('M5TextArea.set_text() requires one argument')
            block = self.block('lvgl_textarea_set_text')
            self.builder.field(block, 'NAME', target)
            value = ET.SubElement(block, 'value', {'name': 'VALUE'})
            value.append(self.text_shadow())
            value.append(self.expression(call.args[0]))
            self.counts['native_blocks'] += 1
            return True, block
        if method == 'set_text_color':
            if call.keywords or len(call.args) != 3:
                raise UnsupportedBlock(
                    'M5TextArea.set_text_color() requires color, opacity, and part'
                )
            color = self.literal_value(call.args[0])
            if type(color) is not int or not 0 <= color <= 0xFFFFFF:
                raise UnsupportedBlock(
                    'M5TextArea.set_text_color() color must be an RGB888 integer'
                )
            opacity_node = call.args[1]
            if ast.unparse(opacity_node) == 'lv.OPA.COVER':
                opacity = 255
            else:
                opacity = self.literal_value(opacity_node)
            if type(opacity) is not int or not 0 <= opacity <= 255:
                raise UnsupportedBlock(
                    'M5TextArea.set_text_color() opacity must be 0..255 or lv.OPA.COVER'
                )
            part = call.args[2]
            default_part = ast.parse(
                'lv.PART.MAIN | lv.STATE.DEFAULT', mode='eval'
            ).body
            if not (
                same_ast(part, default_part)
                or (isinstance(part, ast.Constant) and part.value == 0)
            ):
                raise UnsupportedBlock(
                    'M5TextArea.set_text_color() currently supports only the default state'
                )
            block = self.block('lvgl_textarea_set_text_color')
            self.builder.field(block, 'NAME', target)
            self.builder.field(block, 'MODE', 'DEFAULT')
            color_value = ET.SubElement(block, 'value', {'name': 'COLOR'})
            color_block = self.block('color_rgb_palette')
            ET.SubElement(color_block, 'mutation', {'mode': 'palette'})
            self.builder.field(color_block, 'MODE', 'palette')
            self.builder.field(color_block, 'COLOR', f'#{color:06x}')
            color_value.append(color_block)
            opacity_value = ET.SubElement(block, 'value', {'name': 'OPA'})
            opacity_value.append(self.number_shadow(
                opacity,
                'math_slider',
                max='255',
                min='0',
                step='10',
                precision='1',
            ))
            self.counts['native_blocks'] += 1
            return True, block
        return False, None

    def variable_get(self, name):
        block = self.block('variables_get')
        self.builder.field(block, 'VAR', name, id=self.builder.variable_id(name))
        return block

    def button_was_pressed(self, call, name):
        if call.args or call.keywords:
            raise UnsupportedBlock(f'{name}() does not accept arguments')
        block = self.block(BUTTON_SPEC['block_type'])
        self.builder.field(block, 'NAME', name.split('.')[0])
        self.counts['native_blocks'] += 1
        return block

    def speaker_statement(self, node):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            return None
        call = node.value
        name = call_name(call)
        if name not in {
            'Speaker.begin', 'Speaker.setVolumePercentage', 'Speaker.tone'
        }:
            return None
        if call.keywords:
            raise UnsupportedBlock(f'{name}() keyword arguments are unsupported')
        if name == 'Speaker.begin':
            if call.args:
                raise UnsupportedBlock('Speaker.begin() requires no arguments')
            block = self.block('speaker_begin')
        elif name == 'Speaker.setVolumePercentage':
            if len(call.args) != 1:
                raise UnsupportedBlock(
                    'Speaker.setVolumePercentage() requires one argument')
            volume = numeric_literal(call.args[0])
            if volume is None or not 0 <= volume <= 1:
                raise UnsupportedBlock(
                    'Speaker.setVolumePercentage() requires a numeric literal from 0 to 1')
            block = self.block('speaker_set_volume_percentage')
            value = ET.SubElement(block, 'value', {'name': 'VOLUME'})
            value.append(self.number_shadow(
                volume * 100,
                'math_slider',
                max='100', min='0', step='1', precision='1',
            ))
        else:
            if len(call.args) != 2:
                raise UnsupportedBlock('Speaker.tone() requires frequency and duration')
            frequency = numeric_literal(call.args[0])
            duration = numeric_literal(call.args[1])
            if frequency is None or duration is None:
                raise UnsupportedBlock(
                    'Speaker.tone() requires numeric literal arguments')
            block = self.block('speaker_tone')
            frequency_value = ET.SubElement(block, 'value', {'name': 'FREQ'})
            frequency_value.append(self.number_shadow(frequency))
            duration_value = ET.SubElement(block, 'value', {'name': 'MS'})
            duration_value.append(self.number_shadow(duration))
        self.counts['native_blocks'] += 1
        return block

    def text_conversion(self, call):
        if call.keywords or len(call.args) != 1:
            raise UnsupportedBlock('str() requires one positional argument')
        block = self.block('text_convert_str')
        self.builder.value(block, 'VALUE', self.expression(call.args[0]))
        return block

    def string_membership(self, node):
        if not (
            isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
            and isinstance(node.comparators[0], ast.Name)
        ):
            raise UnsupportedBlock(
                'string membership requires a string literal and a simple variable')
        source = node.comparators[0]
        replaced = self.block('text_replace')
        self.builder.value(replaced, 'FROM', self.expression(node.left))
        self.builder.value(replaced, 'TO', self.expression(ast.Constant(value='')))
        self.builder.value(replaced, 'TEXT', self.expression(source))
        comparison = self.block('logic_compare')
        option = 'NEQ' if isinstance(node.ops[0], ast.In) else 'EQ'
        self.builder.field(comparison, 'OP', option)
        self.builder.value(comparison, 'A', self.expression(source))
        self.builder.value(comparison, 'B', replaced)
        return comparison

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
        if isinstance(node, ast.Call):
            name = call_name(node)
            if name in SUPPORTED_BUTTON_CALLS:
                return self.button_was_pressed(node, name)
            if name == 'str':
                return self.text_conversion(node)
            raise UnsupportedBlock(f'unsupported function call: {name or "dynamic call"}')
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
            if isinstance(node.ops[0], (ast.In, ast.NotIn)):
                return self.string_membership(node)
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
        if isinstance(node, ast.Global) and set(node.names) <= self.managed_globals:
            line, column = node_location(node)
            self.notes.append(Note(
                'info',
                'global_declaration_normalized',
                'UiFlow2 derives global declarations from components and workspace variables.',
                line,
                column,
                source_text(self.source, node),
                'components[] and <variables>',
                'The explicit Python global statement is omitted; UiFlow2 regenerates it from project references.',
            ))
            self.counts['skipped_nodes'] += 1
            return None
        operation = native_operation(node)
        if operation is not None:
            self.counts['native_blocks'] += 1
            return self.builder.make_native(operation)
        if isinstance(node, (ast.If, ast.For, ast.While)):
            return self.control(node, control_depth)
        try:
            if self.ui_assignment(node):
                return None
            matched, ui_block = self.ui_statement(node)
            if matched:
                return ui_block
            speaker = self.speaker_statement(node)
            if speaker is not None:
                return speaker
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
            'The output always includes one verified Core2 LVGL page and the Port A RGB Unit template; a supported M5Page constructor can rename and recolor that page.',
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
            'ui_components': 0,
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
        'ui_components': 0,
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

    constants = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if type(value) in (str, int, float, bool):
                constants[node.targets[0].id] = value

    managed_globals = set()
    for function in (setup, loop):
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                managed_globals.add(node.targets[0].id)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                managed_globals.add(node.target.id)
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                managed_globals.add(node.target.id)

    top_level_nodes = []
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
        top_level_nodes.append(node)

    inlined_constant_nodes = set()
    for phase, function in (('setup', setup), ('loop', loop)):
        converter = FlowConverter(
            builder, source, notes, counts, phase, constants, managed_globals,
            inlined_constant_nodes,
        )
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

    setup_assignments = {
        node.targets[0].id: node.value
        for node in setup.body
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        )
    }
    component_names = set(builder.pages) | set(builder.textareas)
    constant_loads = {name: set() for name in constants}
    for candidate in ast.walk(tree):
        if (
            isinstance(candidate, ast.Name)
            and isinstance(candidate.ctx, ast.Load)
            and candidate.id in constant_loads
        ):
            constant_loads[candidate.id].add(id(candidate))
    fully_inlined_constants = {
        name for name, loads in constant_loads.items()
        if loads and loads <= inlined_constant_nodes
    }
    retained_top_level = []
    for node in top_level_nodes:
        normalized = False
        note_code = 'top_level_declaration_normalized'
        note_message = None
        note_emitted_as = 'component or workspace-variable declaration'
        semantic_difference = (
            'UiFlow2 emits a module-level None declaration and applies the '
            'converted setup value later.'
        )
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            normalized = True
            note_code = 'module_docstring_omitted'
            note_message = 'The module docstring has no UiFlow2 Block representation and is omitted.'
            note_emitted_as = 'conversion note'
            semantic_difference = 'The generated module __doc__ value is None instead of the source text.'
        elif (
            isinstance(node, ast.Import)
            and len(node.names) == 1
            and (
                (node.names[0].name == 'M5' and node.names[0].asname is None)
                or (node.names[0].name == 'm5ui' and node.names[0].asname is None)
                or (node.names[0].name == 'lvgl' and node.names[0].asname == 'lv')
            )
        ) or (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == 'M5'
            and len(node.names) == 1
            and node.names[0].name == '*'
            and node.names[0].asname is None
        ):
            normalized = True
            note_code = 'profile_import_normalized'
            note_message = 'The fixed UiFlow2 profile generates this import automatically.'
            note_emitted_as = 'profile imports'
            semantic_difference = 'Import spelling and ordering are regenerated by UiFlow2.'
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
            if (
                name in component_names
                and isinstance(node.value, ast.Constant)
                and node.value.value is None
            ):
                normalized = True
            elif (
                name in builder.variable_ids
                and name in setup_assignments
                and same_ast(node.value, setup_assignments[name])
            ):
                normalized = True
            elif name in fully_inlined_constants:
                normalized = True
                note_code = 'constant_inlined'
                note_message = (
                    f'Constant {name} is embedded in the converted component or Block value.'
                )
                note_emitted_as = 'component property or value Block'
                semantic_difference = (
                    'The generated Python contains the literal value at each converted use '
                    'instead of a mutable module constant.'
                )
        if normalized:
            line, column = node_location(node)
            notes.append(Note(
                'info',
                note_code,
                note_message or f'Top-level declaration for {name} is supplied by UiFlow2 generation.',
                line,
                column,
                source_text(source, node),
                note_emitted_as,
                semantic_difference,
            ))
            counts['skipped_nodes'] += 1
            continue
        retained_top_level.append(node)
    if retained_top_level:
        builder.append_raw_top_level('\n\n'.join(
            source_text(source, node) for node in retained_top_level
        ))
        counts['raw_top_level_blocks'] += 1
        line, column = node_location(retained_top_level[0])
        notes.append(Note(
            'warning',
            'top_level_raw_code',
            'Imports, constants, helper definitions, and other module statements are grouped into a top-level code block.',
            line,
            column,
            emitted_as='execute_code_import',
            semantic_difference='Leading comments and exact spacing between top-level statements may be lost; execution order relative to generated imports can differ.',
        ))

    strategy = (
        'best-effort-native'
        if counts['raw_statement_blocks'] == 0 and counts['raw_top_level_blocks'] == 0
        else 'hybrid-native-and-raw'
    )
    report = make_report(source, strategy, strict_error, notes, counts)
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
