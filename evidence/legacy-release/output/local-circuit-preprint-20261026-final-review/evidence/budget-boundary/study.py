#!/usr/bin/env python3
"""Locked small-budget nested follow-up, training gate before migration."""
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

BUDGETS = {'p01':[14,6,6,2], 'p02':[30,12,12,2]}
FULL_BUDGET = [146,60,64,12]


def prepare():
    assert not (ROOT/'design-lock.json').exists()
    for d in ['events','graphs','runs','technical','logs','build','analysis-train','analysis-migration']:
        (ROOT/d).mkdir(exist_ok=True)
    assert not list((ROOT/'runs').glob('*'))
    assert all(sha(ROOT/k)==v for k,v in load(ROOT/'inherited-inputs-sha256.json').items())
    original=edges(ROOT/'inherited/original.csv');assert original.shape==(2845,5)
    counts=[int(np.count_nonzero(original[:,0]==a)) for a in range(4)]
    # Round target count to nearest even pair, ties upward, minimum one pair.
    derived={key:[max(2,2*int(np.floor(frac*m/2+.5))) for m in counts]
             for key,frac in [('p01',.01),('p02',.02)]}
    assert derived==BUDGETS,(counts,derived)
    p=load(ROOT/'inherited/prior-protocol.json')
    event_info={}
    for probe,info in p['inputs'].items():
        bits=int(np.array([info['amplitude']],dtype=np.float32).view(np.uint32)[0])
        rows=[dict(slot=t,target=k,amplitude_bits=bits) for t in info['active_slots'] for k in info['targets']]
        table(ROOT/'events'/f'{probe}.csv',rows)
        assert sha(ROOT/'events'/f'{probe}.csv')==info['event_sha256']
        event_info[probe]=info
    protocol=dict(
        title='Nested small-budget training gate for activity-guided structural selection',
        written_utc=now(),status='Prospectively fixed follow-up after inspecting the 9.91% experiment; not a public preregistration or independent replication',
        scientific_question='At two smaller matched adjacency-change budgets, does frozen-source coactivity selection consistently improve closed-loop training-input fidelity over random and activity-ablated controls?',
        chunks=125,units_per_chunk=100,steps=300,dt_ms=.1,edges=2845,
        family=p['family'],kernel=p['kernel'],arm_edge_counts=counts,
        budgets={key:dict(removed_by_arm=v,removed_total=sum(v),fraction=sum(v)/2845,
                         retained_original_pairs=2845-sum(v)) for key,v in BUDGETS.items()},
        budget_definition='Number of original adjacency pairs replaced; round each arm target to the nearest even count (half upward), minimum two. All 2845 edges and states remain.',
        nesting='For each old seed, regenerate the COMPLETE old 9.91% four-arm proposal sequence with one RNG exactly as before; retain the first requested accepted pairs within each arm. Do not early-stop the RNG at small budgets. Verify complete graph bytes against all 640 archived full-budget hashes.',
        candidate_pool=p['candidate_pool'],selection={**p['selection'],
            'mean_evaluation':'With direct=DeltaW@S in float64, J_mean=sum(direct.sum(time)**2)/L. Same mathematical score, but sum source-time residuals before dividing to preserve exact zero. Historical 9.91% scores/selections unchanged.',
            'coactivity_evaluation':'Direct sum((DeltaW @ S)**2) in float64 to preserve exact zero residuals; no Gram-trace cancellation. Exact numerical minimum; ties by candidate index; no tolerance-based score ties.'},
        prior_exposure='Same original, old candidate proposal sequences and reference training activity are known. Prior migration masks and waveforms are also known. Smaller graph prefixes have not been simulated before this lock; this is a budget-conditional follow-up, not a new cohort.',
        inputs=event_info,training_probe='train',migration_probes=PROBES[1:],
        migration_design='Only after the joint training gate passes: apply all already selected small-budget graphs to the three fixed prior-known test inputs. These are conditional known-input transfer checks, not fresh held-out discovery. No old migration state file is read.',
        primary=dict(metric='Identified raw-slot spike L1 normalized by same-input original total count',
                     training='Within each budget paired coactivity minus random across ten shared candidate banks.',
                     conditional_migration='Per budget, equal-weight mean over all three prior-known migration inputs within each block, then coactivity minus each comparator; report every input.',
                     required_comparisons=['random','mean','shuffled'],sign_tolerance=1e-12,
                     zero_reference_spikes='Normalized errors null; gate fails if any required endpoint is undefined.'),
        continuation_gate=dict(epsilon=1e-12,both_budgets_required=True,required_complete_pairs=10,
            random=dict(mean_less_than=-1e-12,median_less_than=-1e-12,minimum_strict_wins=7),
            specificity=dict(comparators=['mean','shuffled'],mean_at_most=1e-12,wins_at_least_losses=True),
            interpretation='Pragmatic precommitted continuation criterion, not a significance test, confidence bound or evidence of universal superiority.',
            failure='If either budget fails any criterion, do not run ANY migration condition; report all training outcomes and stop this experimental branch. Do not change threshold, budget, score, input or metric.'),
        secondary=p['secondary'],statistics=p['statistics'],
        stage_order=['design/code/source/events locked','all 1280 graph prefixes and 80 selector memberships locked','training only','independent training/gate audit','migration only if joint gate passes','fresh-directory reproduction of the authorized completed stage'],
        maximum_training_scientific_runs=81,maximum_migration_scientific_runs=243,
        limitations=p['limitations']+['Prior negative 9.91% outcomes motivated these budgets. Training passage is selected and cannot serve as independent confirmation.']
    )
    save(ROOT/'protocol.json',protocol)
    required=['study.py','reproduce.py','analyze.py','plot.py','audit.py','README.txt','experiment.rs','DRIVER.txt']
    assert all((ROOT/n).exists() for n in required)
    paths=[x for d in ['source','inherited','events'] for x in (ROOT/d).rglob('*') if x.is_file()]
    paths += [ROOT/n for n in required+['protocol.json','inherited-inputs-sha256.json']]
    save(ROOT/'environment.json',dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),compiler=subprocess.check_output(COMPILER+['--version','--verbose'],text=True)))
    save(ROOT/'design-lock.json',dict(locked_utc=now(),scientific_runs_started=False,
         files={str(x.relative_to(ROOT)):sha(x) for x in sorted(set(paths))}))
    print('DESIGN LOCKED; no new simulation.',flush=True)


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

