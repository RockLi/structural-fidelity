"""Plot supplied E3 zero-retention trajectories; no simulation or data fitting."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-dir', type=Path, default=ROOT/'evidence/e3-zero-retention/run')
parser.add_argument('--output-dir', type=Path, default=ROOT/'figures')
parser.add_argument('--metadata-path', type=Path)
args = parser.parse_args()
RUN = args.run_dir.resolve()
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
META = (args.metadata_path or OUT.parent/'trajectory-figure-data.json').resolve()
META.parent.mkdir(parents=True, exist_ok=True)

def read(name):
    with (RUN / name).open() as stream:
        return [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stream)]

raw_name = 'slots/raw_sum-zero.csv'
history_name = 'slots/original_instrumented-zero.csv'
raw, history = read(raw_name), read(history_name)
assert len(raw) == len(history) == 200
assert [(r['slot'], r['explicit_spikes']) for r in raw] == [
    (r['slot'], r['explicit_spikes']) for r in history]
assert all(r['explicit_spikes'] == r['approx_spikes'] for r in raw)
slots = np.array([r['slot'] for r in raw])
assert np.array_equal(slots, np.arange(1, 201))
time = slots * .1
reference = np.array([r['explicit_spikes'] for r in raw])
raw_counts = np.array([r['approx_spikes'] for r in raw])
delta = np.array([r['approx_spikes'] - r['explicit_spikes'] for r in history])
assert np.count_nonzero(delta) == 146

plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11,
    'axes.labelsize': 10, 'axes.spines.top': False, 'axes.spines.right': False,
    'pdf.fonttype': 42, 'savefig.facecolor': 'white',
})
fig, axes = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True,
                         gridspec_kw={'height_ratios': [1.35, 1]}, layout='constrained')
axes[0].plot(time, reference, color='#333333', lw=1.1, label='Explicit reference')
axes[0].plot(time, raw_counts, color='#357B59', lw=.7, ls='--', marker='o',
             markevery=4, ms=3.3, markerfacecolor='none', label='Raw sum (all 200 slots agree)')
axes[0].set_title('A   E3 zero retention population counts', loc='left')
axes[0].set_ylabel('Spikes per 0.1 ms slot')
axes[0].legend(frameon=False, loc='upper right', fontsize=9)
axes[1].vlines(time, 0, delta, color='#32658D', lw=.9, alpha=.8)
axes[1].scatter(time, delta, color='#32658D', s=9, label='History minus reference (146 differing slots)')
axes[1].plot(time, raw_counts-reference, color='#357B59', lw=1.2,
             label='Raw sum minus reference (zero throughout)')
axes[1].set_title('B   Count differences at the same slots', loc='left')
axes[1].set_ylabel('Spike-count difference')
axes[1].set_xlabel('Elapsed time / ms')
fig.legend(*axes[1].get_legend_handles_labels(), frameon=False,
           loc='outside lower center', ncol=1, fontsize=9)
for ax in axes:
    ax.grid(alpha=.16)
    ax.set_axisbelow(True)
    ax.set_xlim(0, 20)
    ax.set_xticks([0, 5, 10, 15, 20])
out = OUT / 'fig6_e3_trajectories'
fig.savefig(out.with_suffix('.png'), dpi=250, bbox_inches='tight', pad_inches=.12)
fig.savefig(out.with_suffix('.pdf'), bbox_inches='tight', pad_inches=.12)
plt.close(fig)
data = {
    'figure': 'Figure 4',
    'scope': 'Visualization of the explicitly selected E3 zero-retention run; this plotting command performs no simulation',
    'sources': {os.path.relpath(RUN/name, META.parent): hashlib.sha256((RUN/name).read_bytes()).hexdigest()
                for name in [raw_name, history_name]},
    'slots': 200, 'dt_ms': .1, 'units': 12500,
    'reference_spikes': int(reference.sum()), 'raw_spikes': int(raw_counts.sum()),
    'history_spikes': int(reference.sum()+delta.sum()),
    'raw_mismatched_slots': 0, 'history_mismatched_slots': int(np.count_nonzero(delta)),
    'history_max_absolute_slot_difference': int(np.abs(delta).max()),
    'plot_transform': 'No smoothing, binning, lag shift or fitting; elapsed time=archived one-based completed-slot index*0.1 ms; difference=approx-explicit',
    'marker_subsampling': 'Raw sum open circles every fourth slot for legibility; line contains all slots',
}
META.write_text(json.dumps(data, indent=2)+'\n')
print(json.dumps(data, indent=2))
