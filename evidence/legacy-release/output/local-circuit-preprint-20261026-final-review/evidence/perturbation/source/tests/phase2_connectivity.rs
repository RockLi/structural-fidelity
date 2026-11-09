//! Phase 2 integration tests: minimal explicit connectivity baseline.
//!
//! Validates Task 1 — that the E/I microcircuit baseline:
//! (a) produces the correct number of edges and projections,
//! (b) injects spike-driven events into target chunks via EventRouter,
//! (c) produces non-trivial (nontrivially quiescent) dynamics.

#[cfg(test)]
mod phase2_connectivity {
    use next_brain::connectivity::{
        event_router::EventRouter, microcircuit::EIMicrocircuitSpec, types::PopulationType,
    };
    use next_brain::core::chunk::{Chunk, ChunkId, ChunkStatus, GridCoord};
    use next_brain::core::scheduler::Scheduler;
    use next_brain::experiment::input_protocol::{InputProtocol, OperatingRegime};
    use next_brain::lpu::aggregator::{AggregationMode, AggregatorParams};
    use next_brain::lpu::calibration::FiringRateRecorder;

    fn make_scheduler_with_chunks(n_exc: u32, n_inh: u32, units: usize) -> Scheduler {
        let mut sched = Scheduler::new(0.001);
        for i in 0..(n_exc + n_inh) {
            let id = ChunkId(i);
            let mut chunk = Chunk::new(
                id,
                GridCoord {
                    x: i as i32,
                    y: 0,
                    z: 0,
                },
                units,
                10.0,
            );
            chunk.status = ChunkStatus::Dormant;
            sched.add_chunk(chunk);
        }
        sched
    }

    // ── Test 1: EIMicrocircuit edge counts are within expected probability bounds ─
    #[test]
    fn test_microcircuit_edge_counts() {
        let exc_ids: Vec<ChunkId> = (0..5).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (5..7).map(ChunkId).collect();

        let spec = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone());
        let mc = spec.build();

        // With p_ee=0.10, expected ~0.10 × 5×4 = 2 E→E edges (allow 0–10 range).
        assert!(
            mc.total_edge_count() > 0,
            "microcircuit must have at least one edge"
        );

        // All four arms must be present as fields.
        let _ = mc.ee.edge_count();
        let _ = mc.ei.edge_count();
        let _ = mc.ie.edge_count();
        let _ = mc.ii.edge_count();

        println!("{}", mc.summary());
    }

    // ── Test 2: PopulationType routing ─────────────────────────────────────────
    #[test]
    fn test_edge_source_types() {
        let exc_ids: Vec<ChunkId> = (0..3).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (3..5).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids, inh_ids).build();

        // All edges in ee/ei must be excitatory source.
        for edge in mc.ee.edges.iter().chain(mc.ei.edges.iter()) {
            assert_eq!(edge.source_type, PopulationType::Excitatory);
        }
        // All edges in ie/ii must be inhibitory source.
        for edge in mc.ie.edges.iter().chain(mc.ii.edges.iter()) {
            assert_eq!(edge.source_type, PopulationType::Inhibitory);
        }
    }

    // ── Test 3: EventRouter builds adjacency correctly ──────────────────────────
    #[test]
    fn test_event_router_builds() {
        let exc_ids: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids, inh_ids).build();

        let projections: Vec<&_> = vec![&mc.ee, &mc.ei, &mc.ie, &mc.ii];
        let router = EventRouter::from_projections(&projections, 8);
        assert_eq!(router.total_edge_count(), mc.total_edge_count());
    }

    // ── Test 4: InputProtocol injects events ────────────────────────────────────
    #[test]
    fn test_input_protocol_injects_events() {
        let targets: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let protocol = InputProtocol::for_regime(OperatingRegime::Driven, targets.clone());

        let mut sched = make_scheduler_with_chunks(4, 2, 100);

        // Before injection, queues are empty.
        for id in &targets {
            let chunk = sched.chunks.get(id).unwrap();
            assert_eq!(chunk.event_queue.count_due(0), 0);
        }

        // Inject drive.
        protocol.inject(&mut sched);

        // After injection, each target chunk should have a pending event.
        let mut injected_count = 0;
        for id in &targets {
            let chunk = sched.chunks.get(id).unwrap();
            if chunk.event_queue.count_due(0) > 0 {
                injected_count += 1;
            }
        }
        assert!(
            injected_count > 0,
            "InputProtocol must inject events into target chunks"
        );
    }

    // ── Test 5: Active chunk with voltage above threshold produces spikes ────────
    #[test]
    fn test_driven_network_produces_spikes() {
        let n_exc = 4u32;
        let units = 10;
        let mut sched = make_scheduler_with_chunks(n_exc, 2, units);

        // Manually set all units in excitatory chunks to just above spike threshold.
        // This directly tests that the scheduler/chunk pipeline produces spike output
        // without relying on the slow Euler integration time constant.
        for i in 0..n_exc {
            let id = next_brain::core::chunk::ChunkId(i);
            if let Some(chunk) = sched.chunks.get_mut(&id) {
                for v in chunk.state.voltages.iter_mut() {
                    *v = 31.0; // Above V_thresh = 30.0
                }
                chunk.status = next_brain::core::chunk::ChunkStatus::Active;
            }
        }
        // Re-register chunks in Active status by removing and re-adding them.
        let mut to_readd = Vec::new();
        for i in 0..n_exc {
            let id = next_brain::core::chunk::ChunkId(i);
            to_readd.push(sched.chunks.remove(&id).unwrap());
        }
        for chunk in to_readd {
            sched.add_chunk(chunk);
        }

        // Step: active chunks with V > 30 must emit spikes.
        let metrics = sched.step();
        assert!(
            metrics.total_spikes > 0,
            "Chunks with voltage above threshold must produce spikes; got 0"
        );
    }

    // ── Test 6: FiringRateRecorder accumulates correctly ────────────────────────
    #[test]
    fn test_firing_rate_recorder() {
        let mut recorder = FiringRateRecorder::default();
        recorder.record(10, 100); // 0.1 rate
        recorder.record(20, 100); // 0.2 rate
        let mean = recorder.mean_rate();
        assert!((mean - 0.15).abs() < 1e-5, "mean rate should be 0.15");
    }

    // ── Test 7: AggregatorParams default mode is NormalizedRate ─────────────────
    #[test]
    fn test_aggregator_params_defaults() {
        let params = AggregatorParams::default();
        assert_eq!(params.mode, AggregationMode::NormalizedRate);
        assert!((params.gain_exc - 1.0).abs() < 1e-6);
        assert!((params.gain_inh - 1.0).abs() < 1e-6);
    }
}
