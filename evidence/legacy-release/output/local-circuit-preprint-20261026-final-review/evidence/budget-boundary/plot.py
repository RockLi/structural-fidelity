#!/usr/bin/env python3
"""Plot locked stage outputs without altering scientific tables or decisions."""
from pathlib import Path
import argparse,csv,hashlib,json,os
import numpy as np

POLICIES=['random','mean','coactivity','shuffled']
LABELS=['Random','Mean','Coactivity','Shuffled']
COLORS=['#707a84','#c88730','#287e87','#8a63a2']
BUDGETS=['p01','p02']
TITLE={'p01':'28 changed adjacencies (0.984%)','p02':'56 changed adjacencies (1.968%)'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def value(x):return float(x) if x not in ['',None] else np.nan

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['train','migration'],default='train')
    p.add_argument('--analysis-dir',type=Path);p.add_argument('--output-dir',type=Path);a=p.parse_args()
    base=a.analysis_dir.resolve() if a.analysis_dir else Path(__file__).resolve().parent/f'analysis-{a.stage}'
    out=a.output_dir.resolve() if a.output_dir else base/'figures'
    assert not out.exists() or not any(out.iterdir()),'Preserve earlier figures; choose empty directory'
    out.mkdir(parents=True,exist_ok=True)
    names=['summary.json','per_policy.csv','per_block_endpoints.csv','paired_contrasts.csv','training_score_pairs.csv']
    inputs={n:sha(base/n) for n in names};summary=json.loads((base/'summary.json').read_text())
    assert summary['status']=='pass' and summary['stage']==a.stage
    policies=rows(base/'per_policy.csv');endpoints=rows(base/'per_block_endpoints.csv');contrasts=rows(base/'paired_contrasts.csv')
    scores=rows(base/'training_score_pairs.csv');endpoint='train' if a.stage=='train' else 'migration_mean'
    os.environ.setdefault('MPLCONFIGDIR','/tmp/activity-guided-budget-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,
        'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42,'savefig.dpi':220})
    def finish(fig,name):
        fig.savefig(out/f'{name}.png',bbox_inches='tight',metadata={'Software':'Nested budget locked analysis'})
        fig.savefig(out/f'{name}.pdf',bbox_inches='tight',metadata={'Creator':'Nested budget locked analysis','CreationDate':None,'ModDate':None})
        plt.close(fig)
    def panel(ax,budget,metric='endpoint_raw_slot_l1',probe=None):
        source=endpoints if probe is None else policies
        for i,policy in enumerate(POLICIES):
            rr=sorted([r for r in source if r['budget']==budget and r['policy']==policy and (probe is None or r['probe']==probe)],key=lambda r:int(r['block']))
            yy=np.array([value(r[metric]) for r in rr])*100
            ax.scatter(i+np.linspace(-.13,.13,len(yy)),yy,c=COLORS[i],s=24,alpha=.75,zorder=3)
            good=yy[np.isfinite(yy)]
            if len(good):ax.plot([i-.2,i+.2],[good.mean()]*2,c='#222222',lw=2,zorder=4)
            else:ax.text(i,.5,'n/a',transform=ax.get_xaxis_transform(),ha='center',color=COLORS[i],fontsize=8)
        ax.set_xticks(range(4),LABELS,rotation=18,ha='right');ax.set_xlim(-.5,3.5);ax.grid(axis='y',alpha=.2)
    fig,axes=plt.subplots(1,2,figsize=(7.0,3.6),sharey=True)
    for ax,b in zip(axes,BUDGETS):panel(ax,b);ax.set_title(TITLE[b],loc='left',weight='bold')
    axes[0].set_ylabel('Identified raw-slot L1 (%)')
    stage_label='Training input; gate fixed before these outcomes.' if a.stage=='train' else 'Mean across three prior-known test inputs; conditional on training gate.'
    fig.subplots_adjust(left=.12,right=.98,top=.88,bottom=.26,wspace=.13)
    fig.text(.5,.025,stage_label+'\nPoints are ten paired candidate banks; bars are means. All 2,845 edges remain.',ha='center',fontsize=8)
    finish(fig,'policy-endpoints')
    fig,axes=plt.subplots(2,3,figsize=(7.2,4.8),sharey=True)
    all_diffs=[abs(value(r['difference_coactivity_minus_comparator'])*100) for r in contrasts if r['probe']==endpoint]
    finite_diffs=[x for x in all_diffs if np.isfinite(x)]
    difference_limit=max(.1,1.12*max(finite_diffs,default=0.))
    for i,b in enumerate(BUDGETS):
        for ax,c,label in zip(axes[i],['random','mean','shuffled'],['Random','Mean','Shuffled']):
            rr=sorted([r for r in contrasts if r['budget']==b and r['probe']==endpoint and r['comparator']==c],key=lambda r:int(r['block']))
            yy=np.array([value(r['difference_coactivity_minus_comparator']) for r in rr])*100
            ax.axhline(0,c='#555555',lw=1,ls='--');ax.scatter(range(1,11),yy,c=COLORS[2],s=24,zorder=3)
            if np.any(np.isfinite(yy)):ax.axhline(np.nanmean(yy),c='#222222',lw=1.3)
            ax.set_title(('~1%: ' if i==0 else '~2%: ')+'Coactivity − '+label,loc='left',fontsize=9,weight='bold')
            ax.set_xticks([1,5,10]);ax.grid(axis='y',alpha=.2)
            ax.set_ylim(-difference_limit,difference_limit)
            if i==1:ax.set_xlabel('Candidate-bank block')
        axes[i,0].set_ylabel('Raw-slot L1 difference\n(percentage points)')
    fig.subplots_adjust(left=.12,right=.99,top=.93,bottom=.18,wspace=.16,hspace=.38)
    fig.text(.5,.025,'Negative favors coactivity; dashed line is equality, solid line is the block mean.\nNested budgets and overlapping selectors are paired observations, not new network replicates.',ha='center',fontsize=8)
    finish(fig,'paired-contrasts')
    if a.stage=='train':
        fig,axes=plt.subplots(2,3,figsize=(7.2,4.9))
        for i,b in enumerate(BUDGETS):
            for ax,metric,label in zip(axes[i],['bin1ms_l1','cumulative_l1','Rcount'],['1-ms identified L1 (%)','30-ms count L1 (%)','Count fraction (%)']):
                panel(ax,b,metric,'train');ax.set_title(('~1%: ' if i==0 else '~2%: ')+label,loc='left',fontsize=8,weight='bold')
        fig.subplots_adjust(left=.07,right=.99,top=.93,bottom=.16,hspace=.45,wspace=.28)
        fig.text(.5,.025,'Prespecified secondary training readouts do not replace the raw-slot gate.\nCount fraction = Dcount / Dslot; undefined values are marked n/a and separately tabulated.',ha='center',fontsize=8)
        finish(fig,'secondary-readouts')
        fig,axes=plt.subplots(1,2,figsize=(6.8,3.3),sharey=True)
        for ax,b in zip(axes,BUDGETS):
            rr=sorted([r for r in scores if r['budget']==b and r['comparator']=='random'],key=lambda r:int(r['block']))
            yy=np.array([value(r['ratio_coactivity_to_comparator']) for r in rr]);ax.scatter(range(1,11),yy,c=COLORS[2],s=28)
            if not np.any(np.isfinite(yy)):ax.text(.5,.5,'All ratios undefined',transform=ax.transAxes,ha='center',fontsize=9)
            ax.axhline(1,c='#555555',ls='--',lw=1);ax.set_xticks([1,5,10]);ax.set_xlabel('Candidate-bank block');ax.grid(axis='y',alpha=.2)
            ax.set_title(TITLE[b],loc='left',weight='bold')
        axes[0].set_ylabel('Selected / random training J')
        fig.subplots_adjust(left=.13,right=.98,top=.87,bottom=.24,wspace=.15)
        fig.text(.5,.025,'Frozen-source coactivity score. Lower scores follow candidate selection by design.\nIf the random score is zero, the ratio is undefined and omitted, not replaced by zero.',ha='center',fontsize=8)
        finish(fig,'training-score-ratios')
    else:
        fig,axes=plt.subplots(3,2,figsize=(7.0,6.3),sharey=True)
        for i,probe in enumerate(['spatial','temporal','spatiotemporal']):
            for j,b in enumerate(BUDGETS):panel(axes[i,j],b,'raw_slot_l1',probe);axes[i,j].set_title(b+' / '+probe,loc='left',weight='bold')
            axes[i,0].set_ylabel('Raw-slot L1 (%)')
        fig.subplots_adjust(left=.12,right=.98,top=.95,bottom=.12,hspace=.45,wspace=.15)
        fig.text(.5,.025,'Every prior-known input is shown; none is selected after outcomes.\nConditional transfer checks share graph identities and are not independent samples.',ha='center',fontsize=8)
        finish(fig,'individual-known-inputs')
    assert all(sha(base/n)==h for n,h in inputs.items())
    (out/'figure-validation.json').write_text(json.dumps(dict(status='pass',stage=a.stage,source_sha256=sha(Path(__file__)),
        inputs=inputs,outputs={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(dict(status='pass',stage=a.stage,figure_pairs=4 if a.stage=='train' else 3)))

if __name__=='__main__':main()
