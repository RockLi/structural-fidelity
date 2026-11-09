#!/usr/bin/env python3
"""Manuscript rendering of locked sensitivity summaries. Only labels differ from the frozen plotting script; numerical plot data are checked against its output."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
PROBES = ['tonic', 'global_burst', 'focal_burst']
NAMES = ['Tonic', 'Global burst', 'Focal burst']
GROUPS = ['extensive', 'swap', 'jitter_1e-4', 'jitter_1e-3', 'jitter_1e-2']
LABELS = ['Broad\nrewire', 'One\nswap', 'δV\n$10^{-4}$', 'δV\n$10^{-3}$', 'δV\n$10^{-2}$']
COLORS = ['#a54850', '#237e8b', '#d4a741', '#c87a34', '#a85425']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readcsv(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def number(row, key):
    return float(row[key]) if row[key] != '' else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent/'evidence/sensitivity')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    analysis = root / 'analysis'
    output = args.output_dir.resolve() if args.output_dir else Path(__file__).resolve().parent/'sensitivity-figures'
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/sensitivity-calibration-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    inputs = {str(path.relative_to(root)): sha(path) for path in [
        analysis / 'comparisons.csv', analysis / 'swap-input-diagnostics.csv',
        analysis / 'curves-1ms.csv', analysis / 'analysis-complete.json']}
    assert json.loads((analysis / 'analysis-complete.json').read_text())['status'] == 'pass'
    rows = readcsv(analysis / 'comparisons.csv')
    swaps = readcsv(analysis / 'swap-input-diagnostics.csv')
    curves = readcsv(analysis / 'curves-1ms.csv')
    assert len(rows) == 288 and len(swaps) == 57
    plt.rcParams.update({'font.size': 8.5, 'axes.titlesize': 9, 'axes.labelsize': 8.5,
        'xtick.labelsize': 7.5, 'ytick.labelsize': 8, 'axes.spines.top': False,
        'axes.spines.right': False, 'savefig.dpi': 220, 'pdf.fonttype': 42})
    outputs = []

    def save(fig, stem):
        for ext in ['png', 'pdf']:
            path = output / f'{stem}.{ext}'
            fig.savefig(path)
            outputs.append(path)
        plt.close(fig)

    figure_data = {'inputs_sha256': inputs, 'primary_scatter': [], 'cancellation_scatter': [],
        'swap_scatter': [], 'curve_summaries': [],
        'intervals': 'Full descriptive range across 19 controls; not a confidence interval',
        'selection': 'All prespecified controls displayed; no point selected by outcome'}
    fig, axes = plt.subplots(2, 3, figsize=(6.56, 5.5), layout='constrained', sharex='col')
    for col, (probe, title) in enumerate(zip(PROBES, NAMES)):
        for axis_row, key in enumerate(['chunk_bin_l1_relative', 'population_bin_l1_relative']):
            ax = axes[axis_row, col]
            for position, (group, color) in enumerate(zip(GROUPS, COLORS)):
                subset = sorted([r for r in rows if r['probe'] == probe and r['group'] == group], key=lambda r: int(r['seed']))
                assert len(subset) == 19
                values = np.array([float(r[key]) * 100 for r in subset])
                ax.scatter(position + np.linspace(-.16, .16, 19), values,
                    color=color, alpha=.8, s=15, linewidths=.3, edgecolors='white', zorder=3)
                ax.plot([position - .21, position + .21], [np.median(values)] * 2, color='#222', linewidth=1.3, zorder=4)
                figure_data['primary_scatter'].append(dict(probe=probe, group=group, metric=key,
                    stems=[r['stem'] for r in subset], values_pct=values.tolist(), median_pct=float(np.median(values))))
            ax.set_xticks(range(5), LABELS)
            ax.set_ylim(bottom=-2)
            ax.axhline(0, color='#aaa', linewidth=.5)
            if axis_row == 0:
                ax.set_title(title)
            if col == 0:
                ax.set_ylabel(('Identified-chunk' if axis_row == 0 else 'Population') + ' L1 (%)')
    fig.suptitle('Sensitivity calibration on one fixed original graph\nAll 19 controls per group; 1 ms bins; black bars show medians', fontsize=11)
    save(fig, 'sensitivity-calibration')

    fig, axes = plt.subplots(1, 3, figsize=(6.56, 3.4), layout='constrained', sharey=True)
    for ax, probe, title in zip(axes, PROBES, NAMES):
        for position, (group, color) in enumerate(zip(GROUPS, COLORS)):
            subset = sorted([r for r in rows if r['probe'] == probe and r['group'] == group], key=lambda r: int(r['seed']))
            valid = [r for r in subset if r['cancellation_fraction'] != '']
            values = np.array([float(r['cancellation_fraction']) for r in valid])
            if len(values):
                ax.scatter(position + np.linspace(-.16, .16, len(values)), values, color=color, alpha=.8, s=16)
                ax.plot([position - .2, position + .2], [np.median(values)] * 2, color='#222', linewidth=1.2)
            ax.text(position, 1.035, f'{len(valid)}/19', ha='center', va='bottom', fontsize=7)
            figure_data['cancellation_scatter'].append(dict(probe=probe, group=group,
                defined=len(valid), undefined=19-len(valid), values=values.tolist(),
                stems=[r['stem'] for r in valid]))
        ax.set_title(title)
        ax.set_xticks(range(5), LABELS)
        ax.set_ylim(-.03, 1.13)
        ax.set_yticks([0, .25, .5, .75, 1])
    axes[0].set_ylabel('Cancellation: 1 − population L1 / chunk L1')
    fig.suptitle('Cancellation computed within each graph and input\nLabels show defined values; zero chunk error gives an undefined ratio', fontsize=11)
    save(fig, 'cancellation-calibration')

    fig, axes = plt.subplots(1, 3, figsize=(6.56, 3.6), layout='constrained')
    arm_colors = ['#267e8b', '#d68c35', '#9b5793', '#607e46']
    arm_names = ['E→E', 'E→I', 'I→E', 'I→I']
    for ax, probe, title in zip(axes, PROBES, NAMES):
        subset = sorted([r for r in swaps if r['probe'] == probe], key=lambda r: int(r['seed']))
        for row in subset:
            x = float(row['shared_input_difference_l1'])
            y = float(row['chunk_bin_l1_relative']) * 100
            ax.scatter(x, y, c=arm_colors[int(row['arm'])], s=26, alpha=.9, edgecolors='white', linewidths=.4)
            figure_data['swap_scatter'].append(dict(stem=row['stem'], probe=probe, arm=int(row['arm']),
                shared_input_l1=x, chunk_l1_pct=y,
                input_identical=row['shared_input_identical_in_window'] == 'True'))
        ax.set_title(title)
        ax.set_xlabel('Shared-source input L1')
        ax.set_ylim(bottom=-2)
        ax.axhline(0, color='#aaa', linewidth=.5)
    axes[0].set_ylabel('Identified-chunk L1 (%)')
    handles = [Line2D([0], [0], marker='o', linestyle='', color=color, label=name)
               for color, name in zip(arm_colors, arm_names)]
    fig.legend(handles=handles, loc='outside lower center', ncol=4, frameon=False)
    fig.suptitle('Was the minimal swap activated by the original source activity?\nSource slots 0–297 can arrive within the 300-slot observation', fontsize=11)
    save(fig, 'swap-activation')

    fig, axes = plt.subplots(2, 3, figsize=(6.56, 5.8), layout='constrained', sharex=True)
    for col, (probe, title) in enumerate(zip(PROBES, NAMES)):
        for group, color in zip(GROUPS, COLORS):
            subset = [r for r in curves if r['probe'] == probe and r['group'] == group]
            stems = sorted(set(r['stem'] for r in subset))
            assert len(stems) == 19
            lookup = {(r['stem'], float(r['time_end_ms'])): r for r in subset}
            times = sorted(set(float(r['time_end_ms']) for r in subset))
            assert len(times) == 30
            for axis_row, key in enumerate(['cumulative_chunk_l1_full_denominator', 'state_rms_standardized']):
                values = np.array([[float(lookup[stem, time][key]) for time in times] for stem in stems])
                if axis_row == 0:
                    values *= 100
                med, low, high = np.median(values, axis=0), values.min(axis=0), values.max(axis=0)
                ax = axes[axis_row, col]
                ax.fill_between(times, low, high, color=color, alpha=.1, linewidth=0)
                ax.plot(times, med, color=color, linewidth=1.3, label=group)
                figure_data['curve_summaries'].append(dict(probe=probe, group=group, metric=key,
                    times_ms=times, median=med.tolist(), minimum=low.tolist(), maximum=high.tolist()))
        axes[0, col].set_title(title)
        axes[1, col].set_xlabel('Time (ms)')
        for ax in axes[:, col]:
            ax.set_xlim(0, 30)
            ax.axvline(8, color='#bbb', linestyle=':', linewidth=.6)
            ax.axvline(15, color='#bbb', linestyle=':', linewidth=.6)
    axes[0, 0].set_ylabel('Cumulative chunk L1 (%)\nFull-window denominator')
    axes[1, 0].set_ylabel('State RMS / original channel SD')
    handles = [Line2D([0], [0], color=color, label=label.replace('\n', ' ')) for color, label in zip(COLORS, LABELS)]
    fig.legend(handles=handles, loc='outside lower center', ncol=5, frameon=False, fontsize=8)
    fig.suptitle('Time-resolved calibration\nLines show medians; shaded areas show full control ranges, not confidence intervals', fontsize=11)
    save(fig, 'sensitivity-time-course')

    assert all(sha(root / path) == digest for path, digest in inputs.items())
    frozen_figure_data=json.loads((analysis/'sensitivity-figure-data.json').read_text())
    for key in ['primary_scatter','cancellation_scatter','swap_scatter','curve_summaries']:
        assert figure_data[key]==frozen_figure_data[key], key
    figure_data['presentation_only_change']='Shortened shared-source x-axis label to prevent overlap; all numerical plot data match the frozen plot output.'
    figure_data['plot_script_sha256'] = sha(Path(__file__))
    figure_data['outputs_sha256'] = {path.name: sha(path) for path in outputs}
    (output / 'sensitivity-figure-data.json').write_text(json.dumps(figure_data, indent=2, allow_nan=False) + '\n')
    print('PASS: four sensitivity figures regenerated from new analysis CSV files.', flush=True)


if __name__ == '__main__':
    main()
