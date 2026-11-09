#!/usr/bin/env python3
"""Same-certificate native interval-filter benchmark against native local replay."""
import ctypes as C,sys,time,json,csv,statistics,hashlib,subprocess,platform,argparse
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'finite-horizon-certificate-audit-20261108'
sys.path.insert(0,str(OLD));import audit as a
FP=C.POINTER(C.c_float);IP=C.POINTER(C.c_int32)
class Result(C.Structure):
 _fields_=[(x,C.c_int) for x in ['certified','slot','target','reason','steps','thresholds','events','fallbacks','trace_rows']]+[('slack',C.c_double)]
FB=C.CFUNCTYPE(C.c_int,C.c_int,FP,FP,C.c_int,C.c_float,FP)
errors=[];fallback_counts=[0,0,0]
@FB
def fallback(op,x,vals,n,field,out):
 try:
  fallback_counts[op]+=1
  if op==0:z=a.accumulate((a.q(x[0]),a.q(x[1])),[np.float32(vals[j]) for j in range(n)],np.float32(field))
  elif op==1:z=a.voltage((a.q(x[0]),a.q(x[1])),(a.q(x[2]),a.q(x[3])),(a.q(x[4]),a.q(x[5])))
  elif op==2:z=a.decay((a.q(x[0]),a.q(x[1])))
  else:raise ValueError(op)
  out[0]=float(z[0]);out[1]=float(z[1]);return 1
 except BaseException as e:errors.append(repr(e));return 0
lib=C.CDLL(str(ROOT/'kernel.dylib'))
lib.run.argtypes=[C.c_int,C.c_int,C.c_int,IP,FP,IP,FP,C.POINTER(Result),FP,FB];lib.run.restype=C.c_int
lib.run_batch.argtypes=[C.c_int]+lib.run.argtypes[:-2]+[FB];lib.run_batch.restype=C.c_int
REASONS={0:'certified',1:'execution-guard',2:'threshold-inconclusive',3:'activity-inconclusive',4:'status-guard',5:'skipped-spike-guard'}
def prepare(probe,ref,cache,g,targets):
 flags=[];fields=[];offset=[0];events=[]
 for k in targets:
  vals,due,pending,_=a.inputs(g,ref[:,:,0],probe,k)
  for n in range(a.T):
   flags.append([cache[k]['execute'][n],bool(ref[n,k,0]),due[n],pending[n],ref[n,k,9]])
   fields.append([0 if n==0 else a.floats(ref[n-1,k,6]),a.floats(ref[n,k,6])])
   for q in range(2):events.extend(vals[n][q]);offset.append(len(events))
 return [np.asarray(flags,dtype=np.int32),np.asarray(fields,dtype=np.float32),np.asarray(offset,dtype=np.int32),np.asarray(events,dtype=np.float32)]
def fast_prepare(probe,ref,cache,g,targets,spike_slots):
 flags=np.empty((2*a.T,5),dtype=np.int32);fields=np.zeros((2*a.T,2),dtype=np.float32)
 offsets=[0];events=[]
 for ki,k in enumerate(targets):
  incoming=sorted(g[g[:,2]==k],key=lambda r:int(r[1]))
  vals=[[[],[]] for _ in range(a.T)];due=np.zeros(a.T+2,dtype=bool);pending=np.zeros(a.T,dtype=bool)
  for edge in incoming:
   src=int(edge[1]);slots=spike_slots[src];arrival=slots+2;due[arrival]=True
   amplitude=np.float32(edge[3].view(np.float32)*np.float32(100))
   for n in arrival[arrival<a.T]:vals[n][int(src>=100)].append(amplitude)
   pending[1:]|=ref[:-1,src,0]>0
  ext=k<100 and (probe!='focal_burst' or k%5==0)
  if ext:
   stop=a.T if probe=='tonic' else 80
   for n in range(stop):vals[n][0].append(np.float32(10 if probe=='tonic' else 150))
   due[:stop]=True
  sl=slice(ki*a.T,(ki+1)*a.T)
  flags[sl,0]=cache[k]['execute'];flags[sl,1]=ref[:,k,0]>0
  flags[sl,2]=due[:a.T];flags[sl,3]=pending;flags[sl,4]=ref[:,k,9]
  fields[ki*a.T+1:(ki+1)*a.T,0]=ref[:-1,k,6].view(np.float32)
  fields[sl,1]=ref[:,k,6].view(np.float32)
  for row in vals:
   for values in row:events.extend(values);offsets.append(len(events))
 return [flags,fields,np.asarray(offsets,dtype=np.int32),np.asarray(events,dtype=np.float32)]

def bindings(data):
 f,z,o,e=data;return [f.ctypes.data_as(IP),z.ctypes.data_as(FP),o.ctypes.data_as(IP),e.ctypes.data_as(FP)]
