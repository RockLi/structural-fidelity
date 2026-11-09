"""Publication figure from completed controlled-input CSVs; no simulation."""
import argparse,csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
R=Path(__file__).resolve().parent
q=argparse.ArgumentParser();q.add_argument('--data-dir',type=Path,default=R.parent/'research/experiments/input-control-directions-20261108');q.add_argument('--output-dir',type=Path,default=R/'figures');a=q.parse_args();a.output_dir.mkdir(exist_ok=True,parents=True)
def read(p):return list(csv.DictReader(p.open()))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,'axes.labelsize':9})
fig,axs=plt.subplots(2,1,figsize=(6.5,5.1),layout='constrained');order=['G_B','F_H','G_T','F_HT','F_B'];m={(int(x['swap']),x['input']):x for x in read(a.data_dir/'network-metrics.csv')};mat=np.array([[int(m[s,u]['spike_equal']=='False') for s in range(93001,93020)] for u in order])
axs[0].imshow(mat,aspect='auto',interpolation='nearest',cmap=ListedColormap(['#eeeeee','#b74c3c']),vmin=0,vmax=1);axs[0].set_yticks(range(5),order);axs[0].set_xticks(range(19),range(1,20),fontsize=8);axs[0].set_xlabel('Fixed swap ID (93000 + index)');axs[0].set_title('A  Spike counts: red = different, grey = identical',loc='left')
r=json.loads((a.data_dir/'directions/analysis.json').read_text())['reversals'];pairs=[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')];rr=[next(x for x in r if x['input_a']==u and x['input_b']==v and x['method']=='temporal') for u,v in pairs];yy=[x['fraction'] for x in rr]
axs[1].bar(range(5),yy,color=['#457b9d','#457b9d','#3d8b77','#3d8b77','#888888'],width=.65);axs[1].set_xticks(range(5),[u+' / '+v for u,v in pairs],fontsize=8);axs[1].set_ylim(0,.65);axs[1].axhline(.5,color='#777777',ls=':',lw=1);axs[1].set_ylabel('Opposite-order fraction');axs[1].set_title('B  Only direction pairs resolved in both inputs',loc='left')
for i,x in enumerate(rr):axs[1].text(i,yy[i]+.015,f"{x['reversals']}/{x['resolved_both']}",ha='center',fontsize=8)
fig.savefig(a.output_dir/'input-controls-paper.png',dpi=300);fig.savefig(a.output_dir/'input-controls-paper.pdf');plt.close(fig)
