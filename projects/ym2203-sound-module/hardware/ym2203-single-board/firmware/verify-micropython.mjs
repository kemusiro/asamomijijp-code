// SPDX-License-Identifier: MIT
// Run with ./scripts/use-node.sh node <this file>. Hardware/time are modelled.
import { readFile } from "node:fs/promises";
import { loadMicroPython } from "../../../tools/micropython-wasm.mjs";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");
const [core, host, fixture, example, audio, endurance, recovery, midi, usb, pitch, handover, midiTest, handoverTest] = await Promise.all([
  read("src/ym2203_fw.py"), read("host/ym2203_revc.py"),
  read("tests/micro_fixture.py"), read("host/example.py"), read("src/ym2203_audio.py"),
  read("host/endurance.py"), read("host/recovery.py"),
  read("src/ym2203_midi.py"), read("src/ym2203_usb.py"), read("src/ym2203_pitch.py"),
  read("host/midi_handover.py"), read("tests/test_midi.py"), read("tests/test_midi_handover.py"),
]);
const output = [];
const decoder = new TextDecoder();
const mp = await loadMicroPython({ linebuffer: false, stdout: (data) => output.push(decoder.decode(data, { stream: true })) });
mp.FS.writeFile("/ym2203_fw.py", core);
mp.FS.writeFile("/ym2203_revc.py", host);
mp.FS.writeFile("/micro_fixture.py", fixture);
mp.FS.writeFile("/machine.py", "Pin = I2C = USBDevice = object\nmem32 = {}\n");
mp.FS.writeFile("/example.py", example);
mp.FS.writeFile("/endurance.py", endurance);
mp.FS.writeFile("/recovery.py", recovery);
mp.FS.writeFile("/ym2203_midi.py", midi);
mp.FS.writeFile("/ym2203_usb.py", usb);
mp.FS.writeFile("/ym2203_pitch.py", pitch);
mp.FS.writeFile("/midi_handover.py", handover);
const excerpt = (source, start, end) => {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  if (a < 0 || b < 0) throw new Error("Missing model class boundary");
  return source.slice(a, b);
};
// Reuse the exact CPython USB/combined model classes without unittest imports.
mp.FS.writeFile("/handover_model.py", [
  "import ym2203_fw as fw\nimport ym2203_midi as midi\nimport ym2203_usb as usb\nfrom micro_fixture import Wire\n",
  excerpt(midiTest,"class FakeUSB:","with patch.dict(sys.modules,{'machine'"),
  excerpt(midiTest,"class Registers:","class Harness:"),
  excerpt(handoverTest,"class CombinedWire(","def program(wire):"),
].join("\n"));
mp.FS.writeFile("/rev_c_fm_live.py", "class Stream:\n    pass\n");
mp.FS.writeFile("/ym2203_audio.py", audio.replace("@micropython.viper\n", "")
  .replace("source: ptr32, destination: ptr16) -> int", "source, destination)"));
