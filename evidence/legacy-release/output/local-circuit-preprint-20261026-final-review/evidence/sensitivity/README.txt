Minimal legal rewiring and initial-condition sensitivity calibration
24 October 2026 — staged experimental package

This is a bounded follow-up to the homogeneous 125-chunk, 300-slot explicit
rewiring study. It keeps the model, input protocols and event scheduling fixed.
One original graph is used; conditions and time slots are not independent graphs.

The prospective protocol specifies 231 new scientific conditions: three original
baselines, 19 single legal swaps across three inputs (57), and 19 balanced initial
voltage directions at three small doses across three inputs (171). Six technical
sham runs are counted separately. The 57 older extensive-rewiring trajectories
and three older originals are archived inputs, reanalysed rather than counted as
new simulations. No output-based seed or amplitude selection is allowed.

Each swap changes the targets of exactly two edges in one E/I projection arm.
The source, edge-list row, weight bits and delay remain fixed. Per-node per-arm
in/out degrees, strengths and weight multisets are exact. EE/EI/IE/II allocation
is 5/5/5/4. A single swap removes 2/2845 original adjacencies (0.07030%); the
symmetric difference contains four edges. This is a local sensitivity intervention,
not a uniformly randomized graph or evidence of Markov-chain mixing.

Initial voltage doses are 1e-4, 1e-3 and 1e-2 in uncalibrated model coordinates.
Signs balance separately across E and I chunks; all 100 units in a chunk still
share their initial voltage. No wake-up events are added. Every initial voltage
and first actual execution is recorded in bits. Leakage and resets can remove
the initial difference; zero spike error would not prove general stability.

Reproduction (Python with NumPy and Matplotlib, rustup toolchain1.98.1):
  python3 -B reproduce.py --output /tmp/sensitivity-fresh --compare-reference

Use a nonexistent output directory outside this package. The driver recompiles
the copied frozen Rust source using edition2024 and optimization level3, runs all
231 conditions plus six technical shams, verifies count/state outputs, recomputes
analysis and figures, and checks against recorded results. There is no archived
result fallback. First-run stages are study.py prepare/run/verify, analyze.py,
audit.py, and plot.py. The protocol and all source/input files are hashed before
any simulation; initialization-only checks do not advance the model.

The primary comparison uses the same 1ms spike-count bins and normalization as
the earlier study. Population/chunk ratios are computed per trajectory before
summarizing; zero chunk error gives an undefined ratio. Original-reference channel
scales remain fixed for state diagnostics. Shared-source input differences mark
which swaps are actually driven within the observation window (source slots0:298
arrive by slot299 under the inherited n+2 routing rule). All values, zero counts,
medians and ranges are descriptive, conditional on the fixed original and inputs.

Source and data provenance are given by inherited-inputs-sha256.json and the
unchanged historical records in legacy/. The source already contains the earlier
documented canonical-source routing and raw-output-control additions. This study
uses only explicit routing and makes no new changes to the library.
