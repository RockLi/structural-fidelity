"""Analysis only: archived trajectories/bounds, no simulation or radius search."""
from pathlib import Path
import csv,json,itertools,statistics,collections,argparse,hashlib
R=Path(__file__).resolve().parent
S=R/'evidence/studies';OLD=R/'evidence/legacy-release';LIF=S/'atlas-heterogeneous-lif-horizon-20261109'
def read(p):return list(csv.DictReader(p.open()))
def write(p,rows):
 with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def run(out):
 out.mkdir(parents=True,exist_ok=True);graphs=[];vis=[]
 inp=OLD/'research/experiments/input-control-directions-20261108';v=read(inp/'visibility-contrasts.csv');tf=read(inp/'directions/conditioned-vs-frozen.csv');rk=read(inp/'directions/rank-concordance.csv')
 for x in v:vis.append(dict(seed=99,input_a=x['input_a'],input_b=x['input_b'],switches=int(x['same/different'])+int(x['different/same']),total=19))
 z=[x for x in tf if x['probe']=='F_H' and x['method']=='temporal' and x['frozen_G_B']!=''];graphs.append(dict(seed=99,family='Independent',frozen=statistics.mean(float(x['frozen_G_B']) for x in z),own=statistics.mean(float(x['input_conditioned']) for x in z),coverage=sum(int(x['resolved_pairs']) for x in rk if x['probe']=='F_H' and x['method']=='temporal' and x['subgroup']=='all')/(19*120)))
 for study in ['multigraph-input-validation-20261109','cross-generator-validation-20261109']:
  p=S/study;vv=read(p/'analysis/visibility.csv');ff=read(p/'analysis/frozen-scores.csv');rank=read(p/'analysis/rank.csv')
  for x in vv:vis.append({k:(int(x[k]) if k in ['seed','switches','total'] else x[k]) for k in ['seed','input_a','input_b','switches','total']})
  for seed in sorted({int(x['seed']) for x in vv}):
   z=next(x for x in ff if int(x['seed'])==seed and x['probe']=='F_H' and x['method']=='temporal');rr=next(x for x in rank if int(x['seed'])==seed and x['probe']=='F_H' and x['method']=='temporal' and x['subgroup']=='all')
   graphs.append(dict(seed=seed,family='Independent' if seed<200 else 'Module' if seed<300 else 'Ring',frozen=float(z['frozen_G_B']),own=float(z['input_conditioned']),coverage=int(rr['resolved_direction_pairs'])/int(rr['possible_direction_pairs'])))
 graphs.sort(key=lambda x:x['seed']);vis.sort(key=lambda x:(x['seed'],x['input_a'],x['input_b']));write(out/'legacy-ten-graphs.csv',graphs);write(out/'legacy-visibility.csv',vis)
 contrasts=[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]
 table1=[]
 for g in graphs:table1.append([g['seed'],g['family']]+[next(x['switches'] for x in vis if x['seed']==g['seed'] and (x['input_a'],x['input_b'])==c) for c in contrasts])
 # Recalculate nested-horizon and cross-input comparisons directly from raw
 # per-direction radius brackets. These are explicitly post-hoc analyses.
 rr=read(LIF/'directions/radii.csv');idx={(x['seed'],x['mode'],x['input'],x['pair'],int(x['steps']),int(x['direction'])):x for x in rr}
 def order(a,b):
  if b['upper'] and float(a['lower'])>float(b['upper']):return 1
  if a['upper'] and float(b['lower'])>float(a['upper']):return -1
  return 0
 shr=[];rev=[]
 for mode in ['hom','hetero']:
  for short,long in [(300,1000),(1000,3000),(300,3000)]:
   for x in rr:
    if x['mode']!=mode or int(x['steps'])!=short:continue
    y=idx[x['seed'],mode,x['input'],x['pair'],long,int(x['direction'])];proven=bool(y['upper']) and float(y['upper'])<float(x['lower'])
    shr.append(dict(seed=int(x['seed']),mode=mode,input=x['input'],pair=int(x['pair']),direction=int(x['direction']),short_steps=short,long_steps=long,short_certified_lower=float(x['lower']),long_failure_upper=y['upper'],strict_shrink=proven))
  for T in [300,1000,3000]:
   for seed in ['100','201','301']:
    for pair in ['0','9','18']:
     for i,j in itertools.combinations(range(16),2):
      a=order(idx[seed,mode,'G_B',pair,T,i],idx[seed,mode,'G_B',pair,T,j]);b=order(idx[seed,mode,'F_H',pair,T,i],idx[seed,mode,'F_H',pair,T,j])
      rev.append(dict(seed=int(seed),mode=mode,pair=int(pair),steps=T,direction_a=i,direction_b=j,GB_order=a,FH_order=b,common_resolved=bool(a and b),different_order=bool(a and b and a!=b)))
 write(out/'posthoc-horizon-witnesses.csv',shr);write(out/'posthoc-input-orders.csv',rev)
 # Copy incorporated archived tabulations, with source paths and hashes recorded.
 paths=['activity.csv','visibility-switches.csv','score-macro.csv','ranking-coverage.csv','region-summary.csv','GB-selection-transfer.csv','resolved-pair-scores.csv','posthoc-margin-floor-audit.csv']
 provenance=[]
 for n in paths:
  p=LIF/'analysis'/n;data=p.read_bytes();(out/n).write_bytes(data);provenance.append(dict(path=str(p.relative_to(R)),sha256=hashlib.sha256(data).hexdigest()))
 v=read(out/'visibility-switches.csv');m=read(out/'score-macro.csv');t2=[]
 for seed in ['100','201','301']:
  for T in ['300','1000','3000']:
   a=next(x for x in v if x['seed']==seed and x['mode']=='hetero' and x['steps']==T and x['readout']=='unit' and x['contrast']=='G_B/F_H');b=next(x for x in m if x['seed']==seed and x['mode']=='hetero' and x['steps']==T and x['input']=='F_H')
   t2.append([int(seed),int(T)//10,int(a['switches']),f"{float(b['joint']):.3f}",f"{float(b['GB_frozen']):.3f}",f"{100*float(b['coverage']):.1f}",int(b['macro_target_pairs'])])
 t3=[]
 for mode in ['hom','hetero']:
  for T in [300,1000,3000]:
   z=[x for x in rr if x['mode']==mode and int(x['steps'])==T];counts=collections.Counter(x['status'] for x in z)
   t3.append([mode,T//10,sum(float(x['lower'])>0 for x in z),len(z),f"{100*statistics.median(float(x['lower']) for x in z):.5f}",counts['cap'],counts['iteration_limit']])
 shrink_summary=[];reverse_summary=[]
 for mode in ['hom','hetero']:
  for a,b in [(300,1000),(1000,3000),(300,3000)]:
   z=[x for x in shr if x['mode']==mode and x['short_steps']==a and x['long_steps']==b];shrink_summary.append(dict(mode=mode,short=a,long=b,strict=sum(x['strict_shrink'] for x in z),total=len(z)))
  for T in [300,1000,3000]:
   z=[x for x in rev if x['mode']==mode and x['steps']==T];reverse_summary.append(dict(mode=mode,steps=T,common=sum(x['common_resolved'] for x in z),changed=sum(x['different_order'] for x in z),possible=len(z)))
 assert next(x['strict'] for x in shrink_summary if x['mode']=='hetero' and x['short']==300 and x['long']==3000)==710
 assert next((x['changed'],x['common']) for x in reverse_summary if x['mode']=='hetero' and x['steps']==3000)==(394,829)
 summary=dict(status='pass',analysis_only=True,posthoc=['horizon failure upper versus short certified lower','cross-input direction order comparison in LIF'],independent_original_graphs=10,LIF_graphs_are_subset=[100,201,301],legacy_visibility={a+'/'+b:dict(min=min(z:=[x['switches'] for x in vis if (x['input_a'],x['input_b'])==(a,b)]),max=max(z),median=statistics.median(z)) for a,b in contrasts},legacy_frozen_range=[min(x['frozen'] for x in graphs),max(x['frozen'] for x in graphs)],legacy_own_range=[min(x['own'] for x in graphs),max(x['own'] for x in graphs)],shrink=shrink_summary,input_orders=reverse_summary,table1=table1,table2=t2,table3=t3,source_csvs=provenance)
 save(out/'summary.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=R/'analysis');args=p.parse_args();run(args.output_dir)
