from common import *
from directions import context
import itertools,statistics,collections
orig,refs,caches,exts=context(ROOT/'runs');pool=load(ROOT/'pool-lock.json');scores=read(ROOT/'directions/scores.csv');radii=read(ROOT/'directions/radii.csv');S={(int(x['pair']),x['probe'],int(x['direction'])):x for x in scores};R={(int(x['pair']),x['probe'],int(x['direction'])):x for x in radii}
rows=[];changes=[]
for fam in pool:
 i=fam['pair']
 for u in INPUTS:
  margins=[]
  for k in fam['targets']:
   eligible=np.asarray(caches[u][k]['execute']) & np.r_[True,refs[u][:-1,k,8]<=np.arange(1,300)];margins.extend(abs(np.asarray(caches[u][k]['pre'],float)[eligible]-30))
  for di in range(16):
   s=S[i,u,di];rr=R[i,u,di];rows.append(dict(pair=i,input=u,direction=di,eligible_states=len(margins),margin_min=None if not margins else min(margins),margin_p10=None if not margins else float(np.quantile(margins,.1)),margin_median=None if not margins else float(np.median(margins)),raw_projection=float(s['f0m0']),filtered_projection=float(s['f1m0']),margin_only=float(s['f0m1']),joint=float(s['temporal']),full=float(s['full']),lower=float(rr['lower']),upper=None if rr['upper']=='' else float(rr['upper']),stop=rr['stop']))
 for u,v in CONTRASTS:
  for di in range(16):
   t=truth(R[i,u,di],R[i,v,di]);pr=pred(float(S[i,u,di]['temporal']),float(S[i,v,di]['temporal']));changes.append(dict(pair=i,input_a=u,input_b=v,direction=di,radius_order=t,joint_order=pr,resolved=bool(t),credit=None if not t else .5 if pr==0 else float(t==pr),J_a=float(S[i,u,di]['temporal']),J_b=float(S[i,v,di]['temporal'])))
table(ROOT/'directions/mechanistic-descriptors.csv',rows);table(ROOT/'directions/same-direction-input-changes.csv',changes)
write(ROOT/'directions/mechanistic-summary.json',dict(comparisons=[dict(input_a=u,input_b=v,resolved=sum(x['resolved'] for x in changes if x['input_a']==u and x['input_b']==v),total=len(pool)*16,concordance=None if not any(x['resolved'] for x in changes if x['input_a']==u and x['input_b']==v) else statistics.mean(x['credit'] for x in changes if x['input_a']==u and x['input_b']==v and x['resolved'])) for u,v in CONTRASTS],interpretation='Predeclared descriptive input-conditioned associations. No causal margin attribution; predictions share reference activity with certificates.'))
