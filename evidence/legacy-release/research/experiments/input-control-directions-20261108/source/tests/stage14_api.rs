//! Integration tests for Stage 1.4: Minimal Model API
//!
//! Tests the full pipeline:
//!   RegionSpec + PopulationSpec → NetworkBuilder → CompiledLayout → Simulation
//!
//! These tests do NOT use criterion — they are correctness tests, not benchmarks.

#[cfg(test)]
mod stage14_integration {
    use next_brain::layout::{
        NetworkBuilder, NeuronType, PopulationSpec, RegionId, RegionSpec, Simulation,
    };

    // ── Test 1: Basic compilation ──────────────────────────────────────────
    #[test]
    fn test_compile_single_region() {
        let layout = NetworkBuilder::new()
            .with_chunk_size(1_000)
            .add_region(
                RegionSpec::new("V1", "Primary Visual Cortex")
                    .add_population(PopulationSpec::new("V1_exc", RegionId::new("V1"), 10_000))
                    .add_population(PopulationSpec::new("V1_inh", RegionId::new("V1"), 2_500)),
            )
            .compile()
            .expect("compile should succeed");

        // V1_exc: 10,000 units → 10 chunks of 1,000
        // V1_inh: 2,500 units → 2 full chunks + 1 partial chunk of 500
        assert_eq!(layout.chunks.len(), 13, "expected 10 + 3 chunks");
        assert_eq!(layout.total_units, 12_500);

        let exc = layout
            .find_population("V1_exc")
            .expect("V1_exc should exist");
        assert_eq!(exc.num_chunks(), 10);
        assert_eq!(exc.total_units(), 10_000);

        let inh = layout
            .find_population("V1_inh")
            .expect("V1_inh should exist");
        assert_eq!(inh.num_chunks(), 3); // 2 full + 1 partial
        // total_units() must return the real count, not 3 * 1000 = 3000.
        assert_eq!(
            inh.total_units(),
            2_500,
            "partial tail chunk must not inflate total_units"
        );
    }

    // ── Test 2: Multi-region compilation ──────────────────────────────────
    #[test]
    fn test_compile_multi_region() {
        let layout =
            NetworkBuilder::new()
                .with_chunk_size(500)
                .add_region(
                    RegionSpec::new("LGN", "Lateral Geniculate Nucleus").add_population(
                        PopulationSpec::new("LGN_relay", RegionId::new("LGN"), 5_000),
                    ),
                )
                .add_region(
                    RegionSpec::new("V1", "Primary Visual Cortex")
                        .add_population(PopulationSpec::new("V1_L4", RegionId::new("V1"), 50_000)),
                )
                .compile()
                .expect("multi-region compile should succeed");

        // LGN: 5,000 / 500 = 10 chunks
        // V1:  50,000 / 500 = 100 chunks
        assert_eq!(layout.chunks.len(), 110);
        assert_eq!(layout.total_units, 55_000);

        // Chunk IDs should be globally contiguous.
        let lgn = layout.find_population("LGN_relay").unwrap();
        let v1 = layout.find_population("V1_L4").unwrap();
        assert_eq!(lgn.chunk_id_start, 0);
        assert_eq!(lgn.chunk_id_end, 10);
        assert_eq!(v1.chunk_id_start, 10);
        assert_eq!(v1.chunk_id_end, 110);
    }

    // ── Test 3: per-population chunk-size override (Phase 2 permissive path) ─
    #[test]
    fn test_population_chunk_size_override() {
        // Phase 2 permissive builder: allows heterogeneous chunk sizes.
        let layout = NetworkBuilder::new_permissive()
            .with_chunk_size(1_000)
            .add_region(RegionSpec::new("R", "Test Region").add_population(
                PopulationSpec::new("small_pop", RegionId::new("R"), 3_000).with_chunk_size(500),
            ))
            .compile()
            .unwrap();
        // 3,000 units / 500 per chunk = 6 chunks.
        assert_eq!(layout.chunks.len(), 6);
    }

