"""Verify that an exception releases PIO and the DMA channel."""

from machine import Pin
import rp2


@rp2.asm_pio(
    out_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=8,
)
def output_serial_bits():
    out(pins, 1)


pattern = bytearray(16 * 1024)
for index in range(len(pattern)):
    pattern[index] = (0xF0, 0xAA, 0x00, 0xFF)[index & 3]

pin = Pin(16, Pin.OUT, value=0)
state_machine = rp2.StateMachine(
    0,
    output_serial_bits,
    freq=100_000,
    out_base=pin,
)
dma = rp2.DMA()
first_channel = dma.channel
ctrl = dma.pack_ctrl(
    size=0,
    inc_read=True,
    inc_write=False,
    treq_sel=0,
)
active_before_exception = False
caught = False

try:
    state_machine.active(1)
    dma.config(
        read=pattern,
        write=state_machine,
        count=len(pattern),
        ctrl=ctrl,
        trigger=True,
    )
    active_before_exception = dma.active()
    raise RuntimeError("intentional cleanup test")
except RuntimeError:
    caught = True
finally:
    state_machine.active(0)
    pin.init(Pin.OUT, value=0)
    dma.close()

replacement = rp2.DMA()
try:
    print("VERIFY,active_before_exception,%d" % active_before_exception)
    print("VERIFY,exception_caught,%d" % caught)
    print("VERIFY,state_machine_active_after_cleanup,%d" % state_machine.active())
    print("VERIFY,gp16_after_cleanup,%d" % pin.value())
    print("VERIFY,first_dma_channel,%d" % first_channel)
    print("VERIFY,replacement_dma_channel,%d" % replacement.channel)
    if not active_before_exception or not caught:
        raise RuntimeError("the intentional exception was not exercised")
    if state_machine.active() or pin.value():
        raise RuntimeError("PIO or GP16 remained active")
    if replacement.channel != first_channel:
        raise RuntimeError("the DMA channel was not released")
finally:
    replacement.close()

print("STATUS,ok")
