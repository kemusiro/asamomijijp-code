# SPDX-License-Identifier: MIT
"""Small quoted-token S-expression reader/writer for plot-only KiCad copies."""
import re

def loads(s):
 tokens=iter(re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^()\s]+',s))
 def read(t):
  if t!='(':return t
  out=[]
  for x in tokens:
   if x==')':return out
   out.append(read(x))
  raise ValueError('Unclosed S-expression')
 return read(next(tokens))

def dumps(v):
 if isinstance(v,str):return v
 return '('+' '.join(dumps(x) for x in v)+')'
