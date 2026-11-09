Fresh end-to-end reproduction validation, 22 October 2026

The driver ran from an extracted candidate source ZIP in a directory containing
spaces. All 12 stages completed: the original suite, three diagnostic variants,
log extraction, E3 zero-retention and bridge runs, eight execution-boundary
fixtures, six figures, and both DOCX manuscripts. Archived numerical data were
used only as comparison references. Input and output hashes were recorded.

fresh-run/ preserves new logs, CSV/JSON results, per-slot records, all generated
figures, commands, compiler provenance and the original run manifests. Paths
in those records identify the actual temporary run location and are preserved.
Source-log paths in tables and input paths in figure metadata are relative to
fresh-run/, so the bundled evidence can be audited after extraction.

fresh-run/output-sha256.json is the inventory of the COMPLETE original run.
Its compiled binaries, duplicated build sources/caches and DOCX files are not
included in this evidence folder. The two DOCX files are delivered separately;
their hashes are in pipeline-validation.json and root document-validation.json.
The evidence-sha256.json here is the exact inventory of this bundled subset.
All source inputs needed to rerun the driver are in the enclosing source package.

candidate-package-validation.json records the executed candidate package and
its extracted member hashes. The final release adds these new run records and
updates README/validation metadata; executable sources remain identical to the
candidate. The final root package-sha256.json verifies the released ZIP contents.

The two independent reports reconstruct fresh table rows from new logs and
compare fresh scientific outputs with the historical archive. Their audit scripts
are included as review records; command-line paths/defaults identify the local
validation environment. They did not rerun Rust simulations. The document QA
reports at package root record the separate rendering and visual inspections.

Command durations are logistical records, not benchmark performance evidence.
No general cross-platform or cross-compiler bitwise guarantee is inferred.
