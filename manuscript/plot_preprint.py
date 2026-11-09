"""Rebuild paper figures from explicitly selected result tables."""
from pathlib import Path
import argparse, csv, hashlib, json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir', type=Path, help='Directory containing fresh exact and rounded CSVs; no archived-data fallback')
parser.add_argument('--rounded-csv', type=Path, help='Explicit alternative rounded-metric CSV')
parser.add_argument('--e3-run-dir', type=Path, default=ROOT/'evidence/e3-zero-retention/run')
parser.add_argument('--output-dir', type=Path, default=ROOT/'figures')
parser.add_argument('--metadata-path', type=Path, help='Source-linked figure data JSON, defaults to output directory parent')
args = parser.parse_args()
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
META = (args.metadata_path or OUT.parent/'figure-data.json').resolve()
META.parent.mkdir(parents=True, exist_ok=True)
exact_path = (args.data_dir or ROOT/'evidence/diagnostics')/'diagnostic-results-exact.csv'
rounded_path = args.rounded_csv or ((args.data_dir/'metrics-rounded.csv') if args.data_dir else ROOT/'evidence/original/metrics-rounded.csv')
zero_source = args.e3_run_dir/'results-exact.csv'
for source in [exact_path, rounded_path, zero_source]:
    if not source.is_file(): parser.error(f'Missing requested input: {source}')
exact = list(csv.DictReader(exact_path.open()))
rounded = list(csv.DictReader(rounded_path.open()))
BLUE, ORANGE, GREEN = '#32658D', '#C57538', '#357B59'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,'axes.labelsize':10,
                     'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'savefig.facecolor':'white'})
used = {}
def save(fig, name):
    fig.savefig(OUT/f'{name}.png', dpi=250, bbox_inches='tight', pad_inches=.12)
    fig.savefig(OUT/f'{name}.pdf', bbox_inches='tight', pad_inches=.12)
    plt.close(fig)
def get(variant,label,benchmark=None):
    matches=[r for r in exact if r['variant']==variant and r['label']==label and (benchmark is None or r['benchmark']==benchmark)]
    assert len(matches)==1,(variant,label,len(matches))
    return matches[0]
def vals(rows, key): return [float(r[key]) for r in rows]

