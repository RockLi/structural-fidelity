Current final-review revision checks
====================================
document-structure.json: bilingual paragraphs/captions, all 19 references,
sequential reader labels, 15 tables, 20 figures, and native equations.
independent-paired-table-audit.py/.json: separate calculation from raw policy
pairs, frozen protocol/gate/ledger, presentation CSV/JSON and DOCX cells.
Run: python3 -B validation/independent-paired-table-audit.py --root . --output /tmp/final-pairs-audit.json
analysis-fresh-run/: this revision's archived-data reanalysis, audits and logs;
no simulator was invoked. Documents were rebuilt again after final table-layout
fixes using these same freshly derived outputs; XML and media agreement is in
final-document-rebuild.json.
evidence-baseline-sha256.json: all 6,440 inherited evidence files, unchanged.
final-scientific-review.json: scope, preserved claims, paired and stop decisions.
visual-en.json / visual-zh.json: full page coverage, hashes and resolved findings.
document-visual-qa.json: final English 43 pages / Chinese 47 pages.
release-validation.json: combined current-release checks and deliverable hashes.

previous-budget-release/: historical validation from the preceding edition,
including its complete simulator-to-document rerun and prior releases. These
files are retained unchanged except that their parent folder has been relocated;
absolute temporary paths describe the original run. They are not new experiments
or newly performed full-simulator checks in this final small revision.
