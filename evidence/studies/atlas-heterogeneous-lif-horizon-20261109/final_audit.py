from analysis_common import *
from collections import Counter,defaultdict
import study,radii,importlib.metadata as metadata
study.check();radii.check_scores();assert metadata.version('brian2-atlas')=='0.2.0'
try:metadata.distribution('Brian2');raise AssertionError('upstream distribution installed')
except metadata.PackageNotFoundError:pass
assert sha(R/'PROTOCOL.txt')==load(R/'protocol-lock.json')['sha256']
for name in ['frozen-baseline.json','previous-study-manifests.json']:
 for p,h in load(R/name).items():assert sha(p)==h,p
# Inherited block graph invariants, exactly counted by node, arm and weight bits.
for seed in SEEDS:
 original=edges(seed)
 def stats(g):
  incoming=Counter((int(t),int(a),int(w)) for a,s,t,w,d in g);outgoing=Counter((int(s),int(a),int(w)) for a,s,t,w,d in g);return incoming,outgoing
 ref=stats(original);support={(int(s),int(t)) for a,s,t,w,d in original}
 for i in range(93001,93020):
  g=edges(seed,f'swap{i}');assert stats(g)==ref;assert np.all(g[:,4]==1)
  other={(int(s),int(t)) for a,s,t,w,d in g};assert len(support-other)==2 and len(other-support)==2
# Independently recompute all score pair orderings and macro means from source
# CSVs, including the censoring denominator and common comparison set.
rr=read(R/'directions/radii.csv');ss=read(R/'directions/scores.csv');raw={}
def key(x):return tuple(x[k] for k in ['seed','mode','input','pair','steps','direction'])
rad={key(x):x for x in rr};sco={key(x):x for x in ss};assert len(rad)==len(sco)==4320
for row in read(R/'analysis/resolved-pair-scores.csv'):
 a=tuple(row[k] for k in ['seed','mode','input','pair','steps'])+(row['larger_direction'],);b=a[:-1]+(row['smaller_direction'],)
 assert rad[b]['upper']!='' and float(rad[a]['lower'])>float(rad[b]['upper'])
 for k in ['f0m0','f1m0','f0m1','joint','full','mean','shuffle']:
  x=float(sco[a][k]);y=float(sco[b][k]);tol=1e-10*max(1.,abs(x),abs(y));score=.5 if abs(x-y)<=tol else int(x<y);assert float(row[k])==score
# Completeness of the resolved set, then independent macro aggregation.
import itertools
stored=read(R/'analysis/resolved-pair-scores.csv');stored_set={tuple(x[k] for k in ['seed','mode','input','pair','steps','larger_direction','smaller_direction']) for x in stored};expected_set=set();grouped=defaultdict(list)
for k,x in rad.items():grouped[k[:-1]].append(x)
for key,z in grouped.items():
 for x,y in itertools.combinations(z,2):
  if y['upper'] and float(x['lower'])>float(y['upper']):expected_set.add(key+(x['direction'],y['direction']))
  elif x['upper'] and float(y['lower'])>float(x['upper']):expected_set.add(key+(y['direction'],x['direction']))
assert expected_set==stored_set
for row in read(R/'analysis/score-macro.csv'):
 filt={k:row[k] for k in ['seed','mode','input','steps']};z=[x for x in stored if all(x[k]==v for k,v in filt.items())];assert len(z)==int(row['resolved']);assert abs(float(row['coverage'])-len(z)/360)<1e-15
 bypair=defaultdict(list)
 for x in z:bypair[x['pair']].append(x)
 assert len(bypair)==int(row['macro_target_pairs'])
 for method in ['f0m0','f1m0','f0m1','joint','full','mean','shuffle','GB_frozen','short_frozen']:
  if not z:assert row[method]=='';continue
  expected=sum(sum(float(x[method]) for x in a)/len(a) for a in bypair.values())/len(bypair);assert abs(float(row[method])-expected)<1e-14
assert load(R/'score-validation.json')['status']=='pass'
for seed in SEEDS:
 for mode in MODES:
  for u in INPUTS:
   folder=R/'runs'/f'seed{seed}_{mode}_{u}';done=load(folder/'complete.json');assert done['status']=='pass'
   for x in done['records']:assert sha(folder/(x['name']+'.npz'))==x['sha256']
   for name in ['reference-validation.json','region-validation.json']:assert load(R/'directions'/f'seed{seed}_{mode}_{u}'/name)['status']=='pass'
assert load(R/'atlas-region-validation.json')['status']=='pass'
# Exact equality is monotone with nested horizon for every saved swap trajectory.
er=read(R/'analysis/swap-errors.csv');groups=defaultdict(list)
for x in er:groups[x['seed'],x['mode'],x['input'],x['swap']].append(x)
for a in groups.values():
 a.sort(key=lambda x:int(x['steps']));assert [int(x['first_difference_slot'])>=0 for x in a]==sorted(int(x['first_difference_slot'])>=0 for x in a)
summary=dict(status='pass',atlas_distribution='brian2-atlas==0.2.0',upstream_brian2_distribution=False,protocol_hash_verified=True,design_and_score_locks_verified=True,frozen_manuscripts_and_old_packages_unchanged=True,statistically_matched_swap_graphs=57,scientific_network_runs=600,independent_prefix_and_repeat_runs=90,additional_preserved_partial_repeat=int((R/'preflight/initial-partial-scientific-F_H/original.npz').exists()),full_atlas_region_checks=load(R/'atlas-region-validation.json')['runs'],score_conditions=4320,independently_checked_resolved_orderings=len(read(R/'analysis/resolved-pair-scores.csv')),unit_changed_but_chunk_equal_readouts=sum(x['unit_equal']=='False' and x['chunk_equal']=='True' for x in er))
save(R/'FINAL-AUDIT.json',summary);print(json.dumps(summary,indent=2))
