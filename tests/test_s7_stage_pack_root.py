#!/usr/bin/env python3
"""Tests for scripts/s7_stage_pack_root.py (S7 pack-root staging)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "s7_stage_pack_root.py"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, corrupt: bool = False) -> tuple[Path, Path, Path]:
    cache = tmp_path / "cache"
    logs = tmp_path / "logs"
    out = tmp_path / "out"
    img_dir = cache / "sdxl"
    img_dir.mkdir(parents=True)
    png = img_dir / "r0001.png"
    png.write_bytes(b"fake-png-bytes")
    digest = "0" * 64 if corrupt else _sha(png)
    job = logs / "s7-sdxl-1"
    job.mkdir(parents=True)
    (job / "manifest.json").write_text(json.dumps({
        "model": "sdxl", "job_id": "s7-sdxl-1",
        "images": [{"file": "r0001.png", "render_id": "r0001",
                    "scene_id": "s01", "sha256": digest, "bytes": 14}],
    }), encoding="utf-8")
    return cache, logs, out


def test_stage_copies_verified_images(tmp_path):
    cache, logs, out = _fixture(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--cache-root", str(cache),
         "--logs-root", str(logs), "--out", str(out), "--models", "sdxl"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    dest = out / "s7_bakeoff_sdxl"
    assert (dest / "manifest.json").is_file()
    assert (dest / "images" / "r0001.png").is_file()
    assert "1 images verified" in r.stdout


def test_sha256_mismatch_blocks(tmp_path):
    cache, logs, out = _fixture(tmp_path, corrupt=True)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--cache-root", str(cache),
         "--logs-root", str(logs), "--out", str(out), "--models", "sdxl"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "BLOCKED" in (r.stdout + r.stderr)
    assert "sha256 mismatch" in (r.stdout + r.stderr)


def test_missing_cache_image_blocks(tmp_path):
    cache, logs, out = _fixture(tmp_path)
    (cache / "sdxl" / "r0001.png").unlink()
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--cache-root", str(cache),
         "--logs-root", str(logs), "--out", str(out), "--models", "sdxl"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "BLOCKED" in (r.stdout + r.stderr)


def test_missing_manifest_blocks(tmp_path):
    cache, logs, out = _fixture(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--cache-root", str(cache),
         "--logs-root", str(logs), "--out", str(out), "--models", "klein"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "BLOCKED" in (r.stdout + r.stderr)
