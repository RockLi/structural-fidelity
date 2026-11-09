#!/usr/bin/env python3
"""Predetermined analysis for the fixed 48-condition perturbation experiment."""
import os,sys
import numpy as np
from study import ROOT,GRAPHS,CONDITIONS,ARMS,readcsv,load,save,table,sha,check_lock
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'analysis/.mpl-cache'))
sys.dont_write_bytecode=True
COLORS={'A_degree':'#cf7837','B_aligned':'#267e8c','C_random':'#9360a0','original':'#252525'}
WINDOWS={'conditioning':(0,80),'pre_perturbation':(80,200),'pulse':(200,210),'early':(210,300),'middle':(300,500),'late':(500,1000),'terminal':(900,1000),'primary_response':(200,1000)}
PREDICTORS=['activity_rank5','activity_training90','training_replay_distortion','weight_frobenius_distortion','reciprocal_pair_change','directed_triangle_change','source_subspace_distance','singular_value_distance','old_module_state_error']
def state(a):return np.ascontiguousarray(a[:,:,1:4]).view(np.float32).astype(float)
def rms(x):return float(np.sqrt(np.mean(x*x)))
def desc(a):
 a=np.asarray(a,dtype=float);return dict(n=len(a),median=float(np.median(a)),min=float(np.min(a)),max=float(np.max(a)))
def ranks(x):
 x=np.asarray(x);return np.array([np.sum(x<t)+(np.sum(x==t)-1)/2 for t in x],dtype=float)
def spearman(x,y):
 x=np.array(x,dtype=float);y=np.array(y,dtype=float)
 if np.ptp(x)<=1e-12*max(1,float(np.max(np.abs(x)))) or np.ptp(y)<=1e-12*max(1,float(np.max(np.abs(y)))):return None
 return float(np.corrcoef(ranks(x),ranks(y))[0,1])
def recovery(q):
 q=q[200:];j=int(np.argmax(q));peak=float(q[j]);end=float(np.sqrt(np.mean(q[-100:]**2)))
 if peak<=1e-12:return dict(response_peak=peak,peak_time_ms=None,response_auc=float(q.sum()*.1),terminal_response_rms=end,terminal_to_peak=None,recovered=False,recovery_time_from_pulse_end_ms=None,recovery_class='zero_response')
 envelope=np.maximum.accumulate(q[::-1])[::-1];idx=[i for i in range(max(j,10),len(q)-49) if envelope[i]<=.05*peak]
 first=idx[0] if idx else None
 return dict(response_peak=peak,peak_time_ms=float((200+j+1)*.1),response_auc=float(q.sum()*.1),terminal_response_rms=end,terminal_to_peak=end/peak,recovered=first is not None,recovery_time_from_pulse_end_ms=float((200+first+1)*.1-21) if first is not None else None,recovery_class='window_recovered' if first is not None else 'right_censored')

