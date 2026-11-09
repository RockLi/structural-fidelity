#!/usr/bin/env python3
"""Run the complete frozen experiment-to-manuscript reproduction in a new directory.

Fresh logs are the only numerical input to extracted tables. Archived results are
used only for an explicit verification gate because manuscript prose is fixed.
This does not render or visually approve DOCX files, and does not package outputs.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback

MODES=('original','original_instrumented','raw_sum','kappa_only')
NON_NUMERICAL={'source','source_log','source_line','source_table','_provenance'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def save(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def normalized(value):
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k not in NON_NUMERICAL}
    if isinstance(value,list):return [normalized(v) for v in value]
    return value

def contains_reference(old,new,path='root'):
    if isinstance(old,dict):
        if not isinstance(new,dict):raise ValueError(f'{path}: expected an object')
        for key,value in old.items():
            if key not in new:raise ValueError(f'{path}: missing {key}')
            contains_reference(value,new[key],path+'.'+key)
    elif isinstance(old,list):
        if not isinstance(new,list) or len(old)!=len(new):raise ValueError(f'{path}: list length differs')
        for i,(a,b) in enumerate(zip(old,new)):contains_reference(a,b,f'{path}[{i}]')
    elif old!=new:raise ValueError(f'{path}: value differs ({old!r}, {new!r})')

def check_equal(reference_path,fresh_path,label,allow_additional_fields=False):
    old,new=read(reference_path),read(fresh_path)
    if allow_additional_fields:
        contains_reference(normalized(old),normalized(new))
    elif normalized(old)!=normalized(new):
        raise ValueError(f'{label}: fresh result differs from archived reference. Fixed manuscript numbers were not updated; inspect both JSON files.')
    return {'stage':label,'status':'pass','reference':str(reference_path),'reference_sha256':sha(reference_path),
            'fresh':str(fresh_path),'fresh_sha256':sha(fresh_path),'comparison':'All values exactly equal after excluding only provenance fields',
            'additional_object_fields_allowed':allow_additional_fields,
            'rows':len(new) if isinstance(new,list) else None}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True,help='New or empty output root; never use the extracted package itself')
    parser.add_argument('--toolchain',default='1.98.1',help='Explicit rustup toolchain used for every Rust build')
    parser.add_argument('--skip-docx',action='store_true',help='Run experiments, table verification and figures without Word generation')
    args=parser.parse_args()
    package=Path(__file__).resolve().parents[2]
    evidence=package/'evidence';scripts=evidence/'scripts'
    output=args.output_dir.resolve()
    if output==package or output.is_relative_to(package):parser.error('Use an output directory outside the package to preserve the source archive')
    if output.exists() and any(output.iterdir()):parser.error('Output directory must be new or empty')
    output.mkdir(parents=True,exist_ok=True)
    for folder in ['runs','tables','logs','figures','documents','builds']:(output/folder).mkdir()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(output/'builds/matplotlib-cache'))
    commands=[];checks=[]
    # Hash every input except delivered/generated binary documents, caches and the ZIP.
    inputs={str(p.relative_to(package)):sha(p) for p in sorted(package.rglob('*'))
        if p.is_file() and p.suffix not in {'.zip','.docx','.pyc'} and '__pycache__' not in p.parts
        and not p.name.startswith('~$')}
    save(output/'input-sha256.json',inputs)
    save(output/'environment.json',{'python':sys.version,'python_executable':sys.executable,
        'platform':platform.platform(),'rustup_toolchain':args.toolchain,'package_root':str(package),
        'output_root':str(output),'skip_docx':args.skip_docx,'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'archived_data_fallback':False,'archived_data_use':'Explicit verification reference only',
        'source_log_relative_to':str(output),'renderer_used':False})
    def run(label,command):
        log=output/'logs'/(label+'.log')
        print(f'Starting {label}',flush=True)
        start=time.monotonic()
        with log.open('w') as stream:
            stream.write('$ '+ ' '.join(command)+'\n');stream.flush()
            proc=subprocess.run(command,cwd=output,env=env,stdout=stream,stderr=subprocess.STDOUT)
        commands.append({'stage':label,'command':command,'cwd':str(output),'returncode':proc.returncode,
            'elapsed_s':time.monotonic()-start,'log':str(log.relative_to(output)),
            'environment_overrides':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','MPLCONFIGDIR']}})
        save(output/'commands.json',commands)
        print(json.dumps(commands[-1]),flush=True)
        if proc.returncode:raise RuntimeError(f'{label} failed; inspect {log}')
    def verify(reference,fresh,label,allow_additional_fields=False):
        checks.append(check_equal(reference,fresh,label,allow_additional_fields));save(output/'reference-verification.json',{'status':'pass','checks':checks})
    try:
        dependency_code = ('import importlib, importlib.metadata, json, pathlib, sys; '
            'names={"numpy":"numpy","matplotlib":"matplotlib"}; '
            'names.update({"docx":"python-docx"} if sys.argv[2]=="yes" else {}); '
            '[importlib.import_module(name) for name in names]; '
            'pathlib.Path(sys.argv[1]).write_text(json.dumps({dist:importlib.metadata.version(dist) for dist in names.values()},indent=2)+"\\n")')
        run('check-python-dependencies',[sys.executable,'-c',dependency_code,str(output/'python-dependencies.json'),
            'no' if args.skip_docx else 'yes'])
        for mode in MODES:
            run('reproduce-'+mode,[sys.executable,str(scripts/'reproduce.py'),'--mode',mode,
                '--toolchain',args.toolchain,'--work-dir',str(output/'runs'/mode)])
            results=read(output/'runs'/mode/'run-results.json')
            if not results or any(r['returncode']!=0 for r in results):raise ValueError(f'Incomplete run: {mode}')
        test_summaries=[]
        for stage in read(output/'runs/original/run-results.json'):
            if stage['stage'].startswith('build-'):continue
            log=output/'runs/original/logs'/(stage['stage']+'.log')
            summaries=re.findall(r'^test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;',log.read_text(),re.M)
            if len(summaries)!=1:raise ValueError(f'Expected one successful test summary in {log}')
            passed,failed,ignored=map(int,summaries[0])
            test_summaries.append({'target':stage['stage'],'passed':passed,'failed':failed,'ignored':ignored})
        test_totals={key:sum(r[key] for r in test_summaries) for key in ['passed','failed','ignored']}
        if test_totals!={'passed':86,'failed':0,'ignored':1}:raise ValueError(f'Unmodified test coverage differs: {test_totals}')
        save(output/'unmodified-test-summary.json',{'status':'pass','targets':test_summaries,'totals':test_totals})
        extraction=[sys.executable,str(scripts/'extract_results.py'),'--source-root',str(output),
            '--original-log',str(output/'runs/original/logs/phase3_benchmarks.log'),'--output-dir',str(output/'tables')]
        for mode in MODES[1:]:extraction+=['--variant-log',mode+'='+str(output/'runs'/mode/'logs/phase3_benchmarks.log')]
        run('extract-tables',extraction)
        for name,folder in [('metrics-rounded','original'),('diagnostic-results-exact','diagnostics'),('primary-comparison-exact','diagnostics')]:
            verify(evidence/folder/(name+'.json'),output/'tables'/(name+'.json'),'verify-'+name)
        run('reproduce-e3-zero',[sys.executable,str(scripts/'reproduce_e3_zero.py'),'--toolchain',args.toolchain,
            '--output-dir',str(output/'e3-zero'),'--work-dir',str(output/'builds/e3-zero'),
            '--reference-results',str(output/'tables/diagnostic-results-exact.json'),
            '--reference-rounded',str(output/'tables/metrics-rounded.json'),'--source-root',str(output)])
        verify(evidence/'e3-zero-retention/run/results-exact.json',output/'e3-zero/results-exact.json','verify-e3-zero')
        run('reproduce-execution-boundaries',[sys.executable,str(scripts/'reproduce_execution_boundaries.py'),
            '--toolchain',args.toolchain,'--output-dir',str(output/'execution-boundaries'),
            '--work-dir',str(output/'builds/execution-boundaries')])
        verify(evidence/'execution-boundaries/final-run/records.json',output/'execution-boundaries/records.json','verify-execution-boundaries')
        for name in ['e3-zero','execution-boundaries']:
            if read(output/name/'validation.json').get('status')!='pass':raise ValueError(f'{name}: validation not passed')
        run('plot-comparisons',[sys.executable,str(package/'plot_preprint.py'),'--data-dir',str(output/'tables'),
            '--e3-run-dir',str(output/'e3-zero'),'--output-dir',str(output/'figures'),
            '--metadata-path',str(output/'figure-data.json')])
        verify(package/'figure-data.json',output/'figure-data.json','verify-plotted-values',allow_additional_fields=True)
        run('plot-trajectories',[sys.executable,str(package/'plot_trajectory_figure.py'),'--run-dir',str(output/'e3-zero'),
            '--output-dir',str(output/'figures'),'--metadata-path',str(output/'trajectory-figure-data.json')])
        # The trajectory metadata contains input path keys, so verify its numeric content separately.
        old,new=read(package/'trajectory-figure-data.json'),read(output/'trajectory-figure-data.json')
        for key,value in old.items():
            if key not in {'sources','_provenance','scope'} and new.get(key)!=value:raise ValueError(f'Trajectory metadata changed: {key}')
        checks.append({'stage':'verify-trajectory-values','status':'pass','comparison':'Every preexisting non-source metadata field matches'})
        save(output/'reference-verification.json',{'status':'pass','checks':checks})
        figure_stems=['fig1_execution','fig2_e1','fig3_budget','fig4_edge_classes','fig5_calibration','fig6_e3_trajectories']
        required=[output/'figures'/(stem+suffix) for stem in figure_stems for suffix in ['.png','.pdf']]
        if not args.skip_docx:
            for language in ['en','zh']:
                run('build-document-'+language,[sys.executable,str(package/'build_preprint.py'),language,
                    '--data-dir',str(output/'tables'),'--boundary-run-dir',str(output/'execution-boundaries'),
                    '--figures-dir',str(output/'figures'),'--output-dir',str(output/'documents')])
                required.append(output/'documents'/f'local-circuit-aggregation-preprint-{language}.docx')
        for path in required:
            if not path.is_file() or path.stat().st_size==0:raise ValueError(f'Missing required output: {path}')
        current={name:sha(package/name) for name in inputs}
        if current!=inputs:raise ValueError('A package input changed during execution')
        report={'status':'pass','completed_stages':len(commands),'reference_checks':len(checks),
            'counts':{'metrics_rounded':72,'diagnostic_results':111,'primary_comparison':24,'e3_records':6,'boundary_cases':8},
            'unmodified_test_totals':test_totals,
            'primary_tables_extracted_from_fresh_logs':True,'e3_and_boundary_tables_generated_from_fresh_runs':True,
            'archive_used_only_for_reference_verification':True,
            'all_package_input_hashes_unchanged':True,'package_input_files':len(inputs),'docx_generated':not args.skip_docx,
            'docx_visual_qa':'Not performed by this driver; render and inspect before publication',
            'command_timings_are_performance_evidence':False,'completed_at_utc':datetime.now(timezone.utc).isoformat(),
            'deliverable_sha256':{str(path.relative_to(output)):sha(path) for path in required}}
        save(output/'pipeline-validation.json',report)
        # Binaries/build copies are logistical output, not evidence for publication; still hash them here.
        save(output/'output-sha256.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*'))
            if p.is_file() and p!=output/'output-sha256.json'})
        print(json.dumps(report,indent=2),flush=True)
    except Exception as error:
        save(output/'pipeline-validation.json',{'status':'fail','error':str(error),'completed_stages':len(commands),
             'fixed_manuscript_numbers_updated':False,'traceback':traceback.format_exc()})
        raise

if __name__=='__main__':main()
