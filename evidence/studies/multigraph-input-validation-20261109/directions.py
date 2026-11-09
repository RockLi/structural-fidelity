#!/usr/bin/env python3
import argparse,datetime,sys
from pathlib import Path
import numpy as np
from common import *
import network

def context(runs):
 orig=graph();refs={};caches={};exts={}
 for u in INPUTS:
  refs[u]=np.load(runs/f'original__{u}.npz')['state_bits'];exts[u]=events(u);caches[u]=reference_cache(refs[u],orig,exts[u]);print('reference checked',u,flush=True)
 return orig,refs,caches,exts

def score(runs,out):
 network.check();out.mkdir(exist_ok=False,parents=True);orig,refs,caches,exts=context(runs);pool=load(ROOT/'pool-lock.json');rows=[];choices=[];bridgechecks=0;old={}
 for fam in pool:
  i=fam['pair']
  for u in INPUTS:
   ref=refs[u];cache=caches[u];sp=ref[:,:,0].astype(float);mean=sp.copy();mean[:298]=sp[:298].mean(0);shuffle=sp.copy();rng=np.random.default_rng(20261108+INDEX[u]);shifts=rng.integers(1,298,125)
   for j in range(125):shuffle[:298,j]=np.roll(sp[:298,j],int(shifts[j]))
   assert np.allclose(mean[:298].sum(0),sp[:298].sum(0),rtol=0,atol=1e-8);assert np.array_equal(shuffle[:298].sum(0),sp[:298].sum(0))
   for di in range(16):
    inp=m.impulses(fam,di,sp);f=factor_scores(inp,ref,cache,fam['targets']);t=m.simple_score(inp,ref,cache,fam['targets']);full=m.full_score(inp,ref,cache,fam['targets']);assert f['f1m1']==t[0]
    row=dict(pair=i,probe=u,direction=di,**f,temporal=t[0],mean=m.simple_score(m.impulses(fam,di,mean),ref,cache,fam['targets'])[0],shuffle=m.simple_score(m.impulses(fam,di,shuffle),ref,cache,fam['targets'])[0],raw=float(abs(inp[:,:,0]-inp[:,:,1]).max()),full=full[0],temporal_target=t[1],temporal_slot=t[2],full_target=full[1],full_slot=full[2],projection_nonzero=bool(np.any(inp)),net_projection_nonzero=bool(np.any(inp[:,:,0]!=inp[:,:,1])),target_spike_slots=int(ref[:,fam['targets'],0].sum()//100));rows.append(row)
    if False: # old seed99 bridge is verified separately, never compared to new graphs

     z=old[i,'global_burst' if u=='G_B' else 'focal_burst',di]
     for key in ['temporal','raw','full']:assert row[key]==float(z[key]),(i,u,di,key);bridgechecks+=1
  train=[r for r in rows if r['pair']==i and r['probe']=='G_B'];choices.append(dict(pair=i,random=0,**{key:m.argmin(train,key) for key in ['f0m0','f1m0','f0m1','temporal','mean','shuffle','full']}))
 table(out/'scores.csv',rows);table(out/'selection-lock.csv',choices);write(out/'selection-lock.json',dict(locked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),training_input='G_B',certificate_outcomes_seen=False,pool_sha256=sha(ROOT/'pool-lock.json'),scores_sha256=sha(out/'scores.csv'),choices_sha256=sha(out/'selection-lock.csv'),reference_sha256={u:sha(runs/f'original__{u}.npz') for u in INPUTS},bridge_score_values_exact=bridgechecks));write(out/'pool-lock.json',pool);print('scores locked',len(rows),'bridge checks',bridgechecks,flush=True)

def radii(runs,out):
 network.check();lock=load(out/'selection-lock.json');assert sha(out/'scores.csv')==lock['scores_sha256'];assert sha(out/'selection-lock.csv')==lock['choices_sha256'];assert not (out/'radii.csv').exists()
 for u in INPUTS:assert sha(runs/f'original__{u}.npz')==lock['reference_sha256'][u]
 orig,refs,caches,exts=context(runs);pool=load(ROOT/'pool-lock.json');smap={(int(x['pair']),x['probe'],int(x['direction'])):x for x in read(out/'scores.csv')};queries=[];outcomes=[];prefixchecks=0;zerochecks=0;bridgecount=0;old={}
 for fam in pool:
  targets=fam['targets'];i=fam['pair']
  for u in INPUTS:
   data,w,ids=prepare(refs[u],caches[u],orig,exts[u],fam);bad,rr=m.point_all(data,data[-1],targets,True);assert bad is None
   for ki,(r,tr) in enumerate(rr):assert np.array_equal(tr[:,[0,2,4]].view(np.uint32),refs[u][:,targets[ki],[1,2,3]]);zerochecks+=tr.size
   for di in range(16):
    signs=m.eventsigns(fam,di,ids);memo={}
    def evaluate(rho,phase):
     if rho in memo:return memo[rho]
     ag=p.model(data,w,signs,1,rho);cert=p.family(data,ag,1,0);bads=[]
     for sg in [-1,1]:
      ev=p.point_stream(data,w,signs,1,rho,[float(sg)]);bad,_=m.point_all(data,ev,targets)
      if bad is not None:bads.append((bad[0],bad[1],bad[2],rho*sg))
     bad=None if not bads else min(bads)
     if cert.certified:assert bad is None
     z=dict(pair=i,probe=u,direction=di,rho=rho,phase=phase,certified=bool(cert.certified),cert_reason=p.old.REASONS[cert.reason],witness=bad is not None,witness_t=None if bad is None else bad[3],witness_slot=None if bad is None else bad[0],witness_target=None if bad is None else bad[1],witness_reason=None if bad is None else p.old.REASONS[bad[2]]);queries.append(z);memo[rho]=z;return z
    L=0.;U=None;witness=None;stop='cap_unresolved';refinements=0
    for rho in m.RADII:
     z=evaluate(rho,'initial')
     if z['certified']:L=rho
     if z['witness']:U=rho;witness=z;break
    if U is None:stop='cap_certified' if L==.25 else 'cap_unresolved'
    else:
     stop='refinement_limit'
     for it in range(8):
      if U-L<=max(2**-20,.05*U):stop='bracket_tolerance';break
      z=evaluate((L+U)/2,'refine');refinements+=1
      if z['certified']:L=z['rho']
      elif z['witness']:U=z['rho'];witness=z
      else:stop='proof_gap';break
     if U-L<=max(2**-20,.05*U):stop='bracket_tolerance'
    if witness:
     t=witness['witness_t'];ev=p.point_stream(data,w,signs,1,abs(t),[1. if t>=0 else -1.]);bad,n=m.validate_point(data,w,signs,ids,fam,di,t,ev,targets);prefixchecks+=n;assert (bad[0],bad[1],p.old.REASONS[bad[2]])==(witness['witness_slot'],witness['witness_target'],witness['witness_reason'])
    sc=smap[i,u,di];r=dict(pair=i,probe=u,direction=di,lower=L,upper=U,stop=stop,refinements=refinements,queries=len(memo),witness_t=None if witness is None else witness['witness_t'],witness_slot=None if witness is None else witness['witness_slot'],witness_target=None if witness is None else witness['witness_target'],witness_reason=None if witness is None else witness['witness_reason'],projection_nonzero=sc['projection_nonzero']=='True',net_projection_nonzero=sc['net_projection_nonzero']=='True',target_spike_slots=int(sc['target_spike_slots']));outcomes.append(r)
    if False: # old seed99 bridge is verified separately, never compared to new graphs

     z=old[i,'global_burst' if u=='G_B' else 'focal_burst',di]
     for key,value in r.items():
      if key=='probe':continue
      assert ('' if value is None else str(value))==z[key],('radius bridge',i,u,di,key,value,z[key])
     bridgecount+=1
   print('radii',i,u,'done',flush=True)
  table(out/'radii-progress.csv',outcomes);table(out/'queries-progress.csv',queries)
 table(out/'radii.csv',outcomes);table(out/'queries.csv',queries);write(out/'run-summary.json',dict(status='pass',conditions=len(outcomes),new_input_direction_conditions=len(outcomes),bridge_conditions_exact=bridgecount,point_prefix_values_validated=prefixchecks,zero_replay_values_checked=zerochecks,radius_queries=len(queries)))
 print('new graph radii complete',len(outcomes),flush=True)

if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('action',choices=['score','radii']);q.add_argument('--runs-dir',type=Path,default=ROOT/'runs');q.add_argument('--output-dir',type=Path,default=ROOT/'directions');x=q.parse_args()
 if x.action=='score':score(x.runs_dir,x.output_dir)
 else:radii(x.runs_dir,x.output_dir)
