#!/usr/bin/env python3
"""Extract manuscript tables exclusively from explicitly supplied fresh Rust logs.

No archived table is read. Repeated gain-grid center rows are intentionally kept.
The output directory must be new or empty, and source_log is relative to --source-root.
"""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import math
import re

VARIANTS = ('original_instrumented', 'raw_sum', 'kappa_only')
NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
PAIR = re.compile(r'(\w+)=(' + NUM + r')')
SECTION_COUNTS = {
    'bench_e1_50k_sustained':2, 'bench_e1_parameter_island':9,
    'bench_e3_boundary_heavy':2, 'bench_hetero_retention_budget':2,
    'bench_e1_medium_calibration':9, 'bench_multimotif_taxonomy_e3':4,
    'bench_retention_budget_curve_e3_hetero':5, 'stateful_closure_e1_50k':4,
    'stateful_single_results':6, 'stateful_retention_budget_curve_e3_hetero':5,
    'stateful_multimotif_taxonomy_e3':4, 'stateful_e1_medium_calibration':9,
    'stateful_e1_parameter_island':9, 'test_frontier_e2e':2,
}
PRIMARY = {'4ch+trace (pure)', '4ch+trace (hybrid)', '4ch+trace-strong-inh (11.2%)',
           '4ch+trace-strong-inh (homo, 22.8%)', 'stable', 'balanced', 'excitable', 'E5'}
EXACT_FIELDS = ['variant','benchmark','label','units','steps','dt_ms','duration_ms',
    'psth_r','fr_delta','explicit_events','approx_events','event_ratio_from_counts',
    'event_reduction_pct','explicit_spikes','approx_spikes','explicit_mean_fr_hz',
    'approx_mean_fr_hz','mismatch_steps','max_step_spike_delta','event_ratio','source_log','source_line']
