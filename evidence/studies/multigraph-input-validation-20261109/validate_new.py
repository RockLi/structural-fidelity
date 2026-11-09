from common import *
from directions import context
import network,time,statistics,ctypes as C
network.check();orig,refs,caches,exts=context(ROOT/'runs');pool=load(ROOT/'pool-lock.json');rmap={(int(x['pair']),x['probe'],int(x['direction'])):x for x in read(ROOT/'directions/radii.csv')}
sys.path.insert(0,str(p.ROOT));import oracle
selected={0,(len(pool)-1)//2,len(pool)-1};rows=[];exact=[];timings=[];endpoint_count=0;total_bounds=0
for fam in pool:
 for u in INPUTS:
  start=time.perf_counter();data,w,ids=prepare(refs[u],caches[u],orig,exts[u],fam);prep=time.perf_counter()-start
  for di in range(16):
   row=rmap[fam['pair'],u,di];rho=float(row['lower']);sg=m.eventsigns(fam,di,ids);ag=p.model(data,w,sg,1,rho);tr=np.full((600,6),np.nan,np.float64);res=p.family(data,ag,1,0,tr)
   assert res.certified or rho==0
   streams=[];wvec=[];traces=[]
   for alpha in [-1.,0.,1.]:
    ev=p.point_stream(data,w,sg,1,rho,[alpha]);bad,rr=m.point_all(data,ev,fam['targets'],True);assert bad is None
    streams.append(ev.view(np.uint32).tobytes());traces.append(b''.join(z.view(np.uint32).tobytes() for _,z in rr))
    weights=[int(a.rn(a.q(np.array(bits,np.uint32).view(np.float32))*(a.F(1)+a.F(rho)*a.F(alpha)*int(sign))).view(np.uint32)) for (_,_,bits),sign in zip(fam['edges'],fam['directions'][di])];wvec.append(tuple(weights))
    if alpha!=0:
     endpoint_count+=1
     if res.certified:
      for ki,(_,pt) in enumerate(rr):
       for j in range(3):assert np.all(pt[:,2*j]>=tr[ki*300:(ki+1)*300,2*j]) and np.all(pt[:,2*j]<=tr[ki*300:(ki+1)*300,2*j+1]);total_bounds+=600
   rows.append(dict(pair=fam['pair'],input=u,direction=di,lower=rho,interval_recheck=bool(res.certified),distinct_weight_vectors=len(set(wvec)),distinct_event_streams=len(set(streams)),distinct_state_traces=len(set(traces)),stop=row['stop']))
   if fam['pair'] in selected and di==0:
    n,reason=oracle.check(data,w,sg,1,rho,tr[:res.trace_rows]);assert reason==res.reason and n==res.trace_rows
    exact.append(dict(pair=fam['pair'],input=u,lower=rho,reason=reason,endpoint_values=n*6))
    def cert():return p.family(data,p.model(data,w,sg,1,rho),1,0)
    def replay(count):
     for alpha in np.linspace(-1.,1.,count):m.point_all(data,p.point_stream(data,w,sg,1,rho,[float(alpha)]),fam['targets'])
    for _ in range(2):cert();replay(2);replay(25)
    cases=[('family_model_and_certificate',cert),('two_endpoints_generation_and_replay',lambda:replay(2)),('25_points_generation_and_replay',lambda:replay(25))]
    for rep in range(5):
     for label,fn in (cases if rep%2==0 else cases[::-1]):
      t=time.perf_counter()
      for _ in range(10):fn()
      timings.append(dict(pair=fam['pair'],input=u,lower=rho,method=label,round=rep,seconds=(time.perf_counter()-t)/10,preparation_seconds=prep))
 print('validated',fam['pair'],flush=True)
table(ROOT/'directions/coverage-witnesses.csv',rows);table(ROOT/'directions/cost.csv',timings);write(ROOT/'validation.json',dict(status='pass',intervals=len(rows),rechecked_positive=sum(r['lower']>0 and r['interval_recheck'] for r in rows),zero_uncertified=[r for r in rows if not r['interval_recheck']],endpoint_replays=endpoint_count,endpoint_state_bounds_checked=total_bounds,distinct_weights=sum(r['lower']>0 and r['distinct_weight_vectors']>1 for r in rows),distinct_events=sum(r['lower']>0 and r['distinct_event_streams']>1 for r in rows),distinct_states=sum(r['lower']>0 and r['distinct_state_traces']>1 for r in rows),exact_cases=exact,exact_endpoint_values=sum(x['endpoint_values'] for x in exact),timing_samples=len(timings)))
