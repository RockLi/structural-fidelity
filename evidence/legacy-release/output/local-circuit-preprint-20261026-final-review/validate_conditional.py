#!/usr/bin/env python3
"""Gate conditional-study claims against fresh outputs; never substitute old data.
Simulated states/counts are exact; derived CSV floats use the disclosed 1e-12
tolerance comparator. Replication does not add independent network samples.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from reproduce_perturbation_stage import compare_csvs

ROOT = Path(__file__).resolve().parent
ARMS = ('A_degree', 'B_aligned', 'C_random')
CONDITIONS = ('baseline', 'small', 'double')
KERNEL_CASES = (
    'scalar_simd_exact_refractory_slots',
    'chunk_injections_precede_gate_and_context_still_decays',
    'silent_kernel_leaks_toward_zero',
    'strong_inhibition_remains_finite_without_voltage_floor',
    'scheduler_dormancy_freezes_voltage_and_zero_wake_steps',
    'pending_status_is_not_a_per_step_execution_flag',
    'post_step_routing_with_delay_one_arrives_two_processed_slots_later',
    'input_protocol_uses_current_slot_before_step',
)


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def load(p):
    return json.loads(p.read_text())


def readcsv(p):
    with p.open(newline='') as f:
        return list(csv.DictReader(f))


def close(a, b, label):
    assert np.isclose(float(a), float(b), rtol=1e-11, atol=1e-11), (label, a, b)


def rms(a):
    return float(np.sqrt(np.mean(np.asarray(a, dtype=float)**2)))


def state(a):
    return np.ascontiguousarray(a[:, :, 1:4]).view(np.float32).astype(float)


def rank(a):
    x = np.asarray(a, dtype=float)
    return np.array([np.sum(x < y)+(np.sum(x == y)-1)/2 for y in x])


def rho(a, b):
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if any(np.ptp(z) <= 1e-12*max(1, float(np.max(np.abs(z)))) for z in (x, y)):
        return None
    return float(np.corrcoef(rank(x), rank(y))[0, 1])


def bits(p):
    with np.load(p, allow_pickle=False) as z:
        assert z.files == ['state_bits'], p
        return z['state_bits']


def matrix(e):
    weights = np.ascontiguousarray(e[:, 3], dtype=np.uint32).view(np.float32).astype(float)
    w = np.zeros((2, 125, 125))
    w[(e[:, 1] >= 100).astype(int), e[:, 2], e[:, 1]] = weights
    return w


def source_check(d):
    lock, inherited = load(d/'experiment-lock.json'), load(d/'inherited-inputs-sha256.json')
    for name, digest in lock['files'].items():
        assert sha(d/name) == digest, ('source lock', name)
    for name, digest in inherited.items():
        assert sha(d/name) == digest, ('inherited input', name)
    return dict(locked_files=len(lock['files']), inherited_files=len(inherited))


def validate(args):
    d, reference = args.perturbation_dir.resolve(), args.reference_dir.resolve()
    result = dict(status='pass', scope='Numerical/source validation; not document visual QA or independent-network inference.')
    result['source_locks'] = source_check(d)
    protocol = load(d/'protocol.json')
    assert (protocol['steps'], protocol['chunks'], protocol['units_per_chunk'], protocol['duration_ms']) == (1000, 125, 100, 100)
    assert protocol['perturbation']['conditions'] == dict(baseline=0., small=1.5, double=3.)
    assert protocol['perturbation']['slots'] == [200, 210]
    assert protocol['conditioning']['targets'] == list(range(40, 60))
    graphs = ['original']+[f'{a}_{s}' for a in ARMS for s in range(92001, 92006)]
    assert protocol['graphs'] == graphs
    records = load(d/'run-complete.json')['runs']
    assert len(records) == len({r['stem'] for r in records}) == 48
    v = load(d/'validation.json')
    assert v['status'] == 'pass' and v['conditions'] == 48
    assert all(v[k] is True for k in ('preperturbation_exact_in_all_conditions', 'step_and_refractory_observation_verified', 'finite_payloads_counts_edge_visits_and_checksums_verified'))

    technical = load(d/'technical/validation.json')
    assert technical['status'] == 'pass'
    assert all(technical[k] is True for k in ('independent_kernel_cases_passed', 'old_300_slot_state_bits_exact', 'old_spike_message_visit_and_stepped_counts_exact'))
    assert 'PASS: 8 independent frozen-kernel, refractory, injection, context, scheduler and routing checks' in (d/'logs/kernel-audit.log').read_text()
    kernel_main = (d/'kernel_audit.rs').read_text().split('fn main() {', 1)[1]
    assert all(f'{case}();' in kernel_main for case in KERNEL_CASES)
    bridge, old = bits(d/'technical/bridge.npz'), bits(d/'legacy_inputs/runs/original__module_burst__explicit.npz')
    assert bridge.shape == (300, 125, 14) and np.array_equal(bridge[:, :, :10], old)
    assert np.array_equal(np.loadtxt(d/'technical/bridge.csv', delimiter=',', skiprows=1, dtype=np.int64)[:, :5],
                          np.loadtxt(d/'legacy_inputs/runs/original__module_burst__explicit.csv', delimiter=',', skiprows=1, dtype=np.int64))
    result['kernel_audits'] = dict(cases=list(KERNEL_CASES), count=8, bridge_slots_exact=300)

    # Directly test per-node, per-projection weight multisets and exact rewiring
    # budgets. The declared B/C group constraints are checked independently.
    original_edges = np.loadtxt(d/'graphs/original.csv', delimiter=',', skiprows=1, dtype=np.int64)
    w0 = matrix(original_edges)
    legacy_protocol = load(d/'legacy_inputs/protocol.json')
    groups = {k: np.eye(10)[legacy_protocol['partitions'][k]] for k in ('aligned', 'random')}
    graph_audits, matrices = [], {}
    for graph in graphs:
        e = np.loadtxt(d/'graphs'/f'{graph}.csv', delimiter=',', skiprows=1, dtype=np.int64)
        assert e.shape == original_edges.shape
        assert np.all(e[:, 1] != e[:, 2]) and np.all(e[:, 4] == 1)
        assert len(set(map(tuple, e[:, :3]))) == len(e)
        assert np.array_equal(e[:, [0, 1, 3, 4]], original_edges[:, [0, 1, 3, 4]])
        assert np.array_equal((e[:, 1] >= 100)*2+(e[:, 2] >= 100), e[:, 0])
        for node_column in (1, 2):
            assert Counter(map(tuple, e[:, [0, node_column, 3]])) == Counter(map(tuple, original_edges[:, [0, node_column, 3]]))
        changed = 0
        for arm in range(4):
            a, r = e[e[:, 0] == arm], original_edges[original_edges[:, 0] == arm]
            missing = len(set(map(tuple, r[:, 1:3]))-set(map(tuple, a[:, 1:3])))
            assert missing == (0 if graph == 'original' else int(.35*len(r)))
            changed += missing
        w = matrix(e)
        matrices[graph] = w
        if graph.startswith(('B_', 'C_')):
            p = groups['aligned' if graph.startswith('B_') else 'random']
            delta = w-w0
            assert not (delta@p).any() and not np.einsum('ia,qij->qaj', p, delta).any()
        graph_audits.append(dict(graph=graph, changed_edges=changed, total_edges=len(e), changed_fraction=changed/len(e)))
    result['graph_constraints'] = dict(graphs=16, per_node_per_arm_in_out_weight_multisets_preserved=True,
                                      source_rows_weights_and_delays_preserved=True,
                                      declared_group_profiles_preserved_for_B_and_C=True, values=graph_audits)

    # Frozen basis: no fitting to new stimulus or perturbation data.
    training = load(d/'predictors/training-summary.json')
    assert training['rank5'] == 5 and training['secondary_training90_rank'] == 19
    assert training['centered'] is False and training['new_stimulus_data_used'] is False
    assert training['graphs_used_to_fit_basis'] == ['original']
    assert training['training_source'] == 'legacy_inputs/runs/original__module_burst__explicit.npz'
    assert training['training_source_sha256'] == sha(d/training['training_source'])
    with np.load(d/'predictors/training-basis.npz', allow_pickle=False) as z:
        u5, u19, scale = z['U5'], z['U90'], z['state_scale']
    assert u5.shape == (125, 5) and u19.shape == (125, 19)
    for u in (u5, u19):
        assert np.allclose(u.T@u, np.eye(u.shape[1]), rtol=0, atol=1e-12)
    assert np.allclose(scale, state(old).std(axis=(0, 1)), rtol=0, atol=1e-10)
    source_train = old[:, :, 0].astype(float).T
    for u, key in ((u5, 'rank5_energy_fraction'), (u19, 'secondary_training90_energy_fraction')):
        close(np.sum((u.T@source_train)**2)/np.sum(source_train**2), training[key], 'training coverage')
    pred = {r['graph']: r for r in readcsv(d/'predictors/frozen-predictors.csv')}
    assert set(pred) == set(graphs[1:])
    g = np.concatenate(w0, axis=0)
    for graph in graphs[1:]:
        delta = np.concatenate(matrices[graph]-w0, axis=0)
        for u, key in ((u5, 'activity_rank5'), (u19, 'activity_training90')):
            close(np.linalg.norm(delta@u)/np.linalg.norm(g@u), pred[graph][key], 'frozen predictor')
        close(np.linalg.norm(delta@source_train)/np.linalg.norm(g@source_train), pred[graph]['training_replay_distortion'], 'training replay')

    outcomes = readcsv(d/'analysis/response-outcomes.csv')
    assert len(outcomes) == 32
    outcome_by = {(r['graph'], r['condition']): r for r in outcomes}
    assert len(outcome_by) == 32
    prediction_rows = readcsv(d/'analysis/prediction-data.csv')
    assert len(prediction_rows) == 30
    original_bits = {c: bits(d/'runs'/f'original__{c}.npz') for c in CONDITIONS}
    original_states = {c: state(a) for c, a in original_bits.items()}
    original_response = {c: (original_states[c]-original_states['baseline'])/scale for c in CONDITIONS[1:]}
    source_coverage = readcsv(d/'analysis/source-subspace-coverage.csv')
    assert len(source_coverage) == 24
    for row in source_coverage:
        lo, hi = protocol['windows'][row['window']]
        s = original_bits[row['condition']][lo:hi, :, 0].astype(float).T
        energy = float(np.sum(s*s))
        close(energy, row['spike_energy'], 'source energy')
        for u, key in ((u5, 'rank5_energy_fraction'), (u19, 'training90_energy_fraction')):
            close(np.sum((u.T@s)**2)/energy, row[key], 'new source coverage')

    new_gates, wrong_gates, total_cells, min_voltage = 0, 0, 0, float('inf')
    for graph in graphs:
        base = bits(d/'runs'/f'{graph}__baseline.npz')
        base_state = state(base)
        e = np.loadtxt(d/'graphs'/f'{graph}.csv', delimiter=',', skiprows=1, dtype=np.int64)
        outdegree = np.bincount(e[:, 1], minlength=125)
        for condition in CONDITIONS:
            stem = f'{graph}__{condition}'
            a = bits(d/'runs'/f'{stem}.npz')
            assert a.shape == (1000, 125, 14) and a.dtype == np.uint32
            record = next(r for r in records if r['stem'] == stem)
            for ext in ('npz', 'csv'):
                assert sha(d/'runs'/f'{stem}.{ext}') == record[ext+'_sha256']
            assert np.array_equal(a, bits(reference/'runs'/f'{stem}.npz')), ('reference states', stem)
            assert np.array_equal(a[:200], base[:200]), ('pre-pulse equality', stem)
            assert np.isfinite(np.ascontiguousarray(a[:, :, 1:8]).view(np.float32)).all()
            assert set(np.unique(a[:, :, 0])).issubset({0, 100})
            counts = np.loadtxt(d/'runs'/f'{stem}.csv', delimiter=',', skiprows=1, dtype=np.int64)
            assert counts.shape == (1000, 7)
            expected = np.column_stack((np.arange(1000), a[:, :, 0].sum(axis=1),
                                       (a[:, :, 0] > 0)@outdegree, (a[:, :, 0] > 0)@outdegree,
                                       a[:, :, 11].sum(axis=1), a[:, :, 12].sum(axis=1),
                                       (a[:, :, 13]*a[:, :, 11]).sum(axis=1)))
            assert np.array_equal(counts, expected), stem
            assert np.array_equal(a[1:, :, 10], a[:-1, :, 8]) and not a[0, :, 10].any()
            gate = (a[:, :, 10] > np.arange(1000)[:, None])*a[:, :, 11]
            assert np.array_equal(gate, a[:, :, 12])
            assert np.array_equal(gate, np.vstack([np.zeros((1, 125), dtype=bool), a[:-1, :, 0] > 0]))
            assert not a[:, :, 0][gate > 0].any()
            new_gates += int(gate.sum())
            wrong_gates += int(np.sum(a[:, :, 8] > np.arange(1000)[:, None]))
            total_cells += gate.size
            x = state(a)
            min_voltage = min(min_voltage, float(x[:, :, 0].min()))
            if condition != 'baseline':
                r = (x-base_state)/scale
                error = r-original_response[condition]
                row = outcome_by[graph, condition]
                close(rms(error[200:]), row['response_fidelity'], 'response fidelity')
                close(rms(r[200:]), row['own_response_rms'], 'own response')
                denominator = rms(original_response[condition][200:])
                close(denominator, row['original_response_rms'], 'original response')
                close(rms(error[200:])/denominator, row['relative_response_fidelity'], 'relative fidelity')
                spike_response = a[:, :, 0].astype(np.int64)-base[:, :, 0].astype(np.int64)
                assert int(np.count_nonzero(spike_response[200:])) == int(row['own_spike_response_nonzero_cells'])
    result['payload_checks'] = dict(new_conditions=48, reference_payloads_exact=48,
                                   all_count_csv_fields_recomputed=True, preperturbation_slots_exact=200,
                                   actual_execution_and_refractory_flags_verified=True,
                                   minimum_V_model_coordinate=min_voltage,
                                   correct_refractory_fraction=new_gates/total_cells,
                                   incorrect_post_deadline_fraction=wrong_gates/total_cells)

    # Recompute reported correlations, including n=5 and leave-one-group-out
    # n=10 sensitivity. These are descriptive dependent-graph comparisons.
    associations = readcsv(d/'analysis/prediction-associations.csv')
    baseline = {r['graph']: r for r in readcsv(d/'analysis/baseline-errors.csv')}
    by_condition = {c: [r for r in prediction_rows if r['condition'] == c] for c in CONDITIONS[1:]}
    for row in associations:
        if row['condition'] == 'baseline':
            chosen = [{**pred[g], **baseline[g]} for g in graphs[1:]]
        else:
            chosen = by_condition[row['condition']]
            sub = row['subset']
            chosen = [r for r in chosen if sub == 'all15' or r['treatment'] == sub or
                      (sub.startswith('without_') and r['treatment'] != sub[8:])]
        assert len(chosen) == int(row['n'])
        value = rho([float(r[row['predictor']]) for r in chosen], [float(r[row['target']]) for r in chosen])
        if value is None:
            assert row['spearman'] == ''
        else:
            close(value, row['spearman'], 'rank association')
    primary = [r for r in associations if r['predictor'] == 'activity_rank5' and r['target'] == 'response_fidelity' and r['subset'] == 'all15']
    assert len(primary) == 2
    result['primary_prediction'] = [dict(condition=r['condition'], n=int(r['n']), spearman=float(r['spearman'])) for r in primary]
    result['zero_response_comparator'] = {
        c: dict(original_response_rms=float(outcome_by['original', c]['original_response_rms']),
                relative_fidelity_min_rewired=min(float(r['relative_response_fidelity']) for r in outcomes if r['condition'] == c and r['graph'] != 'original'),
                zero_spike_response_count_all16=sum(int(r['own_spike_response_nonzero_cells']) == 0 for r in outcomes if r['condition'] == c))
        for c in CONDITIONS[1:]}
    result['coverage'] = dict(training_rank5=training['rank5_energy_fraction'], training_rank19=training['secondary_training90_energy_fraction'],
                             new_original_baseline_response_window=next(r for r in source_coverage if r['condition'] == 'baseline' and r['window'] == 'primary_response'))

    phases = readcsv(d/'legacy_diagnostics/phase-state-errors.csv')
    assert len(phases) == 144
    ranks = readcsv(d/'legacy_inputs/rank-transfer.csv')
    for r in ranks:
        for probe in ('module_burst', 'shifted_burst', 'focal_burst'):
            selected = [x for x in phases if x['graph'] == r['graph'] and x['probe'] == probe]
            assert len(selected) == 3
            full = np.sqrt(sum((int(x['stop_slot_exclusive'])-int(x['start_slot']))*float(x['state_score'])**2 for x in selected)/300)
            close(full, r[probe+'_state_score'], 'legacy weighted full score')
    result['legacy_phase_primary_medians'] = {
        phase: {a: float(np.median([float(r['state_score']) for r in phases if r['probe'] == 'module_burst' and r['phase'] == phase and r['treatment'] == a])) for a in ARMS}
        for phase in ('conditioning', 'early_recovery', 'late_recovery')}
    result['legacy_reanalysis'] = dict(archived_runs_reanalysed=48, phase_rows=144, new_simulations=0, weighted_full_scores_match_archived=45)
    csv_comparison = compare_csvs(reference, d)
    result['derived_reference_csv_comparison'] = csv_comparison
    result['strict_reference_csv_comparisons'] = [
        record['file'] for record in csv_comparison['files'] if record['byte_exact']]
    for folder, marker in (('analysis', 'analysis-complete.json'), ('report_figures', 'render-validation.json')):
        check = load(d/folder/marker)
        assert check['status'] == 'pass'
        for name, digest in check.get('outputs', check.get('outputs_sha256', {})).items():
            path = d/name if name.startswith(folder+'/') else d/folder/name
            assert sha(path) == digest, ('analysis/render output', path)
    if args.rewiring_dir:
        rw = args.rewiring_dir.resolve()
        assert load(rw/'validation.json')['all_360_runs_checked'] is True
        assert len(load(rw/'run-complete.json')['runs']) == 360
        result['fresh_coverage'] = dict(rewiring_conditions=360, perturbation_conditions=48,
                                       total_new_conditions_in_these_two_suites=408,
                                       archived_explicit_trajectories_reanalysed_separately=48,
                                       original_networks_in_perturbation=1, conditional_rewires_in_perturbation=15,
                                       earlier_experiments_additional_not_independent_network_counts=True)
    source_check(d)
    result['validator_sha256'] = sha(Path(__file__).resolve())
    result['input_table_sha256'] = {str(p.relative_to(d)): sha(p) for folder in ('analysis', 'legacy_diagnostics', 'predictors') for p in sorted((d/folder).glob('*.csv'))}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--perturbation-dir', required=True, type=Path)
    p.add_argument('--reference-dir', type=Path, default=ROOT/'evidence/perturbation')
    p.add_argument('--rewiring-dir', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    assert not args.output.exists(), 'Use a new validation output'
    report = validate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'primary_prediction', 'zero_response_comparator', 'legacy_phase_primary_medians')}, indent=2))


if __name__ == '__main__':
    main()
