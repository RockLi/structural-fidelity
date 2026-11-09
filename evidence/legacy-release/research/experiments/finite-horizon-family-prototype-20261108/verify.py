#!/usr/bin/env python3
import csv,json,hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):return list(csv.DictReader(p.open()))
fields=['stem','category','d','rho','method','passed','reason','target','slot','steps','thresholds','events','slack','grid_passes','grid_n','corner_passes','corner_n','distinct_weight_configs','distinct_event_streams']
x=rows(ROOT/'results/coverage.csv');y=rows(ROOT/'repeat/coverage.csv');assert len(x)==len(y)==1596
assert all(all(a[k]==b[k] for k in fields) for a,b in zip(x,y))
assert rows(ROOT/'results/samples.csv')==rows(ROOT/'repeat/samples.csv')
assert rows(ROOT/'results/singleton-regression.csv')==rows(ROOT/'repeat/singleton-regression.csv')
assert read(ROOT/'results/code-sha256.json')==read(ROOT/'repeat/code-sha256.json')
for file,digest in read(ROOT/'results/code-sha256.json').items():assert sha(Path(file))==digest,file
assert read(ROOT/'oracle-validation.json')['status']=='pass'
assert read(ROOT/'state-diversity.json')['status']=='pass'
verified={}
for base,name in [(ROOT.parent/'finite-horizon-certificate-audit-20261108','MANIFEST.json'),(ROOT.parent/'finite-horizon-certificate-cost-20261108','MANIFEST.json'),(BASE,'package-sha256.json')]:
 manifest=read(base/name)
 for file,digest in manifest.items():assert sha(base/file)==digest,str(base/file)
 verified[str(base)]=len(manifest)
report=dict(status='pass',repeated_coverage_records=1596,repeated_sample_records=len(rows(ROOT/'results/samples.csv')),all_nontiming_results_identical=True,original_manifests_unchanged=verified,prior_singleton_endpoint_values=read(ROOT/'results/summary.json')['singleton_interval_values'],oracle_endpoint_values=read(ROOT/'oracle-validation.json')['total_endpoint_values'],no_new_full_network_runs=True,no_manuscript_edits=True)
(ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
