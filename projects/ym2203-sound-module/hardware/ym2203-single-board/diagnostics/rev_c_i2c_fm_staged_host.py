# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""One hardware-I2C host session: staged startup followed by live FM/SSG."""
import time
import rev_c_i2c_isolation_host as startup
import rev_c_i2c_fm_host as mixer


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install updated rev_c_i2c_fm_host.py and soft reset")
    startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for live-control READY")
    time.sleep_ms(3000)
    mixer.check(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / staged I2C + live FM mixer HOST v1.3 / OTHER Pico only")


if __name__ == "__main__":
    run()
