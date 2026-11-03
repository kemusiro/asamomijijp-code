#!/usr/bin/env python3
"""1台のPicoで車体コアを一時実行し、元のmain.pyへ戻す。"""
import argparse
import binascii
import json
from pathlib import Path
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--expected-node-id', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--vehicle', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    host = root/'projects/raspberry-pi-pico-cluster/raytracing/host'
    sys.path.insert(0, str(host))
    from vehicle_scene import DEFAULT_SNAPSHOT, load_snapshot, make_job, model_id
    from render_reference import write_png
    from render_vehicle import render
    from mpremote.transport_serial import SerialTransport
    snapshot = load_snapshot(args.vehicle or DEFAULT_SNAPSHOT)
    job = make_job(snapshot, 'recovery')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    module = 'vehicle_probe_' + uuid.uuid4().hex[:8]
    board = SerialTransport(args.port)
    identity = None
    installed = False
    try:
        board.enter_raw_repl(soft_reset=False)
        board.exec('import machine; machine.WDT(timeout=8000).feed()')
        identity = board.exec('import network_config; print(network_config.NODE_ID)').decode().strip()
        if identity != args.expected_node_id:
            raise RuntimeError('対象が一致しません: ' + identity)
        # Fresh interpreter avoids keeping both gallery and vehicle native code.
        board.enter_raw_repl(soft_reset=True)
        board.exec('import machine; machine.WDT(timeout=8000).feed()')
        source = root/'projects/raspberry-pi-pico-cluster/raytracing/pico/vehicle_raytracer.py'
        installed = True
        board.fs_writefile(module + '.py', source.read_bytes())
        board.exec('import machine; machine.WDT(timeout=8000).feed()')
        code = '''import machine, gc, sys, time, json, binascii
wdt=machine.WDT(timeout=8000)
wdt.feed()
import MODULE as core
wdt.feed()
job=JOB
core.validate_job(job)
w,h=job['width'],job['height']
image=bytearray(w*h*3)
buffer=bytearray(8*8*3)
minimum=gc.mem_free()
maximum_ms=0
started=time.ticks_ms()
for y in range(0,h,8):
 for x in range(0,w,8):
  gc.collect()
  wdt.feed()
  tw,th=min(8,w-x),min(8,h-y)
  t=time.ticks_ms()
  core.compute_tile_into(job,x,y,tw,th,buffer)
  maximum_ms=max(maximum_ms,time.ticks_diff(time.ticks_ms(),t))
  minimum=min(minimum,gc.mem_free())
  wdt.feed()
  for row in range(th):
   start=((y+row)*w+x)*3
   image[start:start+tw*3]=buffer[row*tw*3:(row+1)*tw*3]
elapsed=time.ticks_diff(time.ticks_ms(),started)
gc.collect()
print(json.dumps({'runtime':sys.version,'implementation':str(sys.implementation),'elapsedMs':elapsed,'maxTileMs':maximum_ms,'minimumFree':minimum,'freeAfterGc':gc.mem_free(),'crc32':'%08x'%(binascii.crc32(image)&0xffffffff),'rgbHex':binascii.hexlify(image).decode()}))
'''.replace('MODULE', module).replace('JOB', repr(job))
        output, error = board.exec_raw(code, timeout=120)
        if error:
            raise RuntimeError(error.decode())
        raw = output.decode().strip()
        result = json.loads(raw)
        image = bytes.fromhex(result.pop('rgbHex'))
        if len(image) != job['width']*job['height']*3 or '%08x'%(binascii.crc32(image)&0xffffffff) != result['crc32']:
            raise RuntimeError('USB結果の長さ/CRCが一致しません')
        reference, reference_summary = render(job)
        channel_diff = [abs(a-b) for a,b in zip(reference,image)]
        result.update({'nodeId':identity,'port':args.port,'modelId':model_id(snapshot),'source':snapshot['source'],'job':job,
                       'referenceCpythonCrc32':reference_summary['crc32'],
                       'differentPixels':sum(reference[i:i+3] != image[i:i+3] for i in range(0,len(image),3)),
                       'maxChannelDifference':max(channel_diff),'meanChannelDifference':sum(channel_diff)/len(channel_diff),
                       'validation':'single physical Pico over USB; network/16-node execution not verified'})
        write_png(args.output_dir/'pico-vehicle.png', image, job['width'],job['height'])
        (args.output_dir/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
    finally:
        # Only a uniquely named temporary module was written. No main/core/config
        # is replaced. Reset returns to the existing resident gallery worker.
        try:
            if installed:
                board.exec('import os, machine; machine.WDT(timeout=8000).feed(); os.remove(%r)' % (module+'.py'))
            try:
                board.exec_raw_no_follow('import machine; machine.reset()')
            except OSError as exc:
                if exc.errno not in (5, 6, 19): raise
        finally:
            try: board.close()
            except OSError: pass


if __name__ == '__main__':
    main()
