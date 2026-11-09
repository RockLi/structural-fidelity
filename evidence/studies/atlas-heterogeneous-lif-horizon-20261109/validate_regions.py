from analysis_common import *
from fractions import Fraction as F
import time,concurrent.futures

def f(x):return F.from_float(float(x))
def rn(x):return float(x)
def v_exact(v,e,i,d,tau):
 # Every primitive rounded separately; same AST as emitted Atlas model.
 a=rn(f(d)+f(e));b=rn(f(-.065+.018)+f(a));c=rn(f(i)+f(v));d=rn(f(b)-f(c));e=rn(f(.0001)*f(d));g=rn(f(e)/f(tau));return rn(f(g)+f(v))
def g_exact(g,c):return rn(f(rn(f(c)*f(g)))+f(g))

def rational_checks(data,sg,alpha,T,pointout,pre,elig,aff,rho):
 # Fixed audit grid, includes endpoints and every 37th slot; no outcome selection.
 # Exact-rational evaluation of each rounded operation and exact enclosure test.
 _,off,ch,w,tau,th,drive,sp=data;checks=0;statechecks=0
 for n in sorted(set([0,T-1,*range(0,T,37)])):
  for k in range(8):
   q=k//4;v=-.060 if n==0 else pointout[n-1,k,0];e=0. if n==0 else pointout[n-1,k,1];i=0. if n==0 else pointout[n-1,k,2]
   z=v_exact(v,e,i,drive[n,q],tau[k]) if elig[n,k] else v
   assert bits(z)==bits(pre[n,k]),('voltage',n,k,z,pre[n,k]);checks+=7 if elig[n,k] else 1
   expect=-.060 if sp[n,k] else z;assert bits(expect)==bits(pointout[n,k,0])
   for d in range(3):
    m,a,err=aff[n,k,d];actual=f(pointout[n,k,d]);center=f(m)+f(a)*f(alpha)
    assert abs(actual-center)<=f(err),('affine exact containment',n,k,d,alpha,rho,float(abs(actual-center)),err);statechecks+=1
  for q in range(2):
   k=q*4;gg=[0.,0.] if n==0 else list(pointout[n-1,k,1:]);gg=[g_exact(gg[0],-.0001/.005),g_exact(gg[1],-.0001/.010)];checks+=4
   row=q*data[0]+n
   for idx in range(off[row],off[row+1]):
    scale=rn(f(1.)+f(rn(f(sg[idx])*f(alpha))));weight=rn(f(w[idx])*f(scale));a=int(ch[idx]);gg[a]=rn(f(gg[a])+f(weight));checks+=4
   for a in range(2):assert bits(gg[a])==bits(pointout[n,k,a+1]),('current',n,q,a)
 return checks,statechecks

def work(job):
 seed,mode,u=job;folder=R/'directions'/f'seed{seed}_{mode}_{u}'
 if (folder/'region-validation.json').exists():return
 rr=read(folder/'radii.csv');ref=reference(seed,mode,u);checks=0;rational=0;rational_states=0;multiweights=0;multistates=0;rows=[]
 pool=load(R/f'seed{seed}/pool-selected.json')
 for fam in pool:
  data,ids,neur=fast_stream(seed,mode,u,ref,fam['targets'],fam)
  for row in [x for x in rr if int(x['pair'])==fam['pair']]:
   T=int(row['steps']);di=int(row['direction']);rho=float(row['lower']);sg=replay.signs(fam,di,ids);guard,aff=replay.cert(data,sg,rho,T,True)
   if row['zero_cert']=='False':
    assert rho==0 and guard>=0;continue
   assert guard<0,(job,row)
   distinct_weights=len({(data[3]*(1+sg*a)).tobytes() for a in [-rho,0.,rho]})
   statehash=[]
   for alpha in [-rho,0.,rho]:
    bad,out,pre,elig=replay.point(data,sg,alpha,T,True);assert bad<0,(job,row,alpha,bad)
    # Double enclosure check with outward endpoint arithmetic; exact checks below.
    center=aff[:,:,:,0]+aff[:,:,:,1]*alpha;bound=aff[:,:,:,2]
    allowance=np.nextafter(bound+8*np.finfo(float).eps*(abs(aff[:,:,:,0])+abs(aff[:,:,:,1]*alpha)),np.inf)
    assert np.all(abs(out-center)<=allowance),(job,row,alpha)
    checks+=out.size;statehash.append(hashlib.sha256(out.tobytes()).hexdigest())
    if fam['pair']==pool[0]['pair'] and di==0:
     c,s=rational_checks(data,sg,alpha,T,out,pre,elig,aff,rho);rational+=c;rational_states+=s
   multiweights+=distinct_weights>1;multistates+=len(set(statehash))>1
   rows.append(dict(seed=seed,mode=mode,input=u,pair=fam['pair'],steps=T,direction=di,lower=rho,distinct_actual_event_weight_vectors=distinct_weights,distinct_endpoint_state_paths=len(set(statehash))))
 table(folder/'region-validation.csv',rows);save(folder/'region-validation.json',dict(status='pass',conditions=len(rows),endpoint_state_values=checks,exact_rational_rounded_operations=rational,exact_rational_affine_containment_values=rational_states,multiple_actual_weight_vectors=multiweights,multiple_actual_state_paths=multistates));print('REGION VALIDATED',seed,mode,u,flush=True)

def main():
 assert (R/'radius-complete.json').exists();jobs=[(s,m,u) for s in SEEDS for m in MODES for u in INPUTS]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(work,jobs))
 summary=[load(R/'directions'/f'seed{s}_{m}_{u}'/'region-validation.json') for s,m,u in jobs];save(R/'region-validation.json',dict(status='pass',**{k:sum(x[k] for x in summary) for k in summary[0] if k!='status'}))
if __name__=='__main__':main()
