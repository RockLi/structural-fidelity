Evidence package — local-circuit major revision, 22 October 2026

TOOLCHAIN UPDATE
Explicit rustc 1.98.1 validation is archived in toolchain-1.98.1/. It passes
86 tests (one ignored), and all 111 diagnostic records match the initial run.
The descriptions and logs below record the initial 1.86 reproduction. The
portable driver now defaults to explicit rustup toolchain 1.98.1, not PATH rustc.

E3 ZERO RETENTION EXTENSION
The separate e3-zero-retention/ directory contains an additive Rust test, a
raw-sum output-only patch, six endpoint/bridge records, per-slot CSVs and build
provenance. scripts/reproduce_e3_zero.py builds isolated frozen-source copies
with explicit rustc 1.98.1. The 0% policy selects no edges; the 2.0% bridge uses
the original threshold 2.0. All three bridge methods reproduce the old records.
The original 55-file source manifest and 111 diagnostic rows remain unchanged.
Rebuild to a new or empty output directory:
python3 PATH/TO/evidence/scripts/reproduce_e3_zero.py --output-dir /tmp/e3-zero-results

AUTHORITATIVE SOURCE
original/source is the exact 55-file frozen source from
/Users/rock/workspace/bettiai/brian2/next-brain.
The parent Git SHA is metadata only: this Rust subdirectory was untracked.
Use original/source-sha256.json to identify the source. Source was not modified.

UNMODIFIED REPRODUCTION
86 tests passed, 1 deliberately ignored 500k test; no 100M/500k run.
The standalone stateful closure was also run successfully.
Toolchain: rustc1.86.0, Apple arm64 Darwin; optimization -C opt-level=3;
tests ran sequentially with --nocapture --test-threads=1.
Cargo offline failed on a missing Criterion dev dependency in the initial
older source path; see build-environment/. Because the core has no runtime
dependencies, the authoritative source was compiled directly with rustc.
This is not a claim that cargo test completed.

LAYOUT
original/source/              Frozen source/build/test files, no binaries
original/logs/                Unmodified test commands and full outputs
original/metrics-rounded.*    72 transcript-derived result rows
original/gain-calibration-rounded.csv  36 legacy/stateful calibration rows
original/trajectory-exports/  Existing 300-slot trajectory outputs
original/unit-invalid-psd-exports/  Historical PSD output; units are invalid

diagnostics/primary-comparison-exact.*   24 rows:8 settings x3 variants
diagnostics/diagnostic-results-exact.*  111 rows, including unchanged legacy rows
diagnostics/gain-calibration-exact.*    54 gain-grid rows:18 per variant
diagnostics/{variant}/logs/             Full control logs
diagnostics/{variant}/patches/          All post-hoc isolated edits
diagnostics/{variant}/manifests/        Source hashes for each control

audits/  Reproduction memo, methods audit, independent control review,
         and a supplementary results/figure provenance audit
scripts/reproduce.py  Portable source verification, rebuild and run driver
scripts/historical/  Original /tmp-path scripts retained for transparency

REBUILD
From any directory with Python3, rustc (edition2024 support) and patch:
python3 PATH/TO/evidence/scripts/reproduce.py --mode original
python3 PATH/TO/evidence/scripts/reproduce.py --mode raw_sum
python3 PATH/TO/evidence/scripts/reproduce.py --mode original_instrumented
python3 PATH/TO/evidence/scripts/reproduce.py --mode kappa_only
Optional --work-dir points to a new or empty directory. Default creates a new
temporary directory. No build output is placed in the frozen source.
The ignored500k test remains ignored. On other compilers or architectures,
small floating point differences may occur.

CONTROL INTERPRETATION
raw_sum replaces stateful output with the current raw weighted E/I sums,
preserving the one-slot delay. It matched every per-slot population spike
count in all audited E1/E3/E4/E5 configurations. These checks do not establish
per-neuron spike, membrane voltage or internal state identity.
kappa_only retains near-unit static gain factors and removes history output
modulation. original_instrumented changes measurements only.
Inherited log labels still say4ch+trace: use the variant column to distinguish
controls. Neither control is held-out validation or an optimized speed test.

KAPPA CONTINUATION
The first kappa-only run failed the historical39-Hz PSD assertion; preserve
and inspect kappa_only/logs/closure.log. The complete diagnostic patch turns
only that already-invalid-unit assertion into a logged warning so E4/E5 can
run. closure-complete.log success does not mean the original assertion passed.
To reproduce the original failure:
python3 PATH/TO/evidence/scripts/reproduce.py --mode kappa_only --stage initial

PSD WARNING
The source passes dt=.001 as milliseconds to simulation and as seconds to
spectral analysis. Reported frequency labels are1000x too small. The39-Hz
label cannot substantiate biological gamma recovery. Spectral exports here
are historical records, not corrected scientific spectra.

MEASUREMENT LIMITS
Exact integer counts accompany nine-decimal printed floating metrics.
Event counts are recurrent queue injections, excluding external drive;
event savings are not wall-time speedups. Current data contain deterministic
single configurations, no independent-seed confidence intervals.
Packaged table source_log fields are relative to this evidence directory.
Historical raw logs/scripts and audit memos retain original absolute paths.
