#!/usr/bin/env python3
"""Prospectively fixed calibration analysis; reads only explicit trajectories.

No inference over graph populations, CI, p-value, data-driven dose expansion,
outlier deletion, or choice of an example by its outcome is performed here.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
PROBES = ['tonic', 'global_burst', 'focal_burst']
WINDOWS = {'all': (0, 300), 'early': (0, 80), 'middle': (80, 150), 'late': (150, 300)}
GROUPS = ['extensive', 'swap', 'jitter_1e-4', 'jitter_1e-3', 'jitter_1e-2']
CHANNELS = ['voltage', 'exc_conductance', 'inh_conductance']


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table(path, rows):
    assert rows
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def readcsv(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def floats(bits):
    return np.ascontiguousarray(bits, dtype=np.uint32).view(np.float32).astype(np.float64)


def state(array):
    return floats(array[:, :, 1:4])


def first_true(mask):
    indices = np.flatnonzero(mask)
    return int(indices[0]) if len(indices) else None


def observation_ms(slot):
    return (slot + 1) * .1 if slot is not None else None


def rms(array):
    return float(np.sqrt(np.mean(np.asarray(array, dtype=np.float64) ** 2)))


def ratio(num, den):
    return float(num / den) if den else None


def description(values):
    values = [float(value) for value in values if value is not None]
    if not values:
        return {'n': 0, 'median': None, 'minimum': None, 'maximum': None}
    return {'n': len(values), 'median': float(np.median(values)),
            'minimum': min(values), 'maximum': max(values)}


def group(record):
    if record['type'] != 'jitter':
        return record['type']
    epsilon = float(record['epsilon'])
    return {1e-4: 'jitter_1e-4', 1e-3: 'jitter_1e-3', 1e-2: 'jitter_1e-2'}[epsilon]


def compare(reference, candidate, scale, lo=0, hi=300):
    a = reference[lo:hi, :, 0].astype(np.int64)
    b = candidate[lo:hi, :, 0].astype(np.int64)
    assert (hi - lo) % 10 == 0
    aa = a.reshape(-1, 10, 125).sum(axis=1)
    bb = b.reshape(-1, 10, 125).sum(axis=1)
    cell_abs = int(np.abs(aa - bb).sum())
    pop_abs = int(np.abs(aa.sum(axis=1) - bb.sum(axis=1)).sum())
    denom = int(a.sum())
    assert pop_abs <= cell_abs
    first = first_true(np.any(a != b, axis=1))
    first = first + lo if first is not None else None
    difference = state(candidate[lo:hi]) - state(reference[lo:hi])
    normalized = difference / scale
    result = dict(reference_spikes=denom, candidate_spikes=int(b.sum()),
        chunk_bin_l1_numerator=cell_abs, population_bin_l1_numerator=pop_abs,
        chunk_bin_l1_relative=ratio(cell_abs, denom),
        population_bin_l1_relative=ratio(pop_abs, denom),
        population_to_chunk_l1_ratio=ratio(pop_abs, cell_abs),
        cancellation_fraction=1.0 - pop_abs / cell_abs if cell_abs else None,
        spike_mismatch_cells=int(np.count_nonzero(a != b)),
        population_spike_mismatch_slots=int(np.count_nonzero(a.sum(axis=1) != b.sum(axis=1))),
        first_spike_difference_slot=first, first_spike_difference_ms=observation_ms(first),
        all_recorded_bits_equal=bool(np.array_equal(reference[lo:hi], candidate[lo:hi])),
        state_rms_standardized=rms(normalized),
        voltage_rms_absolute=rms(difference[:, :, 0]),
        voltage_max_abs=float(np.abs(difference[:, :, 0]).max()),
        exc_conductance_rms_absolute=rms(difference[:, :, 1]),
        inh_conductance_rms_absolute=rms(difference[:, :, 2]))
    # Independent scalar integer reduction checks the scientific L1 definition.
    scalar_cell = scalar_pop = 0
    for start in range(0, len(a), 10):
        delta = [sum(int(b[t, k]) - int(a[t, k]) for t in range(start, start + 10))
                 for k in range(125)]
        scalar_cell += sum(abs(value) for value in delta)
        scalar_pop += abs(sum(delta))
    assert (scalar_cell, scalar_pop) == (cell_abs, pop_abs)
    return result


def swap_input_diagnostic(record, audit, reference, comparison):
    a, c = int(audit['a']), int(audit['c'])
    weight = float(floats([audit['weight_bits']])[0])
    source_difference = (reference[:, a, 0].astype(np.int64)
                         - reference[:, c, 0].astype(np.int64))
    # Source slot n arrives at n+2. Only n=0..297 arrives in this observation.
    eligible = source_difference[:298]
    first = first_true(eligible != 0)
    full_l1 = 2 * weight * int(np.abs(eligible).sum())
    return dict(stem=record['stem'], graph=record['graph'], seed=record['seed'],
        probe=record['probe'], arm=int(audit['arm']), source_a=a, old_target_b=int(audit['b']),
        source_c=c, old_target_d=int(audit['d']), weight=weight,
        changed_original_edges=int(audit['changed_edges']),
        changed_original_fraction=int(audit['changed_edges']) / int(audit['edge_count']),
        eligible_source_slots=298,
        source_spike_difference_slots=int(np.count_nonzero(eligible)),
        excluded_late_source_difference_slots=int(np.count_nonzero(source_difference[298:])),
        first_source_difference_slot=first,
        first_eligible_arrival_slot=first + 2 if first is not None else None,
        shared_input_difference_l1=full_l1,
        shared_input_difference_frobenius=float(np.sqrt(2) * weight * np.linalg.norm(eligible)),
        shared_input_identical_in_window=bool(not np.any(eligible)),
        output_spikes_identical=comparison['spike_mismatch_cells'] == 0,
        output_recorded_bits_identical=comparison['all_recorded_bits_equal'],
        chunk_bin_l1_relative=comparison['chunk_bin_l1_relative'],
        first_spike_difference_slot=comparison['first_spike_difference_slot'])


def jitter_diagnostics(record, reference, candidate, metadata, initial_rows):
    initial = np.array([int(row['voltage_bits']) for row in initial_rows], dtype=np.uint32)
    assert [int(row['chunk']) for row in initial_rows] == list(range(125))
    assert initial.tolist() == metadata['initial_voltage_bits']
    values = floats(initial)
    deviations = values + 65.0
    assert np.sum(deviations[:100]) == 0 and np.sum(deviations[100:]) == 0
    assert np.count_nonzero(deviations) == 124
    out = []
    for k in range(125):
        first_step = metadata['first_step_slot'][k]
        pre = metadata['first_pre_update_voltage_bits'][k]
        if first_step is not None:
            assert pre == int(initial[k]), 'dormant initialization was altered before its first update'
        same = np.all(reference[:, k, :] == candidate[:, k, :], axis=1)
        same_continuous = np.all(reference[:, k, 1:8] == candidate[:, k, 1:8], axis=1)
        # A transient crossing is not permanent erasure; report both separately.
        permanently_same = np.logical_and.accumulate(same[::-1])[::-1]
        baseline_reset = first_true(reference[:, k, 0] > 0)
        candidate_reset = first_true(candidate[:, k, 0] > 0)
        common_reset = first_true((reference[:, k, 0] > 0) & (candidate[:, k, 0] > 0))
        changed = first_true(reference[:, k, 0] != candidate[:, k, 0])
        out.append(dict(stem=record['stem'], seed=record['seed'], probe=record['probe'],
            epsilon=float(record['epsilon']), chunk=k, population='E' if k < 100 else 'I',
            initial_voltage_bits=int(initial[k]), actual_initial_delta=float(deviations[k]),
            initial_delta_ulp=abs(int(initial[k]) - int(np.float32(-65).view(np.uint32))),
            first_step_slot=first_step, first_pre_update_voltage_bits=pre,
            initialization_preserved_until_first_step=pre == int(initial[k]) if first_step is not None else None,
            baseline_first_reset_slot=baseline_reset, candidate_first_reset_slot=candidate_reset,
            first_common_reset_slot=common_reset,
            first_recorded_state_equal_slot=first_true(same),
            first_continuous_state_equal_slot=first_true(same_continuous),
            permanently_recorded_state_equal_from_slot=first_true(permanently_same),
            first_spike_difference_slot=changed,
            all_fields_equal_at_first_common_reset=bool(same[common_reset]) if common_reset is not None else None,
            max_absolute_voltage_difference=float(np.abs(floats(candidate[:, k, 1]) - floats(reference[:, k, 1])).max()),
            final_recorded_state_equal=bool(same[-1])))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / 'analysis'
    assert not (out / 'analysis-complete.json').exists(), 'Preserve completed analysis'
    # study.py owns the experiment lock; analyses add no mutable source inputs.
    sys.path.insert(0, str(root))
    import study
    study.check_lock()
    assert load(root / 'validation.json')['status'] == 'pass'
    out.mkdir(exist_ok=True)
    inputs = {}

    def track(path):
        path = Path(path)
        inputs[str(path.relative_to(root))] = sha(path)
        return path

    complete = load(track(root / 'run-complete.json'))
    records = complete['runs']
    assert len(records) == 231
    assert {kind: sum(r['type'] == kind for r in records) for kind in ['original', 'swap', 'jitter']} == {
        'original': 3, 'swap': 57, 'jitter': 171}
    audit_records = load(track(root / 'graph-audit.json'))
    graph_audits = {record['graph']: record for record in audit_records if record['type'] == 'swap'}
    assert len(graph_audits) == 19
    originals = {}
    arrays = {}
    metadata = {}
    for record in records:
        path = track(root / 'runs' / (record['stem'] + '.npz'))
        if 'npz_sha256' in record:
            assert sha(path) == record['npz_sha256']
        with np.load(path) as container:
            array = container['state_bits']
        assert array.shape == (300, 125, 10) and array.dtype == np.uint32
        assert np.all(np.isfinite(floats(array[:, :, 1:8])))
        arrays[record['stem']] = array
        metadata[record['stem']] = load(track(path.with_suffix('.json')))
        if record['type'] == 'original':
            assert record['probe'] not in originals
            originals[record['probe']] = array
    assert set(originals) == set(PROBES)
    scales = {probe: state(originals[probe]).std(axis=(0, 1), ddof=0) for probe in PROBES}
    assert all(np.all(scale > 0) for scale in scales.values())
    scale_document = {probe: dict(zip(CHANNELS, map(float, value))) for probe, value in scales.items()}
    save(out / 'frozen-reference-scales.json', dict(fit='original explicit trajectory only; ddof=0; all 300 slots and 125 chunks',
        source_shas={probe: inputs[f'runs/original__{probe}.npz'] for probe in PROBES}, scales=scale_document))
    legacy_records = []
    for probe in PROBES:
        for name in ['original'] + [f'r{seed}' for seed in range(91001, 91020)]:
            stem = f'homogeneous__{name}__{probe}__explicit'
            path = track(root / 'legacy' / 'runs' / (stem + '.npz'))
            with np.load(path) as container:
                array = container['state_bits']
            assert array.shape == (300, 125, 10) and array.dtype == np.uint32
            if name == 'original':
                assert np.array_equal(array, originals[probe]), 'new baseline must exactly bridge archived 10-field trajectory'
            else:
                record = dict(stem=stem, type='extensive', seed=int(name[1:]), probe=probe,
                    epsilon=None, graph=name, initial_file=None)
                legacy_records.append(record)
                arrays[stem] = array
    comparisons, phases, curves, swap_rows, jitter_rows = [], [], [], [], []
    independent_checks = 0
    for record in records + legacy_records:
        probe = record['probe']
        reference = originals[probe]
        candidate = arrays[record['stem']]
        identity = dict(stem=record['stem'], group=group(record), type=record['type'], seed=record['seed'],
            probe=probe, epsilon=record['epsilon'], graph=record['graph'])
        measured = compare(reference, candidate, scales[probe])
        independent_checks += 1
        comparisons.append({**identity, **measured})
        for window, (lo, hi) in WINDOWS.items():
            phases.append({**identity, 'window': window, 'start_slot': lo, 'end_slot_exclusive': hi,
                **compare(reference, candidate, scales[probe], lo, hi)})
            independent_checks += 1
        a = reference[:, :, 0].astype(np.int64)
        b = candidate[:, :, 0].astype(np.int64)
        normalized = (state(candidate) - state(reference)) / scales[probe]
        cumulative_cell = cumulative_pop = 0
        denominator = int(a.sum())
        for lo in range(0, 300, 10):
            hi = lo + 10
            delta = b[lo:hi].sum(axis=0) - a[lo:hi].sum(axis=0)
            cumulative_cell += int(np.abs(delta).sum())
            cumulative_pop += abs(int(delta.sum()))
            curves.append({**identity, 'time_start_ms': lo * .1, 'time_end_ms': hi * .1,
                'chunk_l1_contribution_full_denominator': ratio(np.abs(delta).sum(), denominator),
                'population_l1_contribution_full_denominator': ratio(abs(int(delta.sum())), denominator),
                'cumulative_chunk_l1_full_denominator': ratio(cumulative_cell, denominator),
                'cumulative_population_l1_full_denominator': ratio(cumulative_pop, denominator),
                'state_rms_standardized': rms(normalized[lo:hi]),
                'chunk_spike_mismatch_cells': int(np.count_nonzero(a[lo:hi] != b[lo:hi]))})
        if record['type'] == 'swap':
            swap_rows.append(swap_input_diagnostic(record, graph_audits[record['graph']], reference, measured))
        elif record['type'] == 'jitter':
            initial_rows = readcsv(track(root / record['initial_file']))
            jitter_rows.extend(jitter_diagnostics(record, reference, candidate, metadata[record['stem']], initial_rows))
    summary = []
    keys = ['chunk_bin_l1_relative', 'population_bin_l1_relative', 'cancellation_fraction',
            'state_rms_standardized', 'voltage_rms_absolute', 'first_spike_difference_ms']
    for probe in PROBES:
        for name in GROUPS:
            rows = [r for r in comparisons if r['probe'] == probe and r['group'] == name]
            assert len(rows) == 19
            result = dict(probe=probe, group=name, n=19,
                spike_identical_runs=sum(r['spike_mismatch_cells'] == 0 for r in rows),
                all_recorded_bits_identical_runs=sum(r['all_recorded_bits_equal'] for r in rows),
                nonzero_chunk_bin_error_runs=sum(r['chunk_bin_l1_relative'] != 0 for r in rows),
                undefined_cancellation_runs=sum(r['cancellation_fraction'] is None for r in rows))
            for key in keys:
                for stat, value in description(r[key] for r in rows).items():
                    result[f'{key}_{stat}'] = value
            summary.append(result)
    summary_phases = []
    for probe in PROBES:
        for name in GROUPS:
            for window in WINDOWS:
                rows = [r for r in phases if r['probe'] == probe and r['group'] == name and r['window'] == window]
                assert len(rows) == 19
                result = dict(probe=probe, group=name, window=window, n=19)
                for key in keys[:5]:
                    for stat, value in description(r[key] for r in rows).items():
                        result[f'{key}_{stat}'] = value
                summary_phases.append(result)
    jitter_summary = []
    for record in records:
        if record['type'] != 'jitter':
            continue
        rows = [row for row in jitter_rows if row['stem'] == record['stem']]
        assert len(rows) == 125
        jitter_summary.append(dict(stem=record['stem'], probe=record['probe'], seed=record['seed'], epsilon=record['epsilon'],
            chunks_perturbed=sum(row['actual_initial_delta'] != 0 for row in rows),
            chunks_executed=sum(row['first_step_slot'] is not None for row in rows),
            chunks_changed_spikes=sum(row['first_spike_difference_slot'] is not None for row in rows),
            chunks_with_common_reset=sum(row['first_common_reset_slot'] is not None for row in rows),
            chunks_equal_at_first_common_reset=sum(row['all_fields_equal_at_first_common_reset'] is True for row in rows),
            chunks_equal_at_end=sum(row['final_recorded_state_equal'] for row in rows),
            actual_initial_max_abs=max(abs(row['actual_initial_delta']) for row in rows),
            max_absolute_voltage_difference=max(row['max_absolute_voltage_difference'] for row in rows)))
    for filename, rows in [('comparisons.csv', comparisons), ('phase-comparisons.csv', phases),
            ('curves-1ms.csv', curves), ('summary.csv', summary), ('phase-summary.csv', summary_phases),
            ('swap-input-diagnostics.csv', swap_rows), ('jitter-reset-diagnostics.csv', jitter_rows),
            ('jitter-reset-summary.csv', jitter_summary)]:
        table(out / filename, rows)
    save(out / 'summary.json', dict(status='pass', new_scientific_runs=231, archived_comparison_runs=57,
        archived_baseline_bridges=3, controls_per_group=19, groups=GROUPS, summaries=summary,
        swap_diagnostic_counts={probe: dict(n=19,
            shared_input_identical=sum(r['shared_input_identical_in_window'] for r in swap_rows if r['probe'] == probe),
            shared_input_identical_but_output_changed=sum(r['shared_input_identical_in_window'] and not r['output_spikes_identical'] for r in swap_rows if r['probe'] == probe),
            shared_input_changed_but_output_identical=sum(not r['shared_input_identical_in_window'] and r['output_spikes_identical'] for r in swap_rows if r['probe'] == probe)) for probe in PROBES},
        limits=['Single fixed original; descriptive finite-horizon calibration only',
            'Swap arms stratified 5/5/5/4, not a uniform random graph sample',
            'Initial-voltage perturbations are blockwise; within-chunk synchrony retained',
            'Jitter directions repeated across doses; probes and doses are not independent samples',
            'Common-source input differences are diagnostics, not nonlinear trajectory predictors',
            'Small initial differences can contract and be erased by common spike resets',
            'Cancellation fraction is computed within each graph/probe, not from a ratio of group medians']))
    save(out / 'metric-audit.json', dict(status='pass', scalar_integer_l1_reductions=independent_checks,
        archived_baselines_bitwise_equal=3, jitter_chunk_diagnostics=len(jitter_rows),
        zero_shared_input_is_reported_not_excluded=True,
        standardization='Per-probe original-only V,gE,gI std; ddof=0; frozen for all conditions/windows'))
    study.check_lock()
    assert all(sha(root / path) == digest for path, digest in inputs.items()), 'Analysis input changed'
    save(out / 'analysis-inputs-sha256.json', inputs)
    save(out / 'analysis-complete.json', dict(status='pass', new_scientific_runs=231,
        archived_structural_controls=57, comparisons=len(comparisons), source_sha256=sha(Path(__file__)),
        input_files_unchanged=True, outputs={str(path.relative_to(root)): sha(path)
            for path in sorted(out.iterdir()) if path.is_file() and path.name != 'analysis-complete.json'}))
    print('PASS: 231 new runs; 57 archived extensive controls; 3 exact archived baseline bridges.', flush=True)


if __name__ == '__main__':
    main()
