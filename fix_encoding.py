#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix bare open() calls: add encoding="utf-8" so JSON/YAML loaders work on GBK Windows.
   Run once from repo root: PYTHONUTF8=1 python fix_encoding.py
   (Yes this script itself needs PYTHONUTF8=1 on first run — once fixed, not needed.)"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent

FIXES = {
    "lib/checkpoint.py": [
        # Schema loader (line 100 — the critical crash site)
        (r'open\(CHECKPOINT_SCHEMA_PATH\)',
         'open(CHECKPOINT_SCHEMA_PATH, encoding="utf-8")'),
        # Read project marker
        (r'open\(marker_path\)',
         'open(marker_path, encoding="utf-8")'),
        # Write project marker
        (r'open\(marker_path, "w"\)',
         'open(marker_path, "w", encoding="utf-8")'),
        # Read checkpoint data (3 sites: archive / merge / read)
        (r'with open\(path\) as',
         'with open(path, encoding="utf-8") as'),
        # Write decision_log
        (r'open\(path, "w"\)',
         'open(path, "w", encoding="utf-8")'),
        # Write temp checkpoint
        (r'open\(tmp_path, "w"\)',
         'open(tmp_path, "w", encoding="utf-8")'),
        # Read latest checkpoint
        (r'open\(checkpoints\[0\]\)',
         'open(checkpoints[0], encoding="utf-8")'),
    ],
    "lib/pipeline_loader.py": [
        (r'open\(SCHEMA_PATH\)',
         'open(SCHEMA_PATH, encoding="utf-8")'),
        (r'open\(path\)',
         'open(path, encoding="utf-8")'),
    ],
    "schemas/artifacts/__init__.py": [
        (r'open\(path\)',
         'open(path, encoding="utf-8")'),
    ],
}

ok = 0
for rel_path, replacements in FIXES.items():
    fp = REPO / rel_path
    if not fp.exists():
        print(f"SKIP: {rel_path} not found")
        continue
    text = fp.read_text(encoding="utf-8")
    for pattern, replacement in replacements:
        new_text = re.sub(pattern, replacement, text, count=0)
        if new_text != text:
            text = new_text
            print(f"  FIX {rel_path}: {pattern[:55]}...")
    fp.write_text(text, encoding="utf-8")
    ok += 1
    print(f"OK: {rel_path}")

print(f"\nFixed {ok} files. Verify: grep for remaining bare open() calls.")
