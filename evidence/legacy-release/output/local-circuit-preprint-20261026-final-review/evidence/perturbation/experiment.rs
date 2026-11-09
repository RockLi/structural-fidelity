//! Additive experiment driver. Neuronal integration and proxy equations come
//! from the frozen preprint library. See build.patch for the two library edits.
use next_brain::connectivity::microcircuit::{EIMicrocircuit, EIMicrocircuitSpec};
use next_brain::connectivity::types::{LocalProjection, PopulationType, SynapticEdge};
use next_brain::connectivity::event_router::EventRouter;
use next_brain::core::chunk::{ChunkId, ChunkStatus, DelayedEvent};
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
const STEPS: usize = 1000;
const WIDTH: usize = 14;

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
// All simulations use explicit canonical-order routing. a=0,1.5,3.0.
struct Run { data: Vec<u32>, counts: Vec<(u32,u32,u32,u32,u32,u32)>, elapsed: f64 }
fn simulate(g: &EIMicrocircuit, amplitude: f32, steps: usize, targets: std::ops::Range<u32>) -> Run {
    let (mut s,_,_) = build_harness_scheduler(10_000,2_500,U,0.1);
    let router = EventRouter::from_projections(&g.all_proj_refs(),N);
    let mut outdeg=[0u32;N]; for e in g.all_edges() {outdeg[e.source_chunk.0 as usize]+=1;}
    let mut data=Vec::with_capacity(steps*N*WIDTH); let mut counts=Vec::with_capacity(steps);
    let started=std::time::Instant::now();
    for n in 0..steps {
        assert_eq!(s.current_slot,n as u64);
        let dose=if n<80 {150.0} else if n>=200 && n<210 {amplitude} else {0.0};
        if dose>0.0 {for target in targets.clone() {s.inject_event(DelayedEvent{target_chunk:ChunkId(target),target_slot:n as u64,signal_strength:dose});}}
        let mut pre=[(0u64,0u64,0u32,0u32);N];
        for i in 0..N {let c=&s.chunks[&ChunkId(i as u32)]; pre[i]=(c.state.refractory_until[0],c.metrics.active_step_count,c.state.voltages[0].to_bits(),c.event_queue.count_due(n as u64));}
        let m=s.step();
        router.route_spikes(&mut s,1.0);let(a,b)=router.count_injected_events(&s,1.0);let events=a+b;
        let(mut observed,mut visits,mut stepped_total,mut gated_total)=(0,0,0,0);
        for i in 0..N {
            let c=&s.chunks[&ChunkId(i as u32)];let st=&c.state;
            for array in [&st.voltages,&st.recovery,&st.g_local_exc,&st.g_local_inh,&st.g_long_range,&st.spike_flags] {assert!(array.iter().all(|x|x.is_finite()&&x.to_bits()==array[0].to_bits()));}
            assert!(st.refractory_until.iter().all(|&x|x==st.refractory_until[0]));
            let stepped=(c.metrics.active_step_count-pre[i].1) as u32;assert!(stepped<=1);
            let gated=stepped*((pre[i].0>n as u64) as u32);
            if gated==1 {assert_eq!(st.voltages[0].to_bits(),pre[i].2);assert_eq!(st.spike_flags[0],0.0);}
            let spikes=st.spike_flags.iter().sum::<f32>() as u32;
            if stepped==0 {assert_eq!(spikes,0);assert_eq!(st.voltages[0].to_bits(),pre[i].2);}
            if spikes>0 {visits+=outdeg[i];}
            observed+=spikes;stepped_total+=stepped;gated_total+=gated;
            let status=match c.status {ChunkStatus::Active=>1,ChunkStatus::Dormant=>0,ChunkStatus::PendingWakeUp{..}=>2};
            data.extend_from_slice(&[spikes,st.voltages[0].to_bits(),st.g_local_exc[0].to_bits(),st.g_local_inh[0].to_bits(),st.g_long_range[0].to_bits(),st.recovery[0].to_bits(),c.context.local_exc_field.to_bits(),c.context.local_inh_field.to_bits(),st.refractory_until[0] as u32,status,pre[i].0 as u32,stepped,gated,pre[i].3]);
        }
        assert_eq!(observed,m.total_spikes);assert_eq!(visits,events);assert_eq!(stepped_total,m.active_chunk_count);
        counts.push((observed,events,visits,stepped_total,gated_total,m.event_count));
    }
    Run{data,counts,elapsed:started.elapsed().as_secs_f64()}
}
fn output(run:&Run,prefix:&Path) {
    let mut w=BufWriter::new(std::fs::File::create(prefix.with_extension("bin")).unwrap());for x in &run.data {w.write_all(&x.to_le_bytes()).unwrap();}
    let mut w=BufWriter::new(std::fs::File::create(prefix.with_extension("csv")).unwrap());writeln!(w,"step,spikes,recurrent_messages,active_source_edge_visits,stepped_chunks,refractory_skipped_chunks,due_events").unwrap();
    for(i,(a,b,c,d,e,f)) in run.counts.iter().enumerate(){writeln!(w,"{i},{a},{b},{c},{d},{e},{f}").unwrap();}
    std::fs::write(prefix.with_extension("json"),format!("{{\"steps\":{},\"chunks\":125,\"units_per_chunk\":100,\"columns\":14,\"instrumented_seconds\":{},\"performance_benchmark\":false}}\n",run.counts.len(),run.elapsed)).unwrap();
}
fn main(){
    let a:Vec<String>=std::env::args().collect();
    match a.get(1).map(String::as_str){
        Some("simulate")=>output(&simulate(&read_graph(Path::new(&a[2])),a[3].parse().unwrap(),STEPS,40..60),Path::new(&a[4])),
        Some("bridge")=>output(&simulate(&read_graph(Path::new(&a[2])),0.0,300,0..20),Path::new(&a[3])),
        _=>panic!("simulate GRAPH AMPLITUDE PREFIX | bridge GRAPH PREFIX")
    }
}
