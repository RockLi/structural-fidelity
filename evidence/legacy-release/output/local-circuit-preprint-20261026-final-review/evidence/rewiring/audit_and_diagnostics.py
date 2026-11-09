#!/usr/bin/env python3
"""Independent graph-constraint audit plus explicitly post-hoc diagnostics.

Rate-distribution distances ignore chunk identities within E/I groups. They are
descriptive additions after the locked primary analysis; no p-values or gates.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parent
def save(path,x): path.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    with path.open() as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
def attrs(rows):
    degree=Counter(); incoming=defaultdict(Counter); outgoing=defaultdict(Counter)
    for r in rows:
        a,s,t,w,d=[r[k] for k in ['arm','source','target','weight_bits','delay']]
        assert a==2*int(s>=100)+int(t>=100) and s!=t and d==1
        degree[(a,'out',s)]+=1;degree[(a,'in',t)]+=1
        outgoing[(a,s)][(w,d)]+=1; incoming[(a,t)][(w,d)]+=1
    assert len({(r['source'],r['target']) for r in rows})==len(rows)
    return degree,incoming,outgoing
def distance(ref,other):
    # Equal empirical sample sizes: sorting computes 1D Wasserstein distance.
    return float(np.abs(np.sort(ref)-np.sort(other)).mean()),float(np.abs(ref-other).mean())
def main():
    assert not (P/'independent-audit.json').exists()
    checked=[]
    for family in ['homogeneous','heterogeneous']:
        root=P/'graphs'/family; orig=read(root/'original.csv'); d0,i0,o0=attrs(orig)
        for path in sorted(root.glob('*.csv')):
            rows=read(path); deg,inc,out=attrs(rows)
            assert deg==d0 and out==o0 and len(rows)==len(orig)
            if family=='homogeneous':assert inc==i0
            checked.append(dict(graph=str(path.relative_to(P)),sha256=sha(path),
                per_arm_degree_counter_exact=True,source_weight_delay_multisets_exact=True,
                target_weight_delay_multisets_exact=(inc==i0)))
    old=read(P/'frozen-inputs/historical-e3-trace-zero.csv')
    exp=read(P/'runs/heterogeneous__original__tonic__explicit.csv')[:200]
    trace=read(P/'runs/heterogeneous__original__tonic__trace.csv')[:200]
    raw=read(P/'runs/heterogeneous__original__tonic__raw_sum.csv')[:200]
    assert len(old)==len(exp)==len(trace)==len(raw)==200
    for o,e,t,r in zip(old,exp,trace,raw):
        assert o['slot']==e['step']+1==t['step']+1==r['step']+1
        assert o['explicit_spikes']==e['spikes']==r['spikes']
        assert o['explicit_events']==e['recurrent_messages']
        assert o['approx_spikes']==t['spikes'] and o['approx_events']==t['recurrent_messages']
    save(P/'independent-audit.json',dict(status='pass',implementation='Python dictionaries and multisets; separate from vectorized generator checks',
        graphs=checked,historical_e3_per_slot_bridge=dict(status='pass',steps=200,explicit_spikes_and_messages=True,
            trace_spikes_and_messages=True,raw_spikes=True,reference_sha256=sha(P/'frozen-inputs/historical-e3-trace-zero.csv'))))
    rows=[]
    for family in ['homogeneous','heterogeneous']:
        for probe in ['tonic','global_burst','focal_burst']:
            with np.load(P/f'runs/{family}__original__{probe}__explicit.npz') as z:
                ref=z['state_bits'][:,:,0].sum(axis=0).astype(float)/100/.03
            for seed in range(91001,91020):
                with np.load(P/f'runs/{family}__r{seed}__{probe}__explicit.npz') as z:
                    other=z['state_bits'][:,:,0].sum(axis=0).astype(float)/100/.03
                for label,sl in [('E',slice(0,100)),('I',slice(100,125))]:
                    a,b=ref[sl],other[sl]; w1,identified=distance(a,b)
                    rows.append(dict(family=family,probe=probe,graph=f'r{seed}',population=label,
                        original_mean_rate_hz=float(a.mean()),rewired_mean_rate_hz=float(b.mean()),
                        distribution_wasserstein_hz=w1,identity_matched_rate_mae_hz=identified,
                        normalized_distribution_w1=float(w1/a.mean()) if a.mean() else None,
                        normalized_identity_mae=float(identified/a.mean()) if a.mean() else None))
    with (P/'analysis/posthoc-rate-distributions.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for family in ['homogeneous','heterogeneous']:
        for probe in ['tonic','global_burst','focal_burst']:
            for pop in ['E','I']:
                sel=[r for r in rows if r['family']==family and r['probe']==probe and r['population']==pop]
                a=[r['normalized_distribution_w1'] for r in sel];b=[r['normalized_identity_mae'] for r in sel]
                summary.append(dict(family=family,probe=probe,population=pop,
                    distribution_w1_median=float(np.median(a)),distribution_w1_min=float(min(a)),distribution_w1_max=float(max(a)),
                    identity_mae_median=float(np.median(b))))
    save(P/'analysis/posthoc-rate-distributions.json',dict(status='descriptive post-hoc addition',
        reason='Separate identity-sensitive trajectory fidelity from identity-insensitive rate-distribution similarity; no new simulations',
        definition='W1 between empirical per-chunk 30-ms mean-rate distributions, separately in E and I; normalized by original population mean',
        limitation='Rates quantized by short 30-ms window; W1 similarity is not dynamic or statistical equivalence',summary=summary))
    print('Independent graph multiset audit and archived per-slot bridge: PASS')
    print(json.dumps(summary[:6],indent=2))
if __name__=='__main__':main()
