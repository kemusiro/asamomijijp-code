# SPDX-License-Identifier: MIT
# Tick-level subset of the actual FM receiver PIO;all times are PIO ticks.
import re

def assemble(text):
 code=[];labels={}
 for line in text.splitlines():
  line=line.split(';')[0].strip()
  if not line or line.startswith('.'):continue
  if line.endswith(':'):labels[line[:-1]]=len(code);continue
  delay=re.search(r'\[(\d+)\]',line)
  code.append((re.sub(r'\s*\[\d+\]','',line),int(delay.group(1)) if delay else 0))
 return code,labels

def receive(text,clock,data,sh,max_ticks=2400):
 code,labels=assemble(text);pc=0;tick=0;x=0;isr=0;bits=0;frames=[];sample_ticks=[]
 while tick<max_ticks and len(frames)<2:
  ins,delay=code[pc];nextpc=(pc+1)%len(code)
  if ins.startswith('wait'):
   _,level,_,pin=ins.split();level=int(level);pin=int(pin)
   value=sh(tick) if pin==18 else clock(tick)
   if value!=level:tick+=1;continue
  elif ins=='set x, 23':x=23
  elif ins.startswith('jmp pin'):
   if clock(tick):nextpc=labels[ins.replace(',','').split()[-1]]
  elif ins.startswith('jmp x--'):
   if x:nextpc=labels[ins.split()[-1]]
   x=(x-1)&0xffffffff
  elif ins.startswith('jmp '):nextpc=labels[ins[4:]]
  elif ins=='irq 0':pass
  elif ins=='in pins, 1':
   isr=(isr>>1)|(data(tick)<<31);bits+=1;sample_ticks.append(tick)
   if bits==24:frames.append(isr);bits=0;isr=0
  else:raise ValueError(ins)
  pc=nextpc;tick+=1+delay
 return frames,sample_ticks

def fixture(words,glitches=(),skew=0,phase=0):
 # Two or more24-clock frames,SH falls12 ticks before first rising CLK.
 base=40+phase;period=24;size=576
 def clk(t):
  for a,b,value in glitches:
   if a<=t<b:return value
  return int((t-base)%period<12)
 def sd(t):
  pos=(t-base-skew)//period
  if pos<0:return 0
  frame,bit=divmod(pos,24)
  return (words[min(frame,len(words)-1)]>>bit)&1
 def sh(t):
  rel=(t-(base-12))%size
  return int(rel>=size-6)
 return clk,sd,sh
