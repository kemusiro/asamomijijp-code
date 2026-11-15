# SPDX-License-Identifier: MIT
"""Compile real usb.c with pinned TinyUSB headers; inspect CDC+MIDI descriptors."""
import argparse
import ctypes as C
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(sdk):
    lock = json.loads((ROOT / 'toolchain-lock.json').read_text())
    tinyusb = sdk / 'lib/tinyusb'
    commit = subprocess.check_output(['git', '-C', str(tinyusb), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != lock['tinyusb']['commit']:
        raise ValueError('Pinned TinyUSB checkout required')
    with tempfile.TemporaryDirectory(prefix='revc-usb-desc-') as folder:
        folder = Path(folder)
        (folder / 'pico').mkdir()
        (folder / 'pico/unique_id.h').write_text('''#include <stddef.h>
#define PICO_UNIQUE_BOARD_ID_SIZE_BYTES 8
static inline void pico_get_unique_board_id_string(char *s,size_t n){
 const char id[]="0123456789abcdef";for(size_t i=0;i<n;i++)s[i]=i<sizeof(id)?id[i]:0;
}
''')
        lib = folder / 'usb.so'
        subprocess.run([shutil.which('cc'), '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-DCFG_TUSB_MCU=OPT_MCU_NONE', '-DTUP_DCD_ENDPOINT_MAX=16',
                        '-I' + str(folder), '-I' + str(ROOT / 'src'), '-I' + str(tinyusb / 'src'),
                        str(ROOT / 'src/usb.c'), '-o', str(lib)], check=True)
        c = C.CDLL(str(lib))
        c.revc_usb_identity_init()
        c.tud_descriptor_device_cb.restype = C.c_void_p
        c.tud_descriptor_configuration_cb.restype = C.c_void_p
        c.tud_descriptor_string_cb.restype = C.c_void_p
        device = C.string_at(c.tud_descriptor_device_cb(), 18)
        p = c.tud_descriptor_configuration_cb(0)
        head = C.string_at(p, 9)
        config = C.string_at(p, int.from_bytes(head[2:4], 'little'))
        assert device[:2] == bytes([18, 1])
        assert struct.unpack_from('<HHH', device, 8) == (0x2e8a, 9, 0x0501)
        assert head[4] == 4 and len(config) == 175
        interfaces, endpoints, iads, descs = [], [], [], []
        pos = 0
        while pos < len(config):
            size, kind = config[pos:pos + 2]
            assert size >= 2 and pos + size <= len(config)
            d = config[pos:pos + size]
            descs.append(d)
            if kind == 4:
                interfaces.append((d[2], d[5], d[6]))
            elif kind == 5:
                endpoints.append(d[2])
            elif kind == 11:
                iads.append((d[2], d[3], d[4]))
            pos += size
        assert interfaces == [(0, 2, 2), (1, 10, 0), (2, 1, 1), (3, 1, 3)]
        assert endpoints == [0x81, 0x02, 0x82, 0x03, 0x83]
        assert len(set(endpoints)) == 5
        assert iads == [(0, 2, 2), (2, 2, 1)]
        assert bytes([7, 0x24, 1, 0, 1, 65, 0]) in descs
        assert bytes([5, 0x25, 1, 1, 1]) in descs and bytes([5, 0x25, 1, 1, 3]) in descs
        names = []
        for i in [2, 4, 5]:
            p = c.tud_descriptor_string_cb(i, 0x409)
            n = C.string_at(p, 1)[0]
            names.append(C.string_at(p, n)[2:].decode('utf-16-le'))
        assert names == ['YM2203 Rev C C MIDI', 'Rev C control', 'YM2203 Rev C MIDI']
        return dict(passed=True, scope='Actual usb.c and pinned TinyUSB descriptor macros; no OS enumeration',
                    tinyusb_commit=commit, configuration_bytes=len(config), interfaces=interfaces,
                    endpoints=endpoints, IADs=iads, strings=names, usb_midi_version='1.0', CDC_retained=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sdk', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(verify(args.sdk), indent=2))
