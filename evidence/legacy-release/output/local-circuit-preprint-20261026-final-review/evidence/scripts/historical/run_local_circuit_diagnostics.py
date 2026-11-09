from pathlib import Path
import shutil,hashlib,json,subprocess,time,difflib
source=Path('/tmp/local-circuit-repro-current')
base=Path('/tmp/local-circuit-repro-diagnostics')
base.mkdir(exist_ok=True)
records=[]
for variant in ['raw_sum','kappa_only']:
 out=base/variant
 out.mkdir(exist_ok=True)
 for name in ['Cargo.toml','Cargo.lock','src','tests']:
  p=source/name
  if p.is_dir(): shutil.copytree(p,out/name,dirs_exist_ok=True)
  else:shutil.copy2(p,out/name)
 for d in ['bin','logs','docs/phase3']: (out/d).mkdir(parents=True,exist_ok=True)
 p=out/'src/experiment/lpu_index.rs'; text=p.read_text()
 for channel in ['exc','inh']:
  before=f'let {channel}_drive = kappa_{channel} * filter_gain_{channel[0]} * raw_{channel};'
  after=f'let {channel}_drive = raw_{channel};' if variant=='raw_sum' else f'let {channel}_drive = kappa_{channel} * raw_{channel};'
  assert text.count(before)==1,(variant,before)
  text=text.replace(before,after)
 p.write_text(text)
 # Measurement instrumentation only: record exact integer event/spike counts and
 # the number of mismatching population spike-count bins in each paired run.
 p=out/'src/experiment/frontier.rs';text=p.read_text()
 begin=text.index('    pub fn from_runs(');end=text.index('    /// Compute a `FrontierPoint` from a hybrid',begin)
 part=text[begin:end]
 old='''        Self {
            label: label.into(),'''
 new='''        let label = label.into();
        let mismatched_steps = rec_explicit.steps.iter().zip(&rec_proxy.steps).filter(|(a,b)| a.total_spikes != b.total_spikes).count();
        let max_spike_count_delta = rec_explicit.steps.iter().zip(&rec_proxy.steps).map(|(a,b)| a.total_spikes.abs_diff(b.total_spikes)).max().unwrap_or(0);
        println!("[DIAGNOSTIC] label={} psth_r={:.9} fr_delta={:.9} event_ratio={:.9} explicit_events={} approx_events={} explicit_spikes={} approx_spikes={} mismatch_steps={} max_step_spike_delta={}", label, cmp.psth_correlation, cmp.mean_fr_delta_pct, event_ratio, explicit_events, proxy_events, explicit_spikes, proxy_spikes, mismatched_steps, max_spike_count_delta);
        Self {
            label,'''
 assert part.count(old)==1
 text=text[:begin]+part.replace(old,new)+text[end:];p.write_text(text)
 diff=''
 for name in ['src/experiment/lpu_index.rs','src/experiment/frontier.rs']:
  diff+=''.join(difflib.unified_diff((source/name).read_text().splitlines(True),(out/name).read_text().splitlines(True),fromfile='source/'+name,tofile=variant+'/'+name))
 (out/'diagnostic.patch').write_text(diff)
 cmds=[['rustc','--edition=2024','-C','opt-level=3','--crate-name','next_brain','--crate-type','lib','src/lib.rs','-o','bin/libnext_brain.rlib'],['rustc','--edition=2024','-C','opt-level=3','--test','tests/phase3_benchmarks.rs','--extern','next_brain=bin/libnext_brain.rlib','-o','bin/phase3_tests'],['bin/phase3_tests','bench_stateful_proxy_closure_and_psd','--nocapture','--test-threads=1']]
 for i,cmd in enumerate(cmds):
  t=time.monotonic();logname='closure.log' if i==2 else f'build-{i}.log'
  with (out/'logs'/logname).open('w') as log:
   log.write('$ '+' '.join(cmd)+'\n');log.flush()
   result=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT)
  record={'variant':variant,'command':cmd,'elapsed_s':time.monotonic()-t,'returncode':result.returncode,'log':str(out/'logs'/logname)}
  records.append(record);print(json.dumps(record),flush=True)
  if result.returncode:break
 manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((out/'src').rglob('*.rs'))}
 (out/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (base/'run-results.json').write_text(json.dumps(records,indent=2)+'\n')
