#!/usr/bin/env python3
"""Render fixed policy comparisons from audited numerical analysis tables."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

POLICIES=['random','mean','coactivity','shuffled']
LABELS=['Random','Mean','Coactivity','Shuffled']
COLORS=['#707a84','#c88730','#287e87','#8a63a2']
PROBES=['train','spatial','temporal','spatiotemporal']
PROBE_LABELS={'train':'Training input','spatial':'New spatial mask',
              'temporal':'Split pulse','spatiotemporal':'New mask + split pulse',
              'heldout_mean':'Mean across three held-out inputs'}


def read(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def number(value):
    return float(value) if value not in ['',None] else np.nan


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis-dir',type=Path,default=Path(__file__).resolve().parent/'analysis')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args();base=args.analysis_dir.resolve()
    out=args.output_dir.resolve() if args.output_dir else base/'figures'
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Use a new empty figure directory; preserve earlier figures.')
    out.mkdir(parents=True,exist_ok=True)
    summary=json.loads((base/'summary.json').read_text())
    assert summary['status']=='pass' and summary['blocks']==10
    per_policy=read(base/'per_policy.csv')
    endpoints=read(base/'per_block_endpoints.csv')
    contrasts=read(base/'paired_contrasts.csv')
    inputs={name:sha(base/name) for name in ['summary.json','per_policy.csv','per_block_endpoints.csv','paired_contrasts.csv']}
    os.environ.setdefault('MPLCONFIGDIR','/tmp/activity-guided-retention-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
                         'axes.spines.top':False,'axes.spines.right':False,
                         'axes.titlesize':10,'axes.labelsize':9,
                         'xtick.labelsize':8,'ytick.labelsize':8,
                         'pdf.fonttype':42,'savefig.dpi':220})

    def finish(fig,name):
        fig.savefig(out/(name+'.png'),bbox_inches='tight',metadata={'Software':'Activity-guided retention locked analysis'})
        fig.savefig(out/(name+'.pdf'),bbox_inches='tight',
                    metadata={'Creator':'Activity-guided retention locked analysis','CreationDate':None,'ModDate':None})
        plt.close(fig)

    def policy_panel(ax,probe,metric='raw_slot_l1',percent=True):
        multiplier=100 if percent else 1
        for i,policy in enumerate(POLICIES):
            if probe=='heldout_mean':
                rows=sorted([r for r in endpoints if r['policy']==policy],key=lambda r:int(r['block']))
                yy=np.array([number(r['heldout_raw_slot_l1_mean']) for r in rows])*multiplier
            else:
                rows=sorted([r for r in per_policy if r['policy']==policy and r['probe']==probe],key=lambda r:int(r['block']))
                yy=np.array([number(r[metric]) for r in rows])*multiplier
            ax.scatter(i+np.linspace(-.13,.13,10),yy,color=COLORS[i],s=24,alpha=.75,zorder=3)
            valid=yy[np.isfinite(yy)]
            if len(valid):ax.plot([i-.20,i+.20],[np.mean(valid)]*2,color='#222222',lw=2,zorder=4)
        ax.set_xticks(range(4),LABELS,rotation=18,ha='right')
        ax.set_xlim(-.5,3.5);ax.grid(axis='y',alpha=.2)
        ax.set_title(PROBE_LABELS[probe],loc='left',weight='bold')

    fig,axes=plt.subplots(2,2,figsize=(6.8,5.2),sharey=True)
    for ax,probe in zip(axes.ravel(),['heldout_mean','spatial','temporal','spatiotemporal']):
        policy_panel(ax,probe)
    axes[0,0].set_ylabel('Identified raw-slot L1 (%)');axes[1,0].set_ylabel('Identified raw-slot L1 (%)')
    fig.subplots_adjust(left=.12,right=.98,top=.92,bottom=.16,hspace=.43,wspace=.15)
    fig.text(.5,.025,'Ten matched candidate-bank blocks; points are block outcomes, bars are means.\n'
             'Top left averages three held-out inputs within each block; no training error enters it.',ha='center',fontsize=8)
    finish(fig,'heldout-policy-errors')

    fig,axes=plt.subplots(1,3,figsize=(6.8,3.4),sharey=True)
    for ax,comparator,label in zip(axes,['random','mean','shuffled'],['Random','Mean','Shuffled']):
        rows=sorted([r for r in contrasts if r['probe']=='heldout_mean' and r['comparator']==comparator],
                    key=lambda r:int(r['block']))
        yy=np.array([number(r['difference_coactivity_minus_comparator']) for r in rows])*100
        ax.axhline(0,color='#555555',lw=1,ls='--')
        ax.scatter(range(1,11),yy,color=COLORS[2],s=28,zorder=3)
        valid=yy[np.isfinite(yy)]
        if len(valid):ax.axhline(np.mean(valid),color='#222222',lw=1.5)
        ax.set_xticks([1,5,10]);ax.set_xlabel('Candidate-bank block')
        ax.set_title('Coactivity − '+label,loc='left',weight='bold');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Held-out mean L1 difference\n(percentage points)')
    fig.subplots_adjust(left=.13,right=.99,top=.87,bottom=.23,wspace=.15)
    fig.text(.5,.025,'Negative favors coactivity; dashed line is equality, solid line is the block mean.\n'
             'Same selected graph yields a paired zero; overlapping selections remain in the analysis.',ha='center',fontsize=8)
    finish(fig,'paired-heldout-contrasts')

    fig,axes=plt.subplots(1,2,figsize=(6.8,3.6),sharey=True)
    policy_panel(axes[0],'train');policy_panel(axes[1],'heldout_mean')
    axes[0].set_ylabel('Identified raw-slot L1 (%)')
    fig.subplots_adjust(left=.12,right=.98,top=.88,bottom=.25,wspace=.15)
    fig.text(.5,.025,'Training and test panels use closed-loop outcomes; selection scores are not output error.\n'
             'All graphs retain 2,845 edges. Coactivity uses same-time second moments, not event order.',ha='center',fontsize=8)
    finish(fig,'training-and-transfer')

    fig,axes=plt.subplots(2,3,figsize=(7.2,5.2))
    for col,probe in enumerate(PROBES[1:]):
        policy_panel(axes[0,col],probe,metric='cumulative_l1')
        policy_panel(axes[1,col],probe,metric='Rcount')
        axes[1,col].set_title('Count fraction of discrepancy',loc='left',weight='bold',fontsize=9)
    axes[0,0].set_ylabel('30-ms identified-count L1 (%)')
    axes[1,0].set_ylabel('Dcount / Dslot (%)')
    fig.subplots_adjust(left=.10,right=.99,top=.92,bottom=.16,hspace=.47,wspace=.28)
    fig.text(.5,.025,'Top: cumulative-count error. Bottom: count-component share of nonzero raw-slot errors.\n'
             'Undefined fractions are omitted, never replaced by zero; denominators are tabulated.',ha='center',fontsize=8)
    finish(fig,'secondary-count-readouts')
    assert all(sha(base/name)==digest for name,digest in inputs.items())
    report=dict(status='pass',source_sha256=sha(Path(__file__)),inputs=inputs,
                numerical_files_unchanged=True,
                outputs={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'figure-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status='pass',figure_pairs=4),indent=2))


if __name__=='__main__':main()