# Figure 1: implementation contract, not a biological wiring diagram.
fig, ax = plt.subplots(figsize=(9,4.3)); ax.set_xlim(0,10); ax.set_ylim(0,5); ax.axis('off')
def box(x,y,w,h,s,color='#EDF1F4'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.06,rounding_size=0.05',fc=color,ec='#687580',lw=.8))
    ax.text(x+w/2,y+h/2,s,ha='center',va='center',fontsize=10)
def arrow(x,y,xx,yy): ax.add_patch(FancyArrowPatch((x,y),(xx,yy),arrowstyle='-|>',mutation_scale=12,lw=1,color='#48535B'))
ax.text(.05,4.8,'A   Shared model and two routing rules',weight='bold')
box(.1,2.15,2,1.65,'Source chunks\n100 identical units\nper chunk\nSpike counts Sⱼ')
box(3,3.25,3,1,'Explicit routing\nOne message per edge')
box(3,1.6,3,1,'Raw-sum batching\nSum by target and sign','#EDF5EF')
box(7,2.15,2.8,1.65,'Destination chunk\nBroadcast summed input\nSame unit updates\nand scheduler')
arrow(2.15,3.2,2.94,3.75);arrow(2.15,2.7,2.94,2.1)
arrow(6.07,3.75,6.94,3.2);arrow(6.07,2.1,6.94,2.7)
ax.text(4.5,2.9,'Same adjacency retained',ha='center',fontsize=9,color='#555555')
ax.text(.05,1.15,'B   Delivery slot for a spike generated in slot n',weight='bold')
ax.plot([3,8.9],[.52,.52],color='#687580',lw=1)
for x,label in [(3,'n'),(5.95,'n + 1'),(8.9,'n + 2')]:
    ax.plot([x,x],[.45,.59],color='#687580');ax.text(x,.18,label,ha='center')
ax.text(3,.78,'Generate spike',ha='center',fontsize=9)
ax.text(5.95,.78,'2ch / filtered 4ch',ha='center',fontsize=9,color=ORANGE)
ax.text(8.9,.80,'Explicit / trace /\nraw sum',ha='center',fontsize=8,color=GREEN)
save(fig,'fig1_execution')

# Figure 2: E1 main modes, all with the same reference and workload.
e1_labels=[('original_instrumented','4ch-default','Filtered 4ch'),('original_instrumented','4ch+trace (pure)','Trace, 0% retained'),
 ('original_instrumented','4ch+trace (hybrid)','Trace, 24% retained'),('raw_sum','4ch+trace (pure)','Raw sum, 0% retained'),('raw_sum','4ch+trace (hybrid)','Raw sum, 24% retained')]
rows=[get(v,l,'E1 50k') for v,l,_ in e1_labels];used['fig2']=rows
fig,axes=plt.subplots(1,3,figsize=(9,3.1),sharey=True,gridspec_kw={'wspace':.32})
y=np.arange(len(rows));colors=[ORANGE,BLUE,BLUE,GREEN,GREEN]
for ax,key,title in zip(axes,['psth_r','fr_delta','event_ratio_from_counts'],['A   Activity correlation r','B   Mean-rate error (%)','C   Queue-message ratio Q']):
    ax.barh(y,vals(rows,key),color=colors,height=.57);ax.set_title(title,loc='left');ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
axes[0].set_yticks(y,[x[2] for x in e1_labels]);axes[0].invert_yaxis();axes[0].set_xlim(0,1.07)
axes[0].axvline(.7,color='#777777',ls=':',lw=1)
axes[1].set_xlim(-20,1);axes[1].axvline(0,color='#777777',lw=.7)
axes[2].set_xlim(0,.57)
for ax,key in [(axes[0],'psth_r'),(axes[2],'event_ratio_from_counts')]:
    for yy,r in zip(y,rows): ax.text(float(r[key])+.015,yy,f'{float(r[key]):.3f}',va='center',fontsize=8)
for yy,r in zip(y,rows): axes[1].text(float(r['fr_delta'])-.5,yy,f'{float(r["fr_delta"]):.1f}',va='center',ha='right',fontsize=8)
save(fig,'fig2_e1')

# Figure 3: fixed graph, retained-edge threshold sweep.
legacy=sorted([r for r in rounded if r['section']=='bench_retention_budget_curve_e3_hetero'],key=lambda r:float(r['ret_e']))
st=[get('original_instrumented','stateful_'+r['label'],'E3 heterogeneous') for r in legacy]
raw=[get('raw_sum','stateful_'+r['label'],'E3 heterogeneous') for r in legacy]
zero_rows=[r for r in csv.DictReader(zero_source.open()) if int(r['retained_edges'])==0]
assert len(zero_rows)==3, 'Expected one measured zero-retention point per method'
def zero(variant):
    matches=[r for r in zero_rows if r['variant']==variant]
    assert len(matches)==1,(variant,len(matches))
    row=dict(matches[0])
    row['ret_e']=row['retained_edges_pct']
    row['ev_ratio']=row['event_ratio_from_counts']
    row['source_table']=os.path.relpath(zero_source.resolve(), META.parent)
    return row
legacy=[zero('filtered_4ch')]+legacy
st=[zero('original_instrumented')]+st
raw=[zero('raw_sum')]+raw
used['fig3']={'legacy':legacy,'trace':st,'raw_sum':raw}
x=vals(legacy,'ret_e')
fig,axes=plt.subplots(1,3,figsize=(9,3.2),layout='constrained')
for ax,lk,ek,title in zip(axes,['psth_r','fr_delta','ev_ratio'],['psth_r','fr_delta','event_ratio_from_counts'],['A   Activity correlation r','B   Mean-rate error (%)','C   Queue-message ratio Q']):
    for rr,kk,c,m,name in [(legacy,lk,ORANGE,'s','Filtered 4ch'),(st,ek,BLUE,'o','Trace modulation'),(raw,ek,GREEN,'^','Raw sum')]:
        ax.plot(x,vals(rr,kk),color=c,marker=m,ms=4,lw=1.4,label=name)
    ax.set_title(title,loc='left');ax.set_xlabel('Retained edges (%)');ax.grid(alpha=.18);ax.set_xticks([0,5,10,15,20])
axes[0].set_ylim(min(.42,min(vals(legacy,'psth_r'))-.05),1.035);axes[0].axhline(.7,color='#777777',ls=':',lw=.8)
axes[1].axhspan(-20,20,color='#E9ECEF',alpha=.45,zorder=0)
axes[2].legend(frameon=False,fontsize=8,loc='center right')
save(fig,'fig3_budget')

# Figure 4: operational edge classes; unequal retention budgets remain visible.
policy_labels=['StrongInhibitoryLoop','FastInhibitoryLoop','ShortCycleMotif','StrongInh+FastInh']
display=['I-source\n17.4%','I → I\n3.7%','E → I\n13.1%','Union\n21.1%']
legacy=[next(r for r in rounded if r['section']=='bench_multimotif_taxonomy_e3' and r['label']==p) for p in policy_labels]
st=[get('original_instrumented',p,'E3 heterogeneous') for p in policy_labels]
raw=[get('raw_sum',p,'E3 heterogeneous') for p in policy_labels]
used['fig4']={'legacy':legacy,'trace':st,'raw_sum':raw}
fig,axes=plt.subplots(1,3,figsize=(9,3.4),layout='constrained');x=np.arange(4)
for ax,lk,ek,title in zip(axes,['psth_r','fr_delta','ev_ratio'],['psth_r','fr_delta','event_ratio_from_counts'],['A   Activity correlation r','B   Mean-rate error (%)','C   Queue-message ratio Q']):
    for off,rr,kk,c,name in [(-.23,legacy,lk,ORANGE,'Filtered 4ch'),(0,st,ek,BLUE,'Trace modulation'),(.23,raw,ek,GREEN,'Raw sum')]:
        ax.bar(x+off,vals(rr,kk),width=.21,color=c,label=name)
    ax.set_title(title,loc='left');ax.set_xticks(x,display,fontsize=8);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
axes[0].set_ylim(0,1.07);axes[0].axhline(.7,color='#777777',ls=':',lw=.8)
axes[1].axhspan(-20,20,color='#E9ECEF',alpha=.45,zorder=0);axes[1].axhline(0,color='#777777',lw=.7)
fig.legend(*axes[0].get_legend_handles_labels(),loc='outside lower center',ncol=3,frameon=False,fontsize=9)
save(fig,'fig4_edge_classes')

# Figure 5: distinct gain pairs only; no uncertainty bars because these are not trials.
cal_legacy=[r for r in rounded if r['section'] in ('bench_e1_medium_calibration','bench_e1_parameter_island')]
cal_st=[r for r in rounded if r['section'] in ('stateful_e1_medium_calibration','stateful_e1_parameter_island')]
def distinct(rr):
    d={}
    for r in rr: d[(r['gfe'],r['gfi'])]=r
    assert len(d)==17
    return list(d.values())
cal_legacy,cal_st=distinct(cal_legacy),distinct(cal_st);used['fig5']={'legacy':cal_legacy,'trace':cal_st}
fig,ax=plt.subplots(figsize=(7.2,3.4),layout='constrained')
ax.fill_between([-20,20],.7,1.03,color='#E9ECEF',alpha=.7,label='Descriptive screening region')
ax.scatter(vals(cal_legacy,'fr_delta'),vals(cal_legacy,'psth_r'),c=ORANGE,marker='s',s=35,label='Filtered 4ch: 17 gain pairs',zorder=3)
ax.scatter(vals(cal_st,'fr_delta'),vals(cal_st,'psth_r'),c=BLUE,marker='o',s=35,label='Trace modulation: 17 gain pairs',zorder=3)
ax.axhline(.7,color='#777777',ls=':',lw=1);ax.axvline(-20,color='#777777',ls=':',lw=1);ax.axvline(20,color='#777777',ls=':',lw=1)
ax.set_xlim(-55,23);ax.set_ylim(.2,1.035);ax.set_xlabel('Mean-rate error (%)');ax.set_ylabel('Population activity correlation r');ax.grid(alpha=.15)
ax.legend(frameon=False,loc='lower right',fontsize=9)
save(fig,'fig5_calibration')
used['_provenance'] = {'input_files': {os.path.relpath(path.resolve(), META.parent):
    hashlib.sha256(path.read_bytes()).hexdigest() for path in [exact_path, rounded_path, zero_source]},
    'archived_data_fallback': False}
META.write_text(json.dumps(used,ensure_ascii=False,indent=2)+'\n')
print('Created 5 figures, PNG + vector PDF, and source-linked figure-data.json')
