"""Reporting-only visualization; no new experiment or acceptance rule."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;A=R/'analysis';J=json.loads((A/'summary.json').read_text());seeds=[201,202,203,301,302,303];colors=['#174a6a','#357ea2','#77b4c9','#833d20','#ba6542','#dea57b'];inputs=['G_B','F_B','F_H','G_T','F_HT'];labels=[('Module ' if s<300 else 'Ring ')+str(s) for s in seeds]
fig,ax=plt.subplots(2,2,figsize=(13.5,9.5),layout='constrained');x=np.arange(5)
for i,s in enumerate(seeds):
 vals=[r['counts'][str(s)] for r in J['visibility']];ax[0,0].bar(x+(i-2.5)*.13,vals,.125,color=colors[i],label=labels[i])
ax[0,0].set(xticks=x,xticklabels=['G_B / F_H','G_T / F_HT','G_B / G_T','F_H / F_HT','F_B / F_H'],ylim=(0,19),yticks=[0,5,10,15,19],ylabel='Visibility switches / 19 fixed swaps',title='A  One timing contrast does not replicate in all graphs');ax[0,0].tick_params(axis='x',labelrotation=18);ax[0,0].legend(frameon=False,ncol=2,fontsize=8)
for i,s in enumerate(seeds):
 vals=[r['deltas'][str(s)] for r in J['score_factor_gates']];ax[0,1].plot(x,vals,'o-' if s<300 else 's--',color=colors[i],ms=4)
ax[0,1].axhline(0,color='.5',lw=.8);ax[0,1].set(xticks=x,xticklabels=['Random','Filter only','Margin only','Mean','Shuffle'],ylabel='Joint minus control concordance',title='B  Equal-input graph-level score differences');ax[0,1].tick_params(axis='x',labelrotation=18)
for i,s in enumerate(seeds):
 vals=[next(r['lower_median']*100 for r in J['coverage'] if r['seed']==s and r['input']==u) for u in inputs];ax[1,0].plot(x,vals,'o-' if s<300 else 's--',color=colors[i],ms=4)
ax[1,0].set(xticks=x,xticklabels=inputs,ylabel='Median certified lower radius (%)',title='C  Width is conditional on graph and input',ylim=(0,None))
keys=['bracket_tolerance','proof_gap','cap_certified','cap_unresolved','refinement_limit'];names=['Tolerance','Proof gap','Certified cap','Unresolved cap','Step limit'];pal=['#72a6b7','#d4a15e','#9da7ae','#b55766','#6c4a78'];left=np.zeros(6)
for name,k,col in zip(names,keys,pal):
 vals=np.array([sum(r[k] for r in J['coverage'] if r['seed']==s)/sum(r['n'] for r in J['coverage'] if r['seed']==s)*100 for s in seeds]);ax[1,1].barh(np.arange(6),vals,left=left,color=col,label=name);left+=vals
ax[1,1].set(yticks=np.arange(6),yticklabels=labels,xlabel='All direction / input conditions (%)',title='D  Every stopping outcome retained',xlim=(0,100));ax[1,1].legend(frameon=False,fontsize=8,ncol=2,loc='lower center',bbox_to_anchor=(.5,-.30))
for aa in ax.flat:aa.spines[['top','right']].set_visible(False);aa.set_axisbelow(True);aa.grid(axis='y',alpha=.12)
fig.suptitle('Two new graph-generation laws; the same synchronized numerical kernel',fontsize=14)
fig.savefig(A/'cross-generator-summary.png',dpi=160);fig.savefig(A/'cross-generator-summary.pdf');plt.close(fig)
