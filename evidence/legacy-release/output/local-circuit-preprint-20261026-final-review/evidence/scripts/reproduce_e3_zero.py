#!/usr/bin/env python3
"""Reproduce the additive E3 zero-retention endpoint and the unchanged 2% bridge.

Usage: python3 evidence/scripts/reproduce_e3_zero.py --output-dir /tmp/e3-zero-results
Compiles isolated frozen-source copies using rustup run 1.98.1 rustc, edition 2024,
opt-level 3. No Cargo downloads, production edits, or historical data edits.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import tempfile
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def f32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def f32_sum(values):
    result = 0.0
    for value in values:
        result = f32(result + value)
    return result


def original_f32_metrics(a, b, units):
    """Recheck original metrics at their actual precision, in iteration order."""
    scale = f32(1.0 / f32(units * f32(f32(0.1) / 1000.0)))
    a, b = [f32(x * scale) for x in a], [f32(y * scale) for y in b]
    ma, mb = f32(f32_sum(a) / len(a)), f32(f32_sum(b) / len(b))
    da, db = [f32(x-ma) for x in a], [f32(y-mb) for y in b]
    num = f32_sum(f32(x*y) for x,y in zip(da,db))
    sa, sb = f32_sum(f32(x*x) for x in da), f32_sum(f32(y*y) for y in db)
    r = f32(num / f32(math.sqrt(f32(sa*sb))))
    delta = f32(f32(f32(mb-ma) / ma) * 100.0)
    return r, delta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='New or empty evidence output directory')
    parser.add_argument('--work-dir', type=Path, help='New or empty isolated build directory (default /tmp)')
    parser.add_argument('--toolchain', default='1.98.1')
    parser.add_argument('--reference-results', type=Path, help='Explicit 111-row diagnostic JSON for bridge verification; default is archived evidence, never a result fallback')
    parser.add_argument('--reference-rounded', type=Path, help='Explicit rounded JSON for filtered bridge verification; default is archived evidence, never a result fallback')
    parser.add_argument('--source-root', type=Path, help='Root for relative source_log paths; defaults to the result directory')
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parents[1]
    source = evidence / 'original/source'
    manifest_path = evidence / 'original/source-sha256.json'
    historical_path = (args.reference_results or evidence / 'diagnostics/diagnostic-results-exact.json').resolve()
    rounded_path = (args.reference_rounded or evidence / 'original/metrics-rounded.json').resolve()
    patches = evidence / 'e3-zero-retention/patches'
    manifest = json.loads(manifest_path.read_text())
    expected_manifest = '9a266203cf86bbe43b201e7af53fab3131c9d89deddbb64d6181f30199a6e448'
    if sha(manifest_path) != expected_manifest:
        raise SystemExit('Frozen source manifest identity changed')
    for name, expected in manifest.items():
        if sha(source / name) != expected:
            raise SystemExit(f'Frozen source hash mismatch: {name}')
    historical_hash = sha(historical_path)
    rounded_hash = sha(rounded_path)
    historical = json.loads(historical_path.read_text())
    if len(historical) != 111:
        raise SystemExit('Expected 111 reference diagnostic records for bridge verification')
    rounded = json.loads(rounded_path.read_text())
    if len(rounded) != 72:
        raise SystemExit('Expected 72 reference rounded records for bridge verification')
    output = args.output_dir.resolve()
    source_root = args.source_root.resolve() if args.source_root else output
    if not output.is_relative_to(source_root):
        raise SystemExit('Output directory must lie within --source-root')
    if output.exists() and any(output.iterdir()):
        raise SystemExit('Output directory must be empty; earlier results are preserved')
    output.mkdir(parents=True, exist_ok=True)
    for subdir in ['logs', 'slots']:
        (output / subdir).mkdir()
    work = args.work_dir.resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix='e3-zero-', dir='/tmp'))
    if work.exists() and any(work.iterdir()):
        raise SystemExit('Work directory must be empty')
    work.mkdir(parents=True, exist_ok=True)
    compiler = ['rustup', 'run', args.toolchain, 'rustc']
    compiler_version = subprocess.check_output(compiler + ['--version', '--verbose'], text=True)
    save(output / 'compiler-provenance.json', {
        'compiler_command': compiler, 'version_verbose': compiler_version,
        'platform': platform.platform(), 'machine': platform.machine(),
        'work_directory': str(work), 'script_sha256': sha(Path(__file__)),
        'source_manifest_sha256': expected_manifest,
        'bridge_reference_results': {'path': str(historical_path), 'sha256': historical_hash,
            'selection': 'explicit' if args.reference_results else 'archived_default'},
        'bridge_reference_rounded': {'path': str(rounded_path), 'sha256': rounded_hash,
            'selection': 'explicit' if args.reference_rounded else 'archived_default'},
    })
    save(output / 'protocol.json', {
        'study': 'Post-hoc additive E3 zero-retention endpoint; fixed-seed descriptive comparison',
        'topology': 'EIMicrocircuitSpec::boundary_heavy_hetero', 'rng_seed': 200,
        'weight_spread': 0.5, 'p_ee_ei_ie_ii': [0.15, 0.25, 0.25, 0.20],
        'w_ee_ei_ie_ii': [0.6, 0.8, 1.4, 0.5], 'delay_slots': 1,
        'forbid_within_chunk': True, 'exc_chunks': 100, 'inh_chunks': 25,
        'units_per_chunk': 100, 'units': 12500, 'dt_ms': 0.1,
        'steps': 200, 'duration_ms': 20, 'drive': 'tonic Sustained', 'drive_strength': 10,
        'zero_policy': 'RetentionPolicy::new(vec![], 2.0); threshold unused because classes empty',
        'zero_explicit_path': 'Existing run_mixed_with_retention constructs an empty explicit router',
        'bridge_policy': 'StrongInhibitoryLoop, threshold 2.0; identical to old minimum-budget point',
        'filtered_4ch_params': 'RicherProxyParams::default()',
        'stateful_params': 'gain_fast_exc=2.5, gain_fast_inh=0.4; other fields default',
        'raw_sum': 'Stateful with only final exc_drive=raw_exc, inh_drive=raw_inh; state updates retained',
        'event_ratio': 'All recurrent injected events in approximate run / explicit reference',
        'mismatch_scope': 'Per-slot total population spike counts; not per-neuron or voltages',
        'r_and_fr_delta': 'Original compare_dynamics f32; exact f32 bits and float64 trace checks saved',
        'timings': 'Reproduction logistics only; not optimized performance evidence',
        'tests': 'Dedicated additive test only; no PSD assertions or altered historical tests',
    })
    commands = []

    def run(label, command, cwd, env=None):
        started = time.monotonic()
        log_path = output / 'logs' / (label + '.log')
        with log_path.open('w') as log:
            log.write('$ ' + ' '.join(command) + '\n')
            if env:
                log.write('E3_OUTPUT_DIR=' + env['E3_OUTPUT_DIR'] + '\n')
            log.flush()
            proc = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        record = {'stage': label, 'command': command, 'cwd': str(cwd),
                  'returncode': proc.returncode, 'elapsed_s': time.monotonic() - started,
                  'log': str(log_path.relative_to(output))}
        if env:
            record['environment_overrides'] = {'E3_OUTPUT_DIR': env['E3_OUTPUT_DIR']}
        commands.append(record)
        save(output / 'commands.json', commands)
        print(json.dumps(record), flush=True)
        if proc.returncode:
            raise SystemExit(f'Failed: inspect {log_path}')

    for variant in ['original', 'raw_sum']:
        build = work / variant
        shutil.copytree(source, build)
        (build / 'bin').mkdir()
        run(variant + '-apply-additive-test', ['patch', '-p1', '-i', str(patches / 'e3-zero-retention-test.patch')], build)
        if variant == 'raw_sum':
            run(variant + '-apply-output-ablation', ['patch', '-p1', '-i', str(patches / 'raw-sum-output-only.patch')], build)
        # Only the additive test and the raw variant's two output expressions may differ.
        changed = [name for name, digest in manifest.items() if sha(build / name) != digest]
        expected_changed = [] if variant == 'original' else ['src/experiment/lpu_index.rs']
        assert sorted(changed) == expected_changed, changed
        assert sha(build / 'tests/e3_zero_retention.rs') == sha(patches / 'e3_zero_retention.rs')
        compiled_sources = {name: sha(build / name) for name in manifest}
        compiled_sources['tests/e3_zero_retention.rs'] = sha(build / 'tests/e3_zero_retention.rs')
        save(output / (variant + '-compiled-source-sha256.json'), compiled_sources)
        run(variant + '-build-library', compiler + ['--edition=2024', '-C', 'opt-level=3',
            '--crate-name', 'next_brain', '--crate-type', 'lib', 'src/lib.rs', '-o', 'bin/libnext_brain.rlib'], build)
        cfg = ['--cfg', 'raw_sum_ablation'] if variant == 'raw_sum' else []
        run(variant + '-build-test', compiler + ['--edition=2024', '-C', 'opt-level=3', '--test',
            'tests/e3_zero_retention.rs', '--extern', 'next_brain=bin/libnext_brain.rlib',
            '-o', 'bin/e3_zero_retention'] + cfg, build)
        run(variant + '-test', ['bin/e3_zero_retention', '--exact', 'e3_zero_and_bridge',
            '--nocapture', '--test-threads=1'], build, dict(os.environ, E3_OUTPUT_DIR=str(output)))

    rows = []
    integers = {'units', 'steps', 'retained_edges', 'total_edges', 'explicit_events', 'approx_events',
                'explicit_spikes', 'approx_spikes', 'mismatched_slots', 'max_step_spike_delta',
                'mixed_explicit_events', 'proxy_events', 'psth_r_f32_bits', 'fr_delta_f32_bits'}
    floats = {'dt_ms', 'threshold', 'retained_edges_pct', 'psth_r', 'fr_delta',
              'event_ratio_from_counts', 'gain_fast_exc', 'gain_fast_inh'}
    for variant in ['original', 'raw_sum']:
        for row in csv.DictReader((output / (variant + '-records.csv')).open()):
            row = {k: (int(v) if k in integers else float(v) if k in floats and v else None if k == 'threshold' else v) for k,v in row.items()}
            row['duration_ms'] = row['steps'] * row['dt_ms']
            row['event_reduction_pct'] = 100 * (1 - row['event_ratio_from_counts'])
            row['source_log'] = str((output / 'logs' / (variant + '-test.log')).relative_to(source_root))
            rows.append(row)
    assert len(rows) == 6
    assert {r['variant'] for r in rows} == {'filtered_4ch', 'original_instrumented', 'raw_sum'}
    checks = []
    reference_slots = None
    for row in rows:
        slots = [{k: int(v) for k,v in s.items()} for s in csv.DictReader((output / row['slot_file']).open())]
        assert len(slots) == row['steps']
        assert len({s['slot'] for s in slots}) == row['steps']
        a = [s['explicit_spikes'] for s in slots]
        b = [s['approx_spikes'] for s in slots]
        reference = [(s['slot'], s['explicit_spikes'], s['explicit_events']) for s in slots]
        if reference_slots is None:
            reference_slots = reference
        assert reference_slots == reference, 'Different reference trajectories between builds/methods'
        assert sum(a) == row['explicit_spikes'] and sum(b) == row['approx_spikes']
        assert sum(s['explicit_events'] for s in slots) == row['explicit_events']
        assert sum(s['approx_events'] for s in slots) == row['approx_events']
        assert sum(x != y for x,y in zip(a,b)) == row['mismatched_slots']
        assert max(abs(x-y) for x,y in zip(a,b)) == row['max_step_spike_delta']
        ma, mb = sum(a)/len(a), sum(b)/len(b)
        r64 = sum((x-ma)*(y-mb) for x,y in zip(a,b)) / math.sqrt(sum((x-ma)**2 for x in a) * sum((y-mb)**2 for y in b))
        fr64 = (sum(b)/sum(a) - 1) * 100
        r32, fr32 = original_f32_metrics(a, b, row['units'])
        assert r32 == row['psth_r'] and fr32 == row['fr_delta']
        # f32 accumulation differs from f64 by up to 6.8e-6 here; retain both.
        assert abs(r64-row['psth_r']) < 1e-4
        assert abs(fr64-row['fr_delta']) < 1e-4
        if row['retained_edges'] == 0:
            assert row['retained_edges_pct'] == 0 and row['mixed_explicit_events'] == 0
        checks.append({'variant': row['variant'], 'label': row['label'], 'slot_recheck': 'pass',
                       'psth_r_f32_exact_recheck': r32, 'fr_delta_f32_exact_recheck': fr32,
                       'psth_r_float64_from_counts': r64, 'fr_delta_float64_from_counts': fr64})

    bridges = []
    for row in (r for r in rows if r['retained_edges'] > 0):
        if row['variant'] == 'filtered_4ch':
            old = next(r for r in rounded if r['section'] == 'bench_retention_budget_curve_e3_hetero' and r['label'] == 'thr=2.00(~2%)')
            comparison = {'psth_r': (row['psth_r'], old['psth_r'], 3), 'fr_delta': (row['fr_delta'], old['fr_delta'], 1),
                          'event_ratio_from_counts': (row['event_ratio_from_counts'], old['ev_ratio'], 3),
                          'retained_edges_pct': (row['retained_edges_pct'], old['ret_e'], 1)}
            assert all(f'{new:.{n}f}' == f'{prior:.{n}f}' for new,prior,n in comparison.values()), comparison
            bridges.append({'variant': row['variant'], 'status': 'pass', 'comparison': 'All available supplied reference rounded metrics', 'values': comparison})
        else:
            old = next(r for r in historical if r['variant'] == row['variant'] and r['label'] == 'stateful_thr=2.00(~2%)')
            for field in ['explicit_events', 'approx_events', 'explicit_spikes', 'approx_spikes', 'max_step_spike_delta']:
                assert row[field] == old[field], (field, row[field], old[field])
            assert row['mismatched_slots'] == old['mismatch_steps']
            assert abs(row['psth_r'] - old['psth_r']) < 1e-9
            assert abs(row['fr_delta'] - old['fr_delta']) < 1e-9
            assert row['event_ratio_from_counts'] == old['event_ratio_from_counts']
            bridges.append({'variant': row['variant'], 'status': 'pass', 'comparison': 'Exact event/spike/mismatch integers; r/error match supplied reference nine-decimal values', 'reference_record': old})
    assert sha(historical_path) == historical_hash
    assert sha(rounded_path) == rounded_hash
    assert sha(manifest_path) == expected_manifest
    assert all(sha(source / name) == digest for name,digest in manifest.items())
    save(output / 'validation.json', {'status': 'pass', 'slot_checks': checks, 'bridge_checks': bridges,
         'source_files_verified_unchanged': len(manifest), 'reference_records_verified_unchanged': len(historical),
         'reference_111_records_sha256': historical_hash, 'reference_rounded_sha256': rounded_hash,
         'reference_tables_are_comparison_only': True, 'source_log_relative_to': str(source_root),
         'source_manifest_sha256': expected_manifest})
    save(output / 'results-exact.json', rows)
    with (output / 'results-exact.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    input_hashes = {str(p.relative_to(evidence)): sha(p) for p in [Path(__file__).resolve(), *sorted(patches.iterdir())] if p.is_file()}
    save(output / 'input-sha256.json', input_hashes)
    save(output / 'output-sha256.json', {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'output-sha256.json'})
    print(json.dumps({'status': 'pass', 'output_dir': str(output), 'records': len(rows), 'zero_rows': [r for r in rows if r['retained_edges'] == 0]}, indent=2), flush=True)


if __name__ == '__main__':
    main()
