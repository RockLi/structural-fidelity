#!/usr/bin/env python3
"""Independent log/CSV audit. Writes only an explicitly requested /tmp report."""
from pathlib import Path
import argparse,csv,json,re,collections,decimal
P=argparse.ArgumentParser();P.add_argument('--archive',type=Path,default=Path('/Users/rock/workspace/next-brain.ai/next-brain.ai/output/local-circuit-preprint-20261022/evidence'));P.add_argument('--fresh-evidence',type=Path);P.add_argument('--fresh-run-dir',type=Path);P.add_argument('--report',type=Path,default=Path('/tmp/local-circuit-pipeline-revision/independent-csv-audit.json'));a=P.parse_args()
ROUNDED=['section','label','psth_r','fr_delta','spike_ratio','ev_ratio','ret_e','ev_share','gfe','gfi','exp','stateful','test_gate','source']
NUM=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
def read_csv(p):return list(csv.DictReader(p.open()))
def extract_rounded(path):
 rows=[];section=None
 for source_line,line in enumerate(path.read_text().splitlines(),1):
  h=re.search(r'\[(?:Frontier|HybridCalibrationGrid): ([^]]+)\]',line)
  if h: section=h.group(1);continue
  if not line.strip():section=None;continue
  single=re.match(r'(\[Stateful [^]]+\])',line)
  if single:
   label=single.group(1);sec='stateful_single_results'
  elif section and line.startswith('  ') and not line.lstrip().startswith('→') and 'psth_r=' in line:
   label=line.split('psth_r=',1)[0].strip().removesuffix('→').strip();sec=section
  else:continue
  row={k:'' for k in ROUNDED};row.update(section=sec,label=label,source_line=source_line)
  for key in ROUNDED[2:-2]+['burst','quiet','thr','stateful_thr']:
   hits=list(re.finditer(r'\b'+key+r'=('+NUM+r')',line))
   if hits:row[key]=hits[-1].group(1)
  gate=re.search(r'\b(GO|STOP)\s*$',line)
  if gate:row['test_gate']=gate.group(1)
  rows.append(row)
 return rows
PRIMARY={'4ch+trace (pure)','4ch+trace (hybrid)','4ch+trace-strong-inh (11.2%)','4ch+trace-strong-inh (homo, 22.8%)','stable','balanced','excitable','E5'}
def extract_diag(path,variant):
 rows=[]
 for source_line,line in enumerate(path.read_text().splitlines(),1):
  hit=re.search(r'\[DIAGNOSTIC(?:_E45)?\] label=(.*?) psth_r=(.*)',line)
  if not hit:continue
  label=hit.group(1);vals='psth_r='+hit.group(2)
  row=dict(re.findall(r'\b(\w+)=('+NUM+r')',vals));row.update(variant=variant,label=label,source_line=source_line)
  if label in ['2ch','4ch-default','4ch+trace (pure)','4ch+trace (hybrid)']: bench,N,T='E1 50k',50000,500
  elif label=='4ch+trace-strong-inh (homo, 22.8%)':bench,N,T='E3 homogeneous',12500,300
  elif label in ['stable','balanced','excitable']:bench,N,T='E4 '+label,5000,200
  elif label=='E5':bench,N,T='E5 perturbation',5000,300
  elif label.startswith('gfe='):bench,N,T='E1 medium calibration',12500,200
  else:bench,N,T='E3 heterogeneous',12500,200
  row.update(benchmark=bench,units=N,steps=T,dt_ms=.1,duration_ms=T*.1)
  q=int(row['approx_events'])/int(row['explicit_events']);row.update(event_ratio_from_counts=q,event_reduction_pct=100*(1-q))
  for prefix in ['explicit','approx']:row[prefix+'_mean_fr_hz']=int(row[prefix+'_spikes'])/(N*T*.1/1000)
  rows.append(row)
 return rows
