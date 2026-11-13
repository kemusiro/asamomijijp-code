# SPDX-License-Identifier: MIT
"""Mixed-path command sequencing and mute independence; listening is manual."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel
from test_rev_c_fm_live import LiveModel, TestStream, load as load_live


HERE = Path(__file__).resolve().parent


class MixerModel(LiveModel):
    def __init__(self, bad_ssg=False):
        super().__init__()
        self.allow_ssg_mix = True
        self.bad_ssg = bad_ssg
        self.mix_transfers = []
        original = self.I2S.write
        model = self
        def write(audio, data):
            if len(data) == 2160:
                model.mix_transfers.append((bool(any(data)), model.level(19), model.level(26),
                                            tuple(model.registers[8:11]), model.registers[7]))
            return original(audio, data)
        self.I2S.write = write

    def changed(self, gpio, old, value):
        BusModel.changed(self, gpio, old, value)
        if self.level(19):
            self_check = self.level(22) == self.level(9) == 1
            assert self_check
            assert self.stream.starts >= 2
            assert self.registers[7] & 0x38 == 0x38, "SSG noise was enabled"

    def read_data(self):
        data = super().read_data()
        if self.bad_ssg and self.level(8) and self.address == 0 and self.registers[0] == 28:
            return data ^ 1
        return data


def load(model):
    live, machine = load_live(model)
    spec = importlib.util.spec_from_file_location("mixer_diagnostic", HERE / "rev_c_fm_ssg_check.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"rev_c_fm_live": live,
                                "rev_c_bus_check": types.SimpleNamespace(SSG_MASKS=(255,15,255,15,255,15,31,255,31,31,31))}):
        spec.loader.exec_module(module)
    return module, live, machine


class MixerTests(unittest.TestCase):
    def test_comparisons_include_independent_mutes_chord_and_source_silence(self):
        model = MixerModel()
        module, live, machine = load(model)
        original = module.MixerBus.ssg
        def checked_ssg(bus, mode):
            self.assertFalse(model.stream.running)
            self.assertEqual(model.level(19), 0)
            self.assertEqual(model.level(26), 0)
            original(bus, mode)
        output = io.StringIO()
        with patch.object(live, "Stream", lambda: TestStream(model)), patch.object(module.MixerBus, "ssg", checked_ssg), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output):
            module.run()
        observed = set(model.mix_transfers)
        for state in (
            (True, 1, 1, (0, 0, 0), 0x3F),       # FM only
            (False, 1, 1, (10, 0, 0), 0x3E),     # SSG only
            (True, 1, 1, (10, 0, 0), 0x3E),      # both
            (True, 1, 0, (10, 0, 0), 0x3E),      # DAC mute leaves SSG route
            (True, 0, 1, (10, 0, 0), 0x3E),      # LINE mute blocks both routes
            (True, 1, 1, (7, 7, 7), 0x38),       # four voices
            (False, 1, 1, (0, 0, 0), 0x3F),      # sources off with both gates on
        ):
            self.assertIn(state, observed)
        self.assertIn("MIXER: sequence complete", output.getvalue())
        self.assertIn("SAFE:", output.getvalue())
        self.assertTrue(model.audio.closed and model.stream.closed)
        model.assert_stopped()

    def test_ssg_readback_failure_keeps_line_muted_and_cleans_up(self):
        model = MixerModel(bad_ssg=True)
        module, live, machine = load(model)
        with patch.object(live, "Stream", lambda: TestStream(model)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "readback mismatch"):
            module.run()
        self.assertFalse(any(levels == (10, 0, 0) for nonzero, line, dac, levels, mixer in model.mix_transfers))
        model.assert_stopped()
        self.assertTrue(model.audio.closed and model.stream.closed)

    def test_interruption_with_both_sources_enabled_mutes_and_resets_ssg(self):
        model = MixerModel()
        module, live, machine = load(model)
        class InterruptStream(TestStream):
            def take(self):
                if model.level(19) and model.registers[8] == 10 and model.registers[0x28] == 0x10:
                    raise KeyboardInterrupt
                return super().take()
        with patch.object(live, "Stream", lambda: InterruptStream(model)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            module.run()
        model.assert_stopped()
        self.assertTrue(model.audio.closed and model.stream.closed)

    def test_ssg_policy_rejects_noise_envelope_and_louder_levels(self):
        model = MixerModel()
        module, unused, machine = load(model)
        bus = module.MixerBus()
        try:
            bus.start()
            for register, value in ((6, 1), (7, 0), (7, 0x36), (8, 11), (8, 16), (9, 15), (10, True), (True, 0)):
                with self.subTest(register=register), self.assertRaises(ValueError):
                    bus.write_ssg(register, value)
            with self.assertRaises(ValueError):
                bus.ssg("noise")
        finally:
            bus.close()
        self.assertFalse(model.writes)
        model.assert_stopped()

    def test_import_never_touches_gpio(self):
        model = MixerModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