mp.FS.writeFile("/heap_probe.py", `
import gc
import ym2203_fw as fw
class Clock:
    def ticks_ms(self): return 0
    def ticks_diff(self,a,b): return a-b
    def ticks_add(self,a,b): return a+b
class Pin:
    def value(self,n): pass
class Board:
    def __init__(self): self.line_allow=Pin();self.dac_allow=Pin()
    def cancel_write(self): pass
    def write_register(self,r,v): return True
def measure():
    engine=fw.Engine(Board(),Clock())
    engine.active=engine.running=True
    gc.collect();gc.disable()
    before=gc.mem_alloc()
    for unused in range(1000):
        engine.queue.push(0,0xA0,1)
        engine.poll()
    growth=gc.mem_alloc()-before
    gc.enable()
    assert engine.executed==1000 and engine.queue.count==0
    print('ENGINE HEAP:1000 queued register opportunities,bytes=%d'%growth)
    # This WASM build records allocations here. Use the separate Unix
    # v1.29 small-int probe;neither is a physical RP2350 heap measurement.
`);
try {
  await mp.runPythonAwaitable(`
import sys
import ym2203_fw as fw
import ym2203_revc as host
from micro_fixture import Wire
from example import events
import ym2203_audio as audio
print(sys.version)
wire=Wire()
client=wire.client()
client.pure_fm()
client.ssg_bass()
client.stream(events(2))
assert not wire.engine.failed and not wire.engine.expired
assert wire.engine.gates==0 and wire.board.regs[8:11]==bytes((0,0,0))
assert wire.engine.queue.count==0
print('PASS: actual v0.1 host,CRC frames,initialization,streamed melody/rests,seal/drain and STOP in MicroPython;hardware/time simulated')
del wire,client
import gc
gc.collect()
class StretchedWire(Wire):
    stretch_us=5000
    def service(self,idle):
        before=len(self.board.calls)
        super().service(idle)
        if len(self.board.calls)!=before: self.clock.us+=4400
    def writeto(self,address,data):
        self.clock.advance(self.stretch_us,False)
        return super().writeto(address,data)
    def readfrom(self,address,count):
        self.clock.advance(self.stretch_us,False)
        return super().readfrom(address,count)
for latency in (5000,30000):
    stretched=StretchedWire()
    stretched.stretch_us=latency
    stretched.trace_transfers=False
    client=stretched.client()
    client.pure_fm();client.ssg_bass()
    expected=list(events(2))
    offset=len(stretched.board.calls)
    client.stream(iter(expected))
    actual=stretched.board.calls[offset+6:offset+6+len(expected)]
    assert [(r,v) for t,r,v in actual]==[(r,v) for d,r,v in expected]
    assert stretched.engine.executed==len(expected)
    assert not stretched.engine.failed and stretched.engine.expirations==0
    assert stretched.engine.gates==0 and stretched.engine.max_late<=100
    del stretched,client,expected,actual
    gc.collect()
print('PASS: actual MicroPython host/core plays exact demo under5/30ms I2C stretching and4.4ms YM write model;no LATE suppression')
wire2=Wire()
wire2.trace_transfers=False
client2=wire2.client()
def long_events():
    for i in range(300): yield 200,0xA0,i&255
client2.stream(long_events())
assert wire2.engine.executed==300 and not wire2.engine.failed
assert wire2.engine.expirations==0 and wire2.engine.gates==0
print('PASS:300 streamed register events exceed128-entry ring;sequence/replenishment stay operational')
del wire2,client2
gc.collect()
import endurance
stream_wire=StretchedWire()
stream_wire.trace_transfers=False
endurance.Pin=lambda n:n
endurance.I2C=lambda *args,**kwargs:stream_wire
original_host_time=host.time
original_endurance_time=endurance.time
host.time=stream_wire.clock
endurance.time=stream_wire.clock
try:
    endurance.main()
finally:
    host.time=original_host_time
    endurance.time=original_endurance_time
assert stream_wire.engine.executed==726 and stream_wire.engine.expirations==0
assert not stream_wire.engine.failed and stream_wire.engine.gates==0
assert stream_wire.engine.status[1:]==bytes((0,1,0))
print('PASS: actual endurance.main726-event/180000ms source,progress,normal end and STOP;hardware/time simulated')
del stream_wire
import sys
del sys.modules['endurance']
del endurance
gc.collect()
import recovery
recovery_wire=StretchedWire()
recovery_wire.trace_transfers=False
class RecoveryPin:
    IN=0
    def __init__(self,n,mode=None,pull=None): pass
recovery.Pin=RecoveryPin
recovery.I2C=lambda *args,**kwargs:recovery_wire
original_host_time=host.time
original_recovery_time=recovery.time
host.time=recovery_wire.clock
recovery.time=recovery_wire.clock
try:
    recovery.main()
finally:
    host.time=original_host_time
    recovery.time=original_recovery_time
assert recovery_wire.engine.expirations==1 and recovery_wire.engine.gates==0
assert not recovery_wire.engine.failed and recovery_wire.engine.queue.count==0
assert recovery_wire.engine.status[1:]==bytes((0,1,0))
print('PASS: actual recovery.main STOP/4s quiet/replay/lease/read-only rebind/explicit recovery;hardware/time simulated')
del recovery_wire
del sys.modules['recovery']
del recovery
gc.collect()
import ym2203_midi as midi
import ym2203_usb as usb
from micro_fixture import Clock,Board
class USBModel:
    pending=False
    def submit_xfer(self,ep,buffer):
        assert not self.pending
        self.pending=True;self.buffer=buffer
        return True
    def receive(self,data):
        assert self.pending
        self.buffer[:len(data)]=data
        self.pending=False
        transport.xfer_cb(3,0,len(data))
class SOFModel:
    frozen=None
    def __getitem__(self,address):
        return (clock.us//1000)&2047 if self.frozen is None else self.frozen
clock=Clock();board=Board(clock);engine=midi.Engine(board,clock)
device=USBModel();registers=SOFModel()
transport=usb.Transport(device,2,3,clock,registers)
control=midi.Controller(engine,transport,clock)
transport.open_cb(bytes((9,4,2,0,0,1,1,0,0)))
transport.start()
def service(idle):
    before=len(board.calls)
    engine.poll(idle);control.poll()
    assert len(board.calls)-before<=1
clock.service=service
clock.sleep_ms(12)
packet=bytearray()
for channel in range(6): packet.extend((9,0x90|channel,60+channel,100))
device.receive(packet);clock.sleep_ms(500)
assert engine.midi_mask==63 and engine.gates==3
clock.sleep_ms(3000)
assert control.owned and engine.expirations==0
registers.frozen=registers[usb.SOF_RD];clock.sleep_ms(350)
assert not control.owned and engine.gates==0
registers.frozen=None;clock.sleep_ms(100)
assert not control.owned
# A new Note On is needed after USB frame flow resumes.
device.receive(bytes((9,0x93,60,100)));clock.sleep_ms(400)
assert control.owned and engine.midi_mask==8
request=bytearray(16);request[0]=1;request[1]=(engine.seq+1)&255;request[2]=fw.STOP
crc=host.crc16(memoryview(request)[:14]);request[14]=crc&255;request[15]=crc>>8
engine.accept(request);clock.sleep_ms(150)
assert not control.owned and engine.gates==0 and engine.midi_mask==0
print('PASS: actual MIDI/USB modules,six-voice note plan,long notes,SOF loss/resume and I2C STOP;one-register budget;USB/GPIO/time simulated')
del clock,board,engine,device,registers,transport,control,packet,request
gc.collect()
import midi_handover as handover
from handover_model import CombinedWire
combined=CombinedWire();combined.trace_transfers=False
combined.chord();combined.clock.sleep_ms(500);combined.actor=True
handover.Pin=lambda n:n
handover.I2C=lambda *args,**kwargs:combined
original_host_time=host.time
host.time=combined.clock;handover.time=combined.clock
try:
    handover.main()
finally:
    host.time=original_host_time
assert combined.attempted and combined.recovered
assert combined.control.rejected==6
assert combined.engine.gates==0 and combined.engine.midi_mask==0
assert combined.engine.expirations==0 and not combined.control.owned
print('PASS: actual midi_handover.main attaches without STOP,verifies BUSY,I2C chord,quiet and explicit MIDI recovery;USB/user actions/GPIO/time simulated')
del combined
del sys.modules['midi_handover']
del handover
gc.collect()
source=[0x0600<<19]*625
destination=[0]*1080
assert audio.convert(source,destination)==0
source=[0x1FFF<<19]*625
result=audio.convert(source,destination)
assert result>>16==0 and result==4088
assert destination[0]==4088 and destination[1]==0
print('PASS: full-range floating-point FM scaling keeps PCM cap4096 and right digital channel zero')
import heap_probe
heap_probe.measure()
print('PASS: MicroPython firmware compatibility;WASM allocation observed,not an RP2350 heap guarantee')
`);
} catch (error) {
  process.stdout.write(output.join(""));
  throw error;
}
const report = output.join("");
if (!report.includes("PASS: MicroPython firmware compatibility")) throw new Error("Firmware probe incomplete");
process.stdout.write(report);
