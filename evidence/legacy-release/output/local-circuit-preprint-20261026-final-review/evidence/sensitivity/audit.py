#!/usr/bin/env python3
"""Independent, read-only validation of completed sensitivity trajectories.

No simulation, graph generation, metric import, or fitting is performed. The
only write is the final independent-audit.json after every assertion passes.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
PROBES = ('tonic', 'global_burst', 'focal_burst')
SWAP_SEEDS = tuple(range(93001, 93020))
JITTER_SEEDS = tuple(range(94001, 94020))
DOSES = (('e1e-4', 1e-4), ('e1e-3', 1e-3), ('e1e-2', 1e-2))
WINDOWS = {'all': (0, 300), 'early': (0, 80), 'middle': (80, 150), 'late': (150, 300)}
COUNT_HEADER = ['step', 'spikes', 'recurrent_messages', 'active_source_edge_visits', 'active_chunks']
DEFAULT_V_BITS = int(np.array([-65.0], dtype='<f4').view('<u4')[0])


class Evidence:
    def __init__(self, root):
        self.root = root.resolve()
        self.before = {}

    def path(self, relative):
        path = (self.root / relative).resolve()
        path.relative_to(self.root)  # Reject a manifest escaping the study.
        assert path.is_file(), path
        key = str(path.relative_to(self.root))
        if key not in self.before:
            self.before[key] = self.hash(path)
        return path

    @staticmethod
    def hash(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def json(self, relative):
        return json.loads(self.path(relative).read_text())

    def rows(self, relative):
        with self.path(relative).open(newline='') as stream:
            return list(csv.DictReader(stream))

    def numeric_csv(self, relative, header):
        with self.path(relative).open(newline='') as stream:
            rows = list(csv.reader(stream))
        assert rows[0] == header, relative
        return np.array([[int(x) for x in row] for row in rows[1:]], dtype=np.int64)

    def array(self, relative):
        with np.load(self.path(relative), allow_pickle=False) as container:
            assert container.files == ['state_bits'], relative
            array = container['state_bits']
        assert array.shape == (300, 125, 10) and array.dtype == np.dtype('uint32'), relative
        assert np.isfinite(np.ascontiguousarray(array[:, :, 1:8]).view(np.float32)).all(), relative
        assert set(np.unique(array[:, :, 0])).issubset({0, 100}), relative
        assert set(np.unique(array[:, :, 9])).issubset({0, 1, 2}), relative
        assert np.all(array[:, :, 8] <= np.arange(300)[:, None] + 2), relative
        return array

    def manifests(self):
        lock = self.json('experiment-lock.json')
        assert lock['expected_runs'] == 231 and lock['scientific_runs_started'] is False
        for relative, expected in lock['files'].items():
            assert self.hash(self.path(relative)) == expected, relative
        inherited = self.json('inherited-inputs-sha256.json')
        for relative, expected in inherited.items():
            assert self.hash(self.path(relative)) == expected, relative
        for folder in ('source', 'legacy', 'graphs', 'initial'):
            actual = {str(p.relative_to(self.root)) for p in (self.root / folder).rglob('*') if p.is_file()}
            frozen = {key for key in lock['files'] if key.startswith(folder + '/')}
            assert actual == frozen, (folder, sorted(actual ^ frozen))
        return lock, inherited

    def unchanged(self):
        for relative, expected in self.before.items():
            assert self.hash(self.root / relative) == expected, relative


def graph(evidence, relative):
    array = evidence.numeric_csv(relative, ['arm', 'source', 'target', 'weight_bits', 'delay'])
    assert array.shape == (2845, 5)
    assert np.all((array[:, 1:3] >= 0) & (array[:, 1:3] < 125))
    assert np.all(array[:, 1] != array[:, 2]) and np.all(array[:, 4] == 1)
    assert np.all((array[:, 1] >= 100) * 2 + (array[:, 2] >= 100) == array[:, 0])
    assert len(set(map(tuple, array[:, 1:3]))) == 2845
    weights = np.ascontiguousarray(array[:, 3], dtype='<u4').view('<f4')
    assert np.all(np.isfinite(weights) & (weights > 0))
    return array


def audit_graphs(evidence):
    original = graph(evidence, 'graphs/original.csv')
    assert np.array_equal(original, graph(evidence, 'legacy/graphs/original.csv'))
    assert np.array_equal(original, graph(evidence, 'graphs/inverse-sham.csv'))
    rows = evidence.json('graph-audit.json')
    assert len(rows) == 20 and len({r['graph'] for r in rows}) == 20
    by_name = {r['graph']: r for r in rows}
    found = {'original': original, 'inverse-sham': original}
    arms = [0] * 5 + [1] * 5 + [2] * 5 + [3] * 4
    for seed, arm in zip(SWAP_SEEDS, arms):
        name = f'swap{seed}'
        candidate = graph(evidence, f'graphs/{name}.csv')
        report = by_name[name]
        assert report['seed'] == seed and report['arm'] == arm
        assert np.array_equal(original[:, [0, 1, 3, 4]], candidate[:, [0, 1, 3, 4]])
        changed = np.flatnonzero(original[:, 2] != candidate[:, 2])
        assert len(changed) == 2 and set(map(int, changed)) == set(report['rows'])
        i, j = changed
        a, b = map(int, original[i, 1:3])
        c, d = map(int, original[j, 1:3])
        assert len({a, b, c, d}) == 4
        assert original[i, 0] == original[j, 0] == arm
        assert np.array_equal(original[i, 3:5], original[j, 3:5])
        assert candidate[i, 2] == d and candidate[j, 2] == b
        ri, rj = report['rows']
        assert [report[key] for key in ('a', 'b', 'c', 'd')] == [int(original[ri, 1]), int(original[ri, 2]), int(original[rj, 1]), int(original[rj, 2])]
        assert report['weight_bits'] == int(original[ri, 3])
        old_pairs, new_pairs = set(map(tuple, original[:, 1:3])), set(map(tuple, candidate[:, 1:3]))
        assert len(old_pairs - new_pairs) == len(new_pairs - old_pairs) == 2
        assert (a, d) not in old_pairs and (c, b) not in old_pairs
        for projection in range(4):
            old = original[original[:, 0] == projection]
            new = candidate[candidate[:, 0] == projection]
            for endpoint in (1, 2):
                assert np.array_equal(np.bincount(old[:, endpoint], minlength=125),
                                      np.bincount(new[:, endpoint], minlength=125))
                assert collections.Counter(map(tuple, old[:, [endpoint, 3]])) == collections.Counter(map(tuple, new[:, [endpoint, 3]]))
        assert report['changed_edges'] == 2 and report['symmetric_difference_edges'] == 4
        assert report['graph_sha256'] == evidence.hash(evidence.path(f'graphs/{name}.csv'))
        found[name] = candidate
    return found


def initial_bits(evidence, relative):
    rows = evidence.numeric_csv(relative, ['chunk', 'voltage_bits'])
    assert rows.shape == (125, 2) and np.array_equal(rows[:, 0], np.arange(125))
    assert np.all((rows[:, 1] >= 0) & (rows[:, 1] <= 2**32 - 1))
    bits = rows[:, 1].astype('<u4')
    assert np.isfinite(bits.view('<f4')).all()
    return bits


def audit_initials(evidence):
    zero = initial_bits(evidence, 'initial/zero.csv')
    assert np.all(zero == DEFAULT_V_BITS)
    output = {'initial/zero.csv': zero}
    audit = evidence.json('initial-audit.json')
    assert len(audit) == 57 and len({r['name'] for r in audit}) == 57
    by_name = {r['name']: r for r in audit}
    ulp = abs(float(np.spacing(np.float32(-65.0))))
    for seed in JITTER_SEEDS:
        previous_sign = None
        previous_magnitude = 0.0
        for label, epsilon in DOSES:
            name = f'jitter{seed}__{label}'
            relative = f'initial/{name}.csv'
            bits = initial_bits(evidence, relative)
            delta = bits.view('<f4').astype(np.float64) + 65.0
            signs = np.sign(delta).astype(np.int64)
            assert collections.Counter(signs[:100]) == {-1: 50, 1: 50}
            assert collections.Counter(signs[100:]) == {-1: 12, 0: 1, 1: 12}
            assert delta[:100].sum() == delta[100:].sum() == 0
            expected = np.asarray(-65.0 + epsilon * signs, dtype='<f4').view('<u4')
            assert np.array_equal(bits, expected)
            if previous_sign is not None:
                assert np.array_equal(signs, previous_sign)
            magnitude = float(np.max(np.abs(delta)))
            assert magnitude > previous_magnitude and np.count_nonzero(delta) == 124
            report = by_name[name]
            assert report['seed'] == seed and report['epsilon'] == epsilon
            assert report['signs'] == signs.tolist()
            assert report['actual_linf'] == magnitude and report['ulp_steps'] == magnitude / ulp
            assert report['initial_sha256'] == evidence.hash(evidence.path(relative))
            previous_sign, previous_magnitude = signs, magnitude
            output[relative] = bits
    return output


def expected_records():
    expected = {}
    for probe in PROBES:
        expected[f'original__{probe}'] = ('original', None, probe, None, 'original', 'initial/zero.csv')
    for seed in SWAP_SEEDS:
        for probe in PROBES:
            expected[f'swap{seed}__{probe}'] = ('swap', seed, probe, None, f'swap{seed}', 'initial/zero.csv')
    for seed in JITTER_SEEDS:
        for label, epsilon in DOSES:
            for probe in PROBES:
                expected[f'jitter{seed}__{label}__{probe}'] = ('jitter', seed, probe, epsilon, 'original', f'initial/jitter{seed}__{label}.csv')
    return expected


def audit_run(evidence, record, graphs, initials, folder='runs'):
    prefix = f'{folder}/{record["stem"]}'
    for ext in ('npz', 'csv', 'json'):
        assert evidence.hash(evidence.path(f'{prefix}.{ext}')) == record[f'{ext}_sha256']
    array = evidence.array(prefix + '.npz')
    counts = evidence.numeric_csv(prefix + '.csv', COUNT_HEADER)
    assert counts.shape == (300, 5) and np.array_equal(counts[:, 0], np.arange(300))
    assert np.array_equal(counts[:, 1], array[:, :, 0].sum(axis=1, dtype=np.int64))
    degree = np.bincount(graphs[record['graph']][:, 1], minlength=125)
    messages = np.sum((array[:, :, 0] > 0) * degree[None, :], axis=1, dtype=np.int64)
    assert np.array_equal(counts[:, 2], messages) and np.array_equal(counts[:, 3], messages)
    assert np.all((counts[:, 4] >= 0) & (counts[:, 4] <= 125))
    metadata = evidence.json(prefix + '.json')
    assert (metadata['steps'], metadata['chunks'], metadata['units_per_chunk'], metadata['columns']) == (300, 125, 100, 10)
    assert metadata['mode'] == 'explicit' and metadata['timing_is_performance_benchmark'] is False
    assert metadata['instrumented_loop_seconds'] >= 0 and np.isfinite(metadata['instrumented_loop_seconds'])
    for key in ('initialization_before_add_chunk', 'initial_queues_empty',
                'other_initial_fields_match_frozen_harness', 'within_chunk_equality_initial_and_all_slots'):
        assert metadata[key] is True
    assert metadata['initial_slot'] == 0 and metadata['within_chunk_checks'] == 37625
    initial = initials[record['initial_file']]
    assert metadata['initial_voltage_bits'] == initial.tolist()
    first_slots, pre_bits = metadata['first_step_slot'], metadata['first_pre_update_voltage_bits']
    assert len(first_slots) == len(pre_bits) == 125
    for k, (slot, bits) in enumerate(zip(first_slots, pre_bits)):
        assert (slot is None) == (bits is None)
        assert slot is None or (isinstance(slot, int) and 0 <= slot < 300 and bits == int(initial[k]))
        before = array[:300 if slot is None else slot, k, :]
        assert np.all(before[:, 1] == initial[k])
        assert np.all(before[:, [0, 2, 3, 4, 5, 6, 7, 8, 9]] == 0)
    return array


def independent_metrics(reference, candidate, scale, lo, hi):
    # Integer bin reductions are derived directly from source NPZ arrays. No
    # study/analyze module is imported and no existing metric helper is used.
    a = reference[lo:hi, :, 0].astype(np.int64)
    b = candidate[lo:hi, :, 0].astype(np.int64)
    chunk_total = population_total = 0
    for start in range(0, hi - lo, 10):
        vector = np.sum(b[start:start + 10], axis=0, dtype=np.int64) - np.sum(a[start:start + 10], axis=0, dtype=np.int64)
        chunk_total += sum(abs(int(value)) for value in vector)
        population_total += abs(sum(map(int, vector)))
    denominator = int(a.sum(dtype=np.int64))
    assert population_total <= chunk_total
    different = np.nonzero(np.any(a != b, axis=1))[0]
    first = int(different[0]) + lo if len(different) else None
    x = np.ascontiguousarray(reference[lo:hi, :, 1:4]).view(np.float32).astype(np.float64)
    y = np.ascontiguousarray(candidate[lo:hi, :, 1:4]).view(np.float32).astype(np.float64)
    delta = y - x
    return dict(reference_spikes=denominator, candidate_spikes=int(b.sum(dtype=np.int64)),
        chunk_bin_l1_numerator=chunk_total, population_bin_l1_numerator=population_total,
        chunk_bin_l1_relative=chunk_total / denominator if denominator else None,
        population_bin_l1_relative=population_total / denominator if denominator else None,
        population_to_chunk_l1_ratio=population_total / chunk_total if chunk_total else None,
        cancellation_fraction=1 - population_total / chunk_total if chunk_total else None,
        spike_mismatch_cells=int(np.sum(a != b)),
        population_spike_mismatch_slots=int(np.sum(a.sum(axis=1) != b.sum(axis=1))),
        first_spike_difference_slot=first,
        first_spike_difference_ms=(first + 1) * .1 if first is not None else None,
        all_recorded_bits_equal=bool(np.array_equal(reference[lo:hi], candidate[lo:hi])),
        state_rms_standardized=float(np.sqrt(np.mean((delta / scale) ** 2))),
        voltage_rms_absolute=float(np.sqrt(np.mean(delta[:, :, 0] ** 2))),
        voltage_max_abs=float(np.max(np.abs(delta[:, :, 0]))),
        exc_conductance_rms_absolute=float(np.sqrt(np.mean(delta[:, :, 1] ** 2))),
        inh_conductance_rms_absolute=float(np.sqrt(np.mean(delta[:, :, 2] ** 2))))


def compare_metrics(row, expected):
    for key, value in expected.items():
        actual = row[key]
        if value is None:
            assert actual == '', (row['stem'], key, actual)
        elif isinstance(value, bool):
            assert actual == str(value), (row['stem'], key, actual, value)
        elif isinstance(value, int):
            assert int(actual) == value, (row['stem'], key, actual, value)
        else:
            assert np.isfinite(float(actual)) and np.isclose(float(actual), value, rtol=1e-12, atol=1e-12), (row['stem'], key, actual, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    evidence = Evidence(args.root)
    destination = evidence.root / 'independent-audit.json'
    assert not destination.exists(), 'Preserve completed independent audit'
    lock, inherited = evidence.manifests()
    protocol = evidence.json('protocol.json')
    assert protocol['scientific_runs']['total'] == 231 and protocol['technical_sham_runs'] == 6
    graphs, initials = audit_graphs(evidence), audit_initials(evidence)
    completed = evidence.json('run-complete.json')
    assert completed['status'] == 'pass' and completed['total_runs'] == 231
    records = completed['runs']
    expected = expected_records()
    assert len(records) == len(expected) == 231
    assert {r['stem'] for r in records} == set(expected)
    for record in records:
        assert tuple(record[key] for key in ('type', 'seed', 'probe', 'epsilon', 'graph', 'initial_file')) == expected[record['stem']]
    for suffix in ('npz', 'csv', 'json'):
        assert {p.stem for p in (evidence.root / 'runs').glob('*.' + suffix)} == set(expected)
    assert not list((evidence.root / 'runs').glob('*.bin'))

    comparisons = evidence.rows('analysis/comparisons.csv')
    phases = evidence.rows('analysis/phase-comparisons.csv')
    analysis_complete = evidence.json('analysis/analysis-complete.json')
    assert analysis_complete['status'] == 'pass' and analysis_complete['comparisons'] == 288
    for relative, digest in analysis_complete['outputs'].items():
        assert evidence.hash(evidence.path(relative)) == digest, relative
    assert len(comparisons) == 288 and len(phases) == 1152
    main_by_stem = {r['stem']: r for r in comparisons}
    phase_by_key = {(r['stem'], r['window']): r for r in phases}
    assert len(main_by_stem) == 288 and len(phase_by_key) == 1152
    baselines = {}
    for probe in PROBES:
        baseline_record = next(r for r in records if r['stem'] == f'original__{probe}')
        array = audit_run(evidence, baseline_record, graphs, initials)
        old_prefix = f'legacy/runs/homogeneous__original__{probe}__explicit'
        assert np.array_equal(array, evidence.array(old_prefix + '.npz'))
        assert evidence.path(f'runs/original__{probe}.csv').read_bytes() == evidence.path(old_prefix + '.csv').read_bytes()
        baselines[probe] = array
    scales = {}
    for probe, array in baselines.items():
        values = np.ascontiguousarray(array[:, :, 1:4]).view(np.float32).astype(np.float64)
        scales[probe] = np.std(values, axis=(0, 1), ddof=0)
        assert np.all(scales[probe] > 0)

    technical = evidence.json('technical-validation.json')
    assert technical['status'] == 'pass' and technical['new_originals_match_legacy_exact'] == 3
    assert len(technical['sham_runs']) == technical['technical_runs_not_scientific_conditions'] == 6
    assert {r['stem'] for r in technical['sham_runs']} == {f'{kind}__{probe}' for kind in ('zero_sham', 'inverse_sham') for probe in PROBES}
    for record in technical['sham_runs']:
        candidate = audit_run(evidence, record, graphs, initials, folder='technical')
        assert np.array_equal(candidate, baselines[record['probe']])
        assert evidence.path(f'technical/{record["stem"]}.csv').read_bytes() == evidence.path(f'runs/original__{record["probe"]}.csv').read_bytes()

    checked_stems = set()
    numeric_checks = 0
    def check_comparison(record, candidate):
        nonlocal numeric_checks
        stem, probe = record['stem'], record['probe']
        assert stem not in checked_stems
        row = main_by_stem[stem]
        assert row['type'] == record['type'] and row['probe'] == probe and row['graph'] == record['graph']
        assert row['seed'] == ('' if record['seed'] is None else str(record['seed']))
        if record['epsilon'] is None:
            assert row['epsilon'] == ''
        else:
            assert float(row['epsilon']) == record['epsilon']
        expected_group = record['type'] if record['type'] != 'jitter' else {1e-4: 'jitter_1e-4', 1e-3: 'jitter_1e-3', 1e-2: 'jitter_1e-2'}[record['epsilon']]
        assert row['group'] == expected_group
        measured = independent_metrics(baselines[probe], candidate, scales[probe], 0, 300)
        compare_metrics(row, measured)
        numeric_checks += 1
        for window, (lo, hi) in WINDOWS.items():
            phase = phase_by_key[(stem, window)]
            assert phase['probe'] == probe and int(phase['start_slot']) == lo and int(phase['end_slot_exclusive']) == hi
            compare_metrics(phase, independent_metrics(baselines[probe], candidate, scales[probe], lo, hi))
            numeric_checks += 1
        checked_stems.add(stem)

    for record in records:
        candidate = baselines[record['probe']] if record['type'] == 'original' else audit_run(evidence, record, graphs, initials)
        check_comparison(record, candidate)
    for seed in range(91001, 91020):
        for probe in PROBES:
            stem = f'homogeneous__r{seed}__{probe}__explicit'
            candidate = evidence.array(f'legacy/runs/{stem}.npz')
            check_comparison(dict(stem=stem, type='extensive', seed=seed, probe=probe, epsilon=None, graph=f'r{seed}'), candidate)
    assert checked_stems == set(main_by_stem)
    assert set(phase_by_key) == {(stem, window) for stem in checked_stems for window in WINDOWS}
    assert numeric_checks == 1440
    evidence.unchanged()
    result = dict(status='pass',independent_metric_implementation=True,simulations_started_by_audit=0,
        frozen_files_checked=len(lock['files']),inherited_files_checked=len(inherited),
        complete_locked_source_and_input_directories=True,all_inputs_unchanged_before_after=True,
        single_legal_swaps=19,exact_per_node_per_arm_degree_and_weight_multisets=True,
        balanced_initial_vectors=57,same_direction_across_doses=True,
        scientific_runs_checked=231,technical_shams_checked=6,baseline_legacy_exact_pairs=3,
        count_state_initial_and_first_execution_bits_consistent=True,
        within_chunk_equality_scope='asserted by unchanged instrumented driver for all 100 units; stored NPZ has one representative per chunk',
        archived_extensive_runs_reanalyzed=57,comparison_rows=288,phase_rows=1152,
        independently_recomputed_metric_sets=numeric_checks,float_tolerance=dict(rtol=1e-12,atol=1e-12),
        integer_l1_numerators_exact=True,paired_ratio_and_cancellation_checked=True,
        source_and_input_sha256=evidence.before)
    destination.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('status','scientific_runs_checked','technical_shams_checked','baseline_legacy_exact_pairs','independently_recomputed_metric_sets')}))


if __name__ == '__main__':
    main()
