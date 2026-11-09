use next_brain::connectivity::microcircuit::EIMicrocircuitSpec;
use next_brain::core::chunk::ChunkId;
use std::io::{BufWriter,Write};
fn main(){
 let a:Vec<String>=std::env::args().collect();let seed:u64=a[1].parse().unwrap();
 let spec=EIMicrocircuitSpec{exc_chunks:(0..100).map(ChunkId).collect(),inh_chunks:(100..125).map(ChunkId).collect(),p_ee:0.15,p_ei:0.25,p_ie:0.25,p_ii:0.20,w_ee:0.6,w_ei:0.8,w_ie:1.4,w_ii:0.5,delay_slots:1,rng_seed:seed,forbid_within_chunk:true,weight_spread:0.0};
 let g=spec.build();let mut f=BufWriter::new(std::fs::File::create(&a[2]).unwrap());writeln!(f,"arm,source,target,weight_bits,delay").unwrap();
 for (arm,p) in [&g.ee,&g.ei,&g.ie,&g.ii].iter().enumerate(){for e in &p.edges{writeln!(f,"{},{},{},{},{}",arm,e.source_chunk.0,e.target_chunk.0,e.weight.to_bits(),e.delay_slots).unwrap();}}
}
