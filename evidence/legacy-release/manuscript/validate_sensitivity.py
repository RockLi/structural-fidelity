#!/usr/bin/env python3
"""Gate the manuscript's sensitivity claims against supplied run evidence.

This post-experiment claim validator does not fit, select, or simulate. It reads
only --sensitivity-dir and checks that numerical claims and their qualifications
remain true when the complete study is rebuilt into a new directory.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PROBES = ('tonic', 'global_burst', 'focal_burst')
EXPECTED = {
    'tonic': dict(extensive_median=0.6900878293601004, extensive_minimum=0.45545796737766625,
        swap_median=0.0, swap_maximum=0.39146800501882056, extensive_population_median=0.11731493099121706,
        swap_population_median=0.0, extensive_cancellation_median=0.8330241187384044,
        swap_cancellation_median=0.6206896551724138, swap_bin_zero=10, shared_input_zero=2),
    'global_burst': dict(extensive_median=0.28989508558807286, extensive_minimum=0.23136388735505245,
        swap_median=0.013528437327443401, swap_maximum=0.09828823854224185, extensive_population_median=0.07205963556046384,
        swap_population_median=0.006350082827167311, extensive_cancellation_median=0.7593220338983051,
        swap_cancellation_median=0.5527851458885942, swap_bin_zero=7, shared_input_zero=0),
    'focal_burst': dict(extensive_median=0.8868563685636857, extensive_minimum=0.736449864498645,
        swap_median=0.07046070460704607, swap_maximum=0.2269647696476965, extensive_population_median=0.15311653116531165,
        swap_population_median=0.03523035230352303, extensive_cancellation_median=0.8252730109204368,
        swap_cancellation_median=0.4716417910447761, swap_bin_zero=8, shared_input_zero=2),
}
ACTUAL_DOSES = {1e-4: (0.00009918212890625, 13), 1e-3: (0.00099945068359375, 131),
                1e-2: (0.01000213623046875, 1311)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensitivity-dir', type=Path, default=ROOT / 'evidence/sensitivity')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.sensitivity_dir.resolve()
    tracked = {}

    def path(relative):
        target = (source / relative).resolve()
        target.relative_to(source)
        assert target.is_file(), target
        tracked.setdefault(str(target.relative_to(source)), digest(target))
        return target

    def digest(target):
        return hashlib.sha256(target.read_bytes()).hexdigest()

    def load(relative):
        return json.loads(path(relative).read_text())

    def rows(relative):
        with path(relative).open(newline='') as stream:
            return list(csv.DictReader(stream))

    def array(relative):
        with np.load(path(relative), allow_pickle=False) as container:
            result = container['state_bits']
        assert result.shape == (300, 125, 10) and result.dtype == np.uint32
        return result

    lock = load('experiment-lock.json')
    assert lock['expected_runs'] == 231 and lock['scientific_runs_started'] is False
    for relative, value in lock['files'].items():
        assert digest(path(relative)) == value, relative
    audit = load('independent-audit.json')
    assert audit['status'] == 'pass' and audit['independent_metric_implementation'] is True
    assert (audit['scientific_runs_checked'], audit['technical_shams_checked'], audit['baseline_legacy_exact_pairs'],
            audit['independently_recomputed_metric_sets']) == (231, 6, 3, 1440)
    assert audit['all_inputs_unchanged_before_after'] is True
    for relative, value in audit['source_and_input_sha256'].items():
        assert digest(path(relative)) == value, relative
    validation = load('validation.json')
    assert validation['status'] == 'pass' and validation['conditions'] == 231
    assert validation['first_execution_initial_bits_exact'] is True
    protocol = load('protocol.json')
    assert protocol['steps'] == 300 and protocol['dt_ms'] == .1 and protocol['chunks'] == 125
    assert protocol['scientific_runs'] == dict(original=3, single_swap=57, initial_jitter=171, total=231)
    complete = load('run-complete.json')
    assert complete['status'] == 'pass' and len(complete['runs']) == complete['total_runs'] == 231
    for record in complete['runs']:
        for extension in ('npz', 'csv', 'json'):
            assert digest(path(f'runs/{record["stem"]}.{extension}')) == record[f'{extension}_sha256']

    comparisons = rows('analysis/comparisons.csv')
    assert len(comparisons) == 288
    summaries = rows('analysis/summary.csv')
    assert len(summaries) == 15
    by_summary = {(r['probe'], r['group']): r for r in summaries}
    swap_diagnostics = rows('analysis/swap-input-diagnostics.csv')
    assert len(swap_diagnostics) == 57
    baselines = {probe: array(f'runs/original__{probe}.npz') for probe in PROBES}
    graph_audits = {r['graph']: r for r in load('graph-audit.json') if r['type'] == 'swap'}
    original_graph = np.loadtxt(path('graphs/original.csv'), delimiter=',', skiprows=1, dtype=np.int64)
    assert original_graph.shape == (2845, 5)
    replay_zero_active = replay_zero_silent = replay_nonzero_spike_exact = 0
    comparison_index = {r['stem']: r for r in comparisons}
    for diagnostic in swap_diagnostics:
        probe, name = diagnostic['probe'], diagnostic['graph']
        candidate_graph = np.loadtxt(path(f'graphs/{name}.csv'), delimiter=',', skiprows=1, dtype=np.int64)
        record = graph_audits[name]
        i, j = record['rows']
        changed = np.flatnonzero(original_graph[:, 2] != candidate_graph[:, 2])
        assert set(map(int, changed)) == {i, j}
        a, b = map(int, original_graph[i, 1:3])
        c, d = map(int, original_graph[j, 1:3])
        assert candidate_graph[i, 2] == d and candidate_graph[j, 2] == b
        assert original_graph[i, 3] == original_graph[j, 3]
        assert (int(diagnostic['source_a']), int(diagnostic['old_target_b']),
                int(diagnostic['source_c']), int(diagnostic['old_target_d'])) == (a, b, c, d)
        weight = float(np.array([original_graph[i, 3]], dtype='<u4').view('<f4')[0])
        reference = baselines[probe]
        source_delta = reference[:, a, 0].astype(np.int64) - reference[:, c, 0].astype(np.int64)
        eligible = source_delta[:298]
        # A same-weight target swap has opposite discrepancies at the two
        # targets. This independently replays represented weights and original
        # source activity; it does not infer the closed-loop response from them.
        target_pair = np.stack((weight * eligible, -weight * eligible))
        l1 = float(np.abs(target_pair).sum())
        frobenius = float(np.sqrt(np.sum(target_pair ** 2)))
        assert np.isclose(float(diagnostic['shared_input_difference_l1']), l1, rtol=1e-12, atol=1e-12)
        assert np.isclose(float(diagnostic['shared_input_difference_frobenius']), frobenius, rtol=1e-12, atol=1e-12)
        assert int(diagnostic['eligible_source_slots']) == 298
        assert int(diagnostic['source_spike_difference_slots']) == int(np.count_nonzero(eligible))
        assert int(diagnostic['excluded_late_source_difference_slots']) == int(np.count_nonzero(source_delta[298:]))
        nonzero = np.flatnonzero(eligible)
        first = int(nonzero[0]) if len(nonzero) else None
        assert diagnostic['first_source_difference_slot'] == ('' if first is None else str(first))
        assert diagnostic['first_eligible_arrival_slot'] == ('' if first is None else str(first + 2))
        zero_input = not np.any(eligible)
        assert diagnostic['shared_input_identical_in_window'] == str(bool(zero_input))
        candidate = array(f'runs/{diagnostic["stem"]}.npz')
        spike_exact = bool(np.array_equal(candidate[:, :, 0], reference[:, :, 0]))
        bits_exact = bool(np.array_equal(candidate, reference))
        assert diagnostic['output_spikes_identical'] == str(spike_exact)
        assert diagnostic['output_recorded_bits_identical'] == str(bits_exact)
        assert (int(comparison_index[diagnostic['stem']]['spike_mismatch_cells']) == 0) == spike_exact
        if zero_input:
            assert bits_exact
            source_active = bool(np.any(reference[:298, a, 0]) or np.any(reference[:298, c, 0]))
            replay_zero_active += int(source_active)
            replay_zero_silent += int(not source_active)
        elif spike_exact:
            replay_nonzero_spike_exact += 1
    assert (replay_zero_active, replay_zero_silent, replay_nonzero_spike_exact) == (3, 1, 17)
    claims = {}
    aliases = []
    for probe in PROBES:
        extensive = [r for r in comparisons if r['probe'] == probe and r['type'] == 'extensive']
        swaps = [r for r in comparisons if r['probe'] == probe and r['type'] == 'swap']
        assert len(extensive) == len(swaps) == 19
        e = [float(r['chunk_bin_l1_relative']) for r in extensive]
        s = [float(r['chunk_bin_l1_relative']) for r in swaps]
        diagnostics = [r for r in swap_diagnostics if r['probe'] == probe]
        calculated = dict(extensive_median=float(np.median(e)), extensive_minimum=min(e),
            swap_median=float(np.median(s)), swap_maximum=max(s),
            extensive_population_median=float(np.median([float(r['population_bin_l1_relative']) for r in extensive])),
            swap_population_median=float(np.median([float(r['population_bin_l1_relative']) for r in swaps])),
            extensive_cancellation_median=float(np.median([float(r['cancellation_fraction']) for r in extensive if r['cancellation_fraction'] != ''])),
            swap_cancellation_median=float(np.median([float(r['cancellation_fraction']) for r in swaps if r['cancellation_fraction'] != ''])),
            swap_bin_zero=sum(value == 0 for value in s),
            shared_input_zero=sum(r['shared_input_identical_in_window'] == 'True' for r in diagnostics))
        for key, expected in EXPECTED[probe].items():
            assert np.isclose(calculated[key], expected, rtol=0, atol=1e-12), (probe, key, calculated[key], expected)
        assert min(e) > max(s), probe
        assert sum(int(r['spike_mismatch_cells']) == 0 for r in swaps) == 7
        assert all(int(r['spike_mismatch_cells']) > 0 for r in extensive)
        for row in extensive + swaps:
            numerator = int(row['chunk_bin_l1_numerator'])
            population = int(row['population_bin_l1_numerator'])
            assert population <= numerator
            if numerator:
                assert np.isclose(float(row['population_to_chunk_l1_ratio']), population / numerator, rtol=0, atol=1e-12)
                assert np.isclose(float(row['cancellation_fraction']), 1 - population / numerator, rtol=0, atol=1e-12)
            else:
                assert row['population_to_chunk_l1_ratio'] == row['cancellation_fraction'] == ''
                if int(row['spike_mismatch_cells']):
                    aliases.append(dict(stem=row['stem'], mismatch_cells=int(row['spike_mismatch_cells'])))
        for group, selected in [('extensive', extensive), ('swap', swaps)]:
            summary = by_summary[(probe, group)]
            assert int(summary['n']) == 19
            assert float(summary['chunk_bin_l1_relative_median']) == float(np.median([float(r['chunk_bin_l1_relative']) for r in selected]))
            assert int(summary['spike_identical_runs']) == sum(int(r['spike_mismatch_cells']) == 0 for r in selected)
        for row in diagnostics:
            if row['shared_input_identical_in_window'] == 'True':
                assert row['output_recorded_bits_identical'] == row['output_spikes_identical'] == 'True'
        claims[probe] = dict(calculated, swap_slot_exact=7, extensive_minimum_above_swap_maximum=True)
    assert len(aliases) == 4
    assert sorted(x['mismatch_cells'] for x in aliases) == [2, 2, 6, 8]

    initial_audit = load('initial-audit.json')
    assert len(initial_audit) == 57
    for epsilon, (actual, ulps) in ACTUAL_DOSES.items():
        subset = [r for r in initial_audit if r['epsilon'] == epsilon]
        assert len(subset) == 19
        assert all(r['actual_linf'] == actual and r['ulp_steps'] == ulps and r['nonzero_chunks'] == 124 for r in subset)
    jitter_records = [r for r in complete['runs'] if r['type'] == 'jitter']
    assert len(jitter_records) == 171
    for record in jitter_records:
        candidate = array(f'runs/{record["stem"]}.npz')
        reference = baselines[record['probe']]
        assert np.array_equal(candidate[:, :, 0], reference[:, :, 0])
        assert np.array_equal(candidate[-1], reference[-1])
        assert not np.array_equal(candidate, reference)
    resets = rows('analysis/jitter-reset-summary.csv')
    assert len(resets) == 171
    assert all(int(r['chunks_equal_at_end']) == 125 and int(r['chunks_changed_spikes']) == 0 for r in resets)
    assert {int(r['chunks_with_common_reset']) for r in resets if r['probe'] == 'focal_burst'} == {71}
    assert {int(r['chunks_with_common_reset']) for r in resets if r['probe'] != 'focal_burst'} == {125}
    for relative, value in tracked.items():
        assert digest(source / relative) == value, relative
    result = dict(status='pass',new_scientific_conditions=231,technical_shams_not_scientific_conditions=6,
        archived_extensive_conditions_reanalyzed=57,original_baseline_bridges=3,
        claims=claims,actual_initial_f32_doses={str(k): dict(linf=v[0], ulps=v[1]) for k,v in ACTUAL_DOSES.items()},
        all_171_jitter_runs_slot_spikes_exact_and_final_125_chunk_10fields_exact=True,
        jitter_trajectories_continuous_state_not_identical_throughout=True,
        focal_jitter_common_reset_chunks=71,focal_jitter_additional_chunks_recoincide_without_spiking=54,
        bin_zero_but_slot_different_cases=aliases,all_four_zero_shared_input_cases_state_bits_exact=True,
        shared_source_replay_independently_recomputed_cases=57,
        zero_input_cases_with_identical_nonzero_source_sequences=replay_zero_active,
        zero_input_cases_with_two_silent_sources=replay_zero_silent,
        nonzero_shared_input_cases_with_identical_spikes=replay_nonzero_spike_exact,
        manuscript_scope='One original graph; fixed inputs, local interventions and 30 ms horizon; no general chaos, robustness, uniform-null, causal motif, or optimal-topology claim',
        paired_cancellation_excludes_undefined_zero_chunk_error=True,inputs_unchanged=True,
        frozen_and_run_input_sha256=tracked)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('status','new_scientific_conditions','technical_shams_not_scientific_conditions','archived_extensive_conditions_reanalyzed')}))


if __name__ == '__main__':
    main()
