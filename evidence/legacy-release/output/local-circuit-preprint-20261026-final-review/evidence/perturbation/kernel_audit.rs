//! Independent, minimal semantic checks against the frozen next_brain library.
//! The production source is neither patched nor reimplemented here.
use next_brain::connectivity::event_router::EventRouter;
use next_brain::connectivity::types::{LocalProjection, PopulationType, SynapticEdge};
use next_brain::core::chunk::{Chunk, ChunkId, ChunkStatus, DelayedEvent, GridCoord};
use next_brain::core::scheduler::Scheduler;
use next_brain::experiment::input_protocol::InputProtocol;
use next_brain::state::ChunkStateArrays;

const DT: f32 = 0.1;

fn close(actual: f32, expected: f32) {
    assert!(actual.is_finite() && expected.is_finite());
    assert!((actual - expected).abs() <= 1e-5_f32.max(expected.abs() * 2e-6),
        "actual={actual}, expected={expected}");
}
fn chunk(id: u32) -> Chunk {
    Chunk::new(ChunkId(id), GridCoord { x: id as i32, y: 0, z: 0 }, 1, 10.0)
}
fn equal_states(a: &ChunkStateArrays, b: &ChunkStateArrays) {
    for (x, y) in [(&a.voltages, &b.voltages), (&a.recovery, &b.recovery),
        (&a.g_local_exc, &b.g_local_exc), (&a.g_local_inh, &b.g_local_inh),
        (&a.g_long_range, &b.g_long_range), (&a.spike_flags, &b.spike_flags)] {
        assert_eq!(x.iter().map(|v| v.to_bits()).collect::<Vec<_>>(),
            y.iter().map(|v| v.to_bits()).collect::<Vec<_>>());
    }
    assert_eq!(a.refractory_until, b.refractory_until);
}

fn scalar_simd_exact_refractory_slots() {
    let mut scalar = ChunkStateArrays::new(1);
    let mut simd = ChunkStateArrays::new(1);
    for st in [&mut scalar, &mut simd] {
        st.g_local_exc[0] = 1000.0;
        st.recovery[0] = 7.0;
    }
    for n in 0..3 {
        let pre_until = scalar.refractory_until[0];
        let kernel_gate = pre_until > n;
        scalar.step_euler(DT, n);
        simd.step_euler_simd_friendly(DT, n);
        equal_states(&scalar, &simd);
        assert_eq!(kernel_gate, n == 1);
        assert_eq!(scalar.spike_flags[0], if n == 1 { 0.0 } else { 1.0 });
        assert_eq!(scalar.voltages[0], -65.0);
        assert_eq!(scalar.recovery[0], 7.0); // Stored but dynamically unused.
        assert_eq!(scalar.refractory_until[0], if n < 2 { 2 } else { 4 });
        close(scalar.g_local_exc[0], if n < 2 { 900.0 } else { 810.0 });
        if n == 0 {
            assert!(scalar.refractory_until[0] > n);
            assert!(!kernel_gate); // Post-step deadline would falsely count this spike step.
        }
    }
}

fn chunk_injections_precede_gate_and_context_still_decays() {
    let mut c = chunk(0);
    c.state.refractory_until[0] = 1;
    c.state.g_local_exc[0] = 10.0;
    c.state.g_local_inh[0] = 20.0;
    c.state.g_long_range[0] = 30.0;
    c.state.recovery[0] = 7.0;
    c.context.local_exc_field = 40.0;
    c.context.local_inh_field = 50.0;
    for strength in [5.0, -7.0] {
        c.event_queue.push(DelayedEvent { target_chunk: c.id, target_slot: 0,
            signal_strength: strength });
    }
    c.step(DT, 0);
    assert_eq!(c.state.voltages[0], -65.0);
    assert_eq!(c.state.spike_flags[0], 0.0);
    close(c.state.g_local_exc[0], (10.0 + 5.0) + 40.0 * 0.01);
    close(c.state.g_local_inh[0], (20.0 + 7.0) + 50.0 * 0.01);
    assert_eq!(c.state.g_long_range[0], 30.0); // No channel decay in the gated step.
    assert_eq!(c.state.recovery[0], 7.0);
    let decay = (-DT / 10.0).exp();
    close(c.context.local_exc_field, 40.0 * decay);
    close(c.context.local_inh_field, 50.0 * decay);
    assert_eq!(c.metrics.active_step_count, 1);
    assert_eq!(c.event_queue.count_due(0), 0);
    // At the equality boundary until==slot, integration and decay resume.
    let e = c.state.g_local_exc[0] + c.context.local_exc_field * 0.01;
    let i = c.state.g_local_inh[0] + c.context.local_inh_field * 0.01;
    let expected_v = -65.0 + (65.0 + (e - i + 30.0)) * DT;
    c.step(DT, 1);
    close(c.state.voltages[0], expected_v);
    close(c.state.g_local_exc[0], e * (1.0 - DT));
    close(c.state.g_local_inh[0], i * (1.0 - DT));
    close(c.state.g_long_range[0], 30.0 * (1.0 - DT));
}

fn silent_kernel_leaks_toward_zero() {
    let mut s = ChunkStateArrays::new(1);
    s.step_euler_simd_friendly(DT, 0);
    close(s.voltages[0], -58.5);
    for n in 1..200 { s.step_euler_simd_friendly(DT, n); }
    assert!(s.voltages[0] < 0.0 && s.voltages[0].abs() < 1e-6);
    assert_eq!(s.spike_flags[0], 0.0);
}

