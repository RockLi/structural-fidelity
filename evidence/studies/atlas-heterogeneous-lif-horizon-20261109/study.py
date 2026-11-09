from model import *
import sys,datetime,importlib.metadata as meta,platform,concurrent.futures,collections

def prepare():
 assert not (R/'design-lock.json').exists()
 try:meta.distribution('Brian2');raise AssertionError('upstream Brian2 installed')
 except meta.PackageNotFoundError:pass
 assert meta.version('brian2-atlas')=='0.2.0'
 # Exact dyadic input control checks, independent of firing outcomes.
 x={u:input_matrix(u) for u in INPUTS}
 for u,v in [('G_B','F_H'),('G_T','F_HT')]:assert np.array_equal(x[u].sum(1),x[v].sum(1))
 for u,v in [('G_B','G_T'),('F_H','F_HT')]:assert np.array_equal(np.sort(x[u][:300],axis=0),np.sort(x[v][:300],axis=0))
 for seed in SEEDS:
  for mode in MODES:
   for u in INPUTS:
    p=R/'models'/f'seed{seed}_{mode}_{u}/model.json'
    if not p.exists():
     import brian2 as b;b.device.reinit();build(seed,mode,u)
    m=load(p);assert m['run']['clocks'][0]['steps']==3000
    # Verify support and every initial parameter directly against copied graph.
    g=edges(seed);tau,th=pars(seed,mode);pp=m['instance']['populations'][0]['parameters'];assert np.array_equal(vals(pp['tau']),tau) and np.array_equal(vals(pp['vth']),th)
    for d,s in zip(m['definition']['synapses'],m['instance']['synapses']):
     src,dst,w,rows=expand(g,d['name']=='exc');assert np.array_equal(s['source'],src) and np.array_equal(s['target'],dst) and np.array_equal(vals(s['initial_state']['w']),w)
    print('EXPORTED',seed,mode,u,flush=True)
 dist=meta.distribution('brian2-atlas');dep={}
 for pp in dist.files:
  p=Path(dist.locate_file(pp))
  if p.is_file() and p.suffix in ['.py','.so','.dylib'] or p.is_file() and p.name in ['b2-runner','METADATA','RECORD']:dep[str(p)]=sha(p)
 save(R/'atlas-installed-lock.json',dep);save(R/'environment.json',dict(python=sys.version,platform=platform.platform(),atlas=meta.version('brian2-atlas'),numpy=np.__version__,backend=str(BACKEND),backend_sha256=sha(BACKEND),pip_freeze=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)))
 old=R.parents[2]/'output/local-circuit-preprint-20261109-final-polish';frozen=[*old.joinpath('manuscript').glob('*.docx'),*old.joinpath('manuscript').glob('*.pdf'),old/'local-circuit-preprint-source-and-evidence.zip'];save(R/'frozen-baseline.json',{str(p):sha(p) for p in frozen})
 save(R/'previous-study-manifests.json',{str(R.parent/n/'MANIFEST.json'):sha(R.parent/n/'MANIFEST.json') for n in ['multigraph-input-validation-20261109','cross-generator-validation-20261109']})
 files=[p for p in R.rglob('*') if p.is_file() and not set(p.relative_to(R).parts)&{'.venv','__pycache__','tmp','logs'}]
 save(R/'design-lock.json',dict(locked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_outcomes_seen=False,files={str(p.relative_to(R)):sha(p) for p in files}))
 print('DESIGN LOCKED',flush=True)

def check():
 for p,h in load(R/'design-lock.json')['files'].items():assert sha(R/p)==h,p
 for p,h in load(R/'atlas-installed-lock.json').items():assert sha(p)==h,p

def networks():
 import brian2_atlas # initialize signal handlers on main thread
 check();jobs=[(seed,mode,u) for seed in SEEDS for mode in MODES for u in INPUTS]
 def work(job):
  seed,mode,u=job;base=load(R/'models'/f'seed{seed}_{mode}_{u}/model.json');folder=R/'runs'/f'seed{seed}_{mode}_{u}';folder.mkdir(exist_ok=True);records=[]
  for name in ['original']+[f'swap{x}' for x in range(93001,93020)]:
   keep=name=='original';m=variant(base,seed,mode,name,record=keep);out=cached_run(m,folder/name,keep);records.append(dict(name=name,sha256=sha(folder/f'{name}.npz')))
   if keep:
    assert np.isfinite(out['v']).all() and np.isfinite(out['ge']).all() and np.isfinite(out['gi']).all();reference=out
    if mode=='hom':
     for key in ['v','ge','gi','spikes']:assert np.all(out[key].reshape(3000,C,U)==out[key].reshape(3000,C,U)[:,:,:1])
    for key in ['ge','gi']:assert np.all(out[key].reshape(3000,C,U)==out[key].reshape(3000,C,U)[:,:,:1])
  tech=R/'technical'/f'seed{seed}_{mode}_{u}';tech.mkdir(exist_ok=True)
  for steps,label in [(3000,'repeat'),(300,'prefix30'),(1000,'prefix100')]:
   z=cached_run(variant(base,seed,mode,steps=steps,record=True),tech/label,True)
   for key in z:assert np.array_equal(z[key].view(np.uint8),reference[key][:steps].view(np.uint8)),(job,label,key)
  save(folder/'complete.json',dict(status='pass',scientific_runs=20,technical_runs=3,records=records));print('NETWORK COMPLETE',seed,mode,u,flush=True)
 # Independent directory per worker; no scientific adaptation or shared RNG.
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(work,jobs))
 check();save(R/'network-complete.json',dict(status='pass',scientific_conditions=600,technical_repeats_and_prefixes=90))

if __name__=='__main__':globals()[sys.argv[1]]()
