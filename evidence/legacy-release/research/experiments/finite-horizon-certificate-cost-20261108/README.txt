Finite-horizon certificate cost audit — frozen 57-case archived dataset

Read REPORT.zh.txt for results and decision; IMPLEMENTATION.txt for the exact
filter equivalence argument and measurement boundaries. This is an incremental
cost-audit package, NOT an updated preprint or self-contained network dataset.

Dependencies: Python3 + NumPy; a C11 compiler with IEEE binary32/binary64;
macOS build command below. Tests recorded with Python3.13.5, NumPy2.5.4,
Apple clang21.0.0 on arm64. No Rust code was modified. The bundled dylib is only
for the recorded platform; rebuild from source before using elsewhere. Results
on another backend require revalidation; no cross-platform equivalence claim.

Keep this directory in research/experiments/ alongside:
  finite-horizon-certificate-audit-20261108/
and preserve the existing repository-relative evidence directory:
  output/local-circuit-preprint-20261026-final-review/
The earlier audit imports these paths. Original candidate outcome archives are
read ONLY after each certificate is decided, for validation. No simulator runs.

From this directory, with the suitable Python environment active:

clang -O3 -std=c11 -fno-fast-math -ffp-contract=off -dynamiclib kernel.c -o kernel.dylib
python -B check_arithmetic.py arithmetic-fresh.json
python -B run.py --output-dir /tmp/certificate-cost-fresh-1 --rounds 11 --batch 100
python -B run.py --output-dir /tmp/certificate-cost-fresh-2 --rounds 11 --batch 100
python -B verify.py

Output directories must not already exist. run.py includes exact endpoint and
point-replay checks in every run. verify.py checks the INCLUDED results/ and
repeat/ directories against each other, the prior stored decisions and original
file manifests. To verify newly generated runs with verify.py, work in a fresh
copy of this cost directory, moving aside the included results and repeat then
use those names for the new runs. Recorded absolute source paths in hash files
refer to the original checkout; relocation requires regenerating results/hash
files in the original relative repository layout. A rebuilt binary may change
its hash, invalidating comparison with included binary provenance; this is an
expected distinction between reproducing checks and preserving the old binary.

Timing outputs:
- cases.csv: every case, guard outcomes/counters, shared prep, graph I/O,
  original exact checker, native certificate and native replay costs.
- timings.csv: every alternating round's C-batched per-call kernel time.
- summary.json: separate aggregates for all57, target17, certified_nonzero16,
  setup costs, endpoints/decision digests, environment and assumptions.
- code-sha256.json: exact code/binary/protocol/old-theory input provenance.
- arithmetic.json: adjacent-float and fallback verification results.
- validation.json: repeated-result comparison + immutable evidence hashes.
- MANIFEST.json: hashes of this audit package's files; archive-integrity.json
  separately records the incremental ZIP digest (not included inside itself).

Do not compare the original Python oracle timing to native point replay as
algorithmic evidence. The principal fair comparison is native certificate vs
native point replay with shared prepared inputs and matched full-horizon work.
Both must amortize or pay the reference setup. Kernel-only and preparation-
inclusive measurements answer different questions; retain both.
