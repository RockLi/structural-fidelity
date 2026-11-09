#!/usr/bin/env python3
"""Archived trajectories -> regenerated CSVs -> figures -> current bilingual DOCX."""
from pathlib import Path
import argparse,subprocess,sys,shutil,json,hashlib,os,zipfile
R=Path(__file__).resolve().parent;M=R/'manuscript';E=R/'research/experiments'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,log):
 env=os.environ.copy();env.setdefault('MPLCONFIGDIR','/private/tmp/nextbrain-reproduce-mpl')
 with log.open('w') as f:subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
def main():
 q=argparse.ArgumentParser();q.add_argument('--output-dir',type=Path,required=True);q.add_argument('--simulation-python',default=sys.executable,help='Scientific Python with NumPy/Matplotlib; no simulation is run.');a=q.parse_args();out=a.output_dir.resolve();out.mkdir(exist_ok=False,parents=True);checks={}
 score=E/'score-factor-coverage-audit-20261108';dose=E/'paired-dose-composition-20261108'
 for name,src,script in [('score',score,'analyze_scores.py'),('dose',dose,'analyze.py')]:
  run([a.simulation_python,'-B',src/script,'--output-dir',out/name],out/(name+'.log'))
  for f in sorted((out/name).glob('*.csv')):
   key=name+'/'+f.name;checks[key]=sha(f)==sha(src/'results'/f.name);assert checks[key],key
  assert json.loads((out/name/'summary.json').read_text())==json.loads((src/'results/summary.json').read_text());checks[name+'/summary.json']=True
 run([a.simulation_python,'-B',R/'reanalyze_input.py','--output-dir',out/'input'],out/'input.log')
 figs=out/'figures';shutil.copytree(M/'figures',figs)
 run([a.simulation_python,'-B',M/'plot_input_controls_paper.py','--data-dir',out/'input','--output-dir',figs],out/'figure.log')
 checks['input-figure']=sha(figs/'input-controls-paper.png')==sha(M/'figures/input-controls-paper.png');assert checks['input-figure']
 for lang in ['en','zh']:
  run([sys.executable,'-B',M/'build_preprint.py',lang,'--score-audit-dir',out/'score','--dose-dir',out/'dose','--input-control-dir',out/'input','--figures-dir',figs,'--output-dir',out/'manuscript'],out/('build-'+lang+'.log'))
  with zipfile.ZipFile(M/f'local-circuit-aggregation-preprint-{lang}.docx') as a1,zipfile.ZipFile(out/'manuscript'/f'local-circuit-aggregation-preprint-{lang}.docx') as a2:
   parts=['word/document.xml']+[x for x in a1.namelist() if x.startswith('word/media/')];assert all(a1.read(x)==a2.read(x) for x in parts)
  checks['document-'+lang]=True
 report=dict(status='pass',mode='archived data reanalysis only',new_network_conditions=0,new_radius_queries=0,checks=checks,input_reanalysis=json.loads((out/'input/reanalysis.json').read_text()),documents_built_from_regenerated_csvs=True,source_sha256={str(p.relative_to(R)):sha(p) for p in [R/'reproduce_current.py',R/'reanalyze_input.py',M/'build_preprint.py',M/'revision_tables.py',M/'plot_input_controls_paper.py',M/'paper_en.py',M/'paper_zh.py']})
 (out/'reproduction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
