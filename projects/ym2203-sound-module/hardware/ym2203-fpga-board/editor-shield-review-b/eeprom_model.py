# SPDX-License-Identifier: MIT
"""PC-only page-write planner. ACK polling is a firmware contract, not a driver."""
from voice_model import encode, integer, SIZE
PAGE=64
CHUNK=16
ACK_DEADLINE_MS=10

def chunks(address,data):
    integer(address,0,SIZE-1)
    data=bytes(data)
    if address+len(data)>SIZE:raise ValueError('memory bounds')
    while data:
        n=min(CHUNK,PAGE-address%PAGE,len(data))
        yield address,data[:n]
        address+=n;data=data[n:]

def save_plan(voice,slot,target,generation):
    integer(slot,0,63);integer(target,0,1)
    base=(slot*2+target)*256;record=encode(voice,slot,generation)
    # Each WRITE must finish ACK polling before the next operation.
    return [('write',base+255,b'\0')]+[('write',a,b) for a,b in chunks(base,record[:255])]+[('verify_uncommitted',base,record[:255]),('write',base+255,b'\xa5'),('verify_committed',base,record)]

def poll_result(elapsed_ms,ack):
    """Caller releases bus between attempts and services STOP every iteration."""
    if elapsed_ms>=ACK_DEADLINE_MS:raise TimeoutError('EEPROM write deadline')
    return 'ready' if ack else 'pending'