def main():
 check_lock();assert load(ROOT/'validation.json')['status']=='pass';out=ROOT/'analysis';assert not (out/'analysis-complete.json').exists()
 with np.load(ROOT/'predictors/training-basis.npz') as z:scale=z['state_scale'];U5=z['U5'];U90=z['U90']
 pred={r['graph']:{k:(float(v) if k not in ['graph','treatment'] else v) for k,v in r.items()} for r in readcsv(ROOT/'predictors/frozen-predictors.csv')}
 arrays={};states={}
 for name in GRAPHS:
  for cond in CONDITIONS:
   p=ROOT/'runs'/f'{name}__{cond}.npz'
   with np.load(p) as z:a=z['state_bits']
   arrays[name,cond]=a;states[name,cond]=state(a)
 original_base=states['original','baseline'];response0={c:(states['original',c]-original_base)/scale for c in ['small','double']}
 outcomes=[];phase=[];health=[];curve_rows=[];curves={};linearity=[];baseline_rows=[];coverage=[]
 for name in GRAPHS:
  treatment='original' if name=='original' else name.rsplit('_',1)[0];base=states[name,'baseline'];bb=arrays[name,'baseline'];delta_base=(base-original_base)/scale
  baseline_rows.append(dict(graph=name,treatment=treatment,baseline_state_error=rms(delta_base),baseline_response_window_error=rms(delta_base[200:]),baseline_terminal_error=rms(delta_base[900:])))
  for cond,amp in CONDITIONS.items():
   a=arrays[name,cond];x=states[name,cond];r=(x-base)/scale;f=r-response0[cond] if cond!='baseline' else delta_base
   q=np.sqrt(np.mean(r*r,axis=(1,2)));fq=np.sqrt(np.mean(f*f,axis=(1,2)));curves[name,cond]=(q,fq)
   for label,(lo,hi) in WINDOWS.items():
    xx=x[lo:hi];g=a[lo:hi];rr=r[lo:hi];ff=f[lo:hi]
    phase.append(dict(graph=name,treatment=treatment,condition=cond,window=label,start_slot=lo,end_slot_exclusive=hi,response_rms=rms(rr),fidelity_rms=rms(ff),reference_kind='baseline_trajectory' if cond=='baseline' else 'perturbation_response',voltage_min=float(xx[:,:,0].min()),voltage_max=float(xx[:,:,0].max()),voltage_p01=float(np.quantile(xx[:,:,0],.01)),voltage_median=float(np.median(xx[:,:,0])),voltage_p99=float(np.quantile(xx[:,:,0],.99)),gE_max=float(xx[:,:,1].max()),gI_max=float(xx[:,:,2].max()),EI_imbalance_rms=rms(xx[:,:,1]-xx[:,:,2]),actually_stepped_fraction=float(g[:,:,11].mean()),refractory_gate_fraction=float(g[:,:,12].mean()),post_status_dormant_fraction=float(np.mean(g[:,:,9]==0)),spikes=int(g[:,:,0].sum())))
   health.append(dict(graph=name,condition=cond,voltage_min=float(x[:,:,0].min()),voltage_max=float(x[:,:,0].max()),voltage_below_minus100_fraction=float(np.mean(x[:,:,0]<-100)),gE_max=float(x[:,:,1].max()),gI_max=float(x[:,:,2].max()),finite=True,refractory_fraction=float(a[:,:,12].mean()),stepped_fraction=float(a[:,:,11].mean()),terminal_stepped_chunks=int(a[-1,:,11].sum()),terminal_spikes=int(a[-1,:,0].sum()),pulse_target_gate_fraction=float(a[200:210,40:60,12].mean()),pulse_target_stepped_fraction=float(a[200:210,40:60,11].mean())))
   if cond!='baseline':
    refnorm=rms(response0[cond][200:]);y=rms(f[200:]);spike_response=a[:,:,0].astype(float)-bb[:,:,0].astype(float);ospike=arrays['original',cond][:,:,0].astype(float)-arrays['original','baseline'][:,:,0].astype(float);different=np.flatnonzero(np.any(spike_response!=0,axis=1))
    outcomes.append(dict(graph=name,treatment=treatment,condition=cond,amplitude=amp,response_fidelity=y,relative_response_fidelity=y/refnorm if refnorm>1e-12 else None,own_response_rms=rms(r[200:]),original_response_rms=refnorm,response_per_amplitude=rms(r[200:])/amp,spike_response_error_rms=rms(spike_response[200:]-ospike[200:]),own_spike_response_nonzero_cells=int(np.count_nonzero(spike_response[200:])),first_spike_response_ms=float((different[0]+1)*.1) if len(different) else None,pulse_target_gate_fraction=float(a[200:210,40:60,12].mean()),**recovery(q)))
   for lo in range(0,1000,10):
    curve_rows.append(dict(graph=name,condition=cond,time_start_ms=lo*.1,time_end_ms=(lo+10)*.1,response_rms=float(np.sqrt(np.mean(q[lo:lo+10]**2))),fidelity_rms=float(np.sqrt(np.mean(fq[lo:lo+10]**2))),spikes=int(a[lo:lo+10,:,0].sum()),stepped_fraction=float(a[lo:lo+10,:,11].mean()),refractory_fraction=float(a[lo:lo+10,:,12].mean())))
  r1=(states[name,'small']-base)/scale;r2=(states[name,'double']-base)/scale;den=np.linalg.norm(2*r1[200:])
  linearity.append(dict(graph=name,treatment=treatment,double_vs_twice_small_relative=float(np.linalg.norm(r2[200:]-2*r1[200:])/den) if den>1e-12 else None,small_response_rms=rms(r1[200:]),double_response_rms=rms(r2[200:]),ratio_double_to_small=rms(r2[200:])/rms(r1[200:]) if rms(r1[200:])>1e-12 else None))
 for c in CONDITIONS:
  S=arrays['original',c][:,:,0].astype(float).T
  for w,(lo,hi) in WINDOWS.items():
   s=S[:,lo:hi];energy=float(np.sum(s*s))
   coverage.append(dict(condition=c,window=w,spike_energy=energy,rank5_energy_fraction=float(np.sum((U5.T@s)**2)/energy) if energy else None,training90_energy_fraction=float(np.sum((U90.T@s)**2)/energy) if energy else None))
 table(out/'response-outcomes.csv',outcomes);table(out/'phase-diagnostics.csv',phase);table(out/'model-health.csv',health);table(out/'curves-1ms.csv',curve_rows);table(out/'amplitude-linearity.csv',linearity);table(out/'baseline-errors.csv',baseline_rows);table(out/'source-subspace-coverage.csv',coverage)
 associations=[];joined=[]
 for cond in ['small','double']:
  rr=[r for r in outcomes if r['condition']==cond and r['graph']!='original']
  for r in rr:joined.append({**pred[r['graph']],**{k:r[k] for k in ['condition','amplitude','response_fidelity','relative_response_fidelity','own_response_rms','response_auc','terminal_to_peak','recovery_class']}})
  for feat in PREDICTORS:
   for subset in ['all15']+ARMS+['without_'+a for a in ARMS]:
    chosen=[r for r in rr if subset=='all15' or r['treatment']==subset or (subset.startswith('without_') and r['treatment']!=subset[8:])]
    x=[pred[r['graph']][feat] for r in chosen]
    for target in ['response_fidelity','own_response_rms','response_auc']:
     y=[r[target] for r in chosen];associations.append(dict(condition=cond,predictor=feat,target=target,subset=subset,n=len(chosen),spearman=spearman(x,y),expected_direction='positive for response_fidelity; other targets descriptive',inferential_p_value='not computed'))
 # Predict new unperturbed trajectory separately; does not replace primary response outcome.
 for feat in PREDICTORS:
  rr=baseline_rows[1:];associations.append(dict(condition='baseline',predictor=feat,target='baseline_state_error',subset='all15',n=15,spearman=spearman([pred[r['graph']][feat] for r in rr],[r['baseline_state_error'] for r in rr]),expected_direction='positive',inferential_p_value='not computed'))
 table(out/'prediction-associations.csv',associations);table(out/'prediction-data.csv',joined)
 # Independently recompute all primary fidelity scores by chunk.
 for row in outcomes:
  n,c=row['graph'],row['condition'];d=(states[n,c]-states[n,'baseline']-(states['original',c]-original_base))/scale
  score=np.sqrt(sum(float(np.sum(d[200:,j,:]**2)) for j in range(125))/(800*125*3));assert abs(score-row['response_fidelity'])<1e-11
 summary=dict(status='pass',conditions=48,graph_count=16,rank5_primary=True,training=load(ROOT/'predictors/training-summary.json'),
  original_outcomes=[r for r in outcomes if r['graph']=='original'],
  responses={c:{a:{k:desc([r[k] for r in outcomes if r['condition']==c and r['treatment']==a]) for k in ['response_fidelity','own_response_rms','response_peak','response_auc']} for a in ARMS} for c in ['small','double']},
  recovery_counts={c:{a:sum(r['recovered'] for r in outcomes if r['condition']==c and r['treatment']==a) for a in ['original']+ARMS} for c in ['small','double']},
  primary_correlations=[r for r in associations if r['predictor']=='activity_rank5' and r['target']=='response_fidelity'],
  comparison_correlations=[r for r in associations if r['target']=='response_fidelity' and r['subset']=='all15'],
  voltage_min_all=min(r['voltage_min'] for r in health),refractory_fraction=desc([r['refractory_fraction'] for r in health]),
  source_coverage=[r for r in coverage if r['window']=='primary_response'],
  zero_spike_responses=sum(r['own_spike_response_nonzero_cells']==0 for r in outcomes),
  limits=['One original network,15 conditional surrogates; no population inference','New stimulus on existing graphs, not unseen networks','Fixed source basis, no test fitting','State coordinates are placeholder model quantities','Finite100ms response/recovery only','Eigen/singular structure is not a hybrid-system Jacobian','Different amplitudes and windows are not independent samples'])
 save(out/'summary.json',summary);plots(outcomes,associations,pred,curve_rows,health,coverage,out)
 save(out/'analysis-complete.json',dict(status='pass',primary_fidelity_independently_recomputed=32,source_lock_unchanged=True,outputs={str(p.relative_to(ROOT)):sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='analysis-complete.json'}))
 print('ANALYZED:48 conditions;32 response comparisons;fixed prediction tests.',flush=True)
 print('Original outcomes:',summary['original_outcomes'],flush=True)
 print('All15 correlations:',summary['comparison_correlations'],flush=True)