def invoke(mode,ptrs,trace=None,result=None):
 r=Result() if result is None else result
 lib.run(mode,2,a.T,*ptrs,C.byref(r),trace.ctypes.data_as(FP) if trace is not None else None,fallback)
 assert not errors and r.reason not in [98,99],errors
 return r

def verify(r,old,targets):
 observed=dict(certified=bool(r.certified),first_unresolved_slot=None if r.certified else r.slot,first_unresolved_chunk=None if r.certified else targets[r.target],reason=REASONS[r.reason],checked_chunk_slots=r.steps,threshold_checks=r.thresholds,visited_incoming_events=r.events,minimum_certified_slack=None if np.isinf(r.slack) else r.slack)
 assert observed=={k:old[k] for k in observed},(observed,old)
 return observed

def python_replay(data):
 flags,fields,offsets,events=data;trace=[];reason=0;steps=0
 for k in range(2):
  v=np.float32(-65);ge=gi=np.float32(0);active=False;deadline=0
  for n in range(a.T):
   row=k*a.T+n;f=flags[row];steps+=1;execute=active or f[2]
   if execute!=f[0]:return trace,1,steps
   if execute:
    b,mid,end=offsets[row*2:row*2+3]
    vp,ge,gi=a.point_step(v,ge,gi,fields[row,0],np.float32(0),[events[b:mid],events[mid:end]],deadline<=n)
    if deadline<=n:
     if bool(vp>=30)!=bool(f[1]):return trace,2,steps
     if f[1]:v=np.float32(-65);deadline=n+2
     else:v=vp
    elif f[1]:raise AssertionError('refractory reference spike')
    fixed=f[1] or f[2] or abs(fields[row,1])>np.float32(1e-6)
    hot=fixed or ge>np.float32(1e-6) or gi>np.float32(1e-6)
    status=1 if hot else 2 if f[3] else 0
    if status!=f[4]:return trace,4,steps
    active=hot or f[3]
   else:
    if f[1]:return trace,5,steps
    active=False
   trace.append([v,v,ge,ge,gi,gi])
 return trace,0,steps