def candidate_prefixes(original,seed):
    full=original.copy();small={key:original.copy() for key in BUDGETS}
    rng=random.Random(seed);old=set(map(tuple,full[:,1:3]));present=old.copy();details=[]
    for arm in range(4):
        available=np.flatnonzero(original[:,0]==arm).tolist();accepted=0;swaps=[]
        for attempt in range(1,200001):
            i,j=rng.sample(available,2);u,v=map(int,full[i,1:3]);x,y=map(int,full[j,1:3])
            if u==x or v==y or u==y or x==v or (u,y) in old or (x,v) in old or (u,y) in present or (x,v) in present:continue
            if not np.array_equal(full[i,3:5],full[j,3:5]):continue
            present.remove((u,v));present.remove((x,y));present.add((u,y));present.add((x,v))
            full[i,2],full[j,2]=y,v;available.remove(i);available.remove(j);accepted+=2
            swaps.append(dict(rows=[i,j],original_targets=[v,y],new_targets=[y,v],proposal=attempt))
            for key,budget in BUDGETS.items():
                if accepted<=budget[arm]:small[key][i,2],small[key][j,2]=y,v
            if accepted==FULL_BUDGET[arm]:break
        assert accepted==FULL_BUDGET[arm],f'Failed fixed proposal cap seed={seed},arm={arm}; no replacement'
        details.append(dict(arm=arm,proposals=attempt,swaps=swaps))
    return full,small,details


def matrices(e):
    out=np.zeros((2,125,125),dtype=np.float64)
    weight=np.ascontiguousarray(e[:,3],dtype=np.uint32).view(np.float32).astype(np.float64)
    out[(e[:,1]>=100).astype(int),e[:,2],e[:,1]]=weight
    return out

