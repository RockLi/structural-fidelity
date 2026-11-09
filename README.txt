INPUT AND HORIZON DEPENDENT STRUCTURAL FIDELITY
Zenodo availability update, 10 November 2026
Author: Xinjun Li, NEXT BRAIN LTD

START HERE
Current online article: manuscript/input-and-horizon-dependent-structural-fidelity-preprint-en.pdf
The current publication is English PDF only. Word files are local working files.
Historical Chinese/Word artifacts in the already-published frozen archive are unchanged.

The current manuscript is one complete article with Appendices A–N. It is based
on the full frozen manuscript, retaining all 25 original tables and 22 original
figures, and integrating five tables and three figures from the completed studies.
It has two principal questions: input-conditioned structural
effects, and finite-horizon fidelity ranges. The previous frozen release is
preserved under evidence/legacy-release, including its manuscripts and manifest.
No neural simulation, new graph sampling or radius search was run for this revision.

THIS EDITION
This edition changes only the English Data and code availability paragraph to
identify the companion Zenodo archive, public repository and authorized CC BY 4.0
license. Scientific text, results, proofs, tables, images and references are unchanged.
The previous frozen GitHub release preprint-2026-11-10 remains intact; its source
and evidence ZIP is the exact archive deposited with Zenodo.
validation/previous-github-freeze-lock.json records the immediate parent hashes.
Earlier body-reference edits and their frozen source remain in editorial/.

EVIDENCE LINEAGE
1. evidence/legacy-release: immutable previous release, including the seed99
   discovery, controlled inputs, score ablations, paired doses and negative results.
2. evidence/studies/multigraph-input-validation-20261109: three new original graphs.
3. evidence/studies/cross-generator-validation-20261109: six new original graphs.
4. evidence/studies/atlas-heterogeneous-lif-horizon-20261109: homogeneous and
   heterogeneous LIF, 30/100/300 ms prefixes, on three REUSED originals.
There are ten distinct original graphs, not thirteen. The LIF implementation uses
published brian2-atlas 0.2.0, native reference-f64; its import name is brian2.
The isolated experiment environment used no upstream Brian2 distribution/fallback.
Archived protocols, models, source, raw results, independent checks and environment
metadata remain with each study. Follow their own README/protocol when inspecting
historical execution; the current default reproduction below is analysis only.

POST HOC RECOMPUTATIONS
analysis/posthoc-horizon-witnesses.csv records all short/long comparisons.
A recorded actual long-horizon failure U_long < certified L_short witnesses strict
loss of a previously certified interval: 710/720 heterogeneous 30-to-300 ms cases.
analysis/posthoc-input-orders.csv retains every candidate pair, including unresolved
pairs: 394/829 jointly resolved heterogeneous G_B/F_H orders differ at 300 ms.
These are post hoc, dependent summaries, not new preregistered tests. Positive
region coverage, finite-radius resolution and legacy single-point 16/17 coverage
have different denominators and are not pooled. See manuscript Sections 2–4.

REBUILD CURRENT RESULTS, FIGURES AND DOCX (NO SIMULATIONS)
Use Python 3 with python-docx for the main interpreter, and a Python environment
with numpy and matplotlib for --plot-python (the same interpreter is acceptable).
  python prepare_local_word.py
  python reproduce_current.py --plot-python /absolute/path/to/python \
      --output-dir /absolute/path/to/a-new-empty-location
The output directory must not exist. This first rebuilds the legacy score-factor,
paired-dose and input-control analyses from archived records, then runs
reanalyze.py, plot_paper.py and both complete document builds. It compares regenerated CSV/JSON, PNG and every DOCX OOXML/media
member with the released versions. Plot PNG byte equality depends on the recorded
matplotlib/font environment; differing environments require numerical and visual
comparison rather than ignoring a failed check. See validation/rebuild-verification.json.
No simulator is imported or executed by this path.

PDF RENDERING
PDFs are verified exports of the supplied DOCX. Render each with LibreOffice using
the recorded fonts (Times New Roman and Songti SC) and inspect every page.
The development render command and runtime versions are recorded in validation.
The source includes native editable Word equations and generated scientific figures.

INTEGRITY
  python verify_release.py
Checks source-study manifests, raw-bracket recomputations, table values, reference
numbering and bilingual labels. External old-release hashes are checked if present.
The frozen archive package-sha256.json and archive-integrity.json describe the
unchanged Zenodo ZIP. Apply the availability update only after verifying that ZIP.
availability-update-sha256.json verifies every replacement/addition in the update;
current-package-sha256.json identifies the combined current package, excluding
the locally regenerated English Word file (verified by OOXML/member hashes). The old
manifest continues to describe the frozen archive, not the overlaid manuscripts.
Large temporary page PNG renders and environment caches are excluded from the ZIP;
archived evidence files required by the original manifests are retained.

PUBLIC AVAILABILITY
https://github.com/RockLi/structural-fidelity
The complete archive is distributed in numbered binary parts on the GitHub
Release. Concatenate parts in numeric order to reconstruct the ZIP, then verify
its SHA-256 using the release checksum files. The frozen complete archive DOI is https://doi.org/10.5281/zenodo.24089361.
The author has authorized CC BY 4.0 for this package.
This package does not claim journal acceptance, speedup, arbitrary graph-rewiring
certification or unlimited robustness.

EDITORIAL RETENTION CHECK
  python verify_editorial_retention.py
Checks exact retention against the immediate frozen parent, allowing only the
declared body-reference additions and public-availability replacement recorded in
editorial/table-citation-changes.json. Table cells, images, native equations,
authorship and bibliography remain unchanged.

OUTPUT NAMES
Current PDF/DOCX names use input-and-horizon-dependent-structural-fidelity-preprint.
The archive is input-and-horizon-dependent-structural-fidelity-source-and-evidence.zip.
Historical evidence keeps its original filenames and immutable manifests.

ZENODO AVAILABILITY UPDATE
The current published paper is English-only. Chinese manuscript files are retained
unchanged solely as historical components of the frozen reproducibility package.
The Zenodo archive is the unchanged pre-DOI release, SHA-256
85a4b86fbbf1d52b30975d94de7bc648858eb5e4ab9742d17a67d59a4131b3f7.
Extract it into a fresh directory, then apply the separately supplied availability
update ZIP to that directory to rebuild the current manuscripts. The update
replaces only non-evidence files; no archived experimental evidence is changed.

PDF-ONLY AVAILABILITY UPDATE
The update ZIP contains no Word files and no new Chinese manuscript. After
applying it over the verified frozen archive, run python prepare_local_word.py
to rebuild and verify the current English Word locally before reproduction checks.
