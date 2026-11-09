Input Dependent Structural Effects and Temporal Error Composition in Chunk Coupled Spiking Networks
Xinjun Li — NEXT BRAIN LTD — final review revision, 26 October 2026

This final small revision adds no simulations. It clarifies the score/corollary
boundary and reports all three paired controls and the frozen stopping decision
in Table 8. The two principal findings and all numerical evidence are retained.

The preceding budget-boundary edition retains the two main findings on input-dependent structural effects
and temporal error composition. It adds the completed 9.912% activity-selection
experiment and a prospectively locked follow-up at 0.984% and 1.968% original
adjacency replacement. All four selection rules use shared candidate banks.
The two new budgets are nested prefixes of the known larger-budget candidates,
not independent graph cohorts. Training results determine a precommitted
continue/stop gate. No migration run is permitted unless BOTH budgets pass.
The prior input/readout analyses remain explicitly post hoc; the new follow-up
was designed after observing the larger-budget results and is not a public
preregistration. Exact rules and previous exposure are recorded in its protocol.

DELIVERABLES
  local-circuit-aggregation-preprint-en.docx / .pdf  English manuscript
  local-circuit-aggregation-preprint-zh.docx / .pdf  Chinese counterpart
  REVISION-NOTES.txt                               Changes and interpretation
  validation/                                     Current audits and historical checks
  package-sha256.json                              SHA256 of archived member files

REPRODUCE THIS REVISION FROM THE DEPOSITED TRAJECTORIES
Extract the entire archive and retain its directory structure. Run:

  python3 -B reproduce_analysis.py --output-dir /tmp/input-readout-analysis-fresh

The Python environment needs python-docx, NumPy and Matplotlib. If document and
scientific dependencies are separate, run:

  /path/to/document/python3 -B reproduce_analysis.py     --simulation-python /path/to/scientific/python3     --output-dir /tmp/input-readout-analysis-fresh

The output directory must not exist and must be outside this package. This path
performs no simulation: archived states generate new CSV files and figures,
followed by an independent numerical audit and both editable manuscripts. Every
new numerical CSV and PNG/PDF figure must match the deposited analysis exactly.
The archived low-budget analyses and frozen gate are also regenerated and audited.
The new paired-comparison CSV is generated from these fresh derived data and
checked along with the JSON and existing plots. Earlier evidence is retained. The completed independent audit checks
raw trajectories, input hashes, classifications, discrepancy decompositions,
bin assignments and all 570 exponential distances with a separate implementation.

FULL SIMULATOR TO DOCUMENT REPRODUCTION
To additionally repeat all inherited simulations, use:

  /path/to/document/python3 -B reproduce_stage.py     --simulation-python /path/to/scientific/python3     --output-dir /tmp/input-readout-full-fresh

Install rustup toolchain 1.98.1. Rust compiles directly with edition 2024 and
optimization level 3, without Cargo dependency downloads. The validated platform
is Apple arm64 Darwin. These checks target the recorded environment; they do not
promise bitwise equality across platforms. Allow at least 2 GB beyond the source
package, with additional space for rendering or another archive.

The full driver repeats E1/E3/E4/E5 and B1–B8, the 360-condition rewiring suite,
the 48-condition perturbation suite, the 231-condition sensitivity suite and its
six separate technical shams. It also repeats all 136 conditions of the prior
activity-selection experiment and the completed stages of the new budget module,
respecting its training gate. It then performs the post-hoc input/readout analysis,
independent audit, exact comparison of all new CSVs and figures, and bilingual
manuscript builds using the fresh outputs. Repeating an archived condition does
not add a new independent scientific observation. Phase and input/readout analyses
reuse specified archived trajectories and are identified as reanalyses.

Simulation state payloads and count CSVs must agree exactly. Only the inherited
48-run perturbation suite's derived floating CSV fields use rtol=atol=1e-12;
labels, row order, integers and missingness remain exact. Each difference is
logged. A failed fresh run never falls back to archived results. See the nested
environment records and artifact-build-environment.json for exact versions.

The drivers create DOCX. PDF rendering and page inspection are separate steps.
The released PDFs use bundled headless LibreOffice and the fonts documented in
the build environment. See validation/document-visual-qa.json for the final gate.

