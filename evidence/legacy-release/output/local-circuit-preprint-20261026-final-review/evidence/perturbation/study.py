#!/usr/bin/env python3
"""Frozen-model perturbation/recovery experiment; only the driver is new."""
import argparse,csv,datetime,hashlib,json,platform,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
ARMS=['A_degree','B_aligned','C_random'];SEEDS=list(range(92001,92006))
GRAPHS=['original']+[f'{a}_{s}' for a in ARMS for s in SEEDS]
CONDITIONS={'baseline':0.0,'small':1.5,'double':3.0}
COMPILER=['rustup','run','1.98.1','rustc']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def table(p,rows):
 with Path(p).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def readcsv(p):return list(csv.DictReader(Path(p).open()))
def edges(p):return np.loadtxt(p,delimiter=',',skiprows=1,dtype=np.int64)
def matrices(e):
 w=np.ascontiguousarray(e[:,3],dtype=np.uint32).view(np.float32).astype(float);a=np.zeros((2,125,125));a[(e[:,1]>=100).astype(int),e[:,2],e[:,1]]=w;return a

def command(label,args):
 p=ROOT/'logs'/f'{label}.log';started=time.monotonic()
 with p.open('w') as f:
  f.write(json.dumps(list(map(str,args)))+'\n');f.flush();result=subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 with (ROOT/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(label=label,command=list(map(str,args)),elapsed_s=time.monotonic()-started,returncode=result.returncode))+'\n')
 assert result.returncode==0,p

