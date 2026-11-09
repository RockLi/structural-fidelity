Execution-boundary fixtures (post-hoc, open-loop)

Purpose: test delivery conditions with the actual frozen Rust Scheduler and Chunk.
These fixtures do not repeat the E1/E3 network experiments and do not establish
full-state equality for those experiments. They are not performance benchmarks.

Canonical reproducible results: final-run/records.json and final-run/summary.csv.
Full per-slot, per-chunk, per-unit float bits: final-run/slots/*.csv.
Protocol, event lists, compiler identity, commands and hashes are in final-run/.
All chunks are explicitly initialized Dormant; Chunk::new otherwise uses Active.
Slots are zero based. Each row is recorded AFTER processing that slot.

Reproduce from the package root:
  python3 evidence/scripts/reproduce_execution_boundaries.py --output-dir /tmp/new-boundary-results
The output directory must be new or empty. The default toolchain is rustc 1.98.1,
edition 2024, opt-level 3. The driver copies and verifies all 55 frozen files,
adds only the new integration test, and never patches the frozen implementation.

Five correct controls preserve all recorded f32 state bits, refractory deadlines,
spike flags, chunk step decisions, statuses and earliest pending slots. Three
deliberate violations illustrate dropping a zero wake-up, merging E/I channels,
or moving input across arrival slots. The latter two retain original destination
wake-slot support, so the intended condition is isolated. Message multiplicity
and queue representations are intentionally permitted to differ.

The initial run/ directory retains the preliminary successful execution using
the identical Rust fixture before descriptive case IDs/protocol/summary.csv were
added to the runner. final-run/ is the release result and matches the current
runner hash. No fixture was retuned between these executions.
