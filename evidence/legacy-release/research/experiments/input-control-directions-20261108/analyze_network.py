import itertools,collections
from common import *
rows=[];activity=[]
for u in INPUTS:
 ref=np.load(ROOT/'runs'/f'original__{u}.npz')['state_bits'];sp=ref[:,:,0].astype(np.int64);den=int(sp.sum());assert den>0
 activity.append(dict(input=u,total_spikes=den,active_chunks=int((sp.sum(0)>0).sum()),spiking_slots=int((sp.sum(1)>0).sum()),min_voltage=float(np.ascontiguousarray(ref[:,:,1]).view(np.float32).min())))
 for sid in range(93001,93020):
  bits=np.load(ROOT/'runs'/f'swap{sid}__{u}.npz')['state_bits'];delta=bits[:,:,0].astype(np.int64)-sp;ds=int(abs(delta).sum());dc=int(abs(delta.sum(0)).sum());dg=int(abs(delta.sum(1)).sum());idx=np.flatnonzero(np.any(delta!=0,axis=1))
  rows.append(dict(swap=sid,input=u,Dslot=ds/den,Dcount=dc/den,Dglobal=dg/den,R=None if ds==0 else dc/ds,slot_absolute=ds,count_absolute=dc,reference_spikes=den,spike_equal=ds==0,bitwise_equal=bool(np.array_equal(bits,ref)),first_mismatch=None if not len(idx) else int(idx[0])))
table(ROOT/'network-metrics.csv',rows);table(ROOT/'reference-activity.csv',activity)
lookup={(r['swap'],r['input']):r for r in rows};contrasts=[];patterns=[]
for u,v in CONTRASTS:
 c=collections.Counter(('same' if lookup[s,u]['spike_equal'] else 'different')+'/'+('same' if lookup[s,v]['spike_equal'] else 'different') for s in range(93001,93020))
 contrasts.append(dict(input_a=u,input_b=v,**{k:c[k] for k in ['same/same','different/different','same/different','different/same']}))
for s in range(93001,93020):patterns.append(dict(swap=s,**{u:lookup[s,u]['spike_equal'] for u in ['G_B','F_H','G_T','F_HT']}))
table(ROOT/'visibility-contrasts.csv',contrasts);table(ROOT/'joint-patterns.csv',patterns)
write(ROOT/'network-analysis.json',dict(inputs={u:dict(spike_equal=sum(r['spike_equal'] for r in rows if r['input']==u),Dslot_median=float(np.median([r['Dslot'] for r in rows if r['input']==u])),R_median_nonzero=None if not any(r['R'] is not None for r in rows if r['input']==u) else float(np.median([r['R'] for r in rows if r['input']==u and r['R'] is not None]))) for u in INPUTS},contrasts=contrasts,activity=activity))
