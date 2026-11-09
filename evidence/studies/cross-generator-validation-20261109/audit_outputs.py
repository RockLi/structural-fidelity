"""Independent graph invariants and raw-output reductions, without simulation."""
from pathlib import Path
import json,hashlib,csv,collections
import numpy as np
R=Path(__file__).resolve().parent;SEEDS=[201,202,203,301,302,303];INPUTS=['G_B','F_B','F_H','G_T','F_HT']
def load(p):return json.loads(p.read_text())
def read(p):return list(csv.DictReader(p.open()))
def edge(p):return np.loadtxt(p,delimiter=',',skiprows=1,dtype=np.int64)
results=[]
for seed in SEEDS:
 d=R/f'seed{seed}';g=edge(d/'graphs/original.csv');meta=load(d/'generator.json');assert len(g)==2845 and np.bincount(g[:,0]).tolist()==[1467,610,648,120]
 assert len(set(map(tuple,g[:,1:3])))==2845 and not np.any(g[:,1]==g[:,2]);assert np.all(g[:,4]==1)
 if seed<300:
  lab=np.array(meta['labels']);assert np.bincount(lab[:100]).tolist()==[20]*5 and np.bincount(lab[100:]).tolist()==[5]*5
 else:
  x=np.array(meta['coordinates']);assert np.array_equal(np.sort(x),np.arange(125)/125)
 swaps={};m={(int(x['swap']),x['input']):x for x in read(d/'network-metrics.csv')}
 for sid in range(93001,93020):
  e=edge(d/'graphs'/f'swap{sid}.csv');assert np.array_equal(g[:,[0,1,3,4]],e[:,[0,1,3,4]]) and np.count_nonzero(g[:,2]!=e[:,2])==2
  assert len(set(map(tuple,e[:,1:3])))==2845 and not np.any(e[:,1]==e[:,2]);assert set(map(tuple,g[:,1:3]))!=set(map(tuple,e[:,1:3]))
  for arm in range(4):
   for col in [1,2]:
    assert collections.Counter(map(tuple,g[g[:,0]==arm][:,[col,3,4]]))==collections.Counter(map(tuple,e[e[:,0]==arm][:,[col,3,4]]))
  swaps[sid]=e
 for u in INPUTS:
  ref=np.load(d/'runs'/f'original__{u}.npz')['state_bits'];s=ref[:,:,0].astype(np.int64);den=s.sum();flags={}
  for sid,e in swaps.items():
   b=np.load(d/'runs'/f'swap{sid}__{u}.npz')['state_bits'];diff=b[:,:,0].astype(np.int64)-s;ds=int(np.abs(diff).sum());dc=int(np.abs(diff.sum(0)).sum());r=m[sid,u];assert ds==int(r['slot_absolute']) and dc==int(r['count_absolute']);assert float(r['Dslot'])==ds/den and float(r['Dcount'])==dc/den
   assert (r['spike_equal']=='True')==(ds==0);assert (r['bitwise_equal']=='True')==np.array_equal(b,ref);flags[sid]=(ds==0)
  assert np.array_equal(ref,np.load(d/'repeat'/f'original__{u}.npz')['state_bits'])
 for row in read(d/'visibility-contrasts.csv'):
  counts=collections.Counter(('same' if m[sid,row['input_a']]['spike_equal']=='True' else 'different')+'/'+('same' if m[sid,row['input_b']]['spike_equal']=='True' else 'different') for sid in swaps)
  assert sum(counts.values())==19
  for key in ['same/same','same/different','different/same','different/different']:assert counts[key]==int(row[key])
 for p in (d/'events').glob('*'):
  assert p.read_bytes()==(R.parent/'multigraph-input-validation-20261109/seed100/events'/p.name).read_bytes()
 results.append(dict(seed=seed,family=meta['family'],graphs_audited=19,trajectory_comparisons_audited=95,per_node_per_arm_multisets_exact=True))
source=R.parent/'multigraph-input-validation-20261109/source'
for p in (R/'source').rglob('*'):
 if p.is_file():assert p.read_bytes()==(source/p.relative_to(R/'source')).read_bytes()
out=dict(status='pass',graphs=results,unchanged_frozen_library=True,scope='Independent reduction/invariant checks; no new simulation or acceptance criterion.')
(R/'independent-network-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
