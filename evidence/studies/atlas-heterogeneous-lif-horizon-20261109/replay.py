from model import *
import ctypes as ct
lib=ct.CDLL(str(R/'local.dylib'));DP=ct.POINTER(ct.c_double);IP=ct.POINTER(ct.c_int64);BP=ct.POINTER(ct.c_uint8)
lib.point.argtypes=[ct.c_int,ct.c_int,IP,BP,DP,DP,ct.c_double,DP,DP,DP,BP,DP,DP,BP];lib.point.restype=ct.c_int
lib.certify.argtypes=[ct.c_int,ct.c_int,IP,BP,DP,DP,ct.c_double,DP,DP,DP,BP,DP];lib.certify.restype=ct.c_int
def ptr(x,typ=DP):return None if x is None else x.ctypes.data_as(typ)
def stream(seed,mode,u,ref,targets,fam=None):
 g=edges(seed);sp=ref['spikes'];T=len(sp);offset=[0];weights=[];channel=[];ids=[]
 emap={} if fam is None else {(int(s),int(t)):i for i,(s,t,_) in enumerate(fam['edges'])}
 for k in targets:
  incoming=[(int(row[1]),int(row[2]),float(np.array(row[3],np.uint32).view(np.float32))*.001/4) for row in g if row[2]==k];incoming.sort()
  for n in range(T):
   if n>0:
    for source,target,w in incoming:
     for j in range(4):
      if sp[n-1,source*4+j]:weights.append(w);channel.append(source>=100);ids.append(emap.get((source,target),-1))
   offset.append(len(weights))
 tau,theta=pars(seed,mode);neur=np.array([4*k+j for k in targets for j in range(4)]);inp=input_matrix(u)[:T,targets];args=(T,np.array(offset,np.int64),np.array(channel,np.uint8),np.array(weights,float),np.ascontiguousarray(tau[neur]),np.ascontiguousarray(theta[neur]),np.ascontiguousarray(inp),np.ascontiguousarray(sp[:,neur]))
 return args,np.array(ids),neur

def point(data,signs,alpha=0.,limit=None,trace=False):
 T,off,ch,w,tau,th,drive,sp=data;limit=T if limit is None else limit;out=np.empty((limit,8,3)) if trace else None;pre=np.empty((limit,8)) if trace else None;eligible=np.empty((limit,8),np.uint8) if trace else None
 bad=lib.point(T,limit,ptr(off,IP),ptr(ch,BP),ptr(w),ptr(signs),alpha,ptr(tau),ptr(th),ptr(drive),ptr(sp,BP),ptr(out),ptr(pre),ptr(eligible,BP));return bad,out,pre,eligible

def cert(data,signs,rho,limit=None,trace=False):
 T,off,ch,w,tau,th,drive,sp=data;limit=T if limit is None else limit;out=np.empty((limit,8,3,3)) if trace else None
 bad=lib.certify(T,limit,ptr(off,IP),ptr(ch,BP),ptr(w),ptr(signs),rho,ptr(tau),ptr(th),ptr(drive),ptr(sp,BP),ptr(out));return bad,out

def signs(fam,di,ids):
 z=np.zeros(len(ids));mask=ids>=0;z[mask]=np.array(fam['directions'][di])[ids[mask]];return np.ascontiguousarray(z)