def plots(outcomes,assoc,pred,curves,health,coverage,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':160})
 fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
 for ax,c in zip(axes,['small','double']):
  for i,a in enumerate(ARMS):
   rr=[r for r in outcomes if r['condition']==c and r['treatment']==a];vals=[r['response_fidelity'] for r in rr];ax.scatter(i+np.linspace(-.12,.12,5),vals,c=COLORS[a],s=35);ax.plot([i-.18,i+.18],[np.median(vals)]*2,c='black',lw=2)
  ax.set_xticks(range(3),['E/I only','Aligned','Random']);ax.set_title(f'Pulse amplitude {CONDITIONS[c]:g}');ax.set_ylabel('Response fidelity error (lower is better)')
 fig.suptitle('Each graph\'s response to its own baseline, compared with original response');fig.savefig(out/'response-fidelity.png');fig.savefig(out/'response-fidelity.pdf');plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
 for ax,c in zip(axes,['small','double']):
  rr=[r for r in outcomes if r['condition']==c and r['graph']!='original']
  for r in rr:
   name=r['graph'];ax.scatter(pred[name]['activity_rank5'],r['response_fidelity'],c=COLORS[r['treatment']],s=35);ax.annotate(name[0]+name[-2:],(pred[name]['activity_rank5'],r['response_fidelity']),xytext=(3,3),textcoords='offset points',fontsize=7)
  rho=next(r['spearman'] for r in assoc if r['condition']==c and r['predictor']=='activity_rank5' and r['target']=='response_fidelity' and r['subset']=='all15');ax.set_title(f'Amplitude {CONDITIONS[c]:g}; Spearman = {rho:.3f}' if rho is not None else f'Amplitude {CONDITIONS[c]:g}; constant outcome');ax.set_xlabel('Frozen activity-aware wiring distortion (rank 5)');ax.set_ylabel('Response fidelity error')
 fig.suptitle('Prespecified prediction on new stimulus; 15 graphs; no test refitting');fig.savefig(out/'prediction-rank5.png');fig.savefig(out/'prediction-rank5.pdf');plt.close(fig)
 fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained',sharex=True)
 for col,c in enumerate(['small','double']):
  for name in GRAPHS:
   rr=[r for r in curves if r['graph']==name and r['condition']==c];x=[r['time_end_ms'] for r in rr];color=COLORS['original' if name=='original' else name.rsplit('_',1)[0]];lw=2 if name=='original' else .7;alpha=1 if name=='original' else .45
   axes[0,col].plot(x,[r['response_rms'] for r in rr],color=color,lw=lw,alpha=alpha)
   if name!='original':axes[1,col].plot(x,[r['fidelity_rms'] for r in rr],color=color,lw=lw,alpha=alpha)
  axes[0,col].set_title(f'Amplitude {CONDITIONS[c]:g}')
  for ax in axes[:,col]:ax.axvspan(20,21,color='#ddd',alpha=.5);ax.set_xlim(18,100);ax.set_xlabel('Time (ms)')
 axes[0,0].set_ylabel('Own-baseline response RMS');axes[1,0].set_ylabel('Original-response fidelity error');fig.suptitle('Finite-horizon response and recovery; black = original, colored = controls')
 fig.savefig(out/'response-recovery-curves.png');fig.savefig(out/'response-recovery-curves.pdf');plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
 for ax,c in zip(axes,['small','double']):
  for r in outcomes:
   if r['condition']==c:ax.scatter(r['own_response_rms'],r['response_fidelity'],c=COLORS[r['treatment']],marker='D' if r['graph']=='original' else 'o',s=45)
  ax.set_xlabel('Own-baseline response magnitude');ax.set_ylabel('Original-response fidelity error');ax.set_title(f'Amplitude {CONDITIONS[c]:g}')
 fig.suptitle('Weak response does not by itself mean good fidelity');fig.savefig(out/'sensitivity-versus-fidelity.png');fig.savefig(out/'sensitivity-versus-fidelity.pdf');plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
 for a in ARMS:
  rr=[r for r in health if r['condition']=='baseline' and r['graph'].startswith(a)];axes[0].scatter([r['refractory_fraction'] for r in rr],[r['voltage_min'] for r in rr],c=COLORS[a],label=a)
 axes[0].set_xlabel('Correct pre-update refractory fraction');axes[0].set_ylabel('Minimum V (model coordinate)');axes[0].legend(fontsize=8)
 rr=[r for r in coverage if r['condition']=='baseline' and r['window'] in ['conditioning','pre_perturbation','early','middle','late']];pos=np.arange(len(rr));axes[1].bar(pos-.17,[r['rank5_energy_fraction'] or 0 for r in rr],.34,label='rank 5');axes[1].bar(pos+.17,[r['training90_energy_fraction'] or 0 for r in rr],.34,label='training 90% basis');axes[1].set_xticks(pos,[r['window'] for r in rr],rotation=25,ha='right');axes[1].set_ylabel('New original source energy captured');axes[1].set_ylim(0,1);axes[1].legend()
 fig.suptitle('Model-scale audit and out-of-sample activity coverage');fig.savefig(out/'model-scale-and-coverage.png');fig.savefig(out/'model-scale-and-coverage.pdf');plt.close(fig)

if __name__=='__main__':main()
