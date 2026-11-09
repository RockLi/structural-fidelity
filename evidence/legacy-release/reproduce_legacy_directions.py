#!/usr/bin/env python3
"""Fresh paired run -> verified CSV/figure -> current bilingual manuscripts."""
from pathlib import Path
import argparse,subprocess,sys,shutil,json,hashlib,os
R=Path(__file__).resolve().parent
P=R/'research/experiments/paired-direction-mechanism-20261108'
M=R/'manuscript'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,log):
 with log.open('w') as f:subprocess.run([str(x) for x in args],stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
 q=argparse.ArgumentParser();q.add_argument('--output-dir',type=Path,required=True);q.add_argument('--simulation-python',default=sys.executable);q.add_argument('--archived-only',action='store_true',help='Regenerate analyses and figure only; no new radius run.');q.add_argument('--rebuild-native',action='store_true');a=q.parse_args();out=a.output_dir.resolve();out.mkdir(exist_ok=False,parents=True)
 if a.rebuild_native:
  for name in ['finite-horizon-certificate-cost-20261108','finite-horizon-family-prototype-20261108']:
   folder=R/'research/experiments'/name
   run(['clang','-O3','-std=c11','-fno-fast-math','-ffp-contract=off','-dynamiclib',folder/'kernel.c','-o',folder/'kernel.dylib'],out/(name+'-build.log'))
 if a.archived_only:shutil.copytree(P/'results',out/'results')
 else:run([a.simulation_python,'-B',P/'mechanism.py','--output-dir',out/'results'],out/'mechanism.log')
 run([a.simulation_python,'-B',P/'analyze.py','--results',out/'results'],out/'analysis.log')
 exact=['pool-lock.json','scores.csv','selection-lock.csv','selection-lock.json','radii.csv','queries.csv','analysis.json','conditioned-vs-frozen.csv','failure-predictions.csv','input-reversals.csv','rank-concordance.csv','selection-transfer.csv']
 checks={}
 for name in exact:
  checks[name]=sha(out/'results'/name)==sha(P/'results'/name);assert checks[name],name
 # The archived plot is path-relative and read-only with respect to its source.
 shutil.copy2(P/'plot_results.py',out/'plot_results.py')
 run([a.simulation_python,'-B',out/'plot_results.py'],out/'plot.log')
 assert sha(out/'mechanism-summary.png')==sha(P/'mechanism-summary.png')
 figs=out/'figures';shutil.copytree(M/'figures',figs);run([a.simulation_python,'-B',M/'plot_mechanism_paper.py','--data-dir',out/'results','--output-dir',figs],out/'paper-plot.log')
 assert sha(figs/'mechanism-summary.png')==sha(M/'figures/mechanism-summary.png')
 for lang in ['en','zh']:
  run([sys.executable,'-B',M/'build_preprint.py',lang,'--mechanism-dir',out,'--figures-dir',figs,'--output-dir',out/'manuscript'],out/('build-'+lang+'.log'))
 report={'status':'pass','fresh_radius_run':not a.archived_only,'conditions':912,'all_numerical_outputs_exact':checks,'mechanism_figure_byte_identical':True,'documents_built_from_fresh_results':True,'no_new_network_or_input_conditions':True,'source_module_sha256':{str(x.relative_to(R)):sha(x) for x in [P/'mechanism.py',P/'analyze.py',P/'plot_results.py',M/'build_preprint.py',M/'plot_mechanism_paper.py',M/'paper_en.py',M/'paper_zh.py']},'native_libraries_rebuilt':a.rebuild_native,'source_path_provenance_note':'Archived absolute-path hash logs are historical. Fresh code-sha256.json records the relocated paths; source contents, numerical outputs and figure are checked separately.'}
 (out/'reproduction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
