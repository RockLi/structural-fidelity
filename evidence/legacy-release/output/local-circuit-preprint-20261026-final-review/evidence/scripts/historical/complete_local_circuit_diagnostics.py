from pathlib import Path
import shutil,subprocess,time,json,difflib,hashlib
base=Path('/tmp/local-circuit-repro-diagnostics');source=Path('/tmp/local-circuit-repro-current')
# Instrumented original is copied from raw diagnostic, restoring the original dynamics.
original=base/'original_instrumented';original.mkdir(exist_ok=True)
for name in ['Cargo.toml','Cargo.lock','src','tests']:
 p=base/'raw_sum'/name
 if p.is_dir():shutil.copytree(p,original/name,dirs_exist_ok=True)
 else:shutil.copy2(p,original/name)
shutil.copy2(source/'src/experiment/lpu_index.rs',original/'src/experiment/lpu_index.rs')
records=[]
for variant in ['original_instrumented','raw_sum','kappa_only']:
 out=base/variant
 for d in ['bin','logs','docs/phase3']: (out/d).mkdir(parents=True,exist_ok=True)
 p=out/'tests/phase3_benchmarks.rs';text=p.read_text()
 # Detailed audit for E4/E5; no test-network or numerical changes.
 for marker,label in [('                println!(\n                    "[Stateful E4/{label}]','label'),('            println!(\n                "[Stateful E5]','"E5"')]:
  assert marker in text
  audit='''                println!("[DIAGNOSTIC_E45] label={} psth_r={:.9} fr_delta={:.9} explicit_events={} approx_events={} explicit_spikes={} approx_spikes={} mismatch_steps={} max_step_spike_delta={}", LABEL, cmp_st.psth_correlation, cmp_st.mean_fr_delta_pct, rec_exp.total_events(), res_st.record.total_events(), rec_exp.steps.iter().map(|s|s.total_spikes as u64).sum::<u64>(), res_st.record.steps.iter().map(|s|s.total_spikes as u64).sum::<u64>(), rec_exp.steps.iter().zip(&res_st.record.steps).filter(|(a,b)|a.total_spikes!=b.total_spikes).count(), rec_exp.steps.iter().zip(&res_st.record.steps).map(|(a,b)|a.total_spikes.abs_diff(b.total_spikes)).max().unwrap_or(0));
'''.replace('LABEL',label)
  text=text.replace(marker,audit+marker)
 if variant=='kappa_only':
  before='''            assert!(
                (dyn_bh_st.peak_freq_hz - 39.0).abs() <= 2.0,
                "Boundary-Heavy Stateful PSD must recover ~39 Hz gamma peak, got {:.1}Hz",
                dyn_bh_st.peak_freq_hz
            );'''
  after='''            println!("[DIAGNOSTIC CONTINUATION] Original PSD assertion disabled after its documented failure; unit-invalid reported peak={:.1}", dyn_bh_st.peak_freq_hz);'''
  assert text.count(before)==1;text=text.replace(before,after)
 p.write_text(text)
 diff=''
 for name in ['src/experiment/lpu_index.rs','src/experiment/frontier.rs','tests/phase3_benchmarks.rs']:
  diff+=''.join(difflib.unified_diff((source/name).read_text().splitlines(True),(out/name).read_text().splitlines(True),fromfile='source/'+name,tofile=variant+'/'+name))
 (out/'diagnostic-complete.patch').write_text(diff)
 cmds=[['rustc','--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','src/lib.rs','-o','bin/libnext_brain.rlib'],['rustc','--edition=2024','-C','opt-level=3','--test','tests/phase3_benchmarks.rs','--extern','next_brain=bin/libnext_brain.rlib','-o','bin/phase3_tests'],['bin/phase3_tests','bench_stateful_proxy_closure_and_psd','--nocapture','--test-threads=1']]
 for i,cmd in enumerate(cmds):
  t=time.monotonic();logname='closure-complete.log' if i==2 else f'build-complete-{i}.log'
  with (out/'logs'/logname).open('w') as log:
   log.write('$ '+' '.join(cmd)+'\n');log.flush();r=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT)
  record={'variant':variant,'command':cmd,'elapsed_s':time.monotonic()-t,'returncode':r.returncode,'log':str(out/'logs'/logname)}
  records.append(record);print(json.dumps(record),flush=True)
  if r.returncode:break
 (out/'source-sha256-complete.json').write_text(json.dumps({str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for dirname in ['src','tests'] for p in sorted((out/dirname).rglob('*.rs'))},indent=2)+'\n')
 (base/'run-results-complete.json').write_text(json.dumps(records,indent=2)+'\n')