STANDALONE NEW ANALYSIS AND AUDIT
  python3 -B evidence/input-readout/analyze.py     --sensitivity-dir evidence/sensitivity --output-dir /tmp/readout-derived
  python3 -B validate_input_readout.py     --sensitivity-dir evidence/sensitivity --analysis-dir /tmp/readout-derived     --output /tmp/readout-independent.json
  python3 -B build_preprint.py en --input-readout-dir /tmp/readout-derived
  python3 -B build_preprint.py zh --input-readout-dir /tmp/readout-derived

The builder uses stable evidence keys internally. document_labels.py assigns
sequential main and supplementary labels after the manuscript is reorganized;
the generated document-labels-en.json and document-labels-zh.json expose the
mapping. The document audit checks citations, native equations, every paragraph,
all captions and the bilingual correspondence after this label transformation.

EVIDENCE MAP
  evidence/original/              Frozen original Rust source and results
  evidence/diagnostics/           Aligned sum, gain and instrumented controls
  evidence/e3-zero-retention/     Zero-retention trajectories and repeat checks
  evidence/execution-boundaries/ B1–B8 fixtures and state/scheduling validations
  evidence/scripts/              Earlier experiment reproduction
  evidence/rewiring/              360 conditions, graph audits and analyses
  evidence/perturbation/          48 pulse conditions and archived phase inputs
  evidence/sensitivity/          231 conditions, six shams and archived controls
  evidence/input-readout/        New post-hoc plan, analyzer and derived evidence
  conditional-figures/            Preserved phase and predictor figures
  sensitivity-figures/            Preserved calibration figures
  evidence/activity-guided-retention/  Prior 9.912% selection, 136 conditions
  evidence/budget-boundary/       Locked nested low-budget training and gate
  activity-figures/               Selector/zero and paired-decision tables; budget figure
  validation/analysis-fresh-run/  Current archived-data rebuild and logs
  validation/previous-budget-release/  Prior simulator-to-document validation
  validation/independent-paired-table-audit.py  Standalone raw-pair/table audit

Nested README files describe their original experimental stage. Their references
to new simulations or prior manuscript titles do not describe this revision.
Frozen historical files are intentionally unchanged, including inert hidden files
listed in inherited manifests. Retain figure-data.json and
trajectory-figure-data.json: older reproductions require these metadata.

WHAT THE NEW ANALYSIS ESTABLISHES
Of the same 19 swaps, two preserve raw-slot spikes under all three protocols,
seven change them under all three, and ten switch between these outcomes.
The 57 graph/input cases fall into four observed categories: 4 shared-source
input-equal/state-equal; 17 input-changed/spike-equal; 4 spike-changed/1-ms-bin-equal;
32 changed even after 1-ms binning. The diagnostic concerns arrivals inside the
window and does not certify all assumptions of the finite-horizon corollary.

Within comparisons with nonzero raw-slot error, the median fraction remaining
in each node's 30-ms cumulative count is 4.34%, 5.93%, 12.66% for single swaps
(n=12 per input), versus 56.77%, 58.36%, 52.55% for extensive rewiring (n=19).
Ratios are undefined for the seven spike-identical swaps per input. Cancellation
is defined with time accumulation before node pooling; it is not a unique
mechanistic decomposition, and does not establish short spike-time jitter.

Identified-node error ranges remain separated at all tested bin widths and
origins and all five tested exponential time constants. E/I and global pooling
usually give overlapping ranges. All offsets and filters reuse the same data;
they are not independent confirmations. The normalized squared van Rossum score
includes analytic tails, is dimensionless, and is neither an L1 percentage nor
bounded by one. Its precise convention is in Methods and the analysis notes.

SCOPE AND AVAILABILITY
The original input/readout analysis has one original, 125 chunks, three protocols and 30 ms.
Protocols differ in total drive, so input dependence is not an isolated effect
of spatial locality. Extensive and minimal interventions differ by about
1100-fold in removed adjacency fraction. Within-chunk units remain synchronous,
and the numerical kernel is uncalibrated. No optimal geometry, general stability
law, biological generality, compression benefit or runtime speedup is claimed.

The finite-horizon corollary assumes exact arithmetic, equal effective pending
inputs and activation effects, and matching source-dependent input maps along
the reference history, including scheduling-relevant future arrivals. It does
not identify queue representations or guarantee floating-point state bits.

The first sixteen references are retained; Victor and Purpura (1997) and van
Rossum (2001) provide the temporal-readout context. Reference 19, Moore and
Chaudhuri (2020), places activity-guided selection beside actual covariance-based
pruning with restricted model guarantees; it is not the algorithm tested here. Earlier proxy, phase and
pulse evidence is preserved in appendices. Public hosting remains a separate
publication step; no public archive identifier is invented in this local package.

