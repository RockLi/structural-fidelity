#!/usr/bin/env python3
from pathlib import Path
import csv,json,itertools
import numpy as np
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/paired-mechanism-mpl")
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;D=ROOT/'results';r=json.loads((D/'analysis.json').read_text());raw=list(csv.DictReader((D/'radii.csv').open()));scores=list(csv.DictReader((D/'scores.csv').open()));pool=json.loads((D/'pool-lock.json').read_text());mp={(int(x['pair']),x['probe'],int(x['direction'])):x for x in raw}
def order(a,b):
 if b['upper'] and float(a['lower'])>float(b['upper']):return 1
 if a['upper'] and float(b['lower'])>float(a['upper']):return -1
 return 0
examples=[]
for ua,ub in [('tonic','global_burst'),('tonic','focal_burst')]:
 found=False
 for fam in pool:
  if found:break
  for i,j in itertools.combinations(range(len(fam['directions'])),2):
   a,b=order(mp[fam['pair'],ua,i],mp[fam['pair'],ua,j]),order(mp[fam['pair'],ub,i],mp[fam['pair'],ub,j])
   if a and b and a!=b:
    examples.append(dict(pair=fam['pair'],targets=fam['targets'],inputs=[ua,ub],directions=[i,j],records=[mp[fam['pair'],u,di] for u in [ua,ub] for di in [i,j]],selection='first lexicographic resolved reversal, not largest effect or predictor success'));found=True;break
(ROOT/'reversal-examples.json').write_text(json.dumps(examples,indent=2)+'\n')
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,3,figsize=(15,4.7),gridspec_kw={'width_ratios':[1.15,1,1]})
probes=['tonic','global_burst','focal_burst'];labels=['Tonic','Global burst','Focal burst'];colors={'temporal':'#007f80','mean':'#d78b28','shuffle':'#8a6ca8'}
for j,m in enumerate(['mean','shuffle','temporal']):
 vals=[next(x['macro_concordance'] for x in r['rank'] if x['probe']==u and x['subgroup']=='all' and x['method']==m) for u in probes]
 axes[0].bar(np.arange(3)+(j-1)*.24,vals,.23,label={'mean':'Mean activity','shuffle':'Time shuffled','temporal':'Temporal + margin'}[m],color=colors[m])
axes[0].axhline(.5,color='#777777',ls=':',lw=1);axes[0].set(xticks=range(3),xticklabels=labels,ylim=(0,1),ylabel='Within-pair ordering concordance',title='A  Reference-informed direction ranking');axes[0].legend(frameon=True,framealpha=.95,edgecolor='white',fontsize=8,loc='lower left')
for j,(kind,lab,col) in enumerate([('frozen_tonic','Frozen tonic score','#999999'),('input_conditioned','Current-input reference','#007f80')]):
 vals=[next(x[kind] for x in r['conditioned_vs_frozen'] if x['probe']==u and x['method']=='temporal') for u in probes[1:]]
 axes[1].bar(np.arange(2)+(j-.5)*.32,vals,.30,label=lab,color=col)
axes[1].axhline(.5,color='#777777',ls=':',lw=1);axes[1].set(xticks=range(2),xticklabels=labels[1:],ylim=(0,1),ylabel='Ordering concordance',title='B  Input awareness matters');axes[1].legend(frameon=True,framealpha=.95,edgecolor='white',fontsize=8,loc='lower left')
ex=examples[0];colors2=['#007f80','#c05c43']
for ui,u in enumerate(ex['inputs']):
 for di,direction in enumerate(ex['directions']):
  row=mp[ex['pair'],u,direction];lo=float(row['lower'])*100;hi=float(row['upper'])*100 if row['upper'] else 25.;y=ui+(di-.5)*.2
  axes[2].plot([lo,hi],[y,y],color=colors2[di],lw=3);axes[2].plot(lo,y,'o',color=colors2[di],label=f'Direction {direction}' if ui==0 else None)
  axes[2].plot(hi,y,'x' if row['upper'] else '>',color=colors2[di])
axes[2].set(yticks=[0,1],yticklabels=['Tonic','Global burst'],xlabel='Relative weight radius (%)',title=f'C  Same-budget reversal: targets {ex["targets"]}');axes[2].legend(frameon=False,fontsize=8)
fig.text(.02,.025,'A/B: descriptive macro averages over target pairs with resolvable orders; one graph, not independent network samples.\nC: circles = certified lower bounds; crosses = failed-witness upper bounds; arrows = study cap. These are not confidence intervals.',fontsize=8,color='#444444')
fig.tight_layout(rect=[0,.12,1,1]);fig.savefig(ROOT/'mechanism-summary.png',dpi=180);plt.close(fig)
