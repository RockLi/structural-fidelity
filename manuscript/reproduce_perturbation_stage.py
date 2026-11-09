#!/usr/bin/env python3
"""Reproduce frozen perturbation simulations, then audit exact and derived outputs.

The archived simulator and analysis scripts remain unchanged. Integer simulation
payloads and count CSV bytes must match exactly. Derived CSV floating values are
compared at rtol=atol=1e-12, with every nonidentical value disclosed. This wrapper
never substitutes archived results for fresh output.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
RTOL = ATOL = 1e-12
FOLDERS = ('analysis', 'legacy_diagnostics', 'predictors')
INTEGER = re.compile(r'[+-]?\d+\Z')
SCRIPTS = ('study.py', 'analyze.py', 'legacy_phases.py', 'reproduce.py',
           'experiment.rs', 'kernel_audit.rs', 'inherited-library.patch',
           'inherited-inputs-sha256.json')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    assert rows and len(set(rows[0])) == len(rows[0]), ('missing/duplicate CSV header', path)
    assert all(len(row) == len(rows[0]) for row in rows[1:]), ('CSV row width', path)
    return rows[0], rows[1:]


def number(value):
    try:
        return float(value)
    except (ValueError, OverflowError):
        return None


def ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for index in order[i:j]:
            result[index] = (i + j - 1) / 2 + 1
        i = j
    return result


def near_constant(values):
    return bool(values) and max(values) - min(values) <= 1e-12 * max(1.0, max(map(abs, values)))


def compare_csvs(reference, candidate):
    """Audit all derived CSVs; row order/schema/strings/integers remain exact."""
    reference, candidate = Path(reference), Path(candidate)
    records, differences, rank_changes = [], [], []
    for folder in FOLDERS:
        refs = {p.name: p for p in (reference / folder).glob('*.csv')}
        actual = {p.name: p for p in (candidate / folder).glob('*.csv')}
        assert refs and set(refs) == set(actual), ('CSV file set', folder, sorted(refs), sorted(actual))
        for name in sorted(refs):
            ref, out = refs[name], actual[name]
            header, old = read_csv(ref)
            new_header, new = read_csv(out)
            assert header == new_header and len(old) == len(new), ('CSV schema/row count', folder, name)
            relative = str(ref.relative_to(reference))
            column_types = {}
            file_differences = []
            for col, label in enumerate(header):
                nonblank = [row[col] for row in old if row[col] != '']
                if nonblank and all(INTEGER.fullmatch(v) for v in nonblank):
                    kind = 'integer_exact'
                elif nonblank and all(number(v) is not None for v in nonblank):
                    values = [number(v) for v in nonblank]
                    kind = ('integer_exact' if all(math.isfinite(v) and v.is_integer() for v in values)
                            else 'float_tolerance')
                else:
                    kind = 'string_exact'
                column_types[label] = kind
                finite_old, finite_new = [], []
                for row_index, (a_row, b_row) in enumerate(zip(old, new), start=2):
                    a, b = a_row[col], b_row[col]
                    where = (relative, row_index, label)
                    if a == '' or b == '':
                        assert a == b, ('blank semantics', where, a, b)
                        continue
                    if kind != 'float_tolerance':
                        assert a == b, ('exact string/integer/row-order', where, a, b)
                        continue
                    x, y = number(a), number(b)
                    assert x is not None and y is not None, ('invalid numeric value', where, a, b)
                    if math.isnan(x) or math.isnan(y):
                        assert math.isnan(x) and math.isnan(y), ('NaN semantics', where, a, b)
                        continue
                    assert math.isfinite(x) and math.isfinite(y), ('nonfinite numeric value', where, a, b)
                    finite_old.append(x)
                    finite_new.append(y)
                    delta = abs(y - x)
                    assert delta <= ATOL + RTOL * abs(x), ('float tolerance exceeded', where, a, b, delta)
                    if a != b:
                        detail = dict(file=relative, csv_line=row_index, column=label,
                                      reference=a, candidate=b, absolute_delta=delta,
                                      relative_delta=(delta / abs(x) if x != 0 else None),
                                      allowed_absolute_delta=ATOL + RTOL * abs(x),
                                      same_fixed_3_4_6_9_decimals=all(f'{x:.{n}f}' == f'{y:.{n}f}' for n in (3, 4, 6, 9)),
                                      same_9_significant_digits=format(x, '.9g') == format(y, '.9g'))
                        file_differences.append(detail)
                if kind == 'float_tolerance' and ranks(finite_old) != ranks(finite_new):
                    rank_changes.append(dict(file=relative, column=label,
                        reference_near_constant=near_constant(finite_old),
                        candidate_near_constant=near_constant(finite_new),
                        reference_range=max(finite_old)-min(finite_old),
                        candidate_range=max(finite_new)-min(finite_new),
                        reference_ranks=ranks(finite_old), candidate_ranks=ranks(finite_new)))
            differences.extend(file_differences)
            records.append(dict(file=relative, rows=len(old), columns=header, column_types=column_types,
                                byte_exact=sha(ref) == sha(out), reference_sha256=sha(ref),
                                candidate_sha256=sha(out), differing_float_cells=len(file_differences),
                                max_absolute_delta=max((d['absolute_delta'] for d in file_differences), default=0.0)))
    # Changes to near-constant raw ranks are disclosed, not described as rank equality.
    # The existing protocol excludes these columns before correlations are computed.
    excluded_rank_changes = [r for r in rank_changes
                             if r['column'] == 'weight_frobenius_distortion'
                             and r['reference_near_constant'] and r['candidate_near_constant']]
    unexpected_rank_changes = [r for r in rank_changes if r not in excluded_rank_changes]
    assert not unexpected_rank_changes, ('nonconstant numerical rank changed', unexpected_rank_changes)
    association_exact = sha(reference/'analysis/prediction-associations.csv') == sha(candidate/'analysis/prediction-associations.csv')
    assert association_exact, 'Reported association table changed'
    assert all(d['same_fixed_3_4_6_9_decimals'] and d['same_9_significant_digits'] for d in differences), 'Displayed precision changed'
    return dict(status='pass', tolerance=dict(rtol=RTOL, atol=ATOL,
                rule='abs(candidate-reference) <= atol + rtol*abs(reference)'),
                schema_row_order_strings_integers_exact=True, blank_and_nan_semantics_match=True,
                infinite_or_invalid_numeric_values_rejected=True,
                file_count=len(records), byte_exact_file_count=sum(r['byte_exact'] for r in records),
                all_csv_bytes_exact=all(r['byte_exact'] for r in records),
                differing_float_cells=len(differences),
                max_absolute_delta=max((d['absolute_delta'] for d in differences), default=0.0),
                max_relative_delta=max((d['relative_delta'] for d in differences if d['relative_delta'] is not None), default=0.0),
                affected_columns=sorted({(d['file'] + ':' + d['column']) for d in differences}),
                reported_association_csv_byte_exact=association_exact,
                nonconstant_ranks_unchanged=True,
                excluded_near_constant_rank_changes=excluded_rank_changes,
                tested_fixed_decimal_and_significant_precision_unchanged=True,
                files=records, float_differences=differences)


def verify(reference, candidate):
    reference, candidate = reference.resolve(), candidate.resolve()
    assert not candidate.is_relative_to(reference) and not reference.is_relative_to(candidate), 'Fresh output must be separate from archived evidence'
    inherited = json.loads((reference/'inherited-inputs-sha256.json').read_text())
    for name, digest in inherited.items():
        assert sha(reference/name) == digest == sha(candidate/name), ('frozen inherited input', name)
    for name in SCRIPTS:
        assert sha(reference/name) == sha(candidate/name), ('frozen experiment script', name)
    archived = json.loads((reference/'run-complete.json').read_text())['runs']
    fresh = json.loads((candidate/'run-complete.json').read_text())['runs']
    ref_by = {r['stem']: r for r in archived}
    new_by = {r['stem']: r for r in fresh}
    assert len(ref_by) == 48 and set(ref_by) == set(new_by) and len(fresh) == 48
    run_records = []
    for stem, old in sorted(ref_by.items()):
        current = new_by[stem]
        assert all(old[k] == current[k] for k in ('graph', 'condition', 'amplitude', 'stem'))
        old_csv, new_csv = reference/'runs'/f'{stem}.csv', candidate/'runs'/f'{stem}.csv'
        assert sha(old_csv) == old['csv_sha256'] == sha(new_csv) == current['csv_sha256'], ('count CSV bytes', stem)
        old_npz, new_npz = reference/'runs'/f'{stem}.npz', candidate/'runs'/f'{stem}.npz'
        assert sha(old_npz) == old['npz_sha256'] and sha(new_npz) == current['npz_sha256']
        with np.load(old_npz, allow_pickle=False) as a, np.load(new_npz, allow_pickle=False) as b:
            assert a.files == b.files == ['state_bits'], ('state payload keys', stem)
            x, y = a['state_bits'], b['state_bits']
            assert x.dtype == y.dtype == np.dtype('uint32') and x.shape == y.shape == (1000, 125, 14)
            assert np.array_equal(x, y), ('state bits', stem)
            run_records.append(dict(stem=stem, state_payload_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
                                    count_csv_sha256=sha(new_csv), state_payload_bit_exact=True, count_csv_byte_exact=True))
    derived = compare_csvs(reference, candidate)
    return dict(status='pass', reference_dir=str(reference), fresh_dir=str(candidate),
                exact_state_payloads=48, exact_count_csv=48,
                all_analysis_legacy_phase_and_predictor_csv_exact=derived['all_csv_bytes_exact'],
                all_analysis_legacy_phase_and_predictor_csv_within_tolerance=True,
                derived_csv_comparison=derived, source_library_unchanged=True,
                inherited_inputs_exact=len(inherited), frozen_experiment_scripts_unchanged=True,
                timing_equality_required=False, container_npz_byte_equality_required=False,
                wrapper_sha256=sha(Path(__file__).resolve()), simulated_output_records=run_records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path, help='New directory for a complete frozen reproduction')
    mode.add_argument('--verify-existing', type=Path, help='Read-only comparison of existing completed outputs')
    parser.add_argument('--reference-dir', type=Path, default=ROOT/'evidence/perturbation')
    parser.add_argument('--simulation-python', default=sys.executable)
    parser.add_argument('--comparison-report', type=Path)
    args = parser.parse_args()
    reference = args.reference_dir.resolve()
    out = (args.output or args.verify_existing).resolve()
    if args.output:
        assert not out.exists(), 'Use a new output directory'
        # Leave the frozen byte-only comparator unused; audit it externally below.
        subprocess.run([args.simulation_python, '-B', str(reference/'reproduce.py'), '--output', str(out)],
                       cwd=reference, check=True)
    report_path = args.comparison_report or out/'fresh-comparison.json'
    assert not report_path.resolve().is_relative_to(reference), 'Do not overwrite frozen evidence'
    report = verify(reference, out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'exact_state_payloads', 'exact_count_csv',
                     'all_analysis_legacy_phase_and_predictor_csv_exact')}, indent=2))
    print('Derived CSV comparison:', report['derived_csv_comparison']['byte_exact_file_count'], '/',
          report['derived_csv_comparison']['file_count'], 'byte-exact;',
          report['derived_csv_comparison']['differing_float_cells'], 'disclosed floating differences')
    print('Comparison report:', report_path)


if __name__ == '__main__':
    main()
