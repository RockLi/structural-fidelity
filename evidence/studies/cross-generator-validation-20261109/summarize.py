from pathlib import Path
import csv,json,statistics,hashlib,collections,sys
import numpy as np
R=Path(__file__).resolve().parent;SEEDS=[201,202,203,301,302,303];INPUTS=['G_B','F_B','F_H','G_T','F_HT'];CONTRASTS=[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]
def load(p):return json.loads(p.read_text())
def read(p):return list(csv.DictReader(p.open()))
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def table(p,rows):
 with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
out=R/'analysis';out.mkdir(exist_ok=False);visibility=[];ranks=[];cover=[];cost=[];transfer=[];flip=[];factors=[];mechanism=[];frozen=[];env=[]
for seed in SEEDS:
 d=R/f'seed{seed}';assert load(d/'validation.json')['status']=='pass';anal=load(d/'directions/analysis.json')
 for x in read(d/'visibility-contrasts.csv'):visibility.append(dict(seed=seed,**x,switches=int(x['same/different'])+int(x['different/same']),total=19))
 for u in INPUTS:
  rr=[x for x in read(d/'directions/radii.csv') if x['probe']==u];vals=[float(x['lower']) for x in rr];witness=[x for x in read(d/'directions/coverage-witnesses.csv') if x['input']==u]
  cover.append(dict(seed=seed,input=u,n=len(rr),positive=sum(v>0 for v in vals),lower_min=min(vals),lower_median=statistics.median(vals),lower_max=max(vals),lower_ge_1pct=sum(v>=.01 for v in vals),distinct_weight_regions=sum(float(x['lower'])>0 and int(x['distinct_weight_vectors'])>1 for x in witness),distinct_event_regions=sum(float(x['lower'])>0 and int(x['distinct_event_streams'])>1 for x in witness),distinct_state_regions=sum(float(x['lower'])>0 and int(x['distinct_state_traces'])>1 for x in witness),**{s:sum(x['stop']==s for x in rr) for s in ['bracket_tolerance','proof_gap','cap_certified','cap_unresolved','refinement_limit']}))
 for x in anal['rank']:
  if x['subgroup']=='all':ranks.append(dict(seed=seed,**x))
 for x in anal['selection_transfer']:transfer.append(dict(seed=seed,**x))
 for x in anal['conditioned_vs_frozen']:frozen.append(dict(seed=seed,**x))
 for x in anal['reversals']:
  if x['method']=='temporal' and (x['input_a'],x['input_b']) in CONTRASTS:flip.append(dict(seed=seed,**x))
 for x in load(d/'directions/mechanistic-summary.json')['comparisons']:mechanism.append(dict(seed=seed,**x))
 for label in ['family_model_and_certificate','two_endpoints_generation_and_replay','25_points_generation_and_replay']:
  ts=[x for x in read(d/'directions/cost.csv') if x['method']==label];per=[]
  for key in sorted({(x['pair'],x['input']) for x in ts}):per.append(statistics.median(float(x['seconds']) for x in ts if (x['pair'],x['input'])==key))
  cost.append(dict(seed=seed,method=label,cases=len(per),median_ms=1000*statistics.median(per),min_ms=1000*min(per),max_ms=1000*max(per)))
 lookup={(x['probe'],x['method']):x['macro_concordance'] for x in anal['rank'] if x['subgroup']=='all'}
 for cmp in ['random','f1m0','f0m1','mean','shuffle']:
  vals=[None if lookup[u,'temporal'] is None or lookup[u,cmp] is None else lookup[u,'temporal']-lookup[u,cmp] for u in INPUTS]
  delta=None if any(x is None for x in vals) else statistics.mean(vals)
  factors.append(dict(seed=seed,comparator=cmp,equal_input_mean_delta=delta,positive=None if delta is None else delta>1e-12,**{u:v for u,v in zip(INPUTS,vals)}))
for name,rows in [('visibility',visibility),('rank',ranks),('coverage',cover),('cost',cost),('factor-deltas',factors),('same-direction-changes',mechanism),('frozen-scores',frozen)]:table(out/(name+'.csv'),rows)
visg=[]
for u,v in CONTRASTS:
 z=[x for x in visibility if x['input_a']==u and x['input_b']==v];visg.append(dict(input_a=u,input_b=v,counts={str(x['seed']):x['switches'] for x in z},graphs_with_switch=sum(x['switches']>0 for x in z),all_six_have_switch=all(x['switches']>0 for x in z)))
fg=[]
for cmp in ['random','f1m0','f0m1','mean','shuffle']:
 z=[x for x in factors if x['comparator']==cmp];fg.append(dict(comparator=cmp,deltas={str(x['seed']):x['equal_input_mean_delta'] for x in z},graphs_positive=sum(x['positive'] is True for x in z),consistent_all_six=all(x['positive'] is True for x in z)))
for path,h in load(R/'frozen-baseline.json').items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
family_gates={}
for label,seeds in [('module',[201,202,203]),('ring',[301,302,303])]:
 family_gates[label]=dict(visibility=[dict(input_a=u,input_b=v,all_three_have_switch=all(x['switches']>0 for x in visibility if x['seed'] in seeds and x['input_a']==u and x['input_b']==v)) for u,v in CONTRASTS],score=[dict(comparator=c,all_three_positive=all(x['positive'] is True for x in factors if x['seed'] in seeds and x['comparator']==c)) for c in ['random','f1m0','f0m1','mean','shuffle']])
report=dict(family_gates=family_gates,status='pass',new_original_graphs=SEEDS,scientific_network_conditions=600,technical_network_conditions=35,radius_conditions=sum(x['n'] for x in cover),visibility=visg,score_factor_gates=fg,coverage=cover,cost=cost,selection_transfer=transfer,conditioned_vs_frozen=frozen,cross_input_orders=flip,same_direction_input_changes=mechanism,frozen_preprint_unchanged=True,interpretation='Six prospectively fixed original graphs from two affinity-weighted graph generators with the unchanged synchronized kernel. Graphs are the replication units; within-graph swaps, inputs and direction pairs are dependent. No population inference, causal attribution or cross-model validation.')
write(out/'summary.json',report)
print(json.dumps(dict(status='pass',visibility=visg,factor_gates=fg,radius_conditions=report['radius_conditions']),indent=2))
