#!/usr/bin/env python3
from pathlib import Path
import csv,os
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR','/tmp/score-factor-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
D=ROOT/'results'
def read(n):return list(csv.DictReader((D/n).open()))
r=read('rank-summary.csv');s=read('separation-strata.csv');c=read('coverage-by-target.csv');d=read('factor-differences-by-target.csv')
probes=['tonic','global_burst','focal_burst'];names=['Tonic','Global burst','Focal burst'];colors=['#2166ac','#dd7b25','#168376']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axs=plt.subplots(2,2,figsize=(12,8.6),layout='constrained')
a=axs[0,0];methods=['original_f0m0','original_f1m0','original_f0m1','original_f1m1'];mat=np.array([[float(next(x for x in r if x['probe']==u and x['method']==m)['macro']) for u in probes] for m in methods]);a.imshow(mat,vmin=.45,vmax=1,cmap='YlGnBu',aspect='auto');a.set_xticks(range(3),names);a.set_yticks(range(4),['Neither','Filter only','Margin only','Filter + margin']);a.set_title('A  Factor ablation on the same resolved pairs',loc='left',fontweight='bold')
for i in range(4):
 for j in range(3):a.text(j,i,f'{mat[i,j]:.3f}',ha='center',va='center',color='white' if mat[i,j]>.8 else 'black',fontweight='bold')
a.set_xlabel('Macro concordance; unresolved pairs excluded')
a=axs[0,1];levels=['1-1.10','1.10-1.25','1.25-1.50','1.50-2','>2']
for u,label,color in zip(probes,names,colors):
 rows=[next(x for x in s if x['probe']==u and x['method']=='original_f1m1' and x['dimension']=='ratio_bin' and x['level']==level) for level in levels];a.plot(range(5),[float(x['macro']) for x in rows],'-o',color=color,label=label)
a.set_xticks(range(5),['(1,1.1]','(1.1,1.25]','(1.25,1.5]','(1.5,2]','>2'],rotation=15);a.set_ylim(.45,1.03);a.axhline(.5,color='gray',linestyle=':',linewidth=1);a.set_ylabel('Macro concordance');a.set_xlabel('Certified lower bound on radius ratio');a.legend(frameon=True,facecolor='white',framealpha=1,loc='lower right');a.set_title('B  Small certified separations are harder',loc='left',fontweight='bold')
a=axs[1,0];bottom=np.zeros(3)
for key,label,color in [('resolved','Resolved','#168376'),('both_capped','Both at cap','#90c4b4'),('proof_gap_overlap','Proof-gap overlap','#e9a85c'),('finite_overlap','Finite overlap','#9eabc0'),('cap_overlap','Other cap overlap','#67517e')]:
 values=np.array([sum(int(x[key]) for x in c if x['probe']==u)/2280*100 for u in probes]);a.bar(range(3),values,bottom=bottom,label=label,color=color)
 if key=='resolved':
  for i,v in enumerate(values):a.text(i,v/2,f'{v:.1f}%',ha='center',color='white',fontweight='bold')
 bottom+=values
a.set_xticks(range(3),names);a.set_ylabel('All 2,280 direction pairs per input (%)');a.set_ylim(0,105);a.legend(frameon=False,fontsize=8,loc='upper left',bbox_to_anchor=(0,-.1),ncol=2);a.set_title('C  Coverage and reasons for non-ordering',loc='left',fontweight='bold')
a=axs[1,1]
for j,(u,color) in enumerate(zip(probes,colors)):
 vals=[float(x['delta'])*100 for x in d if x['probe']==u and x['source']=='original' and x['contrast']=='margin_with_filter'];jitter=np.linspace(-.13,.13,len(vals));a.scatter(j+jitter,vals,color=color,s=25,alpha=.8);a.plot([j-.23,j+.23],[np.mean(vals)]*2,color='black',linewidth=2)
a.axhline(0,color='gray',linewidth=1);a.set_ylim(-22,105);a.set_xticks(range(3),names);a.set_ylabel('Concordance change (percentage points)');a.set_title('D  Adding margin after filtering',loc='left',fontweight='bold');a.text(.02,.98,'Dots: target pairs; bars: means\nDependent comparisons on one graph',transform=a.transAxes,va='top',fontsize=9)
fig.suptitle('Post hoc analysis of existing directions and reference trajectories\nNo new simulation, certification or radius refinement',fontsize=14)
fig.savefig(ROOT/'analysis-summary.png',dpi=180);fig.savefig(ROOT/'analysis-summary.pdf');plt.close(fig)
