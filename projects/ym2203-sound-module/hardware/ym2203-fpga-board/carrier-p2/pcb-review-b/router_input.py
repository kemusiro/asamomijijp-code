#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create router-only 3 signal layer model; native PCB remains 4-layer with GND on In1."""
from pathlib import Path
import re
p=Path(__file__).resolve().parent/'schematic'
import sys
source=p/(sys.argv[1] if len(sys.argv)>1 else 'p2-b.dsn')
tokens=iter(re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^()\s]+',source.read_text().replace('(string_quote " )', '(string_quote DOUBLE_QUOTE)').replace('(string_quote ")', '(string_quote DOUBLE_QUOTE)')))
def read(t):
 if t!='(':return t
 out=[]
 for x in tokens:
  if x==')':return out
  out.append(read(x))
 raise ValueError('Unclosed')
d=read(next(tokens))
def flat(v):return [v] if isinstance(v,str) else sum((flat(x) for x in v),[])
def clean(v):
 if isinstance(v,str):return v
 if v and v[0] in ['autoroute_settings']:return None
 if v and v[0] in ['layer','plane','shape','keepout'] and 'In1.Cu' in flat(v):return None
 return [y for x in v if (y:=clean(x)) is not None]
def dump(v,depth=0):
 if isinstance(v,str):return v
 if not any(isinstance(x,list) for x in v):return '('+' '.join(v)+')'
 return '('+' '.join(dump(x,depth+1) for x in v)+')'
(p/'p2-three-signals.dsn').write_text(dump(clean(d)).replace('(string_quote DOUBLE_QUOTE)', '(string_quote ")')+'\n')
