"""
purge_all_renders.py
Safely deletes all previous test renders, intermediate video files, and old project outputs.
Preserves raw downloaded documentary assets in assets/documentaries/.
"""

import sys
import shutil
from pathlib import Path

# UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
deleted_files = 0
deleted_bytes = 0

# 1. Projects renders
for p in ROOT.glob("projects/**/renders/*"):
    if p.is_file():
        try:
            deleted_bytes += p.stat().st_size
            deleted_files += 1
            p.unlink()
            print(f"Deleted project render: {p.relative_to(ROOT)}")
        except Exception as e:
            print(f"Failed to delete {p}: {e}")

# 2. Top-level renders folder
renders_dir = ROOT / "renders"
if renders_dir.exists():
    for p in renders_dir.glob("*"):
        if p.is_file():
            try:
                deleted_bytes += p.stat().st_size
                deleted_files += 1
                p.unlink()
                print(f"Deleted root render: {p.relative_to(ROOT)}")
            except Exception as e:
                print(f"Failed to delete {p}: {e}")

# 3. Scratch video exports
scratch_dir = ROOT / "scratch"
if scratch_dir.exists():
    for ext in ["*.mp4", "*.webm", "*.avi", "*.mov", "*.mkv"]:
        for p in scratch_dir.glob(ext):
            try:
                deleted_bytes += p.stat().st_size
                deleted_files += 1
                p.unlink()
                print(f"Deleted scratch video: {p.relative_to(ROOT)}")
            except Exception as e:
                print(f"Failed to delete {p}: {e}")

print(f"\n✅ Cleaned up: {deleted_files} render files deleted ({deleted_bytes / (1024*1024):.1f} MB freed).")
