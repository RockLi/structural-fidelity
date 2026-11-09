from common import *
from directions import context
import network
network.check();records=load(ROOT/'runs/completed.json')['records'];values=0
for x in records:
 stem=x['stem'];aa=np.load(ROOT/'runs'/f'{stem}.npz')['state_bits'];bb=np.load(ROOT/'runs-repeat'/f'{stem}.npz')['state_bits'];assert np.array_equal(aa,bb);assert (ROOT/'runs'/f'{stem}.csv').read_bytes()==(ROOT/'runs-repeat'/f'{stem}.csv').read_bytes();values+=aa.size
orig,refs,caches,exts=context(ROOT/'runs');rmap={(int(x['pair']),x['probe'],int(x['direction'])):x for x in read(ROOT/'directions/radii.csv')};pool=load(ROOT/'pool-lock.json');lowers=ends=exact_values=0;exact=[];zero_fail=[]
sys.path.insert(0,str(p.ROOT));import oracle
for fam in pool:
 for u in INPUTS:
  data,w,ids=prepare(refs[u],caches[u],orig,exts[u],fam)
  for di in range(16):
   r=rmap[fam['pair'],u,di];rho=float(r['lower']);sg=m.eventsigns(fam,di,ids);ag=p.model(data,w,sg,1,rho);tr=np.full((600,6),np.nan,np.float64);res=p.family(data,ag,1,0,tr)
   if not res.certified:assert rho==0;zero_fail.append([fam['pair'],u,di])
   else:lowers+=1
   for alpha in [-1.,1.]:
    ev=p.point_stream(data,w,sg,1,rho,[alpha]);bad,rr=m.point_all(data,ev,fam['targets'],True);assert bad is None
    if res.certified:
     for ki,(_,pt) in enumerate(rr):
      for j in range(3):assert np.all(pt[:,2*j]>=tr[ki*300:(ki+1)*300,2*j]) and np.all(pt[:,2*j]<=tr[ki*300:(ki+1)*300,2*j+1])
    ends+=1
   if fam['pair'] in [0,9,18] and di==0 and u in ['F_H','G_T','F_HT']:
    n,reason=oracle.check(data,w,sg,1,rho,tr[:res.trace_rows]);assert reason==0,(fam['pair'],u,reason);exact_values+=n;exact.append(dict(pair=fam['pair'],input=u,radius=rho,values=n))
 print('validated lower families',fam['pair'],flush=True)
write(ROOT/'validation.json',dict(status='pass',repeated_networks=len(records),identical_state_words=values,lower_certificates=lowers,zero_interval_failures=zero_fail,lower_endpoints=ends,exact_fraction_values=exact_values,exact_fraction_cases=exact,source_lock='pass'))
