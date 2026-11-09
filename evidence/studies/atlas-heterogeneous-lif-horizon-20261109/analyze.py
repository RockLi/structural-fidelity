from analysis_common import *
from collections import Counter,defaultdict
import itertools
A=R/'analysis';A.mkdir(exist_ok=True)
CONTRASTS=[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]

def network_analysis():
 activity=[];errors=[];switches=[];equality={}
 for seed in SEEDS:
  for mode in MODES:
   for u in INPUTS:
    ref=reference(seed,mode,u);s=ref['spikes'].astype(np.int64);chunk=s.reshape(3000,C,U).sum(2)
    for T in HORIZONS:
     heterochunks=sum(not np.all(s[:T,4*k:4*k+4]==s[:T,4*k:4*k+1]) for k in range(C))
     activity.append(dict(seed=seed,mode=mode,input=u,steps=T,total_spikes=int(s[:T].sum()),active_units=int(np.count_nonzero(s[:T].sum(0))),rate_hz=float(s[:T].sum()/(N*T*DT)),chunks_with_unequal_unit_spike_trains=heterochunks,voltage_min=float(ref['v'][:T].min()),voltage_max=float(ref['v'][:T].max()),last_100ms_spikes=int(s[2000:].sum()) if T==3000 else '',cycle_spikes=' '.join(str(int(s[n:min(n+300,T)].sum())) for n in range(0,T,300))))
    for name in [f'swap{x}' for x in range(93001,93020)]:
     z=np.load(R/'runs'/f'seed{seed}_{mode}_{u}'/f'{name}.npz')['spikes'].astype(np.int64);delta=z-s;cd=delta.reshape(3000,C,U).sum(2)
     for T in HORIZONS:
      diff=delta[:T];num=int(abs(diff).sum());den=int(s[:T].sum());count=int(abs(diff.sum(0)).sum());cnum=int(abs(cd[:T]).sum());first=np.argwhere(diff)
      errors.append(dict(seed=seed,mode=mode,input=u,swap=name,steps=T,unit_slot_numerator=num,reference_spikes=den,unit_Dslot=num/den if den else '',unit_Dcount=count/den if den else '',unit_count_retention=count/num if num else '',chunk_slot_numerator=cnum,chunk_Dslot=cnum/den if den else '',unit_equal=num==0,chunk_equal=cnum==0,first_difference_slot=-1 if not len(first) else int(first[0,0])))
      equality[(seed,mode,u,name,T)]=(num==0,cnum==0)
   for T in HORIZONS:
    for x,y in CONTRASTS:
     for level in [0,1]:
      pairs=[(equality[(seed,mode,x,f'swap{i}',T)][level],equality[(seed,mode,y,f'swap{i}',T)][level]) for i in range(93001,93020)]
      cnt=Counter(pairs);switches.append(dict(seed=seed,mode=mode,steps=T,contrast=x+'/'+y,readout='unit' if level==0 else 'chunk',both_equal=cnt[True,True],first_equal_only=cnt[True,False],second_equal_only=cnt[False,True],both_different=cnt[False,False],switches=cnt[True,False]+cnt[False,True],controls=19))
 table(A/'activity.csv',activity);table(A/'swap-errors.csv',errors);table(A/'visibility-switches.csv',switches)
 save(A/'network-summary.json',dict(scientific_trajectories=600,readouts=len(errors),activity_rows=len(activity),switch_rows=len(switches)))

def numrow(r):
 for k in ['seed','pair','steps','direction']:r[k]=int(r[k])
 for k in ['lower','upper']:r[k]=float(r[k]) if r[k]!='' else None
 return r

