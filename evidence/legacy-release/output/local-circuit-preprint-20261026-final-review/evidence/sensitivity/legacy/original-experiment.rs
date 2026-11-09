//! Additive experiment driver. Neuronal integration and proxy equations come
//! from the frozen preprint library. See build.patch for the two library edits.
use next_brain::connectivity::microcircuit::{EIMicrocircuit, EIMicrocircuitSpec};
use next_brain::connectivity::types::{LocalProjection, PopulationType, SynapticEdge};
use next_brain::connectivity::event_router::EventRouter;
use next_brain::core::chunk::{ChunkId, ChunkStatus};
use next_brain::experiment::harness::{build_harness_scheduler, HarnessConfig, run_explicit, run_lpu};
use next_brain::experiment::input_protocol::{InputProtocol, OperatingRegime};
use next_brain::experiment::lpu_index::LpuTopologyIndex;
use next_brain::lpu::proxy::ProxyMode;
use next_brain::lpu::proxy_params::RicherProxyParams;
use next_brain::lpu::aggregator::AggregatorParams;
use std::io::{BufWriter, Write};
use std::path::Path;

const N: usize = 125;
const U: usize = 100;
const STEPS: usize = 300;
const WIDTH: usize = 10;

fn ids() -> (Vec<ChunkId>, Vec<ChunkId>) {
    ((0..100).map(ChunkId).collect(), (100..125).map(ChunkId).collect())
}
fn params() -> RicherProxyParams {
    RicherProxyParams { gain_fast_exc: 2.5, gain_fast_inh: 0.4, ..Default::default() }
}
fn graph(family: &str) -> EIMicrocircuit {
    let (exc, inh) = ids();
    if family == "heterogeneous" { return EIMicrocircuitSpec::boundary_heavy_hetero(exc, inh).build(); }
    assert_eq!(family, "homogeneous");
    EIMicrocircuitSpec { exc_chunks: exc, inh_chunks: inh,
        p_ee: 0.15, p_ei: 0.25, p_ie: 0.25, p_ii: 0.20,
        w_ee: 0.6, w_ei: 0.8, w_ie: 1.4, w_ii: 0.5,
        delay_slots: 1, rng_seed: 99, forbid_within_chunk: true, weight_spread: 0.0 }.build()
}
fn write_graph(g: &EIMicrocircuit, path: &Path) {
    let mut w = BufWriter::new(std::fs::File::create(path).unwrap());
    writeln!(w, "arm,source,target,weight_bits,delay").unwrap();
    for (a,p) in g.all_proj_refs().iter().enumerate() {
        for e in &p.edges { writeln!(w, "{a},{},{},{},{}", e.source_chunk.0, e.target_chunk.0, e.weight.to_bits(), e.delay_slots).unwrap(); }
    }
}
fn read_graph(path: &Path) -> EIMicrocircuit {
    let empty = |a: usize| LocalProjection { label: ["E→E","E→I","I→E","I→I"][a].to_string(),
        source_type: if a < 2 { PopulationType::Excitatory } else { PopulationType::Inhibitory }, edges: vec![] };
    let mut p = [empty(0),empty(1),empty(2),empty(3)];
    for line in std::fs::read_to_string(path).unwrap().lines().skip(1) {
        let v: Vec<u32> = line.split(',').map(|s| s.parse().unwrap()).collect();
        assert_eq!(v.len(), 5);
        let a = v[0] as usize;
        assert!(a < 4 && v[1] < N as u32 && v[2] < N as u32 && v[1] != v[2]);
        assert_eq!((v[1] >= 100) as usize * 2 + (v[2] >= 100) as usize, a);
        assert_eq!(v[4], 1);
        assert!(f32::from_bits(v[3]).is_finite() && f32::from_bits(v[3]) > 0.0);
        p[a].edges.push(SynapticEdge::new(ChunkId(v[1]),ChunkId(v[2]),p[a].source_type,f32::from_bits(v[3]),v[4] as u64));
    }
    let [ee,ei,ie,ii] = p;
    EIMicrocircuit { ee,ei,ie,ii }
}
fn input(probe: &str) -> InputProtocol {
    let (e,_) = ids();
    match probe {
        "tonic" => InputProtocol::for_regime(OperatingRegime::Sustained, e),
        "global_burst" => InputProtocol::pulsed(e,150.0,80,22000),
        "focal_burst" => InputProtocol::pulsed(e.into_iter().filter(|id| id.0 % 5 == 0).collect(),150.0,80,22000),
        _ => panic!("unknown probe")
    }
}
struct Run { data: Vec<u32>, counts: Vec<(u32,u32,u32,u32)>, elapsed: f64 }
fn simulate(g: &EIMicrocircuit, probe: &str, mode: &str) -> Run {
    let (mut s,_,_) = build_harness_scheduler(10_000,2_500,U,0.1);
    let router = EventRouter::from_projections(&g.all_proj_refs(),N);
    let mut index = LpuTopologyIndex::build_with_mode(g,N,ProxyMode::Stateful);
    let mut outdeg = [0u32;N];
    for edge in g.all_edges() { outdeg[edge.source_chunk.0 as usize] += 1; }
    let protocol = input(probe);
    let mut data = Vec::with_capacity(STEPS*N*WIDTH);
    let mut counts = Vec::with_capacity(STEPS);
    let start = std::time::Instant::now();
    for _ in 0..STEPS {
        protocol.inject(&mut s);
        let m = s.step();
        let mut visits = 0;
        for i in 0..N {
            let c = &s.chunks[&ChunkId(i as u32)];
            if c.state.spike_flags.iter().any(|&x| x > 0.0) { visits += outdeg[i]; }
        }
        let events = match mode {
            "explicit" => { router.route_spikes(&mut s,1.0); let (a,b)=router.count_injected_events(&s,1.0); a+b },
            "raw_sum" => index.step_raw_sum_control(&mut s,&params(),U),
            "trace" => index.step_stateful(&mut s,&params(),U),
            _ => panic!("unknown mode")
        };
        let mut observed = 0;
        for i in 0..N {
            let c = &s.chunks[&ChunkId(i as u32)];
            let st = &c.state;
            // Shared broadcast + identical initialization means units within a
            // chunk are exact duplicates here. Check rather than assume this.
            for array in [&st.voltages,&st.recovery,&st.g_local_exc,&st.g_local_inh,&st.g_long_range,&st.spike_flags] {
                assert!(array.iter().all(|x| x.is_finite() && x.to_bits() == array[0].to_bits()));
            }
            assert!(st.refractory_until.iter().all(|&x| x == st.refractory_until[0]));
            let spikes = st.spike_flags.iter().sum::<f32>() as u32;
            observed += spikes;
            let status = match c.status { ChunkStatus::Active=>1, ChunkStatus::Dormant=>0, ChunkStatus::PendingWakeUp{..}=>2 };
            data.extend_from_slice(&[spikes, st.voltages[0].to_bits(), st.g_local_exc[0].to_bits(),
                st.g_local_inh[0].to_bits(), st.g_long_range[0].to_bits(), st.recovery[0].to_bits(),
                c.context.local_exc_field.to_bits(),c.context.local_inh_field.to_bits(),
                u32::try_from(st.refractory_until[0]).unwrap(),status]);
        }
        assert_eq!(observed,m.total_spikes);
        counts.push((observed,events,visits,m.active_chunk_count));
    }
    Run { data,counts,elapsed:start.elapsed().as_secs_f64() }
}
fn output(run: &Run, prefix: &Path) {
    let mut w=BufWriter::new(std::fs::File::create(prefix.with_extension("bin")).unwrap());
    for x in &run.data { w.write_all(&x.to_le_bytes()).unwrap(); }
    let mut w=BufWriter::new(std::fs::File::create(prefix.with_extension("csv")).unwrap());
    writeln!(w,"step,spikes,recurrent_messages,active_source_edge_visits,active_chunks").unwrap();
    for (i,(a,b,c,d)) in run.counts.iter().enumerate() { writeln!(w,"{i},{a},{b},{c},{d}").unwrap(); }
    std::fs::write(prefix.with_extension("json"),format!("{{\"steps\":{STEPS},\"chunks\":{N},\"units_per_chunk\":{U},\"columns\":{WIDTH},\"instrumented_loop_seconds\":{},\"timing_is_performance_benchmark\":false}}\n",run.elapsed)).unwrap();
}
fn checks() {
    let g=graph("heterogeneous");
    let exp=simulate(&g,"tonic","explicit");
    assert_eq!(exp.counts[..200].iter().map(|x|x.0 as u64).sum::<u64>(),124_500);
    assert_eq!(exp.counts[..200].iter().map(|x|x.1 as u64).sum::<u64>(),32_247);
    let (e,i)=ids();
    let mut cfg=HarnessConfig { exc_units:10_000,inh_units:2_500,units_per_chunk:U,dt:0.1,num_steps:STEPS as u64,
        input_protocol:input("tonic"), router:Some(EventRouter::from_projections(&g.all_proj_refs(),N)),
        lpu_params:AggregatorParams::default(),replaced_circuit:None,lpu_index:None,
        proxy_mode:ProxyMode::Stateful,richer_params:params() };
    let old=run_explicit(&cfg);
    for (a,b) in old.steps.iter().zip(&exp.counts) { assert_eq!((a.total_spikes,a.events_injected),(b.0,b.1)); }
    cfg.router=None;
    cfg.lpu_index=Some(LpuTopologyIndex::build_with_mode(&g,N,ProxyMode::Stateful));
    let trace=simulate(&g,"tonic","trace");
    let old=run_lpu(&mut cfg,&e,&i);
    for (a,b) in old.steps.iter().zip(&trace.counts) { assert_eq!((a.total_spikes,a.events_injected),(b.0,b.1)); }
    let raw=simulate(&g,"tonic","raw_sum");
    for (a,b) in exp.data.chunks_exact(WIDTH).zip(raw.data.chunks_exact(WIDTH)) { assert_eq!(a[0],b[0]); }
    let repeat=simulate(&g,"tonic","explicit");
    assert_eq!(exp.data,repeat.data);
    assert_eq!(exp.counts,repeat.counts);
    println!("PASS: historical 200-slot bridge; unchanged harness explicit/trace bridge; raw spike control; full instrumented-data repeat; within-chunk equality");
}
fn main() {
    let a:Vec<String>=std::env::args().collect();
    match a.get(1).map(String::as_str) {
        Some("generate") => write_graph(&graph(&a[2]),Path::new(&a[3])),
        Some("simulate") => output(&simulate(&read_graph(Path::new(&a[2])),&a[3],&a[4]),Path::new(&a[5])),
        Some("check") => checks(),
        _ => panic!("generate FAMILY CSV | simulate GRAPH PROBE MODE PREFIX | check")
    }
}
