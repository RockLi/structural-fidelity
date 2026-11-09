from pathlib import Path
import csv,json,argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,default=R/'analysis');p.add_argument('--output-dir',type=Path,default=R/'manuscript/figures');args=p.parse_args();A=args.analysis;O=args.output_dir;O.mkdir(parents=True,exist_ok=True)
def read(n):return list(csv.DictReader((A/n).open()))
def emit(fig,name):fig.savefig(O/(name+'.png'),dpi=240);fig.savefig(O/(name+'.pdf'));plt.close(fig)
plt.rcParams.update({'font.size':12,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
summary=json.loads((A/'summary.json').read_text());g=read('legacy-ten-graphs.csv');vis=read('legacy-visibility.csv');contrasts=[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]
fig,ax=plt.subplots(1,2,figsize=(9.4,4.2),gridspec_kw={'width_ratios':[1.15,1]});mat=np.array([[int(next(x['switches'] for x in vis if x['seed']==r['seed'] and (x['input_a'],x['input_b'])==c)) for c in contrasts] for r in g]);im=ax[0].imshow(mat,cmap='Blues',vmin=0,vmax=19,aspect='auto');ax[0].set(xticks=range(5),xticklabels=['GB/FH','GT/FHT','GB/GT','FH/FHT','FB/FH'],yticks=range(10),yticklabels=[r['seed'] for r in g],ylabel='Original graph seed',title='A  Visibility switches / 19')
for i in range(10):
 for j in range(5):ax[0].text(j,i,str(mat[i,j]),ha='center',va='center',color='white' if mat[i,j]>10 else 'black',fontsize=11)
x=np.arange(10)
for k,c,mark,label in [('own','#166b95','o','Own F_H reference'),('frozen','#bd6727','s','Frozen G_B score')]:ax[1].plot(x,[float(r[k]) for r in g],marker=mark,color=c,label=label)
ax[1].axhline(.5,lw=.7,c='gray');ax[1].set(xticks=x,xticklabels=[r['seed'] for r in g],ylim=(.35,1),ylabel='Macro agreement on resolved pairs',title='B  Reference-conditioned scores');ax[1].tick_params(axis='x',rotation=50);ax[1].legend(fontsize=10);fig.tight_layout();emit(fig,'fig1_graphs')
v=read('visibility-switches.csv');m=read('score-macro.csv');fig,ax=plt.subplots(1,2,figsize=(9.4,4.4));seeds=['100','201','301'];ts=['300','1000','3000'];x=np.arange(9);sel=[next(r for r in v if r['mode']=='hetero' and r['seed']==s and r['steps']==t and r['contrast']=='G_B/F_H' and r['readout']=='unit') for s in seeds for t in ts];bottom=np.zeros(9)
for key,c,label in [('both_equal','#55a08f','Both equal'),('switches','#e4ac56','Switch'),('both_different','#67758b','Both different')]:
 y=np.array([int(z[key]) for z in sel]);ax[0].bar(x,y,bottom=bottom,color=c,label=label);bottom+=y
ax[0].set(xticks=x,xticklabels=['30','100','300']*3,ylim=(0,23),ylabel='Swaps / 19',xlabel='Horizon (ms)',title='A  Heterogeneous equality labels')
for i,s in enumerate(seeds):ax[0].text(1+3*i,20.4,'Seed '+s,ha='center',fontsize=10)
ax[0].legend(fontsize=10,ncol=3,loc='upper center',bbox_to_anchor=(.5,-.16))
for i,s in enumerate(seeds):
 z=[next(r for r in m if r['mode']=='hetero' and r['seed']==s and r['steps']==t and r['input']=='F_H') for t in ts]
 for k,style,label in [('joint','-','own'),('GB_frozen','--','frozen')]:ax[1].plot([30,100,300],[float(r[k]) for r in z],style,marker='o',c=['#166b95','#bd6727','#725598'][i],label=f'{s} {label}')
ax[1].set(xticks=[30,100,300],ylim=(.4,1.04),xlabel='Horizon (ms)',ylabel='Macro agreement',title='B  F_H ordering and transfer');ax[1].axhline(.5,lw=.7,c='gray');ax[1].legend(fontsize=10,ncol=3,loc='upper center',bbox_to_anchor=(.5,-.16));fig.tight_layout(rect=(0,.03,1,1));emit(fig,'fig2_horizon')
s=read('posthoc-horizon-witnesses.csv');rr=read('posthoc-input-orders.csv');fig,ax=plt.subplots(1,2,figsize=(9.4,4.4));z=[r for r in s if r['mode']=='hetero' and r['short_steps']=='300' and r['long_steps']=='3000'];assert len(z)==720
for flag,c,label in [('True','#166b95','Strict witness (710)'),('False','#bd6727','Not established (10)')]:
 a=[r for r in z if r['strict_shrink']==flag];ax[0].scatter([float(r['short_certified_lower'])*100 for r in a],[float(r['long_failure_upper'])*100 for r in a],s=11,c=c,alpha=.65,label=label)
ax[0].plot([.00005,30],[.00005,30],c='gray',lw=.8);ax[0].set(xscale='log',yscale='log',xlim=(.01,35),ylim=(.00005,35),xlabel='30 ms certified lower (%)',ylabel='300 ms failure upper (%)',title='A  Paired strict range-loss test');ax[0].legend(fontsize=10,loc='upper center',bbox_to_anchor=(.5,-.20))
counts=[]
for seed in seeds:
 a=[r for r in rr if r['mode']=='hetero' and r['steps']=='3000' and r['seed']==seed and r['common_resolved']=='True'];changed=sum(r['different_order']=='True' for r in a);counts.append((len(a)-changed,changed))
ax[1].bar(range(3),[n[0] for n in counts],color='#55a08f',label='Order retained');ax[1].bar(range(3),[n[1] for n in counts],bottom=[n[0] for n in counts],color='#bd6727',label='Order changed')
for i,(same,change) in enumerate(counts):ax[1].text(i,same+change+7,f'{change}/{same+change}',ha='center',fontsize=11)
ax[1].set(xticks=range(3),xticklabels=['Seed '+s for s in seeds],ylim=(0,375),ylabel='Common-resolved direction pairs',title='B  G_B / F_H at 300 ms');ax[1].legend(fontsize=10,loc='upper center',bbox_to_anchor=(.5,-.20));fig.tight_layout();emit(fig,'fig3_bounds')
