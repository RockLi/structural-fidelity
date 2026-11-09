Cross-generator validation, 2026-11-09

Start with REPORT.zh.txt, PROTOCOL.txt and analysis/summary.json. This is a
separate experiment. It does not replace the frozen preprint or the earlier
multigraph-input-validation-20261109 study.

Design: six fixed original graphs, two new affinity laws sharing a weighted
sampling-without-replacement implementation, exact projection-arm counts.
Same frozen synchronized numerical kernel and five inherited input event tables.
600 scientific full-network conditions; 35 technical reference/bridge runs.
112 distinct target pairs, 16 fixed weight directions, five inputs: 8960 radius
conditions. Input/target/direction comparisons are dependent within each graph.

Protocol locked before new dynamics; design lock includes generated graphs,
source, events and pools. All-score-lock.json was written for ALL six graphs
before any radius search. An integrity-reader adapter fix before dynamics is
recorded in adapter-fix.json and the prior design lock is preserved. This only
fixes reading a flat pre-existing manifest; no scientific changes.

Local dependencies and reproduction
The scientific interpreter was:
/Users/rock/workspace/bettiai/next-brain/experiments/flywire_poc/.venv/bin/python
Compiler: rustup run 1.98.1 rustc --edition=2024 -C opt-level=3.
Source Rust library and driver are included. Native certificate/point kernels
and independent oracle are reused from sibling experiment directories named in
dependencies.json; their exact hashes are checked. They are dependencies, not
new results, and must remain accessible in the same relative study layout.
This is not a self-contained publicly archived package or an archival DOI.

To reproduce scientific runs, first create a NEW sibling working directory,
copy only source/, root code files, PROTOCOL.txt and protocol-lock.json, and the
six seed*/events directories (no generated graphs/runs/directions/locks/results).
Do not run prepare in this sealed directory. The new directory needs the same
sibling frozen dependencies. Run with -B:
  study.py prepare
  study.py networks
  audit_outputs.py
  study.py scores
  study.py radii
  summarize.py
  plot_summary.py
  audit_ranks.py
  verify.py
  report.py
The run records compiler/environment and all commands. Cost measurements are
Python-wrapped same-case comparisons, not optimized native-batch speed claims.
Independent audits check graph invariants and metric reductions; this is not a
second full rerun of the entire 600-condition experiment. Every original/input
is repeated exactly; seed99 bridging uses all five archived inputs.

Certification semantics
Positive lower radii are common-branch guarantees for all parameters in the
specified one-dimensional joint-weight interval, fixed support and finite
horizon. Endpoints alone do not certify the interval. Upper witnesses demonstrate
an actual branch/spike violation. Failure to prove is not a counterexample.
Proof gaps, censored caps and numerical zero-width failures are retained.
The lower radius is not a maximum safe radius or a multidimensional volume.
Continuous internal states need not remain close.

Integrity
verification.json checks protocol/design/score/dependency locks and every lower
certificate / upper witness provenance. MANIFEST.json covers completed study files;
integrity.json records the manifest hash and exclusions. Prior experiment file
hashes and frozen preprint DOCX/PDF/ZIP hashes are rechecked. No manuscript edits.