def select():
    check_files('design-lock.json');assert not (ROOT/'selection-lock.json').exists()
    assert not list((ROOT/'runs').glob('*')) and not list((ROOT/'graphs').glob('*'))
    original=edges(ROOT/'inherited/original.csv');write_edges(ROOT/'graphs/original.csv',original)
    archived=load(ROOT/'inherited/prior-full-graph-sha256.json');assert len(archived)==640
    W=matrices(original)
    with np.load(ROOT/'inherited/training-original.npz') as z:S=z['state_bits'][:298,:,0].T.astype(np.float64)/100.
    assert S.shape==(125,298);mu=S.mean(axis=1);C=(S-mu[:,None])@(S-mu[:,None]).T;G=S@S.T
    allrows=[];selected=[];audits=[];prefix_records=[]
    for block in range(BLOCKS):
        rng=np.random.Generator(np.random.PCG64(1000000+block));Gs=np.zeros((125,125))
        for rep in range(SHUFFLES):
            ss=np.stack([S[j,rng.permutation(298)] for j in range(125)]);Gs+=ss@ss.T
        Gs/=SHUFFLES;banks={key:[] for key in BUDGETS}
        for k in range(BANK_SIZE):
            seed=980000+1000*block+k;oldname=f'b{block:02d}_c{k:02d}'
            full,prefixes,details=candidate_prefixes(original,seed)
            # Serialize identically in memory: no archived held-out trajectories or full graph files are read.
            import io
            s=io.StringIO();w=csv.writer(s,lineterminator='\n');w.writerow(['arm','source','target','weight_bits','delay']);w.writerows(full)
            fullhash=hashlib.sha256(s.getvalue().encode()).hexdigest();assert fullhash==archived[oldname],oldname
            audit_graph(original,full,FULL_BUDGET)
            prefix_records.append(dict(block=block,candidate=k,seed=seed,prior_graph=oldname,full_sha256=fullhash,sequence=details))
            for key,e in prefixes.items():
                name=f'{key}_{oldname}';audit=audit_graph(original,e,BUDGETS[key]);write_edges(ROOT/'graphs'/f'{name}.csv',e);D=matrices(e)-W
                direct=D@S
                jm=float(np.sum(direct.sum(axis=2)**2)/298);jc=float(np.sum(direct**2));js=float(np.sum((D@Gs)*D));je=jm+float(np.sum(D*D*np.diag(C)[None,None,:]))
                assert min(jm,jc,js,je)>=0 and all(np.isfinite([jm,jc,js,je]))
                row=dict(budget=key,block=block,candidate=k,graph=name,seed=seed,J_mean=jm,J_coactivity=jc,J_shuffled=js,J_shuffle_expectation=je)
                banks[key].append(row);allrows.append(row)
                audits.append(dict(budget=key,graph=name,graph_sha256=sha(ROOT/'graphs'/f'{name}.csv'),**audit))
            changed=[set(np.flatnonzero(prefixes[key][:,2]!=original[:,2])) for key in BUDGETS]
            assert changed[0]<changed[1]
        for key,rows in banks.items():
            indices=dict(random=random.Random(990000+block).randrange(BANK_SIZE),
                mean=min(range(64),key=lambda k:(rows[k]['J_mean'],k)),
                coactivity=min(range(64),key=lambda k:(rows[k]['J_coactivity'],k)),
                shuffled=min(range(64),key=lambda k:(rows[k]['J_shuffled'],k)))
            for policy,k in indices.items():selected.append(dict(policy=policy,**rows[k]))
        print(f'Nested bank {block+1}/10 selected; no new simulation.',flush=True)
    allrows.sort(key=lambda r:(r['budget'],r['block'],r['candidate']))
    selected.sort(key=lambda r:(r['budget'],r['block'],POLICIES.index(r['policy'])))
    canonical={};aliases={}
    for row in allrows:
        h=sha(ROOT/'graphs'/f'{row["graph"]}.csv');aliases[row['graph']]=canonical.setdefault(h,row['graph'])
    table(ROOT/'candidates.csv',allrows);save(ROOT/'selection.json',selected)
    save(ROOT/'graph-audit.json',audits);save(ROOT/'prefix-sequences.json',prefix_records);save(ROOT/'graph-aliases.json',aliases)
    unique=sorted(set(aliases[r['graph']] for r in selected))
    for stage,probes in [('train',['train']),('migration',PROBES[1:])]:
        save(ROOT/f'planned-{stage}.json',[dict(graph=g,probe=probe,stem=f'{g}__{probe}') for g in ['original']+unique for probe in probes])
    paths=list((ROOT/'graphs').glob('*.csv'))+[ROOT/n for n in ['design-lock.json','candidates.csv','selection.json','graph-audit.json','prefix-sequences.json','graph-aliases.json','planned-train.json','planned-migration.json']]
    save(ROOT/'selection-lock.json',dict(locked_utc=now(),scientific_runs_started=False,
         unique_selected_graphs=len(unique),maximum_training_runs=1+len(unique),
         files={str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}))
    print(f'SELECTION LOCKED: {len(unique)} unique selected graphs; training plan {1+len(unique)} runs.',flush=True)


