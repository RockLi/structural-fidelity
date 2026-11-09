#!/usr/bin/env python3
"""Independent exact-rational affine enclosure. Validation, not timed baseline."""
from fractions import Fraction as F
import hashlib,json,time,argparse
from pathlib import Path
import numpy as np
import prototype as p
a=p.a
U=F(1,2**24);TINY=F(1,2**149);H=F(float(np.float32(.1)));D=F(float(np.float32(1)-np.float32(.1)))
def const(c):return (F(c),(F(0),F(0)),F(0))
def plus(x,y):return(x[0]+y[0],tuple(s+t for s,t in zip(x[1],y[1])),x[2]+y[2])
def neg(x):return(-x[0],tuple(-v for v in x[1]),x[2])
def scale(x,c):return(x[0]*c,tuple(v*c for v in x[1]),x[2]*c)
def noise(x,r):return(x[0],x[1],x[2]+r)
def bounds(x):
 rad=sum(map(abs,x[1]))+x[2];return(x[0]-rad,x[0]+rad)
def mag(x):return max(abs(x[0]),abs(x[1]))
def addi(x,y):return(x[0]+y[0],x[1]+y[1])
def subi(x,y):return(x[0]-y[1],x[1]-y[0])
def inflate(x,r):return(x[0]-r,x[1]+r)
def multi(x,c):return(x[0]*c,x[1]*c)
def models(data,weights,signs,d,rho):
 _,fields,offset,base=data;rho=F(rho);out=[]
 for row in range(600):
  for ch in range(2):
   b,end=offset[row*2+ch:row*2+ch+2];val=const(0);upper=F(0)
   for k in range(b,end):
    w=F(float(weights[k]));z=const(float(base[k]));hi=F(float(base[k]))
    if w:
     c=w*100;coeff=tuple(c*rho*int(signs[k,j])/d if j<d else F(0) for j in range(2));wm=w*(1+rho);we=U*wm+TINY;eta=100*we+U*100*(wm+we)+TINY
     z=(c,coeff,eta);hi=100*wm+eta
    val=plus(val,z);upper+=hi
   inj=F(float(np.float32(fields[row,0]*np.float32(.01)))) if ch==0 else F(0)
   out.append((plus(val,const(inj)),upper+inj,int(end-b+1)))
 return out

def accumulate(x,model):
 y,upper,m=model;gam=m*U/(1-m*U);r=gam*(mag(bounds(x))+upper)+m*TINY/(1-m*U)
 return noise(plus(x,y),r)
def voltage(v,ge,gi):
 vr=bounds(v);syn=subi(bounds(ge),bounds(gi));e1=U*mag(syn)+TINY
 z=subi(inflate(syn,e1),vr);e2=U*mag(z)+TINY
 prod=multi(inflate(z,e2),H);e3=U*mag(prod)+TINY
 end=addi(vr,inflate(prod,e3));e4=U*mag(end)+TINY
 return noise(plus(scale(v,1-H),scale(plus(ge,neg(gi)),H)),H*(e1+e2)+e3+e4)
def decay(g):return noise(scale(g,D),U*D*mag(bounds(g))+TINY)

def check(data,weights,signs,d,rho,native_trace):
 ms=models(data,weights,signs,d,rho);flags,fields,_,_=data;idx=0;eps=F(float(np.float32(1e-6)))
 for k in range(2):
  v=const(-65);ge=gi=const(0);active=False;deadline=0
  for n in range(300):
   row=k*300+n;f=flags[row];execute=active or f[2]
   if execute!=f[0]:return idx,1
   if execute:
    ge=accumulate(ge,ms[row*2]);gi=accumulate(gi,ms[row*2+1])
    if deadline<=n:
     vp=voltage(v,ge,gi);lo,hi=bounds(vp)
     if (f[1] and lo<30) or (not f[1] and hi>=30):return idx,2
     v=const(-65) if f[1] else vp
     if f[1]:deadline=n+2
     ge=decay(ge);gi=decay(gi)
    elif f[1]:raise AssertionError('refractory')
    el,eh=bounds(ge);il,ih=bounds(gi);fixed=f[1] or f[2] or abs(F(float(fields[row,1])))>eps
    low=fixed or el>eps or il>eps;high=fixed or eh>eps or ih>eps
    if low!=high:return idx,3
    status=1 if low else 2 if f[3] else 0
    if status!=f[4]:return idx,4
    active=low or f[3]
   else:
    if f[1]:return idx,5
    active=False
   if idx<len(native_trace):
    for j,x in enumerate([v,ge,gi]):
     lo,hi=bounds(x)
     assert F(float(native_trace[idx,2*j]))<=lo and F(float(native_trace[idx,2*j+1]))>=hi,(k,n,j,'native must enclose exact rational range')
   idx+=1
 return idx,0

def main():
 q=argparse.ArgumentParser();q.add_argument('--coverage',type=Path,required=True);q.add_argument('--output',type=Path,default=p.ROOT/'oracle-validation.json');args=q.parse_args()
 rows=a.csvread(args.coverage);chosen={}
 for row in rows:
  if row['method']!='affine_support':continue
  key=(row['stem'],int(row['d']));rho=float(row['rho'])
  if row['passed']=='True' and (key not in chosen or rho>float(chosen[key]['rho'])):chosen[key]=row
 extra=[r for r in rows if r['method']=='affine_support' and r['stem'].split('__')[0] in ['swap93001','swap93010','swap93019'] and float(r['rho']) in [0,2**-16,.25]]
 chosen_rows={(r['stem'],r['d'],r['rho']):r for r in list(chosen.values())+extra}
 orig=a.graph('original');oset={tuple(map(int,e)) for e in orig};refs={};cache={};slots={}
 for probe in ['tonic','global_burst','focal_burst']:
  refs[probe]=a.state(probe);cache[probe],_=a.reference_cache(probe,refs[probe],orig);slots[probe]=[np.flatnonzero(refs[probe][:,k,0]) for k in range(a.N)]
 checks=[]
 for row in chosen_rows.values():
  stem=row['stem'];gname,probe=stem.split('__');g=a.graph(gname);targets=sorted({e[2] for e in oset^{tuple(map(int,x)) for x in g}})
  data,w,s,_,_=p.prepare(probe,refs[probe],cache[probe],g,targets,slots[probe]);d=int(row['d']);rho=float(row['rho']);ag=p.model(data,w,s,d,rho);tr=np.empty((600,6),np.float64);nr=p.family(data,ag,d,0,tr)
  t=time.perf_counter();count,reason=check(data,w,s,d,rho,tr[:nr.trace_rows]);elapsed=time.perf_counter()-t
  assert nr.reason==reason and nr.trace_rows==count,(stem,d,rho,nr.reason,reason,nr.trace_rows,count)
  checks.append(dict(stem=stem,d=d,rho=rho,exact_rational_reason=reason,enclosed_endpoint_values=count*6,seconds=elapsed));print(stem,d,rho,count,round(elapsed,3),flush=True)
 a.write(args.output,dict(status='pass',checks=checks,total_endpoint_values=sum(r['enclosed_endpoint_values'] for r in checks),scope='exact rational real coefficients and rounding radii; every native saved bound encloses the oracle bound; representative grid conditions plus every largest passing region'))
if __name__=='__main__':main()
