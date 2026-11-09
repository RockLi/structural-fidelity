#!/usr/bin/env python3
"""Independent reductions from saved scores/radii and input immutability checks."""
from pathlib import Path
import csv,json,hashlib,collections,statistics,itertools,sys
import numpy as np
R=Path(__file__).resolve().parent;OLD=R.parent/'paired-direction-mechanism-20261108/results'
def read(p):return list(csv.DictReader(p.open()))
def main():
 checked=0
 for report in [R/'results/input-sha256.json',R/'dose/input-sha256.json']:
  for name,h in json.loads(report.read_text()).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name;checked+=1
 scores=read(R/'results/scores-factorial.csv');rad=read(OLD/'radii.csv');rm={(x['probe'],int(x['pair']),int(x['direction'])):x for x in rad}
 groups=collections.defaultdict(list)
 for x in scores:groups[x['probe'],int(x['pair'])].append(x)
 saved={(x['probe'],int(x['pair']),x['method']):x for x in read(R/'results/rank-by-target.csv')}
 methods=[k for k in scores[0] if k not in ['pair','probe','direction','eligible_target_slots']]
 checks=0;exacttie=[]
 for (u,i),rows in groups.items():
  rows=sorted(rows,key=lambda x:int(x['direction']));z=[rm[u,i,d] for d in range(16)];lo=np.array([float(x['lower']) for x in z]);hi=np.array([float(x['upper']) if x['upper'] else np.inf for x in z]);ia,ib=np.triu_indices(16,1)
  truth=(lo[ia]>hi[ib]).astype(int)-(lo[ib]>hi[ia]).astype(int);valid=truth!=0
  for m in methods:
   v=np.array([float(x[m]) for x in rows]);diff=v[ib]-v[ia];eps=1e-10*np.maximum(1,np.maximum(abs(v[ia]),abs(v[ib])));predict=np.where(abs(diff)<=eps,0,np.sign(diff));credit=np.where(predict==0,.5,(predict==truth).astype(float))
   s=saved[u,i,m];assert int(s['resolved'])==np.count_nonzero(valid)
   if valid.any():assert abs(float(s['concordance'])-np.mean(credit[valid]))<1e-14
   assert abs(float(s['known_credit'])-sum(credit[valid]))<1e-14
   lows=np.where(valid,credit,np.where(predict==0,.5,0));highs=np.where(valid,credit,np.where(predict==0,.5,1))
   assert abs(float(s['completion_lower'])-np.mean(lows))<1e-14
   assert abs(float(s['completion_upper'])-np.mean(highs))<1e-14;checks+=1
   if m.startswith('original'):
    strict=np.sign(diff);score=np.where(strict==0,.5,(strict==truth).astype(float))
    exacttie.append(dict(probe=u,pair=i,method=m,resolved=int(valid.sum()),tolerance_ties=int(np.count_nonzero((predict==0)&valid)),exact_ties=int(np.count_nonzero((strict==0)&valid)),exact_tie_concordance=None if not valid.any() else float(np.mean(score[valid]))))
 # Validate stratification by independent direct ratio comparisons.
 data=read(R/'results/pair-comparisons.csv');n=0
 for x in data:
  if not int(x['order']):continue
  a=rm[x['probe'],int(x['pair']),int(x['direction_a'])];b=rm[x['probe'],int(x['pair']),int(x['direction_b'])]
  safe,unsafe=(a,b) if int(x['order'])==1 else (b,a);g=float(safe['lower'])/float(unsafe['upper']);assert g>1 and g==float(x['ratio_lower']);n+=1
 with(R/'results/tie-rule-audit.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(exacttie[0]));w.writeheader();w.writerows(exacttie)
 # Scalar impulse filtering vs an independently constructed convolution for a selected
 # already stored reference. This recalculates scores only, never neuron trajectories.
 sys.path.insert(0,str(R.parent/'finite-horizon-certificate-audit-20261108'));import audit as a
 pools=json.loads((OLD/'pool-lock.json').read_text());ref=a.state('tonic');cache,_=a.reference_cache('tonic',ref,a.graph('original'));sm={(int(x['pair']),x['probe'],int(x['direction'])):x for x in scores};convchecks=0
 for i in [0,9,18]:
  fam=pools[i]
  for di in range(16):
   inp=np.zeros((2,300));mask=np.zeros((2,300),bool);margin=np.zeros((2,300))
   for j,k in enumerate(fam['targets']):
    # Matrix product grouping differs from the production source-ordered additions.
    coeff=np.zeros(125)
    for (src,target,bits),sign in zip(fam['edges'],fam['directions'][di]):
     if target==k:coeff[src]=float(np.array(bits,np.uint32).view(np.float32))*sign*(1 if src<100 else -1)
    inp[j,2:]=ref[:-2,:,0].astype(float)@coeff
    mask[j]=np.array(cache[k]['execute']) & np.r_[True,ref[:-1,k,8]<=np.arange(1,300)]
    margin[j]=np.maximum(abs(np.asarray(cache[k]['pre'],float)-30),2**-20)
   decay=float(a.d);kernel=(1-decay)*decay**np.arange(300);filtered=np.stack([np.convolve(x,kernel)[:300] for x in inp])
   for key,v in [('f0m0',abs(inp)),('f1m0',abs(filtered)),('f0m1',abs(inp)/margin),('f1m1',abs(filtered)/margin)]:
    expected=float(sm[i,'tonic',di]['original_'+key]);actual=float(v[mask].max());assert np.isclose(expected,actual,rtol=2e-12,atol=1e-10),(i,di,key,expected,actual);convchecks+=1
 d=json.loads((R/'dose/summary.json').read_text());assert d['all_prefixes_checked']==1920;assert d['training_variant_runs_hash_verified']==90
 complete=[x for x in read(R/'dose/candidate-availability.csv') if x['complete_chain']=='True'];assert len(complete)==10 and all(x['random_all_budgets']=='True' for x in complete)
 out=dict(status='pass',input_file_checks=checked,independent_rank_and_completion_checks=checks,independent_ratio_checks=n,convolution_score_checks=convchecks,exact_tie_sensitivity='results/tie-rule-audit.csv; diagnostic added after observed high tie counts, no new simulation',dose_complete_chains=10,manuscript_modified=False,new_simulations=0)
 (R/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
