#!/usr/bin/env python3
"""Post-hoc score-only sensitivity to the two-slot arrival-window boundary."""
import csv,json,itertools,statistics
import numpy as np
import mechanism as m
p=m.p;a=p.a;ROOT=m.ROOT;D=ROOT/'results';pools=json.loads((D/'pool-lock.json').read_text());R=a.csvread(D/'radii.csv');S=a.csvread(D/'scores.csv');C=a.csvread(D/'selection-lock.csv');rmap={(int(x['pair']),x['probe'],int(x['direction'])):x for x in R}
def truth(x,y):
 if y['upper'] and float(x['lower'])>float(y['upper']):return 1
 if x['upper'] and float(y['lower'])>float(x['upper']):return -1
 return 0
orig=a.graph('original');rows=[];boundary=[];rank=[];transfers=[]
for ui,u in enumerate(m.PROBES):
 ref=a.state(u);cache,_=a.reference_cache(u,ref,orig);sp=ref[:,:,0].astype(float)
 rng=np.random.default_rng(20261108+ui);oldshifts=rng.integers(1,300,a.N);old=np.stack([np.roll(sp[:,j],int(oldshifts[j])) for j in range(a.N)],axis=1)
 corrected_mean=sp.copy();corrected_mean[:298]=sp[:298].mean(axis=0)
 rng=np.random.default_rng(20261108+ui);shift=rng.integers(1,298,a.N);corrected_shuffle=sp.copy()
 for j in range(a.N):corrected_shuffle[:298,j]=np.roll(sp[:298,j],int(shift[j]))
 assert np.allclose(corrected_mean[:298].sum(0),sp[:298].sum(0),rtol=0,atol=1e-8)
 assert np.array_equal(corrected_shuffle[:298].sum(0),sp[:298].sum(0))
 delta=(old[:298].sum(0)-sp[:298].sum(0))/100
 boundary.append(dict(probe=u,old_shuffle_sources_with_changed_delivered_count=int(np.count_nonzero(delta)),old_shuffle_max_absolute_count_delta=float(np.max(np.abs(delta))),source_count=125))
 for fam in pools:
  for di in range(16):
   ms=m.simple_score(m.impulses(fam,di,corrected_mean),ref,cache,fam['targets'])[0]
   ss=m.simple_score(m.impulses(fam,di,corrected_shuffle),ref,cache,fam['targets'])[0]
   rows.append(dict(pair=fam['pair'],probe=u,direction=di,mean_window=ms,shuffle_window=ss))
mp={(x['pair'],x['probe'],x['direction']):x for x in rows}
for u in m.PROBES:
 for method in ['mean_window','shuffle_window']:
  vals=[];N=0
  for fam in pools:
   i=fam['pair'];n=correct=0
   for x,y in itertools.combinations(range(16),2):
    t=truth(rmap[i,u,x],rmap[i,u,y])
    if not t:continue
    sx,sy=mp[i,u,x][method],mp[i,u,y][method];pred=0 if abs(sx-sy)<=1e-10*max(1,abs(sx),abs(sy)) else 1 if sx<sy else -1
    n+=1;correct+=.5 if not pred else int(pred==t)
   if n:vals.append(correct/n);N+=n
  rank.append(dict(probe=u,method=method,pairs_with_comparisons=len(vals),macro_concordance=statistics.mean(vals),resolved_direction_pairs=N))
for fam in pools:
 train=[x for x in rows if x['pair']==fam['pair'] and x['probe']=='tonic'];sel=int(next(x for x in C if int(x['pair'])==fam['pair'])['temporal'])
 for method in ['mean_window','shuffle_window']:
  other=m.argmin(train,method)
  for u in m.PROBES:
   x,y=rmap[fam['pair'],u,sel],rmap[fam['pair'],u,other];t=truth(x,y)
   outcome='win' if t==1 else 'loss' if t==-1 else 'tie_same_direction' if sel==other else 'tie_at_cap' if x['stop']==y['stop']=='cap_certified' else 'unresolved'
   transfers.append(dict(pair=fam['pair'],probe=u,control=method,temporal_direction=sel,control_direction=other,outcome=outcome))
m.table(ROOT/'window-score-sensitivity.csv',rows);m.table(ROOT/'window-selection-sensitivity.csv',transfers)
a.write(ROOT/'window-sensitivity.json',dict(status='pass',post_hoc=True,new_direction_or_radius_runs=0,scope='Preserve source counts in slots0..297 that arrive in the300-slot window; keep last2source slots unchanged. Recompute scores/choices only, using already-fixed radius intervals. Does not replace original preregistered-in-session results.',old_boundary_effect=boundary,rank=rank))
print(json.dumps(rank,indent=2))