INT_FIELDS = {'explicit_events','approx_events','explicit_spikes','approx_spikes',
              'mismatch_steps','max_step_spike_delta'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def fail(message): raise ValueError(message)

def check_completed(text, passed, ignored, path):
    summaries = re.findall(r'^test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;', text, re.M)
    if summaries != [(str(passed),'0',str(ignored))]:
        fail(f'{path}: expected one successful test summary ({passed} passed, {ignored} ignored); found {summaries}')

def rounded_rows(path, source_log):
    text=path.read_text()
    check_completed(text,19,1,path)
    result=[]
    section=None
    for line_number,line in enumerate(text.splitlines(),1):
        header=re.search(r'\[(?:Frontier|HybridCalibrationGrid): ([^]]+)\]',line)
        if header:
            section=header.group(1)
            if section not in SECTION_COUNTS: fail(f'Unrecognized section {section!r} at {path}:{line_number}')
            continue
        single=re.search(r'(\[Stateful (?:E3 Hetero|E3 Homo|E4/[^]]+|E5)\])',line)
        if single:
            label=single.group(1)
            row={'section':'stateful_single_results','label':label}
        elif section and line.startswith('  ') and 'psth_r=' in line and not line.lstrip().startswith('→'):
            label=line.split('psth_r=',1)[0].strip().removesuffix('→').strip()
            row={'section':section,'label':label}
        else:
            # Frontier/grid bodies are contiguous; unrelated diagnostics cannot enter a section.
            if not line.strip() or line.startswith('ok') or line.startswith('test '): section=None
            continue
        row.update({key:float(value) for key,value in PAIR.findall(line)})
        if not {'psth_r','fr_delta'} <= row.keys(): fail(f'Incomplete rounded row at {path}:{line_number}')
        gate=re.search(r'\b(GO|STOP)\s*$',line)
        if gate: row['test_gate']=gate.group(1)
        row.update(source=source_log,source_log=source_log,source_line=line_number)
        result.append(row)
    if Counter(row['section'] for row in result) != Counter(SECTION_COUNTS):
        fail(f'Rounded section counts differ: {Counter(row["section"] for row in result)}')
    if len({(r['section'],r['label']) for r in result}) != 72: fail('Duplicate rounded section/label')
    return result

def workload(label):
    if label in {'2ch','4ch-default','4ch+trace (pure)','4ch+trace (hybrid)'}:
        return 'E1 50k',50000,500
    if label=='4ch+trace-strong-inh (homo, 22.8%)': return 'E3 homogeneous',12500,300
    if label in {'stable','balanced','excitable'}: return 'E4 '+label,5000,200
    if label=='E5': return 'E5 perturbation',5000,300
    if label.startswith(('4ch+trace-strong','stateful_thr','Strong','Fast','Short')):
        return 'E3 heterogeneous',12500,200
    if re.fullmatch(r'gfe=\d+\.\d+_gfi=\d+\.\d+',label): return 'E1 medium calibration',12500,200
    fail(f'Unrecognized diagnostic workload label {label!r}')

def exact_rows(path, variant, source_log):
    text=path.read_text()
    check_completed(text,1,0,path)
    result=[]
    for line_number,line in enumerate(text.splitlines(),1):
        if '[DIAGNOSTIC]' not in line and '[DIAGNOSTIC_E45]' not in line: continue
        match=re.search(r'\[DIAGNOSTIC(?:_E45)?\] label=(.*?) psth_r=(.*)$',line)
        if not match: fail(f'Malformed diagnostic row at {path}:{line_number}')
        label=match.group(1)
        pairs=PAIR.findall('psth_r='+match.group(2))
        if len(dict(pairs))!=len(pairs): fail(f'Duplicate diagnostic fields at {path}:{line_number}')
        row={'variant':variant,'label':label,'source_log':source_log,'source_line':line_number}
        row.update({key:int(value) if key in INT_FIELDS else float(value) for key,value in pairs})
        required=INT_FIELDS|{'psth_r','fr_delta'}
        if '[DIAGNOSTIC_E45]' not in line: required|={'event_ratio'}
        if not required <= row.keys(): fail(f'Missing diagnostic field at {path}:{line_number}: {required-row.keys()}')
        if any(row[k]<0 for k in INT_FIELDS) or row['explicit_events']==0: fail('Invalid diagnostic integer counts')
        benchmark,units,steps=workload(label)
        row.update(benchmark=benchmark,units=units,steps=steps,dt_ms=.1,duration_ms=steps*.1)
        if row['mismatch_steps']>steps: fail('Mismatch count exceeds number of slots')
        row['event_ratio_from_counts']=row['approx_events']/row['explicit_events']
        row['event_reduction_pct']=100*(1-row['event_ratio_from_counts'])
        row['explicit_mean_fr_hz']=row['explicit_spikes']/(units*row['duration_ms']/1000)
        row['approx_mean_fr_hz']=row['approx_spikes']/(units*row['duration_ms']/1000)
        if any(isinstance(v,float) and not math.isfinite(v) for v in row.values()): fail('Non-finite metric')
        result.append(row)
    expected=Counter({'E1 50k':4,'E3 heterogeneous':10,'E3 homogeneous':1,
                      'E1 medium calibration':18,'E4 stable':1,'E4 balanced':1,'E4 excitable':1,'E5 perturbation':1})
    if Counter(r['benchmark'] for r in result)!=expected: fail(f'{variant}: incomplete diagnostic coverage')
    labels=Counter(r['label'] for r in result)
    if labels['gfe=2.50_gfi=0.40']!=2 or any(count!=1 for label,count in labels.items() if label!='gfe=2.50_gfi=0.40'):
        fail(f'{variant}: unexpected duplicate/missing label counts')
    return result

def write_table(out,name,rows,fields):
    save(out/(name+'.json'),rows)
    with (out/(name+'.csv')).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader();writer.writerows({key:value for key,value in row.items() if key in fields} for row in rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original-log',type=Path,required=True)
    p.add_argument('--variant-log',action='append',required=True,metavar='VARIANT=PATH')
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--source-root',type=Path,required=True,help='Root for portable relative source_log paths')
    args=p.parse_args()
    source_root=args.source_root.resolve(); original=args.original_log.resolve()
    variants={}
    for entry in args.variant_log:
        name,sep,path=entry.partition('=')
        if not sep or name not in VARIANTS or name in variants: p.error('Exactly one --variant-log for each of '+', '.join(VARIANTS))
        variants[name]=Path(path).resolve()
    if set(variants)!=set(VARIANTS): p.error('All three diagnostic variants are required')
    inputs={'original':original,**variants}
    if len(set(inputs.values()))!=4: p.error('Each mode must have its own input log')
    for path in inputs.values():
        if not path.is_file(): p.error(f'Input log missing: {path}')
        if not path.is_relative_to(source_root): p.error(f'Input outside --source-root: {path}')
    out=args.output_dir.resolve()
    if out.exists() and any(out.iterdir()): p.error('Output directory must be new or empty')
    relative=lambda path: str(path.relative_to(source_root))
    rounded=rounded_rows(original,relative(original))
    exact=[r for variant in VARIANTS for r in exact_rows(variants[variant],variant,relative(variants[variant]))]
    primary=[r for r in exact if r['label'] in PRIMARY]
    if len(rounded)!=72 or len(exact)!=111 or len(primary)!=24: fail('Unexpected extraction totals')
    out.mkdir(parents=True,exist_ok=True)
    # Match the existing plotted CSV schema; JSON additionally retains threshold and
    # pulse fields that were present in the log but not columns of that legacy CSV.
    rounded_fields=['section','label','psth_r','fr_delta','spike_ratio','ev_ratio','ret_e','ev_share',
        'gfe','gfi','exp','stateful','test_gate','source','source_log','source_line']
    write_table(out,'metrics-rounded',rounded,rounded_fields)
    write_table(out,'diagnostic-results-exact',exact,EXACT_FIELDS)
    write_table(out,'primary-comparison-exact',primary,EXACT_FIELDS)
    save(out/'extraction-validation.json',{'status':'pass','archived_data_fallback':False,
        'rows':{'metrics-rounded':len(rounded),'diagnostic-results-exact':len(exact),'primary-comparison-exact':len(primary)},
        'rounded_section_counts':dict(Counter(r['section'] for r in rounded)),
        'diagnostic_rows_per_variant':dict(Counter(r['variant'] for r in exact)),
        'repeated_gain_centers_preserved':True,'source_log_relative_to':str(source_root),
        'input_logs':{mode:{'path':relative(path),'sha256':sha(path)} for mode,path in inputs.items()},
        'extractor_sha256':sha(Path(__file__))})
    save(out/'output-sha256.json',{path.name:sha(path) for path in sorted(out.iterdir()) if path.is_file() and path.name!='output-sha256.json'})
    print(json.dumps({'status':'pass','output_dir':str(out),'rounded':72,'diagnostic':111,'primary':24}))

if __name__=='__main__':main()
