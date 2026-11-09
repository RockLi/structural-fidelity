from model import *
import replay,csv

def table(p,rows):
 with Path(p).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def read(p):return list(csv.DictReader(Path(p).open()))
def fast_stream(seed,mode,u,ref,targets,fam=None):
 g=edges(seed);sp=ref['spikes'];T=len(sp);off=[0];w=[];ch=[];ids=[];emap={} if fam is None else {(int(s),int(t)):i for i,(s,t,_) in enumerate(fam['edges'])}
 for target in targets:
  events=[]
  for row in g[g[:,2]==target]:
   source=int(row[1]);ww=float(np.array(row[3],np.uint32).view(np.float32))*.001/4;idx=emap.get((source,int(target)),-1)
   for j in range(4):
    unit=source*4+j
    for n in np.flatnonzero(sp[:-1,unit])+1:events.append((int(n),unit,ww,int(source>=100),idx))
  events.sort(key=lambda z:(z[0],z[1]));count=np.bincount([e[0] for e in events],minlength=T)
  off.extend((off[-1]+np.cumsum(count)).tolist());w.extend(e[2] for e in events);ch.extend(e[3] for e in events);ids.extend(e[4] for e in events)
 tau,th=pars(seed,mode);neur=np.array([4*k+j for k in targets for j in range(4)]);data=(T,np.array(off,np.int64),np.array(ch,np.uint8),np.array(w),np.ascontiguousarray(tau[neur]),np.ascontiguousarray(th[neur]),np.ascontiguousarray(input_matrix(u)[:T,targets]),np.ascontiguousarray(sp[:,neur]));return data,np.array(ids),neur

def reference(seed,mode,u):
 r=R/'runs'/f'seed{seed}_{mode}_{u}';z=np.load(r/'original.npz');return {k:z[k] for k in z.files}

def get_cache(seed,mode,u):
 p=R/'directions'/f'seed{seed}_{mode}_{u}';p.mkdir(exist_ok=True);target=p/'reference-cache.npz';ref=reference(seed,mode,u)
 if target.exists():z=np.load(target);return ref,{k:z[k] for k in z.files}
 pre=np.empty((3000,N));elig=np.empty((3000,N),np.uint8);checked=0
 for k in range(0,C,2):
  targets=[k,(k+1)%C];data,ids,neur=fast_stream(seed,mode,u,ref,targets);bad,out,pp,ee=replay.point(data,np.zeros(len(ids)),trace=True);assert bad<0,(seed,mode,u,targets,bad)
  actual=np.stack([ref['v'][:,neur],ref['ge'][:,neur],ref['gi'][:,neur]],axis=-1)
  assert np.array_equal(out.view(np.uint64),actual.view(np.uint64)),(seed,mode,u,targets,np.argwhere(out.view(np.uint64)!=actual.view(np.uint64))[:2])
  pre[:,neur]=pp;elig[:,neur]=ee;checked+=out.size
 np.savez_compressed(target,pre=pre,eligible=elig);save(p/'reference-validation.json',dict(status='pass',neurons=N,state_words_checked_with_one_duplicate_chunk=checked,unique_state_words=3000*N*3));return ref,dict(pre=pre,eligible=elig)

def impulse(fam,di,counts,T):
 coeff=np.zeros((C,2,2))
 for (src,dst,wb),sg in zip(fam['edges'],fam['directions'][di]):coeff[src,fam['targets'].index(dst),int(src>=100)]+=float(np.array(wb,np.uint32).view(np.float32))*.001/4*sg
 z=np.zeros((T,2,2));z[2:]=np.einsum('ts,sqc->tqc',counts[:T-2],coeff);return z

def score(seed,mode,fam,inp,cache,refsp,T):
 neur=np.array([4*k+j for k in fam['targets'] for j in range(4)]);tau,theta=pars(seed,mode);h=DT/tau[neur];beta=1-h;mask=cache['eligible'][:T,neur].astype(bool);margin=np.maximum(abs(cache['pre'][:T,neur]-theta[neur]),2**-20)
 cur=np.zeros((2,2));v=np.zeros(8);full=np.zeros(8);filtered=np.empty((T,8));fullpre=np.empty((T,8));raw=np.repeat(inp[:,:,0]-inp[:,:,1],4,axis=1)*h
 for n in range(T):
  cur=cur*np.array([1-DT/.005,1-DT/.010])+inp[n];net=np.repeat(cur[:,0]-cur[:,1],4);v=beta*v+h*net;filtered[n]=v
  full=np.where(mask[n],beta*full+h*net,full);fullpre[n]=full;full=np.where(refsp[n,neur]>0,0,full)
 def maximum(x):return 0. if not mask.any() else float(np.max(x[mask]))
 return dict(f0m0=maximum(abs(raw)),f1m0=maximum(abs(filtered)),f0m1=maximum(abs(raw)/margin),joint=maximum(abs(filtered)/margin),full=maximum(abs(fullpre)/margin),eligible=int(mask.sum()))
