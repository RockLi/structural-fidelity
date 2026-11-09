#!/usr/bin/env python3
"""Analysis of fresh graph-by-method runs; no archived result fallback."""
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'analysis/.mpl-cache'))

def save(p,obj): p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def load(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def table(p,rows):
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def divide(a,b): return float(a/b) if b else None
def corr(a,b):
    a=np.asarray(a,dtype=float).ravel(); b=np.asarray(b,dtype=float).ravel()
    da,db=a-a.mean(),b-b.mean(); denom=np.linalg.norm(da)*np.linalg.norm(db)
    return float(da@db/denom) if denom else None
def describe(a):
    a=np.asarray([v for v in a if v is not None],dtype=float)
    return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),minimum=float(a.min()),maximum=float(a.max())) if len(a) else dict(n=0)
def spikes(a): return a[:,:,0].astype(np.int64)
def binned(a): return spikes(a).reshape(30,10,125).sum(axis=1)
def compare(ref,other):
    a,b=spikes(ref),spikes(other); ba,bb=binned(ref),binned(other)
    pa,pb=a.sum(axis=1),b.sum(axis=1); pba,pbb=ba.sum(axis=1),bb.sum(axis=1)
    rf=np.ascontiguousarray(ref[:,:,1:8]).view(np.float32).astype(np.float64)
    of=np.ascontiguousarray(other[:,:,1:8]).view(np.float32).astype(np.float64)
    out=dict(population_spike_mismatch_slots=int(np.count_nonzero(pa!=pb)),
        chunk_spike_mismatch_cells=int(np.count_nonzero(a!=b)),
        population_bin_l1_relative=divide(np.abs(pba-pbb).sum(),pba.sum()),
        chunk_bin_l1_relative=divide(np.abs(ba-bb).sum(),ba.sum()),
        mean_rate_delta_pct=divide(100*(b.sum()-a.sum()),a.sum()),
        post_stimulus_rate_delta_pct=divide(100*(b[80:].sum()-a[80:].sum()),a[80:].sum()),
        population_bin_correlation=corr(pba,pbb),
        chunk_mean_rate_correlation=corr(a.sum(axis=0),b.sum(axis=0)),
        within_chunk_synchrony_note='all 100 units identical at each recorded slot; counted as 125 chunks',
        all_recorded_bits_equal=bool(np.array_equal(ref,other)),
        voltage_max_abs=float(np.abs(rf[:,:,0]-of[:,:,0]).max()),
        exc_conductance_max_abs=float(np.abs(rf[:,:,1]-of[:,:,1]).max()),
        inh_conductance_max_abs=float(np.abs(rf[:,:,2]-of[:,:,2]).max()))
    return out