ACTIVITY SELECTION FOLLOW-UP
The original graph contains 2845 edges. All selection candidates retain every
edge slot, source identity, weight and delay; legal swaps change targets while
preserving each node's arm-specific degree, strength and weight multiset. The
small budgets replace 28 and 56 original pairs, respectively. Stored graphs,
source states and edge visits are not compressed by this procedure.

Both budgets must have ten defined coactivity/random pairs, mean and median
error differences below -1e-12, and at least seven strict wins. Mean-activity
and shuffled controls must additionally have mean coactivity-minus-control
difference <=1e-12 and wins >= losses. These are pragmatic continuation guards,
not significance or formal noninferiority tests. All ties and zeros are retained.
The two budgets share banks and therefore are not independent replications.

Run only the activity modules and their gate-preserving fresh simulation path:
  /path/to/scientific/python3 -B reproduce_activity_stage.py --output /tmp/activity-stage-fresh

Its outputs can feed the new publication figure directly:
  /path/to/scientific/python3 -B plot_activity_budget.py --retention-dir /tmp/activity-stage-fresh/retention --budget-dir /tmp/activity-stage-fresh/budget --output-dir /tmp/activity-figures-fresh
  /path/to/document/python3 -B build_preprint.py en --activity-figures-dir /tmp/activity-figures-fresh --output-dir /tmp/activity-documents-fresh
  /path/to/document/python3 -B build_preprint.py zh --activity-figures-dir /tmp/activity-figures-fresh --output-dir /tmp/activity-documents-fresh

The standalone historical retention reproducer writes a sidecar to its source,
so the enclosing driver uses a copied reference. Released evidence remains
unchanged. The new budget reproducer writes its report to the fresh destination.
Instrumented loop times are excluded from performance claims. Raw-slot L1 may
exceed one and is not an error probability. Public deposition is still a
separate user-authorized step; no archive identifier has been invented.
Use the top-level reproduction entry points with an output directory outside
the extracted package. Do not build manuscripts in the package concurrently
with a full rerun: the immutable-input audit also checks generated label maps.

FINAL VALIDATION
This revision reruns the archived-trajectory analysis and document build only.
No new simulations, candidate selection, tuning or migration runs are added.
The six paired summaries and stopping decision are independently recomputed,
then checked against the displayed bilingual table. All 6,440 evidence files
remain byte-identical to the preceding release. See
validation/final-document-rebuild.json for numerical-to-document lineage and
validation/document-visual-qa.json for final page coverage. Previous full
simulation-to-document results and their logs are historical records under
validation/previous-budget-release/, not new runs for this editorial revision.

Reader Table 8 uses coactivity-minus-control differences in percentage points.
Its tolerance of 1e-12 applies to the unrounded normalized-L1 differences before
conversion. W/T/L and graph overlap are distinct columns. Both budgets must
pass every comparator condition; the joint STOP remains unchanged. The
continuation rule is not a significance or formal noninferiority test.

The coactivity score includes source slots 0–297, whose arrivals lie within the
300-slot observation window. A zero score by itself would not certify Corollary
1: the input-map condition must also hold for source slots 298 and 299, and all
initial-state, pending-input and activation hypotheses must hold. This added
explanation does not change the theorem or any observed outcome.

COMPLETED LOW-BUDGET OUTCOME
Both small budgets improve training raw-slot L1 relative to random: coactivity
minus random means -0.0859078591 and -0.1138211382, each 7 wins / 1 tie / 2 losses.
At 0.984%, coactivity is worse on average than mean activity (+0.0413279133)
and shuffled (+0.0044037940), so its comparator guards fail. The 1.968% budget
passes individually, but BOTH are required: the joint gate is false. No new
migration condition was simulated. Do not reinterpret this as failure versus
random at both budgets, and do not continue only the successful budget.
Coactivity and shuffled select the same graph in 9/10 banks at each budget;
these comparisons do not establish a coactivity-specific improvement. All 1280
candidate scores and all 80 selected policy memberships have nonzero J scores.
The 57 unique selected training graphs all have nonzero raw-slot, 1 ms and
cumulative-count errors and nonidentical recorded states. The original bridge
brings the scientific run count to 58, plus one technical repeat. All zeros,
ties and negative comparisons are preserved in the module's tables.
