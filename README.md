# Input and Horizon Dependent Structural Fidelity in Chunk Coupled Spiking Networks

**Xinjun Li · NEXT BRAIN LTD** · Preprint and reproducibility materials · 10 November 2026

This study distinguishes input-conditioned effects of structural edits from finite-horizon guarantees for fixed-support weight perturbations. It includes the original chunk-network studies, controlled inputs, multiple original graphs, heterogeneous LIF validation using **brian2-atlas**, negative selection results, and complete proofs. The scope and limitations are stated in the manuscript.

## Read the paper

| Language | PDF | Editable Word |
|---|---|---|
| English | [PDF](manuscript/input-and-horizon-dependent-structural-fidelity-preprint-en.pdf) | [DOCX](manuscript/input-and-horizon-dependent-structural-fidelity-preprint-en.docx) |
| 中文 | [PDF](manuscript/input-and-horizon-dependent-structural-fidelity-preprint-zh.pdf) | [DOCX](manuscript/input-and-horizon-dependent-structural-fidelity-preprint-zh.docx) |

This edition adds missing body references to Table 9 and appendix tables, and updates public availability. It does not change scientific conclusions or add experiments. The immediately preceding frozen manuscript is preserved in the complete package. No archival DOI has been assigned.

## Download the complete reproducibility package

Use the [2026-11-10 release](https://github.com/RockLi/structural-fidelity/releases/tag/preprint-2026-11-10). Download all three numbered `.zip.part01`–`.zip.part03` assets, `release-checksums.json`, and `assemble_release.py` into one directory. Then run:

```sh
python3 assemble_release.py
unzip input-and-horizon-dependent-structural-fidelity-source-and-evidence.zip -d structural-fidelity-full
cd structural-fidelity-full
```

The helper verifies each part and the reconstructed ZIP with SHA-256. Do not unzip an individual part. GitHub's automatically generated “Source code” archives contain only the Git snapshot, **not the complete evidence package**.

The Git repository provides the manuscripts, current analysis tables, figures, scripts, and a browsable subset of archived study source/protocols. The release ZIP includes the complete immutable evidence, historical manuscripts, per-study manifests, and editorial retention material. **Run reproduction from the extracted complete ZIP, not this lightweight checkout.**

## Reproduce the current article without new simulations

In an environment with the recorded dependencies:

```sh
python reproduce_current.py --plot-python /absolute/path/to/plot-python --output-dir /absolute/path/to/new-empty-output
python verify_release.py
python verify_editorial_retention.py
```

The output location must not exist. The default path rebuilds analyses, plots, and bilingual DOCX files from archived data; it does not execute a simulator or search new certificate radii. Validation compares numeric outputs, PNG bytes, and DOCX members. PDF files are checked exports of the DOCX files, rendered with LibreOffice.

See [README.txt](README.txt), [environment metadata](validation/environment.json), and the archived study protocols for details. Recorded versions include python-docx 1.2.0, matplotlib 3.10.8 and numpy 2.5.4; PNG equality depends on the recorded fonts and plotting environment. Different environments require numerical and visual review rather than ignoring mismatches. Historical simulation uses brian2-atlas 0.2.0 (Python import name `brian2`), not an upstream Brian2 fallback.

## Integrity and citation

[release-checksums.json](release-checksums.json) identifies the complete archive and parts. The ZIP contains `package-sha256.json` for every packaged member. [Validation records](validation/) document content retention, bilingual references, layout review and a fresh analysis-only rebuild. Published source, raw data and proofs retain their original filenames and provenance.

Citation metadata is in [CITATION.cff](CITATION.cff). No DOI or ORCID has been invented, and this publication does not assign a new software or document license.
