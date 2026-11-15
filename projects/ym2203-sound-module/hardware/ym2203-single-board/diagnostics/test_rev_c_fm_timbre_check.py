# SPDX-License-Identifier: MIT
"""Register sequencing and failure cleanup; the model does not emulate FM timbre."""
from contextlib import redirect_stdout
import importlib.util
import io
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_rev_c_fm_live import TestStream, packed
from test_rev_c_fm_ssg_check import MixerModel, load as load_mixer


HERE = Path(__file__).resolve().parent


class TimbreStream(TestStream):
    def __init__(self, model, fault=None):
        super().__init__(model, fault)
        self.states = []

    def take(self):
        assert self.running
        self.model.us += 11250
        regs = self.model.registers
        mods = tuple(regs[0x40 + slot] for slot in (0,4,8))
        multis = tuple(regs[0x30 + slot] for slot in (0,4,8))
        keys = sum(register == 0x28 for register, value in self.model.writes)
        self.states.append((regs[0x28], regs[0xB0], mods, multis,
                            regs[0x4C], regs[0x6C], regs[0x8C], keys,
                            self.model.level(19), self.model.level(26)))
        if self.model.level(19) and mods == (24,24,24):
            if self.fault == "memory":
                raise MemoryError
            if self.fault == "invalid":
                return packed([0] * 625)
        # Synthetic amplitude is only for testing the transport and silence guards.
        # It deliberately does not predict the hardware's harmonics or envelopes.
        amplitude = 127 if regs[0x28] == 0x10 else 32 if regs[0x28] == 0xF0 else 0
        words = []
        for unused in range(625):
            value = round(amplitude * math.sin(self.phase))
            self.phase = (self.phase + 2 * math.pi * 440 / (4000000/72)) % (2*math.pi)
            words.append(0x400 | (512 + value))
        return packed(words)


def load(model):
    mixer, live, machine = load_mixer(model)
    spec = importlib.util.spec_from_file_location("timbre_diagnostic", HERE / "rev_c_fm_timbre_check.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"rev_c_fm_live": live, "rev_c_fm_ssg_check": mixer}):
        spec.loader.exec_module(module)
    return module, live, machine


class TimbreTests(unittest.TestCase):
    def test_presets_and_live_changes_keep_carrier_quiet_and_keys_held(self):
        model = MixerModel()
        module, live, machine = load(model)
        original = module.TimbreBus.configure
        def configure(bus, preset):
            self.assertFalse(model.stream.running)
            self.assertEqual(model.level(19), 0)
            self.assertEqual(model.level(26), 0)
            original(bus, preset)
        output = io.StringIO()
        with patch.object(live, "Stream", lambda: TimbreStream(model)), patch.object(module.TimbreBus, "configure", configure), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output):
            module.run()
        states = model.stream.states
        self.assertTrue(any(key == 0xF0 and alg == 7 and mods == (127,127,127) and carrier == 64
                            for key, alg, mods, multi, carrier, dr, sl, count, line, dac in states))
        live_states = [state for state in states if state[0] == 0xF0 and state[1] == 0 and state[5] == 0]
        self.assertEqual(len({state[7] for state in live_states}), 1, "Live changes retriggered the note")
        for level in module.MOD_LEVELS:
            self.assertTrue(any(state[2] == (level,)*3 for state in live_states))
        for value in module.MULTIPLES:
            self.assertTrue(any(state[3] == (value,)*3 for state in live_states))
        self.assertTrue(all(state[4] == 64 for state in live_states))
        self.assertTrue(any(state[0] == 0xF0 and state[5:7] == (12,0x8F) for state in states))
        self.assertTrue(all(levels == (0,0,0) for nonzero,line,dac,levels,mixer in model.mix_transfers))
        key_values = [value for register, value in model.writes if register == 0x28]
        self.assertEqual(key_values.count(0xF0), 4)  # pure, serial, decay, decay retrigger
        self.assertEqual(key_values[-3:], [0,1,2])
        self.assertIn("TIMBRE: all six sections sent.", output.getvalue())
        self.assertIn("SAFE:", output.getvalue())
        self.assertIn("DONE:", output.getvalue())
        model.assert_stopped()
        self.assertTrue(model.stream.closed and model.audio.closed)

    def test_decay_programs_all_four_slots_and_presets_do_not_key_on(self):
        model = MixerModel()
        module, live, machine = load(model)
        bus = module.TimbreBus()
        try:
            bus.start()
            bus.configure("decay")
            for slot in module.SLOTS:
                self.assertEqual(model.registers[0x50+slot], 31)
                self.assertEqual(model.registers[0x60+slot], 12)
                self.assertEqual(model.registers[0x70+slot], 0)
                self.assertEqual(model.registers[0x80+slot], 0x8F)
                self.assertEqual(model.registers[0x90+slot], 0)
            self.assertEqual(model.registers[0x4C], 64)
            self.assertEqual(model.registers[0xB0], 0)
            self.assertNotIn((0x28,0xF0), model.writes)
        finally:
            bus.close()
        model.assert_stopped()

    def test_memory_error_during_live_change_still_mutes_and_closes(self):
        self.check_fault("memory", MemoryError)

    def test_invalid_serial_word_during_live_change_still_mutes_and_closes(self):
        self.check_fault("invalid", RuntimeError)

    def check_fault(self, fault, exception):
        model = MixerModel()
        module, live, machine = load(model)
        output = io.StringIO()
        with patch.object(live, "Stream", lambda: TimbreStream(model, fault)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output), self.assertRaises(exception):
            module.run()
        model.assert_stopped()
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertIn("SAFE:", output.getvalue())
        self.assertNotIn("DONE:", output.getvalue())

    def test_policy_rejects_louder_carrier_other_channels_and_invalid_changes(self):
        model = MixerModel()
        module, live, machine = load(model)
        bus = module.TimbreBus()
        try:
            bus.start()
            for register, value in ((0x4C,48), (0x4C,0), (0x4C,127), (0x40,0),
                                    (0x41,64), (0xB1,0), (0xB0,1), (0x28,0xF1),
                                    (0x3C,2), (0x27,0), (0x90,8), (True,0), (0x40,40.0)):
                with self.subTest(register=register, value=value), self.assertRaises(ValueError):
                    bus._write_tone(register, value)
            for method, values in ((bus.modulation, (0,48,127,True,40.0)),
                                   (bus.multiple, (0,4,True,1.0)),
                                   (bus.configure, ("bad",))):
                for value in values:
                    with self.subTest(value=value), self.assertRaises(ValueError):
                        method(value)
        finally:
            bus.close()
        self.assertFalse(model.writes)
        model.assert_stopped()

    def test_import_does_not_touch_gpio(self):
        model = MixerModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
