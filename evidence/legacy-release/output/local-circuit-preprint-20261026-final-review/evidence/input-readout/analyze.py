#!/usr/bin/env python3
"""Post-hoc readout analysis of immutable archived explicit trajectories.

Usage: analyze.py --sensitivity-dir PATH --output-dir NEW_DIRECTORY
No simulations, fitting, seed selection or graph edits occur here.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

PROBES = ['tonic', 'global_burst', 'focal_burst']
LABELS = ['Tonic', 'Global burst', 'Focal burst']
WIDTHS = [1, 2, 10, 50, 300]
TAUS = [.1, .2, 1., 5., 30.]
READOUTS = ['identified', 'EI', 'global']
GROUPS = ['swap', 'extensive']
CATEGORIES = ['input_zero_state_equal', 'input_changed_spikes_equal',
              'spikes_changed_1ms_equal', '1ms_changed']
DT = .1


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                   allow_nan=False) + '\n')


def table(path, rows):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def describe(values):
    values = [float(x) for x in values if x is not None]
    return dict(n=len(values), median=float(np.median(values)) if values else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def binned(delta, width, offset):
    # Integer boundaries intersected with [0,T); never drop an edge bin.
    t = len(delta)
    edges = np.array(sorted({0, t, *range(offset, t, width)}), dtype=np.int64)
    cs = np.concatenate([np.zeros((1, delta.shape[1]), dtype=np.int64),
                         np.cumsum(delta, axis=0)], axis=0)
    result = cs[edges[1:]] - cs[edges[:-1]]
    assert np.array_equal(result.sum(axis=0), delta.sum(axis=0))
    return result


def nums(delta):
    return [int(np.abs(delta).sum()),
            int(np.abs(np.stack([delta[:, :100].sum(axis=1),
                                 delta[:, 100:].sum(axis=1)], axis=1)).sum()),
            int(np.abs(delta.sum(axis=1)).sum())]


def vr2(delta, tau):
    """Original van Rossum squared distance, complete analytic tail.

    delta is a time-by-channel matrix of signed representative event counts.
    Kernel identity: D^2=0.5 sum_{k,n,m}d[n,k]d[m,k]exp(-|n-m|dt/tau).
    Independently integrate the piecewise decaying filtered difference.
    """
    delta = np.asarray(delta, dtype=np.float64)
    a = math.exp(-DT / tau)
    past = np.zeros(delta.shape[1])
    quadratic = 0.
    zs = []
    for row in delta:
        past *= a
        quadratic += float(row @ row + 2 * row @ past)
        past += row
        zs.append(float(past @ past))
    integral = .5 * ((1 - a * a) * sum(zs[:-1]) + zs[-1])
    closed = .5 * quadratic
    assert math.isclose(closed, integral, rel_tol=2e-11, abs_tol=2e-10), (closed, integral)
    assert closed >= -1e-10
    return max(0., closed)


def selfchecks():
    checks = 0
    sample = np.arange(21, dtype=np.int64).reshape(7, 3) - 10
    for width in [1, 2, 3, 7, 10]:
        for offset in range(width):
            got = binned(sample, width, offset)
            ids = [(i - offset) // width for i in range(len(sample))]
            expected = np.array([[sum(int(sample[t, k]) for t in range(len(sample)) if ids[t] == j)
                                  for k in range(3)] for j in sorted(set(ids))])
            assert np.array_equal(got, expected)
            checks += 1
    for tau in TAUS:
        a = np.zeros((7, 2)); a[2, 0] = 1
        assert math.isclose(vr2(a, tau), .5, abs_tol=1e-13)
        a[5, 0] = -1
        assert math.isclose(vr2(a, tau), 1-math.exp(-.3/tau), abs_tol=1e-13)
        a[5, 0] = 0; a[5, 1] = -1
        assert math.isclose(vr2(a, tau), 1., abs_tol=1e-13)
        assert vr2(np.zeros((7, 2)), tau) == 0
        a = np.zeros((7, 1)); a[-1, 0] = 1
        assert math.isclose(vr2(a, tau), .5, abs_tol=1e-13), 'tail must not be truncated'
        checks += 5
    return checks


def plots(out, switching, composition, bin_summary, smooth_summary):
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/local-circuit-input-readout-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titlesize': 10, 'axes.labelsize': 9,
                         'xtick.labelsize': 8, 'ytick.labelsize': 8,
                         'pdf.fonttype': 42, 'savefig.dpi': 220})
    colors = ['#287d8e', '#d7782c']
    catcolors = ['#266b53', '#7bb997', '#eebc63', '#a54f38']

    def finish(fig, name):
        fig.savefig(out / (name + '.png'), bbox_inches='tight', metadata={'Software':'input-readout post-hoc analysis'})
        fig.savefig(out / (name + '.pdf'), bbox_inches='tight',
                    metadata={'Creator':'input-readout post-hoc analysis', 'CreationDate':None, 'ModDate':None})
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 5.1), gridspec_kw={'width_ratios':[1.25, 1]})
    matrix = np.array([[CATEGORIES.index(next(r['category'] for r in switching
                        if r['seed'] == seed and r['probe'] == probe))
                        for probe in PROBES] for seed in range(93001,93020)])
    axes[0].imshow(matrix, cmap=ListedColormap(catcolors), vmin=-.5, vmax=3.5, aspect='auto')
    axes[0].set_xticks(range(3), ['Tonic','Global\nburst','Focal\nburst'])
    axes[0].set_yticks(range(19), [str(seed) for seed in range(93001,93020)])
    axes[0].set_ylabel('Same swap graph across inputs')
    axes[0].set_title('A  Input-dependent visibility', loc='left', weight='bold')
    for i in range(19):
        for j in range(3):
            axes[0].text(j, i, str(matrix[i,j]+1), ha='center', va='center', fontsize=8,
                         color='white' if matrix[i,j] in [0,3] else '#222222')
    vals = [sum(r['category']==c for r in switching) for c in CATEGORIES]
    axes[1].barh(range(4), vals, color=catcolors)
    axes[1].set_yticks(range(4), ['1  Shared-source input\n    equal; state equal', '2  Shared-source input\n    changed; spikes equal',
                               '3  Spikes changed;\n    1-ms bins equal', '4  1-ms bins\n    changed'])
    axes[1].invert_yaxis(); axes[1].set_xlim(0,37)
    for i,v in enumerate(vals): axes[1].text(v+.6,i,str(v),va='center')
    axes[1].set_xlabel('Graph / input comparisons (n = 57)')
    axes[1].set_title('B  Four observed outcomes',loc='left',weight='bold')
    fig.subplots_adjust(wspace=.75, bottom=.15, top=.91, left=.13, right=.98)
    fig.text(.5,.035,'Spike identity across three inputs: 2 always equal; 7 always different; 10 switch.',
             ha='center',fontsize=8)
    finish(fig,'input-switching')

    fig, axes = plt.subplots(1,3,figsize=(6.5,3.5),sharey=True)
    for pi,(ax,probe) in enumerate(zip(axes,PROBES)):
        for gi,group in enumerate(GROUPS):
            rr=[r for r in composition if r['probe']==probe and r['group']==group and r['Dslot']>0]
            yy=np.array([r['count_retained_fraction'] for r in rr])*100
            xx=gi+np.linspace(-.12,.12,len(yy))
            ax.scatter(xx,yy,s=17,color=colors[gi],alpha=.75,zorder=3)
            ax.plot([gi-.19,gi+.19],[np.median(yy)]*2,color='#222222',lw=2,zorder=4)
            ax.text(gi,104,f'n = {len(yy)}',ha='center',fontsize=8)
        ax.set_title(LABELS[pi],weight='bold'); ax.set_xticks([0,1],['One swap','Extensive'])
        ax.set_ylim(-3,113); ax.set_xlim(-.5,1.5); ax.grid(axis='y',alpha=.22)
    axes[0].set_ylabel('Raw-slot error retained in\nper-node 30-ms counts (%)')
    fig.subplots_adjust(bottom=.20,left=.12,right=.99,top=.86,wspace=.12)
    fig.text(.5,.04,'Each point is one nonzero-error comparison; black lines are medians.\n'
             'Time accumulation can cancel differences without establishing small spike shifts.',ha='center',fontsize=8)
    finish(fig,'error-composition')

    fig,axes=plt.subplots(2,3,figsize=(6.5,5.0),sharex='row')
    for pi,probe in enumerate(PROBES):
        for gi,group in enumerate(GROUPS):
            med=[]; low=[]; high=[]
            for width in WIDTHS:
                rows=[r for r in bin_summary if r['probe']==probe and r['group']==group
                      and r['width_slots']==width and r['readout']=='identified']
                med.append(next(r['median'] for r in rows if r['offset_slots']==0)*100)
                low.append(min(r['median'] for r in rows)*100)
                high.append(max(r['median'] for r in rows)*100)
            xx=np.array(WIDTHS)*DT
            axes[0,pi].plot(xx,med,'o-',ms=3,color=colors[gi],label='One swap' if gi==0 else 'Extensive')
            axes[0,pi].fill_between(xx,low,high,color=colors[gi],alpha=.18)
            rr=[next(r for r in smooth_summary if r['probe']==probe and r['group']==group
                     and r['tau_ms']==tau) for tau in TAUS]
            axes[1,pi].plot(TAUS,[r['median'] for r in rr],'o-',ms=3,color=colors[gi])
            axes[1,pi].fill_between(TAUS,[r['minimum'] for r in rr],
                                   [r['maximum'] for r in rr],color=colors[gi],alpha=.14)
        for row in range(2):
            axes[row,pi].set_xscale('log');axes[row,pi].set_xticks([.1,1,5,30],['0.1','1','5','30'])
            axes[row,pi].grid(alpha=.2)
        axes[0,pi].set_title(LABELS[pi],weight='bold')
        axes[0,pi].set_xlabel('Bin width (ms)');axes[1,pi].set_xlabel('Time constant τ (ms)')
    axes[0,0].set_ylabel('Identified count L1 (%)')
    axes[1,0].set_ylabel('Normalized squared\nvan Rossum distance')
    axes[0,0].legend(frameon=False,fontsize=8)
    fig.subplots_adjust(left=.12,right=.99,bottom=.17,top=.93,wspace=.29,hspace=.52)
    fig.text(.5,.025,'Top: medians of all 19 graphs; lines use offset 0, bands span all offset medians.\n'
             'Bottom: medians and full graph ranges; analytic tails included, no bin boundaries.',
             ha='center',fontsize=8)
    finish(fig,'binning-robustness')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensitivity-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(); root=args.sensitivity_dir.resolve(); out=args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Output directory must be empty; preserve earlier completed analysis.')
    out.mkdir(parents=True,exist_ok=True)
    plan=Path(__file__).with_name('analysis-plan.json')
    assert load(plan)['not_preregistered'] is True
    inputs={}; source_hash=digest(Path(__file__)); plan_hash=digest(plan)
    def track(path):
        path=Path(path);inputs[str(path.relative_to(root))]=digest(path);return path
    complete=load(track(root/'run-complete.json'))
    assert len(complete['runs'])==231
    audits={r['graph']:r for r in load(track(root/'graph-audit.json')) if r['type']=='swap'}
    def read(path):
        with np.load(track(path)) as data: a=data['state_bits']
        assert a.shape==(300,125,10) and a.dtype==np.uint32
        assert np.all((a[:,:,0]==0)|(a[:,:,0]==100))
        return a
    originals={probe:read(root/'runs'/f'original__{probe}.npz') for probe in PROBES}
    # Verify the archived broad controls and freshly-calibrated original share
    # every recorded baseline bit, not only a count summary.
    for probe in PROBES:
        old=read(root/'legacy'/'runs'/f'homogeneous__original__{probe}__explicit.npz')
        assert np.array_equal(old,originals[probe])
    controls=[]
    for group in GROUPS:
        for seed in (range(93001,93020) if group=='swap' else range(91001,91020)):
            for probe in PROBES:
                stem=f'swap{seed}__{probe}' if group=='swap' else f'homogeneous__r{seed}__{probe}__explicit'
                path=root/('runs' if group=='swap' else 'legacy/runs')/(stem+'.npz')
                controls.append((dict(group=group,seed=seed,probe=probe,stem=stem),read(path)))
    checks=selfchecks();switching=[];composition=[];binrows=[];smoothrows=[]
    for identity,candidate in controls:
        probe=identity['probe'];reference=originals[probe]
        delta=candidate[:,:,0].astype(np.int64)-reference[:,:,0].astype(np.int64)
        denom=int(reference[:,:,0].sum());assert denom>0
        dslot=int(np.abs(delta).sum());dcount=int(np.abs(delta.sum(axis=0)).sum())
        dglobal=abs(int(delta.sum())); d1ms=nums(binned(delta,10,0))[0]
        assert 0<=dglobal<=dcount<=dslot
        # Explicitly check cancellation as twice the min of positive and
        # negative discrepancies, independently of aggregate subtraction.
        positive=np.maximum(delta,0).sum(axis=0);negative=np.maximum(-delta,0).sum(axis=0)
        temporal=int(2*np.minimum(positive,negative).sum())
        assert temporal==dslot-dcount
        node=delta.sum(axis=0)
        spatial=int(2*min(np.maximum(node,0).sum(),np.maximum(-node,0).sum()))
        assert spatial==dcount-dglobal
        assert temporal+spatial+dglobal==dslot
        composition.append({**identity,'reference_spikes':denom,'Dslot':dslot,'Dcount':dcount,
            'Dglobal':dglobal,'D1ms':d1ms,'Dslot_relative':dslot/denom,'Dcount_relative':dcount/denom,
            'Dglobal_relative':dglobal/denom,'D1ms_relative':d1ms/denom,
            'temporal_cancelled':temporal,'spatial_cancelled_after_time':spatial,
            'count_retained_fraction':dcount/dslot if dslot else None,
            'temporal_cancelled_fraction':temporal/dslot if dslot else None,
            'spatial_cancelled_fraction':spatial/dslot if dslot else None,
            'global_retained_fraction':dglobal/dslot if dslot else None})
        if identity['group']=='swap':
            audit=audits[f'swap{identity["seed"]}'];a,c=int(audit['a']),int(audit['c'])
            src=reference[:298,a,0].astype(np.int64)-reference[:298,c,0].astype(np.int64)
            sameinput=not bool(np.any(src));samestate=bool(np.array_equal(reference,candidate))
            if sameinput:
                assert samestate and dslot==0
                category=CATEGORIES[0]
            elif dslot==0: category=CATEGORIES[1]
            elif d1ms==0: category=CATEGORIES[2]
            else: category=CATEGORIES[3]
            switching.append({**identity,'arm':audit['arm'],'source_a':a,'source_c':c,
                'target_b':audit['b'],'target_d':audit['d'],
                'shared_input_identical':sameinput,'all_recorded_bits_equal':samestate,
                'spikes_identical':dslot==0,'bins_1ms_identical':d1ms==0,
                'spike_mismatch_cells':int(np.count_nonzero(delta)),
                'eligible_source_mismatch_slots':int(np.count_nonzero(src)),
                'category':category})
        prev=None
        for width in WIDTHS:
            for offset in range(width):
                quantities=nums(binned(delta,width,offset))
                assert quantities[2]<=quantities[1]<=quantities[0]<=dslot
                cumulative_nums=nums(delta.sum(axis=0,keepdims=True))
                assert all(a<=b for a,b in zip(cumulative_nums,quantities))
                if offset==0:
                    if prev is not None: assert all(a<=b for a,b in zip(quantities,prev))
                    prev=quantities
                for name,num in zip(READOUTS,quantities):
                    binrows.append({**identity,'width_slots':width,'width_ms':width*DT,
                        'offset_slots':offset,'offset_ms':offset*DT,'readout':name,
                        'l1_numerator':num,'reference_spikes':denom,'relative_l1':num/denom})
        for tau in TAUS:
            distance=vr2(delta/100.,tau); norm=2*distance/(denom/100.)
            assert (distance==0)==(dslot==0)
            smoothrows.append({**identity,'tau_ms':tau,'vr_squared':distance,
                               'reference_representative_spikes':denom//100,
                               'normalized_squared_distance':norm})
    patterns=[]
    for seed in range(93001,93020):
        rows=[next(r for r in switching if r['seed']==seed and r['probe']==p) for p in PROBES]
        exact=sum(r['spikes_identical'] for r in rows)
        patterns.append(dict(seed=seed,tonic_category=rows[0]['category'],
            global_burst_category=rows[1]['category'],focal_burst_category=rows[2]['category'],
            spike_equal_probe_count=exact,pattern='all_equal' if exact==3 else 'all_different' if exact==0 else 'switches'))
    # Re-check reported counts, do not infer or select desired conditions.
    category_counts={c:sum(r['category']==c for r in switching) for c in CATEGORIES}
    pattern_counts={p:sum(r['pattern']==p for r in patterns) for p in ['all_equal','all_different','switches']}
    assert list(category_counts.values())==[4,17,4,32],category_counts
    assert list(pattern_counts.values())==[2,7,10],pattern_counts
    composition_summary=[]
    for probe in PROBES:
        for group in GROUPS:
            rows=[r for r in composition if r['probe']==probe and r['group']==group]
            record=dict(probe=probe,group=group,n=len(rows),nonzero_slot_error=sum(r['Dslot']>0 for r in rows))
            for metric in ['Dslot_relative','Dcount_relative','Dglobal_relative','D1ms_relative',
                           'count_retained_fraction','temporal_cancelled_fraction',
                           'spatial_cancelled_fraction','global_retained_fraction']:
                record.update({metric+'_'+k:v for k,v in describe(r[metric] for r in rows).items()})
            assert record['nonzero_slot_error']==(12 if group=='swap' else 19)
            composition_summary.append(record)
    bins_index={}
    for r in binrows:
        key=(r['probe'],r['group'],r['width_slots'],r['offset_slots'],r['readout'])
        bins_index.setdefault(key,[]).append(r['relative_l1'])
    bin_summary=[dict(probe=k[0],group=k[1],width_slots=k[2],width_ms=k[2]*DT,
                      offset_slots=k[3],readout=k[4],**describe(v)) for k,v in sorted(bins_index.items())]
    separation=[]
    for probe in PROBES:
        for width in WIDTHS:
            for readout in READOUTS:
                margins=[min(bins_index[(probe,'extensive',width,o,readout)])-
                         max(bins_index[(probe,'swap',width,o,readout)]) for o in range(width)]
                across_offsets=(min(v for o in range(width) for v in bins_index[(probe,'extensive',width,o,readout)])-
                                max(v for o in range(width) for v in bins_index[(probe,'swap',width,o,readout)]))
                separation.append(dict(probe=probe,width_slots=width,width_ms=width*DT,readout=readout,
                    offsets=width,strictly_separated_offsets=sum(m>0 for m in margins),
                    minimum_margin=min(margins),maximum_margin=max(margins),
                    cross_offset_envelope_margin=across_offsets))
    smooth_summary=[]
    for probe in PROBES:
        for group in GROUPS:
            for tau in TAUS:
                vals=[r['normalized_squared_distance'] for r in smoothrows if
                      r['probe']==probe and r['group']==group and r['tau_ms']==tau]
                smooth_summary.append(dict(probe=probe,group=group,tau_ms=tau,**describe(vals)))
    smooth_separation=[]
    for probe in PROBES:
        for tau in TAUS:
            ss=[r['normalized_squared_distance'] for r in smoothrows if r['probe']==probe and r['group']=='swap' and r['tau_ms']==tau]
            ee=[r['normalized_squared_distance'] for r in smoothrows if r['probe']==probe and r['group']=='extensive' and r['tau_ms']==tau]
            smooth_separation.append(dict(probe=probe,tau_ms=tau,extensive_minimum=min(ee),
                swap_maximum=max(ss),range_separation=min(ee)-max(ss),strictly_separated=min(ee)>max(ss)))
    for name,rows in [('input-switching',switching),('graph-input-patterns',patterns),
                      ('error-composition',composition),('composition-summary',composition_summary),
                      ('binning-values',binrows),('binning-summary',bin_summary),('binning-separation',separation),
                      ('smooth-values',smoothrows),('smooth-summary',smooth_summary),('smooth-separation',smooth_separation)]:
        table(out/(name+'.csv'),rows)
    save(out/'summary.json',dict(status='pass',analysis_type='post_hoc',new_simulations=0,
        original_graphs=1,swaps=19,extensive_graphs=19,probes=PROBES,
        category_counts=category_counts,input_switching_counts=pattern_counts,
        composition=composition_summary,binning_separation=separation,
        smooth_summary=smooth_summary,smooth_separation=smooth_separation,
        plan_sha256=plan_hash,analyzer_sha256=source_hash))
    plots(out,switching,composition,bin_summary,smooth_summary)
    methods='''POST-HOC INPUT AND READOUT ANALYSIS — METHODS AND RESULTS

Status. This reuses immutable archived explicit trajectories. No simulations or
independent graph samples were added. Known switching and composition findings
were inspected before the plan was fixed; this is not preregistered confirmation.
One homogeneous original (seed 99), 19 legal single swaps and 19 extensive
controls are compared under the same three archived protocols, each for 300
slots of 0.1 ms. The 19 graph identities repeat across protocols.

Input switching. Four categories are applied in order: eligible common-source
input identical and recorded state identical; input changed but raw-slot spikes
identical; raw-slot spikes changed but aligned 1-ms counts identical; 1-ms counts
changed. Eligibility includes source slots 0..297 because source n arrives at
n+2. This does not claim queues beyond the observation horizon are equal.
Category counts are 4,17,4,32. Among the same 19 graphs, 2 are spike-identical
under all three inputs, 7 differ under all three, and 10 switch. Swap 93006 is
an illustrative post-hoc example: categories 1,2,4 under tonic/global/focal,
with 1268 mismatching chunk/slot cells in focal input.

Composition. With signed count difference delta[n,k]=candidate-reference,
Dslot=sum_nk|delta|, Dcount=sum_k|sum_n delta|, Dglobal=|sum_nk delta|.
The exact identity Dslot=(Dslot-Dcount)+(Dcount-Dglobal)+Dglobal first cancels
differences within each identified node across time, then across nodes. The
order matters and is not a unique mechanistic decomposition. The first
difference is twice the sum over nodes of the minimum of positive and negative
temporal discrepancies. This does not identify actual spike correspondences,
short displacements, or a firing-rate/timing causal mechanism. Dcount covers
only 30 ms, not long-term rates. Dcount/Dslot is undefined for zero Dslot;
each input has 12 defined swap and 19 defined extensive ratios. Summaries
are medians of ratios, never ratios of group medians. The median retained
fractions are 4.3449473%,5.9339888%,12.6640249% for swaps and
56.7726737%,58.3643123%,52.5452977% for extensive controls (tonic/global/focal).

Binning. Widths are 1,2,10,50,300 slots. For every width b, offsets o=0..b-1
partition slots by floor((n-o)/b). Both partial edge bins are retained, giving
the same 30-ms observation window and original total-spike denominator for
every offset. At width 300 only o=0 is a single full-window bin; shifted
versions split the window into two partial bins. Identified, E/I-pooled and
globally pooled L1 values are reported. Only origin-aligned widths are nested.
The integer inequalities Dcount <= identified-bin L1 <= Dslot and
global-bin L1 <= E/I-bin L1 <= identified-bin L1 are verified. An independently
implemented scalar binning fixture checks partial bins and mass preservation.
All 1089 common-offset/input/width settings have extensive minimum larger than
swap maximum for identified-count L1. This is not 1089 independent experiments.
At 1 ms the even stronger cross-offset envelope gaps are 6.0225847,
13.1419105 and 50.0 percentage points. Pooled E/I and global readouts mostly
have overlapping group ranges, so separation is not claimed for all readouts.

Smooth robustness. For each identified chunk, count/100 gives its synchronized
representative spike train. For h_tau(t)=H(t) exp(-t/tau), the original van
Rossum squared distance is V_tau^2=(1/tau) integral_0^infinity sum_k
[(h_tau*delta_k)(t)]^2 dt. The normalized score reported is R_tau=2V_tau^2/Nref,
where Nref is original representative-spike count. This is dimensionless,
unbounded, and is not an L1 percentage. Tau=0.1,0.2,1,5,30 ms. The integral
includes the full analytic exponential tail of spikes inside the recorded
window; it assumes no subsequent recorded events and makes no claim about
unobserved future activity. An independent piecewise integral equals the
exponential-kernel quadratic recurrence. Single insertion, shifted spike,
different channels, zero difference and last-slot tail tests pass. Extensive
minimum exceeds swap maximum in all 15 input/tau settings; zero distance
occurs exactly in the 21 spike-identical swap comparisons for every finite tau.
The score need not decrease monotonically with tau: net count differences
and correlations also contribute. No new spike metric is proposed.

Primary source consulted for the smoothing definition and full-tail convention:
M. C. W. van Rossum (2001), A Novel Spike Distance, Neural Computation 13(4),
751–763, doi:10.1162/089976601300014321, equations (2.2)–(2.8).
https://www.pure.ed.ac.uk/ws/portalfiles/portal/7772755/089976601300014321.pdf

Limits. The three input protocols differ in total drive, so switching is an
input-protocol result, not an isolated spatial-locality effect. Structural
budgets differ by about 1100-fold, so separation does not establish a preferred
geometry or error per changed edge. One synchronized, uncalibrated numerical
kernel and one original do not support graph-population inference, generic
robustness, a universal causal mechanism, or long-time equivalence. All
curves and offsets reuse the same data. No p-values or population confidence
intervals are calculated. The same-source input diagnostic is not a predictor
of nonlinear closed-loop error once source trajectories diverge.
'''
    (out/'METHODS-RESULTS.txt').write_text(methods)
    assert all(digest(root/p)==h for p,h in inputs.items()),'Archived input changed'
    assert digest(plan)==plan_hash and digest(Path(__file__))==source_hash
    save(out/'input-sha256.json',dict(sensitivity_inputs=inputs,
        analysis_sources={'analyze.py':source_hash,'analysis-plan.json':plan_hash}))
    save(out/'validation.json',dict(status='pass',analysis_type='post_hoc',new_simulations=0,
        original_bridges_bitwise_equal=3,comparison_count=114,swap_categories_checked=57,
        selfcheck_cases=checks,integer_decompositions_exact=114,
        offset_mass_conservation_checks=114*sum(WIDTHS),nested_origin_binnings_checked=114,
        smooth_kernel_integral_crosschecks=114*len(TAUS),input_files_unchanged=True,
        source_sha256=source_hash,plan_sha256=plan_hash,
        outputs={p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()}))
    print(json.dumps(dict(status='pass',pattern_counts=pattern_counts,category_counts=category_counts,
        smooth_separated=sum(r['strictly_separated'] for r in smooth_separation),
        identified_offsets_separated=sum(r['strictly_separated_offsets'] for r in separation if r['readout']=='identified'),
        identified_offsets_total=sum(r['offsets'] for r in separation if r['readout']=='identified')),indent=2))


if __name__=='__main__':
    main()
