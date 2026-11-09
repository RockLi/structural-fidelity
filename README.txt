INPUT AND HORIZON DEPENDENT STRUCTURAL FIDELITY
Final table-reference revision and complete evidence release, 10 November 2026
Author: Xinjun Li, NEXT BRAIN LTD

START HERE
manuscript/input-and-horizon-dependent-structural-fidelity-preprint-en.docx and .pdf
manuscript/input-and-horizon-dependent-structural-fidelity-preprint-zh.docx and .pdf
The current manuscript is one complete article with Appendices A–N. It is based
on the full frozen manuscript, retaining all 25 original tables and 22 original
figures, and integrating five tables and three figures from the completed studies.
It has two principal questions: input-conditioned structural
effects, and finite-horizon fidelity ranges. The previous frozen release is
preserved under evidence/legacy-release, including its manuscripts and manifest.
No neural simulation, new graph sampling or radius search was run for this revision.

THIS EDITION
Added body references to Table 9 and Tables S1, S2, S8–S13 in both languages.
Updated public availability to the dedicated GitHub repository. No study-specific
archival DOI has been assigned. No scientific conclusion, numerical result,
equation, proof, table cell or image changed in this editorial revision.
The full article and Appendices A–N retain all 30 tables, 25 figures and 27
references. The two main questions concern input-conditioned structural effects
and finite-horizon fidelity ranges. The older experiments and negative results
remain intact. Main figures and tables follow their first references.
The immediately preceding 9 November release remains frozen separately;
validation/previous-20261109-lock.json records its hashes. Its manuscript sources
and DOCX are also retained in editorial/table-citations-prior.

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
package-sha256.json lists all release members except itself and the post-archive
integrity report. archive-integrity.json is a companion report beside the ZIP (not inside it),
recording ZIP member hash/CRC verification.
Large temporary page PNG renders and environment caches are excluded from the ZIP;
archived evidence files required by the original manifests are retained.

PUBLIC AVAILABILITY
https://github.com/RockLi/structural-fidelity
The complete archive is distributed in numbered binary parts on the GitHub
Release. Concatenate parts in numeric order to reconstruct the ZIP, then verify
its SHA-256 using the release checksum files. No archival DOI has been assigned.
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