def main():
    out=ROOT/'analysis'; out.mkdir(exist_ok=True)
    assert not (out/'analysis-complete.json').exists(), 'Preserve completed analysis'
    lock=load(ROOT/'experiment-lock.json')
    assert all(sha(ROOT/k)==v for k,v in lock['files'].items())
    complete=load(ROOT/'run-complete.json'); assert complete['total_runs']==360
    validation=load(ROOT/'validation.json'); assert validation['status']=='pass'
    arrays={}; observations=[]
    for r in complete['runs']:
        prefix=ROOT/'runs'/r['stem']; assert sha(prefix.with_suffix('.npz'))==r['npz_sha256']
        with np.load(prefix.with_suffix('.npz')) as z: a=z['state_bits']
        arrays[(r['family'],r['graph'],r['probe'],r['mode'])]=a
        rows=np.loadtxt(prefix.with_suffix('.csv'),delimiter=',',skiprows=1,dtype=np.int64)
        counts=spikes(a); c=counts.sum(axis=1)
        observations.append(dict(family=r['family'],graph=r['graph'],probe=r['probe'],mode=r['mode'],
            total_spikes=int(c.sum()),mean_rate_hz=float(c.sum()/(12500*.03)),
            exc_mean_rate_hz=float(counts[:,:100].sum()/(10000*.03)),
            inh_mean_rate_hz=float(counts[:,100:].sum()/(2500*.03)),
            first_8ms_rate_hz=float(c[:80].sum()/(12500*.008)),
            last_22ms_rate_hz=float(c[80:].sum()/(12500*.022)),
            last_5ms_spikes=int(c[-50:].sum()),
            last_spike_ms=float((np.flatnonzero(c)[-1]+1)*.1) if np.any(c) else None,
            recurrent_messages=int(rows[:,2].sum()),active_source_edge_visits=int(rows[:,3].sum()),
            active_chunk_steps=int(rows[:,4].sum()),
            instrumented_loop_seconds=load(prefix.with_suffix('.json'))['instrumented_loop_seconds']))
    table(out/'run-metrics.csv',observations)
    by_id={(r['family'],r['graph'],r['probe'],r['mode']):r for r in observations}
    approximations=[]; wiring=[]
    for (family,graph,probe,mode),a in arrays.items():
        if mode!='explicit':
            key=(family,graph,probe,'explicit'); ref=arrays[key]
            row=dict(family=family,graph=graph,probe=probe,mode=mode,**compare(ref,a))
            own=by_id[(family,graph,probe,mode)]; base=by_id[key]
            row['recurrent_message_ratio']=divide(own['recurrent_messages'],base['recurrent_messages'])
            row['active_source_edge_visit_ratio']=divide(own['active_source_edge_visits'],base['active_source_edge_visits'])
            approximations.append(row)
        if graph!='original' and mode=='explicit':
            ref=arrays[(family,'original',probe,'explicit')]
            wiring.append(dict(family=family,graph=graph,probe=probe,**compare(ref,a)))
    table(out/'approximation-errors.csv',approximations); table(out/'wiring-effects.csv',wiring)
    # Error differences are paired to each graph's own explicit trajectory.
    interactions=[]
    for row in approximations:
        if row['graph']=='original': continue
        orig=next(x for x in approximations if x['graph']=='original' and all(x[k]==row[k] for k in ['family','probe','mode']))
        interactions.append(dict(family=row['family'],graph=row['graph'],probe=row['probe'],mode=row['mode'],
            chunk_bin_error_change=row['chunk_bin_l1_relative']-orig['chunk_bin_l1_relative'],
            population_bin_error_change=row['population_bin_l1_relative']-orig['population_bin_l1_relative']))
    table(out/'topology-error-interactions.csv',interactions)
    summary=[]
    for family in ['homogeneous','heterogeneous']:
        for probe in ['tonic','global_burst','focal_burst']:
            group=lambda rows:[x for x in rows if x['family']==family and x['probe']==probe]
            we=group(wiring); ap=group(approximations)
            result=dict(family=family,probe=probe,
                original_explicit=by_id[(family,'original',probe,'explicit')],
                wiring_effect={k:describe([x[k] for x in we]) for k in ['population_bin_l1_relative','chunk_bin_l1_relative',
                    'mean_rate_delta_pct','post_stimulus_rate_delta_pct','chunk_mean_rate_correlation']},proxy={})
            for mode in ['raw_sum','trace']:
                original=next(x for x in ap if x['mode']==mode and x['graph']=='original')
                controls=[x for x in ap if x['mode']==mode and x['graph']!='original']
                result['proxy'][mode]=dict(original=original,
                    rewired={k:describe([x[k] for x in controls]) for k in ['population_bin_l1_relative','chunk_bin_l1_relative',
                        'mean_rate_delta_pct','post_stimulus_rate_delta_pct','recurrent_message_ratio','active_source_edge_visit_ratio']},
                    original_chunk_error_rank_ascending=1+sum(x['chunk_bin_l1_relative']<original['chunk_bin_l1_relative'] for x in controls),
                    rank_is_p_value=False)
            summary.append(result)
    save(out/'summary.json',summary)
    raw=[x for x in approximations if x['mode']=='raw_sum']
    checks=dict(raw_runs=len(raw),raw_population_spike_mismatch_runs=sum(x['population_spike_mismatch_slots']>0 for x in raw),
        raw_chunk_spike_mismatch_runs=sum(x['chunk_spike_mismatch_cells']>0 for x in raw),
        raw_all_recorded_bits_equal_runs=sum(x['all_recorded_bits_equal'] for x in raw),
        raw_voltage_max_abs=max(x['voltage_max_abs'] for x in raw),
        raw_exc_conductance_max_abs=max(x['exc_conductance_max_abs'] for x in raw),
        raw_inh_conductance_max_abs=max(x['inh_conductance_max_abs'] for x in raw))
    save(out/'raw-control-check.json',checks)
    # Independent arithmetic checks using Python integer loops rather than
    # vectorized bin reductions. Recompute every reported error, not a sample.
    rechecked=0
    for rows,is_wiring in [(approximations,False),(wiring,True)]:
        for r in rows:
            a=arrays[(r['family'],'original' if is_wiring else r['graph'],r['probe'],'explicit')][:,:,0].tolist()
            b=arrays[(r['family'],r['graph'],r['probe'],'explicit' if is_wiring else r['mode'])][:,:,0].tolist()
            denom=sum(sum(x) for x in a); cell_l1=0; pop_l1=0
            for start in range(0,300,10):
                aa=[sum(a[t][j] for t in range(start,start+10)) for j in range(125)]
                bb=[sum(b[t][j] for t in range(start,start+10)) for j in range(125)]
                cell_l1+=sum(abs(x-y) for x,y in zip(aa,bb)); pop_l1+=abs(sum(aa)-sum(bb))
            assert abs(cell_l1/denom-r['chunk_bin_l1_relative'])<1e-14
            assert abs(pop_l1/denom-r['population_bin_l1_relative'])<1e-14
            rechecked+=1
    save(out/'metric-audit.json',dict(status='pass',independent_scalar_reductions=rechecked,all_reported_primary_l1_errors_recomputed=True))
    make_plots(summary,approximations,wiring,arrays,out)
    save(out/'analysis-complete.json',dict(status='pass',completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        script_sha256=sha(Path(__file__)),input_run_manifest_sha256=sha(ROOT/'run-complete.json'),
        comparisons=dict(wiring=len(wiring),approximation=len(approximations),interactions=len(interactions)),
        outputs={str(p.relative_to(ROOT)):sha(p) for p in out.iterdir() if p.is_file() and p.name!='analysis-complete.json'}))
    print(json.dumps(checks,indent=2),flush=True)
    for r in summary:
        print(r['family'],r['probe'],'wiring chunk L1',r['wiring_effect']['chunk_bin_l1_relative'],
              'trace original L1',r['proxy']['trace']['original']['chunk_bin_l1_relative'],
              'trace rewired L1',r['proxy']['trace']['rewired']['chunk_bin_l1_relative'],flush=True)

