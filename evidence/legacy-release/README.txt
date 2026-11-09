Input Dependent Structural Fidelity in Chunk Coupled Spiking Networks
Xinjun Li — NEXT BRAIN LTD
Bilingual preprint and complete local evidence package — final editorial polish, 9 November 2026

FINAL EDITORIAL POLISH
The abstract is focused (190 English words), retaining 9/19 controlled-input
switches and 16/17 archived certified cases. It reports the actual paired-dose
means without interpreting normalized L1 = 1 as decorrelation or saturation.
The matched-focal temporal comparison has one switch and 18 unchanged binary
labels: a counterexample to exact sufficiency, not evidence of frequent switching.
Numeric lists, inline mathematical subscripts and proof delimiters are corrected.
No new simulation, radius search, graph seed or scientific condition was added.

CURRENT MANUSCRIPTS
manuscript/local-circuit-aggregation-preprint-en.docx and .pdf
manuscript/local-circuit-aggregation-preprint-zh.docx and .pdf

This release incorporates three completed studies: post hoc score-factor/coverage
analysis; post hoc paired-dose composition in ten random chains; and the locked
controlled-input experiment. It adds no experiment during manuscript preparation.
The input experiment had previously added 60 network/input and 912 direction/input
conditions; its 1,520 total direction conditions overlap 608 earlier conditions.
No new original graph seed or neuron kernel has been introduced. Negative
selection decisions, frozen-input transfer losses, unresolved orders, proof gaps,
cap censoring and two refinement-limit conditions are retained.

科学主张
同图、30ms的输入控制显示：逐槽匹配总驱动，以及逐节点输入幅值多重集保持，
均不足以确定固定修改的脉冲效应或方向安全次序。评分的联合因子优势只针对
可分辨方向对，依赖当前参考动态；配对剂量显示差异总量与时间抵消可不同步，
存在非单调负结果。没有宣称普遍剂量定律、跨模型预测或无参考迁移成功。

PACKAGE STRUCTURE
manuscript/       Current editable sources, figures, DOCX/PDF, label maps.
research/experiments/
  finite-horizon-certificate-audit-20261108     singleton and exact oracle
  finite-horizon-certificate-cost-20261108      native cost and replay comparison
  finite-horizon-family-prototype-20261108      set coverage and validation
  paired-direction-mechanism-20261108           original 912-direction study
  score-factor-coverage-audit-20261108          offline factors and coverage
  paired-dose-composition-20261108             thirty trajectories, ten chains
  input-control-directions-20261108            locked inputs, runs and radii
output/local-circuit-preprint-20261026-final-review/
                  Complete immutable earlier source/evidence dependency.
validation/       Current content, reanalysis, visual QA and lineage checks.

Historical reports saying 'no manuscript edit' describe their original audit
stage. This release now integrates their results. Historical absolute paths,
compiler records and prior README claims remain provenance within immutable
subpackages; this root README describes the current release. No public archive
identifier, public repository or publication is asserted.

DEFAULT REPRODUCTION: NO NEW SIMULATION
In this complete extracted package, using separate document and scientific Python:

/path/to/document/python3 -B reproduce_current.py \
 --simulation-python /path/to/scientific/python3 \
 --output-dir /tmp/preprint-analysis-fresh

The destination must not exist. Document Python requires python-docx; scientific
Python requires NumPy and Matplotlib. The historically named --simulation-python
argument selects the scientific interpreter; this entry point does NOT simulate.
It recomputes the factor and dose CSVs from archived data, reconstructs controlled
input scores, reads archived radius bounds, regenerates all incorporated tables
and the new figure, and builds both manuscripts. CSVs, numerical JSON and document
XML/images must agree with the deposit. There is no numerical archive fallback
following a failed recomputation. Time/path provenance fields are checked separately.
Existing source/plot figures for earlier studies remain immutable dependencies.
The new figure is regenerated from the recomputed input-control summaries.

REPEATING THE PREVIOUS EXPERIMENTS
The study scripts and protocols document full network, certificate and family
repetition. These are separate from the default analysis-only command. The root
reproduce_legacy_directions.py retains the older 912-condition workflow. The input
folder's network.py and directions.py support fresh destinations; never overwrite
archived runs or modify locked scientific settings. Current editorial validation
does not run these simulations. Historical technical repeats remain in the package.

Native libraries target Apple arm64 Darwin. C compilation uses clang -O3 -std=c11
-fno-fast-math -ffp-contract=off -dynamiclib; source is included. Rebuild only in a
working extraction, then validate the finite nearest-even IEEE contract, gradual
underflow and fixed operation order. Cross-platform bitwise agreement is not
promised. Neural trajectory provenance: Rust 1.98.1, edition 2024, opt-level 3.
Document authoring/render runtime and fonts are recorded in validation/.

PDF AND NUMERIC QA
Use the bundled document render_docx.py and bundled LibreOffice, with the provided
macOS fontconfig file on compatible systems. PDFs are generated from final DOCX,
and every rendered page is visually inspected. Fonts can change pagination on
other platforms. Internal PNG render folders are excluded from the final ZIP.
python3 -B verify_release.py checks all immutable manifests, references, equations,
bilingual labels and numeric table values. It includes independently recomputed
dose means and visibility counts. This does not replace visual page inspection.
python3 -B package_release.py writes the source/evidence ZIP and verifies every
member's SHA256 plus ZIP CRC. package-sha256.json records current release content.

METRIC NAMING
The input-control network-metrics.csv field Dglobal means population-pooled
per-slot L1 in that archive. The manuscript's D_global in the temporal-first
composition denotes absolute whole-window population count difference. The
new input-control tables use spike equality and direction brackets, not that
archive field; the dose tables use the explicit Dslot/Dcount definitions.
All normalized L1 denominators and undefined zero-error ratios remain explicit.
