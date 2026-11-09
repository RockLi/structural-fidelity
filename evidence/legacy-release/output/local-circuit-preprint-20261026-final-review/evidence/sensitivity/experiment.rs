//! Explicit-only sensitivity instrumentation over the unchanged frozen library.
//!
//! The graph, probes, time horizon, canonical EventRouter, ten output fields,
//! and simulation-loop order match evidence/rewiring/experiment.rs. The sole
//! new intervention is optional chunk-wise initial-voltage bits. It is applied
//! before each chunk is registered with the scheduler, before any event or step.
use next_brain::connectivity::event_router::EventRouter;
use next_brain::connectivity::microcircuit::EIMicrocircuit;
use next_brain::connectivity::types::{LocalProjection, PopulationType, SynapticEdge};
use next_brain::core::chunk::{Chunk, ChunkId, ChunkStatus, GridCoord};
use next_brain::core::scheduler::Scheduler;
use next_brain::experiment::harness::build_harness_scheduler;
use next_brain::experiment::input_protocol::{InputProtocol, OperatingRegime};
use std::collections::HashSet;
use std::io::{BufWriter, Write};
use std::path::Path;

const N: usize = 125;
const U: usize = 100;
const STEPS: usize = 300;
const WIDTH: usize = 10;
const DEFAULT_V: f32 = -65.0;

fn read_graph(path: &Path) -> EIMicrocircuit {
    let empty = |a: usize| LocalProjection {
        label: ["E→E", "E→I", "I→E", "I→I"][a].to_string(),
        source_type: if a < 2 { PopulationType::Excitatory } else { PopulationType::Inhibitory },
        edges: vec![],
    };
    let mut projections = [empty(0), empty(1), empty(2), empty(3)];
    let contents = std::fs::read_to_string(path).unwrap();
    let mut lines = contents.lines();
    assert_eq!(lines.next(), Some("arm,source,target,weight_bits,delay"));
    let mut pairs = HashSet::new();
    for line in lines {
        let v: Vec<u32> = line.split(',').map(|s| s.parse().unwrap()).collect();
        assert_eq!(v.len(), 5);
        let a = v[0] as usize;
        assert!(a < 4 && v[1] < N as u32 && v[2] < N as u32 && v[1] != v[2]);
        assert_eq!((v[1] >= 100) as usize * 2 + (v[2] >= 100) as usize, a);
        assert_eq!(v[4], 1);
        assert!(f32::from_bits(v[3]).is_finite() && f32::from_bits(v[3]) > 0.0);
        assert!(pairs.insert((v[1], v[2])), "duplicate directed pair");
        // Preserve supplied row order within each arm, as the frozen driver did.
        let source_type = projections[a].source_type;
        projections[a].edges.push(SynapticEdge::new(
            ChunkId(v[1]), ChunkId(v[2]), source_type, f32::from_bits(v[3]), v[4] as u64,
        ));
    }
    let [ee, ei, ie, ii] = projections;
    EIMicrocircuit { ee, ei, ie, ii }
}

fn read_initial(path: Option<&Path>) -> [u32; N] {
    let Some(path) = path else { return [DEFAULT_V.to_bits(); N] };
    let contents = std::fs::read_to_string(path).unwrap();
    let mut lines = contents.lines();
    assert_eq!(lines.next(), Some("chunk,voltage_bits"));
    let mut bits = [0u32; N];
    let mut seen = [false; N];
    for line in lines {
        let v: Vec<u32> = line.split(',').map(|s| s.parse().unwrap()).collect();
        assert_eq!(v.len(), 2);
        let id = v[0] as usize;
        assert!(id < N && !seen[id], "initial CSV must contain each chunk once");
        assert!(f32::from_bits(v[1]).is_finite(), "initial voltage must be finite");
        bits[id] = v[1];
        seen[id] = true;
    }
    assert!(seen.iter().all(|x| *x), "initial CSV must contain all 125 chunks");
    bits
}

fn input(probe: &str) -> InputProtocol {
    let e = (0..100).map(ChunkId).collect::<Vec<_>>();
    match probe {
        "tonic" => InputProtocol::for_regime(OperatingRegime::Sustained, e),
        "global_burst" => InputProtocol::pulsed(e, 150.0, 80, 22000),
        "focal_burst" => InputProtocol::pulsed(e.into_iter().filter(|id| id.0 % 5 == 0).collect(), 150.0, 80, 22000),
        _ => panic!("unknown probe"),
    }
}

fn assert_within_chunk(c: &Chunk) {
    let st = &c.state;
    assert_eq!(st.num_units, U);
    for array in [&st.voltages, &st.recovery, &st.g_local_exc, &st.g_local_inh, &st.g_long_range, &st.spike_flags] {
        assert_eq!(array.len(), U);
        assert!(array.iter().all(|x| x.is_finite() && x.to_bits() == array[0].to_bits()));
    }
    assert_eq!(st.refractory_until.len(), U);
    assert!(st.refractory_until.iter().all(|&x| x == st.refractory_until[0]));
}

