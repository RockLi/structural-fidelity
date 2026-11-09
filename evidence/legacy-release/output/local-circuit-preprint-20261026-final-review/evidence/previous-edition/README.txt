Delay Aligned Message Aggregation in a Chunk Coupled Spiking Model
Xinjun Li
NEXT BRAIN LTD
22 October 2026

This package accompanies the English preprint and its complete Chinese counterpart.
Both manuscripts contain four main figures, two supplementary figures, seven tables,
ten references and editable Word equations. The English manuscript is the primary
scientific text. Both languages use the shared bibliography in paper_en.py.

MANUSCRIPTS (delivered separately from the source-and-evidence ZIP)
local-circuit-aggregation-preprint-en.docx
local-circuit-aggregation-preprint-zh.docx

SOURCE AND FIGURES
paper_en.py and paper_zh.py contain the manuscript text and captions.
build_preprint.py and docx_helpers.py generate the DOCX files using python-docx.
plot_preprint.py generates the original five figures from the archived numerical tables.
plot_trajectory_figure.py adds the E3 zero-retention trajectory and difference figure
from existing per-slot evidence, with provenance in trajectory-figure-data.json.
figures/ contains PNG and vector PDF versions of the scientific figures.
figure-data.json links plotted values to the archived result rows.
supplementary_data.py records the complete workload parameters.

COMPLETE REPRODUCTION FROM NEW EXPERIMENT RUNS
Use a Python environment with python-docx, numpy and matplotlib, plus rustup,
the explicitly installed Rust toolchain 1.98.1, and the standard patch command.
The validated Python environment is Python 3.12.14, python-docx 1.2.0,
matplotlib 3.11.2 and numpy 2.5.4; details are in artifact-build-environment.json.
The workflow does not require a Codex runtime or any private installation path.
For example, install the Python dependencies in your own virtual environment:
  python3 -m pip install python-docx==1.2.0 numpy==2.5.4 matplotlib==3.11.2

From this extracted package directory, run:
  python3 evidence/scripts/reproduce_all.py --output-dir /tmp/local-circuit-fresh

The output directory must be new or empty and outside the package. This command
runs the unmodified implementation and all three diagnostic variants, extracts
new numerical tables from their explicit log paths, runs E3 zero-retention and
the eight execution-boundary fixtures, verifies results against the archived
reference, and generates all six figures and both DOCX files from the new data.
The unmodified suite is checked for 86 passing tests and one ignored test.
Use --skip-docx to omit Word generation. Every Rust stage explicitly selects
--toolchain 1.98.1 by default; an alternative compiler is not assumed to give
identical floating-point results.

The new output tree contains:
  runs/{original,original_instrumented,raw_sum,kappa_only}/  isolated sources/builds/logs
  tables/                  72 rounded rows, 111 diagnostic rows, 24 primary rows
  e3-zero/                 six endpoint/bridge records and per-slot measurements
  execution-boundaries/    eight fixtures and complete per-unit state records
  figures/                 six PNG/PDF figure pairs
  documents/               rebuilt English and Chinese DOCX files
  logs/, commands.json     stage commands, exit status and execution logs
  input-sha256.json, output-sha256.json, reference-verification.json,
  pipeline-validation.json and unmodified-test-summary.json

Only new logs supply the main comparison-table values; E3 and fixture tables
are generated directly by their fresh runs. Archived tables are used as an explicit
verification reference, never as a fallback when a run or input is missing.
The fixed manuscript prose and summary table contain this release's numbers;
the pipeline stops if new results differ, rather than claiming those fixed
numbers were automatically rewritten. The E3 bridge checks explicitly use
the newly extracted tables. Source-log paths in new comparison tables are
relative to the output root. Repeated gain-grid center points remain separate.
Commands and input/output hashes make the new evidence traceable after moving
the directory. Build copies and binaries are logistical outputs, not new
performance evidence. DOCX generation is not visual validation: render and
inspect the new documents before publication.

This release's complete workflow was executed from an extracted candidate ZIP
in a path containing spaces. All 12 stages and seven numerical-reference checks
passed. The 72 rounded, 111 diagnostic and 24 primary rows were reconstructed
independently from fresh logs; all six E3 records and eight fixtures agree with
the archive. All six new figure PNGs also match the archived figures byte-for-byte.
The delivered DOCX files are the exact outputs of that run, separately rendered
and checked (English 16 pages; Chinese 17 pages).
See evidence/pipeline-validation/ for the new logs, CSVs, figures, commands,
hashes and independent audit reports. The frozen 55-file Rust source and all
preexisting numerical evidence are preserved unchanged. Final packaging updates
documentation and validation records without changing the executed code.

