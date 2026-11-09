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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output_dir.resolve() if args.output_dir else root / 'analysis'
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Use a new empty output directory; do not replace a completed analysis.')
    out.mkdir(parents=True, exist_ok=True)
    input_hashes = {}
    source_hash = sha(Path(__file__))
    def track(path):
        path = Path(path)
        input_hashes[str(path.relative_to(root))] = sha(path)
        return path

    # Read only declared archived artifacts. No selected edge/candidate is
    # changed by evaluation of held-out trajectories.
    protocol = load(track(root / 'protocol.json'))
    selections = load(track(root / 'selection.json'))
    candidates = read_csv(track(root / 'candidates.csv'))
    aliases = load(track(root / 'graph-aliases.json'))
    records = load(track(root / 'run-complete.json'))['records']
    assert isinstance(protocol, dict)
    assert len(selections) == 40
    assert {(int(s['block']), s['policy']) for s in selections} == {
        (block, policy) for block in range(10) for policy in POLICIES}
    assert len(candidates) == 640
    by_candidate = {(int(c['block']), int(c['candidate'])): c for c in candidates}
    assert set(by_candidate) == {(b,c) for b in range(10) for c in range(64)}
    for s in selections:
        c = by_candidate[(int(s['block']), int(s['candidate']))]
        assert s['graph'] == c['graph']
        for key in SCORES:
            assert float(s[key]) == float(c[key])
            assert math.isfinite(float(s[key])) and float(s[key]) >= 0
        if s['policy'] != 'random':
            key = 'J_' + s['policy']
            minimum = min(float(row[key]) for (b,_),row in by_candidate.items() if b==int(s['block']))
            assert float(s[key]) == minimum, 'Chosen policy is not a training-score minimizer'
    selected_graphs = sorted({aliases[s['graph']] for s in selections})
    record_map = {(r['graph'], r['probe']): r for r in records}
    assert len(record_map) == len(records), 'Duplicate graph/probe runs'
    expected = {(g,p) for g in ['original'] + selected_graphs for p in PROBES}
    assert expected.issubset(record_map), 'Missing original or selected-graph run'

    originals = {}; arrays = {}; counters = {}; edge_counts = {}
    for graph in ['original'] + selected_graphs:
        graph_rows = read_csv(track(root / 'graphs' / (graph + '.csv')))
        edge_counts[graph] = len(graph_rows)
        assert edge_counts[graph] == 2845, 'All connections must still be present'
        for probe in PROBES:
            record = record_map[(graph,probe)]
            assert record['stem'] == f'{graph}__{probe}'
            path = root / 'runs' / (record['stem'] + '.npz')
            with np.load(track(path)) as container:
                array = container['state_bits']
            assert array.shape == (300,125,10) and array.dtype == np.uint32
            assert np.all((array[:,:,0]==0)|(array[:,:,0]==100))
            fields=np.ascontiguousarray(array[:,:,1:8]).view(np.float32)
            assert np.all(np.isfinite(fields))
            assert np.all(array[:,:,9]<=2)
            array_counts=read_csv(track(path.with_suffix('.csv')))
            assert len(array_counts)==300
            assert [int(r['spikes']) for r in array_counts] == array[:,:,0].sum(axis=1).tolist()
            metadata=load(track(path.with_suffix('.json')))
            for ext,key in [('.npz','npz_sha256'),('.csv','csv_sha256'),('.json','json_sha256')]:
                if key in record: assert sha(path.with_suffix(ext))==record[key]
            assert metadata['timing_is_performance_benchmark'] is False
            assert metadata['external_input_positive_finite'] is True
            counters[(graph,probe)] = dict(
                recurrent_messages=sum(int(r['recurrent_messages']) for r in array_counts),
                active_source_edge_visits=sum(int(r['active_source_edge_visits']) for r in array_counts),
                active_chunk_slot_sum=sum(int(r['active_chunks']) for r in array_counts),
                edge_count=edge_counts[graph])
            arrays[(graph,probe)] = array
            if graph=='original': originals[probe]=array
    scales={p:float_fields(originals[p]).std(axis=(0,1),ddof=0) for p in PROBES}
    save(out/'reference-scales.json',dict(definition='Per-probe original-only V,gE,gI std over all 300 slots and 125 chunks, ddof=0.',
        zero_scale_behavior='standardized state RMS is null if any reference scale is zero',
        scales={p:dict(zip(['V','gE','gI'],map(float,v))) for p,v in scales.items()}))
    checks=selfchecks(); per_graph=[]; metrics={}
    for graph in ['original']+selected_graphs:
        for probe in PROBES:
            measurement=compare(originals[probe],arrays[(graph,probe)],scales[probe])
            row=dict(graph=graph,probe=probe,**measurement,**counters[(graph,probe)])
            metrics[(graph,probe)]=row;per_graph.append(row)
    per_policy=[]; endpoints=[]; policy_map={}
    for s in sorted(selections,key=lambda s:(int(s['block']),POLICIES.index(s['policy']))):
        identity=dict(block=int(s['block']),policy=s['policy'],candidate=int(s['candidate']),
                      **{k:float(s[k]) for k in SCORES})
        canonical=aliases[s['graph']]
        for probe in PROBES:
            row={**identity,**metrics[(canonical,probe)],'graph':s['graph'],'canonical_graph':canonical}
            per_policy.append(row); policy_map[(int(s['block']),s['policy'],probe)]=row
        endpoints.append({**identity,'graph':s['graph'],'canonical_graph':canonical,
            'heldout_raw_slot_l1_mean':complete_mean([metrics[(canonical,p)]['raw_slot_l1'] for p in HELDOUT]),
            'train_raw_slot_l1':metrics[(canonical,'train')]['raw_slot_l1']})
    endpoint_map={(r['block'],r['policy']):r for r in endpoints}
    contrasts=[]
    for block in range(10):
        for probe in PROBES+['heldout_mean']:
            for comparator in COMPARATORS:
                left=endpoint_map[(block,'coactivity')];right=endpoint_map[(block,comparator)]
                if probe=='heldout_mean':
                    a=left['heldout_raw_slot_l1_mean'];b=right['heldout_raw_slot_l1_mean']
                else:
                    a=policy_map[(block,'coactivity',probe)]['raw_slot_l1']
                    b=policy_map[(block,comparator,probe)]['raw_slot_l1']
                contrasts.append(dict(block=block,probe=probe,comparator=comparator,
                    coactivity_graph=left['graph'],comparison_graph=right['graph'],
                    coactivity_loss=a,comparator_loss=b,
                    difference_coactivity_minus_comparator=a-b if a is not None and b is not None else None,
                    same_selected_graph=left['canonical_graph']==right['canonical_graph']))
    contrast_summary=[]
    for probe in PROBES+['heldout_mean']:
        for comparator in COMPARATORS:
            rows=[r for r in contrasts if r['probe']==probe and r['comparator']==comparator]
            values=[r['difference_coactivity_minus_comparator'] for r in rows]
            valid=[v for v in values if v is not None]
            contrast_summary.append(dict(probe=probe,comparator=comparator,**describe(values),
                coactivity_better=sum(v < -SIGN_TOLERANCE for v in valid),
                tied=sum(abs(v)<=SIGN_TOLERANCE for v in valid),
                coactivity_worse=sum(v>SIGN_TOLERANCE for v in valid),
                same_selected_graph=sum(r['same_selected_graph'] for r in rows)))
    metric_summary=[]
    for probe in PROBES:
        for policy in POLICIES:
            for metric in METRICS:
                rows=[r for r in per_policy if r['probe']==probe and r['policy']==policy]
                metric_summary.append(dict(probe=probe,policy=policy,metric=metric,
                    undefined=sum(r[metric] is None for r in rows),**describe(r[metric] for r in rows)))
    endpoint_summary=[dict(policy=p,**describe(r['heldout_raw_slot_l1_mean'] for r in endpoints if r['policy']==p))
                      for p in POLICIES]
    primary=next(r for r in contrast_summary if r['probe']=='heldout_mean' and r['comparator']=='random')
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
        primary='Compute each of the three held-out normalized raw-slot losses, take their equal-weight mean within each block/policy, then subtract comparator from coactivity. No dropping undefined held-out inputs.',
        inference='Ten descriptive matched graph-search banks on one original. No independent-input or independent-network sample claim, p-value, or bootstrap interval.'))
    for name,rows in [('per_graph',per_graph),('per_policy',per_policy),('per_block_endpoints',endpoints),
                      ('paired_contrasts',contrasts),('contrast_summary',contrast_summary),
                      ('metric_summary',metric_summary)]:
        write_csv(out/(name+'.csv'),rows)
    summary=dict(status='pass',analysis='Locked matched-block selector comparison',
        blocks=10,candidates_per_block=64,policies=POLICIES,probes=PROBES,
        selected_policy_records=40,unique_selected_graphs=len(selected_graphs),
        selected_graph_runs=len(per_graph)-4,reference_graph_runs=4,
        primary_definition='Within each block: unweighted mean of normalized raw-slot identified L1 across all three held-out inputs; coactivity minus random. Negative favors coactivity.',
        primary_complete=primary['n']==10,primary=primary,
        heldout_policy_endpoints=endpoint_summary,contrasts=contrast_summary,
        metric_summaries=metric_summary,numerical_sign_tolerance=SIGN_TOLERANCE,
        performance_claim=False,edge_counts_all_2845=True,
        limits=['One original graph; blocks randomize candidate sets, not biological network replicates.',
                'The three held-out protocols share graph identities and are not independent network samples.',
                'Coactivity score uses uncentered same-time second-order activity, not sequence order or a memory mechanism.',
                'Independent per-source shuffling changes cross-source coactivity while retaining each source count distribution.',
                'Every graph retains 2845 edges; endpoint-change budget is not storage reduction or computational compression.',
                'Recorded loop timing contains instrumentation and is excluded from performance comparisons.',
                'Rcount is undefined when raw-slot discrepancy is zero; its conditional summaries have explicit denominators.',
                'No p-values, bootstrap intervals or post-test policy/metric selection.'],
        analyzer_sha256=source_hash)
    save(out/'summary.json',summary)
    assert all(sha(root/path)==digest for path,digest in input_hashes.items())
    assert sha(Path(__file__))==source_hash
    # Provenance has raw runtime/timestamp-bearing JSON hashes. Keep it distinct
    # from deterministic numerical files in the fresh-run byte comparison.
    save(out/'input-sha256-audit.json',dict(inputs=input_hashes,analysis_source_sha256=source_hash))
    save(out/'validation.json',dict(status='pass',selfcheck_cases=checks,
        selected_training_minima_checked=30,unique_graph_comparisons=len(per_graph),
        independent_integer_reductions=2*len(per_graph),full_tail_distance_crosschecks=len(per_graph),
        selected_policy_probe_rows=len(per_policy),paired_contrast_rows=len(contrasts),
        original_reference_denominators={p:int(originals[p][:,:,0].sum()) for p in PROBES},
        inputs_unchanged=True,source_sha256=source_hash,
        outputs={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and 'audit' not in p.name}))
    print(json.dumps(dict(status='pass',primary=primary,primary_complete=primary['n']==10,
                         unique_selected_graphs=len(selected_graphs)),indent=2))


if __name__=='__main__':
    main()