fn scheduler(initial: &[u32; N]) -> Scheduler {
    let mut s = Scheduler::new(0.1);
    // This is the specialized 10,000-E / 2,500-I / 100-units-per-chunk
    // construction from build_harness_scheduler, with the same coordinates,
    // field-decay constant and Dormant registration. No kernel is replaced.
    for (i, &voltage_bits) in initial.iter().enumerate() {
        let mut c = Chunk::new(
            ChunkId(i as u32),
            GridCoord { x: i as i32, y: if i < 100 { 0 } else { 1 }, z: 0 },
            U, 10.0,
        );
        c.state.voltages.fill(f32::from_bits(voltage_bits));
        c.status = ChunkStatus::Dormant;
        assert_eq!(c.event_queue.next_wake_slot(), None);
        assert_within_chunk(&c);
        s.add_chunk(c);
    }
    assert_initialization(&s, initial);
    s
}

// This check constructs the historical scheduler but never injects an event or
// advances either scheduler. All accessible initial state other than V must be
// bit-identical to the historical constructor; supplied V bits must survive.
fn assert_initialization(s: &Scheduler, initial: &[u32; N]) {
    let (reference, exc, inh) = build_harness_scheduler(10_000, 2_500, U, 0.1);
    assert_eq!(exc, (0..100).map(ChunkId).collect::<Vec<_>>());
    assert_eq!(inh, (100..125).map(ChunkId).collect::<Vec<_>>());
    assert_eq!(s.current_slot, 0);
    assert_eq!(s.dt.to_bits(), reference.dt.to_bits());
    assert_eq!(s.chunks.len(), N);
    for (i, &bits) in initial.iter().enumerate() {
        let a = &s.chunks[&ChunkId(i as u32)];
        let b = &reference.chunks[&ChunkId(i as u32)];
        assert_eq!(a.id, b.id);
        assert_eq!((a.coord.x, a.coord.y, a.coord.z), (b.coord.x, b.coord.y, b.coord.z));
        assert_eq!(a.status, b.status);
        assert_eq!(a.status, ChunkStatus::Dormant);
        assert_eq!(a.event_queue.next_wake_slot(), None);
        assert_eq!(a.event_queue.count_due(0), 0);
        assert_eq!(a.state.num_units, b.state.num_units);
        assert!(a.state.voltages.iter().all(|x| x.to_bits() == bits));
        for (x, y) in [(&a.state.recovery, &b.state.recovery),
            (&a.state.g_local_exc, &b.state.g_local_exc),
            (&a.state.g_local_inh, &b.state.g_local_inh),
            (&a.state.g_long_range, &b.state.g_long_range),
            (&a.state.spike_flags, &b.state.spike_flags)] {
            assert!(x.iter().zip(y).all(|(u, v)| u.to_bits() == v.to_bits()));
        }
        assert_eq!(a.state.refractory_until, b.state.refractory_until);
        assert_eq!(a.context.local_exc_field.to_bits(), b.context.local_exc_field.to_bits());
        assert_eq!(a.context.local_inh_field.to_bits(), b.context.local_inh_field.to_bits());
        assert_eq!(a.context.field_decay_tau.to_bits(), b.context.field_decay_tau.to_bits());
        assert_eq!(a.metrics.spikes_last_step, 0);
        assert_eq!(a.metrics.dormant_skip_count, 0);
        assert_eq!(a.metrics.active_step_count, 0);
        assert_within_chunk(a);
    }
}

struct Run {
    data: Vec<u32>,
    counts: Vec<(u32, u32, u32, u32)>,
    initial: [u32; N],
    first_step_slot: [Option<u32>; N],
    first_pre_update_voltage_bits: [Option<u32>; N],
    elapsed: f64,
}

