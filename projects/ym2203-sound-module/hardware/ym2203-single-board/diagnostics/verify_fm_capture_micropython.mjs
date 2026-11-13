// SPDX-License-Identifier: MIT
// Run via ./scripts/use-node.sh node <this file> from the repository root.
// Verifies Python compatibility in real MicroPython WASM. GPIO/PIO/DMA are stubbed.
import { readFile } from "node:fs/promises";
import { loadMicroPython } from "../../../tools/micropython-wasm.mjs";

const source = await readFile(new URL("rev_c_fm_capture.py", import.meta.url), "utf8");
const dacSource = await readFile(new URL("rev_c_dac_check.py", import.meta.url), "utf8");
const playbackSource = await readFile(new URL("rev_c_fm_playback.py", import.meta.url), "utf8");
const liveSource = await readFile(new URL("rev_c_fm_live.py", import.meta.url), "utf8");
const mixerSource = await readFile(new URL("rev_c_fm_ssg_check.py", import.meta.url), "utf8");
const polySource = await readFile(new URL("rev_c_six_voice_check.py", import.meta.url), "utf8");
const timbreSource = await readFile(new URL("rev_c_fm_timbre_check.py", import.meta.url), "utf8");
const enduranceSource = await readFile(new URL("rev_c_endurance_check.py", import.meta.url), "utf8");
const i2cTargetSource = await readFile(new URL("rev_c_i2c_target_check.py", import.meta.url), "utf8");
const i2cHostSource = await readFile(new URL("rev_c_i2c_host_check.py", import.meta.url), "utf8");
const ssgSource = await readFile(new URL("rev_c_ssg_check.py", import.meta.url), "utf8");
const i2cSsgTargetSource = await readFile(new URL("rev_c_i2c_ssg_target.py", import.meta.url), "utf8");
const i2cSsgHostSource = await readFile(new URL("rev_c_i2c_ssg_host.py", import.meta.url), "utf8");
const i2cFmTargetSource = await readFile(new URL("rev_c_i2c_fm_target.py", import.meta.url), "utf8");
const i2cFmHostSource = await readFile(new URL("rev_c_i2c_fm_host.py", import.meta.url), "utf8");
const isolationTargetSource = await readFile(new URL("rev_c_i2c_isolation_target.py", import.meta.url), "utf8");
const isolationHostSource = await readFile(new URL("rev_c_i2c_isolation_host.py", import.meta.url), "utf8");
const stagedTargetSource = await readFile(new URL("rev_c_i2c_fm_staged_target.py", import.meta.url), "utf8");
const stagedHostSource = await readFile(new URL("rev_c_i2c_fm_staged_host.py", import.meta.url), "utf8");
const i2cEnduranceSource = await readFile(new URL("rev_c_i2c_endurance_host.py", import.meta.url), "utf8");
const i2cCycleSource = await readFile(new URL("rev_c_i2c_cycle_host.py", import.meta.url), "utf8");
const i2cPitchTargetSource = await readFile(new URL("rev_c_i2c_pitch_target.py", import.meta.url), "utf8");
const i2cPitchHostSource = await readFile(new URL("rev_c_i2c_pitch_host.py", import.meta.url), "utf8");
const i2cTimbreTargetSource = await readFile(new URL("rev_c_i2c_timbre_target.py", import.meta.url), "utf8");
const i2cTimbreHostSource = await readFile(new URL("rev_c_i2c_timbre_host.py", import.meta.url), "utf8");
const i2cCombinedTargetSource = await readFile(new URL("rev_c_i2c_combined_target.py", import.meta.url), "utf8");
const i2cCombinedHostSource = await readFile(new URL("rev_c_i2c_combined_host.py", import.meta.url), "utf8");
const i2cEnvelopeTargetSource = await readFile(new URL("rev_c_i2c_envelope_target.py", import.meta.url), "utf8");
const i2cEnvelopeHostSource = await readFile(new URL("rev_c_i2c_envelope_host.py", import.meta.url), "utf8");
const i2cSixTargetSource = await readFile(new URL("rev_c_i2c_six_target.py", import.meta.url), "utf8");
const i2cSixHostSource = await readFile(new URL("rev_c_i2c_six_host.py", import.meta.url), "utf8");
const i2cSixEnduranceSource = await readFile(new URL("rev_c_i2c_six_endurance_host.py", import.meta.url), "utf8");
const i2cSixCycleSource = await readFile(new URL("rev_c_i2c_six_cycle_host.py", import.meta.url), "utf8");
const i2cSixRecoverySource = await readFile(new URL("rev_c_i2c_six_recovery_host.py", import.meta.url), "utf8");
const i2cVoicePitchTargetSource = await readFile(new URL("rev_c_i2c_voice_pitch_target.py", import.meta.url), "utf8");
const i2cVoicePitchHostSource = await readFile(new URL("rev_c_i2c_voice_pitch_host.py", import.meta.url), "utf8");
const i2cVoicePitchEnduranceSource = await readFile(new URL("rev_c_i2c_voice_pitch_endurance_host.py", import.meta.url), "utf8");
const i2cQueueTargetSource = await readFile(new URL("rev_c_i2c_queue_target.py", import.meta.url), "utf8");
const i2cQueueHostSource = await readFile(new URL("rev_c_i2c_queue_host.py", import.meta.url), "utf8");
const i2cQueueStopSource = await readFile(new URL("rev_c_i2c_queue_stop_host.py", import.meta.url), "utf8");
const i2cQueueAccompTargetSource = await readFile(new URL("rev_c_i2c_queue_accomp_target.py", import.meta.url), "utf8");
const i2cQueueAccompHostSource = await readFile(new URL("rev_c_i2c_queue_accomp_host.py", import.meta.url), "utf8");
const i2cQueueAccompStopSource = await readFile(new URL("rev_c_i2c_queue_accomp_stop_host.py", import.meta.url), "utf8");
const i2cQueueMuteTargetSource = await readFile(new URL("rev_c_i2c_queue_mute_target.py", import.meta.url), "utf8");
const i2cQueueMuteHostSource = await readFile(new URL("rev_c_i2c_queue_mute_host.py", import.meta.url), "utf8");
const i2cQueueMuteStopSource = await readFile(new URL("rev_c_i2c_queue_mute_stop_host.py", import.meta.url), "utf8");
const i2cQueueMuteLeaseSource = await readFile(new URL("rev_c_i2c_queue_mute_lease_host.py", import.meta.url), "utf8");
const i2cQueueReplaceSource = await readFile(new URL("rev_c_i2c_queue_replace_host.py", import.meta.url), "utf8");
const i2cQueueRestTargetSource = await readFile(new URL("rev_c_i2c_queue_rest_target.py", import.meta.url), "utf8");
const i2cQueueRestHostSource = await readFile(new URL("rev_c_i2c_queue_rest_host.py", import.meta.url), "utf8");
const i2cQueueRestFinalSource = await readFile(new URL("rev_c_i2c_queue_rest_final_host.py", import.meta.url), "utf8");
// WASM has no Arm Viper emitter: check the same arithmetic as Python here.
// The unchanged Viper source is separately compiled with official Arm mpy-cross.
const scalarLiveSource = liveSource.replace("@micropython.viper\n", "")
  .replace("source: ptr32, destination: ptr16) -> int", "source, destination)");
