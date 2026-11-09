#!/usr/bin/env python3
"""Recheck already evaluated largest boxes; export enclosures and state diversity."""
import json,itertools,hashlib
import numpy as np
import prototype as p
a=p.a;out=p.ROOT/'enclosures';out.mkdir(exist_ok=False)
rows=a.csvread(p.ROOT/'results/largest-regions.csv');orig=a.graph('original');oset={tuple(map(int,e)) for e in orig};refs={};cache={};slots={};records=[]
for probe in ['tonic','global_burst','focal_burst']:
 refs[probe]=a.state(probe);cache[probe],_=a.reference_cache(probe,refs[probe],orig);slots[probe]=[np.flatnonzero(refs[probe][:,k,0]) for k in range(a.N)]
for row in rows:
 if not row['largest_tested_passing_rho']:continue
 rho=float(row['largest_tested_passing_rho']);d=int(row['d']);stem=row['stem'];graph,probe=stem.split('__');g=a.graph(graph);targets=sorted({e[2] for e in oset^{tuple(map(int,x)) for x in g}})
 data,w,s,_,edges=p.prepare(probe,refs[probe],cache[probe],g,targets,slots[probe]);ag=p.model(data,w,s,d,rho)
 traces=[]
 for method in [0,1]:
  trace=np.empty((600,6),np.float64);r=p.family(data,ag,d,method,trace);assert r.certified;traces.append(trace)
 states=[]
 alphas=np.array(list(itertools.product([-1.,-.5,0.,.5,1.],repeat=d)))
 for alpha in alphas:
  ev=p.point_stream(data,w,s,d,rho,alpha);trace=np.empty((600,6),np.float32);r=p.point(data,ev,trace);assert r.certified;states.append(trace[:,[0,2,4]])
 states=np.asarray(states);span=np.max(states.astype(float),axis=0)-np.min(states.astype(float),axis=0)
 statehashes={hashlib.sha256(x.tobytes()).hexdigest() for x in states}
 np.savez_compressed(out/f'{stem}__d{d}.npz',affine_enclosure=traces[0],corner_enclosure=traces[1],sample_alphas=alphas,sample_states=states,targets=np.array(targets),rho=rho,flags=data[0],fields=data[1],offsets=data[2],base_events=data[3],event_weights=w,event_signs=s)
 records.append(dict(stem=stem,d=d,rho=rho,sample_states=len(states),distinct_sample_state_trajectories=len(statehashes),max_v_span=float(span[:,0].max()),max_ge_span=float(span[:,1].max()),max_gi_span=float(span[:,2].max())))
assert len(records)==40 and all(x['distinct_sample_state_trajectories']>1 for x in records)
a.write(p.ROOT/'state-diversity.json',dict(status='pass',records=records,scope='same parameter grid and largest passing boxes already evaluated; no additional conditions or full-network runs'))
print('saved',len(records),'existing box enclosures; all have distinct internal-state trajectories')