def norm(value):
 if value is None or value=='':return ''
 try:return decimal.Decimal(str(value)).normalize()
 except decimal.InvalidOperation:return str(value)
def compare(rows,expected,ignore=('source','source_log')):
 assert len(rows)==len(expected),(len(rows),len(expected))
 keys=[k for k in expected[0] if k not in ignore]
 differences=[]
 for i,(x,y) in enumerate(zip(rows,expected),1):
  for k in keys:
   if norm(x.get(k,''))!=norm(y.get(k,'')):
    # Only permit unavoidable last-bit Python f64 arithmetic spelling in derived values.
    derived=k in ['explicit_mean_fr_hz','approx_mean_fr_hz','event_ratio_from_counts','event_reduction_pct']
    if derived and abs(float(x[k])-float(y[k]))<=1e-12:continue
    differences.append({'row':i,'key':k,'actual':x.get(k),'expected':y.get(k)})
 return {'rows':len(rows),'fields':len(keys),'differences':differences,'pass':not differences}
rounded=read_csv(a.archive/'original/metrics-rounded.csv')
diag=read_csv(a.archive/'diagnostics/diagnostic-results-exact.csv')
primary=read_csv(a.archive/'diagnostics/primary-comparison-exact.csv')
assert len(rounded)==72 and len(diag)==111 and len(primary)==24
extracted_diag=[]
for variant in ['original_instrumented','raw_sum','kappa_only']:
 extracted_diag+=extract_diag(a.archive/'diagnostics'/variant/'logs/closure-complete.log',variant)
report={'scope':'Independent parser and CSV comparison; no Rust execution, no archived files modified. Numeric printed values must match exactly; only derived Python f64 calculations allow absolute 1e-12. Source-path metadata excluded from numeric comparisons.',
 'archive_log_reconstruction':{'rounded':compare(extract_rounded(a.archive/'original/logs/phase3.log'),rounded),'diagnostic':compare(extracted_diag,diag),'primary':compare([r for r in extracted_diag if r['label'] in PRIMARY],primary)},
 'rounded_sections':dict(collections.Counter(r['section'] for r in rounded)),
 'diagnostic_variant_counts':dict(collections.Counter(r['variant'] for r in diag)),
 'duplicated_calibration_center_count':sum(r['label']=='gfe=2.50_gfi=0.40' for r in diag),
 'diagnostic_blank_event_ratio':sum(r['event_ratio']=='' for r in diag)}
if a.fresh_evidence:
 report['fresh_comparison']={n:compare(read_csv(a.fresh_evidence/f),exp) for n,f,exp in [('rounded','original/metrics-rounded.csv',rounded),('diagnostic','diagnostics/diagnostic-results-exact.csv',diag),('primary','diagnostics/primary-comparison-exact.csv',primary)]}
if a.fresh_run_dir:
 fresh=a.fresh_run_dir; tables=fresh/'tables'; runs=fresh/'runs'
 fr=read_csv(tables/'metrics-rounded.csv');fd=read_csv(tables/'diagnostic-results-exact.csv');fp=read_csv(tables/'primary-comparison-exact.csv')
 fresh_diags=[]
 for variant in ['original_instrumented','raw_sum','kappa_only']:
  fresh_diags+=extract_diag(runs/variant/'logs/phase3_benchmarks.log',variant)
 report['fresh_log_reconstruction']={'rounded':compare(extract_rounded(runs/'original/logs/phase3_benchmarks.log'),fr),'diagnostic':compare(fresh_diags,fd),'primary':compare([r for r in fresh_diags if r['label'] in PRIMARY],fp)}
 report['fresh_comparison']={'rounded':compare(fr,rounded),'diagnostic':compare(fd,diag),'primary':compare(fp,primary)}
report['pass']=all(x['pass'] for group in [report['archive_log_reconstruction'],report.get('fresh_comparison',{}),report.get('fresh_log_reconstruction',{})] for x in group.values())
a.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));assert report['pass']
