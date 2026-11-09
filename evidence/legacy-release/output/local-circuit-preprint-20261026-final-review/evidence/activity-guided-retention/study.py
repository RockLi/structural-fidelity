#!/usr/bin/env python3
"""Prospectively locked, equal-budget coactivity-guided structural retention."""
from pathlib import Path
import argparse, collections, csv, datetime, hashlib, json, platform, random
import shutil, subprocess, sys, time
import numpy as np

ROOT = Path(__file__).resolve().parent
PROBES = ['train', 'spatial', 'temporal', 'spatiotemporal']
POLICIES = ['random', 'mean', 'coactivity', 'shuffled']
COMPILER = ['rustup', 'run', '1.98.1', 'rustc']
BLOCKS, BANK_SIZE, SHUFFLES = 10, 64, 32

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def save(p, x): Path(p).write_text(json.dumps(x, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def table(p, rows):
    with Path(p).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def edges(p): return np.loadtxt(p,delimiter=',',skiprows=1,dtype=np.int64)
def write_edges(p,e):
    with Path(p).open('w') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['arm','source','target','weight_bits','delay']);w.writerows(e)
def check_files(lock):
    for name,digest in load(ROOT/lock)['files'].items(): assert sha(ROOT/name)==digest,name
def command(label,args):
    t=time.monotonic();log=ROOT/'logs'/f'{label}.log'
    with log.open('w') as f:
        f.write(json.dumps(list(map(str,args)))+'\n');f.flush()
        result=subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    with (ROOT/'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label,command=list(map(str,args)),returncode=result.returncode,elapsed_seconds=time.monotonic()-t,log=str(log.relative_to(ROOT))))+'\n')
    assert result.returncode==0,str(log)

def prepare():
    assert not (ROOT/'design-lock.json').exists()
    for d in ['events','graphs','runs','technical','logs','build','analysis']: (ROOT/d).mkdir(exist_ok=True)
    assert not list((ROOT/'runs').glob('*'))
    assert all(sha(ROOT/k)==v for k,v in load(ROOT/'inherited-inputs-sha256.json').items())
    e=edges(ROOT/'inherited/original.csv');assert e.shape==(2845,5)
    budgets=[2*(int(np.count_nonzero(e[:,0]==a))//20) for a in range(4)]
    mask0=list(range(0,100,5));mask1=sorted(random.Random(97001).sample(range(100),20))
    assert len(mask1)==20 and mask1!=mask0
    bits=int(np.array([150],dtype=np.float32).view(np.uint32)[0])
    event_info={}
    for probe in PROBES:
        mask=mask1 if probe in ['spatial','spatiotemporal'] else mask0
        slots=list(range(40))+list(range(80,120)) if probe in ['temporal','spatiotemporal'] else list(range(80))
        rows=[dict(slot=t,target=k,amplitude_bits=bits) for t in slots for k in mask]
        table(ROOT/'events'/f'{probe}.csv',rows)
        event_info[probe]=dict(targets=mask,active_slots=slots,event_count=len(rows),amplitude=150,total_amplitude=240000,event_sha256=sha(ROOT/'events'/f'{probe}.csv'))
    protocol=dict(
        title='Equal-budget coactivity-guided preservation of identified adjacency under input changes',
        written_utc=now(),status='Prospectively fixed exploratory follow-up after prior experiments; not a public preregistration',
        scientific_question='Does selecting less activity-disruptive statistically matched rewiring using one reference input improve closed-loop fidelity under held-out inputs?',
        family='One existing homogeneous E/I block-random original, seed 99; 125 chunks, 100 synchronized copies per chunk',
        chunks=125,units_per_chunk=100,steps=300,dt_ms=0.1,edges=2845,
        kernel='Frozen source, canonical explicit routing, same dormant/refractory semantics; no model repair or proxy',
        budget=dict(definition='Number of original adjacency pairs removed in each arm; all edges retained in rewired graph',formula='2*floor(M_arm/20)',arm_order=['EE','EI','IE','II'],removed_by_arm=budgets,removed_total=sum(budgets),retained_original_pairs=len(e)-sum(budgets),same_edge_storage=True,no_runtime_or_compression_claim=True),
        candidate_pool=dict(blocks=BLOCKS,candidates_per_block=BANK_SIZE,seed_formula='980000 + 1000*block + candidate',proposal_cap_per_arm=200000,algorithm='Independent from original. Within arm select two unused original rows without replacement, same weight bits/delay; require distinct source/target, no loops or duplicate current pairs, and no new pair in ORIGINAL adjacency. After each accepted target swap mark both rows used. Stop at exact per-arm missing-original-pair budget.',sampling='Conditional monotone first-legal-swap construction; no uniform random-graph/null/mixing claim',stable_tie_break='Smallest candidate index'),
        selection=dict(policies=POLICIES,shared_bank=True,random_index_seed_formula='990000 + block',random_index='random.Random(seed).randrange(64)',training_activity='inherited/training-original.npz state_bits[:, :, 0]/100, source slots 0..297 inclusive (298 columns), corresponding to recurrent arrival n+2 within 300 slots',weights='Separate excitatory and inhibitory source matrices W^q[target,source]; no E/I cancellation',
            mean='J_mean = L sum_q ||DeltaW^q mu||_2^2; mu is source temporal mean, L=298',
            coactivity='J_coactivity = sum_q ||DeltaW^q S||_F^2; uncentered zero-lag second-order coactivity, invariant under a common time permutation; not temporal ordering or a learned memory',
            shuffled='J_shuffled = mean over 32 independent per-source time permutations of J_coactivity; one shared set of permutations per block for all candidates; preserves each source spike-count distribution, destroys across-source alignment',
            shuffle_seed_formula='1000000 + block',shuffle_rng='numpy Generator(PCG64), repeat order then source index order, permutation(L)',shuffle_repetitions=SHUFFLES,
            analytic_shuffle_diagnostic='L sum_q ||DeltaW^q mu||^2 + sum_q,j ||DeltaW^q[:,j]||^2 C_jj, C=(S-mu)(S-mu)^T. Diagnostic only; never selects.',
            score_scope='Full DeltaW, including interference between simultaneous swaps; no rank truncation; 64 scores per policy except uniform random',
            overlap='Keep all policy memberships; simulate unique graph bytes once per input; do not replace overlapping selections'),
        inputs=event_info,spatial_mask_seed=97001,mask_overlap=len(set(mask0)&set(mask1)),
        heldout=['spatial','temporal','spatiotemporal'],heldout_design='2x2 mask/waveform design with train as one cell; three held-out conditions, not three independent networks. Split input ends at 12 ms rather than 8 ms, shortening post-input observation.',
        primary=dict(metric='Identified raw-slot spike L1 normalized by same-input original total spike count',aggregation='Within block equal-weight mean of three held-out errors, then paired coactivity minus random; report mean, median, full range and win/tie/loss counts across 10 blocks',required_comparisons=['coactivity-random','coactivity-mean','coactivity-shuffled'],sign_tolerance=1e-12,zero_reference_spikes='Normalized errors undefined; retain and report, do not replace the input',per_input='All training and individual held-out results must also be reported; no selection of most favorable input',success_interpretation='Training score improvement is selection-induced, not evidence. Consistent closed-loop improvement over random and mean/shuffled is needed to attribute a transfer benefit to across-source coactivity; mixed/negative results retained without protocol revision'),
        secondary=['1 ms binned identified spike L1','identified cumulative-count L1 and cumulative/raw ratio Rcount (undefined if raw zero)','van Rossum tau=1 ms full exponential tail, representative spikes, normalized by same-input original spike count','absolute and original-channel-standardized RMS of V/gE/gI','spike equality and first differing slot','source edge visits and queue events only as diagnostics, not runtime'],
        statistics='Conditional paired descriptive results across 10 graph-search banks, one original graph and one alternate mask. No p-values or generalization intervals; do not pool held-out inputs or duplicate selectors as independent samples. All conditions and selectors reported.',
        gates=['Design/code/source/events locked before any new simulation','All 640 candidates, scores, selections and hashes locked before any held-out simulation','Original train CSV driver identical to archived counts and all ten state fields','Within-chunk identity and finite fields for all runs','Independent graph/score/metric audit','Fresh-directory regenerate, rebuild, rerun all unique selected graphs and compare state payload/count CSV and derived numerical outputs'],
        maximum_scientific_runs=164,limitations=['No biological calibration or larger-model claim','No inferred necessity of specific individual edges; selection optimizes a complete candidate graph','Graph-search effort and training trajectory storage are offline costs, not savings','No adaptation of masks, budgets, pool size, score, horizon or metric after outcomes'])
    save(ROOT/'protocol.json',protocol)
    required=['study.py','reproduce.py','analyze.py','plot.py','audit.py','experiment.rs','DRIVER.txt']
    assert all((ROOT/n).exists() for n in required),required
    paths=[p for d in ['source','inherited','events'] for p in (ROOT/d).rglob('*') if p.is_file()]
    paths+=[ROOT/n for n in required+['protocol.json','inherited-inputs-sha256.json']]
    save(ROOT/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),compiler=subprocess.check_output(COMPILER+['--version','--verbose'],text=True)))
    save(ROOT/'design-lock.json',dict(locked_utc=now(),scientific_runs_started=False,files={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}))
    print('DESIGN LOCKED before any new simulation.',flush=True)

def audit_graph(original,e,budgets):
    assert e.shape==original.shape and np.array_equal(e[:,[0,1,3,4]],original[:,[0,1,3,4]])
    old=set(map(tuple,original[:,1:3]));pairs=set(map(tuple,e[:,1:3]));assert len(pairs)==len(e)
    assert np.all(e[:,1]!=e[:,2]) and np.all((e[:,1]>=100)*2+(e[:,2]>=100)==e[:,0])
    missing=[]
    for a in range(4):
        orig=original[original[:,0]==a];new=e[e[:,0]==a]
        for c in (1,2): assert collections.Counter(map(tuple,orig[:,[c,3]]))==collections.Counter(map(tuple,new[:,[c,3]]))
        missing.append(len(set(map(tuple,orig[:,1:3]))-set(map(tuple,new[:,1:3]))))
    assert missing==budgets and len(old-pairs)==len(pairs-old)==sum(budgets)
    return dict(removed_by_arm=missing,removed_total=sum(missing),per_node_per_arm_degrees_strengths_weight_multisets_exact=True,source_rows_weights_delays_exact=True,no_loops_or_parallel_pairs=True)

def candidate(original,seed,budgets):
    e=original.copy();rng=random.Random(seed);old=set(map(tuple,e[:,1:3]));present=old.copy();details=[]
    for a in range(4):
        available=np.flatnonzero(original[:,0]==a).tolist();accepted=0
        for attempt in range(1,200001):
            i,j=rng.sample(available,2);u,v=map(int,e[i,1:3]);x,y=map(int,e[j,1:3])
            if u==x or v==y or u==y or x==v or (u,y) in old or (x,v) in old or (u,y) in present or (x,v) in present:continue
            if not np.array_equal(e[i,3:5],e[j,3:5]):continue
            present.remove((u,v));present.remove((x,y));present.add((u,y));present.add((x,v))
            e[i,2],e[j,2]=y,v;available.remove(i);available.remove(j);accepted+=2
            if accepted==budgets[a]: break
        assert accepted==budgets[a],f'Failed fixed cap: seed={seed},arm={a}; stop, no replacement seed'
        details.append(dict(arm=a,removed=accepted,proposals=attempt))
    return e,details

def matrices(e):
    out=np.zeros((2,125,125),dtype=np.float64)
    weight=np.ascontiguousarray(e[:,3],dtype=np.uint32).view(np.float32).astype(np.float64)
    out[(e[:,1]>=100).astype(int),e[:,2],e[:,1]]=weight
    return out

def select():
    check_files('design-lock.json');assert not (ROOT/'selection-lock.json').exists()
    assert not list((ROOT/'runs').glob('*')) and not list((ROOT/'graphs').glob('*'))
    p=load(ROOT/'protocol.json');original=edges(ROOT/'inherited/original.csv');budgets=p['budget']['removed_by_arm']
    write_edges(ROOT/'graphs/original.csv',original);W=matrices(original)
    with np.load(ROOT/'inherited/training-original.npz') as z: S=z['state_bits'][:298,:,0].T.astype(np.float64)/100.
    assert S.shape==(125,298);mu=S.mean(axis=1);C=(S-mu[:,None])@(S-mu[:,None]).T;G=S@S.T
    allrows=[];selected=[];audits=[]
    for b in range(BLOCKS):
        rng=np.random.Generator(np.random.PCG64(1000000+b));Gshuffle=np.zeros((125,125))
        for rep in range(SHUFFLES):
            shuffled=np.stack([S[j,rng.permutation(S.shape[1])] for j in range(125)])
            Gshuffle+=shuffled@shuffled.T
        Gshuffle/=SHUFFLES;rows=[]
        for k in range(BANK_SIZE):
            seed=980000+1000*b+k;name=f'b{b:02d}_c{k:02d}';e,details=candidate(original,seed,budgets)
            audit=audit_graph(original,e,budgets);write_edges(ROOT/'graphs'/f'{name}.csv',e);D=matrices(e)-W
            jm=float(298*np.sum((D@mu)**2));jc=float(np.sum((D@G)*D));js=float(np.sum((D@Gshuffle)*D));je=jm+float(np.sum(D*D*np.diag(C)[None,None,:]))
            assert min(jm,jc,js,je)>=0 and all(np.isfinite([jm,jc,js,je]))
            row=dict(block=b,candidate=k,graph=name,seed=seed,J_mean=jm,J_coactivity=jc,J_shuffled=js,J_shuffle_expectation=je);rows.append(row)
            audits.append(dict(graph=name,seed=seed,swaps=details,graph_sha256=sha(ROOT/'graphs'/f'{name}.csv'),**audit))
        allrows.extend(rows)
        indices=dict(random=random.Random(990000+b).randrange(BANK_SIZE),mean=min(range(BANK_SIZE),key=lambda k:(rows[k]['J_mean'],k)),coactivity=min(range(BANK_SIZE),key=lambda k:(rows[k]['J_coactivity'],k)),shuffled=min(range(BANK_SIZE),key=lambda k:(rows[k]['J_shuffled'],k)))
        for policy,k in indices.items(): selected.append(dict(policy=policy,**rows[k]))
        print(f'Candidate bank {b+1}/{BLOCKS} selected; no new simulation.',flush=True)
    # Alias exact duplicate graph bytes across the complete bank before simulation.
    canonical={};aliases={}
    for row in allrows:
        h=sha(ROOT/'graphs'/f'{row["graph"]}.csv');aliases[row['graph']]=canonical.setdefault(h,row['graph'])
    table(ROOT/'candidates.csv',allrows);save(ROOT/'selection.json',selected);save(ROOT/'graph-audit.json',audits);save(ROOT/'graph-aliases.json',aliases)
    unique=sorted(set(aliases[r['graph']] for r in selected));save(ROOT/'planned-runs.json',[dict(graph=g,probe=probe,stem=f'{g}__{probe}') for g in ['original']+unique for probe in PROBES])
    paths=list((ROOT/'graphs').glob('*.csv'))+[ROOT/n for n in ['design-lock.json','candidates.csv','selection.json','graph-audit.json','graph-aliases.json','planned-runs.json']]
    save(ROOT/'selection-lock.json',dict(locked_utc=now(),scientific_runs_started=False,unique_selected_graphs=len(unique),scientific_runs=4*(1+len(unique)),files={str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}))
    print(f'SELECTION LOCKED: {len(unique)} unique selected graphs; {4*(1+len(unique))} runs.',flush=True)

def simulate(record,folder='runs'):
    prefix=ROOT/folder/record['stem']
    command(record['stem'],['build/experiment','simulate',ROOT/'graphs'/f'{record["graph"]}.csv',ROOT/'events'/f'{record["probe"]}.csv',prefix])
    bits=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(300,125,10)
    np.savez_compressed(prefix.with_suffix('.npz'),state_bits=bits)
    with np.load(prefix.with_suffix('.npz')) as z: assert np.array_equal(bits,z['state_bits'])
    prefix.with_suffix('.bin').unlink()
    return dict(record,npz_sha256=sha(prefix.with_suffix('.npz')),csv_sha256=sha(prefix.with_suffix('.csv')),json_sha256=sha(prefix.with_suffix('.json')))

def run():
    check_files('design-lock.json');check_files('selection-lock.json');assert not list((ROOT/'runs').glob('*'))
    command('build-library',COMPILER+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','source/src/lib.rs','-o','build/libnext_brain.rlib'])
    command('build-driver',COMPILER+['--edition=2024','-C','opt-level=3','experiment.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/experiment'])
    command('initialization',['build/experiment','check-initialization'])
    save(ROOT/'run-start.json',dict(started_utc=now(),design_lock_sha256=sha(ROOT/'design-lock.json'),selection_lock_sha256=sha(ROOT/'selection-lock.json')))
    records=[];planned=load(ROOT/'planned-runs.json')
    assert planned[0]['stem']=='original__train'
    for i,rec in enumerate(planned):
        result=simulate(rec);records.append(result)
        if i==0:
            with np.load(ROOT/'runs/original__train.npz') as a,np.load(ROOT/'inherited/training-original.npz') as b: assert np.array_equal(a['state_bits'],b['state_bits'])
            assert sha(ROOT/'runs/original__train.csv')==sha(ROOT/'inherited/training-original.csv')
            save(ROOT/'training-bridge.json',dict(status='pass',all_ten_fields_and_counts_identical=True,checked_utc=now()))
        if (i+1)%4==0: print(f'Runs {i+1}/{len(planned)}',flush=True)
    technical=simulate(dict(graph='original',probe='train',stem='repeat_original__train'),folder='technical')
    with np.load(ROOT/'technical/repeat_original__train.npz') as a,np.load(ROOT/'runs/original__train.npz') as b: assert np.array_equal(a['state_bits'],b['state_bits'])
    assert technical['csv_sha256']==records[0]['csv_sha256']
    save(ROOT/'run-complete.json',dict(completed_utc=now(),records=records,technical_repeat=technical,scientific_runs=len(records),policy_input_evaluations=160,originals=4))
    print(f'COMPLETE: {len(records)} scientific runs + one technical repeat.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','select','run']);a=p.parse_args();globals()[a.action]()
