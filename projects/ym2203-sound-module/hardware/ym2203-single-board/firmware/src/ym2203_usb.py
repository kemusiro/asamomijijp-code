# SPDX-License-Identifier: MIT
"""Bounded USB-MIDI1.0 receive transport,composed with built-in CDC.

Implemented from USB-MIDI1.0 Appendix B and MicroPython1.29 USBDevice API.
Callbacks only record state; application polling consumes/rearms the64-byte
buffer. No Python scheduling queue or YM writes in USB callbacks.
"""
import time
from machine import USBDevice, mem32

SOF_RD = 0x50110048  # RP2350 USBCTRL_REGS_BASE + USB_SOF_RD_OFFSET
SOF_TIMEOUT_MS = 250
_transport = None
_requested = False


def descriptors(builtin):
    if len(builtin.desc_dev)!=18 or len(builtin.desc_cfg)<9:
        raise ValueError('Invalid built-in USB descriptors')
    itf,ep,string = builtin.itf_max,builtin.ep_max,builtin.str_max
    if itf>253 or not 1<=ep<=15 or string>254:
        raise ValueError('No room for MIDI interfaces/endpoints/strings')
    # Two interfaces grouped by an IAD. USB-MIDI1.0's conventional Appendix B
    # MS total65 includes its37 interface/jack bytes and28 endpoint bytes.
    extra = bytes((
        8,11,itf,2,1,0,0,string,
        9,4,itf,0,0,1,1,0,string,
        9,0x24,1,0,1,9,0,1,itf+1,
        9,4,itf+1,0,2,1,3,0,string,
        7,0x24,1,0,1,65,0,
        6,0x24,2,1,1,0,
        6,0x24,2,2,2,0,
        9,0x24,3,1,3,1,2,1,0,
        9,0x24,3,2,4,1,1,1,0,
        9,5,ep,2,64,0,0,0,0,
        5,0x25,1,1,1,
        9,5,ep|128,2,64,0,0,0,0,
        5,0x25,1,1,3,
    ))
    cfg = bytearray(builtin.desc_cfg)
    cfg.extend(extra)
    cfg[2],cfg[3] = len(cfg)&255,len(cfg)>>8
    cfg[4] = itf+2
    device = bytearray(builtin.desc_dev)
    device[12],device[13] = 0,2  # bcdDevice2.00;retain built-in VID/PID/CDC
    strings = {string:'YM2203 Rev C MIDI',device[15]:'YM2203 Rev C MIDI'}
    return device,cfg,strings


class Transport:
    def __init__(self,device,itf,ep,clock=None,registers=None):
        self.device,self.itf,self.ep = device,itf,ep
        self.clock = time if clock is None else clock
        self.mem32 = mem32 if registers is None else registers
        self.buffer = bytearray(64)
        self.count = self.offset = 0
        self.opened = self.armed = self.online = self.fault = self.enabled = False
        self.last_sof = -1
        self.last_sof_ms = self.clock.ticks_ms()
        # Prebind callback objects before audio capture starts.
        self.open_cb,self.reset_cb,self.xfer_cb = self._open,self._reset,self._xfer

    def _open(self,descriptor):
        if len(descriptor)>=9 and descriptor[1]==4 and descriptor[2]==self.itf:
            self.opened = True

    def _reset(self):
        self.opened = self.armed = self.online = False
        self.count = self.offset = 0
        self.fault = True
        self.last_sof = -1

    def _xfer(self,ep,result,size):
        if ep!=self.ep:return
        self.armed = False
        if not self.enabled:
            self.count = self.offset = 0
            return
        if result!=0 or size<0 or size>64 or size&3:
            self.count = self.offset = 0
            self.fault = True
        else:
            self.count,self.offset = size,0

    def service(self):
        now = self.clock.ticks_ms()
        sof = self.mem32[SOF_RD]&2047
        if sof!=self.last_sof:
            self.last_sof,self.last_sof_ms = sof,now
        online = self.opened and self.clock.ticks_diff(now,self.last_sof_ms)<SOF_TIMEOUT_MS
        if self.online and not online:self.fault = True
        self.online = online
        if not online:self.discard()

    def discard(self):
        # An already armed hardware transfer remains owned by USB until its
        # callback/reset. Never reuse/mutate a buffer that USB may be writing.
        self.count = self.offset = 0

    def start(self):
        self.discard()
        self.enabled = True

    def stop(self):
        self.enabled = False
        self.discard()

    def arm(self):
        if not self.enabled or not self.online or self.armed or self.count:return
        self.armed = True
        try:
            if not self.device.submit_xfer(self.ep,self.buffer):self.armed = False
        except OSError:
            self.armed = False
            self.fault = True


def configure():
    global _transport,_requested
    if _transport is not None:return _transport
    _requested = True
    device = USBDevice()
    if not hasattr(device,'BUILTIN_CDC') or device.BUILTIN_DEFAULT is not device.BUILTIN_CDC:
        raise RuntimeError('USB-MIDI requires the built-in CDC driver')
    builtin = device.BUILTIN_DEFAULT
    device.active(False)
    device.builtin_driver = builtin
    dev,cfg,strings = descriptors(builtin)
    transport = Transport(device,builtin.itf_max,builtin.ep_max)
    device.config(dev,cfg,strings,open_itf_cb=transport.open_cb,
                  reset_cb=transport.reset_cb,xfer_cb=transport.xfer_cb)
    device.active(True)
    _transport = transport
    return transport


def get_transport():
    if _requested and _transport is None:
        raise RuntimeError('USB-MIDI boot configuration failed;outputs remain muted')
    return _transport
