//! Controlled delivery fixtures against the unmodified frozen Scheduler/Chunk.
//! These are open-loop execution checks, not recurrent-network benchmarks.
use next_brain::core::chunk::{Chunk, ChunkId, ChunkStatus, DelayedEvent, GridCoord};
use next_brain::core::scheduler::Scheduler;
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::Write;
use std::path::Path;

const STEPS: u64 = 12;
const CHUNKS: u32 = 2;
const UNITS: usize = 4;

#[derive(Clone, Copy)]
struct Input { target: u32, arrival: u64, strength: f32 }
fn input(target: u32, arrival: u64, strength: f32) -> Input {
    Input { target, arrival, strength }
}

fn grouped(events: &[Input], preserve_zero: bool) -> Vec<Input> {
    let mut groups = BTreeMap::<(u32, u64, i8), f32>::new();
    let mut result = Vec::new();
    for e in events {
        if e.strength == 0.0 {
            if preserve_zero { result.push(*e); }
        } else {
            let sign = if e.strength > 0.0 { 1 } else { -1 };
            *groups.entry((e.target, e.arrival, sign)).or_default() += e.strength.abs();
        }
    }
    result.extend(groups.into_iter().map(|((target, arrival, sign), magnitude)|
        input(target, arrival, magnitude * sign as f32)));
    result
}

fn scheduler(heterogeneous: bool, events: &[Input]) -> Scheduler {
    let mut s = Scheduler::new(0.1);
    for id in 0..CHUNKS {
        let mut c = Chunk::new(ChunkId(id), GridCoord {x: id as i32, y: 0, z: 0}, UNITS, 10.0);
        c.status = ChunkStatus::Dormant;
        if heterogeneous { c.state.voltages = vec![-65.0, -32.0, 0.0, 29.0]; }
        s.add_chunk(c);
    }
    // Every event is enqueued at slot 0. Its arrival is an absolute scheduler slot.
    for e in events {
        s.inject_event(DelayedEvent { target_chunk: ChunkId(e.target),
            target_slot: e.arrival, signal_strength: e.strength });
    }
    s
}

fn status(c: &Chunk) -> &'static str {
    match c.status { ChunkStatus::Active => "active", ChunkStatus::Dormant => "dormant",
        ChunkStatus::PendingWakeUp {..} => "pending" }
}
fn pending(c: &Chunk) -> String {
    c.event_queue.next_wake_slot().map(|x| x.to_string()).unwrap_or_else(|| "none".into())
}
fn floats(c: &Chunk, i: usize) -> [f32; 7] {
    [c.state.voltages[i], c.state.recovery[i], c.state.g_local_exc[i],
     c.state.g_local_inh[i], c.state.g_long_range[i],
     c.context.local_exc_field, c.context.local_inh_field]
}

