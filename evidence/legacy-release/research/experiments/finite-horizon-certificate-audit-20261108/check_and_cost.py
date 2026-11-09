#!/usr/bin/env python3
"""Independent arithmetic checks and reference-driven local-work timing (no network runs)."""
import audit as a
import numpy as np,csv,json,time,statistics,itertools
from pathlib import Path
F=a.F
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=a.ROOT/'checks');args=parser.parse_args()
out=args.output_dir;out.mkdir(exist_ok=False)
# Test interval arithmetic independently using explicit binary32 primitive operations.
checks=0
values=[-5500.,-65.,-1e-35,0.,29.999,30.,30.001,100.,5000.]
for v in values:
 for ge in [0.,1e-35,.1,30.,150.,10000.]:
  for gi in [0.,.3,140.,5500.]:
   vv=np.float32(v);ee=np.float32(ge);ii=np.float32(gi)
   vi=(a.q(np.nextafter(vv,np.float32(-np.inf))),a.q(np.nextafter(vv,np.float32(np.inf))))
   ei=(max(F(0),a.q(np.nextafter(ee,np.float32(-np.inf)))),a.q(np.nextafter(ee,np.float32(np.inf))))
   ij=(max(F(0),a.q(np.nextafter(ii,np.float32(-np.inf)))),a.q(np.nextafter(ii,np.float32(np.inf))))
   bound=a.voltage(vi,ei,ij)
   for x,y,z in itertools.product(vi,ei,ij):
    x,y,z=map(np.float32,(x,y,z));syn=np.float32(y-z);pre=np.float32(x+np.float32(np.float32(-x+syn)*np.float32(.1)))
    assert bound[0]<=a.q(pre)<=bound[1];checks+=1
for initial in [0.,1e-35,.1,150.,10000.]:
 for n in [0,1,2,10,100,1000]:
  terms=[np.float32(60 if i%2 else .0001) for i in range(n)]
  bound=a.accumulate((a.q(initial),a.q(initial)),terms,np.float32(123.45))
  x=np.float32(initial)
  for term in terms:x=np.float32(x+term)
  x=np.float32(x+np.float32(np.float32(123.45)*np.float32(.01)))
  assert bound[0]<=a.q(x)<=bound[1];checks+=1
for x in [F(0),F(1,2**150),-F(1,2**150),F(1)+F(1,2**24),F(30)+F(1,2**20)]:
 lo=a.floor32(x);hi=a.ceil32(x);near=a.rn(x)
 assert a.q(lo)<=x<=a.q(hi)
 assert abs(a.q(near)-x)==min(abs(a.q(lo)-x),abs(a.q(hi)-x));checks+=1
# Stored evidence, paper and scripts in released manifest remain unchanged.
manifest=json.loads((a.BASE/'package-sha256.json').read_text());verified=0
for name,expected in manifest.items():
 assert a.sha(a.BASE/name)==expected,name;verified+=1
rows=a.csvread(a.BASE/'evidence/input-readout/analysis/input-switching.csv');selected=[r for r in rows if r['category']=='input_changed_spikes_equal'];assert len(selected)==17
orig=a.graph('original');refs={};cache={};setup=[]
for p in ['tonic','global_burst','focal_burst']:
 t=time.perf_counter();refs[p]=a.state(p);cache[p],_=a.reference_cache(p,refs[p],orig);setup.append(time.perf_counter()-t)

def point_replay(p,ref,g,targets):
 """A two-target reference-clamped diagnostic, NOT a full feedback simulation."""
 checked=0
 for k in targets:
  vals,_,_,_=a.inputs(g,ref[:,:,0],p,k);v=np.float32(-65);ge=gi=np.float32(0)
  for n in range(a.T):
   if not cache[p][k]['execute'][n]:continue
   deadline=0 if n==0 else int(ref[n-1,k,8]);fe=np.float32(0) if n==0 else a.floats(ref[n-1,k,6])
   pre,ge,gi=a.point_step(v,ge,gi,fe,np.float32(0),vals[n],deadline<=n)
   v=np.float32(-65) if ref[n,k,0] else pre;checked+=1
 return checked
costs=[]
for r in selected:
 p=r['probe'];times=[];point=[];prepare=[]
 for repeat in range(5):
  t=time.perf_counter();g=a.graph('swap'+r['seed']);old={tuple(map(int,e)) for e in orig};new={tuple(map(int,e)) for e in g};targets=sorted({e[2] for e in old^new});prepare.append(time.perf_counter()-t)
  t=time.perf_counter();res,_=a.certify(p,refs[p],cache[p],g,targets);times.append(time.perf_counter()-t)
  t=time.perf_counter();point_replay(p,refs[p],g,targets);point.append(time.perf_counter()-t)
 archived=json.loads((a.E/'runs'/f"{r['stem']}.json").read_text())['instrumented_loop_seconds']
 costs.append(dict(stem=r['stem'],certified=res['certified'],graph_load_and_difference_seconds_median=statistics.median(prepare),certificate_seconds_median=statistics.median(times),local_point_replay_seconds_median=statistics.median(point),archived_instrumented_rust_seconds=archived,checked_chunk_slots=res['checked_chunk_slots'],incoming_events=res['visited_incoming_events']))
with(out/'costs.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(costs[0]));w.writeheader();w.writerows(costs)
# Diagnose the sole noncertificate without re-running its network.
r=next(r for r in selected if r['seed']=='93005');p=r['probe'];ref=refs[p];candidate=a.state(p,'swap93005');g=a.graph('swap93005')
status=np.argwhere(ref[:,:,9]!=candidate[:,:,9]);diag=[]
for n,k in status:
 diag.append(dict(slot=int(n),chunk=int(k),reference_status=int(ref[n,k,9]),candidate_status=int(candidate[n,k,9]),reference_voltage=float(a.floats(ref[n,k,1])),candidate_voltage=float(a.floats(candidate[n,k,1]))))
summary=dict(status='pass',arithmetic_checks=checks,release_files_hash_verified=verified,certificate_median_seconds=statistics.median([r['certificate_seconds_median'] for r in costs]),graph_setup_median_seconds=statistics.median([r['graph_load_and_difference_seconds_median'] for r in costs]),local_point_replay_median_seconds=statistics.median([r['local_point_replay_seconds_median'] for r in costs]),original_reference_setup_seconds=setup,archived_rust_loop_median_seconds=statistics.median([r['archived_instrumented_rust_seconds'] for r in costs]),speedup_claim=False,cost_scope='Current Python exact-rational checker versus same-language two-target reference-clamped point replay; Rust timings historical/instrumented/non-comparable. No full simulator launched.',noncertificate=dict(stem=r['stem'],status_differences=diag,spikes_equal=bool(np.array_equal(ref[:,:,0],candidate[:,:,0]))))
a.write(out/'summary.json',summary);print(json.dumps(summary,indent=2))