The extractor can also be called separately with --original-log, one
--variant-log NAME=PATH for each of original_instrumented, raw_sum and
kappa_only, --source-root and --output-dir. It reads no archived result table.
See evidence/scripts/extract_results.py --help for its complete interface.

To redraw only the archived data and rebuild the manuscript without rerunning
experiments (this is a separate, lighter operation):
  python3 plot_preprint.py
  python3 plot_trajectory_figure.py
  python3 build_preprint.py en
  python3 build_preprint.py zh

The build environment is recorded in artifact-build-environment.json. Rendering
used the Codex document renderer with an explicit macOS Fontconfig configuration
so that Songti SC Chinese glyphs and Times New Roman text were available. The
included render_fontconfig_macos.conf is platform-specific, not a font bundle.

EXECUTION CONDITIONS AND VALIDATION REVISION
The proposition now explicitly restricts delivery to input accumulation (apart from
activation bookkeeping), with all due inputs accumulated before neuronal updates.
The manuscript states the strictly positive recurrent-weight scope of E1-E5 and
the extra wake-up markers needed for zero-weight recurrent edges. It also explains
the effective-gain asymmetry and activity dependence of queue-message ratios.

Eight controlled delivery fixtures use the unchanged frozen Scheduler and Chunk
code: five correct controls and three deliberate condition violations. Every
fixture has two chunks, four units per chunk, dt=0.1 ms and 12 slots, with explicitly
dormant initial chunks and preloaded events. These are open-loop execution tests,
not new E1-E5 recurrent-network runs or performance measurements.

Correct controls preserve every observed dynamical-state bit pattern and activation
record. Dropping zero wake-ups, cancelling E/I channels, and moving later input
earlier cause state differences. All three violating fixtures nevertheless retain
the same per-unit spike sequences over the short window. Figures and prose do not
infer that condition violations must change spikes.

Reproduce the fixtures from this package directory:
  python3 evidence/scripts/reproduce_execution_boundaries.py --output-dir /tmp/execution-boundary-results

The canonical results, protocol, compiler and command records, complete per-unit
state CSVs, and hashes are in evidence/execution-boundaries/final-run/. The additive
Rust test is in evidence/execution-boundaries/tests/. Independent reconstruction
of all 768 rows is recorded in evidence/execution-boundaries/independent-validation.json.
The earlier run/ folder records the initial execution; final-run/ is used in the
manuscript. The two runs have identical trajectory CSVs.

EARLIER REFERENCE AND POSITIONING REVISION
The revision adds Lytton (1996), Brette et al. (2007), Albers et al. (2022) and
van Albada et al. (2015). Citations are renumbered by first appearance, identically
in both languages. Proposition 1 states sufficient execution conditions for an
established additive-aggregation principle; it is not a claim of a newly discovered
general aggregation method or exact continuous-time integration. The discussion
distinguishes NEST source-to-process spike compression from destination/channel/
arrival-slot sums, and within-network pairwise correlations from the cross-run
population-count correlation measured here.

reference-validation.json records the bibliography, citation checks and scope of
the unchanged experimental evidence. document-validation.json records structural
and visual checks of the updated manuscripts. The source-and-evidence ZIP includes
every file required by the frozen source manifest, including its listed metadata
file, so strict source verification also succeeds after extracting the archive.

EXPERIMENTAL EVIDENCE
evidence/original/source/ is the frozen Rust source from brian2/next-brain.
evidence/original/source-sha256.json identifies its 55 files.
evidence/diagnostics/ contains comparison summaries, patches and run logs.
evidence/scripts/reproduce.py verifies source hashes and builds isolated copies.

Example reproduction commands, run from this package directory with rustup and toolchain 1.98.1 installed:
  python3 evidence/scripts/reproduce.py --mode original
  python3 evidence/scripts/reproduce.py --mode original_instrumented
  python3 evidence/scripts/reproduce.py --mode raw_sum
  python3 evidence/scripts/reproduce.py --mode kappa_only
  python3 evidence/scripts/reproduce_e3_zero.py --output-dir /tmp/e3-zero-results

The reproduction driver explicitly selects rustup toolchain 1.98.1 by default.
Use --toolchain stable to inspect the host default, or --rustc PATH to select an
exact compiler executable. Each run saves compiler-provenance.json.

These builds use direct rustc compilation. They do not claim that Cargo dependency
resolution succeeded. The complete kappa_only variant replaces an inherited
unit-invalid spectral assertion with a logged warning; the original failure and
patch are preserved. Spectral outputs are excluded from the paper's conclusions.