const output = [];
const decoder = new TextDecoder();
const mp = await loadMicroPython({
  linebuffer: false,
  stdout: (data) => output.push(decoder.decode(data, { stream: true })),
});
mp.FS.writeFile("/machine.py", "class Pin:\n    pass\nI2C = SoftI2C = I2S = object\nmem32 = {}\n");
mp.FS.writeFile("/rev_c_bus_check.py", [
  "class RevCBus:", "    pass", "def _check_platform():", "    pass",
  "def _diagnose(bus):", "    pass", "def _emergency_stop():", "    pass", "",
  "I2S_OUTPUT_GPIO = (10, 11, 12)", "",
  "SSG_MASKS = (255,15,255,15,255,15,31,255,31,31,31)", "",
].join("\n"));
mp.FS.writeFile("/rev_c_fm_capture.py", source);
mp.FS.writeFile("/rev_c_dac_check.py", dacSource);
mp.FS.writeFile("/rev_c_fm_live.py", scalarLiveSource);
mp.FS.writeFile("/rev_c_fm_ssg_check.py", mixerSource);
mp.FS.writeFile("/rev_c_six_voice_check.py", polySource);
mp.FS.writeFile("/rev_c_i2c_target_check.py", i2cTargetSource);
mp.FS.writeFile("/rev_c_i2c_host_check.py", i2cHostSource);
mp.FS.writeFile("/rev_c_ssg_check.py", ssgSource);
mp.FS.writeFile("/rev_c_i2c_ssg_target.py", i2cSsgTargetSource);
mp.FS.writeFile("/rev_c_i2c_ssg_host.py", i2cSsgHostSource);
mp.FS.writeFile("/rev_c_i2c_fm_target.py", i2cFmTargetSource);
mp.FS.writeFile("/rev_c_i2c_fm_host.py", i2cFmHostSource);
mp.FS.writeFile("/rev_c_i2c_isolation_target.py", isolationTargetSource);
mp.FS.writeFile("/rev_c_i2c_isolation_host.py", isolationHostSource);
mp.FS.writeFile("/rev_c_i2c_fm_staged_host.py", stagedHostSource);
mp.FS.writeFile("/rev_c_i2c_endurance_host.py", i2cEnduranceSource);
mp.FS.writeFile("/rev_c_i2c_isolation_target.py", isolationTargetSource);
mp.FS.writeFile("/rev_c_i2c_fm_staged_target.py", stagedTargetSource);
mp.FS.writeFile("/rev_c_fm_timbre_check.py", timbreSource);
mp.FS.writeFile("/rev_c_i2c_timbre_target.py", i2cTimbreTargetSource);
mp.FS.writeFile("/rev_c_i2c_timbre_host.py", i2cTimbreHostSource);
mp.FS.writeFile("/rev_c_i2c_six_host.py", i2cSixHostSource);
mp.FS.writeFile("/rev_c_i2c_six_target.py", i2cSixTargetSource);
mp.FS.writeFile("/rev_c_i2c_voice_pitch_host.py", i2cVoicePitchHostSource);
mp.FS.writeFile("/rev_c_i2c_voice_pitch_target.py", i2cVoicePitchTargetSource);
mp.FS.writeFile("/rev_c_i2c_queue_host.py", i2cQueueHostSource);
mp.FS.writeFile("/rev_c_i2c_queue_target.py", i2cQueueTargetSource);
mp.FS.writeFile("/rev_c_i2c_queue_stop_host.py", i2cQueueStopSource);
mp.FS.writeFile("/rev_c_i2c_queue_accomp_host.py", i2cQueueAccompHostSource);
mp.FS.writeFile("/rev_c_i2c_queue_accomp_target.py", i2cQueueAccompTargetSource);
mp.FS.writeFile("/rev_c_i2c_queue_mute_host.py", i2cQueueMuteHostSource);
mp.FS.writeFile("/rev_c_i2c_queue_mute_target.py", i2cQueueMuteTargetSource);
mp.FS.writeFile("/rev_c_i2c_queue_rest_host.py", i2cQueueRestHostSource);
await mp.runPythonAwaitable(`
import sys
from array import array
print(sys.version)
try:
    array('I', [0]) * 16384
except TypeError:
    print('PASS: original array repetition failure reproduced')
else:
    raise AssertionError('Runtime did not reproduce original failure')

_ns = {'__name__': '_fm_capture_compatibility_test'}
exec(${JSON.stringify(source)}, _ns)
_capture = _ns['Capture']()
assert len(_capture.words) == 16384
assert len(memoryview(_capture.words)) == 16384
assert not any(_capture.words)
_capture.words[-1] = 0xFFFFFFFF
assert _capture.words[-1] == 0xFFFFFFFF
_capture.words[-1] = 0
assert _capture.sm is None and _capture.dma is None
_result = _ns['analyze'](_capture.words, keep_frames=True)
assert _result['samples'] == 131072
assert _result['clk_edges'] == _result['sh_edges'] == _result['frames'] == 0
assert _result['data'] == []
_capture.close()
print('PASS: corrected Capture allocation, 32-bit buffer, and analyzer in MicroPython')
_replay = {'__name__': '_fm_playback_compatibility_test'}
exec(${JSON.stringify(playbackSource)}, _replay)
assert _replay['decode'](0x600) == 0
assert _replay['decode'](0x67F) == 127
assert _replay['decode'](0x65C) == 92
import math
import struct
_rate = 16000000 / 288
_data = [0x400 | (512 + round(127 * math.sin(2 * math.pi * 440 * i / _rate))) for i in range(454)]
_on = {'data': _data, 'sh_hz': _rate, 'bit_counts': {24: 454}}
_off = {'data': [0x600] * 454, 'sh_hz': _rate, 'bit_counts': {24: 454}}
_buffers, _info = _replay['make_buffers'](_off, _on, _off)
assert 439 <= _info['playback_hz'] <= 441
_steady = _buffers[1]
assert all(abs(struct.unpack_from('<h', _steady, i)[0]) <= 4096 for i in range(0, len(_steady), 4))
assert all(struct.unpack_from('<h', _steady, i)[0] == 0 for i in range(2, len(_steady), 4))
print('PASS: user FM word decode, captured-period resampling, level limit and stereo packing in MicroPython')
_live = {'__name__': '_fm_live_scalar_compatibility_test'}
exec(${JSON.stringify(scalarLiveSource)}, _live)
_src = array('I', (0x67F << 19 for _ in range(625)))
_dst = array('H', (0 for _ in range(1080)))
assert _live['convert'](_src, _dst) == 4064
assert all(_dst[i] == 4064 and _dst[i + 1] == 0 for i in range(0, 1080, 2))
for _i in range(625):
    _src[_i] = 0x600 << 19
assert _live['convert'](_src, _dst) == 0
assert not any(_dst)
print('PASS: live 625-to-540 scalar conversion in MicroPython; Arm Viper execution not tested by WASM')
_mix = {'__name__': '_mixer_compatibility_test'}
exec(${JSON.stringify(mixerSource)}, _mix)
_bus = _mix['MixerBus']()
_regs = [0] * 16
_address = 0
def _write_port(port, value):
    global _address
    if port == 0:
        _address = value
    else:
        _regs[_address] = value
_bus.wait_ready = lambda: None
_bus._write_port = _write_port
_bus.read_ssg = lambda register: _regs[register]
_bus.ssg('single')
assert _regs[0] == 28 and _regs[1] == 1 and _regs[7] == 0x3E
assert _regs[8:11] == [10, 0, 0]
_bus.ssg('chord')
assert _regs[:6] == [239, 0, 190, 0, 159, 0]
assert _regs[7] == 0x38 and _regs[8:11] == [7, 7, 7]
_bus.ssg('off')
assert _regs[7] == 0x3F and _regs[8:11] == [0, 0, 0]
print('PASS: mixed FM/SSG tone, chord and silence register programming in MicroPython')
_poly = {'__name__': '_six_voice_compatibility_test'}
exec(${JSON.stringify(polySource)}, _poly)
_poly_bus = _poly['SixVoiceBus']()
_poly_regs = [0] * 256
_poly_address = 0
_keys = []
def _poly_write_port(port, value):
    global _poly_address
    if port == 0:
        _poly_address = value
    else:
        _poly_regs[_poly_address] = value
        if _poly_address == 0x28:
            _keys.append(value)
_poly_bus.wait_ready = lambda: None
_poly_bus._write_port = _poly_write_port
_poly_bus.read_ssg = lambda register: _poly_regs[register]
_poly_bus.configure_three()
for _channel in range(3):
    assert _poly_regs[0x40 + _channel] == 64
    assert _poly_regs[0xB0 + _channel] == 7
    assert all(_poly_regs[0x40 + _slot + _channel] == 127 for _slot in (4, 8, 12))
_poly_bus.fm_mask((0,1,2))
assert _keys[-3:] == [0x10,0x11,0x12]
_poly_bus.bass()
assert [_poly_regs[2*i] | _poly_regs[2*i+1] << 8 for i in range(3)] == [478,379,319]
assert _poly_regs[7] == 0x38 and _poly_regs[8:11] == [7,7,7]
_poly_bus.fm_mask(())
assert _keys[-3:] == [0,1,2]
print('PASS: three quiet FM carriers, channel keys and SSG bass chord in MicroPython')
_timbre = {'__name__': '_fm_timbre_compatibility_test'}
exec(${JSON.stringify(timbreSource)}, _timbre)
_timbre_bus = _timbre['TimbreBus']()
_timbre_bus.wait_ready = lambda: None
_timbre_bus._write_port = _poly_write_port
_timbre_bus.configure('pure')
assert _poly_regs[0xB0] == 7 and _poly_regs[0x4C] == 64
assert all(_poly_regs[0x40 + _slot] == 127 for _slot in (0,4,8))
_timbre_bus.configure('serial')
assert _poly_regs[0xB0] == 0 and _poly_regs[0x4C] == 64
_timbre_bus.key_on()
assert _keys[-1] == 0xF0
_held_keys = len(_keys)
for _level in (96,64,40,24):
    _timbre_bus.modulation(_level)
    assert all(_poly_regs[0x40 + _slot] == _level for _slot in (0,4,8))
for _multi in (1,2,3):
    _timbre_bus.multiple(_multi)
    assert all(_poly_regs[0x30 + _slot] == _multi for _slot in (0,4,8))
assert _poly_regs[0x3C] == 1 and _poly_regs[0x4C] == 64
assert len(_keys) == _held_keys
_timbre_bus.configure('decay')
assert all(_poly_regs[0x60 + _slot] == 12 and _poly_regs[0x80 + _slot] == 0x8F for _slot in (0,4,8,12))
_timbre_bus.key_on()
_timbre_bus.keys_off()
assert _keys[-4:] == [0xF0,0,1,2]
print('PASS: four-operator presets, held-key TL/MULTI changes and envelope programming in MicroPython')
print('CONTROL-LOOP SIMULATION: fast fake clock and step, no audio/peripheral execution or real-time GC measurement')
_end = {'__name__': '_endurance_compatibility_test'}
exec(${JSON.stringify(enduranceSource)}, _end)
_end_live = _end['live']
_end_bus = _end['six'].SixVoiceBus()
_end_regs = [0] * 256
_end_address = 0
def _end_write_port(port, value):
    global _end_address
    if port == 0:
        _end_address = value
    else:
        _end_regs[_end_address] = value
class _Flag:
    def __init__(self):
        self.state = 0
    def value(self, state):
        self.state = state
class _EndStream:
    def __init__(self):
        self.running = False
        self.ticks = self.starts = self.audible_blocks = 0
    def start(self):
        self.running = True
        self.starts += 1
    def stop(self):
        self.running = False
    def check(self):
        assert self.running
class _EndClock:
    @staticmethod
    def ticks_us():
        return _end_stream.ticks
    @staticmethod
    def ticks_diff(a, b):
        return a - b
class _EndAudio:
    def write(self, data):
        return len(data)
_end_stream = _EndStream()
_end_bus.line_allow = _Flag()
_end_bus.dac_allow = _Flag()
_end_bus.wait_ready = lambda: None
_end_bus._write_port = _end_write_port
_end_bus.read_ssg = lambda register: _end_regs[register]
def _end_print(*args):
    assert not _end_stream.running, 'USB report during capture'
    _end_stream.ticks += 50000  # deliberately slow, stopped-only console
    print(*args)
_end['print'] = _end_print
def _end_step(stream, pcm, audio):
    stream.check()
    stream.ticks += 11250
    if _end_bus.line_allow.state and _end_regs[8:11] == [7,7,7]:
        stream.audible_blocks += 1
    return 2976 if _end_regs[0x28] & 0x10 else 0
_end_live.step = _end_step
_end_live.time = _EndClock
assert sum(_end['SEGMENT_BLOCKS']) == 16000
_end['sequence'](_end_bus, _end_stream, bytearray(2160), _EndAudio(), bytearray(1920))
assert _end_stream.audible_blocks == 16000 and _end_stream.starts == 2
assert not _end_stream.running and not _end_bus.line_allow.state
assert _end_regs[8:11] == [0,0,0]
print('PASS: all 16000 endurance control blocks, deferred reports, stopped-only heap walks and final source-off sequence; transport and clock simulated')
_it = {'__name__': '_i2c_target_compatibility_test'}
_ih = {'__name__': '_i2c_host_compatibility_test'}
exec(${JSON.stringify(i2cTargetSource)}, _it)
exec(${JSON.stringify(i2cHostSource)}, _ih)
_iw = _it['Window']()
class _RamLink:
    def scan(self):
        return [0x42]
    def writeto(self, address, data, stop=True):
        assert address == 0x42
        for index, value in enumerate(data):
            _iw.receive(value | (0x800 if index == 0 else 0))
        return len(data)
    def readfrom(self, address, count):
        assert address == 0x42
        return bytes(_iw.next_byte() for _ in range(count))
_ih['check'](_RamLink())
assert _iw.finish_pending and _iw.ignored == 1
assert _iw.data[:8] == b'RCI2C01!'
print('PASS: I2C diagnostic RAM protocol and all host byte patterns in MicroPython; electrical bus and target register polling simulated separately')
_st = {'__name__': '_i2c_ssg_target_compatibility_test'}
_sh = {'__name__': '_i2c_ssg_host_compatibility_test'}
exec(${JSON.stringify(i2cSsgTargetSource)}, _st)
exec(${JSON.stringify(i2cSsgHostSource)}, _sh)
class _SoundBoard:
    def __init__(self):
        self.active = 0
        self.channels = []
    def select(self, channel):
        assert channel in (1,2,3)
        self.active = channel
        self.channels.append(channel)
    def silence(self):
        self.active = 0
_sb = _SoundBoard()
_sc = _st['SoundTarget'](_sb)
_sl = _st['link']
_sl.mem32[_sl.IC_RAW_INTR_STAT] = 0
_sl.mem32[_sl.IC_RXFLR] = 0
_sl.mem32[_sl.IC_STATUS] = 0
class _SoundClock:
    ticks = 0
    @staticmethod
    def ticks_ms():
        return _SoundClock.ticks
    @staticmethod
    def ticks_diff(a,b):
        return a-b
    @staticmethod
    def sleep_ms(milliseconds):
        while milliseconds:
            delta = min(10,milliseconds)
            _SoundClock.ticks += delta
            _sc.poll()
            milliseconds -= delta
_st['time'] = _sh['time'] = _SoundClock
class _SoundLink:
    def scan(self):
        return [0x42]
    def writeto(self,address,data,stop=True):
        assert address == 0x42
        _sl.mem32[_sl.IC_STATUS] = 0x40
        for index,value in enumerate(data):
            _sc.window.receive(value | (0x800 if index == 0 else 0))
            _sc.poll()
        if stop:
            _sl.mem32[_sl.IC_STATUS] = 0
            _sc.poll()
        return len(data)
    def readfrom(self,address,count):
        assert address == 0x42
        return bytes(_sc.window.next_byte() for _ in range(count))
_sh['check'](_SoundLink())
assert _sc.expirations == 1 and _sc.window.finished and not _sb.active
assert _sb.channels == [1,2,3,1,2,3,1]
print('PASS: I2C SSG command acknowledgements, six tones and lease mute in MicroPython; sound hardware, transport and clock simulated')
class _OrderedReply:
    def __init__(self):
        self.request = 0x20
        self.byte = None
        self.cleared = False
    def __getitem__(self,address):
        if address == _it['IC_RAW_INTR_STAT']:
            return self.request
        if address == _it['IC_CLR_RD_REQ']:
            assert self.byte == ord('R'), 'Request released before data queued'
            self.request = 0
            self.cleared = True
        return 0
    def __setitem__(self,address,value):
        assert address == _it['IC_DATA_CMD'] and self.request == 0x20
        self.byte = value
_ordered = _OrderedReply()
_it['mem32'] = _ordered
_reply = _it['Target']()
_next = _reply.window.next_byte
def _delayed_reply():
    import gc
    assert _ordered.request == 0x20
    gc.collect()
    assert _ordered.request == 0x20
    return _next()
_reply.window.next_byte = _delayed_reply
_reply.poll()
assert _ordered.cleared and _reply.window.sent == 1
print('PASS: v1.1 reply queued before RD_REQ clear, including GC during preparation; peripheral registers simulated')
_ft = {'__name__': '_i2c_fm_control_compatibility_test'}
_fh = {'__name__': '_i2c_fm_host_compatibility_test'}
exec(${JSON.stringify(i2cFmTargetSource)}, _ft)
exec(${JSON.stringify(i2cFmHostSource)}, _fh)
assert _fh['Remote'].ack_wait_ms == 40 and _fh['shared'].Remote.ack_wait_ms == 10
class _MixBoard:
    def __init__(self):
        self.line_allow = _Flag()
        self.dac_allow = _Flag()
        self.fm = self.ssg = 0
    def write_fm(self,register,value):
        assert register == 0x28 and value in (0,0x10)
        self.fm = value
    def checked(self,register,value):
        assert register == 8 and value in (0,10)
        self.ssg = value
_fb = _MixBoard()
_fc = _ft['ControlTarget'](_fb)
_fl = _ft['link']
_fl.mem32[_fl.IC_RAW_INTR_STAT] = 0
_fl.mem32[_fl.IC_RXFLR] = 0
_fl.mem32[_fl.IC_STATUS] = 0
def _service_mix():
    _fc.poll()
    if _fc.start_requested and not _fc.live_started:
        # Startup is simulated here; CPython tests exercise the real sequence
        # with a model stream and register readbacks, not physical peripherals.
        _fc.live_started = True
class _MixClock:
    ticks = 0
    @staticmethod
    def ticks_ms():
        return _MixClock.ticks
    @staticmethod
    def ticks_us():
        return _MixClock.ticks * 1000
    @staticmethod
    def ticks_diff(a,b):
        return a-b
    @staticmethod
    def sleep_ms(milliseconds):
        while milliseconds:
            delta = min(10,milliseconds)
            _MixClock.ticks += delta
            _service_mix()
            milliseconds -= delta
_ft['live'].time = _fh['time'] = _fh['shared'].time = _MixClock
class _MixLink:
    def writeto(self,address,data,stop=True):
        assert address == 0x42
        _fl.mem32[_fl.IC_STATUS] = 0x40
        for index,value in enumerate(data):
            _fc.window.receive(value | (0x800 if index == 0 else 0))
            _service_mix()
        if stop:
            _fl.mem32[_fl.IC_STATUS] = 0
            _service_mix()
        return len(data)
    def readfrom(self,address,count):
        assert address == 0x42
        _fl.mem32[_fl.IC_STATUS] = 0x40
        result = bytes(_fc.window.next_byte() for _ in range(count))
        # A read ends with STOP. Subsequent clock-driven polls can observe idle;
        # do not leave the simulated bus permanently active after a read.
        _fl.mem32[_fl.IC_STATUS] = 0
        return result
_fh['check'](_MixLink())
assert _fc.window.finished and _fc.expirations == 1 and _fc.live_started
assert not _fb.fm and not _fb.ssg and not _fb.line_allow.state and not _fb.dac_allow.state
assert _fc.window.data[0x11:0x14] == bytes((7,0,0))
print('PASS: live FM/I2C control modes, host sequence and lease mute in MicroPython; audio, transport and clock simulated')
_it = {'__name__': '_isolation_target_compatibility_test'}
_ih = {'__name__': '_isolation_host_compatibility_test'}
exec(${JSON.stringify(isolationTargetSource)}, _it)
exec(${JSON.stringify(isolationHostSource)}, _ih)
_ie = _it['ProbeTarget'](0)
class _IsoLink:
    def writeto(self,address,data,stop=True):
        assert address == 0x42
        _fl.mem32[_fl.IC_STATUS] = 0x40
        for index,value in enumerate(data):
            _ie.window.receive(value | (0x800 if index == 0 else 0))
            _ie.poll()
        if stop:
            _fl.mem32[_fl.IC_STATUS] = 0
            _ie.poll()
        return len(data)
    def readfrom(self,address,count):
        assert address == 0x42
        return bytes(_ie.window.next_byte() for _ in range(count))
class _IsoClock:
    transitions = 0
    @staticmethod
    def sleep_ms(milliseconds):
        global _ie
        assert milliseconds == 3000 and _ie.window.advance
        _ie = _it['ProbeTarget'](_ie.window.phase + 1)
        _IsoClock.transitions += 1
_ih['time'] = _IsoClock
_ih['check'](_IsoLink())
assert _ie.window.phase == 5 and _ie.window.finished and _IsoClock.transitions == 5
print('PASS: six isolation host phases, headers, RAM patterns, protected data and control tokens in MicroPython; setup and bus simulated')
_st = {'__name__': '_staged_target_compatibility_test'}
_sh = {'__name__': '_staged_host_compatibility_test'}
exec(${JSON.stringify(stagedTargetSource)}, _st)
exec(${JSON.stringify(stagedHostSource)}, _sh)
_ie = _it['ProbeTarget'](0)
_fc = _ft['ControlTarget'](_MixBoard())
class _StagedClock:
    live = False
    transitions = 0
    ticks_ms = staticmethod(_MixClock.ticks_ms)
    ticks_diff = staticmethod(_MixClock.ticks_diff)
    @staticmethod
    def sleep_ms(milliseconds):
        global _ie
        if _StagedClock.live:
            _MixClock.sleep_ms(milliseconds)
        else:
            assert milliseconds == 3000
            _MixClock.ticks += milliseconds
            if _ie.window.finished:
                _StagedClock.live = True
            else:
                assert _ie.window.advance
                _ie = _it['ProbeTarget'](_ie.window.phase + 1)
                _StagedClock.transitions += 1
class _StagedLink:
    def writeto(self,*args):
        return (_MixLink() if _StagedClock.live else _IsoLink()).writeto(*args)
    def readfrom(self,*args):
        return (_MixLink() if _StagedClock.live else _IsoLink()).readfrom(*args)
_sh['time'] = _sh['startup'].time = _sh['mixer'].time = _sh['mixer'].shared.time = _StagedClock
_sh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _StagedClock.live
assert _ie.window.finished and _fc.window.finished and _fc.expirations == 1
assert _sh['mixer'].Remote.ack_wait_ms == 40
print('PASS: complete staged startup-to-live host flow and target module import in MicroPython; resources and wire simulated')
_en = {'__name__': '_i2c_endurance_compatibility_test'}
exec(${JSON.stringify(i2cEnduranceSource)}, _en)
_ie = _it['ProbeTarget'](0)
_fc = _ft['ControlTarget'](_MixBoard())
_StagedClock.live = False
_StagedClock.transitions = 0
_en['time'] = _en['staged'].startup.time = _en['staged'].mixer.time = _en['staged'].mixer.shared.time = _StagedClock
_en['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x14] == bytes((7,0,0))
print('PASS: complete three-minute I2C endurance host with ACK wrap and final lease mute in MicroPython; time and wire simulated')
_cy = {'__name__': '_i2c_cycle_compatibility_test'}
exec(${JSON.stringify(i2cCycleSource)}, _cy)
_ie = _it['ProbeTarget'](0)
_fc = _ft['ControlTarget'](_MixBoard())
_StagedClock.live = False
_StagedClock.transitions = 0
_cy['time'] = _cy['endurance'].time = _cy['endurance'].staged.startup.time = _cy['endurance'].staged.mixer.time = _cy['endurance'].staged.mixer.shared.time = _StagedClock
_cy['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x14] == bytes((7,0,0))
print('PASS: complete ten-cycle I2C source/mute host, state readbacks, ACK wrap and final lease mute in MicroPython; time and wire simulated')
_pt = {'__name__': '_i2c_pitch_target_compatibility_test'}
_ph = {'__name__': '_i2c_pitch_host_compatibility_test'}
exec(${JSON.stringify(i2cPitchTargetSource)}, _pt)
exec(${JSON.stringify(i2cPitchHostSource)}, _ph)
class _PitchBoard(_MixBoard):
    def __init__(self):
        super().__init__()
        self.fm_notes = []
        self.period_bytes = [0,0]
    def pitch(self,index):
        assert 0 <= index < 5
        self.fm_notes.append(index)
    def checked(self,register,value):
        if register in (0,1):
            self.period_bytes[register] = value
        else:
            super().checked(register,value)
_pb = _PitchBoard()
_fc = _pt['PitchTarget'](_pb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_ph['time'] = _ph['staged'].startup.time = _ph['mixer'].time = _ph['mixer'].shared.time = _StagedClock
_ph['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x16] == bytes((7,0,0,0,0))
assert _pb.fm_notes == list(_ph['MELODY']) * 2
assert _pb.period_bytes == [239,0]
print('PASS: complete I2C pitch host, four scales, pitch selection readbacks and lease mute in MicroPython; hardware and time simulated')
_tt = {'__name__': '_i2c_timbre_target_compatibility_test'}
_th = {'__name__': '_i2c_timbre_host_compatibility_test'}
exec(${JSON.stringify(i2cTimbreTargetSource)}, _tt)
exec(${JSON.stringify(i2cTimbreHostSource)}, _th)
class _TimbreBoard(_MixBoard):
    def __init__(self):
        super().__init__()
        self.timbre_ready = True
        self.levels = []
        self.multis = []
    def modulation(self,value):
        assert value in (96,64,40,24)
        self.levels.append(value)
    def multiple(self,value):
        assert value in (1,2,3)
        self.multis.append(value)
_tb = _TimbreBoard()
_fc = _tt['TimbreTarget'](_tb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_th['time'] = _th['staged'].startup.time = _th['mixer'].time = _th['mixer'].shared.time = _StagedClock
_th['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x16] == bytes((7,0,0,2,0))
assert _tb.levels == [96,96,64,40,24,40,40] and _tb.multis == [1,2,3,1]
assert not _tb.ssg and not _tb.fm
print('PASS: complete I2C timbre host, four TL and three MULTI settings, retrigger and lease mute in MicroPython; hardware and time simulated')
_ct = {'__name__': '_i2c_combined_target_compatibility_test'}
_ch = {'__name__': '_i2c_combined_host_compatibility_test'}
exec(${JSON.stringify(i2cCombinedTargetSource)}, _ct)
exec(${JSON.stringify(i2cCombinedHostSource)}, _ch)
class _CombinedBoard(_TimbreBoard):
    def __init__(self):
        super().__init__()
        self.pitches = []
        self.starts = 0
    def write_fm(self,register,value):
        super().write_fm(register,value)
        if value == 0x10:
            self.starts += 1
    def modulation(self,value):
        assert not self.fm, 'Timbre setup must precede each initial C'
        super().modulation(value)
    def multiple(self,value):
        assert not self.fm, 'Timbre setup must precede each initial C'
        super().multiple(value)
    def pitch(self,index):
        assert 0 <= index < 5
        self.pitches.append(index)
_cb = _CombinedBoard()
_fc = _ct['CombinedTarget'](_cb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_ch['time'] = _ch['timbre'].staged.startup.time = _ch['mixer'].time = _ch['mixer'].shared.time = _StagedClock
_ch['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x17] == bytes((7,0,0,2,2,0))
assert _cb.levels == [96,40,40,40] and _cb.multis == [1,1,2,3]
assert _cb.pitches == list(_ch['MELODY']) * 4
assert _cb.starts == 5
print('PASS: complete I2C combined host, four separate pitch/timbre scales, seven-byte state and lease mute in MicroPython; hardware and time simulated')
_et = {'__name__': '_i2c_envelope_target_compatibility_test'}
_eh = {'__name__': '_i2c_envelope_host_compatibility_test'}
exec(${JSON.stringify(i2cEnvelopeTargetSource)}, _et)
exec(${JSON.stringify(i2cEnvelopeHostSource)}, _eh)
class _EnvelopeBoard(_MixBoard):
    def __init__(self):
        super().__init__()
        self.timbre_ready = True
        self.presets = []
        self.steps = []
        self.key_off_gates = []
        self.starts = 0
    def envelope_step(self,preset,index):
        assert preset in (0,1) and not self.line_allow.state and not self.dac_allow.state
        assert index == len(self.steps) % 8
        self.steps.append((preset,index))
        if index == 7:
            self.presets.append(preset)
    def write_fm(self,register,value):
        super().write_fm(register,value)
        if value == 0x10:
            self.starts += 1
        elif self.line_allow.state:
            self.key_off_gates.append((self.line_allow.state,self.dac_allow.state))
_eb = _EnvelopeBoard()
_fc = _et['EnvelopeTarget'](_eb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_eh['time'] = _eh['timbre'].staged.startup.time = _eh['mixer'].time = _eh['mixer'].shared.time = _StagedClock
_eh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x16] == bytes((7,0,0,0,0))
assert _eb.presets == [0,1,0] and _eb.starts == 5 and _eb.key_off_gates == [(1,1),(1,1)]
assert _fc.preset_updates == 3 and _fc.preset_writes == 24 and len(_eb.steps) == 24
assert not _fc.keyed and not _eb.line_allow.state and not _eb.dac_allow.state
print('PASS: complete I2C envelope host, sustain/decay presets, open-gate key-off and retrigger, lease mute in MicroPython; hardware and time simulated')
_sxt = {'__name__': '_i2c_six_target_compatibility_test'}
_sxh = {'__name__': '_i2c_six_host_compatibility_test'}
exec(${JSON.stringify(i2cSixTargetSource)}, _sxt)
exec(${JSON.stringify(i2cSixHostSource)}, _sxh)
class _SixBoard:
    def __init__(self):
        self.line_allow = _Flag()
        self.dac_allow = _Flag()
        self.voices = self.writes = 0
    def voice(self,index,enabled):
        assert 0 <= index < 6 and enabled in (0,1)
        assert not self.line_allow.state and not self.dac_allow.state
        bit = 1 << index
        self.voices = (self.voices | bit) if enabled else (self.voices & ~bit)
        self.writes += 1
_sb = _SixBoard()
_fc = _sxt['SixTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_sxh['time'] = _sxh['staged'].startup.time = _sxh['mixer'].time = _sxh['mixer'].shared.time = _StagedClock
_sxh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x16] == bytes((7,0,0,0,0))
assert _fc.jobs == 15 and _fc.writes == 38 and _sb.writes == 38 and _sb.voices == 0
assert _fc.job == -1 and _fc.applied == 0 and not _sb.line_allow.state and not _sb.dac_allow.state
print('PASS: complete I2C six-voice host, solos/chords/mutes, split source updates and lease cleanup in MicroPython; hardware and time simulated')
_sxen = {'__name__': '_i2c_six_endurance_compatibility_test'}
exec(${JSON.stringify(i2cSixEnduranceSource)}, _sxen)
_sb = _SixBoard()
_fc = _sxt['SixTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_sxen['time'] = _sxen['six'].staged.startup.time = _sxen['mixer'].time = _sxen['mixer'].shared.time = _StagedClock
_sxen['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x16] == bytes((7,0,0,0,0))
assert _fc.jobs == 7 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0
assert _fc.job == -1 and _fc.applied == 0 and not _sb.line_allow.state and not _sb.dac_allow.state
print('PASS: complete three-minute I2C six-voice endurance host, KEEP/status integrity, ACK wrap and lease cleanup in MicroPython; hardware and time simulated')
_sxcy = {'__name__': '_i2c_six_cycle_compatibility_test'}
exec(${JSON.stringify(i2cSixCycleSource)}, _sxcy)
_sb = _SixBoard()
_fc = _sxt['SixTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_sxcy['time'] = _sxcy['six'].staged.startup.time = _sxcy['mixer'].time = _sxcy['mixer'].shared.time = _StagedClock
_sxcy['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x11:0x16] == bytes((7,0,0,0,0))
assert _fc.jobs == 45 and _fc.writes == 192 and _sb.writes == 192 and _sb.voices == 0
assert _fc.job == -1 and _fc.applied == 0 and not _sb.line_allow.state and not _sb.dac_allow.state
print('PASS: complete ten-cycle I2C six-voice host, all80 sections, ACK wrap and lease cleanup in MicroPython; hardware and time simulated')
_sxre = {'__name__': '_i2c_six_recovery_compatibility_test'}
exec(${JSON.stringify(i2cSixRecoverySource)}, _sxre)
class _HostPin:
    IN = 0
    connected = True
    releases = []
    def __init__(self,number,mode=None,pull=None):
        self.number = number
        if mode is not None:
            assert number in (0,1) and mode == self.IN and pull is None
            _HostPin.connected = False
            _HostPin.releases.append(number)
class _RecoveryLink(_StagedLink):
    def writeto(self,*args):
        assert _HostPin.connected, 'I2C write while HOST pins released'
        return super().writeto(*args)
    def readfrom(self,*args):
        assert _HostPin.connected, 'I2C read while HOST pins released'
        return super().readfrom(*args)
_rebind_states = []
def _rebind_HOST(index,*,sda,scl,freq,timeout):
    assert (index,sda.number,scl.number,freq,timeout) == (0,0,1,10000,500000)
    _rebind_states.append((_fc.expirations,_sb.voices,_sb.line_allow.state,_sb.dac_allow.state))
    _HostPin.connected = True
    return _RecoveryLink()
_sxre['Pin'] = _HostPin
_sxre['I2C'] = _rebind_HOST
_sb = _SixBoard()
_fc = _sxt['SixTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_sxre['time'] = _sxre['six'].staged.startup.time = _sxre['mixer'].time = _sxre['mixer'].shared.time = _StagedClock
_observed = _sxre['mixer'].shared.ObservedI2C(_RecoveryLink())
_sxre['check'](_observed)
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _HostPin.releases == [0,1]*3 and _rebind_states == [(i,0,0,0) for i in (1,2,3)]
assert _fc.expirations == 3 and _fc.window.data[0x11:0x16] == bytes((7,0,0,0,0))
assert _fc.jobs == 13 and _fc.writes == 48 and _sb.writes == 48 and _sb.voices == 0
assert _fc.job == -1 and _fc.applied == 0 and not _sb.line_allow.state and not _sb.dac_allow.state
assert _observed.read_calls > 64
print('PASS: complete three-cycle I2C six-voice recovery host, no I2C while pins released, lease cleanup before same-target reattach and explicit restarts in MicroPython; hardware and time simulated')
_vpt = {'__name__': '_i2c_voice_pitch_target_compatibility_test'}
_vph = {'__name__': '_i2c_voice_pitch_host_compatibility_test'}
exec(${JSON.stringify(i2cVoicePitchTargetSource)}, _vpt)
exec(${JSON.stringify(i2cVoicePitchHostSource)}, _vph)
class _VoicePitchBoard(_SixBoard):
    def __init__(self):
        super().__init__()
        self.pitches = list(_vpt['INITIAL'])
        self.pair = None
        self.pitch_writes = 0
        self.active_updates = []
    def active_mask(self,voice):
        return (1 << voice) | (56 if voice < 3 else 7)
    def record_active(self,voice,note):
        self.active_updates.append((voice,note))
    def pitch_step(self,voice,note,step):
        assert 0 <= voice < 6 and 0 <= note < 5 and step in (0,1)
        if step == 0:
            self.pair = (voice,note)
        else:
            assert self.pair == (voice,note)
            self.pitches[voice] = note
            if self.voices:
                assert self.voices == self.active_mask(voice)
                self.record_active(voice,note)
        self.pitch_writes += 1
_sb = _VoicePitchBoard()
_fc = _vpt['PitchTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_vph['time'] = _vph['six'].staged.startup.time = _vph['mixer'].time = _vph['mixer'].shared.time = _StagedClock
_vph['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert _fc.expirations == 1 and _fc.window.data[0x10:0x16] == bytes((201,7,0,0,0,0))
assert _fc.jobs == 17 and _fc.writes == 60 and _sb.writes == 60 and _sb.voices == 0
assert _fc.pitch_updates == 90 and _fc.pitch_writes == 180 and _sb.pitch_writes == 180
assert _fc.pitch_cancelled == 0 and _fc.pitch_command == -1 and _fc.pitch_step == 2
assert _sb.pitches == list(_vpt['INITIAL']) and _fc.window.data[0x16:0x1C] == bytes(_vpt['INITIAL'])
assert _sb.active_updates == [(v,n) for v in range(6) for n in _vph['MELODY'][1:]]
assert _fc.job == -1 and _fc.applied == 0 and not _sb.line_allow.state and not _sb.dac_allow.state
print('PASS: complete I2C per-voice pitch host, six melodies over held chords, split pitch pairs and full state readbacks in MicroPython; hardware and time simulated')
class _HeapProbeGC:
    enabled = True
    scans = 0
    @staticmethod
    def isenabled():
        return _HeapProbeGC.enabled
    @staticmethod
    def enable():
        _HeapProbeGC.enabled = True
    @staticmethod
    def disable():
        _HeapProbeGC.enabled = False
    @staticmethod
    def collect():
        assert _HeapProbeGC.enabled
    @staticmethod
    def mem_alloc():
        assert not _HeapProbeGC.enabled
        assert not _probe_board.voices and not _probe_board.line_allow.state and not _probe_board.dac_allow.state
        _HeapProbeGC.scans += 1
        return 65536
_probe_board = _VoicePitchBoard()
_probe_board.io_version = '1.1'
_saved_gc = _vpt['gc']
_vpt['gc'] = _HeapProbeGC
_vpt['check_bus_heap'](_probe_board)
_vpt['gc'] = _saved_gc
assert _HeapProbeGC.enabled and _HeapProbeGC.scans == 12
assert _probe_board.pitch_writes == 216 and _probe_board.pitches == list(_vpt['INITIAL'])
print('PASS: silent heap preflight control flow, GC restoration and pitch restoration; heap counter mocked here, actual allocation measured separately with Unix MicroPython')
_dy = {'__name__': '_i2c_dynamic_pitch_endurance_compatibility_test'}
exec(${JSON.stringify(i2cVoicePitchEnduranceSource)}, _dy)
class _DynamicPitchBoard(_VoicePitchBoard):
    def __init__(self):
        super().__init__()
        self.active_count = 0
    def active_mask(self,voice):
        return 63
    def record_active(self,voice,note):
        # Stream-check this long run instead of retaining thousands of tuples
        # in the verifier's shared 1MiB WASM heap. Production retains no history.
        assert voice == self.active_count % 6
        group = self.active_count // 6
        assert note == _dy['pitch'].MELODY[(group+_dy['pitch'].INITIAL[voice]) % 9]
        self.active_count += 1
_sb = _DynamicPitchBoard()
_fc = _vpt['PitchTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_dy['time'] = _dy['pitch'].time = _dy['pitch'].six.staged.startup.time = _dy['mixer'].time = _dy['mixer'].shared.time = _StagedClock
_dy['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
_groups = _sb.active_count // 6
assert _groups >= 9 and _groups * 7 >= 256
assert _sb.active_count == _groups * 6 and not _sb.active_updates
assert _fc.expirations == 1 and _fc.window.data[0x10:0x16] == bytes(((_groups*7+59)&255,7,0,0,0,0))
assert _fc.jobs == 7 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0
assert _fc.pitch_updates == _groups*6+12 and _fc.pitch_writes == _groups*12+24 and _sb.pitch_writes == _fc.pitch_writes
assert _fc.pitch_cancelled == 0 and _fc.pitch_command == -1 and _fc.pitch_step == 2
assert _sb.pitches == list(_vpt['INITIAL']) and _fc.window.data[0x16:0x1C] == bytes(_vpt['INITIAL'])
assert _fc.job == -1 and _fc.applied == 0 and not _sb.line_allow.state and not _sb.dac_allow.state
print('PASS: complete three-minute dynamic six-voice pitch endurance host, full pitch integrity, all voices held, ACK wrap and final lease cleanup in MicroPython; hardware and time simulated')
_qt = {'__name__': '_i2c_queue_target_compatibility_test'}
_qh = {'__name__': '_i2c_queue_host_compatibility_test'}
exec(${JSON.stringify(i2cQueueTargetSource)}, _qt)
exec(${JSON.stringify(i2cQueueHostSource)}, _qh)
class _QueueBoard(_VoicePitchBoard):
    def active_mask(self,voice):
        return 1 << voice
    def voice(self,index,enabled):
        assert index in (0,3) and enabled in (0,1)
        if enabled:
            assert not self.line_allow.state and not self.dac_allow.state
        bit = 1 << index
        self.voices = self.voices | bit if enabled else self.voices & ~bit
        self.writes += 1
_sb = _QueueBoard()
_fc = _qt['QueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qh['time'] = _qh['pitch'].time = _qh['pitch'].six.staged.startup.time = _qh['mixer'].time = _qh['mixer'].shared.time = _StagedClock
_qh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.events,_fc.note_writes) == (3,2,1,20,40)
assert list(_fc.run_states) == [4,4,5] and list(_fc.run_voices) == [0,3,3] and list(_fc.run_notes) == [9,9,2]
assert _fc.jobs == 6 and _fc.writes == 6 and _sb.writes == 6 and _sb.voices == 0
assert _fc.expirations == 1 and _fc.max_late_ms <= 100 and _fc.partial_cancels == 0
for _run in (0,1):
    for _note in range(9):
        assert 500*_note <= _fc.times[_run*9+_note] <= 500*_note+100
assert _fc.run_end[0]-_fc.run_off[0] >= 135
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete uploaded nine-note queue host, target-clock FM/SSG scales, variable KEEP gaps, autonomous completion and lease cancellation in MicroPython; hardware and time simulated')
_qs = {'__name__': '_i2c_queue_stop_compatibility_test'}
exec(${JSON.stringify(i2cQueueStopSource)}, _qs)
_sb = _QueueBoard()
_fc = _qt['QueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qs['time'] = _qs['queue'].time = _qs['queue'].pitch.time = _qs['queue'].pitch.six.staged.startup.time = _qs['mixer'].time = _qs['mixer'].shared.time = _StagedClock
_qs['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,1,2,0)
assert list(_fc.run_states) == [5,4,5] and list(_fc.run_voices) == [0,0,3]
assert 3 <= _fc.run_notes[0] < 9 and _fc.run_notes[1] == 9 and 3 <= _fc.run_notes[2] < 9
assert _fc.events == sum(_fc.run_notes) and _fc.note_writes == _fc.events*2+_fc.partial_cancels
assert _fc.jobs == 5 and _fc.writes == 6 and _sb.writes == 6 and _sb.voices == 0
assert _fc.times[9] == 0 and bytes(_fc.score) == bytes(_qs['queue'].pitch.MELODY)
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete queued FM/SSG STOP host,quiet beyond abandoned end,unchanged uploaded score and explicit FM restart from C in MicroPython; hardware and time simulated')
_qat = {'__name__': '_i2c_queue_accomp_target_compatibility_test'}
_qah = {'__name__': '_i2c_queue_accomp_host_compatibility_test'}
exec(${JSON.stringify(i2cQueueAccompTargetSource)}, _qat)
exec(${JSON.stringify(i2cQueueAccompHostSource)}, _qah)
class _AccompBoard(_VoicePitchBoard):
    def active_mask(self,voice):
        return (1 << voice) | (56 if voice == 0 else 7)
    def voice(self,index,enabled):
        assert 0 <= index < 6 and enabled in (0,1)
        if enabled:
            assert not self.line_allow.state and not self.dac_allow.state
        bit = 1 << index
        self.voices = self.voices | bit if enabled else self.voices & ~bit
        self.writes += 1
_sb = _AccompBoard()
_fc = _qat['AccompaniedTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qah['time'] = _qah['queue'].time = _qah['queue'].pitch.time = _qah['queue'].pitch.six.staged.startup.time = _qah['mixer'].time = _qah['mixer'].shared.time = _StagedClock
_qah['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,2,1,1)
assert list(_fc.run_masks) == [57,15,15] and list(_fc.run_notes) == [9,9,2]
assert _fc.events == 20 and _fc.note_writes == 40 and _fc.partial_cancels == 0
assert _fc.jobs == 6 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0 and _fc.applied == 0
for _run in (0,1):
    for _note in range(9):
        assert 500*_note <= _fc.times[_run*9+_note] <= 500*_note+100
    assert _fc.run_end[_run]-_fc.run_off[_run] >= 135
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete queued FM/SSG accompanied melodies,held voice masks,split four-voice start/end and lease cleanup in MicroPython; hardware and time simulated')
_qas = {'__name__': '_i2c_queue_accomp_stop_compatibility_test'}
exec(${JSON.stringify(i2cQueueAccompStopSource)}, _qas)
_sb = _AccompBoard()
_fc = _qat['AccompaniedTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qas['time'] = _qas['accomp'].time = _qas['queue'].time = _qas['queue'].pitch.time = _qas['queue'].pitch.six.staged.startup.time = _qas['mixer'].time = _qas['mixer'].shared.time = _StagedClock
_qas['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,1,2,0)
assert list(_fc.run_masks) == [57,57,15] and list(_fc.run_states) == [5,4,5]
assert list(_fc.run_voices) == [0,0,3] and list(_fc.run_notes) == [3,9,3]
assert _fc.events == 15 and _fc.note_writes == 30 and _fc.partial_cancels == 0
assert _fc.jobs == 5 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0 and _fc.applied == 0
assert bytes(_fc.score) == bytes(_qas['queue'].pitch.MELODY) and _fc.times[9] == 0
for _note in range(9):
    assert 500*_note <= _fc.times[9+_note] <= 500*_note+100
assert _fc.run_end[1]-_fc.run_off[1] >= 135
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete accompanied queue STOP host,all four voices off,quiet beyond abandoned end,unchanged score and FM replay from C in MicroPython; hardware and time simulated')
_qmt = {'__name__': '_i2c_queue_mute_target_compatibility_test'}
_qmh = {'__name__': '_i2c_queue_mute_host_compatibility_test'}
exec(${JSON.stringify(i2cQueueMuteTargetSource)}, _qmt)
exec(${JSON.stringify(i2cQueueMuteHostSource)}, _qmh)
_sb = _AccompBoard()
_fc = _qmt['MutedQueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qmh['time'] = _qmh['accomp'].time = _qmh['queue'].time = _qmh['queue'].pitch.time = _qmh['queue'].pitch.six.staged.startup.time = _qmh['mixer'].time = _qmh['mixer'].shared.time = _StagedClock
_qmh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,2,1,1)
assert list(_fc.run_masks) == [57,15,15] and list(_fc.run_notes) == [9,9,2]
assert _fc.events == 20 and _fc.note_writes == 40 and _fc.partial_cancels == 0
assert _fc.jobs == 6 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0 and _fc.applied == 0
assert (_fc.gate_commands,_fc.dac_mutes,_fc.line_mutes,_fc.restores,_fc.gates()) == (4,1,1,2,0)
for _run,_muted in ((0,2),(1,1)):
    _trace = list(_fc.gate_notes[_run*9:_run*9+9])
    assert _trace[0] == 3 and _trace[-1] == 3 and _trace.count(_muted) >= 2
    for _note in range(9):
        assert 500*_note <= _fc.times[_run*9+_note] <= 500*_note+100
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete queued gate mute HOST,autonomous notes through DAC/LINE mute,restore without replay and all-voice lease cleanup in MicroPython; hardware and time simulated')
_qmsh = {'__name__': '_i2c_queue_mute_stop_compatibility_test'}
exec(${JSON.stringify(i2cQueueMuteStopSource)}, _qmsh)
_sb = _AccompBoard()
_fc = _qmt['MutedQueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qmsh['time'] = _qmsh['muted'].time = _qmsh['muted'].accomp.time = _qmsh['queue'].time = _qmsh['queue'].pitch.time = _qmsh['queue'].pitch.six.staged.startup.time = _qmsh['mixer'].time = _qmsh['mixer'].shared.time = _StagedClock
_qmsh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,1,2,0)
assert list(_fc.run_masks) == [57,57,15] and list(_fc.run_states) == [5,4,5]
assert list(_fc.run_voices) == [0,0,3] and list(_fc.run_notes) == [5,9,5]
assert _fc.events == 19 and _fc.note_writes == 38 and _fc.partial_cancels == 0
assert _fc.jobs == 5 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0 and _fc.applied == 0
assert (_fc.gate_commands,_fc.dac_mutes,_fc.line_mutes,_fc.restores,_fc.gates()) == (2,1,1,0,0)
assert list(_fc.gate_notes[9:18]) == [3]*9 and _fc.times[9] == 0
assert 2 in list(_fc.gate_notes[:9]) and 1 in list(_fc.gate_notes[18:])
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete muted queue STOP HOST,DAC/LINE muted stops,four-second quiet and PLAY-only unmuted FM replay in MicroPython; hardware and time simulated')
_qmlh = {'__name__': '_i2c_queue_mute_lease_compatibility_test'}
exec(${JSON.stringify(i2cQueueMuteLeaseSource)}, _qmlh)
_sb = _AccompBoard()
_fc = _qmt['MutedQueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qmlh['time'] = _qmlh['muted'].time = _qmlh['muted'].accomp.time = _qmlh['queue'].time = _qmlh['queue'].pitch.time = _qmlh['queue'].pitch.six.staged.startup.time = _qmlh['mixer'].time = _qmlh['mixer'].shared.time = _StagedClock
_qmlh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,1,2,2)
assert list(_fc.run_masks) == [57,57,15] and list(_fc.run_states) == [5,4,5]
assert list(_fc.run_notes) == [5,9,5] and list(_fc.gate_notes[9:18]) == [3]*9
assert _fc.events == 19 and _fc.note_writes == 38 and _fc.partial_cancels == 0
assert _fc.jobs == 7 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0 and _fc.applied == 0
assert (_fc.gate_commands,_fc.dac_mutes,_fc.line_mutes,_fc.restores,_fc.gates()) == (2,1,1,0,0)
assert _fc.times[9] == 0 and bytes(_fc.score) == bytes(_qmlh['queue'].pitch.MELODY)
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete muted queue lease HOST,no-traffic DAC/LINE lease cancellations,quiet readback and explicit STOP/PLAY recovery in MicroPython; hardware and time simulated')
_qrh = {'__name__': '_i2c_queue_replace_compatibility_test'}
exec(${JSON.stringify(i2cQueueReplaceSource)}, _qrh)
_sb = _AccompBoard()
_fc = _qmt['MutedQueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_qrh['time'] = _qrh['muted'].time = _qrh['muted'].accomp.time = _qrh['queue'].time = _qrh['queue'].pitch.time = _qrh['queue'].pitch.six.staged.startup.time = _qrh['mixer'].time = _qrh['mixer'].shared.time = _StagedClock
_qrh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,3,0,0)
assert list(_fc.run_masks) == [57,57,15] and list(_fc.run_states) == [4,4,4] and list(_fc.run_notes) == [9,9,9]
assert _fc.events == 27 and _fc.note_writes == 54 and _fc.partial_cancels == 0
assert _fc.jobs == 5 and _fc.writes == 24 and _sb.writes == 24 and _sb.voices == 0 and _fc.applied == 0
assert (_fc.gate_commands,_fc.dac_mutes,_fc.line_mutes,_fc.restores,_fc.gates()) == (0,0,0,0,0)
assert list(_fc.gate_notes) == [3]*27 and bytes(_fc.score) == bytes(_qrh['ALTERNATE'])
assert _sb.active_updates == [(0,n) for n in _qrh['SCALE'][1:]] + [(0,n) for n in _qrh['ALTERNATE'][1:]] + [(3,n) for n in _qrh['ALTERNATE'][1:]]
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete score replacement HOST,original FM scale,new FM melody and unchanged SSG reuse with all27 events in MicroPython; hardware and time simulated')
_rqt = {'__name__': '_i2c_queue_rest_target_compatibility_test'}
_rqh = {'__name__': '_i2c_queue_rest_host_compatibility_test'}
exec(${JSON.stringify(i2cQueueRestTargetSource)}, _rqt)
exec(${JSON.stringify(i2cQueueRestHostSource)}, _rqh)
class _RestBoard(_AccompBoard):
    def voice(self,index,enabled):
        assert 0 <= index < 6 and enabled in (0,1)
        bit = 1 << index
        if enabled and self.line_allow.state:
            assert index == _fc.voice and self.voices == _fc.companions
        self.voices = self.voices | bit if enabled else self.voices & ~bit
        self.writes += 1
    def pitch_step(self,voice,note,step):
        assert 0 <= voice < 6 and 0 <= note < 5 and step in (0,1)
        if step == 0:
            self.pair = (voice,note)
        else:
            assert self.pair == (voice,note)
            self.pitches[voice] = note
            if self.voices:
                full = self.active_mask(voice)
                assert self.voices == full or self.voices == full & ~(1 << voice)
                self.record_active(voice,note)
        self.pitch_writes += 1
_sb = _RestBoard()
_fc = _rqt['RestQueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_rqh['time'] = _rqh['muted'].time = _rqh['muted'].accomp.time = _rqh['queue'].time = _rqh['queue'].pitch.time = _rqh['queue'].pitch.six.staged.startup.time = _rqh['mixer'].time = _rqh['mixer'].shared.time = _StagedClock
_rqh['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,3,0,0)
assert list(_fc.run_masks) == [57,15,57] and list(_fc.run_states) == [4,4,4] and list(_fc.run_notes) == [9,9,9]
assert (_fc.events,_fc.note_writes,_fc.rest_slots,_fc.tone_slots) == (27,36,9,18)
assert (_fc.rest_key_offs,_fc.resume_key_ons,_fc.pair_step) == (9,9,0)
assert _fc.jobs == 5 and _fc.writes == 42 and _sb.writes == 42 and _sb.voices == 0 and _fc.applied == 0
assert list(_fc.played_score) == list(_rqh['SCORE'])*3 and list(_fc.gate_notes) == [3]*27
for _run,_full,_rest in ((0,57,56),(1,15,7),(2,57,56)):
    assert list(_fc.slot_masks[_run*9:_run*9+9]) == [_rest if n == 5 else _full for n in _rqh['SCORE']]
    for _note in range(9):
        assert _note*500 <= _fc.times[_run*9+_note] <= _note*500+100
assert _fc.window.data[0x2A:0x2C] == bytes((9,18))
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: complete queued rest HOST,melody-only key-offs,split pitch/key-on resumes and held companion masks in MicroPython; hardware and time simulated')
_rqf = {'__name__': '_i2c_queue_rest_final_compatibility_test'}
exec(${JSON.stringify(i2cQueueRestFinalSource)}, _rqf)
_sb = _RestBoard()
_fc = _rqt['RestQueueTarget'](_sb)
_ie = _it['ProbeTarget'](0)
_StagedClock.live = False
_StagedClock.transitions = 0
_rqf['time'] = _rqf['rest'].time = _rqf['rest'].muted.time = _rqf['rest'].muted.accomp.time = _rqf['queue'].time = _rqf['queue'].pitch.time = _rqf['queue'].pitch.six.staged.startup.time = _rqf['mixer'].time = _rqf['mixer'].shared.time = _StagedClock
_rqf['check'](_StagedLink())
assert _StagedClock.transitions == 5 and _ie.window.finished and _fc.window.finished
assert (_fc.runs,_fc.completed,_fc.aborted,_fc.expirations) == (3,1,2,1)
assert list(_fc.run_states) == [5,4,5] and list(_fc.run_masks) == [57,57,15]
assert _fc.run_notes[0] == 3 and _fc.run_notes[1] == 9 and 4 <= _fc.run_notes[2] < 9
_tones,_rests,_resumes = [sum(_rqf['counts'](n)[i] for n in _fc.run_notes) for i in range(3)]
assert (_fc.tone_slots,_fc.rest_slots,_fc.resume_key_ons) == (_tones,_rests,_resumes)
assert _fc.events == _tones+_rests and _tones*2 <= _fc.note_writes <= _tones*2+4
assert _fc.jobs == 6 and _fc.writes == 24+2*_resumes and _sb.writes == _fc.writes and _sb.voices == 0 and _fc.applied == 0
assert _fc.times[9] == 0 and list(_fc.played_score[9:18]) == list(_rqf['rest'].SCORE)
assert not _sb.line_allow.state and not _sb.dac_allow.state
_fc.report()
print('PASS: final initial-commissioning rest HOST,first-rest STOP,full replay and no-traffic lease cleanup in MicroPython; hardware and time simulated')
print('NOTE: GPIO, PIO and DMA hardware are not tested by WASM')
`).catch((error) => {
  process.stdout.write(output.join(""));
  throw error;
});
const report = output.join("");
if (!report.includes("PASS: final initial-commissioning rest HOST")) {
  throw new Error("Final initial-commissioning compatibility probe failed");
}
if (!report.includes("PASS: complete queued rest HOST")) {
  throw new Error("Queued rest compatibility probe failed");
}
if (!report.includes("PASS: complete score replacement HOST")) {
  throw new Error("Score replacement compatibility probe failed");
}
if (!report.includes("PASS: complete muted queue lease HOST")) {
  throw new Error("Muted queue lease compatibility probe failed");
}
if (!report.includes("PASS: complete muted queue STOP HOST")) {
  throw new Error("Muted queue STOP compatibility probe failed");
}
if (!report.includes("PASS: complete queued gate mute HOST")) {
  throw new Error("Queued gate mute compatibility probe failed");
}
if (!report.includes("PASS: complete accompanied queue STOP host")) {
  throw new Error("Accompanied STOP/restart compatibility probe failed");
}
if (!report.includes("PASS: complete queued FM/SSG accompanied melodies")) {
  throw new Error("Accompanied queue compatibility probe failed");
}
if (!report.includes("PASS: complete queued FM/SSG STOP host")) {
  throw new Error("Queue STOP/restart compatibility probe failed");
}
if (!report.includes("PASS: complete uploaded nine-note queue host")) {
  throw new Error("Uploaded nine-note queue compatibility probe failed");
}
if (!report.includes("PASS: silent heap preflight control flow")) {
  throw new Error("Silent heap preflight compatibility probe failed");
}
if (!report.includes("PASS: complete three-minute dynamic six-voice pitch endurance host")) {
  throw new Error("Dynamic six-voice pitch endurance compatibility probe failed");
}
if (!report.includes("PASS: complete I2C per-voice pitch host")) {
  throw new Error("I2C per-voice pitch compatibility probe failed");
}
if (!report.includes("PASS: complete three-cycle I2C six-voice recovery host")) {
  throw new Error("I2C six-voice recovery compatibility probe failed");
}
if (!report.includes("PASS: complete ten-cycle I2C six-voice host")) {
  throw new Error("I2C six-voice cycle compatibility probe failed");
}
if (!report.includes("PASS: complete three-minute I2C six-voice endurance host")) {
  throw new Error("I2C six-voice endurance compatibility probe failed");
}
if (!report.includes("PASS: complete I2C six-voice host")) {
  throw new Error("I2C six-voice compatibility probe failed");
}
if (!report.includes("PASS: complete I2C envelope host")) {
  throw new Error("I2C envelope compatibility probe failed");
}
if (!report.includes("PASS: complete I2C combined host")) {
  throw new Error("Combined I2C compatibility probe failed");
}
if (!report.includes("PASS: complete I2C timbre host")) {
  throw new Error("I2C timbre compatibility probe failed");
}
if (!report.includes("PASS: complete I2C pitch host")) {
  throw new Error("I2C pitch compatibility probe failed");
}
if (!report.includes("PASS: complete staged startup-to-live host flow")) {
  throw new Error("Staged startup-to-live compatibility probe failed");
}
if (!report.includes("PASS: complete three-minute I2C endurance host")) {
  throw new Error("Three-minute I2C endurance compatibility probe failed");
}
if (!report.includes("PASS: complete ten-cycle I2C source/mute host")) {
  throw new Error("Ten-cycle I2C compatibility probe failed");
}
if (!report.includes("PASS: corrected Capture allocation") || !report.includes("PASS: user FM word decode") || !report.includes("PASS: live 625-to-540") || !report.includes("PASS: mixed FM/SSG") || !report.includes("PASS: three quiet FM") || !report.includes("PASS: four-operator presets") || !report.includes("PASS: all 16000 endurance") || !report.includes("PASS: I2C diagnostic RAM protocol") || !report.includes("PASS: I2C SSG command acknowledgements") || !report.includes("PASS: v1.1 reply queued") || !report.includes("PASS: live FM/I2C control modes") || !report.includes("PASS: six isolation host phases")) {
  throw new Error(`MicroPython compatibility verification incomplete:\n${report}`);
}
const retainedDelta = /ENDURANCE COMPLETE[^\n]* delta=(-?\d+)/.exec(report);
if (!retainedDelta || Number(retainedDelta[1]) < -4096) {
  throw new Error("Endurance control-loop simulation retained more than 4 KiB after GC");
}
process.stdout.write(report);
