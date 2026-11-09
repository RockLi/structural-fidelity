#!/usr/bin/env python3
"""Arithmetic checks only: exact rational oracle, forced/natural fallback, bit adjacency."""
import ctypes as C,json,math,random,struct,sys
from pathlib import Path
import numpy as np
import run as r
r.lib.audit_operation.argtypes=[C.c_int,r.FP,r.FP,C.c_int,C.c_float,r.FP,r.FB,C.c_int]
r.lib.audit_operation.restype=C.c_int
r.lib.audit_adjacent.argtypes=[C.c_double,C.c_int];r.lib.audit_adjacent.restype=C.c_double
rng=random.Random(20261108)
def bits(x):return struct.pack('d',x)
xs=[0.,-0.,math.inf,-math.inf,math.nan,1.,-1.,math.nextafter(0.,1.),-math.nextafter(0.,1.),sys.float_info.max,-sys.float_info.max,sys.float_info.min,-sys.float_info.min]
xs += [struct.unpack('d',struct.pack('Q',rng.getrandbits(64)))[0] for _ in range(20000)]
checks=0
for x in xs:
 for up in [0,1]:
  y=r.lib.audit_adjacent(x,up);z=math.nextafter(x,math.inf if up else -math.inf)
  assert (math.isnan(y) and math.isnan(z)) or bits(y)==bits(z),(x,up,y,z)
  checks+=1
natural=[0,0,0];forced=[0,0,0];operations=0
for op in range(3):
 for i in range(240):
  v=sorted([rng.uniform(-6000,100) for _ in range(2)])
  ge=sorted([rng.uniform(0,60000) for _ in range(2)]);gi=sorted([rng.uniform(0,60000) for _ in range(2)])
  if i<8:
   val=[0.,1.,30.,-65.,2**-149,2**-126,2**-24,5500.][i]
   v=[val,val];ge=gi=[abs(val),abs(val)]
  x=np.array(v+ge+gi if op==1 else ge,dtype=np.float32)
  values=np.array([rng.uniform(0,400) for _ in range(i%21)],dtype=np.float32)
  field=np.float32(0 if i<8 else rng.uniform(0,100))
  expected=np.empty(2,dtype=np.float32);out=np.empty(2,dtype=np.float32)
  assert r.fallback(op,x.ctypes.data_as(r.FP),values.ctypes.data_as(r.FP),len(values),field,expected.ctypes.data_as(r.FP))
  for force in [0,1]:
   n=r.lib.audit_operation(op,x.ctypes.data_as(r.FP),values.ctypes.data_as(r.FP),len(values),field,out.ctypes.data_as(r.FP),r.fallback,force)
   assert n>=0 and not r.errors,r.errors
   assert np.array_equal(out.view(np.uint32),expected.view(np.uint32)),(op,i,force,out,expected)
   (forced if force else natural)[op]+=n;operations+=1
assert all(forced) and sum(natural)>0,(forced,natural)
report=dict(status='pass',adjacent_binary64_checks=checks,operation_endpoint_checks=operations,natural_fallbacks_by_accumulate_voltage_decay=natural,forced_fallbacks_by_accumulate_voltage_decay=forced,seed=20261108,new_network_simulations=0)
p=Path(sys.argv[1]) if len(sys.argv)>1 else r.ROOT/'arithmetic.json'
p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