fn run_case(out: &Path, summary: &mut File, name: &str, expect_equal: bool,
            heterogeneous: bool, reference: &[Input], candidate: &[Input]) {
    let mut a = scheduler(heterogeneous, reference);
    let mut b = scheduler(heterogeneous, candidate);
    let mut csv = File::create(out.join("slots").join(format!("{name}.csv"))).unwrap();
    let mut header = vec!["case", "slot", "chunk", "unit", "ref_stepped", "test_stepped",
        "ref_status", "test_status", "ref_pending", "test_pending", "ref_spike", "test_spike",
        "ref_refractory", "test_refractory"].into_iter().map(str::to_owned).collect::<Vec<_>>();
    for field in ["v", "recovery", "ge", "gi", "gl", "fe", "fi"] {
        for prefix in ["ref", "test"] {
            header.push(format!("{prefix}_{field}"));
            header.push(format!("{prefix}_{field}_bits"));
        }
    }
    writeln!(csv, "{}", header.join(",")).unwrap();
    let mut mismatch = false;
    let (mut spikes_a, mut spikes_b, mut processed_a, mut processed_b) = (0u64, 0u64, 0u64, 0u64);
    for slot in 0..STEPS {
        let old_a = (0..CHUNKS).map(|id| a.chunks[&ChunkId(id)].metrics.active_step_count).collect::<Vec<_>>();
        let old_b = (0..CHUNKS).map(|id| b.chunks[&ChunkId(id)].metrics.active_step_count).collect::<Vec<_>>();
        let ma = a.step();
        let mb = b.step();
        spikes_a += ma.total_spikes as u64;
        spikes_b += mb.total_spikes as u64;
        processed_a += ma.event_count as u64;
        processed_b += mb.event_count as u64;
        for id in 0..CHUNKS {
            let ca = &a.chunks[&ChunkId(id)];
            let cb = &b.chunks[&ChunkId(id)];
            let sa = ca.metrics.active_step_count > old_a[id as usize];
            let sb = cb.metrics.active_step_count > old_b[id as usize];
            for i in 0..UNITS {
                let mut row = vec![name.into(), slot.to_string(), id.to_string(), i.to_string(),
                    (sa as u8).to_string(), (sb as u8).to_string(), status(ca).into(), status(cb).into(),
                    pending(ca), pending(cb), (ca.state.spike_flags[i] as u32).to_string(),
                    (cb.state.spike_flags[i] as u32).to_string(), ca.state.refractory_until[i].to_string(),
                    cb.state.refractory_until[i].to_string()];
                let fa = floats(ca, i); let fb = floats(cb, i);
                let same = fa.iter().zip(fb.iter()).all(|(x,y)| x.to_bits() == y.to_bits())
                    && ca.state.spike_flags[i] == cb.state.spike_flags[i]
                    && ca.state.refractory_until[i] == cb.state.refractory_until[i]
                    && sa == sb && status(ca) == status(cb) && pending(ca) == pending(cb);
                mismatch |= !same;
                for j in 0..fa.len() {
                    row.push(fa[j].to_string()); row.push(fa[j].to_bits().to_string());
                    row.push(fb[j].to_string()); row.push(fb[j].to_bits().to_string());
                }
                writeln!(csv, "{}", row.join(",")).unwrap();
            }
        }
    }
    writeln!(summary, "{name},{expect_equal},{heterogeneous},{},{},{spikes_a},{spikes_b},{processed_a},{processed_b}", reference.len(), candidate.len()).unwrap();
    assert_eq!(!mismatch, expect_equal, "unexpected fixture outcome: {name}");
    assert_eq!(processed_a as usize, reference.len());
    assert_eq!(processed_b as usize, candidate.len());
    println!("BOUNDARY {name}: expected_equal={expect_equal}, observed_equal={}, messages={}/{}", !mismatch, candidate.len(), reference.len());
}

#[test]
fn execution_boundaries() {
    let output = std::env::var("BOUNDARY_OUTPUT_DIR").expect("BOUNDARY_OUTPUT_DIR required");
    let out = Path::new(&output);
    fs::create_dir_all(out.join("slots")).unwrap();
    let mut summary = File::create(out.join("case-metadata.csv")).unwrap();
    writeln!(summary, "case,expected_equal,heterogeneous_initial_voltages,reference_messages,candidate_messages,reference_spikes,candidate_spikes,reference_processed,candidate_processed").unwrap();
    let positive = vec![input(0,2,256.0),input(0,2,512.0),input(1,2,128.0),input(1,2,256.0)];
    run_case(out,&mut summary,"positive_aligned",true,false,&positive,&grouped(&positive,true));
    run_case(out,&mut summary,"heterogeneous_initial_aligned",true,true,&positive,&grouped(&positive,true));
    let zero = vec![input(0,2,0.0)];
    run_case(out,&mut summary,"zero_wakeup_dropped",false,false,&zero,&grouped(&zero,false));
    run_case(out,&mut summary,"zero_wakeup_preserved",true,false,&zero,&grouped(&zero,true));
    let signed = vec![input(0,2,256.0),input(0,2,512.0),input(0,2,-256.0),input(0,2,-512.0)];
    run_case(out,&mut summary,"polarity_separate",true,false,&signed,&grouped(&signed,true));
    // Deliberately cancel E and I, retaining a zero wake marker at the same slot.
    run_case(out,&mut summary,"polarity_net_sum",false,false,&signed,&[input(0,2,0.0)]);
    let delayed = vec![input(0,2,256.0),input(0,2,512.0),input(0,4,-128.0),input(0,4,-128.0)];
    run_case(out,&mut summary,"arrival_slots_separate",true,false,&delayed,&grouped(&delayed,true));
    // Move I earlier; preserve destination arrival support {2,4} with a slot-4 marker.
    run_case(out,&mut summary,"arrival_slots_collapsed",false,false,&delayed,
        &[input(0,2,768.0),input(0,2,-256.0),input(0,4,0.0)]);
}
