#!/usr/bin/env python3
"""Offline factor ablation; never invokes a perturbed simulator or certifier."""
from pathlib import Path
import sys,json,csv,hashlib,itertools,collections,statistics,argparse,platform
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'paired-direction-mechanism-20261108'
sys.path.insert(0,str(ROOT.parent/'finite-horizon-certificate-audit-20261108'))
import audit as a
PROBES=['tonic','global_burst','focal_burst']
FACTORS=['f0m0','f1m0','f0m1','f1m1']
METHODS=[s+'_'+f for s in ['original','mean','shuffle'] for f in FACTORS]+['random','legacy_raw','full']
used={}
def use(p):
 p=Path(p);used[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return list(csv.DictReader(use(p).open()))
def load(p):return json.loads(use(p).read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def table(p,rows):
 if not rows:return
 with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def pred(x,y):return 0 if abs(x-y)<=1e-10*max(1,abs(x),abs(y)) else (1 if x<y else -1)
def outcome(x,y):
 if y['upper'] and float(x['lower'])>float(y['upper']):return 1
 if x['upper'] and float(y['lower'])>float(x['upper']):return -1
 return 0
def impulses(fam,di,sp):
 out=np.zeros((2,300),float)
 for (src,k,bits),sgn in zip(fam['edges'],fam['directions'][di]):
  w=float(np.array(bits,np.uint32).view(np.float32));out[fam['targets'].index(k),2:]+=w*sgn*sp[:-2,src]*(1 if src<100 else -1)
 return out
# Keep the exact original per-channel accumulation before subtraction.
def channel_projection(fam,di,sp):
 out=np.zeros((2,300,2),float)
 for (src,k,bits),sgn in zip(fam['edges'],fam['directions'][di]):
  w=float(np.array(bits,np.uint32).view(np.float32));out[fam['targets'].index(k),2:,int(src>=100)]+=w*sgn*sp[:-2,src]
 return out[:,:,0]-out[:,:,1]
def factors(x,mask,margin):
 z=np.zeros_like(x);d=float(a.d)
 for k in range(2):
  prev=0.
  for n in range(300):prev=d*prev+(1-d)*x[k,n];z[k,n]=prev
 v=[np.abs(x),np.abs(z),np.abs(x)/margin,np.abs(z)/margin]
 return {f:float(np.max(y[mask])) for f,y in zip(FACTORS,v)}
def ratio_bin(g):
 for top,label in [(1.1,'1-1.10'),(1.25,'1.10-1.25'),(1.5,'1.25-1.50'),(2,'1.50-2')]:
  if g<=top:return label
 return '>2'
def main():
 q=argparse.ArgumentParser();q.add_argument('--output-dir',type=Path,default=ROOT/'results');arg=q.parse_args();out=arg.output_dir;out.mkdir(exist_ok=False,parents=True)
 lock=load(ROOT/'protocol-lock.json');assert hashlib.sha256((ROOT/'PROTOCOL.txt').read_bytes()).hexdigest()==lock['sha256'];use(ROOT/'PROTOCOL.txt');use(Path(__file__));use(Path(a.__file__))
 pools=load(OLD/'results/pool-lock.json');R=read(OLD/'results/radii.csv');S=read(OLD/'results/scores.csv');prior=load(OLD/'results/analysis.json')
 rm={(int(r['pair']),r['probe'],int(r['direction'])):r for r in R};sm={(int(r['pair']),r['probe'],int(r['direction'])):r for r in S}
 use(a.E/'graphs/original.csv');orig=a.graph('original');scores=[];checks=0;reference_checks=0
 for ui,u in enumerate(PROBES):
  use(a.E/'runs'/f'original__{u}.npz');use(a.E/'runs'/f'original__{u}.csv')
  ref=a.state(u);cache,n=a.reference_cache(u,ref,orig);reference_checks+=n;sp=ref[:,:,0].astype(float)
  rng=np.random.default_rng(20261108+ui);shift=rng.integers(1,300,a.N)
  streams={'original':sp,'mean':np.broadcast_to(sp.mean(0),sp.shape),'shuffle':np.stack([np.roll(sp[:,j],int(shift[j])) for j in range(a.N)],axis=1)}
  for fam in pools:
   i=fam['pair'];targets=fam['targets'];mask=np.zeros((2,300),bool);margin=np.zeros((2,300),float)
   for ki,k in enumerate(targets):
    eligible=np.r_[True,ref[:-1,k,8]<=np.arange(1,300)]
    mask[ki]=np.array(cache[k]['execute']) & eligible
    margin[ki]=np.maximum(np.abs(np.array(cache[k]['pre'],float)-30),2**-20)
   assert mask.any()
   for di in range(16):
    row=dict(pair=i,probe=u,direction=di,eligible_target_slots=int(mask.sum()))
    old=sm[i,u,di]
    for src,stream in streams.items():
     x=channel_projection(fam,di,stream);f=factors(x,mask,margin)
     for k,v in f.items():row[src+'_'+k]=v
     oldkey={'original':'temporal','mean':'mean','shuffle':'shuffle'}[src]
     assert f['f1m1']==float(old[oldkey]),(i,u,di,src,f['f1m1'],old[oldkey]);checks+=1
     if src=='original':assert np.max(abs(x))==float(old['raw'])
    row.update(random=float(di),legacy_raw=float(old['raw']),full=float(old['full']))
    scores.append(row)
  print('scored',u,flush=True)
 table(out/'scores-factorial.csv',scores);sf={(s['pair'],s['probe'],s['direction']):s for s in scores}
 comparisons=[];covers=[];widths=[]
 for fam in pools:
  i=fam['pair']
  for u in PROBES:
   rr=[rm[i,u,d] for d in range(16)];unresolved=collections.Counter();resolved=0
   for r in rr:
    L=float(r['lower']);U=float(r['upper']) if r['upper'] else None
    widths.append(dict(pair=i,probe=u,direction=r['direction'],stop=r['stop'],lower=L,upper=U,relative_width=None if U is None else (U-L)/U))
   for di,dj in itertools.combinations(range(16),2):
    x,y=rr[di],rr[dj];t=outcome(x,y);g=None
    if t:
     hi,lo=(x,y) if t==1 else(y,x);g=float(hi['lower'])/float(lo['upper']);kind='resolved';resolved+=1
    elif x['stop']==y['stop']=='cap_certified':kind='both_capped'
    elif 'proof_gap' in (x['stop'],y['stop']):kind='proof_gap_overlap';unresolved[kind]+=1
    elif not x['upper'] or not y['upper']:kind='cap_overlap';unresolved[kind]+=1
    else:kind='finite_overlap';unresolved[kind]+=1
    if kind=='both_capped':unresolved[kind]+=1
    base=dict(pair=i,probe=u,direction_a=di,direction_b=dj,order=t,kind=kind,ratio_lower=g,ratio_bin=None if g is None else ratio_bin(g),bracket_class='one_capped' if not x['upper'] or not y['upper'] else 'two_finite')
    for m in METHODS:
     p=pred(sf[i,u,di][m],sf[i,u,dj][m]);credit=(.5 if p==0 else float(p==t)) if t else None
     comparisons.append(dict(**base,method=m,prediction=p,credit=credit))
   covers.append(dict(pair=i,probe=u,target_a=fam['targets'][0],target_b=fam['targets'][1],target_spike_slots=int(rr[0]['target_spike_slots']),resolved=resolved,total=120,coverage=resolved/120,cap_conditions=sum(r['stop']=='cap_certified' for r in rr),proof_gap_conditions=sum(r['stop']=='proof_gap' for r in rr),both_capped=unresolved['both_capped'],proof_gap_overlap=unresolved['proof_gap_overlap'],cap_overlap=unresolved['cap_overlap'],finite_overlap=unresolved['finite_overlap']))
 table(out/'pair-comparisons.csv',comparisons);table(out/'coverage-by-target.csv',covers);table(out/'bracket-widths.csv',widths)
 # Group without treating the direction pairs as independent replicates.
 grouped=collections.defaultdict(list)
 for c in comparisons:grouped[c['probe'],c['method'],c['pair']].append(c)
 ranks=[]
 for (u,m,i),z in grouped.items():
  good=[x for x in z if x['order']];un=[x for x in z if not x['order']];credit=sum(x['credit'] for x in good);ties=sum(x['prediction']==0 for x in good);uties=sum(x['prediction']==0 for x in un)
  ranks.append(dict(pair=i,probe=u,method=m,total=len(z),resolved=len(good),prediction_ties=ties,concordance=None if not good else credit/len(good),known_credit=credit,completion_lower=(credit+.5*uties)/len(z),completion_upper=(credit+.5*uties+len(un)-uties)/len(z)))
 table(out/'rank-by-target.csv',ranks)
 summary=[]
 for u in PROBES:
  for m in METHODS:
   z=[x for x in ranks if x['probe']==u and x['method']==m];good=[x for x in z if x['resolved']];n=sum(x['resolved'] for x in z)
   summary.append(dict(probe=u,method=m,targets_with_comparisons=len(good),resolved=n,total=2280,coverage=n/2280,macro=statistics.mean(x['concordance'] for x in good),micro=sum(x['known_credit'] for x in z)/n,prediction_ties=sum(x['prediction_ties'] for x in z),all_pair_completion_lower=statistics.mean(x['completion_lower'] for x in z),all_pair_completion_upper=statistics.mean(x['completion_upper'] for x in z)))
 table(out/'rank-summary.csv',summary)
 # Reproduce all six archived macro scores exactly (small mean-rounding tolerance).
 mapping={'random':'random','legacy_raw':'raw','mean_f1m1':'mean','shuffle_f1m1':'shuffle','original_f1m1':'temporal','full':'full'}
 for s in summary:
  if s['method'] not in mapping:continue
  old=next(x for x in prior['rank'] if x['probe']==s['probe'] and x['method']==mapping[s['method']] and x['subgroup']=='all')
  assert abs(s['macro']-old['macro_concordance'])<1e-14 and s['resolved']==old['resolved_direction_pairs']
 strat=[]
 for u in PROBES:
  for dimension,levels in [('ratio_bin',['1-1.10','1.10-1.25','1.25-1.50','1.50-2','>2']),('bracket_class',['two_finite','one_capped'])]:
   for level in levels:
    for m in METHODS:
     z=[x for x in comparisons if x['probe']==u and x['method']==m and x['order'] and x[dimension]==level];by=collections.defaultdict(list)
     for x in z:by[x['pair']].append(x['credit'])
     strat.append(dict(probe=u,dimension=dimension,level=level,method=m,n=len(z),targets=len(by),macro=None if not by else statistics.mean(statistics.mean(y) for y in by.values()),micro=None if not z else statistics.mean(x['credit'] for x in z),prediction_ties=sum(x['prediction']==0 for x in z)))
 table(out/'separation-strata.csv',strat)
 diffs=[];diffsummary=[];rmap={(r['pair'],r['probe'],r['method']):r['concordance'] for r in ranks}
 contrasts={'filter_without_margin':('f1m0','f0m0'),'margin_without_filter':('f0m1','f0m0'),'filter_with_margin':('f1m1','f0m1'),'margin_with_filter':('f1m1','f1m0')}
 for u in PROBES:
  for src in ['original','mean','shuffle']:
   for name,(hi,lo) in contrasts.items():
    vals=[]
    for i in range(19):
     x=rmap[i,u,src+'_'+hi];y=rmap[i,u,src+'_'+lo]
     if x is None:continue
     d=x-y;vals.append(d);diffs.append(dict(pair=i,probe=u,source=src,contrast=name,delta=d))
    diffsummary.append(dict(probe=u,source=src,contrast=name,targets=len(vals),mean=statistics.mean(vals),median=statistics.median(vals),wins=sum(v>1e-12 for v in vals),ties=sum(abs(v)<=1e-12 for v in vals),losses=sum(v< -1e-12 for v in vals)))
   vals=[]
   for i in range(19):
    z=[rmap[i,u,src+'_'+f] for f in FACTORS]
    if z[0] is None:continue
    d=z[3]-z[2]-z[1]+z[0];vals.append(d);diffs.append(dict(pair=i,probe=u,source=src,contrast='interaction',delta=d))
   diffsummary.append(dict(probe=u,source=src,contrast='interaction',targets=len(vals),mean=statistics.mean(vals),median=statistics.median(vals),wins=sum(v>1e-12 for v in vals),ties=sum(abs(v)<=1e-12 for v in vals),losses=sum(v< -1e-12 for v in vals)))
 table(out/'factor-differences-by-target.csv',diffs);table(out/'factor-differences.csv',diffsummary)
 transfer=[]
 for u in PROBES[1:]:
  for m in METHODS:
   for i in range(19):
    z=grouped[u,m,i];good=[x for x in z if x['order']]
    if not good:continue
    cc=[]
    for x in good:
     pr=pred(sf[i,'tonic',x['direction_a']][m],sf[i,'tonic',x['direction_b']][m]);cc.append(.5 if pr==0 else int(pr==x['order']))
    transfer.append(dict(pair=i,probe=u,method=m,n=len(good),frozen_tonic=statistics.mean(cc),conditioned=statistics.mean(x['credit'] for x in good)))
 table(out/'cross-input-by-target.csv',transfer)
 cross=[]
 for u in PROBES[1:]:
  for m in METHODS:
   z=[x for x in transfer if x['probe']==u and x['method']==m];cross.append(dict(probe=u,method=m,targets=len(z),frozen_tonic=statistics.mean(x['frozen_tonic'] for x in z),conditioned=statistics.mean(x['conditioned'] for x in z)))
 table(out/'cross-input-summary.csv',cross)
 report={'status':'pass','post_hoc':True,'new_simulations':0,'certificate_calls':0,'radius_refinements':0,'original_score_values_exact':checks,'reference_chunk_slots_reconstructed_and_checked':reference_checks,'archived_macros_reproduced':18,'score_rows':len(scores),'factorial_source_variants':12,'rank_summary':summary,'factor_differences_original':[x for x in diffsummary if x['source']=='original'],'coverage':[{**{k:sum(c[k] for c in covers if c['probe']==u) for k in ['resolved','total','both_capped','proof_gap_overlap','cap_overlap','finite_overlap']},'probe':u,'excluded_targets':[c for c in covers if c['probe']==u and not c['resolved']]} for u in PROBES],'scope':'Matched conditional rank comparisons on one graph. Ratio strata use certified lower bounds, not true radii. Completion ranges are loose sensitivity bounds, not confidence intervals. Source controls share the filter and margin. No mechanism or speedup claim.'}
 write(out/'summary.json',report);write(out/'input-sha256.json',used);write(out/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform()))
 print(json.dumps({k:report[k] for k in ['status','new_simulations','original_score_values_exact','reference_chunk_slots_reconstructed_and_checked','score_rows']},indent=2))
if __name__=='__main__':main()
