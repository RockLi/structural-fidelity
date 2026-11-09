from pathlib import Path
import os,json,hashlib,struct,copy,subprocess,time
import numpy as np
R=Path(__file__).resolve().parent
SEEDS=[100,201,301];MODES=['hom','hetero'];INPUTS=['G_B','F_B','F_H','G_T','F_HT'];HORIZONS=[300,1000,3000];C=125;U=4;N=C*U;DT=.0001
BACKEND=R/'.venv/lib/python3.13/site-packages/brian2_rust/_bin/b2-runner'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def bits(x):return struct.pack('>d',float(x)).hex()
def vals(x):return np.frombuffer(bytes.fromhex(''.join(x)),dtype='>f8').astype(float)
def edges(seed,name='original'):return np.loadtxt(R/f'seed{seed}/graphs/{name}.csv',delimiter=',',skiprows=1,dtype=np.int64)
def pars(seed,mode):
 tau=np.full(N,.020);theta=np.full(N,-.050)
 if mode=='hetero':
  rng=np.random.Generator(np.random.PCG64(20261109+seed))
  for k in range(C):
   tau[4*k:4*k+4]=rng.permutation(np.linspace(18,22,4))*.001;theta[4*k:4*k+4]=rng.permutation(np.linspace(-51,-49,4))*.001
 return tau,theta

def input_matrix(u):
 rows=np.loadtxt(R/'events'/f'{u}.csv',delimiter=',',skiprows=1,dtype=np.int64);x=np.zeros((300,C));am=np.ascontiguousarray(rows[:,2],dtype=np.uint32).view(np.float32)
 for (n,k,_),v in zip(rows,am):assert v in [150,750];x[n,k]=.015625 if v==150 else .078125
 return np.tile(x,(10,1))
def expand(g,excit):
 ix=np.flatnonzero((g[:,1]<100)==excit);row=np.repeat(ix,16);su=np.tile(np.repeat(np.arange(U),U),len(ix));tu=np.tile(np.arange(U),len(ix)*U)
 src=g[row,1]*U+su;dst=g[row,2]*U+tu;w=np.ascontiguousarray(g[row,3],dtype=np.uint32).view(np.float32).astype(float)*.001/U
 return src,dst,w,row

def build(seed,mode,u):
 import brian2 as b
 import brian2_atlas
 b.start_scope();b.set_device('atlas',engine='reference',numeric_mode='reference-f64',build_on_run=False);b.seed(20261109);b.defaultclock.dt=DT*b.second
 inp=input_matrix(u);amplitudes=inp.max(axis=0);wave=(inp.sum(axis=1)>0).astype(float);stim=b.TimedArray(wave,dt=DT*b.second)
 eqs='''dv/dt = (El + Ib + ge - gi + drive_amp*stim(t) - v)/tau : volt (unless refractory)
dge/dt = -ge/taue : volt
dgi/dt = -gi/taui : volt
tau : second (constant)
vth : volt (constant)
drive_amp : volt (constant)'''
 ns=dict(El=-65*b.mV,Ib=18*b.mV,Vr=-60*b.mV,taue=5*b.ms,taui=10*b.ms,stim=stim)
 cells=b.NeuronGroup(N,eqs,threshold='v >= vth',reset='v = Vr',refractory=2*b.ms,method='euler',namespace=ns,name='cells');tau,theta=pars(seed,mode);cells.v=-60*b.mV;cells.tau=tau*b.second;cells.vth=theta*b.volt;cells.drive_amp=np.repeat(amplitudes,U)*b.volt
 syn=[];g=edges(seed)
 for ex,name,state in [(True,'exc','ge'),(False,'inh','gi')]:
  src,dst,w,row=expand(g,ex);s=b.Synapses(cells,cells,'w:volt',on_pre=state+'_post += w',delay=DT*b.second,name=name);s.connect(i=src,j=dst);s.w=w*b.volt;syn.append(s)
 sm=b.SpikeMonitor(cells,name='spikes');st=b.StateMonitor(cells,['v','ge','gi','not_refractory','lastspike'],record=True,when='end',name='states')
 net=b.Network(cells,*syn,sm,st);net.run(.3*b.second,namespace={});directory=R/'models'/f'seed{seed}_{mode}_{u}';b.get_device().build(directory=str(directory),run=False)
 model=load(directory/'model.json');assert model['definition']['numeric_profile']=='reference-f64';assert model['run']['clocks'][0]['steps']==3000
 return model

