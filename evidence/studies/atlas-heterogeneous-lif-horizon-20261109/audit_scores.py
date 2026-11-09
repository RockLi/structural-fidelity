# Independent checks on fixed first pair/direction0 in every reference condition.
# Event-stream impulses and closed-form convolution, not the scoring recurrence.
from analysis_common import *
ss=read(R/'directions/scores.csv');checks=[]
for seed in SEEDS:
 for mode in MODES:
  for u in INPUTS:
   fam=load(R/f'seed{seed}/pool-selected.json')[0];ref,cache=get_cache(seed,mode,u);data,ids,neur=fast_stream(seed,mode,u,ref,fam['targets'],fam);sg=replay.signs(fam,0,ids);_,off,ch,w,tau,theta,drive,sp=data;ev=np.zeros((3000,2,2))
   for q in range(2):
    for n in range(2999):
     a,b=off[q*3000+n:q*3000+n+2]
     for channel in [0,1]:ev[n+1,q,channel]=np.sum((w[a:b]*sg[a:b])[ch[a:b]==channel])
   bad,aff=replay.cert(data,sg,0.,trace=True);assert bad<0
   deriv=np.zeros((3000,8));prior=np.zeros((8,3));h=DT/tau
   for n in range(3000):
    vv=(1-h)*prior[:,0]+h*(prior[:,1]-prior[:,2]);deriv[n]=np.where(cache['eligible'][n,neur],vv,prior[:,0]);prior=aff[n,:,:,1]
   projected=np.empty((3000,8));raw=np.repeat(ev[:,:,0]-ev[:,:,1],4,axis=1)*h
   for k in range(8):
    beta=1-h[k];t=np.arange(1,3001);total=np.zeros(3000)
    for channel,decay,sign in [(0,1-DT/.005,1),(1,1-DT/.010,-1)]:
     kernel=h[k]*(beta**t-decay**t)/(beta-decay);nfft=8192
     conv=np.fft.irfft(np.fft.rfft(ev[:,k//4,channel],nfft)*np.fft.rfft(kernel,nfft),nfft)[:3000];total+=sign*conv
    projected[:,k]=total
   for T in HORIZONS:
    mask=cache['eligible'][:T,neur].astype(bool);margin=np.maximum(abs(cache['pre'][:T,neur]-theta),2**-20)
    def mx(x):return float(np.max(x[mask])) if mask.any() else 0.
    expected=dict(f0m0=mx(abs(raw[:T])),f0m1=mx(abs(raw[:T])/margin),f1m0=mx(abs(projected[:T])),joint=mx(abs(projected[:T])/margin),full=mx(abs(deriv[:T])/margin))
    saved=next(x for x in ss if int(x['seed'])==seed and x['mode']==mode and x['input']==u and int(x['pair'])==fam['pair'] and int(x['steps'])==T and int(x['direction'])==0)
    for k,v in expected.items():assert np.isclose(v,float(saved[k]),rtol=2e-10,atol=1e-11),(seed,mode,u,T,k,v,saved[k])
    checks.append(dict(seed=seed,mode=mode,input=u,pair=fam['pair'],steps=T,direction=0,max_abs_difference=max(abs(v-float(saved[k])) for k,v in expected.items())))
table(R/'analysis/independent-score-audit.csv',checks);save(R/'score-validation.json',dict(status='pass',fixed_conditions=len(checks),scores_per_condition=5,max_abs_difference=max(x['max_abs_difference'] for x in checks),relative_tolerance=2e-10,absolute_tolerance=1e-11));print('SCORE AUDIT PASS',len(checks))
