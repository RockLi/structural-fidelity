#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json,hashlib
from PIL import Image, ImageChops
p=argparse.ArgumentParser();p.add_argument('--fresh-run-dir',type=Path,default=Path('/tmp/local-circuit-pipeline-revision/fresh-run'));p.add_argument('--archive',type=Path,default=Path('/Users/rock/workspace/next-brain.ai/next-brain.ai/output/local-circuit-preprint-20261022'));p.add_argument('--report',type=Path,default=Path('/tmp/local-circuit-pipeline-revision/independent-fresh-artifact-audit.json'));a=p.parse_args();F=a.fresh_run_dir;A=a.archive
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
rows=lambda p:list(csv.DictReader(p.open()))
checks={};ignored={'source','source_log','source_line','source_table','_provenance'}
def check_existing(old,new,path):
 if isinstance(old,dict):
  assert isinstance(new,dict),path
  for k,v in old.items():
   if k not in ignored:assert k in new,(path,k);check_existing(v,new[k],path+'/'+k)
 elif isinstance(old,list):
  assert isinstance(new,list) and len(old)==len(new),path
  for i,(x,y) in enumerate(zip(old,new)):check_existing(x,y,path+'/'+str(i))
 else:assert old==new,(path,old,new)
# Every row points to the correct fresh run and literal source line.
origin_counts={}
for name in ['metrics-rounded','diagnostic-results-exact','primary-comparison-exact']:
 data=rows(F/'tables'/(name+'.csv'))
 for x in data:
  mode='original' if name=='metrics-rounded' else x['variant'];expected='runs/'+mode+'/logs/phase3_benchmarks.log'
  assert x['source_log']==expected,(name,x['source_log']);source=F/expected
  line=source.read_text().splitlines()[int(x['source_line'])-1]
  assert x['label'] in line,(name,x['source_line'],x['label'])
 origin_counts[name]=len(data)
checks['fresh_table_source_paths_and_line_numbers']=origin_counts
for name,freshpath,oldpath in [
 ('e3_records',F/'e3-zero/results-exact.json',A/'evidence/e3-zero-retention/run/results-exact.json'),
 ('boundary_records',F/'execution-boundaries/records.json',A/'evidence/execution-boundaries/final-run/records.json')]:
 old,new=read(oldpath),read(freshpath);check_existing(old,new,name);checks[name]={'records':len(new),'all_existing_nonprovenance_values_identical':True}
for name,fd,od,expected in [('e3_slots',F/'e3-zero/slots',A/'evidence/e3-zero-retention/run/slots',6),('boundary_slots',F/'execution-boundaries/slots',A/'evidence/execution-boundaries/final-run/slots',8)]:
 oldfiles=sorted(od.glob('*.csv'));newfiles=sorted(fd.glob('*.csv'));assert len(oldfiles)==len(newfiles)==expected
 assert [p.name for p in oldfiles]==[p.name for p in newfiles]
 assert all(sha(x)==sha(y) for x,y in zip(oldfiles,newfiles)),name
 checks[name]={'csv_files':expected,'byte_identical_to_archive':True}
meta=read(F/'figure-data.json');check_existing(read(A/'figure-data.json'),meta,'figure-data')
provenance=meta['_provenance'];assert provenance['archived_data_fallback'] is False
paths=provenance['input_files'];assert len(paths)==3
for relative,expectedsha in paths.items():
 source=(F/relative).resolve();assert source.is_relative_to(F.resolve()),relative;assert sha(source)==expectedsha,relative
assert {(F/r).resolve() for r in paths}=={(F/'tables/metrics-rounded.csv').resolve(),(F/'tables/diagnostic-results-exact.csv').resolve(),(F/'e3-zero/results-exact.csv').resolve()}
checks['comparison_figure_data']={'all_old_values_identical':True,'fresh_input_hashes_valid':True,'input_paths':list(paths)}
tmeta=read(F/'trajectory-figure-data.json');old=read(A/'trajectory-figure-data.json')
for k,v in old.items():
 if k not in {'sources','scope','_provenance'}:assert tmeta[k]==v,k
for relative,h in tmeta['sources'].items():
 source=(F/relative).resolve();assert source.is_relative_to(F.resolve()),relative;assert sha(source)==h,relative
raw=rows(F/'e3-zero/slots/raw_sum-zero.csv');hist=rows(F/'e3-zero/slots/original_instrumented-zero.csv')
assert len(raw)==len(hist)==tmeta['slots']==200
assert [int(x['slot']) for x in raw]==list(range(1,201))
assert all((r['slot'],r['explicit_spikes'])==(h['slot'],h['explicit_spikes']) for r,h in zip(raw,hist))
assert all(r['explicit_spikes']==r['approx_spikes'] for r in raw)
diff=[int(r['approx_spikes'])-int(r['explicit_spikes']) for r in hist]
assert sum(x!=0 for x in diff)==tmeta['history_mismatched_slots']==146
assert max(map(abs,diff))==tmeta['history_max_absolute_slot_difference']==700
assert sum(int(r['explicit_spikes']) for r in raw)==tmeta['reference_spikes']==124500
assert sum(int(r['approx_spikes']) for r in hist)==tmeta['history_spikes']==121400
checks['trajectory_data']={'all_200_counts_rechecked':True,'all_input_hashes_fresh_and_valid':True,'history_mismatch':146}
imgs={}
for oldpath in sorted((A/'figures').glob('*.png')):
 fresh=F/'figures'/oldpath.name;im1=Image.open(oldpath).convert('RGB');im2=Image.open(fresh).convert('RGB')
 assert im1.size==im2.size,(oldpath.name,im1.size,im2.size)
 box=ImageChops.difference(im1,im2).getbbox()
 imgs[oldpath.name]={'dimensions':im1.size,'byte_identical':sha(oldpath)==sha(fresh),'pixel_identical':box is None,'different_bbox':box}
assert len(imgs)==6
checks['figure_pngs']=imgs
report={'status':'pass','scope':'Independent fresh log source-link, existing result/trajectory and figure-data comparison. No Rust rerun or archive modification. PNG pixel comparison is not itself new visual inspection.','checks':checks}
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
