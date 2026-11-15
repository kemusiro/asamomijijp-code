# SPDX-License-Identifier: MIT
"""Run from Thonny on the OTHER Pico/Pico2,not the Rev C target."""
from machine import I2C, Pin
import time
from ym2203_revc_stream import RevCStream

def main():
    print('Rev C C I2C v2 / Ys II HOST / OTHER Pico only')
    print('GP0=SDA GP1=SCL GND shared;3.3V signals;external Rev C5V on')
    print('Start volumes low. FM100% on target. Sound starts after file validation.')
    bus = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000, timeout=100000)
    try:
        player = RevCStream(bus)
        print('PASS: C firmware I2C v2 identified;100kHz,32 events per request')
        print('Run will take about5minutes. No progress prints during playback.')
        time.sleep(5)
        result = player.play_file('/music/song.bin')
        print('HOST PASS: all %d/%d events,period=%dms,CRC32=%08x' %
              (result['executed'], result['total'], result['period_ms'], result['crc32']))
        print('I2C: commands=%d status_reads=%d retries=%d min_queue=%d max_late_us=%d' %
              (player.commands, player.status_reads, player.retries, result['min_queue'], result['max_late_us']))
        print('DONE: target completed and muted;no automatic replay')
    finally:
        bus.deinit()
        Pin(0, Pin.IN)
        Pin(1, Pin.IN)
        print('HOST SAFE: GP0/GP1 inputs;target lease mutes an interrupted session')

if __name__ == '__main__':
    main()
