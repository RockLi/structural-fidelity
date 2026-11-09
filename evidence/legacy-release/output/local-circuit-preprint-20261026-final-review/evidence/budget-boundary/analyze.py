#!/usr/bin/env python3
"""Locked analysis of selection policies on equal-budget explicit graph changes.

This program does not select graphs, run simulations or fit a test-time model.
It joins the already frozen selection table to unique archived graph runs.
All original edges are still represented; execution counters are diagnostics,
not proof of storage reduction, compression or runtime acceleration.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

PROBES = ['train', 'spatial', 'temporal', 'spatiotemporal']
HELDOUT = PROBES[1:]
POLICIES = ['random', 'mean', 'coactivity', 'shuffled']
COMPARATORS = ['random', 'mean', 'shuffled']
SCORES = ['J_mean', 'J_coactivity', 'J_shuffled', 'J_shuffle_expectation']
METRICS = ['raw_slot_l1', 'bin1ms_l1', 'cumulative_l1', 'Rcount',
           'van_rossum_tau1', 'state_rms_standardized']
SIGN_TOLERANCE = 1e-12


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False) + '\n')


def read_csv(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    assert rows
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ratio(a, b):
    return float(a / b) if b else None


def describe(values):
    vals = [float(v) for v in values if v is not None]
    return dict(n=len(vals), mean=float(np.mean(vals)) if vals else None,
                median=float(np.median(vals)) if vals else None,
                minimum=min(vals) if vals else None,
                maximum=max(vals) if vals else None)


def complete_mean(values):
    return float(np.mean(values)) if all(v is not None for v in values) else None


def float_fields(array):
    return np.ascontiguousarray(array[:, :, 1:4], dtype=np.uint32).view(np.float32).astype(np.float64)


def rms(value):
    return float(np.sqrt(np.mean(np.asarray(value, dtype=np.float64) ** 2)))


def vr_squared(delta, tau=1., dt=.1):
    """Sum of identified-channel squared van Rossum distances, complete tail.

    V^2=(1/tau) integral_0^infinity sum_k(filtered delta_k)^2 dt.
    delta contains representative spike counts, not all 100 synchronous units.
    Full-tail piecewise integration crosschecks the exponential Gram recurrence.
    """
    delta = np.asarray(delta, dtype=np.float64)
    a = math.exp(-dt / tau)
    filtered = np.zeros(delta.shape[1])
    q = 0.
    norms = []
    for row in delta:
        filtered *= a
        q += float(row @ row + 2 * row @ filtered)
        filtered += row
        norms.append(float(filtered @ filtered))
    integral = .5 * ((1 - a*a) * sum(norms[:-1]) + norms[-1])
    quadratic = .5 * q
    assert math.isclose(integral, quadratic, rel_tol=2e-11, abs_tol=2e-10)
    assert quadratic >= -1e-10
    return max(quadratic, 0.)


def compare(reference, candidate, scale):
    a = reference[:, :, 0].astype(np.int64)
    b = candidate[:, :, 0].astype(np.int64)
    delta = b - a
    denominator = int(a.sum())
    dslot = int(np.abs(delta).sum())
    d1ms = int(np.abs(delta.reshape(30, 10, 125).sum(axis=1)).sum())
    dcount = int(np.abs(delta.sum(axis=0)).sum())
    dglobal = abs(int(delta.sum()))
    dpopulation = int(np.abs(delta.sum(axis=1)).sum())
    changed_slots = np.flatnonzero(np.any(delta != 0, axis=1))
    first_slot = int(changed_slots[0]) if len(changed_slots) else None
    assert dglobal <= dcount <= d1ms <= dslot
    # A separate scalar integer reduction guards against an axis/bin error.
    scalar_bins = sum(abs(sum(int(delta[t, k]) for t in range(start, start+10)))
                      for start in range(0, 300, 10) for k in range(125))
    assert scalar_bins == d1ms
    scalar_counts = sum(abs(sum(int(delta[t, k]) for t in range(300))) for k in range(125))
    assert scalar_counts == dcount
    difference = float_fields(candidate) - float_fields(reference)
    normalized = rms(difference / scale) if np.all(scale > 0) else None
    vr = vr_squared(delta / 100.)
    assert (vr == 0) == (dslot == 0)
    return dict(reference_spikes=denominator, candidate_spikes=int(b.sum()),
                Dslot=dslot, D1ms=d1ms, Dcount=dcount,
                Dglobal_cumulative=dglobal, Dpopulation_slot=dpopulation,
                raw_slot_l1=ratio(dslot, denominator), bin1ms_l1=ratio(d1ms, denominator),
                cumulative_l1=ratio(dcount, denominator), Rcount=ratio(dcount, dslot),
                van_rossum_tau1=ratio(2 * vr, denominator / 100.),
                state_rms_standardized=normalized,
                voltage_rms_abs=rms(difference[:, :, 0]),
                exc_rms_abs=rms(difference[:, :, 1]),
                inh_rms_abs=rms(difference[:, :, 2]),
                spike_mismatch_cells=int(np.count_nonzero(delta)),
                spikes_identical=dslot==0,
                first_spike_divergence_slot=first_slot,
                first_spike_divergence_ms=(first_slot+1)*.1 if first_slot is not None else None,
                recorded_bits_equal=bool(np.array_equal(reference, candidate)))


def selfchecks():
    checks = 0
    for tau in [.1, 1., 30.]:
        a = np.zeros((7, 2)); a[2, 0] = 1
        assert math.isclose(vr_squared(a, tau), .5, abs_tol=1e-12)
        a[5, 0] = -1
        assert math.isclose(vr_squared(a, tau), 1-math.exp(-.3/tau), abs_tol=1e-12)
        a[5, 0] = 0; a[5, 1] = -1
        assert math.isclose(vr_squared(a, tau), 1., abs_tol=1e-12)
        a = np.zeros((7, 1)); a[-1, 0] = 1
        assert math.isclose(vr_squared(a, tau), .5, abs_tol=1e-12)
        assert vr_squared(np.zeros((7, 1)), tau) == 0
        checks += 5
    assert ratio(0, 0) is None and ratio(0, 10) == 0
    assert complete_mean([0., 1., 2.]) == 1 and complete_mean([0., None, 2.]) is None
    reference = np.zeros((300,125,10),dtype=np.uint32)
    candidate = reference.copy()
    reference[9,0,0]=100;candidate[10,0,0]=100
    metric = compare(reference,candidate,np.ones(3))
    assert (metric['Dslot'],metric['D1ms'],metric['Dcount'])==(200,200,0)
    assert metric['raw_slot_l1']==2 and metric['Rcount']==0
    assert metric['first_spike_divergence_slot']==9 and metric['first_spike_divergence_ms']==1.
    metric = compare(reference,reference,np.ones(3))
    assert metric['Rcount'] is None and metric['first_spike_divergence_slot'] is None
    assert metric['recorded_bits_equal'] and metric['raw_slot_l1']==0
    return checks + 4


BUDGETS=['p01','p02']


def gate_decision(contrast_summary,per_policy_hash):
    decisions=[]
    for budget in BUDGETS:
        obs={c:next(r for r in contrast_summary if r['budget']==budget and r['probe']=='train' and r['comparator']==c) for c in COMPARATORS}
        complete=all(r['n']==10 for r in obs.values())
        conditions=dict(complete_pairs=complete,
            random_mean_negative=obs['random']['mean'] is not None and obs['random']['mean'] < -SIGN_TOLERANCE,
            random_median_negative=obs['random']['median'] is not None and obs['random']['median'] < -SIGN_TOLERANCE,
            random_at_least_seven_strict_wins=obs['random']['coactivity_better']>=7)
        for c in ['mean','shuffled']:
            conditions[c+'_mean_noninferior']=obs[c]['mean'] is not None and obs[c]['mean']<=SIGN_TOLERANCE
            conditions[c+'_wins_at_least_losses']=obs[c]['coactivity_better']>=obs[c]['coactivity_worse']
        decisions.append(dict(budget=budget,observed=obs,conditions=conditions,passed=all(conditions.values())))
    return dict(schema_version=1,stage='train',proceed_migration=all(d['passed'] for d in decisions),
        budgets=decisions,training_per_policy_sha256=per_policy_hash,epsilon=SIGN_TOLERANCE,
        decision_rule='Both budgets: ten defined pairs; vs random mean and median < -1e-12 and >=7 strict wins; vs each mean/shuffled mean <=1e-12 and wins >= losses.',
        interpretation='Pragmatic continuation rule, not a significance or formal noninferiority test. Comparator guards allow all ties and do not establish a coactivity-specific benefit.')


def gate_selfchecks():
    def fixture(mean=-.2,median=-.2,wins=7,losses=3,n=10):
        return [dict(budget=b,probe='train',comparator=c,n=n,mean=mean,median=median,minimum=-.5,maximum=.1,
                     coactivity_better=wins,tied=n-wins-losses,coactivity_worse=losses,same_selected_graph=0)
                for b in BUDGETS for c in COMPARATORS]
    assert gate_decision(fixture(),'x')['proceed_migration']
    for change in [dict(mean=0),dict(median=0),dict(wins=6,losses=4),dict(n=9,wins=7,losses=2)]:
        assert not gate_decision(fixture(**change),'x')['proceed_migration']
    rows=fixture()
    for r in rows:
        if r['comparator']!='random':r.update(mean=0.,median=0.,coactivity_better=0,tied=10,coactivity_worse=0)
    assert gate_decision(rows,'x')['proceed_migration']
    rows[-1].update(mean=2e-12)
    assert not gate_decision(rows,'x')['proceed_migration']
    return 7


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--stage',choices=['train','migration'],default='train')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args();root=args.root.resolve();stage=args.stage
    probes=['train'] if stage=='train' else ['spatial','temporal','spatiotemporal']
    endpoint_probe='train' if stage=='train' else 'migration_mean'
    out=args.output_dir.resolve() if args.output_dir else root/f'analysis-{stage}'
    if out.exists() and any(out.iterdir()):raise SystemExit('Use a new empty analysis directory; preserve locked evidence.')
    out.mkdir(parents=True,exist_ok=True);input_hashes={};source_hash=sha(Path(__file__))
    def track(path):
        path=Path(path);input_hashes[str(path.relative_to(root))]=sha(path);return path
    if stage=='migration':
        gate=load(track(root/'gate.json'));audited=load(track(root/'audit-train.json'))
        assert gate['proceed_migration'] is True,'Training gate failed: migration analysis is prohibited'
        assert audited['status']=='pass' and audited['gate_verified'] is True and audited['gate_sha256']==sha(root/'gate.json')
    protocol=load(track(root/'protocol.json'));selections=load(track(root/'selection.json'))
    candidates=read_csv(track(root/'candidates.csv'));aliases=load(track(root/'graph-aliases.json'))
    records=load(track(root/f'run-{stage}-complete.json'))['records']
    assert len(selections)==80 and len(candidates)==1280
    assert {(s['budget'],int(s['block']),s['policy']) for s in selections}=={(b,k,p) for b in BUDGETS for k in range(10) for p in POLICIES}
    by_candidate={(c['budget'],int(c['block']),int(c['candidate'])):c for c in candidates}
    assert set(by_candidate)=={(b,k,c) for b in BUDGETS for k in range(10) for c in range(64)}
    for s in selections:
        c=by_candidate[s['budget'],int(s['block']),int(s['candidate'])];assert c['graph']==s['graph']
        assert all(float(c[k])==float(s[k]) and math.isfinite(float(s[k])) and float(s[k])>=0 for k in SCORES)
        if s['policy']!='random':
            field='J_'+s['policy'];bank=[r for (b,k,_),r in by_candidate.items() if b==s['budget'] and k==int(s['block'])]
            best=min(bank,key=lambda r:(float(r[field]),int(r['candidate'])))
            assert int(s['candidate'])==int(best['candidate'])
    selected_graphs=sorted({aliases[s['graph']] for s in selections});record_map={(r['graph'],r['probe']):r for r in records}
    expected={(g,p) for g in ['original']+selected_graphs for p in probes}
    assert len(record_map)==len(records) and set(record_map)==expected,'Incomplete or extra stage runs: fail closed, no gate authorization'
    arrays={};counters={};originals={}
    for graph in ['original']+selected_graphs:
        assert len(read_csv(track(root/'graphs'/f'{graph}.csv')))==2845
        for probe in probes:
            rec=record_map[graph,probe];assert rec['stem']==f'{graph}__{probe}'
            path=root/'runs'/f'{rec["stem"]}.npz'
            with np.load(track(path)) as z:array=z['state_bits']
            assert array.shape==(300,125,10) and array.dtype==np.uint32
            assert np.all((array[:,:,0]==0)|(array[:,:,0]==100))
            assert np.all(np.isfinite(np.ascontiguousarray(array[:,:,1:8]).view(np.float32))) and np.all(array[:,:,9]<=2)
            counts=read_csv(track(path.with_suffix('.csv')));metadata=load(track(path.with_suffix('.json')))
            assert len(counts)==300 and [int(r['spikes']) for r in counts]==array[:,:,0].sum(axis=1).tolist()
            assert metadata['timing_is_performance_benchmark'] is False and metadata['external_input_positive_finite'] is True
            for ext,key in [('.npz','npz_sha256'),('.csv','csv_sha256'),('.json','json_sha256')]:assert sha(path.with_suffix(ext))==rec[key]
            counters[graph,probe]=dict(recurrent_messages=sum(int(r['recurrent_messages']) for r in counts),
                active_source_edge_visits=sum(int(r['active_source_edge_visits']) for r in counts),
                active_chunk_slot_sum=sum(int(r['active_chunks']) for r in counts),edge_count=2845)
            arrays[graph,probe]=array
            if graph=='original':originals[probe]=array
    scales={p:float_fields(originals[p]).std(axis=(0,1),ddof=0) for p in probes}
    save(out/'reference-scales.json',dict(definition='Per-input original-only V,gE,gI std across 300 slots and 125 chunks, ddof=0; any zero channel gives null standardized RMS.',
         scales={p:dict(zip(['V','gE','gI'],map(float,v))) for p,v in scales.items()}))
    checks=selfchecks()+gate_selfchecks();per_graph=[];metrics={}
    for graph in ['original']+selected_graphs:
        for probe in probes:
            row=dict(graph=graph,probe=probe,**compare(originals[probe],arrays[graph,probe],scales[probe]),**counters[graph,probe])
            metrics[graph,probe]=row;per_graph.append(row)
    per_policy=[];endpoints=[];policy_map={}
    for s in sorted(selections,key=lambda s:(s['budget'],int(s['block']),POLICIES.index(s['policy']))):
        identity=dict(budget=s['budget'],block=int(s['block']),policy=s['policy'],candidate=int(s['candidate']),**{k:float(s[k]) for k in SCORES})
        canonical=aliases[s['graph']]
        for probe in probes:
            row={**identity,**metrics[canonical,probe],'graph':s['graph'],'canonical_graph':canonical}
            per_policy.append(row);policy_map[s['budget'],int(s['block']),s['policy'],probe]=row
        endpoints.append({**identity,'graph':s['graph'],'canonical_graph':canonical,'endpoint_probe':endpoint_probe,
            'endpoint_raw_slot_l1':complete_mean([metrics[canonical,p]['raw_slot_l1'] for p in probes])})
    endpoint_map={(r['budget'],r['block'],r['policy']):r for r in endpoints};contrasts=[]
    for budget in BUDGETS:
        for block in range(10):
            for probe in probes+([] if stage=='train' else ['migration_mean']):
                for c in COMPARATORS:
                    left=endpoint_map[budget,block,'coactivity'];right=endpoint_map[budget,block,c]
                    a=left['endpoint_raw_slot_l1'] if probe==endpoint_probe else policy_map[budget,block,'coactivity',probe]['raw_slot_l1']
                    b=right['endpoint_raw_slot_l1'] if probe==endpoint_probe else policy_map[budget,block,c,probe]['raw_slot_l1']
                    contrasts.append(dict(budget=budget,block=block,probe=probe,comparator=c,coactivity_graph=left['graph'],comparison_graph=right['graph'],
                        coactivity_loss=a,comparator_loss=b,difference_coactivity_minus_comparator=a-b if a is not None and b is not None else None,
                        same_selected_graph=left['canonical_graph']==right['canonical_graph']))
    summaries=[]
    for budget in BUDGETS:
        for probe in probes+([] if stage=='train' else ['migration_mean']):
            for c in COMPARATORS:
                rr=[r for r in contrasts if (r['budget'],r['probe'],r['comparator'])==(budget,probe,c)]
                values=[r['difference_coactivity_minus_comparator'] for r in rr];valid=[x for x in values if x is not None]
                summaries.append(dict(budget=budget,probe=probe,comparator=c,**describe(values),
                    coactivity_better=sum(x < -SIGN_TOLERANCE for x in valid),tied=sum(abs(x)<=SIGN_TOLERANCE for x in valid),
                    coactivity_worse=sum(x>SIGN_TOLERANCE for x in valid),same_selected_graph=sum(r['same_selected_graph'] for r in rr)))
    metric_summary=[];zero_summary=[]
    for budget in BUDGETS:
        for probe in probes:
            for policy in POLICIES:
                rr=[r for r in per_policy if (r['budget'],r['probe'],r['policy'])==(budget,probe,policy)]
                for metric in METRICS:
                    metric_summary.append(dict(budget=budget,probe=probe,policy=policy,metric=metric,
                        undefined=sum(r[metric] is None for r in rr),**describe(r[metric] for r in rr)))
                zero_summary.append(dict(budget=budget,probe=probe,policy=policy,n=len(rr),
                    zero_raw_slot=sum(r['Dslot']==0 for r in rr),zero_bin1ms=sum(r['D1ms']==0 for r in rr),
                    zero_cumulative=sum(r['Dcount']==0 for r in rr),zero_reference_spikes=sum(r['reference_spikes']==0 for r in rr),
                    recorded_bits_equal=sum(r['recorded_bits_equal'] for r in rr)))
    score_pairs=[]
    smap={(s['budget'],s['block'],s['policy']):s for s in selections}
    for budget in BUDGETS:
        for block in range(10):
            for comparator in COMPARATORS:
                a=smap[budget,block,'coactivity']['J_coactivity'];b=smap[budget,block,comparator]['J_coactivity']
                score_pairs.append(dict(budget=budget,block=block,comparator=comparator,coactivity_J=a,comparator_J=b,
                    coactivity_J_zero=a==0,comparator_J_zero=b==0,ratio_coactivity_to_comparator=ratio(a,b),
                    relative_reduction=1-a/b if b else None))
    save(out/'metric-definitions.json',dict(
        signed_difference='delta[slot,chunk] = candidate spike count minus same-input original count; includes all 100 synchronized units.',
        Dslot='sum_slot,chunk abs(delta)',
        D1ms='sum_1msbin,chunk abs(sum_slot_in_bin delta); 10-slot bins start at slot 0.',
        Dcount='sum_chunk abs(sum_slot delta)',
        Dglobal_cumulative='abs(sum_slot,chunk delta); full-window total-count difference.',
        Dpopulation_slot='sum_slot abs(sum_chunk delta); raw-slot population discrepancy, distinct from Dglobal_cumulative.',
        raw_slot_l1='Dslot / original full-window total count; null when denominator zero.',
        bin1ms_l1='D1ms / original full-window total count; null when denominator zero.',
        cumulative_l1='Dcount / original full-window total count; null when denominator zero.',
        Rcount='Dcount / Dslot; null when Dslot zero. A finite-window retained-discrepancy fraction, not a causal timing/count decomposition.',
        van_rossum_tau1='2 V^2 / original representative-spike count. V^2=(1/tau) integral_0^infinity sum_chunk(filtered difference)^2 dt; exponential tau=1 ms, representative counts=counts/100, full analytic tail, no future events assumed. Null when reference denominator zero.',
        state_rms_standardized='RMS of all differences in V,gE,gI after division by their same-input original-only full-window channel std (population ddof=0); null if any scale zero.',
        first_spike_divergence_slot='First zero-based recorded slot with a nonzero identified count difference; null for identical spike counts.',
        first_spike_divergence_ms='Completed-step time (first_spike_divergence_slot+1)*0.1; null for identical counts.',
        graph='per_graph uses canonical unique graph IDs; per_policy preserves selected candidate graph ID and provides canonical_graph separately.',
        same_selected_graph='Paired selected graphs have the same canonical graph bytes, including different aliases.',
        counters='Recurrent messages, active-source edge visits and active chunk/slot sum are instrumentation diagnostics. All graphs retain 2845 edges. No runtime or memory saving is inferred.',
        missing='CSV empty field and JSON null; zero values are never used for undefined ratios.',
        primary='Training gate: within each budget compare coactivity minus each comparator on the training raw-slot loss. Conditional migration: equal-weight mean of all three known test inputs within block, no dropping undefined values.',
        inference='Ten descriptive matched graph-search banks on one original. No independent-input or independent-network sample claim, p-value, or bootstrap interval.'))
    for name,rows in [('per_graph',per_graph),('per_policy',per_policy),('per_block_endpoints',endpoints),
        ('paired_contrasts',contrasts),('contrast_summary',summaries),('metric_summary',metric_summary),
        ('zero_summary',zero_summary),('training_score_pairs',score_pairs)]:write_csv(out/(name+'.csv'),rows)
    summary=dict(status='pass',stage=stage,blocks=10,candidates_per_block=64,budgets=protocol['budgets'],policies=POLICIES,probes=probes,
        selected_policy_records=80,unique_selected_graphs=len(selected_graphs),unique_scientific_runs=len(per_graph),
        primary_definition=protocol['primary'],contrasts=summaries,metric_summaries=metric_summary,zero_summaries=zero_summary,
        policy_endpoints=[dict(budget=b,policy=p,**describe(r['endpoint_raw_slot_l1'] for r in endpoints if r['budget']==b and r['policy']==p)) for b in BUDGETS for p in POLICIES],
        score_relative_reductions=[dict(budget=b,comparator=c,**describe(r['relative_reduction'] for r in score_pairs if r['budget']==b and r['comparator']==c)) for b in BUDGETS for c in COMPARATORS],
        numerical_sign_tolerance=SIGN_TOLERANCE,performance_claim=False,edge_counts_all_2845=True,
        limits=['One original, two paired nested budgets and ten candidate-bank blocks; not independent network replication.',
          'Budgets and known test inputs were chosen after the earlier 9.91% outcomes. No new independent held-out cohort.',
          'Training gate is a pragmatic continuation rule. Passing does not establish significance or a coactivity-specific benefit.',
          'All 2845 edges and neuron states remain; no compression or performance claim.',
          'Uncentered zero-lag coactivity score is invariant under a common time permutation; it does not encode sequence order.',
          'No post-outcome alteration of the primary endpoint or gate; report zeros, ties and undefined metrics.'],analyzer_sha256=source_hash)
    if stage=='train':
        gate=gate_decision(summaries,sha(out/'per_policy.csv'));save(out/'gate.json',gate)
        summary['gate']=gate
        if args.output_dir is None:
            assert not (root/'gate.json').exists();save(root/'gate.json',gate)
            save(root/'migration-ledger.json',dict(status='authorized_pending' if gate['proceed_migration'] else 'not_run',
                reason='Both training-budget gates passed' if gate['proceed_migration'] else 'At least one training-budget criterion failed; migration prohibited',
                gate_sha256=sha(root/'gate.json'),scientific_runs=0,prior_known_input_probes=PROBES[1:]))
    save(out/'summary.json',summary)
    assert all(sha(root/path)==digest for path,digest in input_hashes.items()) and sha(Path(__file__))==source_hash
    save(out/'input-sha256-audit.json',dict(inputs=input_hashes,analysis_source_sha256=source_hash))
    save(out/'validation.json',dict(status='pass',stage=stage,selfcheck_cases=checks,selected_training_minima_checked=60,
        unique_graph_comparisons=len(per_graph),selected_policy_probe_rows=len(per_policy),paired_contrast_rows=len(contrasts),
        original_reference_denominators={p:int(originals[p][:,:,0].sum()) for p in probes},inputs_unchanged=True,source_sha256=source_hash,
        outputs={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and 'audit' not in p.name}))
    print(json.dumps(dict(status='pass',stage=stage,unique_graphs=len(selected_graphs),
        proceed_migration=summary.get('gate',{}).get('proceed_migration')),indent=2))


if __name__=='__main__':main()
