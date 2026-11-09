# Post-run integrity checks; no model, score or selection changes.
from common import *
import network
network.check();old=read(ROOT.parent/'score-factor-coverage-audit-20261108/results/scores-factorial.csv');lookup={(int(r['pair']),r['probe'],int(r['direction'])):r for r in old};count=0
for r in read(ROOT/'directions/scores.csv'):
 if r['probe'] not in ['G_B','F_B']:continue
 z=lookup[int(r['pair']),'global_burst' if r['probe']=='G_B' else 'focal_burst',int(r['direction'])]
 for f in ['f0m0','f1m0','f0m1','f1m1']:assert float(r[f])==float(z['original_'+f]);count+=1
pool=load(ROOT/'pool-lock.json');groups=0;configs=0
for fam in pool:
 for t in [-.25,0,.25]:
  expected=None
  for v in fam['directions']:
   weights=[a.rn(a.q(np.array(bits,np.uint32).view(np.float32))*(a.F(1)+a.F(t)*int(s))) for (_,_,bits),s in zip(fam['edges'],v)]
   assert all(w>0 for w in weights)
   signature=[]
   for g in fam['groups']:assert sum(v[j] for j in g)==0;signature.append(tuple(sorted(int(weights[j].view(np.uint32)) for j in g)));groups+=1
   if expected is None:expected=signature
   assert signature==expected;configs+=1
prev=ROOT.parents[2]/'output/local-circuit-preprint-20261108-certified-directions';before=load(prev/'validation/final-fresh-lineage.json');docs={}
for lang in ['en','zh']:
 for ext in ['pdf','docx']:
  f=prev/'manuscript'/f'local-circuit-aggregation-preprint-{lang}.{ext}';h=sha(f);assert h==before['documents'][lang][ext+'_sha256'];docs[f.name]=h
write(ROOT/'integrity.json',dict(status='pass',factor_bridge_values_exact=count,matched_group_checks=groups,positive_weight_configurations=configs,manuscripts_unchanged=docs,design_lock='unchanged',note='Additional post-run integrity checks; experimental protocol unchanged.'))
