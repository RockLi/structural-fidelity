#!/usr/bin/env python3
"""Inventory/prefix check only. No simulation and no dose-response calculation."""
from pathlib import Path
import argparse,csv,json,hashlib,itertools,collections
import numpy as np
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review/evidence'
used={}
def use(p):
 p=Path(p);used[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def load(p):return json.loads(use(p).read_text())
def read(p):return list(csv.DictReader(use(p).open()))
def edges(p):return np.loadtxt(use(p),delimiter=',',skiprows=1,dtype=np.int64)
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def table(p,rows):
 with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 q=argparse.ArgumentParser();q.add_argument('--output-dir',type=Path,default=ROOT/'dose');args=q.parse_args();out=args.output_dir;out.mkdir(exist_ok=False,parents=True)
 use(Path(__file__));lock=load(ROOT/'protocol-lock.json');assert hashlib.sha256(use(ROOT/'PROTOCOL.txt').read_bytes()).hexdigest()==lock['sha256']
 big=BASE/'activity-guided-retention';small=BASE/'budget-boundary';B=['p01','p02','full'];paths={'p01':small,'p02':small,'full':big};counts={'p01':[14,6,6,2],'p02':[30,12,12,2],'full':[146,60,64,12]}
 cs=read(small/'candidates.csv');cb=read(big/'candidates.csv');candidate={}
 for b in B:
  for r in (cb if b=='full' else cs):
   if b!='full' and r['budget']!=b:continue
   candidate[b,int(r['block']),int(r['candidate'])]=r
 assert len(candidate)==1920
 aliases={b:load(paths[b]/'graph-aliases.json') for b in B}
 selections={b:[x for x in load(paths[b]/'selection.json') if b=='full' or x['budget']==b] for b in B}
 records={b:[x for x in load(paths[b]/('run-complete.json' if b=='full' else 'run-train-complete.json'))['records'] if x['probe']=='train' and x['graph']!='original' and (b=='full' or x['graph'].startswith(b+'_'))] for b in B}
 done={b:{r['graph']:r for r in records[b]} for b in B}
 original=edges(small/'inherited/original.csv');big_original=edges(big/'graphs/original.csv');assert np.array_equal(original,big_original)
 sp=load(small/'protocol.json');bp=load(big/'protocol.json');assert sp['inputs']['train']==bp['inputs']['train']
 assert use(small/'events/train.csv').read_bytes()==use(big/'events/train.csv').read_bytes()
 states={}
 for b in ['p01','full']:
  p=paths[b]/'runs/original__train.npz';states[b]=np.load(use(p))['state_bits'];assert states[b].shape==(300,125,10)
 assert np.array_equal(states['p01'],states['full'])
 old=BASE/'sensitivity/runs/original__focal_burst.npz';minref=np.load(use(old))['state_bits'];assert np.array_equal(minref,states['full'])
 verifiedruns=0;actualgraphs={}
 for b in B:
  for r in records[b]:
   for ext in ['npz','csv','json']:
    f=paths[b]/'runs'/(r['stem']+'.'+ext);use(f);assert hashlib.sha256(f.read_bytes()).hexdigest()==r[ext+'_sha256']
   arr=np.load(paths[b]/'runs'/(r['stem']+'.npz'))['state_bits'];assert arr.shape==(300,125,10);assert np.all(np.isin(arr[:,:,0],[0,100]));verifiedruns+=1
  actualgraphs[b]=len(records[b])
 seq=load(small/'prefix-sequences.json');prefix_checks=0;prefixrows=[]
 for item in seq:
  block=item['block'];ci=item['candidate']
  for b in B:
   expected=original.copy();ns=0
   for arm in item['sequence']:
    for change in arm['swaps'][:counts[b][arm['arm']]//2]:
     rows=change['rows'];assert list(expected[rows,2])==change['original_targets'];expected[rows,2]=change['new_targets'];ns+=1
   cr=candidate[b,block,ci];graph=cr['graph'];assert int(cr['seed'])==item['seed']
   real=edges(paths[b]/'graphs'/(graph+'.csv'));assert np.array_equal(real,expected),(b,block,ci)
   if b=='full':assert hashlib.sha256((big/'graphs'/(graph+'.csv')).read_bytes()).hexdigest()==item['full_sha256']
   changed=int(np.count_nonzero(real[:,2]!=original[:,2]));oldpairs=set(map(tuple,original[:,1:3]));newpairs=set(map(tuple,real[:,1:3]));assert len(oldpairs-newpairs)==changed==sum(counts[b]);assert ns==changed//2
   prefixrows.append(dict(budget=b,block=block,candidate=ci,seed=item['seed'],graph=graph,accepted_swaps=ns,replaced_original_adjacencies=changed,graph_sha256=hashlib.sha256((paths[b]/'graphs'/(graph+'.csv')).read_bytes()).hexdigest()))
   prefix_checks+=1
 table(out/'prefix-verification.csv',prefixrows)
 rows=[]
 for block in range(10):
  for ci in range(64):
   row=dict(block=block,candidate=ci,seed=int(candidate['full',block,ci]['seed']))
   for b in B:
    c=candidate[b,block,ci];g=c['graph'];canonical=aliases[b][g];policies=[x['policy'] for x in selections[b] if x['graph']==g]
    has=canonical in done[b];row.update({b+'_graph':g,b+'_canonical':canonical,b+'_policies':'|'.join(policies),b+'_available':has,b+'_run':done[b][canonical]['stem'] if has else ''})
   row['complete_chain']=all(row[b+'_available'] for b in B);row['random_all_budgets']=all('random' in row[b+'_policies'].split('|') for b in B)
   rows.append(row)
 table(out/'candidate-availability.csv',rows)
 intersections=[]
 for size in [2,3]:
  for subset in itertools.combinations(B,size):
   hits=[r for r in rows if all(r[b+'_available'] for b in subset)]
   random=[r for r in hits if all('random' in r[b+'_policies'].split('|') for b in subset)]
   intersections.append(dict(budgets='+'.join(subset),available_chains=len(hits),random_policy_chains=len(random),keys=[dict(block=r['block'],candidate=r['candidate'],seed=r['seed']) for r in hits]))
 membership=[]
 for policy in ['random','mean','coactivity','shuffled']:
  for block in range(10):
   chosen={b:next(x for x in selections[b] if x['block']==block and x['policy']==policy)['candidate'] for b in B}
   membership.append(dict(policy=policy,block=block,**chosen,same_chain_all=len(set(chosen.values()))==1))
 table(out/'policy-chain-pairing.csv',membership)
 avail=[dict(budget=b,replaced_adjacencies=sum(counts[b]),fraction=sum(counts[b])/2845,accepted_swaps=sum(counts[b])//2,candidate_seeds=640,selected_memberships=len(selections[b]),unique_completed_graphs=actualgraphs[b],candidate_seeds_with_available_alias=sum(r[b+'_available'] for r in rows),missing_candidate_seeds=sum(not r[b+'_available'] for r in rows)) for b in B]
 report=dict(status='pass',new_simulations=0,dose_response_calculated=False,all_prefixes_checked=prefix_checks,training_variant_runs_hash_verified=verifiedruns,common_training_event_bytes=True,common_original_state_bits=True,training_matches_archived_focal_reference_bits=True,budgets=avail,intersections=intersections,policy_complete_chains={pol:sum(r['policy']==pol and r['same_chain_all'] for r in membership) for pol in ['random','mean','coactivity','shuffled']},minimal_swap_bridge='Same focal input and original reference, but the 19 earlier single swaps use different candidate chains; they are not within-chain first-dose points. No trajectory is available for the first single-swap prefix of these chains.',limitations=['Only selected graph trajectories are archived; 640 candidates are not 640 completed simulations.','Complete random-policy chains, if available, support a small paired three-budget descriptive analysis under one known training input; they are not a dense dose curve or independent original networks.','Overlaps among score-selected chains are selection-conditioned; preserve memberships and do not count the same graph repeatedly.','Budgets 28/56/282 are replaced original adjacencies, equal here to 14/28/141 disjoint accepted swaps; they are not 28/56/282 swaps.'])
 write(out/'summary.json',report);write(out/'input-sha256.json',used)
 print(json.dumps({k:report[k] for k in ['status','all_prefixes_checked','training_variant_runs_hash_verified','budgets','policy_complete_chains']},indent=2));print('intersections',[(x['budgets'],x['available_chains'],x['random_policy_chains']) for x in intersections])
if __name__=='__main__':main()
