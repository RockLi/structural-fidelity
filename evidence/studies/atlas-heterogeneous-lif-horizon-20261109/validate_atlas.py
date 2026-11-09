from analysis_common import *
import concurrent.futures

def work(job):
 seed,mode,u=job;ref=reference(seed,mode,u);fam=load(R/f'seed{seed}/pool-selected.json')[0];data,ids,neur=fast_stream(seed,mode,u,ref,fam['targets'],fam);sg=replay.signs(fam,0,ids);base=load(R/'models'/f'seed{seed}_{mode}_{u}/model.json')
 folder=R/'atlas-region-checks'/f'seed{seed}_{mode}_{u}';folder.mkdir(parents=True,exist_ok=True)
 row=next(x for x in read(R/'directions'/f'seed{seed}_{mode}_{u}/radii.csv') if int(x['pair'])==fam['pair'] and int(x['direction'])==0 and int(x['steps'])==3000)
 L=float(row['lower']);cases=[('minus_lower',-L),('plus_lower',L)]
 queries=[x for x in read(R/'directions'/f'seed{seed}_{mode}_{u}/queries.csv') if int(x['pair'])==fam['pair'] and int(x['direction'])==0 and int(x['steps'])==3000 and (int(x['minus'])>=0 or int(x['plus'])>=0)]
 if queries:
  x=min(queries,key=lambda x:float(x['radius']));a=float(x['radius']);cases.append(('failure_witness',-a if int(x['minus'])>=0 else a))
 results=[]
 for label,alpha in cases:
  m=variant(base,seed,mode,record=False,alpha=alpha,fam=fam,di=0);z=cached_run(m,folder/label,False);bad=replay.point(data,sg,alpha)[0];diff=np.argwhere(z['spikes']!=ref['spikes'])
  if bad<0:assert not len(diff),(job,label,'Atlas differs inside region')
  else:
   n,k=divmod(bad,8);assert len(diff) and diff[0,0]==n,(job,label,bad,diff[:3]);assert z['spikes'][n,neur[k]]!=ref['spikes'][n,neur[k]],(job,label,bad)
  results.append(dict(label=label,alpha=alpha,local_first_mismatch=bad,atlas_first_mismatch_slot=-1 if not len(diff) else int(diff[0,0]),full_network_spikes_equal=not len(diff)))
 save(folder/'validation.json',dict(status='pass',cases=results));print('ATLAS REGION CHECK',seed,mode,u,flush=True)

def main():
 import brian2_atlas
 assert load(R/'region-validation.json')['status']=='pass'
 jobs=[(s,m,u) for s in SEEDS for m in MODES for u in INPUTS]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(work,jobs))
 rows=[]
 for s,m,u in jobs:
  for x in load(R/'atlas-region-checks'/f'seed{s}_{m}_{u}/validation.json')['cases']:rows.append(dict(seed=s,mode=m,input=u,**x))
 table(R/'atlas-region-checks/results.csv',rows);save(R/'atlas-region-validation.json',dict(status='pass',runs=len(rows),safe_endpoint_runs=sum(x['label']!='failure_witness' for x in rows),failure_witness_runs=sum(x['label']=='failure_witness' for x in rows)))
if __name__=='__main__':main()
