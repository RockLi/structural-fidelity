from analysis_common import *
import datetime,time,concurrent.futures
KEYS=['seed','mode','input','pair','steps','direction']
LEVELS=[0.,2**-16,2**-12,2**-8,2**-6,2**-4,.25]

def check_scores():
 lock=load(R/'score-lock.json')
 for p,h in lock['files'].items():assert sha(R/p)==h,p

def search(data,sg,T,identity):
 queries=[];best=0.;upper=None;witness=None;zero=False;gap=False;t=time.perf_counter()
 def query(r):
  nonlocal best,upper,witness,zero
  before=time.perf_counter();guard,_=replay.cert(data,sg,r,T);ct=time.perf_counter()-before
  before=time.perf_counter();minus=replay.point(data,sg,-r,T)[0];plus=replay.point(data,sg,r,T)[0];pt=time.perf_counter()-before
  if guard<0:assert minus<0 and plus<0,(identity,r,guard,minus,plus)
  if r==0:zero=guard<0;assert minus<0 and plus<0
  if guard<0:best=max(best,r)
  if minus>=0 or plus>=0:
   if upper is None or r<upper:upper=r;witness=-r if minus>=0 else r
  queries.append(dict(**identity,radius=r,guard=guard,minus=minus,plus=plus,cert_seconds=ct,two_point_seconds=pt))
  return guard,minus,plus
 for r in LEVELS:
  a,b,c=query(r)
  if r==0 and a>=0:break
  if b>=0 or c>=0:break
 if not zero:status='zero_guard'
 elif best==.25:status='cap'
 elif upper is None:status='proof_gap'
 else:
  status='iteration_limit'
  for iteration in range(8):
   if upper-best<=max(2**-20,.05*upper):status='tolerance';break
   mid=(best+upper)/2;a,b,c=query(mid)
   if a>=0 and b<0 and c<0:status='proof_gap';break
  if upper-best<=max(2**-20,.05*upper):status='tolerance'
 row=dict(**identity,lower=best,upper='' if upper is None else upper,witness='' if witness is None else witness,status=status,zero_cert=zero,queries=len(queries),seconds=time.perf_counter()-t)
 return row,queries

def work(job):
 seed,mode,u=job;out=R/'directions'/f'seed{seed}_{mode}_{u}';done=out/'radii-complete.json'
 if done.exists():return
 ref=reference(seed,mode,u);rows=[];queries=[]
 for fam in load(R/f'seed{seed}/pool-selected.json'):
  data,ids,neur=fast_stream(seed,mode,u,ref,fam['targets'],fam)
  for T in HORIZONS:
   for di in range(16):
    identity=dict(seed=seed,mode=mode,input=u,pair=fam['pair'],steps=T,direction=di);row,q=search(data,replay.signs(fam,di,ids),T,identity);rows.append(row);queries.extend(q)
 table(out/'radii.csv',rows);table(out/'queries.csv',queries);save(done,dict(status='pass',conditions=len(rows)));print('RADII COMPLETE',seed,mode,u,flush=True)

def main():
 check_scores();jobs=[(s,m,u) for s in SEEDS for m in MODES for u in INPUTS]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(work,jobs))
 rows=[];queries=[]
 for s,m,u in jobs:
  folder=R/'directions'/f'seed{s}_{m}_{u}';rows+=read(folder/'radii.csv');queries+=read(folder/'queries.csv')
 assert len(rows)==4320;table(R/'directions/radii.csv',rows);table(R/'directions/queries.csv',queries);save(R/'radius-complete.json',dict(status='pass',conditions=len(rows),queries=len(queries)));check_scores()
if __name__=='__main__':main()
