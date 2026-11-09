#!/usr/bin/env python3
"""Frozen-kernel local graph and initial-condition sensitivity calibration."""
from pathlib import Path
import argparse,collections,csv,datetime,hashlib,json,platform,random,subprocess,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parent
PROBES=['tonic','global_burst','focal_burst']
SWAP_SEEDS=list(range(93001,93020)); INITIAL_SEEDS=list(range(94001,94020))
ARMS=[0]*5+[1]*5+[2]*5+[3]*4
DOSES=[('e1e-4',1e-4),('e1e-3',1e-3),('e1e-2',1e-2)]
COMPILER=['rustup','run','1.98.1','rustc']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def table(p,rows):
 with Path(p).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def edges(p):return np.loadtxt(p,delimiter=',',skiprows=1,dtype=np.int64)
def write_edges(p,e):
 with Path(p).open('w') as f:
  w=csv.writer(f,lineterminator='\n');w.writerow(['arm','source','target','weight_bits','delay']);w.writerows(e)
def command(label,args):
 started=time.monotonic();log=ROOT/'logs'/f'{label}.log'
 with log.open('w') as f:
  f.write(json.dumps(list(map(str,args)))+'\n');f.flush();result=subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 record=dict(label=label,command=list(map(str,args)),returncode=result.returncode,elapsed_seconds=time.monotonic()-started,log=str(log.relative_to(ROOT)))
 with (ROOT/'commands.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
 assert result.returncode==0,str(log)
def audit_graph(original,e,changed):
 assert e.shape==original.shape and np.array_equal(e[:,[0,1,3,4]],original[:,[0,1,3,4]])
 assert np.all(e[:,1]!=e[:,2]) and np.all(e[:,4]==1)
 pairs=set(map(tuple,e[:,1:3]));old=set(map(tuple,original[:,1:3]));assert len(pairs)==len(e)
 assert np.all((e[:,1]>=100)*2+(e[:,2]>=100)==e[:,0])
 assert len(old-pairs)==len(pairs-old)==changed
 for arm in range(4):
  for col in (1,2):
   # Per-node per-arm weight multisets imply degrees and strengths, too.
   a=collections.Counter((int(row[col]),int(row[3])) for row in original if row[0]==arm)
   b=collections.Counter((int(row[col]),int(row[3])) for row in e if row[0]==arm)
   assert a==b
 return dict(edge_count=len(e),changed_edges=changed,symmetric_difference_edges=2*changed,changed_fraction=changed/len(e),source_rows_weights_delays_exact=True,per_node_per_arm_in_out_degree_strength_weight_multisets_exact=True,no_loops_or_parallel_pairs=True)
def one_swap(original,arm,seed):
 rng=random.Random(seed);ix=np.flatnonzero(original[:,0]==arm).tolist();present=set(map(tuple,original[:,1:3]))
 for attempt in range(1,200001):
  i,j=rng.sample(ix,2);a,b=map(int,original[i,1:3]);c,d=map(int,original[j,1:3])
  if a==c or b==d or a==d or c==b or (a,d) in present or (c,b) in present:continue
  if not np.array_equal(original[i,3:5],original[j,3:5]):continue
  e=original.copy();e[i,2],e[j,2]=d,b
  return e,dict(seed=seed,arm=arm,rows=[i,j],a=a,b=b,c=c,d=d,weight_bits=int(e[i,3]),proposals_until_legal=attempt)
 raise AssertionError('No legal swap within fixed proposal cap; do not select a replacement seed')
def write_initial(p,values):
 bits=np.ascontiguousarray(values,dtype=np.float32).view(np.uint32)
 table(p,[dict(chunk=i,voltage_bits=int(v)) for i,v in enumerate(bits)])
 return bits
def prepare():
 assert not (ROOT/'experiment-lock.json').exists()
 for n in ['graphs','initial','runs','technical','build','logs','analysis']:(ROOT/n).mkdir(exist_ok=True)
 inherited=load(ROOT/'inherited-inputs-sha256.json');assert all(sha(ROOT/k)==v for k,v in inherited.items())
 original=edges(ROOT/'legacy/graphs/original.csv');assert original.shape==(2845,5)
 write_edges(ROOT/'graphs/original.csv',original)
 graphs=[dict(type='original',graph='original',**audit_graph(original,original,0))]
 for seed,arm in zip(SWAP_SEEDS,ARMS):
  e,details=one_swap(original,arm,seed);name=f'swap{seed}';write_edges(ROOT/'graphs'/f'{name}.csv',e)
  graphs.append(dict(type='swap',graph=name,**details,**audit_graph(original,e,2),graph_sha256=sha(ROOT/'graphs'/f'{name}.csv')))
  if seed==SWAP_SEEDS[0]:
   i,j=details['rows'];inverse=e.copy();inverse[i,2],inverse[j,2]=inverse[j,2],inverse[i,2];assert np.array_equal(inverse,original)
   write_edges(ROOT/'graphs/inverse-sham.csv',inverse)
 save(ROOT/'graph-audit.json',graphs)
 write_initial(ROOT/'initial/zero.csv',np.full(125,-65,dtype=np.float32));initial=[]
 for seed in INITIAL_SEEDS:
  rng=random.Random(seed);exc=[-1]*50+[1]*50;inh=[-1]*12+[1]*12+[0];rng.shuffle(exc);rng.shuffle(inh);signs=np.array(exc+inh)
  for label,epsilon in DOSES:
   name=f'jitter{seed}__{label}';v=np.asarray(-65.0+epsilon*signs,dtype=np.float32);bits=write_initial(ROOT/'initial'/f'{name}.csv',v);delta=v.astype(float)+65
   assert np.count_nonzero(delta)==124 and delta[:100].sum()==0 and delta[100:].sum()==0
   actual=float(np.abs(delta).max());ulp=abs(float(np.spacing(np.float32(-65))))
   initial.append(dict(name=name,seed=seed,epsilon=epsilon,dose_label=label,actual_linf=actual,ulp_steps=actual/ulp,nonzero_chunks=124,E_mean_delta=0,I_mean_delta=0,signs=signs.tolist(),initial_sha256=sha(ROOT/'initial'/f'{name}.csv')))
 save(ROOT/'initial-audit.json',initial)
 protocol=dict(title='Minimal legal rewiring and initial-voltage sensitivity calibration',written_utc=now(),status='Prospectively fixed exploratory follow-up to inspected preprint results; not independent preregistration',family='homogeneous only; one original E/I block-random graph',scope='Calibrate existing identified-chunk trajectory differences, not infer optimal topology or chaos',chunks=125,units_per_chunk=100,dt_ms=.1,steps=300,probes=PROBES,kernel='Unchanged frozen canonical-routing library, including dormant/refractory semantics',
  swap=dict(seeds=SWAP_SEEDS,arms=ARMS,allocation='EE/EI/IE/II:5/5/5/4; report all, no output-based selection',operation='one legal same-arm, same-weight-bit, same-delay target swap from original; preserve source/row/weight/delay',source_activity_check='Shared-original-source input discrepancy, only slots0:298 arriving by slot299 via n+2; zero drive is reported separately',sampling='Independent seeded first legal proposal within each preassigned arm; this is a local intervention, not a fully randomized null graph'),
  initial_voltage=dict(seeds=INITIAL_SEEDS,doses=[x[1] for x in DOSES],direction='Independent seeded balanced signs:100E=50minus/50plus,25I=12minus/12plus/1zero; same direction across doses',units='Uncalibrated model coordinate, not mV; record actual f32 magnitudes/ULPs',placement='Before scheduler registration, all100 units in chunk share V; all other states unchanged',activation='No added wake-up. Initial blocks remain Dormant; first executed voltage must equal supplied initial bits',interpretation='Local starting-state calibration; contraction and common resets may erase differences; not online pulse robustness or Lyapunov test'),
  scientific_runs=dict(original=3,single_swap=57,initial_jitter=171,total=231),technical_sham_runs=6,
  archived_comparison='57 explicit extensive-rewiring runs from19 controls x3 probes, plus3 original reference trajectories; reanalysed, not counted as new',
  primary_metrics=['same1ms-bin normalized identified-chunk and population spike L1 as archived study','per-graph population/chunk ratio and1minusratio; undefined when chunk error zero','all19 values, median, range, zero counts per probe/control/dose'],
  diagnostics=['raw slot chunk mismatch and first spike divergence','fixed-original-channel standardized V/gE/gI RMS in0:80,80:150,150:300 and0:300','shared-source swap input mismatch and whether its difference can arrive within horizon','initial perturbation actual first-execution bits and first common reset/state recoincidence'],
  statistics='Conditional descriptive calibration. No p-values, confidence intervals, pooled independent-amplitude counts, treatment optimisation, or threshold chosen after outcomes',
  gates=['All201 inherited files identical','initialization-only audit before any stepping','3 new originals exact legacy states/counts','3zero and3inverse-swap shams exact','all231 count/state files consistent and finite','new analysis then clean-directory independent rerun'],
  exclusions='No new original networks, no heterogenous-unit kernel, no runtime benchmark, no proxy changes; no dose escalation after observing zero effects')
 save(ROOT/'protocol.json',protocol)
 command('build-library',COMPILER+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','source/src/lib.rs','-o','build/libnext_brain.rlib'])
 command('build-driver',COMPILER+['--edition=2024','-C','opt-level=3','experiment.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/experiment'])
 command('initialization-default',['build/experiment','check-initialization'])
 command('initialization-jitter',['build/experiment','check-initialization','initial/jitter94001__e1e-4.csv'])
 required=['analyze.py','plot.py','reproduce.py','audit.py']
 assert all((ROOT/n).exists() for n in required),required
 paths=[p for d in ['source','legacy','graphs','initial'] for p in (ROOT/d).rglob('*') if p.is_file()]
 paths+=list(ROOT.glob('*.py'))+[ROOT/n for n in ['experiment.rs','DRIVER.txt','protocol.json','graph-audit.json','initial-audit.json','inherited-inputs-sha256.json']]
 save(ROOT/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),compiler=subprocess.check_output(COMPILER+['--version','--verbose'],text=True)))
 save(ROOT/'experiment-lock.json',dict(locked_utc=now(),scientific_runs_started=False,expected_runs=231,files={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}))
 print('PREPARED: all design, analysis and inputs locked before simulation.',flush=True)
