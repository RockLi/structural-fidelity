#!/usr/bin/env python3
"""Prepare, run, and verify a bounded synthetic-network rewiring experiment.

Use an environment with numpy. No network, Cargo downloads, or production edits.
Every stage refuses to overwrite completed evidence. See README.txt.
"""
import argparse
import collections
import csv
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time
import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
FAMILIES = ['homogeneous', 'heterogeneous']
PROBES = ['tonic', 'global_burst', 'focal_burst']
MODES = ['explicit', 'raw_sum', 'trace']
SEEDS = list(range(91001, 91020))
STEPS, CHUNKS, UNITS, WIDTH = 300, 125, 100, 10
COMPILER = ['rustup', 'run', '1.98.1', 'rustc']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
def load(p): return json.loads(Path(p).read_text())
def command(label, args):
    path = ROOT / 'logs' / (label + '.log')
    started = time.monotonic()
    with path.open('w') as out:
        out.write(json.dumps(args) + '\n'); out.flush()
        p = subprocess.run(args, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
    record = dict(label=label, command=list(map(str,args)), returncode=p.returncode,
                  elapsed_s=time.monotonic()-started, log=str(path.relative_to(ROOT)))
    with (ROOT/'commands.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
    if p.returncode: raise RuntimeError(f'Command failed: {path}')
    return record

def read_edges(p):
    with Path(p).open() as f: rows=list(csv.reader(f))
    assert rows[0] == ['arm','source','target','weight_bits','delay']
    return np.array([[int(x) for x in r] for r in rows[1:]], dtype=np.int64)
def write_edges(p, edges):
    with Path(p).open('w') as f:
        w=csv.writer(f,lineterminator='\n'); w.writerow(['arm','source','target','weight_bits','delay']); w.writerows(edges)
def weights(e): return np.ascontiguousarray(e[:,3],dtype=np.uint32).view(np.float32).astype(np.float64)

def graph_audit(original, e):
    assert original.shape == e.shape
    assert np.array_equal(original[:,[0,1,3,4]],e[:,[0,1,3,4]])
    pairs=list(map(tuple,e[:,1:3])); assert len(set(pairs)) == len(pairs)
    assert np.all(e[:,1] != e[:,2]) and np.all(e[:,4] == 1)
    assert np.all((e[:,1]>=100)*2+(e[:,2]>=100) == e[:,0])
    strict=True; drift=[]; arm_checks=[]
    for arm in range(4):
        a,b=original[original[:,0]==arm],e[e[:,0]==arm]
        for col in [1,2]: assert np.array_equal(np.bincount(a[:,col],minlength=CHUNKS),np.bincount(b[:,col],minlength=CHUNKS))
        outa=np.bincount(a[:,1],weights=weights(a),minlength=CHUNKS)
        outb=np.bincount(b[:,1],weights=weights(b),minlength=CHUNKS)
        ina=np.bincount(a[:,2],weights=weights(a),minlength=CHUNKS)
        inb=np.bincount(b[:,2],weights=weights(b),minlength=CHUNKS)
        assert np.array_equal(outa,outb)
        equal=bool(np.array_equal(ina,inb)); strict &= equal
        drift.append(dict(arm=arm, input_strength_l1_relative=float(np.abs(ina-inb).sum()/ina.sum()),
                          input_strength_max_absolute=float(np.abs(ina-inb).max())))
        arm_checks.append(dict(arm=arm,edges=len(a),in_degree_exact=True,out_degree_exact=True,
            out_weight_multisets_exact=True,in_strength_exact=equal,out_strength_exact=True))
    adj=np.zeros((CHUNKS,CHUNKS),dtype=np.int64); adj[e[:,1],e[:,2]]=1
    orig_pairs=set(map(tuple,original[:,1:3]))
    return dict(passed=True,edges=len(e),arm_checks=arm_checks,
        target_changed_fraction=float(np.mean(e[:,2]!=original[:,2])),
        original_adjacency_overlap_fraction=len(orig_pairs.intersection(pairs))/len(e),
        incoming_strength_exact=strict,incoming_strength_drift=drift,
        reciprocal_pairs=int(np.trace(adj@adj)//2),directed_triangles=int(np.trace(adj@adj@adj)//3),
        no_self_loops=True,no_parallel_pairs=True,delay_exact=True)

def rewire(original,seed):
    e=original.copy(); rng=random.Random(seed); records=[]
    for arm in range(4):
        ix=np.flatnonzero(e[:,0]==arm).tolist(); present=set(map(tuple,e[ix,1:3])); accepted=0
        # Fixed proposal count, including rejections, avoids state-dependent
        # stopping after a fixed number of successes. No uniform-mixing claim.
        for _ in range(100*len(ix)):
            i,j=rng.sample(ix,2); a,b=int(e[i,1]),int(e[i,2]); c,d=int(e[j,1]),int(e[j,2])
            if a==c or b==d or a==d or c==b or (a,d) in present or (c,b) in present: continue
            present.remove((a,b)); present.remove((c,d)); present.add((a,d)); present.add((c,b))
            e[i,2],e[j,2]=d,b; accepted+=1
        records.append(dict(arm=arm,proposals=100*len(ix),accepted=accepted))
    return e,records

def prepare(source):
    assert not (ROOT/'source').exists(), 'Existing prepared study is preserved'
    manifest_path=source.parent.parent/'source-sha256.json'
    # The supplied path is evidence/original/source.
    manifest_path=source.parent/'source-sha256.json'
    manifest=load(manifest_path)
    assert sha(manifest_path)=='9a266203cf86bbe43b201e7af53fab3131c9d89deddbb64d6181f30199a6e448'
    assert all(sha(source/k)==v for k,v in manifest.items())
    for name in ['source','build','logs','graphs','runs','analysis']: (ROOT/name).mkdir()
    for name in manifest:
        dst=ROOT/'source'/name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source/name,dst)
    save(ROOT/'frozen-source-sha256.json',manifest)
    save(ROOT/'environment.json',dict(created_utc=now(),python=sys.version,numpy=np.__version__,platform=platform.platform(),
        compiler=subprocess.check_output(COMPILER+['--version','--verbose'],text=True),source=str(source),
        source_manifest_sha256=sha(manifest_path),host_machine=platform.machine()))
    protocol=dict(title='Statistics-matched rewiring controls on frozen E3 synthetic chunk networks',
        status='prospectively fixed exploratory extension of previously inspected benchmarks; not independent preregistration',
        written_utc=now(),families=FAMILIES,original_graph_seeds=dict(homogeneous=99,heterogeneous=200),
        graph_scope='100 E and 25 I chunks, 100 identical units per chunk; chunk-level edges, not individual-neuron wiring',
        p=[0.15,0.25,0.25,0.20],w=[0.6,0.8,1.4,0.5],weight_spread=dict(homogeneous=0.0,heterogeneous=0.5),
        rewiring_seeds=SEEDS,proposals_per_arm_edge=100,independent_chains_start='same original graph',
        rewiring='directed target swaps within each projection arm; source, weight bits, delay and list row stay fixed; reject loops/duplicates',
        primary_null='homogeneous: exact per-node per-arm in/out degree, in/out strength, incoming/outgoing weight multisets, E/I identity, edge count, delay',
        secondary_null='heterogeneous: exact per-node per-arm in/out degree and source outgoing weight/delay multiset; target input strengths NOT fixed',
        not_preserved=['specific endpoints','reciprocal pairs','cycles','paths','spectra','spatial lengths','activity'],
        sampler_scope='No claim of uniform sampling or proven chain mixing; original graphs already sampled E/I random circuits, not biological motifs',
        dt_ms=0.1,steps=STEPS,duration_ms=30,methods=MODES,explicit_retention_fraction_for_proxies=0,
        trace_params=dict(gain_fast_exc=2.5,gain_fast_inh=0.4,other='frozen defaults, no fitting on either graph class'),
        raw_sum='copy of frozen step_stateful with two output expressions replaced by raw sums; states still allocated/updated',
        execution='canonical ascending source ID for explicit router, same numerical contract on every graph; additive observation driver',
        probes=dict(tonic=dict(strength=10,targets=list(range(100)),on_slots=300),
            global_burst=dict(strength=150,targets=list(range(100)),on_slots=80),
            focal_burst=dict(strength=150,targets=list(range(0,100,5)),on_slots=80)),
        probe_scope='tonic bridge; existing E5 80-slot pulse moved to E3; new prespecified focal target subset; no cross-probe causal attribution',
        time_windows=dict(burst_steps=[0,80],post_stimulus_steps=[80,300],rate_bin_steps=10),
        metrics=['population and chunk spike trajectories','mean E/I rates','1 ms bin absolute error','post-stimulus activity',
                 'voltage/conductance differences','recurrent queued messages','active-source edge visits'],
        primary_comparisons=['rewired explicit vs original explicit: wiring sensitivity',
            'each proxy vs its OWN explicit graph: approximation fidelity',
            'rewired minus original proxy-error: topology dependence of approximation error'],
        statistics='Report all 19 controls, median/range; no biological inference, no universal-equivalence claim, no topology p-value or selection of best graph',
        sample_unit='rewired graph conditional on one original graph per family and three deterministic probes; slots and duplicate within-chunk units are not independent samples',
        performance='Timing includes instrumentation and differs in counting overhead; no speedup claim. Queue saving is not state/edge compression.',
        technical_gates=['frozen source identity','historical E3 first-200-slot spike/event bridge','wrapper vs original harness',
            'graph invariants','explicit duplicate repeat','within-chunk equality','finite outputs','fresh-file metrics audit'],
        numerical_scope='raw equality is observed, not guaranteed in float32; deviations are reported rather than dropped',
        exclusions='No new FlyWire/MNIST simulation, no scientific parameter sweep, no preprint edits')
    save(ROOT/'protocol.json',protocol)
    # Copy a named raw-output ablation, leaving the original trace intact.
    p=ROOT/'source/src/experiment/lpu_index.rs'; old=p.read_text()
    start=old.index('    pub fn step_stateful('); end=old.index('    /// Inject the contents',start)
    method=old[start:end].replace('pub fn step_stateful(', 'pub fn step_raw_sum_control(',1)
    for src,dst in [('let exc_drive = kappa_exc * filter_gain_e * raw_exc;','let exc_drive = raw_exc;'),
                    ('let inh_drive = kappa_inh * filter_gain_i * raw_inh;','let inh_drive = raw_inh;')]:
        assert method.count(src)==1; method=method.replace(src,dst)
    new=old[:end]+'    // Additive raw-output control; other calculations intentionally retained.\n'+method+old[end:]
    p.write_text(new)
    patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/experiment/lpu_index.rs',tofile='b/src/experiment/lpu_index.rs'))
    p=ROOT/'source/src/connectivity/event_router.rs'; old=p.read_text()
    assert old.count('let spiking: Vec<')==1
    new=old.replace('let spiking: Vec<','let mut spiking: Vec<',1)
    marker='        // Inject events into target chunks.'; assert new.count(marker)==1
    new=new.replace(marker,'        spiking.sort_by_key(|(id, _)| id.0); // Canonical accumulation order.\n\n'+marker)
    p.write_text(new)
    patch+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/connectivity/event_router.rs',tofile='b/src/connectivity/event_router.rs'))
    (ROOT/'build.patch').write_text(patch)
    command('build-library',COMPILER+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib',
        'source/src/lib.rs','-o','build/libnext_brain.rlib'])
    command('build-driver',COMPILER+['--edition=2024','-C','opt-level=3','experiment.rs','--extern','next_brain=build/libnext_brain.rlib','-o','build/experiment'])
    command('technical-checks',['build/experiment','check'])
    # Sampler identity/repeatability and strength invariants are audited BEFORE
    # all graph-by-method scientific simulation, without selecting on outputs.
    graph_records=[]
    for family in FAMILIES:
        folder=ROOT/'graphs'/family; folder.mkdir()
        command('generate-'+family,['build/experiment','generate',family,str(folder/'original.csv')])
        original=read_edges(folder/'original.csv')
        a=graph_audit(original,original); a.update(family=family,graph='original',seed=None)
        graph_records.append(a)
        for seed in SEEDS:
            e,swaps=rewire(original,seed); name=f'r{seed}'; write_edges(folder/(name+'.csv'),e)
            a=graph_audit(original,e)
            if family=='homogeneous': assert a['incoming_strength_exact']
            assert a['target_changed_fraction']>0.5, 'Technical randomization failed; do not retry/select another seed'
            a.update(family=family,graph=name,seed=seed,swaps=swaps); graph_records.append(a)
        e2,sw2=rewire(original,SEEDS[0]); assert np.array_equal(e2,read_edges(folder/f'r{SEEDS[0]}.csv'))
    save(ROOT/'graph-audit.json',graph_records)
    paths=[ROOT/'protocol.json',ROOT/'experiment.rs',ROOT/'run_experiment.py',ROOT/'build.patch',ROOT/'graph-audit.json']
    paths+=sorted((ROOT/'source').rglob('*.rs'))+sorted((ROOT/'graphs').rglob('*.csv'))
    paths += [ROOT/'build/experiment',ROOT/'build/libnext_brain.rlib']
    save(ROOT/'experiment-lock.json',dict(locked_utc=now(),files={str(p.relative_to(ROOT)):sha(p) for p in paths},
        expected_runs=len(FAMILIES)*(len(SEEDS)+1)*len(PROBES)*len(MODES),scientific_runs_started=False))
    print('PREPARED: source, builds, historical bridge and graph invariants passed; experiment locked.',flush=True)

def check_lock():
    lock=load(ROOT/'experiment-lock.json')
    for name,digest in lock['files'].items(): assert sha(ROOT/name)==digest, name
    return lock

def run():
    lock=check_lock(); assert not (ROOT/'run-complete.json').exists()
    assert not list((ROOT/'runs').glob('*.npz')), 'Refuse partial rerun; preserve the run and use a new study directory'
    records=[]
    for family in FAMILIES:
        for graph_name in ['original']+[f'r{s}' for s in SEEDS]:
            for probe in PROBES:
                for mode in MODES:
                    stem=f'{family}__{graph_name}__{probe}__{mode}'; prefix=ROOT/'runs'/stem
                    command(stem,['build/experiment','simulate',str(ROOT/'graphs'/family/(graph_name+'.csv')),probe,mode,str(prefix)])
                    data=np.fromfile(prefix.with_suffix('.bin'),dtype='<u4').reshape(STEPS,CHUNKS,WIDTH)
                    np.savez_compressed(prefix.with_suffix('.npz'),state_bits=data)
                    with np.load(prefix.with_suffix('.npz')) as archive: assert np.array_equal(archive['state_bits'],data)
                    # Only this invocation's temporary raw serialization is removed.
                    prefix.with_suffix('.bin').unlink()
                    records.append(dict(family=family,graph=graph_name,probe=probe,mode=mode,stem=stem,
                        npz_sha256=sha(prefix.with_suffix('.npz')),csv_sha256=sha(prefix.with_suffix('.csv'))))
            print(f'{family}/{graph_name}: completed {len(records)}/{lock["expected_runs"]}',flush=True)
    assert len(records)==lock['expected_runs']; check_lock()
    save(ROOT/'run-complete.json',dict(completed_utc=now(),runs=records,status='pass',total_runs=len(records)))

def verify():
    check_lock(); complete=load(ROOT/'run-complete.json'); assert len(complete['runs'])==360
    for family in FAMILIES:
        base=read_edges(ROOT/'graphs'/family/'original.csv')
        for name in ['original']+[f'r{s}' for s in SEEDS]:
            audit=graph_audit(base,read_edges(ROOT/'graphs'/family/(name+'.csv')))
            if family=='homogeneous': assert audit['incoming_strength_exact']
    for r in complete['runs']:
        prefix=ROOT/'runs'/r['stem']; assert sha(prefix.with_suffix('.npz'))==r['npz_sha256']
        assert sha(prefix.with_suffix('.csv'))==r['csv_sha256']
        with np.load(prefix.with_suffix('.npz')) as z: a=z['state_bits']
        rows=np.loadtxt(prefix.with_suffix('.csv'),delimiter=',',skiprows=1,dtype=np.int64)
        assert a.shape==(STEPS,CHUNKS,WIDTH) and rows.shape==(STEPS,5)
        assert np.array_equal(rows[:,0],np.arange(STEPS))
        assert np.array_equal(a[:,:,0].sum(axis=1),rows[:,1])
        assert np.isfinite(np.ascontiguousarray(a[:,:,1:8]).view(np.float32)).all()
        assert set(np.unique(a[:,:,0])).issubset({0,100})
        edges=read_edges(ROOT/'graphs'/r['family']/(r['graph']+'.csv'))
        outdegree=np.bincount(edges[:,1],minlength=CHUNKS)
        visits=(a[:,:,0]>0)@outdegree
        assert np.array_equal(visits,rows[:,3])
        if r['mode']=='explicit': assert np.array_equal(visits,rows[:,2])
    save(ROOT/'validation.json',dict(status='pass',validated_utc=now(),all_360_runs_checked=True,
        source_and_graph_lock=True,topology_constraints=True,chunk_counts_and_finite_states=True,
        edge_visits_independently_recomputed=True,compressed_payloads_verified=True,
        scientific_scope='Conditional descriptive experiment; no general topology superiority or speedup claim'))
    print('VERIFIED: all 360 new simulations, saved state arrays, counts and graph constraints.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','run','verify'])
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    if args.stage=='prepare':
        assert args.source and args.source.is_dir(); prepare(args.source.resolve())
    elif args.stage=='run': run()
    else: verify()
