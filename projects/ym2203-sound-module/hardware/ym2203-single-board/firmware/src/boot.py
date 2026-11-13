# SPDX-License-Identifier: MIT
"""Install on Rev C root to enumerate MIDI+CDC before the audio server starts."""
import os
try:
    os.stat('/disable-ym2203')
except OSError as error:
    if error.args[0]!=2:raise
    from ym2203_usb import configure
    configure()