fn simulate(g: &EIMicrocircuit, probe: &str, initial: [u32; N]) -> Run {
    let mut s = scheduler(&initial);
    let router = EventRouter::from_projections(&g.all_proj_refs(), N);
    let mut outdeg = [0u32; N];
    for edge in g.all_edges() { outdeg[edge.source_chunk.0 as usize] += 1; }
    let protocol = input(probe);
    let mut data = Vec::with_capacity(STEPS * N * WIDTH);
    let mut counts = Vec::with_capacity(STEPS);
    let mut first_step_slot = [None; N];
    let mut first_pre_update_voltage_bits = [None; N];
    let mut previous_active_steps = [0u64; N];
    let start = std::time::Instant::now();
    for slot in 0..STEPS {
        assert_eq!(s.current_slot, slot as u64);
        protocol.inject(&mut s);
        // Input injection only queues events; it does not update V or wake a
        // chunk. Capture initial/dormant V without advancing either object.
        let before: [u32; N] = std::array::from_fn(|i| s.chunks[&ChunkId(i as u32)].state.voltages[0].to_bits());
        let m = s.step();
        let mut visits = 0;
        for i in 0..N {
            let c = &s.chunks[&ChunkId(i as u32)];
            let now = c.metrics.active_step_count;
            assert!(now == previous_active_steps[i] || now == previous_active_steps[i] + 1);
            if previous_active_steps[i] == 0 && now == 1 {
                assert!(first_step_slot[i].is_none());
                first_step_slot[i] = Some(slot as u32);
                first_pre_update_voltage_bits[i] = Some(before[i]);
                assert_eq!(before[i], initial[i], "dormant voltage changed before first execution");
            }
            previous_active_steps[i] = now;
            if c.state.spike_flags.iter().any(|&x| x > 0.0) { visits += outdeg[i]; }
        }
        // Frozen EventRouter sorts source ChunkIds before routing, preserving
        // canonical f32 input accumulation. No raw-sum or proxy path is used.
        router.route_spikes(&mut s, 1.0);
        let (a, b) = router.count_injected_events(&s, 1.0);
        let events = a + b;
        let mut observed = 0;
        for i in 0..N {
            let c = &s.chunks[&ChunkId(i as u32)];
            assert_within_chunk(c);
            let st = &c.state;
            let spikes = st.spike_flags.iter().sum::<f32>() as u32;
            observed += spikes;
            let status = match c.status { ChunkStatus::Active => 1, ChunkStatus::Dormant => 0, ChunkStatus::PendingWakeUp { .. } => 2 };
            data.extend_from_slice(&[spikes, st.voltages[0].to_bits(), st.g_local_exc[0].to_bits(),
                st.g_local_inh[0].to_bits(), st.g_long_range[0].to_bits(), st.recovery[0].to_bits(),
                c.context.local_exc_field.to_bits(), c.context.local_inh_field.to_bits(),
                u32::try_from(st.refractory_until[0]).unwrap(), status]);
        }
        assert_eq!(observed, m.total_spikes);
        counts.push((observed, events, visits, m.active_chunk_count));
    }
    Run { data, counts, initial, first_step_slot, first_pre_update_voltage_bits,
        elapsed: start.elapsed().as_secs_f64() }
}

fn new_file(path: &Path) -> std::fs::File {
    std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap()
}

fn output(run: &Run, prefix: &Path) {
    let mut w = BufWriter::new(new_file(&prefix.with_extension("bin")));
    for x in &run.data { w.write_all(&x.to_le_bytes()).unwrap(); }
    w.flush().unwrap();
    let mut w = BufWriter::new(new_file(&prefix.with_extension("csv")));
    writeln!(w, "step,spikes,recurrent_messages,active_source_edge_visits,active_chunks").unwrap();
    for (i, (a, b, c, d)) in run.counts.iter().enumerate() { writeln!(w, "{i},{a},{b},{c},{d}").unwrap(); }
    w.flush().unwrap();
    let initial = run.initial.iter().map(u32::to_string).collect::<Vec<_>>().join(",");
    let option_array = |items: &[Option<u32>; N]| items.iter()
        .map(|x| x.map_or_else(|| "null".to_string(), |v| v.to_string()))
        .collect::<Vec<_>>().join(",");
    let first_step = option_array(&run.first_step_slot);
    let first_v = option_array(&run.first_pre_update_voltage_bits);
    let mut w = new_file(&prefix.with_extension("json"));
    writeln!(w, "{{\"steps\":{STEPS},\"chunks\":{N},\"units_per_chunk\":{U},\"columns\":{WIDTH},\"instrumented_loop_seconds\":{},\"timing_is_performance_benchmark\":false,\"mode\":\"explicit\",\"initial_voltage_bits\":[{}],\"initialization_before_add_chunk\":true,\"initial_slot\":0,\"initial_queues_empty\":true,\"other_initial_fields_match_frozen_harness\":true,\"within_chunk_equality_initial_and_all_slots\":true,\"within_chunk_checks\":{},\"first_step_slot\":[{}],\"first_pre_update_voltage_bits\":[{}]}}", run.elapsed, initial, N * (STEPS + 1), first_step, first_v).unwrap();
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    match a.get(1).map(String::as_str) {
        Some("simulate") => {
            assert!(a.len() == 5 || a.len() == 6, "simulate GRAPH PROBE PREFIX [INITIAL_V_CSV]");
            let prefix = Path::new(&a[4]);
            for ext in ["bin", "csv", "json"] { assert!(!prefix.with_extension(ext).exists(), "refusing to overwrite output"); }
            let initial = read_initial(a.get(5).map(|x| Path::new(x.as_str())));
            output(&simulate(&read_graph(Path::new(&a[2])), &a[3], initial), prefix);
        }
        Some("check-initialization") => {
            assert!(a.len() == 2 || a.len() == 3, "check-initialization [INITIAL_V_CSV]");
            let initial = read_initial(a.get(2).map(|x| Path::new(x.as_str())));
            let s = scheduler(&initial);
            assert_eq!(s.current_slot, 0);
            println!("{{\"status\":\"pass\",\"simulation_steps\":0,\"events_injected\":0,\"chunks\":{N},\"units_per_chunk\":{U},\"initialization_before_add_chunk\":true,\"other_initial_fields_match_frozen_harness\":true,\"within_chunk_equality\":true}}");
        }
        _ => panic!("simulate GRAPH PROBE PREFIX [INITIAL_V_CSV] | check-initialization [INITIAL_V_CSV]"),
    }
}
