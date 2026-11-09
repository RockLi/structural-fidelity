#!/usr/bin/env python3
import csv,json,statistics,collections,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=ROOT/'results');args=p.parse_args();base=args.results
rows=list(csv.DictReader((base/'coverage.csv').open()));support=[x for x in rows if x['method']=='affine_support'];endpoint=[x for x in rows if x['method']=='certified_corner_envelope']
def key(x):return x['stem'],int(x['d']),float(x['rho'])
ep={key(x):x for x in endpoint};zero={x['stem']:x for x in csv.DictReader((base/'singleton-regression.csv').open())}
assert all(x['passed']==ep[key(x)]['passed'] and x['reason']==ep[key(x)]['reason'] and x['slot']==ep[key(x)]['slot'] and x['target']==ep[key(x)]['target'] for x in support)
assert all(all(x[k]==zero[x['stem']][k] for k in ['passed','reason','slot','target']) for x in support if float(x['rho'])==0)
curve=[];largest=[];costs={}
for d in [1,2]:
 ds=[x for x in support if int(x['d'])==d]
 for rho in sorted(set(float(x['rho']) for x in ds)):
  rr=[x for x in ds if float(x['rho'])==rho];rr17=[x for x in rr if x['category']=='input_changed_spikes_equal']
  curve.append(dict(d=d,rho=rho,relative_percent=100*rho,passed_all57=sum(x['passed']=='True' for x in rr),passed_target17=sum(x['passed']=='True' for x in rr17),cert_fail_sample_all_pass=sum(x['passed']=='False' and x['grid_passes']==x['grid_n'] for x in rr),cert_fail_corner_all_pass=sum(x['passed']=='False' and x['corner_passes']==x['corner_n'] for x in rr),failures=dict(collections.Counter(x['reason'] for x in rr if x['passed']=='False'))))
 chosen=[]
 for stem in sorted(set(x['stem'] for x in ds)):
  rr=sorted([x for x in ds if x['stem']==stem],key=lambda x:float(x['rho']));passing=[x for x in rr if x['passed']=='True'];mx=passing[-1] if passing else None
  larger=[x for x in rr if mx is not None and float(x['rho'])>float(mx['rho'])];first=larger[0] if larger else rr[0] if mx is None else None
  if mx:chosen.append(mx)
  largest.append(dict(stem=stem,category=rr[0]['category'],d=d,largest_tested_passing_rho=None if mx is None else float(mx['rho']),cap_reached=bool(mx and float(mx['rho'])==.25),distinct_weights=0 if mx is None else int(mx['distinct_weight_configs']),distinct_streams=0 if mx is None else int(mx['distinct_event_streams']),next_tested_failure_rho=None if first is None else float(first['rho']),failure_guard=None if first is None else first['reason'],failure_target=None if first is None else first['target'],failure_slot=None if first is None else first['slot']))
 for label,rr in [('all_certified',chosen),('nonzero_input_certified',[x for x in chosen if x['category']=='input_changed_spikes_equal'])]:
  vals=[]
  for x in rr:
   y=ep[key(x)];c=float(x['kernel_seconds']);end=float(y['kernel_seconds']);prep=float(x['model_prepare_seconds']);shared=float(x['shared_prepare_seconds']);graph=float(x['graph_io_seconds']);grid=float(x['grid_replay_generation_seconds']);cached=float(x['grid_cached_replay_seconds']);corner=float(x['corner_replay_seconds'])
   vals.append(dict(support_kernel_ms=c*1000,certified_corner_kernel_ms=end*1000,model_prepare_ms=prep*1000,support_compute_ms=(c+prep)*1000,certified_corner_compute_ms=(end+prep)*1000,plain_corner_compute_ms=corner*1000,grid_compute_ms=grid*1000,cached_grid_ms=cached*1000,support_with_commonprep_ms=(shared+c+prep)*1000,grid_with_commonprep_ms=(shared+grid)*1000,graph_io_ms=graph*1000,support_to_certified_corner_ratio=c/end,support_compute_to_grid_ratio=(c+prep)/grid))
  costs[f'd{d}_{label}']=dict(n=len(rr),aggregation='one largest passing tested region per graph/input; descriptive median',**{k:statistics.median(v[k] for v in vals) for k in vals[0]})
positive=[x for x in support if x['passed']=='True' and float(x['rho'])>0]
report=dict(status='pass',family_conditions=len(support),rigorous_methods_agree_on_all_outcomes=True,zero_radius_matches_prior_guards=True,positive_certified_conditions=len(positive),positive_certificates_all_nontrivial=all(int(x['distinct_weight_configs'])>1 and int(x['distinct_event_streams'])>1 for x in positive),curve=curve,costs=costs,interpretation='A failed whole-box certificate is not automatically a counterexample; on this fixed grid every failed box also has at least one failing actual corner. Point failures concern common branch fidelity. No claim of maximal radius or speed advantage over sampling with identical guarantees.')
(base/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
with (base/'largest-regions.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(largest[0]));w.writeheader();w.writerows(largest)
print(json.dumps(report,indent=2))
