"""Independent numeric checks for the incorporated tables, using deposited rows."""
import csv,json,statistics,collections
from pathlib import Path

def verify(root,tables):
 E=root/'research/experiments';I=E/'input-control-directions-20261108';A=E/'score-factor-coverage-audit-20261108';D=E/'paired-dose-composition-20261108'
 def read(p):return list(csv.DictReader(p.open()))
 def mean(xs):return statistics.mean(xs)
 dose=read(D/'results/per-chain.csv');factor=read(A/'results/rank-summary.csv');visibility=read(I/'network-metrics.csv');ds=json.loads((I/'directions/detailed-summary.json').read_text());radii=read(I/'directions/radii.csv');tr=read(I/'directions/selection-transfer.csv');n=0
 for lang,tabs in tables.items():
  tb=next(t for t in tabs if len(t)==4 and len(t[0])==6 and t[1][0]=='0.984')
  expected=[]
  for b,e in [('p01',28),('p02',56),('full',282)]:
   z=[x for x in dose if x['budget']==b];assert len(z)==10
   expected.append([f'{e/2845*100:.3f}',str(e),str(e//2),f'{mean(int(x["Dslot"])/147600 for x in z):.4f}',f'{mean(int(x["Dcount"])/147600 for x in z):.4f}',f'{100*mean(int(x["Dcount"])/int(x["Dslot"]) for x in z):.2f}'])
  assert tb[1:]==expected;n+=18
  tb=next(t for t in tabs if t[1][0] in ['Neither factor','无滤波无裕度'])
  for row,m in zip(tb[1:],['original_f0m0','original_f1m0','original_f0m1','original_f1m1','mean_f1m1','shuffle_f1m1']):
   assert row[1:]==[f"{float(next(x['macro'] for x in factor if x['probe']==u and x['method']==m)):.3f}" for u in ['tonic','global_burst','focal_burst']];n+=3
  tb=next(t for t in tabs if len(t)==6 and t[1][0]=='G_B / F_H')
  vis={(x['input'],x['swap']):x['spike_equal']=='True' for x in visibility}
  for row,(u,v) in zip(tb[1:],[('G_B','F_H'),('G_T','F_HT'),('G_B','G_T'),('F_H','F_HT'),('F_B','F_H')]):
   c=collections.Counter((vis[u,str(s)],vis[v,str(s)]) for s in range(93001,93020));assert row[1:]==[str(c[True,True]),str(c[False,False]),str(c[True,False]),str(c[False,True]),str(c[True,False]+c[False,True])];n+=5
  tb=next(t for t in tabs if t[0][1:]==['G_B','F_B','F_H','G_T','F_HT'])
  for row,m in zip(tb[1:8],['f0m0','f1m0','f0m1','temporal','mean','shuffle','full']):
   assert row[1:]==[f"{next(x['macro'] for x in ds['rank'] if x['input']==u and x['method']==m):.3f}" for u in ['G_B','F_B','F_H','G_T','F_HT']];n+=5
  assert tb[8][1:]==[f"{100*ds['coverage'][u]['resolved']/2280:.2f}" for u in ['G_B','F_B','F_H','G_T','F_HT']]
  assert tb[9][1:]==[str(19-len(ds['coverage'][u]['excluded_targets'])) for u in ['G_B','F_B','F_H','G_T','F_HT']];n+=10
  tb=next(t for t in tabs if len(t)==4 and len(t[0])==6 and t[1][1]=='1353')
  cov=read(A/'results/coverage-by-target.csv')
  for row,u in zip(tb[1:],['tonic','global_burst','focal_burst']):
   z=[x for x in cov if x['probe']==u]
   assert row[1:]==[str(sum(int(x[k]) for x in z)) for k in ['resolved','both_capped','proof_gap_overlap','finite_overlap','cap_overlap']];n+=5
  tb=next(t for t in tabs if len(t)==6 and len(t[0])==5 and t[1][0]=='G_B')
  for row,u in zip(tb[1:],['G_B','F_B','F_H','G_T','F_HT']):
   c=collections.Counter(x['stop'] for x in radii if x['probe']==u);assert row[1:]==[str(c[k]) for k in ['bracket_tolerance','proof_gap','cap_certified','refinement_limit']];n+=4
  tb=next(t for t in tabs if len(t)==16 and t[1][0]=='G_B');rows=[]
  for u in ['G_B','F_B','F_H','G_T','F_HT']:
   for control in ['random','mean','shuffle']:
    c=collections.Counter(x['outcome'] for x in tr if x['probe']==u and x['control']==control);rows.append([str(c['win']),str(c['loss']),str(c['tie_same_direction']+c['tie_at_cap']),str(c['unresolved'])])
  assert [x[2:] for x in tb[1:]]==rows;n+=60
 # Labels and row counts must match; compare all numeric cells in corresponding tables.
 import re
 assert len(tables['en'])==len(tables['zh'])
 for a,b in zip(tables['en'],tables['zh']):
  assert len(a)==len(b)
  for ra,rb in zip(a, b):
   assert len(ra)==len(rb)
   for x,y in zip(ra,rb):
    if re.fullmatch(r'[\d.,/%+−–() <>]+',x):assert x==y,(x,y)
 return dict(status='pass',new_numeric_cells_checked=n,bilingual_numeric_cells_equal=True,dose_means_recomputed_from30_chain_rows=True,input_visibility_recounted_from95_swap_rows=True,negative_stops_and_transfer_checked=True)
