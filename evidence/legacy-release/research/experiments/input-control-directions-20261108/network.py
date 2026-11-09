#!/usr/bin/env python3
from pathlib import Path
import json,csv,hashlib,datetime,subprocess,shutil,argparse,sys,platform
import numpy as np
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review/evidence';INPUTS=['G_B','F_B','F_H','G_T','F_HT']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def table(p,rs):
 with Path(p).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def prepare():
 assert not (ROOT/'design-lock.json').exists()
 for name in ['events','graphs','logs','build']: (ROOT/name).mkdir(exist_ok=True)
 old=BASE/'budget-boundary';shutil.copytree(old/'source',ROOT/'source',dirs_exist_ok=True);shutil.copy2(old/'experiment.rs',ROOT/'experiment.rs')
 for g in ['original']+['swap'+str(s) for s in range(93001,93020)]:shutil.copy2(BASE/'sensitivity/graphs'/f'{g}.csv',ROOT/'graphs'/f'{g}.csv')
 shutil.copy2(ROOT.parent/'paired-direction-mechanism-20261108/results/pool-lock.json',ROOT/'pool-lock.json')
 perm=np.random.Generator(np.random.PCG64(20261108)).permutation(160);slots=sorted(map(int,perm[:80]));write(ROOT/'time-permutation.json',dict(seed=20261108,permutation=perm.tolist(),active_slots=slots,unchanged_zero_slots=list(range(160,300))))
 summary=[];mats={}
 for u in INPUTS:
  targets=list(range(100)) if u.startswith('G') else list(range(0,100,5));times=slots if u in ['G_T','F_HT'] else list(range(80));amp=750 if u in ['F_H','F_HT'] else 150;bits=int(np.float32(amp).view(np.uint32));rows=[dict(slot=n,target=k,amplitude_bits=bits) for n in times for k in targets];table(ROOT/'events'/f'{u}.csv',rows);mat=np.zeros((300,125),np.float32);mat[np.ix_(times,targets)]=amp;mats[u]=mat
  summary.append(dict(input=u,targets=len(targets),events=len(rows),amplitude=amp,total=float(mat.sum(dtype=np.float64)),first_slot=min(times),last_slot=max(times),sha256=sha(ROOT/'events'/f'{u}.csv')))
 assert all(float(mats[u].sum())==1200000 for u in ['G_B','F_H','G_T','F_HT'])
 for u,v in [('G_B','G_T'),('F_H','F_HT')]:assert np.array_equal(np.sort(mats[u],axis=0),np.sort(mats[v],axis=0))
 table(ROOT/'input-summary.csv',summary)
 files=[p for folder in ['source','graphs','events'] for p in (ROOT/folder).rglob('*') if p.is_file()]+[ROOT/n for n in ['experiment.rs','pool-lock.json','time-permutation.json','input-summary.csv','PROTOCOL.txt','protocol-lock.json']]+list(ROOT.glob('*.py'))
 write(ROOT/'design-lock.json',dict(locked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_input_runs_started=False,files={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))}))
 print('design locked; no simulation')
def check():
 lock=json.loads((ROOT/'design-lock.json').read_text())
 for f,h in lock['files'].items():assert sha(ROOT/f)==h,f
 assert sha(ROOT/'PROTOCOL.txt')==json.loads((ROOT/'protocol-lock.json').read_text())['sha256']
def command(args,log):
 with log.open('w') as f:subprocess.run(list(map(str,args)),cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
def compile():
 check();cmd=['rustup','run','1.98.1','rustc'];command(cmd+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','source/src/lib.rs','-o','build/libnext_brain.rlib'],ROOT/'logs/build-library.log');command(cmd+['--edition=2024','-C','opt-level=3','experiment.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/experiment'],ROOT/'logs/build-driver.log');command([ROOT/'build/experiment','check-initialization'],ROOT/'logs/initialization.log');write(ROOT/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),compiler=subprocess.check_output(cmd+['--version','--verbose'],text=True),driver_sha256=sha(ROOT/'build/experiment')))
def run(out):
 check();out.mkdir(exist_ok=False,parents=True);records=[];bridges=0
 for u in INPUTS:
  for g in ['original']+['swap'+str(s) for s in range(93001,93020)]:
   stem=g+'__'+u;prefix=out/stem;command([ROOT/'build/experiment','simulate',ROOT/'graphs'/f'{g}.csv',ROOT/'events'/f'{u}.csv',prefix],out/(stem+'.log'));bits=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(300,125,10);np.savez_compressed(prefix.with_suffix('.npz'),state_bits=bits);prefix.with_suffix('.bin').unlink()
   assert np.all(np.isfinite(np.ascontiguousarray(bits[:,:,1:8]).view(np.float32)))
   if u in ['G_B','F_B']:
    old=BASE/'sensitivity/runs'/f'{g}__{ "global_burst" if u=="G_B" else "focal_burst"}'
    assert np.array_equal(bits,np.load(old.with_suffix('.npz'))['state_bits']),(u,g,'bridge states');assert prefix.with_suffix('.csv').read_bytes()==old.with_suffix('.csv').read_bytes(),(u,g,'bridge CSV');bridges+=1
   records.append(dict(input=u,graph=g,stem=stem,npz_sha256=sha(prefix.with_suffix('.npz')),csv_sha256=sha(prefix.with_suffix('.csv')),json_sha256=sha(prefix.with_suffix('.json'))))
  print('network',u,'20 runs complete',flush=True)
 write(out/'completed.json',dict(records=records,bridge_conditions_exact=bridges,new_scientific_conditions=60,all_conditions=100))
if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('action',choices=['prepare','compile','run']);q.add_argument('--output-dir',type=Path,default=ROOT/'runs');x=q.parse_args()
 if x.action=='prepare':prepare()
 elif x.action=='compile':compile()
 else:run(x.output_dir.resolve())
