from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;A=R/'analysis';J=json.loads((A/'summary.json').read_text());seeds=[100,101,102];colors=['#156f8a','#b25337','#6d568c'];inputs=['G_B','F_B','F_H','G_T','F_HT']
fig,ax=plt.subplots(2,2,figsize=(12.6,8.3),layout='constrained')
x=np.arange(5)
for i,s in enumerate(seeds):
 vals=[r['counts'][str(s)] for r in J['visibility']];ax[0,0].bar(x+(i-1)*.24,vals,.23,color=colors[i],label=f'Seed {s}')
ax[0,0].set(xticks=x,xticklabels=['G_B / F_H','G_T / F_HT','G_B / G_T','F_H / F_HT','F_B / F_H'],ylim=(0,19),yticks=[0,5,10,15,19],ylabel='Swaps that change visibility / 19',title='A  Visibility switching on three new graphs');ax[0,0].tick_params(axis='x',labelrotation=20);ax[0,0].legend(frameon=False,ncol=3,fontsize=8)
methods=['random','f1m0','f0m1','mean','shuffle'];x=np.arange(5)
for i,s in enumerate(seeds):
 vals=[r['deltas'][str(s)] for r in J['score_factor_gates']];ax[0,1].plot(x,vals,'o-',color=colors[i],label=f'Seed {s}')
ax[0,1].axhline(0,color='.6',lw=.8);ax[0,1].set(xticks=x,xticklabels=['Random','Filter only','Margin only','Mean','Shuffle'],ylabel='Joint minus control concordance',ylim=(0,.45),title='B  Predeclared equal-input macro differences');ax[0,1].tick_params(axis='x',labelrotation=20)
for i,s in enumerate(seeds):
 vals=[next(r['lower_median']*100 for r in J['coverage'] if r['seed']==s and r['input']==u) for u in inputs];ax[1,0].plot(np.arange(5),vals,'o-',color=colors[i])
ax[1,0].set(xticks=np.arange(5),xticklabels=inputs,ylabel='Median certified lower radius (%)',title='C  Region widths vary with graph and input',ylim=(0,6.5))
labels=['Tolerance','Proof gap','Certified cap','Step limit'];keys=['bracket_tolerance','proof_gap','cap_certified','refinement_limit'];pal=['#73a5b4','#d6a061','#9ba5ad','#943843'];left=np.zeros(3)
for label,key,col in zip(labels,keys,pal):
 vals=np.array([sum(r[key] for r in J['coverage'] if r['seed']==s)/sum(r['n'] for r in J['coverage'] if r['seed']==s)*100 for s in seeds]);ax[1,1].barh(np.arange(3),vals,left=left,color=col,label=label);left+=vals
ax[1,1].set(yticks=np.arange(3),yticklabels=[str(s) for s in seeds],xlabel='All direction / input conditions (%)',ylabel='Original graph seed',title='D  All stopping outcomes retained',xlim=(0,100));ax[1,1].legend(frameon=False,fontsize=8,ncol=2,loc='lower center',bbox_to_anchor=(.5,-.33))
for aa in ax.flat:aa.spines[['top','right']].set_visible(False);aa.grid(axis='y',alpha=.12);aa.set_axisbelow(True)
fig.suptitle('Three prospectively fixed original graphs, one unchanged synchronized kernel',fontsize=14)
fig.savefig(A/'multigraph-summary.png',dpi=160);fig.savefig(A/'multigraph-summary.pdf');plt.close(fig)
