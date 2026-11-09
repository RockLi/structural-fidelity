#!/usr/bin/env python3
"""Reproduce open-loop message-delivery boundary fixtures on frozen Rust code.

Usage: python3 evidence/scripts/reproduce_execution_boundaries.py --output-dir /tmp/boundary-results
Only the new output/build directories are written. No source patches are applied.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import tempfile
import time

MANIFEST_SHA = '9a266203cf86bbe43b201e7af53fab3131c9d89deddbb64d6181f30199a6e448'
FIELDS = ['v', 'recovery', 'ge', 'gi', 'gl', 'fe', 'fi']
CASES = {
    'positive_aligned': ('B1', 'Positive inputs grouped by target and arrival slot', 'control'),
    'heterogeneous_initial_aligned': ('B2', 'Correct grouping with heterogeneous unit initial voltages', 'control'),
    'zero_wakeup_dropped': ('B3', 'Zero-amplitude wake-up discarded', 'violation'),
    'zero_wakeup_preserved': ('B4', 'Zero-amplitude wake-up preserved', 'control'),
    'polarity_separate': ('B5', 'Excitatory and inhibitory inputs grouped separately', 'control'),
    'polarity_net_sum': ('B6', 'Excitatory and inhibitory inputs cancelled into one net sum', 'violation'),
    'arrival_slots_separate': ('B7', 'Different arrival slots grouped separately', 'control'),
    'arrival_slots_collapsed': ('B8', 'Later inhibitory input moved to the earlier arrival slot', 'violation'),
}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
def value(bits): return struct.unpack('!f', struct.pack('!I', int(bits)))[0]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--toolchain', default='1.98.1')
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parents[1]
    source = evidence/'original/source'
    manifest_path = evidence/'original/source-sha256.json'
    test_path = evidence/'execution-boundaries/tests/execution_boundaries.rs'
    assert sha(manifest_path) == MANIFEST_SHA, 'Frozen manifest identity changed'
    manifest = json.loads(manifest_path.read_text())
    def check_sources(root):
        observed = {name: sha(root/name) for name in manifest}
        assert observed == manifest, 'Frozen source differs'
        return observed
    check_sources(source)
    output = args.output_dir.resolve()
    assert not output.exists() or not any(output.iterdir()), 'Output must be new or empty'
    output.mkdir(parents=True, exist_ok=True)
    (output/'logs').mkdir()
    work = args.work_dir.resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix='execution-boundaries-', dir='/tmp'))
    assert not any(work.iterdir()) if work.exists() else True, 'Work directory must be empty'
    work.mkdir(parents=True, exist_ok=True)
    build = work/'source'
    shutil.copytree(source, build)
    (build/'bin').mkdir()
    shutil.copy2(test_path, build/'tests/execution_boundaries.rs')
    assert sha(build/'tests/execution_boundaries.rs') == sha(test_path)
    save(output/'compiled-source-sha256.json', dict(check_sources(build), **{'tests/execution_boundaries.rs': sha(test_path)}))
    compiler = ['rustup','run',args.toolchain,'rustc']
    version = subprocess.check_output(compiler+['--version','--verbose'], text=True)
    save(output/'provenance.json', {'compiler_command': compiler, 'compiler_version': version,
        'platform': platform.platform(), 'machine': platform.machine(), 'work_directory': str(work),
        'runner_sha256': sha(Path(__file__)), 'test_sha256': sha(test_path),
        'source_manifest_sha256': MANIFEST_SHA, 'frozen_files': len(manifest),
        'source_patches': [], 'command_timings_are_performance_evidence': False})
    protocol = {
        'scope':'Open-loop event-delivery fixtures using actual frozen Scheduler/Chunk; not E1/E3 validation, generalization, or a performance benchmark',
        'steps':12,'dt_ms':0.1,'duration_ms':1.2,'chunks':2,'units_per_chunk':4,
        'initial_status':'Explicitly set to Dormant before Scheduler::add_chunk; this overrides Chunk::new Active default',
        'initial_voltage':-65.0,'B2_initial_voltages_each_chunk':[-65.0,-32.0,0.0,29.0],
        'other_initial_unit_states_and_local_fields':0,'field_decay_tau_ms':10.0,
        'enqueue_slot':0,'slot_indexing':'Zero based; CSV slot n records state after Scheduler::step at input current_slot n',
        'event_tuple_order':['target_chunk','absolute_arrival_slot','signed_strength'],
        'reference_events':{
            'B1_B2':[[0,2,256],[0,2,512],[1,2,128],[1,2,256]],
            'B3_B4':[[0,2,0]],
            'B5_B6':[[0,2,256],[0,2,512],[0,2,-256],[0,2,-512]],
            'B7_B8':[[0,2,256],[0,2,512],[0,4,-128],[0,4,-128]]},
        'candidate_events':{
            'B1_B2':[[0,2,768],[1,2,384]],'B3':[],'B4':[[0,2,0]],
            'B5':[[0,2,-768],[0,2,768]],'B6':[[0,2,0]],
            'B7':[[0,2,768],[0,4,-256]],'B8':[[0,2,768],[0,2,-256],[0,4,0]]},
        'single_condition_violations':{
            'B3':'Drops event existence for a zero-amplitude wake-up',
            'B6':'Changes polarity grouping; retains the original arrival-slot wake marker. Subsequent activation differences are consequences of changed conductance states.',
            'B8':'Changes arrival time of inhibitory magnitude; retains destination arrival support {2,4} and channel magnitudes, using a zero wake marker at slot 4'},
        'event_count_scope':'All preloaded fixture messages, including wake markers; no recurrent router or external-drive classification',
        'comparison':'Every recorded f32 state compared by to_bits; max errors decoded from f32 bits. This is measured equality in these fixtures, not a floating-point theorem',
        'observed_state_fields':FIELDS+['spike_flag','refractory_until','post_step_status','stepped_this_slot','earliest_pending_arrival'],
        'not_compared_as_equal':'Queue event multiplicity, processed-message counters, wall-clock timings, and queue payload identity',
    }
    save(output/'protocol.json',protocol)
    commands = []
    def run(label, command, env=None):
        start = time.monotonic()
        with (output/'logs'/f'{label}.log').open('w') as log:
            log.write('$ '+ ' '.join(command)+'\n'); log.flush()
            result = subprocess.run(command,cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT)
        commands.append({'stage':label,'command':command,'cwd':str(build),'returncode':result.returncode,
            'elapsed_s':time.monotonic()-start,'log':f'logs/{label}.log',
            'environment_overrides': {'BOUNDARY_OUTPUT_DIR':str(output)} if env else {}})
        save(output/'commands.json',commands)
        print(json.dumps(commands[-1]),flush=True)
        if result.returncode: raise SystemExit(f'Failed: {output}/logs/{label}.log')
    run('build-library',compiler+['--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','src/lib.rs','-o','bin/libnext_brain.rlib'])
    run('build-test',compiler+['--edition=2024','-C','opt-level=3','--test','tests/execution_boundaries.rs','--extern','next_brain=bin/libnext_brain.rlib','-o','bin/execution_boundaries'])
    run('test',['bin/execution_boundaries','--exact','execution_boundaries','--nocapture','--test-threads=1'],dict(os.environ,BOUNDARY_OUTPUT_DIR=str(output)))
    records = []
    for meta in csv.DictReader((output/'case-metadata.csv').open()):
        name = meta['case']
        rows = list(csv.DictReader((output/'slots'/f'{name}.csv').open()))
        assert len(rows) == 12*2*4
        record = {k: (v == 'true' if k in ['expected_equal','heterogeneous_initial_voltages'] else int(v) if k != 'case' else v) for k,v in meta.items()}
        case_id,human_name,case_type = CASES[name]
        record.update({'case_id':case_id,'human_name':human_name,'case_type':case_type})
        record.update({'slots':12,'chunks':2,'units_per_chunk':4,'dt_ms':0.1,
            'dt_f32_bits':struct.unpack('!I',struct.pack('!f',0.1))[0], 'duration_ms':1.2,
            'enqueue_slot':0, 'slot_csv':f'slots/{name}.csv',
            'max_abs_error':{k:0.0 for k in FIELDS},
            'first_dynamical_divergence':None,'first_activation_divergence':None,
            'first_spike_divergence':None,'first_pending_slot_divergence':None})
        mismatched = {k:set() for k in ['dynamical','activation','spike','pending_slot']}
        for row in rows:
            where = {k:int(row[k]) for k in ['slot','chunk','unit']}
            state_diff = False
            for field in FIELDS:
                aa,bb = row[f'ref_{field}_bits'],row[f'test_{field}_bits']
                state_diff |= aa != bb
                record['max_abs_error'][field] = max(record['max_abs_error'][field],abs(value(aa)-value(bb)))
            spike_diff = row['ref_spike'] != row['test_spike']
            state_diff |= spike_diff or row['ref_refractory'] != row['test_refractory']
            activation_diff = any(row[f'ref_{k}'] != row[f'test_{k}'] for k in ['stepped','status'])
            pending_diff = row['ref_pending'] != row['test_pending']
            for kind,diff in [('dynamical',state_diff),('activation',activation_diff),('spike',spike_diff),('pending_slot',pending_diff)]:
                if diff:
                    mismatched[kind].add((where['slot'],where['chunk']))
                    if record[f'first_{kind}_divergence'] is None:
                        record[f'first_{kind}_divergence'] = where
        record['mismatched_slot_chunk_pairs'] = {k:len(v) for k,v in mismatched.items()}
        record['observed_bitwise_dynamical_equality'] = not mismatched['dynamical']
        record['observed_activation_equality'] = not mismatched['activation']
        record['observed_pending_slot_equality'] = not mismatched['pending_slot']
        equal = not any(mismatched.values())
        assert equal == record['expected_equal']
        assert sum(int(r['ref_spike']) for r in rows) == record['reference_spikes']
        assert sum(int(r['test_spike']) for r in rows) == record['candidate_spikes']
        record['validation'] = 'pass'
        records.append(record)
    assert len(records) == 8
    save(output/'records.json', records)
    summary_fields = ['case_id','case','human_name','case_type','reference_messages','candidate_messages',
        'reference_spikes','candidate_spikes','first_state_divergence_slot','first_activation_divergence_slot',
        'first_spike_divergence_slot','max_abs_v_error','max_abs_conductance_error','max_abs_field_error',
        'observed_bitwise_dynamical_equality','observed_activation_equality']
    with (output/'summary.csv').open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=summary_fields); writer.writeheader()
        for r in records:
            row = {k:r[k] for k in summary_fields if k in r}
            for dest,src in [('state','dynamical'),('activation','activation'),('spike','spike')]:
                first = r[f'first_{src}_divergence']
                row[f'first_{dest}_divergence_slot'] = first['slot'] if first else ''
            row['max_abs_v_error'] = r['max_abs_error']['v']
            row['max_abs_conductance_error'] = max(r['max_abs_error'][k] for k in ['ge','gi','gl'])
            row['max_abs_field_error'] = max(r['max_abs_error'][k] for k in ['fe','fi'])
            writer.writerow(row)
    assert all(r['reference_spikes'] > 0 for r in records if r['case_id'] in ['B1','B2','B7'])
    check_sources(source); check_sources(build)
    assert sha(manifest_path) == MANIFEST_SHA
    save(output/'validation.json', {'status':'pass','fixture_cases':8,
        'correct_condition_controls':5,'deliberate_condition_violations':3,
        'frozen_files_verified_unchanged':len(manifest),'compiled_frozen_files_verified_unchanged':len(manifest),
        'validation_scope':'Measured f32 bits for all unit state arrays, fields, spike flags and refractory deadlines; per-chunk stepped/status/earliest pending slot. Event multiplicity intentionally differs.',
        'no_new_recurrent_network_or_performance_claim':True})
    files = {str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'output-sha256.json'}
    save(output/'output-sha256.json',files)
    print(json.dumps({'status':'pass','cases':len(records),'output':str(output)}))

if __name__ == '__main__': main()
