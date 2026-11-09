#!/usr/bin/env python3
import ctypes as C,csv,json,time,sys,hashlib,itertools,statistics,subprocess,argparse
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'finite-horizon-certificate-cost-20261108'
sys.path.insert(0,str(OLD));import run as old
a=old.a;FP=old.FP;IP=old.IP;DP=C.POINTER(C.c_double);Result=old.Result
class R(C.Structure):_fields_=[('l',C.c_double),('h',C.c_double)]
class Aff(C.Structure):_fields_=[('c',R),('p',R*2),('err',R)]
class Agg(C.Structure):_fields_=[('input',Aff),('upper',R),('m',C.c_int)]
AP=C.POINTER(Agg)
lib=C.CDLL(str(ROOT/'kernel.dylib'))
lib.run.argtypes=old.lib.run.argtypes;lib.run.restype=C.c_int
lib.family_model.argtypes=[C.c_int,C.c_double,C.c_int,FP,IP,FP,FP,IP,AP];lib.family_model.restype=C.c_int
lib.family_run.argtypes=[C.c_int,C.c_int,C.c_int,C.c_int,IP,FP,AP,C.POINTER(Result),DP];lib.family_run.restype=C.c_int
lib.family_batch.argtypes=[C.c_int]+lib.family_run.argtypes[:-1];lib.family_batch.restype=C.c_int
lib.point_events.argtypes=[C.c_int,C.c_double,DP,C.c_int,FP,FP,IP,FP]
lib.points_batch.argtypes=[C.c_int,C.c_int,C.c_double,C.c_int,DP,C.c_int,FP,FP,IP,C.c_int,C.c_int,IP,FP,IP,FP,C.POINTER(Result),old.FB];lib.points_batch.restype=C.c_int
lib.cached_points_batch.argtypes=[C.c_int,C.c_int,C.c_int,FP,C.c_int,C.c_int,IP,FP,IP,C.POINTER(Result),old.FB];lib.cached_points_batch.restype=C.c_int
assert lib.agg_size()==C.sizeof(Agg)
RADII=[0,2**-16,2**-12,2**-8,2**-6,2**-4,.25]
def ptr(x,t=FP):return x.ctypes.data_as(t)
def prepare(probe,ref,cache,g,targets,slots):
 data=old.fast_prepare(probe,ref,cache,g,targets,slots)
 weights=[];signs=[];edgeids=[];edges=[]
 for k in targets:
  incoming=sorted(g[g[:,2]==k],key=lambda r:int(r[1]));vals=[[[],[]] for _ in range(a.T)]
  for rank,edge in enumerate(incoming):
   src=int(edge[1]);w=edge[3].view(np.float32);eid=len(edges);sgn=(1 if rank%2==0 else -1,1 if (rank//2)%2==0 else -1)
   edges.append((src,int(k),float(w),*sgn))
   for n in slots[src]+2:
    if n<a.T:vals[n][int(src>=100)].append((w,sgn,eid))
  ext=k<100 and (probe!='focal_burst' or k%5==0)
  if ext:
   for n in range(a.T if probe=='tonic' else 80):vals[n][0].append((0.,(0,0),-1))
  for row in vals:
   for ch in row:
    for w,sgn,eid in ch:weights.append(w);signs.append(sgn);edgeids.append(eid)
 weights=np.asarray(weights,dtype=np.float32);signs=np.asarray(signs,dtype=np.int32);edgeids=np.asarray(edgeids,dtype=np.int32)
 assert len(weights)==len(data[-1])
 for j,w in enumerate(weights):
  if w:assert np.float32(w*100).view(np.uint32)==data[-1][j].view(np.uint32)
 return data,weights,signs,edgeids,edges

def model(data,weights,signs,d,rho):
 ag=(Agg*(2*a.T*2))();f,z,o,e=data
 assert lib.family_model(d,rho,2*a.T,ptr(z),ptr(o,IP),ptr(e),ptr(weights),ptr(signs,IP),ag)
 return ag

def family(data,ag,d,method,trace=None):
 r=Result();lib.family_run(method,d,2,a.T,ptr(data[0],IP),ptr(data[1]),ag,C.byref(r),None if trace is None else ptr(trace,DP));assert r.reason!=98
 return r

def point_stream(data,weights,signs,d,rho,alpha):
 alpha=np.asarray(alpha,dtype=np.float64);ev=np.empty_like(data[-1]);lib.point_events(d,rho,ptr(alpha,DP),len(ev),ptr(data[-1]),ptr(weights),ptr(signs,IP),ptr(ev));return ev

def point(data,events,trace=None):
 r=Result();f,z,o,_=data
 lib.run(1,2,a.T,ptr(f,IP),ptr(z),ptr(o,IP),ptr(events),C.byref(r),None if trace is None else ptr(trace),old.fallback)
 return r

def result(r,targets):return dict(passed=bool(r.certified),reason=old.REASONS[r.reason],target=None if r.certified else targets[r.target],slot=None if r.certified else r.slot,steps=r.steps,thresholds=r.thresholds,events=r.events,slack=None if np.isinf(r.slack) else r.slack)

def table(path,rows):
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'results');p.add_argument('--rounds',type=int,default=11);p.add_argument('--batch',type=int,default=20);args=p.parse_args();out=args.output_dir;out.mkdir(exist_ok=False)
 selected=a.csvread(a.BASE/'evidence/input-readout/analysis/input-switching.csv');orig=a.graph('original');oset={tuple(map(int,e)) for e in orig};refs={};caches={};slots={};setuptimes={}
 for probe in ['tonic','global_burst','focal_burst']:
  t=time.perf_counter();refs[probe]=a.state(probe);caches[probe],_=a.reference_cache(probe,refs[probe],orig);slots[probe]=[np.flatnonzero(refs[probe][:,k,0]) for k in range(a.N)];setuptimes[probe]=time.perf_counter()-t
 rows=[];samples=[];timings=[];metadata=[];regression=[];contain=0;pointcheck=0
 for case in selected:
  probe=case['probe'];ref=refs[probe];t=time.perf_counter();g=a.graph('swap'+case['seed']);targets=sorted({e[2] for e in oset^{tuple(map(int,x)) for x in g}});gio=time.perf_counter()-t
  pt=[]
  for _ in range(3):
   t=time.perf_counter();data,weights,signs,edgeids,edges=prepare(probe,ref,caches[probe],g,targets,slots[probe]);pt.append(time.perf_counter()-t)
  metadata.append(dict(stem=case['stem'],targets=targets,edges=edges,graph_io_seconds=gio,shared_prepare_seconds=statistics.median(pt)))
  # Regression keeps old singleton algorithm and checks all endpoint bits.
  ort=np.empty((600,6),np.float32);nrt=np.empty_like(ort);orr=old.invoke(0,old.bindings(data),ort);nrr=Result()
  lib.run(0,2,a.T,*old.bindings(data),C.byref(nrr),ptr(nrt),old.fallback)
  assert bytes(orr)==bytes(nrr) and np.array_equal(ort[:orr.trace_rows].view(np.uint32),nrt[:nrr.trace_rows].view(np.uint32))
  regression.append(dict(stem=case['stem'],**result(nrr,targets),endpoint_values=orr.trace_rows*6))
  for d in [1,2]:
   alphas=np.array(list(itertools.product([-1.,-.5,0.,.5,1.],repeat=d)),np.float64);corners=np.array(list(itertools.product([-1.,1.],repeat=d)),np.float64)
   for rho in RADII:
    mt=[]
    for _ in range(3):
     t=time.perf_counter();ag=model(data,weights,signs,d,rho);mt.append(time.perf_counter()-t)
    traces=[np.empty((600,6),np.float64) for _ in range(2)];rs=[family(data,ag,d,m,traces[m]) for m in [0,1]]
    streams=[];weightset=set();eventset=set();outcomes=[];cornerpass=0
    for alpha in alphas:
     ev=point_stream(data,weights,signs,d,rho,alpha);streams.append(ev)
     # Check parameter entry with exact Fraction RN32; all sample coordinates dyadic.
     wb=[]
     for src,k,w,s1,s2 in edges:
      wv=a.rn(a.q(w)*(a.F(1)+a.F(rho)*sum(a.F(float(alpha[j]))*[s1,s2][j] for j in range(d))/d));wb.append(int(wv.view(np.uint32)))
     actualamps=np.array([np.float32(np.array(wb[int(i)],np.uint32).view(np.float32)*np.float32(100)) if i>=0 else data[-1][j] for j,i in enumerate(edgeids)],np.float32)
     assert np.array_equal(ev.view(np.uint32),actualamps.view(np.uint32))
     weightset.add(tuple(wb));eventset.add(hashlib.sha256(ev.tobytes()).hexdigest())
     tr=np.empty((600,6),np.float32);pr=point(data,ev,tr);outcomes.append(bool(pr.certified));corner=bool(np.all(np.abs(alpha)==1));cornerpass+=int(corner and pr.certified)
     # Independent replay on all centre/corners; other samples compared inside proven enclosures.
     if corner or np.all(alpha==0):
      py,reason,steps=old.python_replay([*data[:3],ev]);py=np.asarray(py,np.float32).reshape(-1,6)
      assert pr.reason==reason and pr.steps==steps and pr.trace_rows==len(py) and np.array_equal(tr[:len(py)].view(np.uint32),py.view(np.uint32));pointcheck+=1
     for method,r in enumerate(rs):
      if r.certified:
       assert pr.certified,(case['stem'],d,rho,alpha,method)
       vals=tr[:600,[0,2,4]].astype(np.float64);lo=traces[method][:,::2];hi=traces[method][:,1::2]
       assert np.all(lo<=vals) and np.all(vals<=hi),(case['stem'],d,rho,alpha,'containment')
       contain+=vals.size
     samples.append(dict(stem=case['stem'],d=d,rho=rho,alpha=json.dumps(alpha.tolist()),corner=corner,**result(pr,targets)))
    streams=np.ascontiguousarray(streams);J=len(weights);scratch=np.empty(J,np.float32);rp=(Result*len(alphas))();rc=(Result*len(corners))();rr=[Result(),Result()]
    # Symmetric preallocated native batches; generation included for point compute variants.
    f,z,o,e=data;pf,pz,po=ptr(f,IP),ptr(z),ptr(o,IP)
    def timed_call(which,reps):
     if which<2:return lib.family_batch(reps,which,d,2,a.T,pf,pz,ag,C.byref(rr[which]))
     if which==4:return lib.cached_points_batch(reps,len(alphas),J,ptr(streams),2,a.T,pf,pz,po,rp,old.fallback)
     al= corners if which==2 else alphas;res=rc if which==2 else rp
     return lib.points_batch(reps,d,rho,len(al),ptr(al,DP),J,ptr(e),ptr(weights),ptr(signs,IP),2,a.T,pf,pz,po,ptr(scratch),res,old.fallback)
    for _ in range(2):
     for m in range(5):timed_call(m,1)
    ts={m:[] for m in range(5)}
    for roundid in range(args.rounds):
     for m in (range(5) if roundid%2==0 else reversed(range(5))):
      t=time.perf_counter_ns();timed_call(m,args.batch);sec=(time.perf_counter_ns()-t)/1e9/args.batch;ts[m].append(sec)
      timings.append(dict(stem=case['stem'],d=d,rho=rho,round=roundid,method=m,seconds=sec))
    for m,r in enumerate(rs):
     rows.append(dict(stem=case['stem'],category=case['category'],d=d,rho=rho,method=['affine_support','certified_corner_envelope'][m],**result(r,targets),grid_passes=sum(outcomes),grid_n=len(alphas),corner_passes=cornerpass,corner_n=len(corners),distinct_weight_configs=len(weightset),distinct_event_streams=len(eventset),kernel_seconds=statistics.median(ts[m]),model_prepare_seconds=statistics.median(mt),shared_prepare_seconds=statistics.median(pt),graph_io_seconds=gio,corner_replay_seconds=statistics.median(ts[2]),grid_replay_generation_seconds=statistics.median(ts[3]),grid_cached_replay_seconds=statistics.median(ts[4])))
  print(case['stem'],'done',flush=True)
 table(out/'coverage.csv',rows);table(out/'samples.csv',samples);table(out/'timings.csv',timings);table(out/'singleton-regression.csv',regression)
 a.write(out/'families.json',metadata)
 assert not old.errors,old.errors
 summary=dict(status='pass',cases=len(selected),dimensions=[1,2],radii=RADII,certifier_evaluations=len(rows),sample_checks=len(samples),sample_state_values_enclosed=contain,independent_python_point_replays=pointcheck,singleton_interval_values=sum(x['endpoint_values'] for x in regression),reference_setup_seconds=setuptimes,methods={0:'affine_support',1:'certified_corner_envelope',2:'corner_point_replay_with_generation',3:'grid_point_replay_with_generation',4:'grid_point_replay_cached'},compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],flags='-O3 -std=c11 -fno-fast-math -ffp-contract=off',rounds=args.rounds,batch=args.batch,new_full_network_runs=0,new_network_seeds=0,new_input_protocols=0)
 a.write(out/'summary.json',summary);a.write(out/'code-sha256.json',{str(p):a.sha(p) for p in [ROOT/'kernel.c',ROOT/'kernel.dylib',ROOT/'prototype.py',ROOT/'PROTOCOL.txt',ROOT/'oracle.py',OLD/'run.py',a.ROOT/'audit.py']})
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
