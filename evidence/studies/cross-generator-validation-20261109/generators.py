"""Prespecified independent affinity-weighted graph generators; no dynamics."""
import numpy as np
COUNTS=[1467,610,648,120]
def family(seed):
 if seed in [201,202,203]:return 'module'
 assert seed in [301,302,303];return 'ring'
def make(seed):
 f=family(seed);meta_rng=np.random.Generator(np.random.PCG64(seed+1000000));rng=np.random.Generator(np.random.PCG64(seed))
 meta=dict(seed=seed,family=f,metadata_rng_initial=meta_rng.bit_generator.state,edge_rng_initial=rng.bit_generator.state)
 if f=='module':
  labels=np.empty(125,dtype=int);labels[meta_rng.permutation(100)]=np.repeat(np.arange(5),20);labels[100+meta_rng.permutation(25)]=np.repeat(np.arange(5),5)
  affinity=np.where(labels[:,None]==labels[None,:],4.,1.);meta['labels']=labels.tolist()
 else:
  coordinates=np.empty(125);coordinates[meta_rng.permutation(125)]=np.arange(125)/125
  dist=np.abs(coordinates[:,None]-coordinates[None,:]);dist=np.minimum(dist,1-dist);affinity=np.exp(-dist/.15);meta['coordinates']=coordinates.tolist()
 weights=np.array([.6,.8,1.4,.5],np.float32).view(np.uint32);rows=[]
 for arm,count in enumerate(COUNTS):
  src=np.arange(100) if arm<2 else np.arange(100,125);dst=np.arange(100) if arm%2==0 else np.arange(100,125)
  ss,tt=np.meshgrid(src,dst,indexing='ij');ss=ss.ravel();tt=tt.ravel();mask=ss!=tt;ss=ss[mask];tt=tt[mask]
  keys=-np.log(1-rng.random(len(ss)))/affinity[ss,tt];chosen=np.lexsort((tt,ss,keys))[:count]
  chosen=chosen[np.lexsort((tt[chosen],ss[chosen]))]
  rows.extend((arm,int(ss[i]),int(tt[i]),int(weights[arm]),1) for i in chosen)
 meta.update(metadata_rng_final=meta_rng.bit_generator.state,edge_rng_final=rng.bit_generator.state)
 e=np.array(rows,np.int64);assert len(e)==2845 and len(set(map(tuple,e[:,1:3])))==2845 and np.all(e[:,1]!=e[:,2]);assert np.bincount(e[:,0]).tolist()==COUNTS
 return e,meta

def describe(e,meta):
 a=np.zeros((125,125),np.int64);a[e[:,1],e[:,2]]=1;reach=a.astype(bool)|np.eye(125,dtype=bool)
 for k in range(125):reach|=reach[:,k,None]&reach[k,None,:]
 assigned=set();components=[]
 for i in range(125):
  if i in assigned:continue
  comp=np.flatnonzero(reach[i]&reach[:,i]);assigned.update(map(int,comp));components.append(len(comp))
 out=dict(edges=len(e),arm_counts=np.bincount(e[:,0],minlength=4).tolist(),in_degree_min=int(a.sum(0).min()),in_degree_max=int(a.sum(0).max()),out_degree_min=int(a.sum(1).min()),out_degree_max=int(a.sum(1).max()),reciprocal_pairs=int(np.sum(a*a.T)//2),directed_three_cycles=int(np.trace(a@a@a)//3),scc_count=len(components),scc_sizes=components)
 if meta['family']=='module':
  labels=np.array(meta['labels']);out['within_module_edge_fraction']=float(np.mean(labels[e[:,1]]==labels[e[:,2]]))
 else:
  c=np.array(meta['coordinates']);dist=np.abs(c[e[:,1]]-c[e[:,2]]);out['mean_ring_distance']=float(np.mean(np.minimum(dist,1-dist)))
 return out

def edit_change(orig,e,meta):
 changed=np.flatnonzero(orig[:,2]!=e[:,2]);assert len(changed)==2
 if meta['family']=='module':
  labels=np.array(meta['labels']);a=int(np.sum(labels[orig[changed,1]]==labels[orig[changed,2]]));b=int(np.sum(labels[e[changed,1]]==labels[e[changed,2]]))
  return dict(removed_within_module=a,inserted_within_module=b,within_module_edge_count_delta=b-a)
 c=np.array(meta['coordinates'])
 def length(g):
  dist=np.abs(c[g[changed,1]]-c[g[changed,2]]);return float(np.minimum(dist,1-dist).sum())
 a=length(orig);b=length(e);return dict(removed_ring_distance_sum=a,inserted_ring_distance_sum=b,total_ring_distance_delta=b-a)
