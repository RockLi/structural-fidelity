#!/usr/bin/env python3
import sys,json,csv,hashlib,time,ctypes as C,statistics,argparse
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
PREV=ROOT.parent/'finite-horizon-family-prototype-20261108'
sys.path.insert(0,str(PREV));import prototype as p
a=p.a
PROBES=['tonic','global_burst','focal_burst'];RADII=[0,2**-16,2**-12,2**-8,2**-6,2**-4,.25]

def table(path,rs):
 with path.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def pair_pool(orig,targets,index):
 edges=[]
 for k in targets:
  for e in sorted(orig[orig[:,2]==k],key=lambda e:int(e[1])):edges.append([int(e[1]),int(k),int(e[3])])
 groups={}
 for j,(src,k,bits) in enumerate(edges):groups.setdefault((k,int(src>=100),bits),[]).append(j)
 groups=[v[:len(v)//2*2] for _,v in sorted(groups.items())];rng=np.random.default_rng(20261108+index);pool=[];seen=set()
 for draw in range(10000):
  v=np.zeros(len(edges),np.int32)
  for g in groups:
   signs=np.array([1]*(len(g)//2)+[-1]*(len(g)//2),np.int32);rng.shuffle(signs);v[g]=signs
  nz=np.flatnonzero(v)
  if len(nz)==0:break
  if v[nz[0]]<0:v=-v
  key=tuple(v)
  if key not in seen:pool.append(v.tolist());seen.add(key)
  if len(pool)==16:break
 assert pool
 for v in pool:
  assert np.count_nonzero(v)==sum(map(len,groups))
  for g in groups:assert sum(v[j] for j in g)==0
 return dict(pair=index,targets=list(targets),edges=edges,directions=pool,draws=draw+1,active_edges=sum(map(len,groups)),groups=groups)

def build(probe,ref,cache,orig,fam,slots):
 data,w,_,ids,edges=p.prepare(probe,ref,cache,orig,fam['targets'],slots)
 assert [[x[0],x[1],int(np.float32(x[2]).view(np.uint32))] for x in edges]==fam['edges']
 return data,w,ids

def eventsigns(fam,direction,ids):
 s=np.zeros((len(ids),2),np.int32);ok=ids>=0;s[ok,0]=np.asarray(fam['directions'][direction],np.int32)[ids[ok]];return s

def impulses(fam,direction,sp):
 arr=np.zeros((2,300,2),float);targets=fam['targets']
 for (src,k,bits),sgn in zip(fam['edges'],fam['directions'][direction]):
  w=float(np.array(bits,np.uint32).view(np.float32));arr[targets.index(k),2:,int(src>=100)]+=w*sgn*sp[:-2,src]
 return arr

def simple_score(inp,ref,cache,targets):
 best=(-1,None,None);d=float(a.d)
 for ki,k in enumerate(targets):
  z=0.
  for n in range(300):
   z=d*z+(1-d)*(inp[ki,n,0]-inp[ki,n,1])
   eligible=n==0 or ref[n-1,k,8]<=n
   if cache[k]['execute'][n] and eligible:
    score=abs(z)/max(abs(float(cache[k]['pre'][n])-30),2**-20)
    if score>best[0]:best=(score,k,n)
 return best

def full_score(inp,ref,cache,targets):
 best=(-1,None,None);h=float(a.h);dec=float(a.d)
 for ki,k in enumerate(targets):
  v=ge=gi=0.
  for n in range(300):
   if not cache[k]['execute'][n]:continue
   ge+=inp[ki,n,0];gi+=inp[ki,n,1]
   if n==0 or ref[n-1,k,8]<=n:
    pre=(1-h)*v+h*(ge-gi);score=abs(pre)/max(abs(float(cache[k]['pre'][n])-30),2**-20)
    if score>best[0]:best=(score,k,n)
    v=0. if ref[n,k,0] else pre;ge*=dec;gi*=dec
 return best

def argmin(rows,key):
 low=min(x[key] for x in rows);return min(x['direction'] for x in rows if abs(x[key]-low)<=1e-10*max(1,abs(low),abs(x[key])))

def target_point(data,ev,ki,trace=False):
 f,z,o,_=data;r=p.Result();tr=np.empty((300,6),np.float32) if trace else None
 p.lib.run(1,1,300,p.ptr(f[ki*300:(ki+1)*300],p.IP),p.ptr(z[ki*300:(ki+1)*300]),p.ptr(o[ki*600:],p.IP),p.ptr(ev),C.byref(r),None if tr is None else p.ptr(tr),p.old.fallback)
 return r,tr

def point_all(data,ev,targets,trace=False):
 rs=[target_point(data,ev,i,trace) for i in range(2)];bad=[(r.slot,targets[i],r.reason) for i,(r,_) in enumerate(rs) if not r.certified]
 return (None if not bad else min(bad)),rs

def python_target(data,ev,ki):
 f,z,o,_=data;v=np.float32(-65);ge=gi=np.float32(0);active=False;deadline=0;trace=[]
 for n in range(300):
  row=ki*300+n;flags=f[row];execute=active or flags[2]
  if execute!=flags[0]:return n,1,trace
  if execute:
   b,mid,end=o[row*2:row*2+3];vp,ge,gi=a.point_step(v,ge,gi,z[row,0],np.float32(0),[ev[b:mid],ev[mid:end]],deadline<=n)
   if deadline<=n:
    if bool(vp>=30)!=bool(flags[1]):return n,2,trace
    v=np.float32(-65) if flags[1] else vp
    if flags[1]:deadline=n+2
   elif flags[1]:raise AssertionError('refractory')
   hot=bool(flags[1] or flags[2] or abs(z[row,1])>np.float32(1e-6) or ge>np.float32(1e-6) or gi>np.float32(1e-6))
   status=1 if hot else 2 if flags[3] else 0
   if status!=flags[4]:return n,4,trace
   active=hot or flags[3]
  else:
   if flags[1]:return n,5,trace
   active=False
  trace.append([v,v,ge,ge,gi,gi])
 return -1,0,trace

def validate_point(data,w,signs,ids,fam,direction,t,ev,targets):
 wb=[]
 for (src,k,bits),sgn in zip(fam['edges'],fam['directions'][direction]):
  w0=np.array(bits,np.uint32).view(np.float32);wv=a.rn(a.q(w0)*(a.F(1)+a.F(t)*int(sgn)));wb.append(np.float32(wv*100))
 expected=data[-1].copy();ok=ids>=0;expected[ok]=np.asarray(wb,np.float32)[ids[ok]]
 assert np.array_equal(expected.view(np.uint32),ev.view(np.uint32))
 bad,rs=point_all(data,ev,targets,True)
 for ki,(r,tr) in enumerate(rs):
  slot,reason,py=python_target(data,ev,ki);py=np.asarray(py,np.float32).reshape(-1,6)
  assert r.reason==reason and r.slot==slot and r.trace_rows==len(py)
  assert np.array_equal(tr[:len(py)].view(np.uint32),py.view(np.uint32))
 return bad,sum(r.trace_rows*6 for r,_ in rs)

def main():
 q=argparse.ArgumentParser();q.add_argument('--output-dir',type=Path,default=ROOT/'results');args=q.parse_args();out=args.output_dir;out.mkdir(exist_ok=False)
 orig=a.graph('original');oset={tuple(map(int,x)) for x in orig};pairs=set()
 for seed in range(93001,93020):
  g=a.graph('swap'+str(seed));pairs.add(tuple(sorted({e[2] for e in oset^{tuple(map(int,x)) for x in g}})))
 pools=[pair_pool(orig,t,i) for i,t in enumerate(sorted(pairs))];a.write(out/'pool-lock.json',pools);poolhash=digest(pools)
 refs={};cache={};slots={};setuptime={};spikes={};mean={};shuffled={}
 for i,u in enumerate(PROBES):
  t=time.perf_counter();refs[u]=a.state(u);cache[u],_=a.reference_cache(u,refs[u],orig);slots[u]=[np.flatnonzero(refs[u][:,k,0]) for k in range(a.N)];setuptime[u]=time.perf_counter()-t
  spikes[u]=refs[u][:,:,0].astype(float);mean[u]=np.broadcast_to(spikes[u].mean(axis=0),spikes[u].shape)
  rng=np.random.default_rng(20261108+i);shift=rng.integers(1,300,a.N);shuffled[u]=np.stack([np.roll(spikes[u][:,j],int(shift[j])) for j in range(a.N)],axis=1)
 scores=[];choices=[]
 for fam in pools:
  for u in PROBES:
   for di in range(len(fam['directions'])):
    inp=impulses(fam,di,spikes[u]);ts=simple_score(inp,refs[u],cache[u],fam['targets']);ms=simple_score(impulses(fam,di,mean[u]),refs[u],cache[u],fam['targets']);ss=simple_score(impulses(fam,di,shuffled[u]),refs[u],cache[u],fam['targets']);fs=full_score(inp,refs[u],cache[u],fam['targets'])
    scores.append(dict(pair=fam['pair'],probe=u,direction=di,temporal=ts[0],mean=ms[0],shuffle=ss[0],full=fs[0],raw=float(np.max(np.abs(inp[:,:,0]-inp[:,:,1]))),temporal_target=ts[1],temporal_slot=ts[2],full_target=fs[1],full_slot=fs[2],projection_nonzero=bool(np.any(inp!=0)),net_projection_nonzero=bool(np.any(inp[:,:,0]!=inp[:,:,1])),target_spike_slots=int(refs[u][:,fam['targets'],0].sum()//100)))
  train=[x for x in scores if x['pair']==fam['pair'] and x['probe']=='tonic']
  choices.append(dict(pair=fam['pair'],random=0,mean=argmin(train,'mean'),shuffle=argmin(train,'shuffle'),temporal=argmin(train,'temporal')))
 table(out/'scores.csv',scores);table(out/'selection-lock.csv',choices)
 a.write(out/'selection-lock.json',dict(pool_sha256=poolhash,scores_sha256=a.sha(out/'scores.csv'),choices_sha256=a.sha(out/'selection-lock.csv'),training_input='tonic',perturbed_results_seen=False))
 outcomes=[];queries=[];checkcount=0;scoremap={(x['pair'],x['probe'],x['direction']):x for x in scores}
 for fam in pools:
  targets=fam['targets']
  for u in PROBES:
   data,w,ids=build(u,refs[u],cache[u],orig,fam,slots[u]);zero_bad,zrs=point_all(data,data[-1],targets,True);assert zero_bad is None
   for ki,(r,tr) in enumerate(zrs):assert np.array_equal(tr[:,[0,2,4]].view(np.uint32),refs[u][:,targets[ki],[1,2,3]])
   for di in range(len(fam['directions'])):
    signs=eventsigns(fam,di,ids);memo={}
    def evaluate(rho,phase):
     if rho in memo:return memo[rho]
     ag=p.model(data,w,signs,1,rho);r=p.family(data,ag,1,0)
     bads=[]
     for sign in [-1,1]:
      ev=p.point_stream(data,w,signs,1,rho,[float(sign)]);bad,_=point_all(data,ev,targets)
      if bad is not None:bads.append((bad[0],bad[1],bad[2],rho*sign))
     bad=None if not bads else min(bads)
     if r.certified:assert bad is None
     z=dict(pair=fam['pair'],probe=u,direction=di,rho=rho,phase=phase,certified=bool(r.certified),cert_reason=p.old.REASONS[r.reason],witness=bad is not None,witness_t=None if bad is None else bad[3],witness_slot=None if bad is None else bad[0],witness_target=None if bad is None else bad[1],witness_reason=None if bad is None else p.old.REASONS[bad[2]])
     queries.append(z);memo[rho]=z;return z
    L=0.;U=None;witness=None;stop='cap_unresolved';refinements=0
    for rho in RADII:
     z=evaluate(rho,'initial')
     if z['certified']:L=rho
     if z['witness']:U=rho;witness=z;break
    if U is None:stop='cap_certified' if L==.25 else 'cap_unresolved'
    else:
     stop='refinement_limit'
     for it in range(8):
      if U-L<=max(2**-20,.05*U):stop='bracket_tolerance';break
      mid=(L+U)/2;z=evaluate(mid,'refine');refinements+=1
      if z['certified']:L=mid
      elif z['witness']:U=mid;witness=z
      else:stop='proof_gap';break
     if U-L<=max(2**-20,.05*U):stop='bracket_tolerance'
    if witness:
     t=witness['witness_t'];ev=p.point_stream(data,w,signs,1,abs(t),[1. if t>=0 else -1.]);bad,n=validate_point(data,w,signs,ids,fam,di,t,ev,targets);checkcount+=n
     assert (bad[0],bad[1],p.old.REASONS[bad[2]])==(witness['witness_slot'],witness['witness_target'],witness['witness_reason'])
    outcomes.append(dict(pair=fam['pair'],probe=u,direction=di,lower=L,upper=U,stop=stop,refinements=refinements,queries=len(memo),witness_t=None if witness is None else witness['witness_t'],witness_slot=None if witness is None else witness['witness_slot'],witness_target=None if witness is None else witness['witness_target'],witness_reason=None if witness is None else witness['witness_reason'],projection_nonzero=scoremap[fam['pair'],u,di]['projection_nonzero'],net_projection_nonzero=scoremap[fam['pair'],u,di]['net_projection_nonzero'],target_spike_slots=scoremap[fam['pair'],u,di]['target_spike_slots']))
   print('pair',fam['pair'],targets,u,'done',flush=True)
 table(out/'radii.csv',outcomes);table(out/'queries.csv',queries)
 a.write(out/'summary.json',dict(status='pass',target_pairs=len(pools),pool_sizes=[len(x['directions']) for x in pools],directions_input_conditions=len(outcomes),radius_queries=len(queries),point_prefix_values_validated=checkcount,pool_sha256=poolhash,setup_seconds=setuptime,new_full_network_runs=0,original_graph_only=True,no_new_input_protocols=True))
 a.write(out/'code-sha256.json',{str(f.resolve()):a.sha(f) for f in [ROOT/'mechanism.py',ROOT/'PROTOCOL.txt',PREV/'prototype.py',PREV/'kernel.c',PREV/'kernel.dylib',a.ROOT/'audit.py']})
if __name__=='__main__':main()