def direction_analysis():
 rr=[numrow(x) for x in read(R/'directions/radii.csv')];sc=read(R/'directions/scores.csv');scores={}
 methods=['f0m0','f1m0','f0m1','joint','full','mean','shuffle']
 for x in sc:
  key=(int(x['seed']),x['mode'],x['input'],int(x['pair']),int(x['steps']),int(x['direction']));scores[key]={k:float(x[k]) for k in methods};scores[key]['target_spikes']=int(x['target_spikes'])
 groups=defaultdict(list)
 for x in rr:groups[x['seed'],x['mode'],x['input'],x['pair'],x['steps']].append(x)
 pairrows=[];coverage=[];selection=[];region=[]
 def credit(a,b):
  tol=1e-10*max(1.,abs(a),abs(b));return .5 if abs(a-b)<=tol else float(a<b)
 def relation(a,b):
  if a['direction']==b['direction']:return 'same_direction'
  if b['upper'] is not None and a['lower']>b['upper']:return 'win'
  if a['upper'] is not None and b['lower']>a['upper']:return 'loss'
  return 'unresolved'
 for key,z in groups.items():
  seed,mode,u,pair,T=key;ids=dict(seed=seed,mode=mode,input=u,pair=pair,steps=T);n=0
  for a,b in itertools.combinations(z,2):
   if b['upper'] is not None and a['lower']>b['upper']:large,small=a,b
   elif a['upper'] is not None and b['lower']>a['upper']:large,small=b,a
   else:continue
   n+=1;li=large['direction'];si=small['direction'];s1=scores[(*key,li)];s2=scores[(*key,si)];ratio=large['lower']/small['upper']
   row=dict(**ids,larger_direction=li,smaller_direction=si,separation_ratio_lower=ratio,separation_bin='1-1.25' if ratio<1.25 else '1.25-2' if ratio<2 else '2+',**{k:credit(s1[k],s2[k]) for k in methods})
   for label,inp,horizon in [('GB_frozen','G_B',T),('short_frozen',u,300)]:
    sa=scores[seed,mode,inp,pair,horizon,li]['joint'];sb=scores[seed,mode,inp,pair,horizon,si]['joint'];row[label]=credit(sa,sb)
   pairrows.append(row)
  coverage.append(dict(**ids,resolved=n,possible=120,coverage=n/120,target_spikes=scores[(*key,0)]['target_spikes']))
  lows=[x['lower'] for x in z];cnt=Counter(x['status'] for x in z)
  region.append(dict(**ids,conditions=len(z),positive=sum(v>0 for v in lows),lower_min=min(lows),lower_median=float(np.median(lows)),lower_max=max(lows),**{k:cnt[k] for k in ['tolerance','cap','proof_gap','zero_guard','iteration_limit']}))
  selected={method:min(range(16),key=lambda d:(scores[seed,mode,'G_B',pair,T,d][method],d)) for method in methods};selected['random']=0;refsel=next(a for a in z if a['direction']==selected['joint'])
  for method in ['random','mean','shuffle']:
   other=next(a for a in z if a['direction']==selected[method]);selection.append(dict(**ids,comparator=method,GB_joint_direction=selected['joint'],GB_comparator_direction=selected[method],relation=relation(refsel,other),certified_lower_difference=refsel['lower']-other['lower']))
 table(A/'resolved-pair-scores.csv',pairrows);table(A/'ranking-coverage.csv',coverage);table(A/'region-summary.csv',region);table(A/'GB-selection-transfer.csv',selection)
 # Macro over selected target pairs within each graph/input/horizon. Missing
 # resolved pairs stay absent from accuracy, and present in coverage denominator.
 macro=[]
 for seed in SEEDS:
  for mode in MODES:
   for u in INPUTS:
    for T in HORIZONS:
     groupscov=[x for x in coverage if (x['seed'],x['mode'],x['input'],x['steps'])==(seed,mode,u,T)];ids=dict(seed=seed,mode=mode,input=u,steps=T);per=[]
     for cv in groupscov:
      p=[x for x in pairrows if (x['seed'],x['mode'],x['input'],x['steps'],x['pair'])==(seed,mode,u,T,cv['pair'])]
      if p:per.append({k:float(np.mean([x[k] for x in p])) for k in methods+['GB_frozen','short_frozen']})
     macro.append(dict(**ids,macro_target_pairs=len(per),resolved=sum(x['resolved'] for x in groupscov),possible=360,coverage=sum(x['resolved'] for x in groupscov)/360,**{k:float(np.mean([x[k] for x in per])) if per else '' for k in methods+['GB_frozen','short_frozen']}))
 table(A/'score-macro.csv',macro)
 # Prefix monotonicity of observed lower bounds is diagnostic, not a proof of
 # exact maximal-safe radii. Replay first-divergence upper witnesses are separate.
 nested=[]
 by=defaultdict(dict)
 for r in rr:by[r['seed'],r['mode'],r['input'],r['pair'],r['direction']][r['steps']]=r
 for key,z in by.items():
  nested.append(dict(zip(['seed','mode','input','pair','direction'],key),lower30=z[300]['lower'],lower100=z[1000]['lower'],lower300=z[3000]['lower'],lower_nonincreasing=z[300]['lower']>=z[1000]['lower']>=z[3000]['lower'],upper30=z[300]['upper'] if z[300]['upper'] is not None else '',upper100=z[1000]['upper'] if z[1000]['upper'] is not None else '',upper300=z[3000]['upper'] if z[3000]['upper'] is not None else ''))
 table(A/'nested-radii.csv',nested)
 save(A/'direction-summary.json',dict(conditions=len(rr),positive=sum(x['lower']>0 for x in rr),statuses=dict(Counter(x['status'] for x in rr)),resolved_pairs=len(pairrows),possible_pairs=len(groups)*120,lower_nonincreasing=sum(x['lower_nonincreasing'] for x in nested),nested_direction_families=len(nested)))

if __name__=='__main__':
 import sys
 globals()[sys.argv[1]]()
