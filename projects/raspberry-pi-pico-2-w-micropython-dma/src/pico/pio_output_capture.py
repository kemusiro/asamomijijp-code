"""Output the article pattern on GP16 for an external logic capture."""

from machine import Pin
import rp2
import time


PIO0_SM0_TX_DREQ = 0
PATTERN_VALUES = (0xF0, 0xAA, 0x00, 0xFF)
PATTERN_REPETITIONS = 4096
START_DELAY_MS = 500


@rp2.asm_pio(
    out_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=8,
)
def output_serial_bits():
    out(pins, 1)


try:
    frequency = int(CAPTURE_FREQUENCY_HZ)
except NameError:
    frequency = 100_000
if frequency not in (100_000, 1_000_000, 10_000_000):
    raise ValueError("frequency must be 100000, 1000000, or 10000000")

pattern = bytearray(len(PATTERN_VALUES) * PATTERN_REPETITIONS)
for index in range(len(pattern)):
    pattern[index] = PATTERN_VALUES[index & 3]

output_pin = Pin(16, Pin.OUT, value=0)
state_machine = rp2.StateMachine(
    0, output_serial_bits, freq=frequency, out_base=output_pin
)
dma = rp2.DMA()
ctrl = dma.pack_ctrl(
    size=0,
    inc_read=True,
    inc_write=False,
    treq_sel=PIO0_SM0_TX_DREQ,
    bswap=False,
)

print(
    "READY,frequency_hz=%d,bytes=%d,delay_ms=%d"
    % (frequency, len(pattern), START_DELAY_MS)
)

try:
    time.sleep_ms(START_DELAY_MS)
    state_machine.active(1)
    started = time.ticks_us()
    dma.config(
        read=pattern,
        write=state_machine,
        count=len(pattern),
        ctrl=ctrl,
        trigger=True,
    )
    while dma.active():
        pass
    dma_elapsed_us = time.ticks_diff(time.ticks_us(), started)

    while state_machine.tx_fifo():
        pass
    time.sleep_us((8_000_000 + frequency - 1) // frequency + 10)
    print("DONE,dma_elapsed_us=%d" % dma_elapsed_us)
finally:
    state_machine.active(0)
    output_pin.init(Pin.OUT, value=0)
    dma.close()
