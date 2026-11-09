#!/usr/bin/env python3
"""Manuscript-sized figures from supplied phase/perturbation tables only."""
import argparse, csv, hashlib, json, os
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--perturbation-dir',type=Path,default=ROOT/'evidence/perturbation')
p.add_argument('--output-dir',type=Path,default=ROOT/'conditional-figures')
a=p.parse_args();src=a.perturbation_dir.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(out/'.mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter
def read(name):return list(csv.DictReader((src/name).open()))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
files=['legacy_diagnostics/phase-state-errors.csv','analysis/prediction-data.csv','analysis/prediction-associations.csv','analysis/response-outcomes.csv','analysis/source-subspace-coverage.csv','predictors/training-summary.json']
hashes={name:sha(src/name) for name in files}
phase,pred,assoc,resp,cov=[read(name) for name in files[:5]]
train=json.loads((src/files[5]).read_text())
groups=['A_degree','B_aligned','C_random'];colors=['#C56C2F','#187F8C','#8B5A9F'];markers=['o','s','^']
labels=['A: E/I statistics','B: Aligned groups','C: Random groups']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9,'axes.labelsize':8.5,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,'savefig.dpi':240,'pdf.fonttype':42})
handles=[Line2D([],[],color=c,marker=m,ls='',label=l,markersize=5) for c,m,l in zip(colors,markers,labels)]
data={'input_sha256':hashes,'phase_points':[],'prediction_points':[]}
fig,axes=plt.subplots(1,3,figsize=(6.56,2.8),sharey=True)
fig.subplots_adjust(left=.10,right=.99,top=.83,bottom=.23,wspace=.16)
for ax,window,title in zip(axes,['conditioning','early_recovery','late_recovery'],['A  Conditioning\n0–8 ms','B  Early recovery\n8–15 ms','C  Late recovery\n15–30 ms']):
 for i,(g,c,m) in enumerate(zip(groups,colors,markers)):
  rr=sorted([r for r in phase if r['probe']=='module_burst' and r['treatment']==g and r['phase']==window],key=lambda r:r['graph']);assert len(rr)==5
  values=[float(r['state_score']) for r in rr]
  ax.scatter(i+np.linspace(-.13,.13,5),values,c=c,marker=m,s=21,alpha=.9,zorder=3)
  ax.plot([i-.25,i+.25],[np.median(values)]*2,color=c,lw=2.4)
  data['phase_points'].extend({'graph':r['graph'],'phase':window,'state_score':float(r['state_score'])} for r in rr)
 ax.set_xticks([0,1,2],['A','B','C']);ax.set_xlim(-.5,2.5);ax.set_ylim(0,1.55);ax.set_title(title,loc='left');ax.grid(axis='y',color='#E3E7EA',lw=.5)
axes[0].set_ylabel('Normalized state error')
fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.54,.01),frameon=False,ncol=3,columnspacing=1.1,handletextpad=.3)
for ext in ['png','pdf']:fig.savefig(out/f'phase-preservation.{ext}')
plt.close(fig)

# Native manuscript width; top panels show every graph, bottom panel compares
# training and new-baseline energy coverage. No point selection or test fitting.
fig=plt.figure(figsize=(6.56,5.15));gs=fig.add_gridspec(2,2,height_ratios=[1.05,1],hspace=.63,wspace=.25)
fig.subplots_adjust(left=.10,right=.99,top=.85,bottom=.10)
axes=[fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1])]
for ax,condition,panel in zip(axes,['small','double'],['A','B']):
 for g,c,m in zip(groups,colors,markers):
  rr=[r for r in pred if r['condition']==condition and r['treatment']==g];assert len(rr)==5
  ax.scatter([float(r['activity_rank5']) for r in rr],[float(r['response_fidelity']) for r in rr],c=c,marker=m,s=24,zorder=3)
  data['prediction_points'].extend({'graph':r['graph'],'condition':condition,'activity_rank5':float(r['activity_rank5']),'response_fidelity':float(r['response_fidelity'])} for r in rr)
 r=next(r for r in assoc if r['condition']==condition and r['predictor']=='activity_rank5' and r['subset']=='all15' and r['target']=='response_fidelity')
 z=next(r for r in resp if r['graph']=='original' and r['condition']==condition)
 ax.axhline(float(z['original_response_rms']),color='#596875',ls='--',lw=1)
 ax.set_title(f'{panel}  Amplitude {z["amplitude"]}; ρ = {float(r["spearman"]):.3f}',loc='left')
 ax.set_xlim(.56,.635);ax.set_ylim(0,.6);ax.set_xticks([.56,.58,.60,.62]);ax.set_xlabel('Frozen rank-5 input-map distortion');ax.grid(color='#E3E7EA',lw=.5)
axes[0].set_ylabel('Response error')
ax=fig.add_subplot(gs[1,:])
c=next(r for r in cov if r['condition']=='baseline' and r['window']=='primary_response')
series=[[train['rank5_energy_fraction'],float(c['rank5_energy_fraction'])],[train['secondary_training90_energy_fraction'],float(c['training90_energy_fraction'])]]
for j,(vals,col,rank) in enumerate(zip(series,['#366A94','#AEBAC6'],[5,19])):
 xx=np.arange(2)+(j-.5)*.22;ax.bar(xx,vals,width=.21,color=col,label=f'Rank {rank}')
 for x,y in zip(xx,vals):ax.text(x,y+.025,f'{100*y:.1f}%',ha='center',va='bottom',fontsize=8)
ax.set_ylim(0,1.12);ax.set_xlim(-.6,1.6);ax.set_xticks([0,1],['Old training activity 0–30 ms','New baseline activity 20–100 ms']);ax.set_ylabel('Source energy captured');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_title('C  Coverage of the fixed source-activity bases',loc='left');ax.grid(axis='y',color='#E3E7EA',lw=.5);ax.legend(frameon=False,loc='upper right')
fig.legend(handles=handles+[Line2D([],[],color='#596875',ls='--',label='Zero-response comparator')],loc='upper center',bbox_to_anchor=(.53,.998),frameon=False,ncol=2,columnspacing=1.1,handletextpad=.3)
data['source_coverage']=series
for ext in ['png','pdf']:fig.savefig(out/f'prediction-and-coverage.{ext}')
plt.close(fig)
assert all(sha(src/name)==digest for name,digest in hashes.items())
(out/'figure-data.json').write_text(json.dumps(data,indent=2)+'\n')
print('Rendered two manuscript figures from supplied phase and perturbation outputs:',out)
