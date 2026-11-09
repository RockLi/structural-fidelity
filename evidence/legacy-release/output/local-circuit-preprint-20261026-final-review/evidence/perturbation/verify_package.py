#!/usr/bin/env python3
"""Read-only delivery integrity check; standard library only."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "PACKAGE-MANIFEST.json").read_text())
for relative, expected in manifest["files"].items():
    path = root / relative
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Checksum mismatch: {relative}")
print(f"PASS: {len(manifest['files'])} delivered file checksums match.")