def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'results');p.add_argument('--rounds',type=int,default=11);p.add_argument('--batch',type=int,default=100);args=p.parse_args();out=args.output_dir;out.mkdir(exist_ok=False)
 rows=a.csvread(a.BASE/'evidence/input-readout/analysis/input-switching.csv');orig=a.graph('original');oldset={tuple(map(int,x)) for x in orig}
 refs={};cache={};setuptimes={};spike_slots={}
 for probe in ['tonic','global_burst','focal_burst']:
  start=time.perf_counter();refs[probe]=a.state(probe);cache[probe],_=a.reference_cache(probe,refs[probe],orig);spike_slots[probe]=[np.flatnonzero(refs[probe][:,k,0]) for k in range(a.N)];setuptimes[probe]=time.perf_counter()-start
 timings=[];summary=[];endpoint_count=0;baselinechecks=0;endpoint_hash=hashlib.sha256();decision_hash=hashlib.sha256()
 for row in rows:
  probe=row['probe'];ref=refs[probe]
  gtimes=[];ptimes=[]
  # Both methods receive identical prep; disk/index work is accounted separately.
  for rep in range(3):
   start=time.perf_counter();g=a.graph('swap'+row['seed']);newset={tuple(map(int,x)) for x in g};targets=sorted({e[2] for e in oldset^newset});gtimes.append(time.perf_counter()-start)
   start=time.perf_counter();data=fast_prepare(probe,ref,cache[probe],g,targets,spike_slots[probe]);ptimes.append(time.perf_counter()-start)
  original_data=prepare(probe,ref,cache[probe],g,targets)
  assert all(np.array_equal(x.view(np.uint32),y.view(np.uint32)) for x,y in zip(data,original_data)),row['stem']
  ptrs=bindings(data)
  t=time.perf_counter();old,intervals=a.certify(probe,ref,cache[probe],g,targets);oracle_seconds=time.perf_counter()-t
  trace=np.empty((600,6),dtype=np.float32);r=invoke(0,ptrs,trace);obs=verify(r,old,targets);decision_hash.update(json.dumps(obs,sort_keys=True).encode())
  expect=np.array([[float(x) for iv in (v,ge,gi) for x in iv] for n,k,v,ge,gi in intervals],dtype=np.float32).reshape(-1,6)
  assert r.trace_rows==len(expect)
  assert np.array_equal(trace[:len(expect)].view(np.uint32),expect.view(np.uint32)),row['stem'];endpoint_count+=expect.size;endpoint_hash.update(expect.tobytes())
  # Validate actual native replay state against archived candidate ONLY AFTER certification.
  pt=np.empty((600,6),dtype=np.float32);pr=invoke(1,ptrs,pt)
  python_trace,python_reason,python_steps=python_replay(data)
  python_trace=np.asarray(python_trace,dtype=np.float32).reshape(-1,6)
  assert pr.reason==python_reason and pr.steps==python_steps and pr.trace_rows==len(python_trace)
  assert np.array_equal(pt[:pr.trace_rows].view(np.uint32),python_trace.view(np.uint32))
  actual=a.state(probe,'swap'+row['seed'])
  divergent=np.flatnonzero(np.any(actual[:,:,0]!=ref[:,:,0],axis=1))
  first_divergence=int(divergent[0]) if len(divergent) else a.T
  for index in range(pr.trace_rows):
   k=targets[index//a.T];n=index%a.T
   if n>=first_divergence:continue # after changed source spikes the archived closed loop is not reference-clamped
   assert np.array_equal(pt[index,[0,2,4]].view(np.uint32),actual[n,k,[1,2,3]]),('point',row['stem'],n,k)
   baselinechecks+=1
  # Symmetric warmup; no per-result trace allocation in timed kernels.
  cr=Result();rr=Result()
  for _ in range(3):invoke(0,ptrs,result=cr);invoke(1,ptrs,result=rr)
  ts={0:[],1:[]}
  for rep in range(args.rounds):
   for mode in ([0,1] if rep%2==0 else [1,0]):
    result=cr if mode==0 else rr;start=time.perf_counter_ns()
    lib.run_batch(args.batch,mode,2,a.T,*ptrs,C.byref(result),fallback)
    sec=(time.perf_counter_ns()-start)/1e9/args.batch;ts[mode].append(sec)
    assert not errors and result.reason not in [98,99],errors
    timings.append(dict(stem=row['stem'],round=rep,mode='certificate' if mode==0 else 'point_replay',seconds_per_call=sec,batch=args.batch))
  cert=statistics.median(ts[0]);point=statistics.median(ts[1]);prep=statistics.median(ptimes);gio=statistics.median(gtimes)
  summary.append(dict(stem=row['stem'],category=row['category'],certified=bool(r.certified),reason=REASONS[r.reason],certificate_fallbacks=r.fallbacks,certificate_steps=r.steps,replay_steps=pr.steps,replay_agrees=bool(pr.certified),graph_io_seconds=gio,shared_input_prepare_seconds=prep,old_rational_seconds=oracle_seconds,new_certificate_seconds=cert,native_replay_seconds=point,certificate_to_replay_ratio=cert/point,certificate_total_seconds=gio+prep+cert,replay_total_seconds=gio+prep+point,old_to_new_with_prepare_ratio=oracle_seconds/(prep+cert)))
  summary[-1].update(obs)
  print(row['stem'],'fallback',r.fallbacks,'native_ms',round(cert*1000,4),'replay_ms',round(point*1000,4),flush=True)
 def table(name,rs):
  with(out/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
 table('cases.csv',summary);table('timings.csv',timings)
 groups={}
 for name,rs in [('all57',summary),('target17',[r for r in summary if r['category']=='input_changed_spikes_equal']),('certified_nonzero16',[r for r in summary if r['category']=='input_changed_spikes_equal' and r['certified']])]:
  groups[name]=dict(n=len(rs),**{field:statistics.median([r[field] for r in rs]) for field in ['graph_io_seconds','shared_input_prepare_seconds','old_rational_seconds','new_certificate_seconds','native_replay_seconds','certificate_to_replay_ratio','certificate_total_seconds','replay_total_seconds','old_to_new_with_prepare_ratio']},sum_fallbacks=sum(r['certificate_fallbacks'] for r in rs))
 report=dict(status='pass',cases=57,all_original_decisions_counters_slacks_identical=True,all_prepared_input_bits_identical=True,exact_endpoint_values_compared=endpoint_count,endpoint_sha256=endpoint_hash.hexdigest(),decision_sha256=decision_hash.hexdigest(),replay_state_bit_checks_before_global_spike_divergence=baselinechecks,all_native_replay_outputs_match_python=True,groups=groups,reference_setup_seconds=setuptimes,compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],compiler_flags='-O3 -std=c11 -fno-fast-math -ffp-contract=off',python=sys.version,numpy=np.__version__,platform=platform.platform(),rounds=args.rounds,batch=args.batch,trace_outputs_excluded_equally=True,new_network_simulations=0,baseline='Native point-valued reference-driven local consistency check, same input arrays, primitive rounding, branch checks and early stop; not a full network simulator')
 a.write(out/'summary.json',report);a.write(out/'code-sha256.json',{str(f):a.sha(f) for f in [ROOT/'kernel.c',ROOT/'kernel.dylib',ROOT/'run.py',ROOT/'PROTOCOL.txt',OLD/'audit.py',OLD/'THEORY.txt']});print(json.dumps(report,indent=2))
if __name__=='__main__':main()