fn strong_inhibition_remains_finite_without_voltage_floor() {
    let mut s = ChunkStateArrays::new(1);
    s.g_local_inh[0] = 50_000.0;
    s.step_euler_simd_friendly(DT, 0);
    close(s.voltages[0], -5058.5);
    assert!(s.voltages[0].is_finite() && s.voltages[0] < -4000.0);
    close(s.g_local_inh[0], 45_000.0);
    assert_eq!(s.spike_flags[0], 0.0);
}

fn scheduler_dormancy_freezes_voltage_and_zero_wake_steps() {
    let mut s = Scheduler::new(DT);
    let mut c = chunk(0);
    c.status = ChunkStatus::Dormant;
    s.add_chunk(c);
    let m0 = s.step();
    assert_eq!(m0.active_chunk_count, 0);
    assert_eq!(s.chunks[&ChunkId(0)].state.voltages[0], -65.0);
    s.inject_event(DelayedEvent { target_chunk: ChunkId(0), target_slot: 1,
        signal_strength: 0.0 });
    let m1 = s.step();
    assert_eq!((m1.active_chunk_count, m1.event_count, m1.wakeup_count), (1, 1, 1));
    close(s.chunks[&ChunkId(0)].state.voltages[0], -58.5);
    assert_eq!(s.chunks[&ChunkId(0)].status, ChunkStatus::Active);
    let m2 = s.step(); // The due event kept it active for this additional step.
    assert_eq!(m2.active_chunk_count, 1);
    close(s.chunks[&ChunkId(0)].state.voltages[0], -52.65);
    assert_eq!(s.chunks[&ChunkId(0)].status, ChunkStatus::Dormant);
    let frozen = s.chunks[&ChunkId(0)].state.voltages[0].to_bits();
    let m3 = s.step();
    assert_eq!(m3.active_chunk_count, 0);
    assert_eq!(s.chunks[&ChunkId(0)].state.voltages[0].to_bits(), frozen);
}

fn pending_status_is_not_a_per_step_execution_flag() {
    let mut s = Scheduler::new(DT);
    let mut c = chunk(0); // Starts Active.
    c.event_queue.push(DelayedEvent { target_chunk: c.id, target_slot: 10,
        signal_strength: 0.0 });
    s.add_chunk(c);
    assert_eq!(s.step().active_chunk_count, 1);
    assert_eq!(s.chunks[&ChunkId(0)].status, ChunkStatus::PendingWakeUp { wake_slot: 10 });
    let before = s.chunks[&ChunkId(0)].metrics.active_step_count;
    assert_eq!(s.step().active_chunk_count, 1);
    assert_eq!(s.chunks[&ChunkId(0)].metrics.active_step_count, before + 1);
    close(s.chunks[&ChunkId(0)].state.voltages[0], -52.65);
}

fn post_step_routing_with_delay_one_arrives_two_processed_slots_later() {
    let mut s = Scheduler::new(DT);
    let mut source = chunk(0);
    source.state.g_local_exc[0] = 1000.0;
    let mut target = chunk(1);
    target.status = ChunkStatus::Dormant;
    s.add_chunk(source);
    s.add_chunk(target);
    let projection = LocalProjection { label: "audit".to_string(),
        source_type: PopulationType::Excitatory,
        edges: vec![SynapticEdge::new(ChunkId(0), ChunkId(1),
            PopulationType::Excitatory, 0.6, 1)] };
    let router = EventRouter::from_projections(&[&projection], 2);
    assert_eq!(s.step().total_spikes, 1); // Executes source slot n=0.
    assert_eq!(s.current_slot, 1);
    router.route_spikes(&mut s, 1.0);
    assert_eq!(s.chunks[&ChunkId(1)].event_queue.count_due(1), 0);
    assert_eq!(s.chunks[&ChunkId(1)].event_queue.count_due(2), 1);
    s.step(); // n=1, not yet delivered.
    assert_eq!(s.chunks[&ChunkId(1)].state.g_local_exc[0], 0.0);
    s.step(); // n=2, delivered and decayed during the target kernel step.
    close(s.chunks[&ChunkId(1)].state.g_local_exc[0], 0.6 * (1.0 - DT));
}

fn input_protocol_uses_current_slot_before_step() {
    let mut s = Scheduler::new(DT);
    s.add_chunk(chunk(0));
    let p = InputProtocol::pulsed(vec![ChunkId(0)], 150.0, 2, 3);
    for n in 0..7 {
        s.current_slot = n;
        p.inject(&mut s);
        let due = s.chunks.get_mut(&ChunkId(0)).unwrap().event_queue.drain_due(n);
        assert_eq!(due.len(), if n % 5 < 2 { 1 } else { 0 });
        for e in due { assert_eq!(e.target_slot, n); assert_eq!(e.signal_strength, 150.0); }
    }
}

fn main() {
    scalar_simd_exact_refractory_slots();
    chunk_injections_precede_gate_and_context_still_decays();
    silent_kernel_leaks_toward_zero();
    strong_inhibition_remains_finite_without_voltage_floor();
    scheduler_dormancy_freezes_voltage_and_zero_wake_steps();
    pending_status_is_not_a_per_step_execution_flag();
    post_step_routing_with_delay_one_arrives_two_processed_slots_later();
    input_protocol_uses_current_slot_before_step();
    println!("PASS: 8 independent frozen-kernel, refractory, injection, context, scheduler and routing checks");
}
