from pathlib import Path
import csv,json,hashlib,sys
import numpy as np
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[2]/'output/local-circuit-preprint-20261026-final-review/evidence'
OLD=ROOT.parent/'paired-direction-mechanism-20261108'
sys.path.insert(0,str(OLD));import mechanism as m
p=m.p;a=p.a
INPUTS=['G_B','F_B','F_H','G_T','F_HT'];INDEX={u:i+1 for i,u in enumerate(INPUTS)}
CONTRASTS=[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def read(f):return list(csv.DictReader(Path(f).open()))
def load(f):return json.loads(Path(f).read_text())
def write(f,x):Path(f).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def table(f,rows):
 with Path(f).open('w') as out:w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def events(u):
 mat=np.zeros((300,125),np.float32)
 for r in read(ROOT/'events'/f'{u}.csv'):mat[int(r['slot']),int(r['target'])]=np.array(int(r['amplitude_bits']),np.uint32).view(np.float32)
 return mat
def graph(name='original'):
 return np.array([[int(r[k]) for k in ['arm','source','target','weight_bits','delay']] for r in read(ROOT/'graphs'/f'{name}.csv')],np.uint32)
def incoming(g,sp,ext,k):
 vals=[[[],[]] for _ in range(300)];due=np.zeros(302,bool);pending=np.zeros(300,bool)
 for row in sorted(g[g[:,2]==k],key=lambda r:int(r[1])):
  src=int(row[1]);arr=np.flatnonzero(sp[:,src])+2;due[arr]=True
  amp=np.float32(row[3].view(np.float32)*np.float32(100))
  for n in arr[arr<300]:vals[n][int(src>=100)].append(amp)
  pending[1:]|=sp[:-1,src]>0
 for n in np.flatnonzero(ext[:,k]):vals[n][0].append(ext[n,k]);due[n]=True
 return vals,due[:300],pending

def reference_cache(ref,g,ext):
 assert ref.shape==(300,125,10);assert np.all(np.isin(ref[:,:,0],[0,100]));assert np.all(ref[:,:,4:6]==0) and np.all(ref[:,:,7]==0)
 cache={}
 for k in range(125):
  vals,due,pending=incoming(g,ref[:,:,0],ext,k);v=np.float32(-65);ge=gi=np.float32(0);deadline=0;active=False;execute=[];pre=[]
  for n in range(300):
   step=bool(active or due[n]);execute.append(step);fe=np.float32(0) if n==0 else ref[n-1,k,6].view(np.float32);eligible=deadline<=n
   if step:
    vp,ge,gi=a.point_step(v,ge,gi,fe,np.float32(0),vals[n],eligible);fired=bool(eligible and vp>=30);v=np.float32(-65) if fired else vp
    if fired:deadline=n+2
    hot=bool(fired or due[n] or abs(ref[n,k,6].view(np.float32))>np.float32(1e-6) or ge>np.float32(1e-6) or gi>np.float32(1e-6));status=1 if hot else 2 if pending[n] else 0;active=hot or pending[n]
   else:vp=v;fired=False;status=0;active=False
   assert (int(fired)*100,int(v.view(np.uint32)),int(ge.view(np.uint32)),int(gi.view(np.uint32)),deadline,status)==tuple(int(ref[n,k,j]) for j in [0,1,2,3,8,9]),('reference',k,n)
   pre.append(vp)
  cache[k]=dict(execute=execute,pre=pre)
 return cache

def prepare(ref,cache,g,ext,fam):
 targets=fam['targets'];flags=[];fields=[];offsets=[0];ev=[];weights=[];ids=[];edges=[]
 for k in targets:
  entries=[[[],[]] for _ in range(300)];due=np.zeros(302,bool);pending=np.zeros(300,bool)
  for e in sorted(g[g[:,2]==k],key=lambda r:int(r[1])):
   src=int(e[1]);w=e[3].view(np.float32);eid=len(edges);edges.append([src,k,int(e[3])]);arr=np.flatnonzero(ref[:,src,0])+2;due[arr]=True;pending[1:]|=ref[:-1,src,0]>0
   for n in arr[arr<300]:entries[n][int(src>=100)].append((np.float32(w*100),w,eid))
  for n in np.flatnonzero(ext[:,k]):entries[n][0].append((ext[n,k],np.float32(0),-1));due[n]=True
  for n in range(300):
   flags.append([cache[k]['execute'][n],bool(ref[n,k,0]),due[n],pending[n],ref[n,k,9]])
   fields.append([0 if n==0 else ref[n-1,k,6].view(np.float32),ref[n,k,6].view(np.float32)])
   for ch in range(2):
    for amp,w,eid in entries[n][ch]:ev.append(amp);weights.append(w);ids.append(eid)
    offsets.append(len(ev))
 assert edges==fam['edges']
 data=[np.asarray(flags,np.int32),np.asarray(fields,np.float32),np.asarray(offsets,np.int32),np.asarray(ev,np.float32)]
 return data,np.asarray(weights,np.float32),np.asarray(ids,np.int32)

def factor_scores(inp,ref,cache,targets):
 mask=np.array([np.array(cache[k]['execute']) & np.r_[True,ref[:-1,k,8]<=np.arange(1,300)] for k in targets]);margin=np.array([np.maximum(np.abs(np.asarray(cache[k]['pre'],float)-30),2**-20) for k in targets]);x=inp[:,:,0]-inp[:,:,1];z=np.zeros_like(x);d=float(a.d)
 for k in range(2):
  v=0.
  for n in range(300):v=d*v+(1-d)*x[k,n];z[k,n]=v
 return dict(zip(['f0m0','f1m0','f0m1','f1m1'],[float(y[mask].max()) for y in [abs(x),abs(z),abs(x)/margin,abs(z)/margin]]))

def truth(x,y):
 if y['upper'] not in [None,''] and float(x['lower'])>float(y['upper']):return 1
 if x['upper'] not in [None,''] and float(y['lower'])>float(x['upper']):return -1
 return 0

def pred(x,y):return 0 if abs(x-y)<=1e-10*max(1,abs(x),abs(y)) else 1 if x<y else -1
