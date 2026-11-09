#!/usr/bin/env python3
"""Post-hoc read-only context from saved reference flags, no new conditions."""
from pathlib import Path
import csv,json,numpy as np
ROOT=Path(__file__).resolve().parent
rows=list(csv.DictReader((ROOT/'results/largest-regions.csv').open()));records=[]
for r in rows:
 if not r['largest_tested_passing_rho']:continue
 z=np.load(ROOT/'enclosures'/f"{r['stem']}__d{r['d']}.npz")
 counts=z['flags'][:,1].reshape(2,300).sum(axis=1)
 records.append(dict(stem=r['stem'],d=int(r['d']),category=r['category'],rho=float(r['largest_tested_passing_rho']),target_spiking_slots=counts.tolist(),any_target_spikes=bool(np.any(counts)),both_targets_spike=bool(np.all(counts))))
(ROOT/'activity-context.json').write_text(json.dumps(dict(scope='read-only analysis of saved enclosures and common reference flags; no new runs',records=records),indent=2)+'\n')