    // ── Test 4: Build error — empty population ─────────────────────────────
    #[test]
    fn test_error_on_empty_population() {
        let result = NetworkBuilder::new()
            .add_region(
                RegionSpec::new("R", "bad").add_population(PopulationSpec::new(
                    "empty_pop",
                    RegionId::new("R"),
                    0,
                )),
            )
            .compile();

        assert!(result.is_err(), "should error on zero-unit population");
    }

    // ── Test 5: Build error — empty model ─────────────────────────────────
    #[test]
    fn test_error_on_empty_model() {
        let result = NetworkBuilder::new().compile();
        assert!(result.is_err(), "should error on empty model");
    }

    // ── Test 6: Simulation — dormant step loop ─────────────────────────────
    #[test]
    fn test_simulation_dormant_loop() {
        let layout = NetworkBuilder::new()
            .with_chunk_size(1_000)
            .add_region(
                RegionSpec::new("V1", "Visual Cortex").add_population(PopulationSpec::new(
                    "V1_exc",
                    RegionId::new("V1"),
                    100_000,
                )),
            )
            .compile()
            .unwrap();

        let mut sim = Simulation::from_layout(layout, 0.001);

        // Run 10 steps on all-dormant network.
        let metrics = sim.run(10);

        // All chunks should be dormant: no active chunks, no spikes.
        assert_eq!(metrics.steps_completed, 10);
        assert_eq!(metrics.active_chunks, 0, "all chunks should be dormant");
        assert_eq!(
            metrics.total_spikes, 0,
            "no spikes expected in dormant state"
        );
        assert_eq!(sim.current_slot(), 10);
    }

    // ── Test 7: CompiledLayout memory report ──────────────────────────────
    #[test]
    fn test_memory_bytes_reporting() {
        let layout = NetworkBuilder::new()
            .with_chunk_size(1_000)
            .add_region(
                RegionSpec::new("R", "Test").add_population(PopulationSpec::new(
                    "p",
                    RegionId::new("R"),
                    10_000,
                )),
            )
            .compile()
            .unwrap();

        // 10,000 units × 32 bytes/unit = 320,000 bytes
        // (6 × f32=4B + 1 × u64=8B = 32 bytes per unit)
        let expected_bytes = 10_000 * 32;
        assert_eq!(layout.state_memory_bytes(), expected_bytes);

        // Summary should be non-empty.
        assert!(!layout.summary().is_empty());
    }

    // ── Test 9 (regression): partial-chunk population reports correct total_units ─
    #[test]
    fn test_partial_chunk_total_units_accuracy() {
        let layout = NetworkBuilder::new()
            .with_chunk_size(1_000)
            .add_region(
                RegionSpec::new("R", "Test").add_population(PopulationSpec::new(
                    "p",
                    RegionId::new("R"),
                    1_500,
                )),
            )
            .compile()
            .unwrap();

        let pop = layout.find_population("p").unwrap();
        // 1,500 units with 1,000/chunk → 2 chunks (1 full + 1 of 500).
        assert_eq!(pop.num_chunks(), 2);
        // Must be 1,500, not 2 * 1,000 = 2,000.
        assert_eq!(pop.total_units(), 1_500);
        // State bytes: 1,500 units × 32 bytes/unit.
        assert_eq!(layout.state_memory_bytes(), 1_500 * 32);
    }

    // ── Test 10 (regression): sub-chunk allocation in SyntheticChunkAllocator ─
    #[test]
    fn test_allocator_partial_last_chunk() {
        use next_brain::layout::allocator::SyntheticChunkAllocator;

        // 2,500 units with chunk size 1,000 → 2 full + 1 partial (500).
        let alloc = SyntheticChunkAllocator::new(2_500, 1_000, 10.0);
        assert_eq!(alloc.num_chunks(), 3);
        assert_eq!(alloc.remainder_units(), 500);

        let chunks = alloc.build();
        assert_eq!(chunks.len(), 3);
        // Last chunk must contain remainder units, not a full 1,000.
        assert_eq!(chunks[2].state_memory_bytes(), 500 * 32);
        // expected_state_bytes must match actual total.
        assert_eq!(
            alloc.expected_state_bytes(),
            chunks.iter().map(|c| c.state_memory_bytes()).sum::<usize>()
        );
    }

