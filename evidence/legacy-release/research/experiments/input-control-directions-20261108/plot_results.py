# Post-run presentation only; all scientific contrasts fixed in PROTOCOL.txt.
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
net=load(ROOT/'network-analysis.json');dirs=load(ROOT/'directions/analysis.json');detail=load(ROOT/'directions/detailed-summary.json');order=['G_B','F_H','G_T','F_HT','F_B'];labels=['Global burst','Focal matched','Global rearranged','Focal matched + rearranged','Focal low drive']
fig,ax=plt.subplots(2,2,figsize=(13,9),layout='constrained')
x=np.stack([(events(u).sum(1)) for u in order]);im=ax[0,0].imshow(x,aspect='auto',interpolation='nearest',extent=[0,30,4.5,-.5],cmap='Blues');ax[0,0].set_yticks(range(5),labels);ax[0,0].set_xlabel('Time (ms)');ax[0,0].set_title('A  External amplitude summed across nodes');fig.colorbar(im,ax=ax[0,0],shrink=.75)
metrics=read(ROOT/'network-metrics.csv');mm={(int(r['swap']),r['input']):r for r in metrics};x=np.array([[int(mm[s,u]['spike_equal']=='False') for s in range(93001,93020)] for u in order]);ax[0,1].imshow(x,aspect='auto',cmap=ListedColormap(['#e6e6e6','#b64b3a']),vmin=0,vmax=1);ax[0,1].set_yticks(range(5),labels);ax[0,1].set_xticks(range(19),range(1,20),fontsize=8);ax[0,1].set_xlabel('Fixed minimal-swap ID (93000 + index)');ax[0,1].set_title('B  Spikes: red = differs, grey = identical')
for key,label in [('f0m0','Projection'),('f1m0','Filter only'),('f0m1','Margin only'),('temporal','Filter + margin'),('mean','Mean control'),('shuffle','Shuffle control')]:
 y=[next(r['macro'] for r in detail['rank'] if r['input']==u and r['method']==key) for u in order];ax[1,0].plot(range(5),y,'o-',label=label)
ax[1,0].set_xticks(range(5),order);ax[1,0].set_ylim(.4,1);ax[1,0].set_ylabel('Within-target macro concordance');ax[1,0].set_title('C  Scores conditioned on each input reference');ax[1,0].legend(fontsize=8,ncol=2)
rr=[next(r for r in dirs['reversals'] if r['input_a']==u and r['input_b']==v and r['method']=='temporal') for u,v in [('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]]
y=[r['fraction'] for r in rr];ax[1,1].bar(range(5),y,color=['#457b9d']*2+['#3c8d7a']*2+['#888888']);ax[1,1].set_xticks(range(5),['G_B / F_H','G_T / F_HT','G_B / G_T','F_H / F_HT','F_B / F_H'],rotation=18);ax[1,1].set_ylim(0,.65);ax[1,1].set_ylabel('Order disagreement / jointly resolved pairs');ax[1,1].axhline(.5,c='#777',ls=':',lw=1);ax[1,1].set_title('D  Radius ordering across inputs')
for j,r in enumerate(rr):ax[1,1].text(j,y[j]+.015,f"{r['reversals']}/{r['resolved_both']}",ha='center',fontsize=9)
fig.suptitle('Locked input controls | one 125-chunk graph | 30 ms',fontsize=15);fig.savefig(ROOT/'input-controls.png',dpi=170);fig.savefig(ROOT/'input-controls.pdf');plt.close(fig)
