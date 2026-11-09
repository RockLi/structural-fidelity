from pathlib import Path
import csv,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;A=R/'analysis';F=R/'figures';F.mkdir(exist_ok=True)
def read(n):return list(csv.DictReader((A/n).open()))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
colors=['#166b95','#bf6a27','#6e5194'];seeds=['100','201','301'];times=['300','1000','3000'];labels=['30','100','300']
sw=read('visibility-switches.csv');mac=read('score-macro.csv');reg=read('region-summary.csv')
fig,axs=plt.subplots(1,3,figsize=(14,4.6));ax=axs[0]
for i,s in enumerate(seeds):
 for mode,style in [('hom','--'),('hetero','-')]:
  z=[next(x for x in sw if x['seed']==s and x['mode']==mode and x['steps']==t and x['contrast']=='G_B/F_H' and x['readout']=='unit') for t in times]
  ax.plot(range(3),[int(x['switches']) for x in z],style,marker='o',color=colors[i],label=f'{s} '+('hetero' if mode=='hetero' else 'hom'))
ax.set(xticks=range(3),xticklabels=labels,xlabel='Observation horizon (ms)',ylabel='Switching swaps / 19',ylim=(-.5,19.5),title='A  Visibility under matched total drive');ax.legend(ncol=2,fontsize=8)
ax=axs[1]
for i,s in enumerate(seeds):
 z=[next(x for x in mac if x['seed']==s and x['mode']=='hetero' and x['steps']==t and x['input']=='F_H') for t in times]
 for k,style,l in [('joint','-','own F_H'),('GB_frozen','--','frozen G_B')]:ax.plot(range(3),[float(x[k]) for x in z],style,marker='o',color=colors[i],label=f'{s} {l}')
ax.axhline(.5,color='gray',lw=.8);ax.set(xticks=range(3),xticklabels=labels,xlabel='Observation horizon (ms)',ylabel='Macro ordering agreement',ylim=(.35,1.03),title='B  Heterogeneous LIF: score transfer');ax.legend(ncol=2,fontsize=8)
ax=axs[2]
import statistics
rr=list(csv.DictReader((R/'directions/radii.csv').open()))
for mode,color,style in [('hom','#505b64','--'),('hetero','#166b95','-')]:
 z=[statistics.median(float(x['lower']) for x in rr if x['mode']==mode and x['steps']==t) for t in times];ax.plot(range(3),z,style,marker='o',color=color,label=mode)
ax.set(xticks=range(3),xticklabels=labels,xlabel='Observation horizon (ms)',ylabel='Median certified relative radius',yscale='log',title='C  Nested-horizon certification');ax.legend()
fig.text(.5,.025,'3 original graphs; 500 units; reference-f64 Atlas. Paired hom/hetero, repeated horizons.\nB uses only disjoint radius brackets (41.7–97.2% coverage across shown heterogeneous F_H cells); C includes zeros and capped bounds.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.11,1,1));fig.savefig(F/'atlas-lif-horizon-summary.png');fig.savefig(F/'atlas-lif-horizon-summary.pdf');plt.close(fig)
# Explicitly show the binary-equality saturation behind zero switch counts.
fig,axs=plt.subplots(2,3,figsize=(11,6.4),sharey=True)
for row,mode in enumerate(['hom','hetero']):
 for col,s in enumerate(seeds):
  ax=axs[row,col];z=[next(x for x in sw if x['seed']==s and x['mode']==mode and x['steps']==t and x['contrast']=='G_B/F_H' and x['readout']=='unit') for t in times];bottom=np.zeros(3)
  for key,color,label in [('both_equal','#58a093','Both equal'),('switches','#e9ad54','Visibility switches'),('both_different','#64748b','Both different')]:
   y=np.array([int(x[key]) for x in z]);ax.bar(range(3),y,bottom=bottom,color=color,label=label);bottom+=y
  ax.set(xticks=range(3),xticklabels=labels,ylim=(0,19.8),title=f'Seed {s} — {mode}',xlabel='Horizon (ms)')
  if col==0:ax.set_ylabel('Swaps / 19')
fig.legend(*axs[0,0].get_legend_handles_labels(),loc='lower center',ncol=3);fig.suptitle('Matched total drive: global versus focal input',fontsize=13);fig.tight_layout(rect=(0,.07,1,.96));fig.savefig(F/'visibility-saturation.png');fig.savefig(F/'visibility-saturation.pdf');plt.close(fig)
