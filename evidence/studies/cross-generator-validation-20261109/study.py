from pathlib import Path
import argparse,os,subprocess,sys,json,hashlib,time,datetime,platform
import numpy as np
import sampling_inherited as samp
import generators
R=Path(__file__).resolve().parent;OLD=R.parent/'input-control-directions-20261108';SEEDS=[201,202,203,301,302,303];INPUTS=['G_B','F_B','F_H','G_T','F_HT']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def cmd(a,log,env=None):
 start=time.perf_counter()
 with log.open('w') as f:subprocess.run(list(map(str,a)),stdout=f,stderr=subprocess.STDOUT,check=True,cwd=R,env=env)
 with (R/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(command=list(map(str,a)),log=str(log.relative_to(R)),seconds=time.perf_counter()-start))+'\n')
def env(seed):e=os.environ.copy();e['NB_GRAPH_ROOT']=str(R/f'seed{seed}');e['PYTHONDONTWRITEBYTECODE']='1';return e

def prepare():
 assert not (R/'design-lock.json').exists()
 for n in ['build','logs','technical']:(R/n).mkdir(exist_ok=True)
 cc=['rustup','run','1.98.1','rustc'];cmd(cc+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','source/src/lib.rs','-o','build/libnext_brain.rlib'],R/'logs/compile-library.log')
 for name in ['experiment','generate']:cmd(cc+['--edition=2024','-C','opt-level=3',name+'.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/'+name],R/f'logs/compile-{name}.log')
 cmd([R/'build/experiment','check-initialization'],R/'logs/initialization.log')
 cmd([R/'build/generate',99,R/'technical/seed99.csv'],R/'logs/generate99.log')
 assert (R/'technical/seed99.csv').read_bytes()==(OLD/'graphs/original.csv').read_bytes(),'seed99 generator mismatch'
 sys.path.insert(0,str(R.parent/'paired-direction-mechanism-20261108'));import mechanism as m
 graphs=[]
 for seed in SEEDS:
  d=R/f'seed{seed}';(d/'graphs').mkdir();orig,metadata=generators.make(seed);again,meta2=generators.make(seed);assert np.array_equal(orig,again) and metadata==meta2;samp.write_edges(d/'graphs/original.csv',orig);write(d/'generator.json',metadata);write(d/'structure.json',generators.describe(orig,metadata));audit=[];pairs={}
  for i,arm in enumerate([0]*5+[1]*5+[2]*5+[3]*4):
   e,detail=samp.one_swap(orig,arm,100000*seed+93001+i);name='swap'+str(93001+i);samp.write_edges(d/'graphs'/f'{name}.csv',e);details=dict(name=name,**detail,**samp.audit_graph(orig,e,2),descriptor_change=generators.edit_change(orig,e,metadata));audit.append(details);pair=tuple(sorted([detail['b'],detail['d']]));pairs.setdefault(pair,[]).append(name)
  pool=[m.pair_pool(orig.astype(np.uint32),t,i) for i,t in enumerate(sorted(pairs))];assert all(len(x['directions'])==16 for x in pool)
  write(d/'pool-lock.json',pool);write(d/'graph-audit.json',dict(seed=seed,edges=len(orig),arms=np.bincount(orig[:,0],minlength=4).tolist(),swaps=audit,pairs=[dict(pair=i,targets=list(t),swaps=pairs[t]) for i,t in enumerate(sorted(pairs))],distinct_swap_graphs=len({sha(d/'graphs'/f'{x["name"]}.csv') for x in audit})))
  graphs.append(dict(seed=seed,family=generators.family(seed),edges=len(orig),pairs=len(pool),direction_conditions=len(pool)*16*5))
 deps={}
 for folder in ['paired-direction-mechanism-20261108','finite-horizon-family-prototype-20261108','finite-horizon-certificate-cost-20261108','finite-horizon-certificate-audit-20261108']:
  for p in (R.parent/folder).iterdir():
   if p.is_file() and p.suffix in ['.py','.c','.dylib']:deps[str(p)]=sha(p)
 write(R/'dependencies.json',deps)
 frozen=R.parents[2]/'output/local-circuit-preprint-20261109-final-polish';write(R/'frozen-baseline.json',{str(p):sha(p) for p in list((frozen/'manuscript').glob('*.docx'))+list((frozen/'manuscript').glob('*.pdf'))+[frozen/'local-circuit-preprint-source-and-evidence.zip']})
 write(R/'prior-study-lock.json',dict(manifest_path=str(R.parent/'multigraph-input-validation-20261109/MANIFEST.json'),manifest_sha256=sha(R.parent/'multigraph-input-validation-20261109/MANIFEST.json')))
 write(R/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),rustc=subprocess.check_output(cc+['--version','--verbose'],text=True)))
 files=[p for p in R.rglob('*') if p.is_file() and not set(p.relative_to(R).parts)&{'logs','__pycache__'} and p.name!='commands.jsonl']
 write(R/'design-lock.json',dict(locked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_graph_outcomes_seen=False,graphs=graphs,files={str(p.relative_to(R)):sha(p) for p in sorted(files)}));print('DESIGN LOCKED',graphs,flush=True)

