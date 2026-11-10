# Input and Horizon Dependent Structural Fidelity in Chunk Coupled Spiking Networks

**Xinjun Li · NEXT BRAIN LTD** · Preprint and reproducibility materials · 10 November 2026

This study distinguishes input-conditioned effects of structural edits from finite-horizon guarantees for fixed-support weight perturbations. It includes the original chunk-network studies, controlled inputs, multiple original graphs, heterogeneous LIF validation using **brian2-atlas**, negative selection results, and complete proofs. The scope and limitations are stated in the manuscript.

## Read the paper

[arXiv:2611.12813](https://arxiv.org/abs/2611.12813) · cs.CE · [arXiv PDF (v1)](https://arxiv.org/pdf/2611.12813v1).

[Read the English PDF](manuscript/input-and-horizon-dependent-structural-fidelity-preprint-en.pdf).

This update publishes only the English PDF. Word files remain local working files.
Only the English data/code availability paragraph changes to identify the Zenodo
archive and CC BY 4.0 license. Scientific text, results, proofs, tables and figures
are unchanged. Historical bilingual/Word materials already present in the frozen
archive and previous release are preserved.


## Download the complete reproducibility package

The frozen complete source-and-evidence archive is preserved on [Zenodo](https://doi.org/10.5281/zenodo.24089361), with a mirror in the [2026-11-10 frozen release](https://github.com/RockLi/structural-fidelity/releases/tag/preprint-2026-11-10). Download all three numbered `.zip.part01`–`.zip.part03` assets, `release-checksums.json`, and `assemble_release.py` into one directory. Then run:

```sh
python3 assemble_release.py
unzip input-and-horizon-dependent-structural-fidelity-source-and-evidence.zip -d structural-fidelity-full
cd structural-fidelity-full
```

The helper verifies each part and the reconstructed ZIP with SHA-256. This frozen archive contains the pre-DOI manuscripts. To reproduce the current DOI-only availability update, download `structural-fidelity-availability-update.zip` and its checksum manifest from the [availability update release](https://github.com/RockLi/structural-fidelity/releases/tag/preprint-2026-11-10-doi), then extract it over the verified complete package. No evidence files are replaced. `availability-update-sha256.json` checks the updated files; `current-package-sha256.json` describes the combined current package except the locally generated English DOCX, whose OOXML/media member hashes are independently verified. Run `python prepare_local_word.py` after applying the update and before reproduction; this creates Word only on your own computer. The update ZIP contains no Word files. The original `package-sha256.json` continues to describe the frozen archive. Do not unzip an individual part. GitHub's automatically generated “Source code” archives contain only the Git snapshot, **not the complete evidence package**.

The Git repository provides the current English PDF, current analysis tables, figures, scripts, and a browsable subset of archived study source/protocols. The release ZIP includes the complete immutable evidence, historical manuscripts, per-study manifests, and editorial retention material. **Run reproduction from the extracted complete ZIP, not this lightweight checkout.**

## Reproduce the current article without new simulations

In an environment with the recorded dependencies:

```sh
python prepare_local_word.py
python reproduce_current.py --plot-python /absolute/path/to/plot-python --output-dir /absolute/path/to/new-empty-output
python verify_release.py
python verify_editorial_retention.py
```

The output location must not exist. The default path rebuilds analyses, plots, and bilingual DOCX files from archived data; it does not execute a simulator or search new certificate radii. Validation compares numeric outputs, PNG bytes, and DOCX members. PDF files are checked exports of the DOCX files, rendered with LibreOffice.

See [README.txt](README.txt), [environment metadata](validation/environment.json), and the archived study protocols for details. Recorded versions include python-docx 1.2.0, matplotlib 3.10.8 and numpy 2.5.4; PNG equality depends on the recorded fonts and plotting environment. Different environments require numerical and visual review rather than ignoring mismatches. Historical simulation uses brian2-atlas 0.2.0 (Python import name `brian2`), not an upstream Brian2 fallback.

## Integrity and citation

[release-checksums.json](release-checksums.json) identifies the complete archive and parts. The ZIP contains `package-sha256.json` for every packaged member. [Validation records](validation/) document content retention, bilingual references, layout review and a fresh analysis-only rebuild. Published source, raw data and proofs retain their original filenames and provenance.

Citation metadata for the article is in [CITATION.cff](CITATION.cff). The companion research-materials DOI is [10.5281/zenodo.24089361](https://doi.org/10.5281/zenodo.24089361); it is not an article DOI. The author has authorized **CC BY 4.0** for the archived package. See [LICENSE-NOTICE.txt](LICENSE-NOTICE.txt); existing third-party rights and notices remain in force. Author ORCID: [0009-0005-8381-0416](https://orcid.org/0009-0005-8381-0416).
