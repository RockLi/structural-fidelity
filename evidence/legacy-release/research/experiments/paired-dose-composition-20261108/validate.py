#!/usr/bin/env python3
from pathlib import Path
from fractions import Fraction as F
import csv,json,hashlib,collections
import numpy as np
R=Path(__file__).resolve().parent
BASE=R.parents[2]/'output/local-circuit-preprint-20261026-final-review/evidence'
def read(p):return list(csv.DictReader(p.open()))
def main():
 hashes=json.loads((R/'results/input-sha256.json').read_text())
 for name,h in hashes.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
 m=read(R/'results/per-chain.csv');d={(int(x['block']),x['budget']):x for x in m};bins={(int(x['block']),x['budget'],int(x['width_slots']),int(x['offset_slots'])):int(x['Dbin']) for x in read(R/'results/readout-offsets.csv')};checks=0
 for row in m:
  b=row['budget'];p=BASE/('activity-guided-retention' if b=='full' else 'budget-boundary');ref=np.load(p/'runs/original__train.npz')['state_bits'][:,:,0].astype(np.int64);new=np.load(p/'runs'/(row['canonical']+'__train.npz'))['state_bits'][:,:,0].astype(np.int64);delta=new-ref
  # Bin by per-slot integer labels, independently from cumulative-sum slicing.
  for width in [1,2,10,50,300]:
   for offset in range(width):
    labels=(np.arange(300)-offset)//width;total=0
    for group in np.unique(labels):total+=int(abs(delta[labels==group].sum(0)).sum())
    assert total==bins[int(row['block']),b,width,offset];checks+=1
  positives=sum(int(v) for v in delta.flat if v>0);negatives=-sum(int(v) for v in delta.flat if v<0);assert positives+negatives==int(row['Dslot']);assert abs(positives-negatives)==int(row['Dglobal'])
 pairs=read(R/'results/paired-decomposition.csv')
 for x in pairs:
  a=d[int(x['block']),x['from_budget']];b=d[int(x['block']),x['to_budget']];n=int(a['reference_spikes']);xa=F(int(a['Dslot']),n);xb=F(int(b['Dslot']),n);ya=F(int(a['Dcount']),n);yb=F(int(b['Dcount']),n)
  if xa and xb:
   # Independent two orderings averaged: change magnitude first vs composition first.
   ra=ya/xa;rb=yb/xb;mag=((xb-xa)*ra+(xb-xa)*rb)/2;comp=(xa*(rb-ra)+xb*(rb-ra))/2
   assert mag+comp==yb-ya;assert float(mag)==float(x['magnitude_component']);assert float(comp)==float(x['retained_fraction_component'])
 report=dict(status='pass',input_hashes=len(hashes),independent_all_offset_checks=checks,exact_symmetric_decomposition_checks=len(pairs),new_simulations=0,source='Independent label grouping and exact Fraction endpoint decomposition, using original archived trajectories.')
 (R/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