def build_predictors():
 p=ROOT/'legacy_inputs/runs/original__module_burst__explicit.npz'
 with np.load(p) as z:a=z['state_bits']
 S=a[:,:,0].astype(float).T
 U,s,v=np.linalg.svd(S,full_matrices=False);coverage=np.cumsum(s*s)/np.sum(s*s);k90=int(np.searchsorted(coverage,.9)+1)
 X=np.ascontiguousarray(a[:,:,1:4]).view(np.float32).astype(float);scale=X.std(axis=(0,1));assert np.all(scale>0)
 np.savez_compressed(ROOT/'predictors/training-basis.npz',U5=U[:,:5],U90=U[:,:k90],singular_values=s,state_scale=scale)
 W=matrices(edges(ROOT/'graphs/original.csv'));G=np.concatenate(W,axis=0);adj=(W.sum(axis=0)>0).astype(np.int64)
 recip0=int(np.trace(adj@adj)//2);tri0=int(np.trace(adj@adj@adj)//3)
 old={r['graph']:r for r in readcsv(ROOT/'legacy_inputs/graph-features.csv')};oldrank={r['graph']:r for r in readcsv(ROOT/'legacy_inputs/rank-transfer.csv')}
 rows=[]
 for name in GRAPHS[1:]:
  wg=matrices(edges(ROOT/'graphs'/f'{name}.csv'));D=np.concatenate(wg-W,axis=0);f=old[name]
  rows.append(dict(graph=name,treatment=name.rsplit('_',1)[0],activity_rank5=float(np.linalg.norm(D@U[:,:5])/np.linalg.norm(G@U[:,:5])),activity_training90=float(np.linalg.norm(D@U[:,:k90])/np.linalg.norm(G@U[:,:k90])),training_replay_distortion=float(np.linalg.norm(D@S)/np.linalg.norm(G@S)),weight_frobenius_distortion=float(np.linalg.norm(D)/np.linalg.norm(G)),reciprocal_pair_change=abs(int(f['reciprocal_pairs'])-recip0),directed_triangle_change=abs(int(f['directed_triangles'])-tri0),source_subspace_distance=float(f['leading_source_subspace_distance']),singular_value_distance=float(f['singular_value_relative_distance']),old_module_state_error=float(oldrank[name]['module_burst_state_score'])))
 table(ROOT/'predictors/frozen-predictors.csv',rows)
 save(ROOT/'predictors/training-summary.json',dict(training_source=str(p.relative_to(ROOT)),training_source_sha256=sha(p),centered=False,rank5=5,rank5_energy_fraction=float(coverage[4]),secondary_training90_rank=k90,secondary_training90_energy_fraction=float(coverage[k90-1]),state_scale=scale.tolist(),graphs_used_to_fit_basis=['original'],new_stimulus_data_used=False))

def prepare():
 assert not (ROOT/'experiment-lock.json').exists()
 for n in ['build','logs','runs','analysis','predictors','technical']:(ROOT/n).mkdir(exist_ok=True)
 inherited=load(ROOT/'inherited-inputs-sha256.json');assert all(sha(ROOT/k)==v for k,v in inherited.items())
 build_predictors()
 protocol=dict(title='Finite-horizon perturbation response and training-activity structural predictors',written_utc=now(),scope='Exploratory follow-up; fixed before new scientific simulations; existing model and graphs unchanged',graphs=GRAPHS,graph_independence='15 conditional surrogates of one original; not 15 independent original networks',steps=1000,dt_ms=.1,duration_ms=100,units_per_chunk=100,chunks=125,routing='explicit canonical source order only',conditioning=dict(targets=list(range(40,60)),strength_per_slot=150.0,slots=[0,80],new_location=True),perturbation=dict(targets=list(range(40,60)),slots=[200,210],conditions=CONDITIONS,relative_per_slot_to_conditioning=[0,.01,.02],dose_per_target_unit=[0,15,30],timing='pre-step injection; state row n recorded at completed time (n+1)*0.1ms'),
   model='Frozen placeholder current-like leaky integration; no new physical unit calibration or dt convergence claim',refractory='Pre-update until>slot gates membrane and channel decay; arriving inputs/field still accumulate. until=n+2 after spike skips only next slot.',
   new_observation_fields='10 pre_refractory_until,11 actually_stepped,12 refractory_kernel_skipped,13 events_due_before_step; original ten fields preserved',
   training='Only old original/module_burst source counts; uncentered SVD; state scales also frozen on this old reference',predictors=dict(primary='E/I-stacked relative ||Delta W U5||F',secondary=['training-only90% basis','full training source replay distortion'],controls=['matched Frobenius constant','absolute reciprocal/triangle count change','leading source singular-subspace distance','singular value distance','old module state error']),
   primary_outcome='RMS of standardized [(graph perturbed - graph baseline) - (original perturbed - original baseline)], over slots200:1000, for each amplitude separately',
   other_outcomes=['same-graph perturbation response magnitude/peak/AUC','baseline graph trajectory error vs original','relative response fidelity using original response as denominator','amplitude linearity diagnostic r_double vs 2*r_small','spike-count perturbation response error','source basis coverage on new original trajectory, never refit'],
   windows=dict(conditioning=[0,80],pre_perturbation=[80,200],pulse=[200,210],early=[210,300],middle=[300,500],late=[500,1000],terminal=[900,1000],primary_response=[200,1000]),
   recovery='After global response peak, earliest sample remaining below5%peak through end of recorded horizon with >=50 remaining slots. Otherwise right-censored. Zero responses separate. This is empirical window recovery, not an attractor/stability proof.',
   prediction_evaluation='15 graph-level values per amplitude, original excluded; prespecified positive-direction Spearman; all points, within-arm n5, leave-one-arm-out n10 sensitivities; constant guard1e-12. No p-values, no refitting, no choosing successful ranks after test.',
   predeclared_failures=['new input activity largely outside frozen U','small perturbation is gated or generates no spike response','prediction only separates treatment arms','directions disagree between amplitudes','small own response but poor original-response fidelity','no recovery in finite window'],
   technical_gates=['frozen library/input identity','independent kernel/refraction fixtures','first300slot bridge to old module reference','all48 finite states and within-chunk equality','preperturbation exact bitwise identity to own baseline','refractory and actual execution flags independently checked','full fresh reproduction'],preprint_action='No manuscript changes in this experiment')
 save(ROOT/'protocol.json',protocol)
 command('build-library',COMPILER+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','source/src/lib.rs','-o','build/libnext_brain.rlib'])
 command('build-driver',COMPILER+['--edition=2024','-C','opt-level=3','experiment.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/experiment'])
 command('build-kernel-audit',COMPILER+['--edition=2024','-C','opt-level=3','kernel_audit.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/kernel_audit'])
 command('kernel-audit',['build/kernel_audit'])
 command('bridge',['build/experiment','bridge','graphs/original.csv','technical/bridge'])
 bridge=np.fromfile(ROOT/'technical/bridge.bin',dtype='<u4').reshape(300,125,14)
 with np.load(ROOT/'legacy_inputs/runs/original__module_burst__explicit.npz') as z:assert np.array_equal(bridge[:,:,:10],z['state_bits'])
 rows=np.loadtxt(ROOT/'technical/bridge.csv',delimiter=',',skiprows=1,dtype=np.int64);old=np.loadtxt(ROOT/'legacy_inputs/runs/original__module_burst__explicit.csv',delimiter=',',skiprows=1,dtype=np.int64);assert np.array_equal(rows[:,:5],old)
 np.savez_compressed(ROOT/'technical/bridge.npz',state_bits=bridge);(ROOT/'technical/bridge.bin').unlink()
 save(ROOT/'technical/validation.json',dict(status='pass',independent_kernel_cases_passed=True,old_300_slot_state_bits_exact=True,old_spike_message_visit_and_stepped_counts_exact=True))
 save(ROOT/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),compiler=subprocess.check_output(COMPILER+['--version','--verbose'],text=True)))
 paths=list((ROOT/'source').rglob('*.rs'))+list((ROOT/'graphs').glob('*.csv'))+list((ROOT/'legacy_inputs').rglob('*'))+list((ROOT/'predictors').glob('*'))+list(ROOT.glob('*.py'))+[ROOT/'experiment.rs',ROOT/'kernel_audit.rs',ROOT/'protocol.json']
 save(ROOT/'experiment-lock.json',dict(locked_utc=now(),scientific_runs_started=False,expected_runs=48,files={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}))
 print('PREPARED: frozen model audited, historical bridge exact, predictors and protocol locked.',flush=True)

