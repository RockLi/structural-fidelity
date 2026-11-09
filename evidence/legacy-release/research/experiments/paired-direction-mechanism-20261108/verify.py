#!/usr/bin/env python3
from pathlib import Path
import json,csv,hashlib
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
for name in ['pool-lock.json','scores.csv','selection-lock.csv','selection-lock.json','radii.csv','queries.csv','analysis.json','conditioned-vs-frozen.csv','failure-predictions.csv','input-reversals.csv','rank-concordance.csv','selection-transfer.csv']:
 assert (ROOT/'results'/name).read_bytes()==(ROOT/'repeat'/name).read_bytes(),name
assert read(ROOT/'results/code-sha256.json')==read(ROOT/'repeat/code-sha256.json')
first_summary=read(ROOT/'results/summary.json');repeat_summary=read(ROOT/'repeat/summary.json')
first_summary.pop('setup_seconds');repeat_summary.pop('setup_seconds')
assert first_summary==repeat_summary
for file,digest in read(ROOT/'results/code-sha256.json').items():assert sha(Path(file))==digest,file
assert read(ROOT/'validation.json')['status']=='pass'
verified={}
for dirname in ['finite-horizon-certificate-audit-20261108','finite-horizon-certificate-cost-20261108','finite-horizon-family-prototype-20261108']:
 b=ROOT.parent/dirname;m=read(b/'MANIFEST.json')
 for file,digest in m.items():assert sha(b/file)==digest,str(b/file)
 verified[dirname]=len(m)
m=read(BASE/'package-sha256.json')
for file,digest in m.items():assert sha(BASE/file)==digest,file
verified[BASE.name]=len(m)
report=dict(status='pass',all_nontiming_results_byte_identical=True,source_hashes_match=True,unchanged_prior_manifests=verified,conditions=read(ROOT/'results/summary.json')['directions_input_conditions'],queries=read(ROOT/'results/summary.json')['radius_queries'],no_manuscript_changes=True,no_new_full_network_runs=True)
(ROOT/'reproducibility.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
