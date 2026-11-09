#!/usr/bin/env python3
import csv,json,itertools,statistics,collections,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
q=argparse.ArgumentParser();q.add_argument('--results',type=Path,default=ROOT/'directions');args=q.parse_args();out=args.results

def read(name):return list(csv.DictReader((out/name).open()))
def write(name,x):(out/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def table(name,rs):
 with(out/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
R=read('radii.csv');S=read('scores.csv');C=read('selection-lock.csv')
rmap={(int(x['pair']),x['probe'],int(x['direction'])):x for x in R};smap={(int(x['pair']),x['probe'],int(x['direction'])):x for x in S};pools=json.loads((out/'pool-lock.json').read_text());probes=['G_B','F_B','F_H','G_T','F_HT'];methods=['random','f0m0','f1m0','f0m1','mean','shuffle','temporal','full']
def true_order(a,b):
 if b['upper'] and float(a['lower'])>float(b['upper']):return 1
 if a['upper'] and float(b['lower'])>float(a['upper']):return -1
 return 0

def score(x,method):return float(x['direction']) if method=='random' else float(x[method])
def pred_order(a,b,method):
 x,y=score(a,method),score(b,method)
 if abs(x-y)<=1e-10*max(1,abs(x),abs(y)):return 0
 return 1 if x<y else -1
rankrows=[];revrows=[];selrows=[];orderrows=[];failure=[]
for fam in pools:
 i=int(fam['pair']);N=len(fam['directions'])
 for u in probes:
  for subgroup in ['all','active_nonnull']:
   for m in methods:
    n=correct=ties=total=0
    for di,dj in itertools.combinations(range(N),2):
     a,b=rmap[i,u,di],rmap[i,u,dj]
     if subgroup=='active_nonnull' and (int(a['target_spike_slots'])==0 or a['projection_nonzero']!='True' or b['projection_nonzero']!='True'):continue
     total+=1;t=true_order(a,b)
     if not t:continue
     n+=1;p=pred_order(smap[i,u,di],smap[i,u,dj],m);correct+=int(t==p);ties+=int(p==0)
    rankrows.append(dict(pair=i,probe=u,subgroup=subgroup,method=m,possible_pairs=total,resolved_pairs=n,predicted_ties=ties,concordance=None if not n else (correct+.5*ties)/n))
  # Compare frozen G_B scores with input-conditioned predictions on target input.
  if u!='G_B':
   for m in ['mean','shuffle','temporal','full']:
    n=oldcorrect=newcorrect=0
    for di,dj in itertools.combinations(range(N),2):
     t=true_order(rmap[i,u,di],rmap[i,u,dj])
     if not t:continue
     n+=1
     for src in ['G_B',u]:
      v=pred_order(smap[i,src,di],smap[i,src,dj],m);v=.5 if v==0 else int(v==t)
      if src=='G_B':oldcorrect+=v
      else:newcorrect+=v
    orderrows.append(dict(pair=i,probe=u,method=m,resolved_pairs=n,frozen_G_B=None if not n else oldcorrect/n,input_conditioned=None if not n else newcorrect/n))
 for u,v in itertools.combinations(probes,2):
  nt=nr=0;counts={m:[0,0,0] for m in methods}
  for di,dj in itertools.combinations(range(N),2):
   a=true_order(rmap[i,u,di],rmap[i,u,dj]);b=true_order(rmap[i,v,di],rmap[i,v,dj])
   if not a or not b:continue
   nt+=1;rev=a!=b;nr+=rev
   for m in methods:
    pu=pred_order(smap[i,u,di],smap[i,u,dj],m);pv=pred_order(smap[i,v,di],smap[i,v,dj],m)
    if pu==0 or pv==0:counts[m][2]+=1;continue
    pr=pu!=pv
    if rev:counts[m][0]+=int(pr)
    else:counts[m][1]+=int(not pr)
  for m in methods:
   tp,tn,abstain=counts[m]
   revrows.append(dict(pair=i,input_a=u,input_b=v,method=m,resolved_both=nt,reversals=nr,reversal_fraction=None if not nt else nr/nt,correct_reversals=tp,correct_stable=tn,prediction_tie_abstentions=abstain))
for c in C:
 i=int(c['pair']);selected=int(c['temporal'])
 for u in probes:
  a=rmap[i,u,selected]
  for control in ['random','mean','shuffle']:
   other=int(c[control]);b=rmap[i,u,other];order=true_order(a,b)
   status='win' if order==1 else 'loss' if order==-1 else 'tie_same_direction' if selected==other else 'tie_at_cap' if a['stop']==b['stop']=='cap_certified' else 'unresolved'
   lo_ratio=float(a['lower'])/float(b['upper']) if b['upper'] else None
   hi_ratio=float(a['upper'])/float(b['lower']) if a['upper'] and float(b['lower'])>0 else None
   selrows.append(dict(pair=i,probe=u,control=control,temporal_direction=selected,control_direction=other,outcome=status,temporal_lower=float(a['lower']),temporal_upper=a['upper'],control_lower=float(b['lower']),control_upper=b['upper'],radius_ratio_lower=lo_ratio,radius_ratio_upper=hi_ratio))
for r in R:
 if not r['witness_slot']:continue
 s=smap[int(r['pair']),r['probe'],int(r['direction'])]
 for m in ['temporal','full']:
  failure.append(dict(pair=int(r['pair']),probe=r['probe'],direction=int(r['direction']),method=m,actual_reason=r['witness_reason'],target_match=s[m+'_target']==r['witness_target'],slot_abs_error=abs(int(s[m+'_slot'])-int(r['witness_slot'])),target_and_slot1=s[m+'_target']==r['witness_target'] and abs(int(s[m+'_slot'])-int(r['witness_slot']))<=1))
for name,rs in [('rank-concordance.csv',rankrows),('input-reversals.csv',revrows),('selection-transfer.csv',selrows),('conditioned-vs-frozen.csv',orderrows),('failure-predictions.csv',failure)]:table(name,rs)
ranksummary=[]
for u in probes:
 for sub in ['all','active_nonnull']:
  for m in methods:
   z=[x for x in rankrows if x['probe']==u and x['subgroup']==sub and x['method']==m and x['concordance'] is not None]
   ranksummary.append(dict(probe=u,subgroup=sub,method=m,pairs_with_comparisons=len(z),macro_concordance=None if not z else statistics.mean(x['concordance'] for x in z),resolved_direction_pairs=sum(x['resolved_pairs'] for x in z),possible_direction_pairs=sum(x['possible_pairs'] for x in rankrows if x['probe']==u and x['subgroup']==sub and x['method']==m)))
selectionsummary=[]
for u in probes:
 for c in ['random','mean','shuffle']:
  z=[x for x in selrows if x['probe']==u and x['control']==c];selectionsummary.append(dict(probe=u,control=c,counts=dict(collections.Counter(x['outcome'] for x in z))))
reversalsummary=[]
for u,v in itertools.combinations(probes,2):
 for m in methods:
  z=[x for x in revrows if x['input_a']==u and x['input_b']==v and x['method']==m]
  N=sum(x['resolved_both'] for x in z);rev=sum(x['reversals'] for x in z);TP=sum(x['correct_reversals'] for x in z);TN=sum(x['correct_stable'] for x in z)
  reversalsummary.append(dict(input_a=u,input_b=v,method=m,resolved_both=N,reversals=rev,pairs_with_reversal=sum(x['reversals']>0 for x in z),fraction=None if not N else rev/N,reversal_recall=None if not rev else TP/rev,stable_recall=None if N==rev else TN/(N-rev),abstentions=sum(x['prediction_tie_abstentions'] for x in z)))
conditioned=[]
for u in probes[1:]:
 for m in ['mean','shuffle','temporal','full']:
  z=[x for x in orderrows if x['probe']==u and x['method']==m and x['frozen_G_B'] is not None];conditioned.append(dict(probe=u,method=m,n_pairs=len(z),frozen_G_B=statistics.mean(x['frozen_G_B'] for x in z),input_conditioned=statistics.mean(x['input_conditioned'] for x in z)))
report=dict(status='pass',radii_stops=dict(collections.Counter(x['stop'] for x in R)),positive_certified_lower_bounds=sum(float(x['lower'])>0 for x in R),projection_null_conditions=sum(x['projection_nonzero']=='False' for x in R),silent_conditions=sum(int(x['target_spike_slots'])==0 for x in R),rank=ranksummary,selection_transfer=selectionsummary,reversals=reversalsummary,conditioned_vs_frozen=conditioned,selection_overlap={c:sum(x['temporal']==x[c] for x in C) for c in ['random','mean','shuffle']},failure_prediction={m:dict(n=sum(x['method']==m for x in failure),target_slot1=sum(x['method']==m and x['target_and_slot1'] for x in failure)) for m in ['temporal','full']},interpretation='Descriptive paired results on one original graph; correlated target pairs/directions are not independent networks. Full score shares exact conditional dynamics and is an algebraic ceiling, not independent discovery.')
write('analysis.json',report);print(json.dumps(report,indent=2))
