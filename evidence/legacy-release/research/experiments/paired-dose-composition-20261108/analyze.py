#!/usr/bin/env python3
"""Read archived counts only; no simulator or certification modules are imported."""
from pathlib import Path
from fractions import Fraction as F
import argparse,csv,json,hashlib,itertools,collections,statistics,sys,platform
import numpy as np
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review/evidence'
AUDIT=ROOT.parent/'score-factor-coverage-audit-20261108'
BUDGETS=['p01','p02','full'];EDITS={'p01':28,'p02':56,'full':282};WIDTHS=[1,2,10,50,300]
used={}
def use(p):
 p=Path(p);used[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return list(csv.DictReader(use(p).open()))
def load(p):return json.loads(use(p).read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def table(p,rows):
 with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def desc(xs):
 vals=[float(x) for x in xs if x is not None]
 return dict(n=len(vals),mean=None if not vals else statistics.mean(vals),median=None if not vals else statistics.median(vals),minimum=None if not vals else min(vals),maximum=None if not vals else max(vals))
def sign(x):return 1 if x>1e-12 else -1 if x< -1e-12 else 0
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,default=ROOT/'results');args=ap.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=False)
 use(Path(__file__));lock=load(ROOT/'protocol-lock.json');assert hashlib.sha256(use(ROOT/'PROTOCOL.txt').read_bytes()).hexdigest()==lock['sha256']
 chainrows=read(AUDIT/'dose/candidate-availability.csv');chains=[x for x in chainrows if x['complete_chain']=='True' and x['random_all_budgets']=='True'];assert len(chains)==10 and {int(x['block']) for x in chains}==set(range(10))
 load(AUDIT/'dose/summary.json');prefix=read(AUDIT/'dose/prefix-verification.csv');pm={(x['budget'],x['graph']):x for x in prefix}
 paths={b:BASE/('activity-guided-retention' if b=='full' else 'budget-boundary') for b in BUDGETS}
 original={b:np.load(use(paths[b]/'runs/original__train.npz'))['state_bits'] for b in BUDGETS}
 assert all(np.array_equal(original['p01'],original[b]) for b in BUDGETS)
 for b in BUDGETS:
  assert use(paths[b]/'events/train.csv').read_bytes()==use(paths['p01']/'events/train.csv').read_bytes()
 ref=original['p01'][:,:,0].astype(np.int64);N=int(ref.sum());assert N>0 and ref.shape==(300,125)
 oldmetrics={b:{x['graph']:x for x in read(paths[b]/('analysis/per_graph.csv' if b=='full' else 'analysis-train/per_graph.csv')) if x['probe']=='train'} for b in BUDGETS}
 recorded={b:{x['stem']:x for x in load(paths[b]/('run-complete.json' if b=='full' else 'run-train-complete.json'))['records']} for b in BUDGETS}
 metrics=[];nodes=[];bins=[];binranges=[];scalarchecks=0;hashchecks=0
 for chain in chains:
  block=int(chain['block']);ci=int(chain['candidate']);seed=int(chain['seed'])
  for b in BUDGETS:
   graph=chain[b+'_graph'];canonical=chain[b+'_canonical'];stem=chain[b+'_run'];directory=paths[b]
   for ext in ['csv','npz','json']:
    p=use(directory/'runs'/(stem+'.'+ext));assert hashlib.sha256(p.read_bytes()).hexdigest()==recorded[b][stem][ext+'_sha256'];hashchecks+=1
   g=use(directory/'graphs'/(graph+'.csv'));assert hashlib.sha256(g.read_bytes()).hexdigest()==pm[b,graph]['graph_sha256'];assert int(pm[b,graph]['replaced_original_adjacencies'])==EDITS[b];hashchecks+=1
   data=np.load(directory/'runs'/(stem+'.npz'))['state_bits'];assert data.shape==(300,125,10);cnt=data[:,:,0].astype(np.int64);assert np.all(np.isin(cnt,[0,100]));delta=cnt-ref
   positive=np.maximum(delta,0).sum(0);negative=np.maximum(-delta,0).sum(0);slot=int(abs(delta).sum());count=int(abs(delta.sum(0)).sum());glob=abs(int(delta.sum()));pop=int(abs(delta.sum(1)).sum());cancel=slot-count;space=count-glob
   assert cancel==int(2*np.minimum(positive,negative).sum());assert slot==cancel+space+glob
   # Independent scalar summation for the complete window and 1ms bins.
   scount=sum(abs(sum(int(delta[t,k]) for t in range(300))) for k in range(125));sglob=abs(sum(int(delta[t,k]) for t in range(300) for k in range(125)));assert (scount,sglob)==(count,glob);scalarchecks+=2
   mismatch=np.flatnonzero(np.any(delta!=0,axis=1));r=None if slot==0 else count/slot
   row=dict(block=block,candidate=ci,seed=seed,budget=b,graph=graph,canonical=canonical,replaced_adjacencies=EDITS[b],edit_fraction=EDITS[b]/2845,accepted_swaps=EDITS[b]//2,reference_spikes=N,candidate_spikes=int(cnt.sum()),Dslot=slot,Dcount=count,Dglobal=glob,Dpopulation=pop,Ctime=cancel,Cspace=space,X=slot/N,Y=count/N,G=glob/N,T=cancel/N,S=space/N,Rcount=r,time_cancel_fraction=None if not slot else cancel/slot,space_cancel_fraction=None if not slot else space/slot,global_retained_fraction=None if not slot else glob/slot,changed_nodes=int(np.count_nonzero(positive+negative)),nodes_with_net_count_change=int(np.count_nonzero(positive-negative)),spikes_identical=not slot,recorded_bits_equal=bool(np.array_equal(data,original[b])),first_mismatch_slot=None if not len(mismatch) else int(mismatch[0]))
   old=oldmetrics[b][canonical]
   for k,oldk in [('Dslot','Dslot'),('Dcount','Dcount'),('Dglobal','Dglobal_cumulative'),('Dpopulation','Dpopulation_slot'),('candidate_spikes','candidate_spikes')]:assert row[k]==int(old[oldk]),(b,graph,k)
   for k,oldk in [('X','raw_slot_l1'),('Y','cumulative_l1'),('Rcount','Rcount')]:assert (not old[oldk] and row[k] is None) or (old[oldk] and row[k]==float(old[oldk]))
   metrics.append(row)
   for k in range(125):nodes.append(dict(block=block,budget=b,node=k,positive=int(positive[k]),negative=int(negative[k]),Dslot=int(positive[k]+negative[k]),Dcount=abs(int(positive[k]-negative[k])),Ctime=int(2*min(positive[k],negative[k]))))
   cs=np.concatenate([np.zeros((1,125),np.int64),delta.cumsum(0)])
   for w in WIDTHS:
    vals=[]
    for off in range(w):
     edges=sorted({0,300,*range(off,300,w)});chunks=cs[edges[1:]]-cs[edges[:-1]];error=int(abs(chunks).sum());assert count<=error<=slot
     if off==0 and w==1:assert error==slot
     if off==0 and w==300:assert error==count
     if off==0 and w==10:
      assert error==int(old['D1ms']);assert error==sum(abs(sum(int(delta[t,k]) for t in range(st,st+10))) for st in range(0,300,10) for k in range(125));scalarchecks+=1
     bins.append(dict(block=block,budget=b,width_slots=w,offset_slots=off,Dbin=error,normalized=error/N,retained_fraction=None if not slot else error/slot));vals.append(error)
    binranges.append(dict(block=block,budget=b,width_slots=w,offset_zero=vals[0]/N,offset_min=min(vals)/N,offset_max=max(vals)/N,offset_median=statistics.median(vals)/N,R_zero=None if not slot else vals[0]/slot,R_min=None if not slot else min(vals)/slot,R_max=None if not slot else max(vals)/slot))
 table(out/'per-chain.csv',metrics);table(out/'per-node.csv',nodes);table(out/'readout-offsets.csv',bins);table(out/'readout-ranges.csv',binranges)
 summaries=[]
 for b in BUDGETS:
  rows=[x for x in metrics if x['budget']==b]
  for metric in ['Dslot','Dcount','Dglobal','Ctime','Cspace','X','Y','G','T','S','Rcount','time_cancel_fraction','changed_nodes','nodes_with_net_count_change','first_mismatch_slot']:
   summaries.append(dict(budget=b,metric=metric,**desc([x[metric] for x in rows])))
 table(out/'budget-summary.csv',summaries)
 perbudget=[dict(budget=b,replaced_adjacencies=EDITS[b],n=10,zero_slot=sum(x['Dslot']==0 for x in metrics if x['budget']==b),zero_count=sum(x['Dcount']==0 for x in metrics if x['budget']==b),pooled_R=sum(x['Dcount'] for x in metrics if x['budget']==b)/sum(x['Dslot'] for x in metrics if x['budget']==b) if sum(x['Dslot'] for x in metrics if x['budget']==b) else None) for b in BUDGETS]
 m={(x['block'],x['budget']):x for x in metrics};paired=[];decomp=[];fractionchecks=0
 for b0,b1 in [('p01','p02'),('p02','full'),('p01','full')]:
  for block in range(10):
   x=m[block,b0];y=m[block,b1];base=dict(block=block,from_budget=b0,to_budget=b1)
   for metric in ['X','Y','G','T','Rcount','time_cancel_fraction','changed_nodes','nodes_with_net_count_change']:
    d=None if x[metric] is None or y[metric] is None else y[metric]-x[metric];paired.append(dict(**base,metric=metric,before=x[metric],after=y[metric],delta=d))
   dx=F(y['Dslot']-x['Dslot'],N);dy=F(y['Dcount']-x['Dcount'],N);dt=F(y['Ctime']-x['Ctime'],N);assert dy==dx-dt
   magnitude=composition=None
   if x['Dslot'] and y['Dslot']:
    rx=F(x['Dcount'],x['Dslot']);ry=F(y['Dcount'],y['Dslot']);magnitude=(rx+ry)/2*dx;composition=F(x['Dslot']+y['Dslot'],2*N)*(ry-rx);assert magnitude+composition==dy;fractionchecks+=1
   decomp.append(dict(**base,delta_X=float(dx),delta_Y=float(dy),delta_time_cancellation=float(dt),magnitude_component=None if magnitude is None else float(magnitude),retained_fraction_component=None if composition is None else float(composition),both_nonzero=magnitude is not None))
 table(out/'paired-changes.csv',paired);table(out/'paired-decomposition.csv',decomp)
 pairsummary=[];decsummary=[]
 for b0,b1 in [('p01','p02'),('p02','full'),('p01','full')]:
  for metric in ['X','Y','G','T','Rcount','time_cancel_fraction','changed_nodes','nodes_with_net_count_change']:
   rows=[x for x in paired if x['from_budget']==b0 and x['to_budget']==b1 and x['metric']==metric];vals=[x['delta'] for x in rows if x['delta'] is not None]
   pairsummary.append(dict(from_budget=b0,to_budget=b1,metric=metric,**desc(vals),increase=sum(sign(x)>0 for x in vals),tie=sum(sign(x)==0 for x in vals),decrease=sum(sign(x)<0 for x in vals)))
  good=[x for x in decomp if x['from_budget']==b0 and x['to_budget']==b1 and x['both_nonzero']]
  decsummary.append(dict(from_budget=b0,to_budget=b1,n=len(good),excluded_zero_boundaries=10-len(good),mean_delta_Y=statistics.mean(x['delta_Y'] for x in good) if good else None,mean_magnitude_component=statistics.mean(x['magnitude_component'] for x in good) if good else None,mean_retained_fraction_component=statistics.mean(x['retained_fraction_component'] for x in good) if good else None))
 table(out/'paired-summary.csv',pairsummary);table(out/'decomposition-summary.csv',decsummary)
 trends=[]
 for metric in ['X','Y','Rcount','T']:
  for block in range(10):
   vals=[m[block,b][metric] for b in BUDGETS]
   if any(x is None for x in vals):typ='undefined'
   else:
    signs=[sign(vals[1]-vals[0]),sign(vals[2]-vals[1])]
    typ='constant' if signs==[0,0] else 'nondecreasing' if min(signs)>=0 else 'nonincreasing' if max(signs)<=0 else 'nonmonotonic'
   trends.append(dict(block=block,metric=metric,p01=vals[0],p02=vals[1],full=vals[2],trend=typ))
 table(out/'chain-trends.csv',trends)
 report=dict(status='pass',post_hoc=True,new_simulations=0,reference_spikes=N,chain_count=10,trajectory_count=30,budgets=perbudget,summary=summaries,paired_summary=pairsummary,decomposition=decsummary,trends={metric:dict(collections.Counter(x['trend'] for x in trends if x['metric']==metric)) for metric in ['X','Y','Rcount','T']},validation=dict(run_and_graph_hash_checks=hashchecks,scalar_reductions=scalarchecks,exact_fraction_decompositions=fractionchecks,archived_endpoint_rows_matched=30,all_temporal_positive_negative_identities=True,all_readout_bounds=True),interpretation='Descriptive paired interventions in one graph and one input. Product decomposition is arithmetic, not a causal separation of edit quantity from edge identity or a universal dose law.')
 write(out/'summary.json',report);write(out/'input-sha256.json',used);write(out/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform()));print(json.dumps({k:report[k] for k in ['status','reference_spikes','budgets','decomposition','trends','validation']},indent=2))
if __name__=='__main__':main()
