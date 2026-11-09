#!/usr/bin/env python3
"""Reference-only, exact-rational interval certificate for archived single swaps."""
from pathlib import Path
from fractions import Fraction as F
import csv,json,hashlib,time,sys,platform
import numpy as np
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review'
E=BASE/'evidence/sensitivity';T=300;N=125
u=F(1,2**24);tiny=F(1,2**149)
def q(x):return F(float(np.float32(x)))
h=q(.1);d=q(np.float32(1)-np.float32(.1));theta=F(30);epsilon=q(1e-6)
def csvread(p):return list(csv.DictReader(p.open()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def state(probe,stem='original'):
 return np.load(E/'runs'/f'{stem}__{probe}.npz')['state_bits']
def graph(stem):
 a=np.array([[int(r[k]) for k in ['arm','source','target','weight_bits','delay']] for r in csvread(E/'graphs'/f'{stem}.csv')],dtype=np.uint32)
 assert np.all(a[:,4]==1) and len({(int(r[1]),int(r[2])) for r in a})==len(a)
 return a
# Exact binary32 rounding; binary64 approximation merely seeds a bracket.
def floor32(x):
 y=np.float32(float(x));assert np.isfinite(y)
 while q(y)>x:y=np.nextafter(y,np.float32(-np.inf))
 while q(np.nextafter(y,np.float32(np.inf)))<=x:y=np.nextafter(y,np.float32(np.inf))
 return y
def ceil32(x):
 y=floor32(x)
 return y if q(y)==x else np.nextafter(y,np.float32(np.inf))
def rn(x):
 a=floor32(x);b=ceil32(x);da=x-q(a);db=q(b)-x
 return a if da<db or (da==db and int(a.view(np.uint32))%2==0) else b
def grid(x):return (q(floor32(x[0])),q(ceil32(x[1])))
def maximum(x):return max(abs(x[0]),abs(x[1]))
def plus(x,y):return(x[0]+y[0],x[1]+y[1])
def scale(x,a):return(x[0]*a,x[1]*a) if a>=0 else(x[1]*a,x[0]*a)
def pad(x,r):return(x[0]-r,x[1]+r)
def accumulate(x,values,field):
 # Include local-field injection as the last rounded addition. All summands positive.
 terms=[q(v) for v in values]+[q(rn(q(field)*q(.01)))]
 s=sum(terms,F(0));m=len(terms);gamma=m*u/(1-m*u)
 rho=gamma*(maximum(x)+sum(map(abs,terms)))+m*tiny/(1-m*u)
 z=grid(pad((x[0]+s,x[1]+s),rho))
 return(max(F(0),z[0]),max(F(0),z[1]))
def voltage(v,ge,gi):
 # Affine rewrite retains contraction; rho covers the original 4 rounded operations.
 syn=(ge[0]-gi[1],ge[1]-gi[0]);e1=u*maximum(syn)+tiny
 syn_r=pad(syn,e1);z=plus(scale(v,-1),syn_r);e2=u*maximum(z)+tiny
 zr=pad(z,e2);prod=scale(zr,h);e3=u*maximum(prod)+tiny
 end=plus(v,pad(prod,e3));e4=u*maximum(end)+tiny
 center=plus(scale(v,1-h),scale(syn,h));return grid(pad(center,h*(e1+e2)+e3+e4))
def decay(x):return grid(pad(scale(x,d),u*d*maximum(x)+tiny))
def inputs(g,spikes,probe,k):
 incoming=sorted([r for r in g if r[2]==k],key=lambda r:int(r[1]))
 vals=[[[],[]] for _ in range(T)];event=np.zeros(T+2,dtype=int)
 for row in incoming:
  src=int(row[1]);w=np.array(row[3],dtype=np.uint32).view(np.float32);channel=int(src>=100)
  for n in np.flatnonzero(spikes[:,src]):
   assert spikes[n,src]==100
   amp=rn(q(w)*F(100));event[n+2]+=1
   if n+2<T:vals[n+2][channel].append(amp)
 for n in range(T):
  ext=(probe=='tonic' and k<100) or(probe=='global_burst' and n<80 and k<100) or(probe=='focal_burst' and n<80 and k<100 and k%5==0)
  if ext:vals[n][0].append(np.float32(10 if probe=='tonic' else 150));event[n]+=1
 # Future after draining n is recurrent emission n-1; external events are never future.
 future=np.zeros(T,dtype=bool)
 for row in incoming:
  src=int(row[1]);future[1:]|=spikes[:-1,src]>0
 return vals,event[:T]>0,future,len(incoming)
def floats(a):return a.view(np.float32)
def point_step(v,ge,gi,fe,fi,values,eligible):
 for x in values[0]:ge=np.float32(ge+x)
 for x in values[1]:gi=np.float32(gi+x)
 ge=np.float32(ge+np.float32(fe*np.float32(.01)));gi=np.float32(gi+np.float32(fi*np.float32(.01)))
 pre=v
 if eligible:
  syn=np.float32(ge-gi);pre=np.float32(v+np.float32(np.float32(-v+syn)*np.float32(.1)))
  ge=np.float32(ge*np.float32(d));gi=np.float32(gi*np.float32(d))
 return pre,ge,gi

def reference_cache(probe,a,g):
 sp=a[:,:,0];v=a[:,:,1].copy().view(np.float32);ge=a[:,:,2].copy().view(np.float32);gi=a[:,:,3].copy().view(np.float32)
 assert np.all(np.isin(sp,[0,100]));assert np.all(a[:,:,4:6]==0) and np.all(a[:,:,7]==0)
 cache={};checked=0
 for k in range(N):
  vals,due,pending,indeg=inputs(g,sp,probe,k);execute=[];pre=[];margins=[];active=False;deadline=0
  pv=np.float32(-65);pg=np.float32(0);pi=np.float32(0)
  for n in range(T):
   do=active or due[n];execute.append(do)
   fe=np.float32(0) if n==0 else floats(a[n-1,k,6]);fi=np.float32(0)
   eligible=deadline<=n
   if do:
    vp,pg,pi=point_step(pv,pg,pi,fe,fi,vals[n],eligible)
    fired=eligible and vp>=30;pv=np.float32(-65) if fired else vp
    if fired:deadline=n+2
    # Stored reference field is trusted input to certificate (same under equal branch/spike history).
    hot=bool(fired or due[n] or abs(floats(a[n,k,6]))>np.float32(epsilon) or pg>np.float32(epsilon) or pi>np.float32(epsilon))
    status=1 if hot else 2 if pending[n] else 0;active=hot or pending[n]
   else:vp=pv;fired=False;status=0;active=False
   assert (int(fired)*100,int(pv.view(np.uint32)),int(pg.view(np.uint32)),int(pi.view(np.uint32)),deadline,status)==tuple(int(a[n,k,j]) for j in [0,1,2,3,8,9]),(probe,n,k,'reference-reconstruction')
   pre.append(vp);margins.append(float(abs(q(vp)-theta)) if do and eligible else None);checked+=1
  cache[k]=dict(values=vals,due=due,pending=pending,execute=execute,pre=pre,margin=margins,indeg=indeg)
 counts=csvread(E/'runs'/f'original__{probe}.csv')
 assert [sum(cache[k]['execute'][n] for k in range(N)) for n in range(T)]==[int(r['active_chunks']) for r in counts]
 return cache,checked

def certify(probe,a,cache,g,targets):
 start=time.perf_counter();work=0;events=0;checks=0;smallest=None;intervals=[];failure=None
 for k in targets:
  vals,due,pending,indeg=inputs(g,a[:,:,0],probe,k)
  v=(F(-65),F(-65));ge=(F(0),F(0));gi=ge;active=False;deadline=0
  for n in range(T):
   work+=1;do=active or due[n]
   if do!=cache[k]['execute'][n]:failure=(n,k,'execution-guard');break
   refsp=bool(a[n,k,0]);eligible=deadline<=n
   if do:
    fe=np.float32(0) if n==0 else floats(a[n-1,k,6]);events+=len(vals[n][0])+len(vals[n][1])
    ge=accumulate(ge,vals[n][0],fe);gi=accumulate(gi,vals[n][1],np.float32(0))
    if eligible:
     vp=voltage(v,ge,gi);checks+=1
     slack=vp[0]-theta if refsp else theta-vp[1]
     if (refsp and slack<0) or(not refsp and slack<=0):failure=(n,k,'threshold-inconclusive');break
     smallest=float(slack) if smallest is None else min(smallest,float(slack))
     v=(F(-65),F(-65)) if refsp else vp;ge=decay(ge);gi=decay(gi)
     if refsp:deadline=n+2
    else:
     assert not refsp
    fe_post=q(floats(a[n,k,6]))
    fixed_hot=refsp or due[n] or abs(fe_post)>epsilon
    hotlo=fixed_hot or ge[0]>epsilon or gi[0]>epsilon
    hothi=fixed_hot or ge[1]>epsilon or gi[1]>epsilon
    if hotlo!=hothi:failure=(n,k,'activity-inconclusive');break
    status=1 if hotlo else 2 if pending[n] else 0
    if status!=int(a[n,k,9]):failure=(n,k,'status-guard');break
    active=hotlo or pending[n]
   else:
    if refsp:failure=(n,k,'skipped-spike-guard');break
    active=False
   intervals.append((n,k,v,ge,gi))
  if failure:break
 return dict(certified=failure is None,first_unresolved_slot=None if failure is None else failure[0],first_unresolved_chunk=None if failure is None else failure[1],reason='certified' if failure is None else failure[2],checked_chunk_slots=work,threshold_checks=checks,visited_incoming_events=events,minimum_certified_slack=smallest,certificate_seconds=time.perf_counter()-start),intervals

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT/'results');args=parser.parse_args()
 out=args.output_dir;out.mkdir(exist_ok=False)
 sources=[BASE/'paper_en.py',ROOT/'protocol.json',ROOT/'audit.py',BASE/'evidence/input-readout/analysis/input-switching.csv']
 sources+=list((E/'source/src').rglob('*.rs'))+list((E/'graphs').glob('*.csv'))
 selected=csvread(BASE/'evidence/input-readout/analysis/input-switching.csv');assert len(selected)==57
 orig=graph('original');refs={};caches={};setup={};results=[];enclosure_checks=0
 for probe in ['tonic','global_burst','focal_burst']:
  start=time.perf_counter();refs[probe]=state(probe);caches[probe],checked=reference_cache(probe,refs[probe],orig)
  setup[probe]=dict(seconds=time.perf_counter()-start,reconstructed_chunk_slots=checked)
  sources += [E/'runs'/f'original__{probe}.{ext}' for ext in ['npz','csv','json']]
 for row in selected:
  probe=row['probe'];g=graph('swap'+row['seed'])
  old={tuple(int(x) for x in e) for e in orig};new={tuple(int(x) for x in e) for e in g}
  removed=old-new;added=new-old;targets=sorted({r[2] for r in removed|added});assert len(removed)==len(added)==2 and len(targets)==2
  r,intervals=certify(probe,refs[probe],caches[probe],g,targets)
  # Candidate payload is NEVER used by certify. Open only now for checking an existing outcome.
  actual=state(probe,'swap'+row['seed']);sources.append(E/'runs'/f"swap{row['seed']}__{probe}.npz")
  identical=bool(np.array_equal(actual[:,:,0],refs[probe][:,:,0]));assert identical==(row['spikes_identical']=='True')
  if r['certified']:
   assert identical and np.array_equal(actual[:,:,9],refs[probe][:,:,9])
   for n,k,v,ge,gi in intervals:
    for j,interval in zip([1,2,3],[v,ge,gi]):assert interval[0]<=q(floats(actual[n,k,j]))<=interval[1],(row['stem'],n,k,j,'enclosure')
    enclosure_checks+=1
   untouched=[k for k in range(N) if k not in targets];assert np.array_equal(actual[:,untouched,:],refs[probe][:,untouched,:])
  results.append(dict(seed=int(row['seed']),probe=probe,category=row['category'],targets=str(targets),actual_spikes_identical=identical,**r))
  print(row['stem'],r['certified'],r['reason'],r['first_unresolved_slot'],flush=True)
 with (out/'cases.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 groups={c:dict(total=sum(r['category']==c for r in results),certified=sum(r['category']==c and r['certified'] for r in results)) for c in sorted({r['category'] for r in results})}
 report=dict(status='pass',new_network_simulations=0,groups=groups,false_certificates=sum(r['certified'] and not r['actual_spikes_identical'] for r in results),reference_setup=setup,certified_state_enclosure_checks=enclosure_checks,certificate_seconds_total=sum(r['certificate_seconds'] for r in results),python=sys.version,numpy=np.__version__,platform=platform.platform(),scope='Archived-data feasibility only; mathematical guarantee conditional on interval proof and frozen IEEE/source execution contract; no transfer or full-runtime speedup claim')
 write(out/'summary.json',report);write(out/'input-sha256.json',{str(p.relative_to(BASE)) if p.is_relative_to(BASE) else str(p):sha(p) for p in sources})
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
