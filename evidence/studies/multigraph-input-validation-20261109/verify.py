from pathlib import Path
import hashlib,json,csv,collections,os,sys
R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
read=lambda p:list(csv.DictReader(p.open()))
lock=load(R/'design-lock.json')
for n,h in lock['files'].items():assert sha(R/n)==h,n
for n,h in load(R/'dependencies.json').items():assert sha(Path(n))==h,n
for n,h in load(R/'all-score-lock.json')['files'].items():assert sha(R/n)==h,n
for n,h in load(R/'frozen-baseline.json').items():assert sha(Path(n))==h,n
assert sha(R/'PROTOCOL.txt')==load(R/'protocol-lock.json')['sha256']
assert load(R/'independent-network-audit.json')['status']=='pass'
summary=load(R/'analysis/summary.json');graphs=[]
for seed in [100,101,102]:
 d=R/f'seed{seed}';rr=read(d/'directions/radii.csv');qs=read(d/'directions/queries.csv');scores=read(d/'directions/scores.csv');pool=load(d/'pool-lock.json');N=len(pool)*16*5
 assert len(rr)==len(scores)==N;assert len({(x['pair'],x['probe'],x['direction']) for x in rr})==N
 assert load(d/'validation.json')['intervals']==N
 for rec in load(d/'network-complete.json')['records']:assert sha(d/'runs'/(rec['stem']+'.npz'))==rec['sha256']
 lookup={(x['pair'],x['probe'],x['direction']):x for x in rr}
 for q in qs:
  assert not(q['certified']=='True' and q['witness']=='True')
 for row in rr:
  lo=float(row['lower']);hi=float(row['upper']) if row['upper'] else None;assert 0<=lo<=.25 and (hi is None or lo<hi<=.25)
  local=[q for q in qs if (q['pair'],q['probe'],q['direction'])==(row['pair'],row['probe'],row['direction'])]
  if lo>0:assert any(float(q['rho'])==lo and q['certified']=='True' for q in local)
  if hi is not None:assert any(float(q['rho'])==hi and q['witness']=='True' for q in local)
  if row['stop']=='bracket_tolerance':assert hi-lo<=max(2**-20,.05*hi)
  if row['stop']=='cap_certified':assert lo==.25 and hi is None
 graphs.append(dict(seed=seed,conditions=N,queries=len(qs),stops=dict(collections.Counter(x['stop'] for x in rr))))
assert sum(x['conditions'] for x in graphs)==4400;assert sum(x['queries'] for x in graphs)==44502
out=dict(status='pass',graphs=graphs,protocol_design_score_dependency_locks='pass',frozen_preprint_unchanged=True,lower_and_upper_provenance='pass',scope='Post-run integrity and reduction verification only; does not alter scientific settings or add cases.')
(R/'verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