def simulate(record,folder='runs'):
    prefix=ROOT/folder/record['stem']
    command(record['stem'],['build/experiment','simulate',ROOT/'graphs'/f'{record["graph"]}.csv',ROOT/'events'/f'{record["probe"]}.csv',prefix])
    bits=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(300,125,10)
    np.savez_compressed(prefix.with_suffix('.npz'),state_bits=bits)
    with np.load(prefix.with_suffix('.npz')) as z: assert np.array_equal(bits,z['state_bits'])
    prefix.with_suffix('.bin').unlink()
    return dict(record,npz_sha256=sha(prefix.with_suffix('.npz')),csv_sha256=sha(prefix.with_suffix('.csv')),json_sha256=sha(prefix.with_suffix('.json')))

def compile_driver():
    command('build-library',COMPILER+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','source/src/lib.rs','-o','build/libnext_brain.rlib'])
    command('build-driver',COMPILER+['--edition=2024','-C','opt-level=3','experiment.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/experiment'])
    command('initialization',['build/experiment','check-initialization'])


def run_stage(stage):
    check_files('design-lock.json');check_files('selection-lock.json')
    assert not (ROOT/f'run-{stage}-complete.json').exists()
    if stage=='train':
        assert not list((ROOT/'runs').glob('*'));compile_driver()
    else:
        gate=load(ROOT/'gate.json')
        assert gate['proceed_migration'] is True,'Joint training gate failed: migration is prohibited'
        assert gate==load(ROOT/'analysis-train/gate.json')
        assert sha(ROOT/'analysis-train/per_policy.csv')==gate['training_per_policy_sha256']
        audited=load(ROOT/'audit-train.json')
        assert audited['status']=='pass' and audited['gate_verified'] is True
        assert audited['gate_sha256']==sha(ROOT/'gate.json')
        assert all(sha(ROOT/name)==digest for name,digest in audited['files'].items()),'Audited training inputs changed'
        assert (ROOT/'run-train-complete.json').exists()
        if not (ROOT/'build/experiment').exists():compile_driver()
    planned=load(ROOT/f'planned-{stage}.json');records=[]
    assert not any((ROOT/'runs'/f'{r["stem"]}.npz').exists() for r in planned)
    save(ROOT/f'run-{stage}-start.json',dict(started_utc=now(),design_lock_sha256=sha(ROOT/'design-lock.json'),selection_lock_sha256=sha(ROOT/'selection-lock.json')))
    for i,rec in enumerate(planned):
        result=simulate(rec);records.append(result)
        if stage=='train' and i==0:
            assert rec['stem']=='original__train'
            with np.load(ROOT/'runs/original__train.npz') as a,np.load(ROOT/'inherited/training-original.npz') as b:assert np.array_equal(a['state_bits'],b['state_bits'])
            assert sha(ROOT/'runs/original__train.csv')==sha(ROOT/'inherited/training-original.csv')
            save(ROOT/'training-bridge.json',dict(status='pass',all_ten_fields_and_counts_identical=True,checked_utc=now()))
        if (i+1)%10==0:print(f'{stage} {i+1}/{len(planned)}',flush=True)
    extra={}
    if stage=='train':
        technical=simulate(dict(graph='original',probe='train',stem='repeat_original__train'),folder='technical')
        with np.load(ROOT/'technical/repeat_original__train.npz') as a,np.load(ROOT/'runs/original__train.npz') as b:assert np.array_equal(a['state_bits'],b['state_bits'])
        assert technical['csv_sha256']==records[0]['csv_sha256'];extra['technical_repeat']=technical
    save(ROOT/f'run-{stage}-complete.json',dict(completed_utc=now(),stage=stage,records=records,
         scientific_runs=len(records),policy_input_evaluations=80*(1 if stage=='train' else 3),**extra))
    if stage=='migration':
        save(ROOT/'migration-ledger.json',dict(status='completed',reason='Both training-budget gates passed and audited before migration',
            gate_sha256=sha(ROOT/'gate.json'),scientific_runs=len(records),prior_known_input_probes=PROBES[1:]))
    print(f'{stage} COMPLETE: {len(records)} scientific runs.',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','select','train','migration']);a=p.parse_args()
    if a.action in ['prepare','select']:globals()[a.action]()
    else:run_stage(a.action)
