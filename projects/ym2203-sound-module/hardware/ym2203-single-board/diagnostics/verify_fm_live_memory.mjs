// SPDX-License-Identifier: MIT
// Real MicroPython heap regression; GPIO, DMA and the Arm Viper emitter are unused.
import { readFile } from "node:fs/promises";
import { loadMicroPython } from "../../../tools/micropython-wasm.mjs";

const source = await readFile(new URL("rev_c_fm_live.py", import.meta.url), "utf8");
const scalar = source.replace("@micropython.viper\n", "")
  .replace("source: ptr32, destination: ptr16) -> int", "source, destination)");
const output = [];
const decoder = new TextDecoder();
const mp = await loadMicroPython({
  heapsize: 256 * 1024,
  linebuffer: false,
  stdout: (data) => output.push(decoder.decode(data, { stream: true })),
});
mp.FS.writeFile("/machine.py", "class Pin:\n    pass\n");
mp.FS.writeFile("/rev_c_bus_check.py", "I2S_OUTPUT_GPIO = (10,11,12)\ndef _check_platform():\n    pass\ndef _diagnose(bus):\n    pass\ndef _emergency_stop():\n    pass\n");
mp.FS.writeFile("/rev_c_fm_capture.py", "class RevCFMBus:\n    pass\n");
mp.FS.writeFile("/rev_c_dac_check.py", "def _send(*args):\n    pass\ndef _write(*args):\n    pass\n");
await mp.runPythonAwaitable(`
import gc
import sys
print(sys.version)
_ns = {'__name__': '_live_memory_regression'}
exec(${JSON.stringify(scalar)}, _ns)
_ctrl = 0x04A41033
gc.collect()
_old_failed = False
gc.disable()
try:
    for _i in range(50000):
        _unused = (_ctrl | _ctrl) & 0xE0000000
except MemoryError:
    _old_failed = True
finally:
    gc.enable()
    gc.collect()
assert _old_failed, 'Original allocating status mask did not exhaust bounded heap'
print('PASS: original big-int status mask with GC disabled reproduces MemoryError')
gc.collect()
_shift_before = gc.mem_free()
gc.disable()
try:
    for _i in range(50000):
        if _ctrl >> 29 or _ctrl >> 29:
            raise AssertionError('Unexpected error bits')
    _shift_after = gc.mem_free()
finally:
    gc.enable()
    gc.collect()
assert _shift_before - _shift_after <= 4096
print('PASS: 50000 shifted error checks with GC disabled; heap growth=%d bytes' % (_shift_before - _shift_after))

class Clock:
    @staticmethod
    def ticks_us():
        return 0
    @staticmethod
    def ticks_diff(a, b):
        return 0
class Dma:
    ctrl = _ctrl
_ns['time'] = Clock
_stream = _ns['Stream']()
_stream.running = True
_stream.mem32 = {_ns['FDEBUG']: 0}
_stream.dmas = [Dma(), Dma()]
gc.collect()
_before = gc.mem_free()
gc.enable()
for _i in range(50000):
    _stream.check()
gc.collect()
_after = gc.mem_free()
assert _before - _after <= 4096, 'Status polling still grows the heap'
print('PASS: 50000 corrected Stream.check calls with GC enabled; retained heap growth=%d bytes' % (_before - _after))
print('NOTE: 256 KiB WASM heap; GPIO/DMA timing and Arm native execution are not tested')
`);
const report = output.join("");
if (!report.includes("PASS: original big-int") || !report.includes("PASS: 50000 corrected")) {
  throw new Error(`Memory regression verification incomplete:\n${report}`);
}
process.stdout.write(report);