def simulate(graph,event,prefix):
 cmd([R/'build/experiment','simulate',graph,event,prefix],prefix.with_suffix('.log'));bits=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(300,125,10)
 assert np.isfinite(np.ascontiguousarray(bits[:,:,1:8]).view(np.float32)).all();assert np.isin(bits[:,:,0],[0,100]).all()
 rows=np.loadtxt(prefix.with_suffix('.csv'),skiprows=1,delimiter=',',dtype=np.int64);assert np.array_equal(rows[:,1],bits[:,:,0].sum(1))
 g=samp.edges(graph);vis=(bits[:,:,0]>0)@np.bincount(g[:,1],minlength=125);assert np.array_equal(rows[:,2],vis) and np.array_equal(rows[:,3],vis)
 meta=json.loads(prefix.with_suffix('.json').read_text());assert meta['within_chunk_checks']==37625
 np.savez_compressed(prefix.with_suffix('.npz'),state_bits=bits);prefix.with_suffix('.bin').unlink();return bits

def networks():
 os.environ['NB_GRAPH_ROOT']=str(R/f'seed{SEEDS[0]}');import network;network.check()
 for u in INPUTS:
  bits=simulate(R/'technical/seed99.csv',OLD/'events'/f'{u}.csv',R/'technical'/f'original99__{u}')
  assert np.array_equal(bits,np.load(OLD/'runs'/f'original__{u}.npz')['state_bits'])
 for seed in SEEDS:
  d=R/f'seed{seed}';(d/'runs').mkdir();(d/'repeat').mkdir();records=[]
  for u in INPUTS:
   ref=None
   for name in ['original']+['swap'+str(i) for i in range(93001,93020)]:
    stem=name+'__'+u;bits=simulate(d/'graphs'/f'{name}.csv',d/'events'/f'{u}.csv',d/'runs'/stem);records.append(dict(stem=stem,sha256=sha(d/'runs'/f'{stem}.npz')))
    if name=='original':ref=bits
   repeat=simulate(d/'graphs/original.csv',d/'events'/f'{u}.csv',d/'repeat'/f'original__{u}');assert np.array_equal(repeat,ref)
   print('NETWORK',seed,u,'20 scientific +1 technical',flush=True)
  write(d/'network-complete.json',dict(status='pass',scientific_conditions=100,technical_repeats=5,records=records))
  cmd([sys.executable,'-B',R/'analyze_network.py'],R/f'logs/network-analysis{seed}.log',env(seed))

def scores():
 for seed in SEEDS:
  d=R/f'seed{seed}';cmd([sys.executable,'-B',R/'directions.py','score','--runs-dir',d/'runs','--output-dir',d/'directions'],R/f'logs/score{seed}.log',env(seed));print('SCORES LOCKED',seed,flush=True)
 write(R/'all-score-lock.json',dict(locked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_radius_outcomes_seen=False,files={str(p.relative_to(R)):sha(p) for s in SEEDS for p in (R/f'seed{s}/directions').glob('*') if p.is_file()}))

def radii():
 for n,h in json.loads((R/'all-score-lock.json').read_text())['files'].items():assert sha(R/n)==h
 for seed in SEEDS:
  d=R/f'seed{seed}';cmd([sys.executable,'-B',R/'directions.py','radii','--runs-dir',d/'runs','--output-dir',d/'directions'],R/f'logs/radii{seed}.log',env(seed));print('RADII COMPLETE',seed,flush=True)
  for script in ['validate_new.py','analyze_directions.py','analyze_detail.py','diagnostics.py']:
   cmd([sys.executable,'-B',R/script],R/f'logs/{script[:-3]}{seed}.log',env(seed));print(script,seed,'complete',flush=True)

if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('phase',choices=['prepare','networks','scores','radii']);args=q.parse_args();globals()[args.phase]()