def check_lock():
 lock=load(ROOT/'experiment-lock.json')
 for k,v in lock['files'].items():assert sha(ROOT/k)==v,k
 return lock
def simulate(record,folder='runs',pass_initial=True):
 stem=record['stem'];prefix=ROOT/folder/stem;cmd=['build/experiment','simulate',str(ROOT/'graphs'/f'{record["graph"]}.csv'),record['probe'],str(prefix)]
 if pass_initial:cmd.append(str(ROOT/record['initial_file']))
 command(stem,cmd);data=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(300,125,10)
 np.savez_compressed(prefix.with_suffix('.npz'),state_bits=data)
 with np.load(prefix.with_suffix('.npz')) as z:assert np.array_equal(data,z['state_bits'])
 prefix.with_suffix('.bin').unlink()
 return dict(record,npz_sha256=sha(prefix.with_suffix('.npz')),csv_sha256=sha(prefix.with_suffix('.csv')),json_sha256=sha(prefix.with_suffix('.json')))
def run():
 check_lock();assert not list((ROOT/'runs').glob('*')) and not (ROOT/'run-complete.json').exists();records=[];technical=[]
 for probe in PROBES:
  record=dict(stem=f'original__{probe}',type='original',seed=None,probe=probe,epsilon=None,graph='original',initial_file='initial/zero.csv')
  records.append(simulate(record,pass_initial=False))
  old=ROOT/'legacy/runs'/f'homogeneous__original__{probe}__explicit.npz'
  with np.load(old) as z,np.load(ROOT/'runs'/f'{record["stem"]}.npz') as y:assert np.array_equal(z['state_bits'],y['state_bits'])
  assert sha(ROOT/'legacy/runs'/f'homogeneous__original__{probe}__explicit.csv')==records[-1]['csv_sha256']
  for kind,graph in [('zero_sham','original'),('inverse_sham','inverse-sham')]:
   rec=dict(record,stem=f'{kind}__{probe}',type=kind,graph=graph);rr=simulate(rec,folder='technical',pass_initial=kind=='zero_sham');technical.append(rr)
   with np.load(ROOT/'technical'/f'{rr["stem"]}.npz') as a,np.load(old) as b:assert np.array_equal(a['state_bits'],b['state_bits'])
   assert rr['csv_sha256']==records[-1]['csv_sha256']
 save(ROOT/'technical-validation.json',dict(status='pass',new_originals_match_legacy_exact=3,sham_runs=technical,technical_runs_not_scientific_conditions=6))
 for seed in SWAP_SEEDS:
  for probe in PROBES:
   records.append(simulate(dict(stem=f'swap{seed}__{probe}',type='swap',seed=seed,probe=probe,epsilon=None,graph=f'swap{seed}',initial_file='initial/zero.csv')))
  print(f'Swaps: {len(records)}/231',flush=True)
 for seed in INITIAL_SEEDS:
  for label,epsilon in DOSES:
   for probe in PROBES:
    records.append(simulate(dict(stem=f'jitter{seed}__{label}__{probe}',type='jitter',seed=seed,probe=probe,epsilon=epsilon,graph='original',initial_file=f'initial/jitter{seed}__{label}.csv')))
  print(f'Initial conditions: {len(records)}/231',flush=True)
 check_lock();assert len(records)==231
 save(ROOT/'run-complete.json',dict(status='pass',completed_utc=now(),total_runs=231,runs=records))