    // ── Test 11 (regression): duplicate population labels rejected ───────────────
    #[test]
    fn test_error_on_duplicate_population_label() {
        let result = NetworkBuilder::new()
            .add_region(
                RegionSpec::new("A", "Region A").add_population(PopulationSpec::new(
                    "exc",
                    RegionId::new("A"),
                    1_000,
                )),
            )
            .add_region(
                RegionSpec::new("B", "Region B")
                    // Same label "exc" as above — must be rejected.
                    .add_population(PopulationSpec::new("exc", RegionId::new("B"), 1_000)),
            )
            .compile();

        assert!(
            result.is_err(),
            "duplicate population label should be rejected"
        );
        let err_msg = result.unwrap_err().to_string();
        assert!(
            err_msg.contains("exc"),
            "error message should name the duplicate label"
        );
    }
    // ── Test 8: NeuronType on spec ─────────────────────────────────────────
    #[test]
    fn test_neuron_type_assignment() {
        let pop = PopulationSpec::new("p", RegionId::new("R"), 1_000)
            .with_neuron_type(NeuronType::LeakyIntegrateFire);
        assert_eq!(pop.neuron_type, NeuronType::LeakyIntegrateFire);
    }

    // ── Test 12 (regression): strict mode (new()) rejects / permissive (new_permissive()) allows ─
    #[test]
    fn test_strict_mode_rejects_heterogeneous_chunk_size() {
        // new() is strict by default — override must be rejected.
        let strict = NetworkBuilder::new()
            .with_chunk_size(1_000)
            .add_region(RegionSpec::new("R", "Test").add_population(
                PopulationSpec::new("p", RegionId::new("R"), 3_000).with_chunk_size(500),
            ))
            .compile();
        assert!(
            strict.is_err(),
            "new() must reject heterogeneous chunk sizes"
        );
        let msg = strict.unwrap_err().to_string();
        assert!(
            msg.contains("500"),
            "error should mention the override size"
        );
        assert!(
            msg.contains("1000"),
            "error should mention the default size"
        );

        // new_permissive() allows the same spec.
        let permissive = NetworkBuilder::new_permissive()
            .with_chunk_size(1_000)
            .add_region(RegionSpec::new("R", "Test").add_population(
                PopulationSpec::new("p", RegionId::new("R"), 3_000).with_chunk_size(500),
            ))
            .compile();
        assert!(
            permissive.is_ok(),
            "new_permissive() must allow chunk-size override"
        );
    }

    // ── Test 13 (regression): count_due accurately counts multiple co-due events ─
    #[test]
    fn test_event_queue_count_due_multi_event() {
        use next_brain::core::chunk::{ChunkEventQueue, ChunkId, DelayedEvent};

        let mut queue = ChunkEventQueue::default();

        // Enqueue three events all due at slot 5.
        for _ in 0..3 {
            queue.push(DelayedEvent {
                target_chunk: ChunkId(0),
                target_slot: 5,
                signal_strength: 1.0,
            });
        }
        // One future event due at slot 10.
        queue.push(DelayedEvent {
            target_chunk: ChunkId(0),
            target_slot: 10,
            signal_strength: 1.0,
        });

        // At slot 5: exactly 3 events are due, not 1.
        assert_eq!(
            queue.count_due(5),
            3,
            "count_due must report all co-due events"
        );
        // At slot 4: none are due.
        assert_eq!(queue.count_due(4), 0);
        // At slot 10: all 4 are due.
        assert_eq!(queue.count_due(10), 4);
    }
}