def check_lock():
 lock=load(ROOT/'experiment-lock.json');assert all(sha(ROOT/k)==v for k,v in lock['files'].items());return lock

def run():
 check_lock();assert not list((ROOT/'runs').glob('*.npz'));records=[]
 for name in GRAPHS:
  for condition,amplitude in CONDITIONS.items():
   stem=f'{name}__{condition}';prefix=ROOT/'runs'/stem
   command(stem,['build/experiment','simulate',str(ROOT/'graphs'/f'{name}.csv'),str(amplitude),str(prefix)])
   data=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(1000,125,14);np.savez_compressed(prefix.with_suffix('.npz'),state_bits=data)
   with np.load(prefix.with_suffix('.npz')) as z:assert np.array_equal(data,z['state_bits'])
   prefix.with_suffix('.bin').unlink();records.append(dict(graph=name,condition=condition,amplitude=amplitude,stem=stem,npz_sha256=sha(prefix.with_suffix('.npz')),csv_sha256=sha(prefix.with_suffix('.csv'))))
  print(f'{name}: {len(records)}/48',flush=True)
 check_lock();save(ROOT/'run-complete.json',dict(status='pass',runs=records,total_runs=48,completed_utc=now()))

def verify():
 check_lock();records=load(ROOT/'run-complete.json')['runs'];assert len(records)==48
 for name in GRAPHS:
  with np.load(ROOT/'runs'/f'{name}__baseline.npz') as z:base=z['state_bits']
  e=edges(ROOT/'graphs'/f'{name}.csv');outdeg=np.bincount(e[:,1],minlength=125)
  for condition in CONDITIONS:
   record=next(r for r in records if r['graph']==name and r['condition']==condition);prefix=ROOT/'runs'/record['stem']
   assert sha(prefix.with_suffix('.npz'))==record['npz_sha256'] and sha(prefix.with_suffix('.csv'))==record['csv_sha256']
   with np.load(prefix.with_suffix('.npz')) as z:a=z['state_bits']
   assert a.shape==(1000,125,14);assert np.array_equal(a[:200],base[:200]);assert np.isfinite(np.ascontiguousarray(a[:,:,1:8]).view(np.float32)).all()
   rows=np.loadtxt(prefix.with_suffix('.csv'),delimiter=',',skiprows=1,dtype=np.int64)
   assert np.array_equal(rows[:,0],np.arange(1000));assert np.array_equal(rows[:,1],a[:,:,0].sum(axis=1))
   visits=(a[:,:,0]>0)@outdeg;assert np.array_equal(rows[:,2],visits) and np.array_equal(rows[:,3],visits)
   assert np.array_equal(rows[:,4],a[:,:,11].sum(axis=1));assert np.array_equal(rows[:,5],a[:,:,12].sum(axis=1));assert np.array_equal(rows[:,6],(a[:,:,13]*a[:,:,11]).sum(axis=1))
   assert np.array_equal(a[1:,:,10],a[:-1,:,8]);assert not a[0,:,10].any()
   expected=(a[:,:,10]>np.arange(1000)[:,None])*a[:,:,11];assert np.array_equal(a[:,:,12],expected)
   prevspike=np.vstack([np.zeros((1,125),bool),a[:-1,:,0]>0]);assert np.array_equal(a[:,:,12],prevspike)
   assert not a[:,:,0][a[:,:,12]>0].any()
   assert set(np.unique(a[:,:,0])).issubset({0,100})
 save(ROOT/'validation.json',dict(status='pass',conditions=48,preperturbation_exact_in_all_conditions=True,step_and_refractory_observation_verified=True,finite_payloads_counts_edge_visits_and_checksums_verified=True))
 print('VERIFIED: all48 conditions, exact preperturbation equality, actual execution and refractory gating.',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','run','verify']);a=p.parse_args();globals()[a.stage]()
