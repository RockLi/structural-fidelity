import itertools,collections,statistics
from common import *
out=ROOT/'directions';rs=read(out/'radii.csv');ss=read(out/'scores.csv');R={(int(r['pair']),r['probe'],int(r['direction'])):r for r in rs};S={(int(r['pair']),r['probe'],int(r['direction'])):r for r in ss};methods=['f0m0','f1m0','f0m1','temporal','mean','shuffle','full','random'];rows=[];coverage=[];factors=[];summaries=[]
for u in INPUTS:
 for i in range(19):
  local=[]
  for di,dj in itertools.combinations(range(16),2):
   x,y=R[i,u,di],R[i,u,dj];t=truth(x,y)
   if not t:continue
   safer,less=(x,y) if t==1 else (y,x);ratio=float(safer['lower'])/float(less['upper']);b=next((name for bound,name in [(1.1,'1-1.1'),(1.25,'1.1-1.25'),(1.5,'1.25-1.5'),(2,'1.5-2')] if ratio<=bound),'>2')
   r=dict(pair=i,input=u,direction_a=di,direction_b=dj,truth=t,radius_ratio_lower=ratio,ratio_bin=b)
   for method in methods:
    z=pred(di,dj) if method=='random' else pred(float(S[i,u,di][method]),float(S[i,u,dj][method]));r[method]=.5 if z==0 else int(z==t)
   local.append(r);rows.append(r)
  z=[R[i,u,j] for j in range(16)];coverage.append(dict(pair=i,input=u,resolved=len(local),possible=120,coverage=len(local)/120,cap=sum(r['stop']=='cap_certified' for r in z),proof_gap=sum(r['stop']=='proof_gap' for r in z),silent=sum(int(r['target_spike_slots'])==0 for r in z),projection_null=sum(r['projection_nonzero']=='False' for r in z)))
  if local:
   avg={k:statistics.mean(r[k] for r in local) for k in methods};factors.append(dict(pair=i,input=u,resolved=len(local),**avg,filter_gain_no_margin=avg['f1m0']-avg['f0m0'],filter_gain_with_margin=avg['temporal']-avg['f0m1'],margin_gain_no_filter=avg['f0m1']-avg['f0m0'],margin_gain_with_filter=avg['temporal']-avg['f1m0']))
 for b in ['all','1-1.1','1.1-1.25','1.25-1.5','1.5-2','>2']:
  z=[r for r in rows if r['input']==u and (b=='all' or r['ratio_bin']==b)]
  for method in methods:
   per=[statistics.mean(r[method] for r in z if r['pair']==i) for i in range(19) if any(r['pair']==i for r in z)]
   summaries.append(dict(input=u,ratio_bin=b,method=method,n=len(z),targets=len(per),micro=None if not z else statistics.mean(r[method] for r in z),macro=None if not per else statistics.mean(per)))
table(out/'resolved-pairs.csv',rows);table(out/'coverage-by-target.csv',coverage);table(out/'factor-paired-differences.csv',factors);table(out/'ratio-strata.csv',summaries)
write(out/'detailed-summary.json',dict(coverage={u:dict(resolved=sum(r['resolved'] for r in coverage if r['input']==u),possible=2280,excluded_targets=[r['pair'] for r in coverage if r['input']==u and r['resolved']==0],stops=dict(collections.Counter(r['stop'] for r in rs if r['probe']==u))) for u in INPUTS},rank=[r for r in summaries if r['ratio_bin']=='all'],scope='Matched within-target comparisons; unresolved pairs excluded for every score equally; no independent-network uncertainty inferred.'))
