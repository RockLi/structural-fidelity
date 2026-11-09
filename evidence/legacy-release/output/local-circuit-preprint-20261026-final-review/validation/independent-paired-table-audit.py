#!/usr/bin/env python3
"""Independent, read-only audit of the final revision's paired decision table.

Uses original per-policy measurements, rather than the plotting implementation
or its summaries. Does not import study modules or run simulations.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def read_json(path):
    return json.loads(path.read_text())


def csv_rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected, label):
    assert math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-14), (label, actual, expected)


def boolean(value):
    assert value in (True, False, 'True', 'False', 'true', 'false'), value
    return value is True or value in ('True', 'true')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--figures', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    budget = root / 'evidence/budget-boundary'
    figures = args.figures or root / 'activity-figures'
    protocol = read_json(budget / 'protocol.json')
    gate = read_json(budget / 'gate.json')
    ledger = read_json(budget / 'migration-ledger.json')
    design = protocol['continuation_gate']
    eps = design['epsilon']
    assert eps == 1e-12 and design['both_budgets_required'] is True
    assert design['required_complete_pairs'] == 10
    measurements = csv_rows(budget / 'analysis-train/per_policy.csv')
    assert len(measurements) == 80
    indexed = {(r['budget'], r['policy'], int(r['block'])): r for r in measurements}
    assert len(indexed) == 80
    assert {r['probe'] for r in measurements} == {'train'}
    gate_by_budget = {r['budget']: r for r in gate['budgets']}
    expected = []
    passes = {}
    for name in ('p01', 'p02'):
        this_budget = []
        for comparator in ('random', 'mean', 'shuffled'):
            differences = []
            same = 0
            for bank in range(10):
                co = indexed[name, 'coactivity', bank]
                other = indexed[name, comparator, bank]
                co_error, other_error = float(co['raw_slot_l1']), float(other['raw_slot_l1'])
                assert math.isfinite(co_error) and math.isfinite(other_error)
                differences.append(co_error - other_error)
                same += co['canonical_graph'] == other['canonical_graph']
            mean = statistics.fmean(differences)
            median = statistics.median(differences)
            wins = sum(x < -eps for x in differences)
            losses = sum(x > eps for x in differences)
            ties = len(differences) - wins - losses
            if comparator == 'random':
                passed = mean < design['random']['mean_less_than'] and median < design['random']['median_less_than'] and wins >= design['random']['minimum_strict_wins']
            else:
                passed = mean <= design['specificity']['mean_at_most'] and wins >= losses
            row = dict(budget=name, budget_percent=100*protocol['budgets'][name]['fraction'], comparator=comparator,
                       n=len(differences), mean_difference=mean, median_difference=median,
                       wins=wins, ties=ties, losses=losses, same_selected_graph=same, comparison_passed=passed)
            this_budget.append(row)
            observed = gate_by_budget[name]['observed'][comparator]
            for src, dest in [('mean_difference', 'mean'), ('median_difference', 'median')]:
                close(row[src], observed[dest], f'gate {name} {comparator} {src}')
            for src, dest in [('n', 'n'), ('wins', 'coactivity_better'), ('ties', 'tied'), ('losses', 'coactivity_worse'), ('same_selected_graph', 'same_selected_graph')]:
                assert row[src] == observed[dest], (name, comparator, src)
        passes[name] = all(r['comparison_passed'] for r in this_budget)
        assert passes[name] == gate_by_budget[name]['passed']
        for row in this_budget:
            row['budget_passed'] = passes[name]
        expected.extend(this_budget)
    joint = all(passes.values())
    assert passes == {'p01': False, 'p02': True} and joint is False
    assert gate['proceed_migration'] is joint
    assert ledger['status'] == 'not_run' and ledger['scientific_runs'] == 0
    assert ledger['gate_sha256'] == digest(budget/'gate.json')
    assert not (budget/'run-migration-complete.json').exists()
    evidence_files = ['protocol.json', 'gate.json', 'migration-ledger.json', 'analysis-train/per_policy.csv']
    result = dict(status='pass', scope='Original per-policy pairs, fixed protocol, archived gate, new publication table; no simulation.',
                  rows=expected, budget_passes=passes, proceed_migration=joint,
                  evidence_sha256={name: digest(budget/name) for name in evidence_files})
    expected_by_key = {(r['budget'], r['comparator']): r for r in expected}

    def check_table(rows, source):
        assert len(rows) == 6, (source, len(rows))
        assert {(r['budget'], r['comparator']) for r in rows} == set(expected_by_key)
        for actual in rows:
            wanted = expected_by_key[actual['budget'], actual['comparator']]
            assert set(actual) == set(wanted), (source, set(actual), set(wanted))
            for key, value in wanted.items():
                if key in ('budget', 'comparator'):
                    assert actual[key] == value
                elif key in ('comparison_passed', 'budget_passed'):
                    assert boolean(actual[key]) == value, (source, key, actual[key], value)
                elif key in ('n', 'wins', 'ties', 'losses', 'same_selected_graph'):
                    assert int(actual[key]) == value, (source, key)
                else:
                    close(actual[key], value, (source, key))

    payload = read_json(figures/'activity-budget-figure-data.json')
    check_table(payload['comparison_rows'], 'figure JSON')
    check_table(csv_rows(figures/'paired-comparison-values.csv'), 'paired CSV')
    decision = payload['decision_summary']
    assert decision['epsilon'] == eps
    assert decision['both_budgets_required'] is True
    assert decision['proceed_migration'] is False
    published_budgets = decision['budgets']
    if isinstance(published_budgets, dict):
        published_passes = {key: value if isinstance(value, bool) else value['passed'] for key, value in published_budgets.items()}
    else:
        published_passes = {row['budget']: row['passed'] for row in published_budgets}
    assert published_passes == passes, published_passes
    result['new_publication_json_and_csv_checked'] = True
    result['figure_source_sha256'] = digest(root/'plot_activity_budget.py')
    result['publication_sha256'] = {name: digest(figures/name) for name in ['activity-budget-figure-data.json', 'paired-comparison-values.csv']}
    namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    documents = {}
    for language in ('en', 'zh'):
        document = root/f'local-circuit-aggregation-preprint-{language}.docx'
        with zipfile.ZipFile(document) as archive:
            xml = ET.fromstring(archive.read('word/document.xml'))
        def cell_text(node):
            return ''.join(element.text or '' for element in node.findall('.//w:t', namespaces))
        candidates = [table for table in xml.findall('.//w:tbl', namespaces)
                      if ('W/T/L' if language == 'en' else '胜/平/负') in cell_text(table)]
        assert len(candidates) == 1, (language, len(candidates))
        table = [[cell_text(cell) for cell in row.findall('w:tc', namespaces)]
                 for row in candidates[0].findall('w:tr', namespaces)]
        assert len(table) == 10, (language, table)
        names = {'random': 'Random', 'mean': 'Mean activity', 'shuffled': 'Shuffled'} if language == 'en' else {'random': '随机', 'mean': '平均活动', 'shuffled': '时间打乱'}
        statuses = {True: 'Pass', False: 'Fail'} if language == 'en' else {True: '通过', False: '未通过'}
        for actual, wanted in zip(table[1:7], expected):
            assert len(actual) == 7
            assert actual[0] == format(wanted['budget_percent'], '.3f')
            assert actual[1] == names[wanted['comparator']]
            for column, key in ((2, 'mean_difference'), (3, 'median_difference')):
                assert abs(float(actual[column]) - 100*wanted[key]) <= .00500000001, (language, actual, key)
            assert actual[4] == f"{wanted['wins']}/{wanted['ties']}/{wanted['losses']}"
            assert actual[5] == f"{wanted['same_selected_graph']}/10"
            assert actual[6] == statuses[wanted['comparison_passed']]
        assert len(table[7]) == len(table[8]) == len(table[9]) == 2
        assert '0.984' in table[7][0] and table[7][1] == statuses[False]
        assert '1.968' in table[8][0] and table[8][1] == statuses[True]
        assert table[9][1] == ('Stop' if language == 'en' else '停止')
        labels = read_json(root/f'document-labels-{language}.json')
        assert labels['maps']['TABLE']['12'] == '8'
        documents[language] = dict(status='pass', reader_table='8', pair_rows=6,
                                   budget_summary_rows=2, joint_stop_rows=1,
                                   actual_cells=table, sha256=digest(document))
    result['bilingual_docx_table_audit'] = documents
    result['auditor_sha256'] = digest(Path(__file__))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
