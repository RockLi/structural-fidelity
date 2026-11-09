Fixed-support family certificate prototype — incremental archived-data package

Start with REPORT.zh.txt and THEORY-AND-METHODS.txt. PROTOCOL.txt was fixed
before coverage results. No manuscript or original reproduction package changed.

Requirements
Python3 with NumPy; C11 compiler. Recorded environment: Python3.13.5,
NumPy2.5.4, Apple clang21.0.0, arm64 Darwin. Both rigorous certifiers and all
point baselines are compiled from kernel.c in one translation unit with
-O3 -std=c11 -fno-fast-math -ffp-contract=off.
No new dependencies were installed; no Rust simulation run is required.

Keep directory at research/experiments/finite-horizon-family-prototype-20261108
within the existing repository, with these unmodified dependencies:
research/experiments/finite-horizon-certificate-audit-20261108/
research/experiments/finite-horizon-certificate-cost-20261108/
output/local-circuit-preprint-20261026-final-review/
The earlier audit contains the reference loading/runtime validation code and
original evidence paths. This ZIP does not duplicate that large input corpus.
Absolute provenance paths refer to the original checkout. Relocating requires
regenerating run hashes in the same relative repository layout.

From this directory, with the Python environment active:
clang -O3 -std=c11 -fno-fast-math -ffp-contract=off -dynamiclib kernel.c -o kernel.dylib
python -B prototype.py --output-dir /tmp/family-fresh1 --rounds 11 --batch 20
python -B prototype.py --output-dir /tmp/family-fresh2 --rounds 11 --batch 20
python -B analyze.py --results /tmp/family-fresh1
python -B analyze.py --results /tmp/family-fresh2
python -B oracle.py --coverage /tmp/family-fresh1/coverage.csv --output /tmp/family-oracle.json

Each run directory must be absent. The oracle takes several minutes and is NOT
part of the timing comparison. Do not run compute-intensive oracle validation
concurrently with timed benchmarks. The recorded benchmark processes ran
sequentially, separately from the exact oracle.

For a complete clean rebuild of the included layout, copy this audit directory,
move aside results/, repeat/, enclosures/ and generated validation outputs, then
run prototype.py with --output-dir results and --output-dir repeat, analyze.py
on each, oracle.py on results/coverage.csv writing oracle-validation.json, then:
python -B witnesses.py
python -B activity_context.py
python -B verify.py

witnesses.py only rechecks the already-evaluated grid of the largest passing
boxes and saves state diversity/enclosures; it adds no parameter conditions.
verify.py compares INCLUDED results vs repeat and checks prior evidence hashes.
A new binary can have a different build hash: regenerate provenance rather
than silently overwriting included binary data and claiming unchanged hashes.

Files
- kernel.c: previous exact-singleton filter/replay, affine family construction,
  support-function and certified-corner envelope methods, native point batches.
- prototype.py: immutable data preparation, parameter-entry checks, all57cases,
  fixed radii/dimensions, containment/Python replay tests and fair benchmarks.
- oracle.py: independent exact Fraction affine coefficients and rounding radii.
- analyze.py: coverage curves, failure witnesses, largest tested passing boxes,
  paired costs (one box per case to avoid repeated-radius aggregation bias).
- witnesses.py: all40 largest-box enclosures and distinct state trajectories.
- activity_context.py: post-hoc spiking/silent context from saved reference flags.
- verify.py: repeat comparison and original audit/preprint integrity.
- results/,repeat/: coverage.csv, samples.csv, timings.csv, summary.json,
  singleton-regression.csv, families.json, analysis.json, largest-regions.csv,
  code-sha256.json. Method IDs are listed in summary.json.
- oracle-validation.json:93 exact-rational checked conditions.
- enclosures/*.npz: support/corner post-step bounds (600rows, columns
  vlo,vhi,gElo,gEhi,gIlo,gIhi), fixed-grid states (points,600rows,3variables),
  parameter coordinates and complete input arrays used by the local checker.
  Target-major ordering: first300rows target0, next300rows target1. These are
  reproducible computed enclosures, not standalone proof-assistant objects.
- state-diversity.json,validation.json,MANIFEST.json: validation summaries.

Quantization and guarantee boundary
The family specifies correctly rounded binary32 weights of ideal affine real
parameters. The C point_events helper has been checked against exact rational
rounding for the fixed dyadic grid used here; do not assume arbitrary supplied
binary64 coordinates have the same entry semantics without validating them.
Use the Fraction-based nearest-even conversion in the old audit for general
rational parameter coordinates. The global family error bound covers ideal
parameter values abstractly; point sampling is not its proof.

The box guarantee includes all its members, but only for the original fixed
input/initial state/runtime/horizon and shared support. Continuous states may
differ. Guard failures are inconclusive until a specific branch-failing point
is supplied. Every failed preset box in this run has such a corner witness;
this does not prove untested thresholds or boundaries are exact. No adaptive
radius search or region splitting was performed. Ordinary corner/grid sampling
has a weaker guarantee than either rigorous method; its faster timing is not
an equal-guarantee speed comparison. General low-dimensional support-function
optimization is established mathematics, not a new theoretical contribution.
