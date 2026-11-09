from model import *
import replay
import brian2 as b,brian2_atlas
b.set_device('atlas',engine='reference',numeric_mode='reference-f64',directory=str(R/'preflight/eight-unit'))
b.defaultclock.dt=DT*b.second
ns=dict(El=-65*b.mV,Ib=18*b.mV,Vr=-60*b.mV,taue=5*b.ms,taui=10*b.ms)
g=b.NeuronGroup(8,'''dv/dt = (El + Ib + drive_amp + ge - gi - v)/tau : volt (unless refractory)
dge/dt=-ge/taue : volt
dgi/dt=-gi/taui : volt
drive_amp : volt (constant)
tau : second (constant)
vth : volt (constant)''',threshold='v >= vth',reset='v=Vr',refractory=2*b.ms,method='euler',namespace=ns,name='cells')
tau=np.tile(np.linspace(18,22,4)*.001,2);th=np.tile(np.linspace(-51,-49,4)*.001,2);g.tau=tau*b.second;g.vth=th*b.volt;g.v=-60*b.mV;drive=np.repeat([.078125,.015625],4);g.drive_amp=drive*b.volt
ex=b.Synapses(g,g,'w:volt',on_pre='ge_post+=w',delay=DT*b.second,name='exc');ex.connect(i=np.repeat([0,2],4),j=np.r_[np.arange(4,8),np.arange(4)]);ex.w=.0002*b.volt
inh=b.Synapses(g,g,'w:volt',on_pre='gi_post+=w',delay=DT*b.second,name='inh');inh.connect(i=[6]*4,j=np.arange(4));inh.w=.0003*b.volt
sm=b.SpikeMonitor(g,name='spikes');st=b.StateMonitor(g,['v','ge','gi'],record=True,when='end',name='states');b.Network(g,ex,inh,sm,st).run(.05*b.second,namespace={})
T=500;sp=np.zeros((T,8),np.uint8);sp[np.rint(np.asarray(sm.t)/DT).astype(int),np.asarray(sm.i)]=1;off=[0];ww=[];ch=[];ss=[]
for q in range(2):
 for n in range(T):
  if n:
   for src,w,c,s in ([(2,.0002,0,1),(6,.0003,1,-1)] if q==0 else [(0,.0002,0,-1)]):
    if sp[n-1,src]:ww.append(w);ch.append(c);ss.append(s)
  off.append(len(ww))
data=(T,np.array(off,np.int64),np.array(ch,np.uint8),np.array(ww),tau,th,np.tile(np.array([.078125,.015625]),(T,1)),sp);signs=np.array(ss,float)
bad,out,pre,eligible=replay.point(data,signs,trace=True);assert bad==-1,bad
actual=np.stack([np.asarray(st.v).T,np.asarray(st.ge).T,np.asarray(st.gi).T],axis=-1)
if not np.array_equal(out.view(np.uint64),actual.view(np.uint64)):
 ix=np.argwhere(out.view(np.uint64)!=actual.view(np.uint64));print('mismatch',ix[:8],[(out[tuple(x)],actual[tuple(x)]) for x in ix[:8]]);raise AssertionError('Atlas/replay mismatch')
checks=[]
for rho in [0,2**-20,2**-16,2**-12,2**-8,.01,.25]:
 bad,tr=replay.cert(data,signs,rho,trace=True);points=[]
 for alpha in [-rho,0,rho]:
  pb,pt,_,_=replay.point(data,signs,alpha,trace=True);points.append(pb)
  if bad<0:
   assert pb<0;rad=np.abs(tr[:,:,:,1])*rho+tr[:,:,:,2];assert np.all(pt>=np.nextafter(tr[:,:,:,0]-rad,-np.inf)) and np.all(pt<=np.nextafter(tr[:,:,:,0]+rad,np.inf))
 checks.append(dict(rho=rho,cert_first_failure=bad,point_first_failures=points))
np.savez_compressed(R/'preflight/eight-unit-data.npz',offset=data[1],channel=data[2],weight=data[3],tau=tau,theta=th,drive=data[6],spikes=sp,signs=signs,atlas_states=actual,pre=pre,eligible=eligible)
save(R/'preflight/replay-validation.json',dict(status='pass',end_state_words=actual.size,spikes=int(sp.sum()),checks=checks));print('Native Atlas vs independent C replay exact',actual.size,'states',int(sp.sum()),'spikes');print(checks)