def make_plots(summary,ap,we,arrays,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
    names=['Tonic','Global burst','Focal burst']; probes=['tonic','global_burst','focal_burst']
    fig,axes=plt.subplots(2,3,figsize=(11,6),sharey=True,layout='constrained')
    for row,fam in enumerate(['homogeneous','heterogeneous']):
        for col,probe in enumerate(probes):
            ax=axes[row,col]; d=[x for x in we if x['family']==fam and x['probe']==probe]
            jitter=np.linspace(-.12,.12,len(d))
            for pos,key,color in [(0,'population_bin_l1_relative','#297f99'),(1,'chunk_bin_l1_relative','#d87833')]:
                vals=[100*x[key] for x in d]; ax.scatter(pos+jitter,vals,color=color,s=18,alpha=.8)
                ax.plot([pos-.18,pos+.18],[np.median(vals)]*2,color='black',lw=2)
            ax.set_xticks([0,1],['Population','Chunk']); ax.set_title(names[col] if row==0 else '')
            if col==0: ax.set_ylabel(f'{fam.capitalize()}\nNormalized absolute error (%)')
    fig.suptitle('Effect of rewiring: each explicit control vs original explicit\n1 ms bins; 19 controls per panel; bars mark medians')
    fig.savefig(out/'wiring-effects.png'); fig.savefig(out/'wiring-effects.pdf'); plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(11,6),sharey=True,layout='constrained')
    for row,fam in enumerate(['homogeneous','heterogeneous']):
        for col,probe in enumerate(probes):
            ax=axes[row,col]
            for pos,mode,color in [(0,'raw_sum','#297f99'),(1,'trace','#a54970')]:
                d=[x for x in ap if x['family']==fam and x['probe']==probe and x['mode']==mode]
                ori=next(x for x in d if x['graph']=='original'); controls=[x for x in d if x['graph']!='original']
                ax.scatter(pos+np.linspace(-.12,.12,19),[100*x['chunk_bin_l1_relative'] for x in controls],s=18,color=color,alpha=.7)
                ax.scatter([pos],[100*ori['chunk_bin_l1_relative']],s=65,color='black',marker='D',zorder=3)
            ax.set_xticks([0,1],['Raw sum','Trace']); ax.set_title(names[col] if row==0 else '')
            if col==0: ax.set_ylabel(f'{fam.capitalize()}\nChunk normalized absolute error (%)')
    fig.suptitle('Approximation error against each graph\'s own explicit reference\nColored points: rewired graphs; black diamond: original')
    fig.savefig(out/'proxy-errors.png'); fig.savefig(out/'proxy-errors.pdf'); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4.7),layout='constrained')
    for mode,color,marker in [('raw_sum','#297f99','o'),('trace','#a54970','^')]:
        d=[x for x in ap if x['mode']==mode]
        ax.scatter([x['recurrent_message_ratio'] for x in d],[100*x['chunk_bin_l1_relative'] for x in d],s=22,alpha=.6,color=color,marker=marker,label=mode)
    ax.set_xlabel('Recurrent queue messages / own explicit reference'); ax.set_ylabel('Chunk normalized absolute error (%)')
    ax.set_title('Message counts and fidelity across all fixed conditions\nQueue reduction is not state or graph compression'); ax.legend()
    fig.savefig(out/'messages-and-error.png'); fig.savefig(out/'messages-and-error.pdf'); plt.close(fig)
    # Example graph is the first declared seed, not chosen by outcome.
    fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
    for fam,ax in zip(['homogeneous','heterogeneous'],axes):
        for graph,mode,label,color in [('original','explicit','Original explicit','#222222'),
                ('r91001','explicit','Rewired 91001 explicit','#297f99'),('r91001','trace','Rewired 91001 trace','#a54970')]:
            c=binned(arrays[(fam,graph,'focal_burst',mode)]).sum(axis=1)/12500/.001
            ax.plot(np.arange(30)+.5,c,label=label,color=color)
        ax.axvline(8,color='#999999',ls='--'); ax.set_title(fam.capitalize()); ax.set_ylabel('Population rate (model Hz)')
    axes[-1].set_xlabel('Time (ms)'); axes[0].legend(fontsize=9)
    fig.suptitle('Preselected example: focal burst ends at 8 ms')
    fig.savefig(out/'example-traces.png'); fig.savefig(out/'example-traces.pdf'); plt.close(fig)

if __name__=='__main__': main()
