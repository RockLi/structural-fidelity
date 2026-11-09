#!/usr/bin/env python3
"""Compare repeated results and verify immutable prior audit and preprint."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'finite-horizon-certificate-audit-20261108'
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):return list(csv.DictReader(p.open()))
original={f"swap{r['seed']}__{r['probe']}":r for r in rows(OLD/'results/cases.csv')}
a=rows(ROOT/'results/cases.csv');b=rows(ROOT/'repeat/cases.csv')
keys=['certified','first_unresolved_slot','first_unresolved_chunk','reason','checked_chunk_slots','threshold_checks','visited_incoming_events','minimum_certified_slack']
assert len(a)==len(b)==len(original)==57
for x,y in zip(a,b):
 assert x['stem']==y['stem']
 for k in keys:assert x[k]==y[k]==original[x['stem']][k],(x['stem'],k)
 for k in ['category','replay_agrees','replay_steps','certificate_fallbacks']:assert x[k]==y[k]
s1=read(ROOT/'results/summary.json');s2=read(ROOT/'repeat/summary.json')
for k in ['endpoint_sha256','decision_sha256','exact_endpoint_values_compared','replay_state_bit_checks_before_global_spike_divergence']:assert s1[k]==s2[k],k
assert read(ROOT/'results/code-sha256.json')==read(ROOT/'repeat/code-sha256.json')
for file,digest in read(ROOT/'results/code-sha256.json').items():assert sha(Path(file))==digest,file
verified={}
for base,manifest in [(OLD,'MANIFEST.json'),(BASE,'package-sha256.json')]:
 expected=read(base/manifest)
 for file,digest in expected.items():assert sha(base/file)==digest,str(base/file)
 verified[str(base)]=dict(files=len(expected),manifest_sha256=sha(base/manifest))
report=dict(status='pass',all_57_archived_and_repeated_decisions_identical=True,endpoint_sha256=s1['endpoint_sha256'],decision_sha256=s1['decision_sha256'],source_hashes_match_both_runs=True,unchanged_manifests=verified,new_network_simulations=0,manuscript_edits=0)
(ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
