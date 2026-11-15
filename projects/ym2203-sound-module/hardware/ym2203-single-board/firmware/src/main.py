# SPDX-License-Identifier: MIT
"""Copy to Pico2 root for automatic startup;Ctrl+C during the2s recovery window."""
import time
import os

try:
    os.stat("/disable-ym2203")
except OSError as error:
    if error.args[0] != 2: raise
    print("YM2203 firmware boot in2s;Ctrl+C cancels;outputs remain muted")
    time.sleep_ms(2000)
    from ym2203_hw import run
    run()
else:
    print("YM2203 autostart disabled by /disable-ym2203")
