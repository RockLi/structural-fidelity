from analysis_common import *
import datetime
import study
study.check();assert load(R/'network-complete.json')['status']=='pass';rows=[];choices=[]
for seed in SEEDS:
 pool=load(R/f'seed{seed}/pool-selected.json')
 for mode in MODES:
  for ui,u in enumerate(INPUTS):
   ref,cache=get_cache(seed,mode,u);counts=ref['spikes'].reshape(3000,C,U).sum(2).astype(float)
   for fam in pool:
    for T in HORIZONS:
     mean=counts[:T].copy();mean[:T-2]=mean[:T-2].mean(0);shuffled=counts[:T].copy();rng=np.random.Generator(np.random.PCG64(20261109+ui*10000+T));shifts=rng.integers(1,T-2,C)
     for j in range(C):shuffled[:T-2,j]=np.roll(shuffled[:T-2,j],int(shifts[j]))
     assert np.array_equal(shuffled.sum(0),counts[:T].sum(0));assert np.allclose(mean.sum(0),counts[:T].sum(0),rtol=0,atol=1e-8)
     for di in range(16):
      inp=impulse(fam,di,counts,T);sc=score(seed,mode,fam,inp,cache,ref['spikes'],T);mc=score(seed,mode,fam,impulse(fam,di,mean,T),cache,ref['spikes'],T)['joint'];sh=score(seed,mode,fam,impulse(fam,di,shuffled,T),cache,ref['spikes'],T)['joint'];targets=np.array([4*k+j for k in fam['targets'] for j in range(U)])
      rows.append(dict(seed=seed,mode=mode,input=u,pair=fam['pair'],steps=T,direction=di,**sc,mean=mc,shuffle=sh,projection_nonzero=bool(np.any(inp)),target_spikes=int(ref['spikes'][:T,targets].sum())))
   print('SCORES',seed,mode,u,flush=True)
for seed in SEEDS:
 for mode in MODES:
  for fam in load(R/f'seed{seed}/pool-selected.json'):
   for T in HORIZONS:
    z=[x for x in rows if x['seed']==seed and x['mode']==mode and x['pair']==fam['pair'] and x['steps']==T and x['input']=='G_B'];choices.append(dict(seed=seed,mode=mode,pair=fam['pair'],steps=T,random=0,**{k:min(z,key=lambda r:(r[k],r['direction']))['direction'] for k in ['joint','mean','shuffle','full','f0m0','f1m0','f0m1']}))
table(R/'directions/scores.csv',rows);table(R/'directions/selection.csv',choices)
files={str(p.relative_to(R)):sha(p) for p in list(R.glob('*.py'))+list(R.glob('*.c'))+[R/'local.dylib']+list((R/'directions').rglob('*')) if p.is_file()}
save(R/'score-lock.json',dict(locked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),radius_outcomes_seen=False,conditions=len(rows),files=files));assert len(rows)==4320;print('ALL SCORES LOCKED',len(rows),flush=True)
