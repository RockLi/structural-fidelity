from pathlib import Path
import os,json,importlib.metadata as meta,hashlib
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import numpy as np
import brian2 as b
import brian2_atlas as atlas
R=Path(__file__).resolve().parent
b.set_device('atlas',engine='reference',directory=str(R/'preflight/toy'),numeric_mode='reference-f64')
b.defaultclock.dt=.1*b.ms
stim=b.TimedArray(np.tile(np.array([[.012,0,.012,0]]),(50,1))*b.volt,dt=.1*b.ms)
eqs='''dv/dt = (El + Ib + ge - gi + stim(t,i) - v)/tau : volt (unless refractory)
dge/dt = -ge/taue : volt
dgi/dt = -gi/taui : volt
tau : second (constant)
vth : volt (constant)'''
g=b.NeuronGroup(4,eqs,threshold='v >= vth',reset='v = Vr',refractory=2*b.ms,method='euler',namespace=dict(El=-65*b.mV,Ib=18*b.mV,Vr=-60*b.mV,taue=5*b.ms,taui=10*b.ms,stim=stim),name='cells')
g.v=-60*b.mV;g.tau=np.array([18,20,22,19])*b.ms;g.vth=np.array([-51,-50,-49,-50])*b.mV
s=b.Synapses(g,g,'w:volt',on_pre='ge_post += w',delay=.1*b.ms,name='exc');s.connect(i=[0,0,1,2],j=[1,2,2,3]);s.w=.2*b.mV
sm=b.SpikeMonitor(g,name='spikes');st=b.StateMonitor(g,['v','ge','gi','not_refractory','lastspike'],record=True,when='end',name='states')
b.Network(g,s,sm,st).run(5*b.ms)
np.savez(R/'preflight/toy.npz',v=np.asarray(st.v),ge=np.asarray(st.ge),gi=np.asarray(st.gi),nr=np.asarray(st.not_refractory),last=np.asarray(st.lastspike),t=np.asarray(st.t),sp_i=np.asarray(sm.i),sp_t=np.asarray(sm.t))
print('atlas',meta.version('brian2-atlas'),'last',st.v[:,-1], 'spikes',sm.num_spikes)
print('device',type(b.get_device()),b.get_device()._runner())