def verify():
 check_lock();records=load(ROOT/'run-complete.json')['runs'];assert len(records)==231
 for r in records:
  prefix=ROOT/'runs'/r['stem']
  for ext in ('npz','csv','json'):assert sha(prefix.with_suffix('.'+ext))==r[ext+'_sha256']
  with np.load(prefix.with_suffix('.npz')) as z:a=z['state_bits']
  assert a.shape==(300,125,10) and np.isfinite(np.ascontiguousarray(a[:,:,1:8]).view(np.float32)).all()
  assert set(np.unique(a[:,:,0])).issubset({0,100})
  rows=np.loadtxt(prefix.with_suffix('.csv'),delimiter=',',skiprows=1,dtype=np.int64);assert rows.shape==(300,5)
  assert np.array_equal(rows[:,0],np.arange(300)) and np.array_equal(rows[:,1],a[:,:,0].sum(axis=1))
  outdeg=np.bincount(edges(ROOT/'graphs'/f'{r["graph"]}.csv')[:,1],minlength=125);visits=(a[:,:,0]>0)@outdeg
  assert np.array_equal(rows[:,2],visits) and np.array_equal(rows[:,3],visits)
  j=load(prefix.with_suffix('.json'));initial=np.loadtxt(ROOT/r['initial_file'],delimiter=',',skiprows=1,dtype=np.uint32)[:,1]
  assert np.array_equal(j['initial_voltage_bits'],initial) and j['within_chunk_checks']==37625
  assert j['initialization_before_add_chunk'] and j['initial_queues_empty'] and j['other_initial_fields_match_frozen_harness']
  for slot,bits,init in zip(j['first_step_slot'],j['first_pre_update_voltage_bits'],initial):
   assert (slot is None)==(bits is None)
   if slot is not None:assert 0<=slot<300 and bits==int(init)
 save(ROOT/'validation.json',dict(status='pass',conditions=231,all_initial_states_applied_without_extra_wakeup=True,all_count_state_hashes_and_edge_visits_verified=True,first_execution_initial_bits_exact=True,within_chunk_equality_checked_by_driver=True))
 print('VERIFIED: all231 scientific conditions and their recorded initial/first-execution states.',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','run','verify']);a=p.parse_args();globals()[a.stage]()
