"""Independent vectorized reduction of existing score/radius outputs only."""
from pathlib import Path
import json,csv,itertools,statistics
import numpy as np
R=Path(__file__).resolve().parent;SEEDS=[201,202,203,301,302,303];inputs=['G_B','F_B','F_H','G_T','F_HT'];methods=['random','f0m0','f1m0','f0m1','mean','shuffle','temporal','full']
def read(p):return list(csv.DictReader(p.open()))
def load(p):return json.loads(p.read_text())
records=[]
for seed in SEEDS:
 d=R/f'seed{seed}/directions';rr=read(d/'radii.csv');ss=read(d/'scores.csv');j=load(d/'analysis.json');pool=load(d/'pool-lock.json');lookup={(r['probe'],r['method']):r for r in j['rank'] if r['subgroup']=='all'}
 for u in inputs:
  rates={m:[] for m in methods};total=0;possible=0
  for fam in pool:
   r=sorted((r for r in rr if int(r['pair'])==fam['pair'] and r['probe']==u),key=lambda z:int(z['direction']));s=sorted((s for s in ss if int(s['pair'])==fam['pair'] and s['probe']==u),key=lambda z:int(z['direction']));assert len(r)==len(s)==16
   lo=np.array([float(z['lower']) for z in r]);hi=np.array([float(z['upper']) if z['upper'] else np.inf for z in r]);a,b=np.triu_indices(16,1);truth=(lo[a]>hi[b]).astype(int)-(lo[b]>hi[a]).astype(int);mask=truth!=0;total+=int(mask.sum());possible+=len(a)
   for m in methods:
    scores=np.arange(16,dtype=float) if m=='random' else np.array([float(z[m]) for z in s]);ties=np.abs(scores[a]-scores[b])<=1e-10*np.maximum(1,np.maximum(np.abs(scores[a]),np.abs(scores[b])));pred=np.where(ties,0,np.sign(scores[b]-scores[a]));credit=np.where(ties,.5,pred==truth)
    if mask.any():rates[m].append(float(credit[mask].mean()))
  for m in methods:
   z=lookup[u,m];assert z['resolved_direction_pairs']==total and z['possible_direction_pairs']==possible and z['pairs_with_comparisons']==len(rates[m]);v=None if not rates[m] else statistics.mean(rates[m]);assert (v is None and z['macro_concordance'] is None) or abs(v-z['macro_concordance'])<1e-14
  records.append(dict(seed=seed,input=u,resolved=total,possible=possible,rank_methods_checked=len(methods)))
result=dict(status='pass',graph_input_cells=len(records),records=records,scope='Independent vectorized aggregation of existing data; no new simulations, score selection or acceptance threshold.')
(R/'independent-rank-audit.json').write_text(json.dumps(result,indent=2)+'\n');print('Independent rank audit passed:',len(records),'graph/input cells')
