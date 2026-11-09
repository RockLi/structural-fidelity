#!/usr/bin/env python3
import sys,json,csv,hashlib,ctypes as C
from pathlib import Path
import numpy as np
import mechanism as m
p=m.p;a=p.a
sys.path.insert(0,str(m.PREV));import oracle
ROOT=m.ROOT

def main():
 out=ROOT/'results';rs=a.csvread(out/'radii.csv');scores=a.csvread(out/'scores.csv');choices=a.csvread(out/'selection-lock.csv');pools=json.loads((out/'pool-lock.json').read_text());lock=json.loads((out/'selection-lock.json').read_text())
 assert lock['pool_sha256']==m.digest(pools) and lock['scores_sha256']==a.sha(out/'scores.csv') and lock['choices_sha256']==a.sha(out/'selection-lock.csv')
 orig=a.graph('original');refs={};cache={};slots={}
 for u in m.PROBES:
  refs[u]=a.state(u);cache[u],_=a.reference_cache(u,refs[u],orig);slots[u]=[np.flatnonzero(refs[u][:,k,0]) for k in range(a.N)]
 invariants=0
 for fam in pools:
  for t in [0,2**-16,.25,-.25]:
   refhist=None
   for direction in fam['directions']:
    group_hists=[]
    for group in fam['groups']:
     vals=[int(a.rn(a.q(np.array(fam['edges'][j][2],np.uint32).view(np.float32))*(a.F(1)+a.F(t)*int(direction[j]))).view(np.uint32)) for j in group]
     group_hists.append(sorted(vals))
    if refhist is None:refhist=group_hists
    else:assert group_hists==refhist
    invariants+=1
  train=[x for x in scores if int(x['pair'])==fam['pair'] and x['probe']=='tonic']
  parsed=[dict(direction=int(x['direction']),**{k:float(x[k]) for k in ['temporal','mean','shuffle']}) for x in train];chosen=next(x for x in choices if int(x['pair'])==fam['pair'])
  for key in ['temporal','mean','shuffle']:assert m.argmin(parsed,key)==int(chosen[key])
 # Certify every lower bound independently of the stored result; enclose actual endpoints.
 lowerchecks=0;endpointvalues=0;rational=[]
 for fam in pools:
  for u in m.PROBES:
   data,w,ids=m.build(u,refs[u],cache[u],orig,fam,slots[u])
   sel=int(next(x for x in choices if int(x['pair'])==fam['pair'])['temporal'])
   for row in [x for x in rs if int(x['pair'])==fam['pair'] and x['probe']==u]:
    di=int(row['direction']);rho=float(row['lower']);s=m.eventsigns(fam,di,ids);ag=p.model(data,w,s,1,rho);trace=np.empty((600,6),np.float64);r=p.family(data,ag,1,0,trace);assert r.certified;lowerchecks+=1
    for alpha in [-1.,1.]:
     ev=p.point_stream(data,w,s,1,rho,[alpha]);bad,prs=m.point_all(data,ev,fam['targets'],True);assert bad is None
     state=np.concatenate([tr[:,[0,2,4]] for _,tr in prs]).astype(float);assert np.all(trace[:,::2]<=state) and np.all(state<=trace[:,1::2]);endpointvalues+=state.size
    # Each tonic-selected temporal direction + fixed first/middle/last pair on both other inputs.
    use=(u=='tonic' and di==sel) or (u!='tonic' and fam['pair'] in [0,9,18] and di==0)
    if use:
     n,reason=oracle.check(data,w,s,1,rho,trace);assert reason==0 and n==600
     rational.append(dict(pair=fam['pair'],probe=u,direction=di,rho=rho,exact_endpoint_values=n*6));print('rational',fam['pair'],u,di,rho,flush=True)
    if row['upper']:
     t=float(row['witness_t']);ev=p.point_stream(data,w,s,1,abs(t),[1. if t>=0 else -1.]);bad,_=m.point_all(data,ev,fam['targets']);assert bad is not None
     assert (bad[0],bad[1],p.old.REASONS[bad[2]])==(int(row['witness_slot']),int(row['witness_target']),row['witness_reason'])
 a.write(ROOT/'validation.json',dict(status='pass',matched_group_histogram_checks=invariants,selection_locks_recomputed=True,all_certified_lower_bounds_rechecked=lowerchecks,endpoint_state_values_enclosed=endpointvalues,exact_rational_checks=rational,exact_endpoint_values=sum(x['exact_endpoint_values'] for x in rational),all_upper_bounds_have_actual_point_witness=True))
if __name__=='__main__':main()