TOOLCHAIN VALIDATION
The initial reproduction selected the host default rustc 1.86.0. Release
validation explicitly rebuilt the same source using rustc 1.98.1 (LLVM 22.1.8):
86 tests passed and one remained ignored. All 111 diagnostic rows and all
88 unmodified Phase3 metric lines agree with the initial run. Both sets of logs
are preserved; see evidence/toolchain-1.98.1/provenance.json and comparison.json.
The machine default and the source project toolchain were not changed.

E3 ZERO RETENTION EXTENSION
Figure 3 now includes 0% retention for filtered four-channel, history-modulated
and raw-sum delivery. The extension uses the same seed-200 E3 graph, 12,500 units,
200 slots at dt=0.1 ms and sustained input 10. An empty edge-selection policy
aggregates all 2,840 edges; no recurrent messages use the explicit subpath.

The additive test and two-line raw-sum output patch are in
  evidence/e3-zero-retention/patches/
Six records (three zero-retention results and three 2.0% bridge controls),
per-slot population and message counts, commands, logs, compiler provenance,
source hashes and validation checks are in
  evidence/e3-zero-retention/run/
The three bridge controls agree with the historical scan to its archived
precision. The original 111 diagnostic records and 55 source files are unchanged.
The original E3 runner is preserved byte-for-byte at
  evidence/scripts/historical/reproduce_e3_zero_20261022.py
Its SHA matches the scripts/reproduce_e3_zero.py entry in the historical run's
input-sha256.json. The current runner adds explicit reference-table and source-root
arguments for the complete pipeline; historical run records are not rewritten.
The historical script is a provenance snapshot; use the current runner above
for execution because its relative file location is part of the original design.

At 0%, raw sums match all 200 population-count slots and enqueue 15,319 messages
versus 32,247 for the reference (Q=0.475051943). History modulation has r=0.985609,
rate error -2.48996%, Q=0.471950879 and 146 mismatching slots. Filtered four-channel
has r=0.434598, rate error +69.15663%, Q=1.420566254 and 167 mismatching slots.
The extension explicitly uses rustc 1.98.1, edition 2024 and opt-level 3.
Original float32 metrics are preserved, with bit-exact float32 recomputation and
independent float64 checks recorded. Floating summaries do not replace integer
slot-equality checks. These are fixed-seed descriptive results, not new trials
for statistical inference or optimized runtime measurements.

DATA SCOPE
The archive preserves integer spike and queue totals, per-slot mismatch counts,
floating-point summary metrics and reproducible source. The E1-E5 evidence is not a complete
archive of all neural-state trajectories. The additional B1-B8 delivery fixtures
do include per-unit state and activation records, with their narrower scope
explicitly described in the manuscript. The raw-sum and static-gain controls
are exploratory post-hoc analyses. Graph settings have one deterministic
realization; gain-grid points are not independent replicates.

PUBLICATION STATUS
This is an independent preprint manuscript prepared for author review. No upload
or public release was performed. Its affiliation follows the author's explicit
instruction, NEXT BRAIN LTD. The related brian2-atlas preprint is cited as a
separate study: https://arxiv.org/abs/2610.23964. Its performance results are not
treated as evidence for this model. A stable public location for this study's
reproducibility archive remains to be assigned at release.

中文说明
本稿已按独立预印本重写，英文为主稿，中文为完整对照稿。作者与单位为
Xinjun Li / NEXT BRAIN LTD。正文围绕研究问题、执行条件、方法、实验、
结果及讨论组织；源码核查和频谱运行问题放在附录与复现记录中。
未执行论文上传或公开发布，也未把 Brian2 Atlas 的性能结果用于本研究。

E3 的 0% 保留率及三个 2.0% 衔接对照已补齐；新增结果单独归档，原始记录保留。
本次文献修订新增四篇直接相关工作，两稿按首次出现顺序统一编号为 [1]–[10]。
引言、命题 1 和讨论明确既有聚合原理与本模型执行条件的关系，并区分通信压缩、
输入求和及不同保真观测量。实验数据与图表未改动，参考文献及排版重新核验。

本轮进一步补严命题、零幅值唤醒边界、增益扫描和消息比值解释，新增八个受控投递测试。
五个正确对照的记录状态完全一致；三个违反条件的案例出现内部状态差异，但短窗口
脉冲序列仍相同。新增图 4 展示既有 E3 轨迹与逐槽差异。原有 E1–E5 证据保持不变。
