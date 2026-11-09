# Descriptive diagnostic only: no score, direction, radius or simulation changes.
from analysis_common import *
rows=[]
for seed in SEEDS:
 for mode in MODES:
  for u in INPUTS:
   ref,cache=get_cache(seed,mode,u);tau,theta=pars(seed,mode)
   for fam in load(R/f'seed{seed}/pool-selected.json'):
    neur=np.array([4*k+j for k in fam['targets'] for j in range(4)])
    for T in HORIZONS:
     eligible=cache['eligible'][:T,neur].astype(bool);margin=abs(cache['pre'][:T,neur]-theta[neur]);z=margin[eligible]
     rows.append(dict(seed=seed,mode=mode,input=u,pair=fam['pair'],steps=T,eligible_updates=int(eligible.sum()),updates_below_fixed_floor=int(np.count_nonzero(z<2**-20)),min_margin_volts=float(z.min()) if len(z) else '',floor_volts=2**-20))
table(R/'analysis/posthoc-margin-floor-audit.csv',rows)