def variant(base,seed,mode,name='original',steps=3000,record=True,alpha=None,fam=None,di=None):
 m=copy.deepcopy(base);m['run']['duration']=bits(steps*DT);m['run']['clocks'][0]['steps']=steps
 p=m['definition']['populations'][0];p['steps']=steps;p['monitor']['window_steps']=steps
 if not record:
  p['monitor']['record']=[];p['monitor']['variables']=[];p['state_monitors']=[]
  sch=m['definition']['schedule'];removed={x['id'] for x in sch['nodes'] if x['operation']=='state_monitor'};sch['nodes']=[x for x in sch['nodes'] if x['id'] not in removed]
  for x in sch['nodes']:x['dependencies']=[y for y in x['dependencies'] if y not in removed]
 g=edges(seed,name);tau,theta=pars(seed,mode);sgn={}
 if alpha is not None:
  sgn={(int(src),int(dst)):int(s) for (src,dst,_),s in zip(fam['edges'],fam['directions'][di])}
 for definition,instance in zip(m['definition']['synapses'],m['instance']['synapses']):
  src,dst,w,row=expand(g,definition['name']=='exc')
  if alpha is not None:
   signs=np.array([sgn.get((int(g[i,1]),int(g[i,2])),0) for i in row]);w=w*(1+signs*float(alpha))
  instance['source']=src.tolist();instance['target']=dst.tolist();instance['initial_state']['w']=[bits(v) for v in w]
  amplitude=vals(m['instance']['populations'][0]['parameters']['drive_amp'])
  for key,v in [('tau_pre',tau[src]),('tau_post',tau[dst]),('vth_pre',theta[src]),('vth_post',theta[dst]),('drive_amp_pre',amplitude[src]),('drive_amp_post',amplitude[dst])]:
   if key in instance['parameters']:
    instance['parameters'][key]=[bits(vv) for vv in v] # encoded model parameters use IEEE values also for integer domain
 from brian2_rust.protocol import attach_protocol
 return attach_protocol(m)

def run(m,prefix,keep_state):
 from brian2_rust.results import load_results
 import tempfile,shutil
 prefix=Path(prefix);prefix.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='atlas-',dir=R/'tmp') as td:
  td=Path(td);p=td/'model.json';p.write_text(json.dumps(m,separators=(',',':')));mh=sha(p);t=time.perf_counter();q=subprocess.run([str(BACKEND),str(p),str(td/'out')],capture_output=True,text=True)
  prefix.with_suffix('.log').write_text(q.stdout+q.stderr);assert q.returncode==0,(prefix,q.stderr)
  elapsed=time.perf_counter()-t;res=load_results(m,td/'out');pop=res['populations'][0]
  if not (R/'preflight/result-layout.json').exists():save(R/'preflight/result-layout.json',{k:str(type(v)) for k,v in pop.items()})
  steps=m['run']['clocks'][0]['steps'];sp=np.zeros((steps,N),np.uint8);sp[np.asarray(pop['spike_ticks'],int),np.asarray(pop['indices'],int)]=1
  out=dict(spikes=sp)
  if keep_state:
   for key in ['v','ge','gi']:out[key]=np.asarray(pop['trace'][key])
  np.savez_compressed(prefix.with_suffix('.npz'),**out);save(prefix.with_suffix('.json'),dict(atlas_version='0.2.0',backend_sha256=sha(BACKEND),model_sha256=mh,seconds=elapsed,steps=steps,spikes=int(sp.sum()),result_summary=res['metadata']))
 return out


def cached_run(m,prefix,keep_state):
 prefix=Path(prefix)
 if prefix.with_suffix('.npz').exists():
  info=load(prefix.with_suffix('.json'))
  expected=hashlib.sha256(json.dumps(m,separators=(',',':')).encode()).hexdigest()
  assert info['model_sha256']==expected,(prefix,'cached model mismatch')
  assert info['backend_sha256']==sha(BACKEND)
  return dict(np.load(prefix.with_suffix('.npz')))
 return run(m,prefix,keep_state)
