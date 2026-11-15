# SPDX-License-Identifier: MIT
"""Interactive player. Run on the OTHER Pico/Pico2, not the Rev C target."""
from machine import I2C, Pin
from ym2203_revc_stream import RevCStream
from ym2203_revc_player import run_console


def main():
    print('Rev C I2C HOST player v1 / OTHER Pico only')
    print('Target C0.5.0-alpha.3; external5V ON; GP0=SDA GP1=SCL; volumes low; FM100percent')
    print('Select a track to start. Ctrl+C during playback stops and returns to menu.')
    print('Repeat/loop run until Ctrl+C. At menu q or Ctrl+C exits. No auto-play on launch.')
    bus = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000, timeout=100000)
    try:
        stream = RevCStream(bus)  # Read-only attach; menu alone never takes MIDI ownership.
        run_console(stream)
    finally:
        # Each playlist cleans up its own STOP; browsing/exiting an idle menu
        # must not globally stop an unrelated MIDI performance.
        try:
            bus.deinit()
        finally:
            Pin(0, Pin.IN)
            Pin(1, Pin.IN)
        print('HOST SAFE: GP0/GP1 inputs; target lease is fallback on transport failure')


if __name__ == '__main__':
    main()
