#!/usr/bin/env python3
"""F2 step 2a: fetch the Kaggle kernel output and verify it before use.

Checks, in order (fail closed):
  1. `kaggle kernels status` is terminal-complete (any other status -> BLOCKED)
  2. DONE.json exists and says status=ok
  3. manifest.json: generated == total_requested, black_count/nan_count reported
  4. every image file named in the manifest is present and its sha256 matches
  5. the image count equals the number of sentences asked for

Then copies images/f2_S###.png -> /tmp/f2/images/S###.png and writes
/tmp/f2/fetch_report.json (per-image sha256, kernel timings, verdict).

Usage:
  python3 scripts/f2_collect.py                 # fetch + verify + place
  python3 scripts/f2_collect.py --no-fetch      # verify an already-fetched dir
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/f2")
FETCH = WORK / "fetch"
IMAGES = WORK / "images"
KERNEL_SLUG = "forts845/of-bridge-runner"
EXPECTED = 214
TERMINAL_OK = ("complete",)
TERMINAL_BAD = ("error", "failed", "cancel", "timeout", "not found")


def status() -> str:
    p = subprocess.run(["kaggle", "kernels", "status", KERNEL_SLUG],
                       capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    low = out.lower()
    for token in TERMINAL_BAD:
        if token in low:
            return token
    for token in TERMINAL_OK:
        if f'"{token}"' in low or f"status {token}" in low:
            return token
    return "running"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_output_root(root: Path) -> Path:
    hits = list(root.rglob("manifest.json"))
    if not hits:
        raise SystemExit(f"BLOCKED: no manifest.json under {root}")
    return hits[0].parent


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--expected", type=int, default=EXPECTED)
    args = ap.parse_args(argv)

    st = status()
    print(f"kernel status: {st}")
    if st != "complete" and not args.no_fetch:
        print(f"BLOCKED: kernel is {st!r}, not complete", file=sys.stderr)
        return 2

    if not args.no_fetch:
        if FETCH.exists():
            shutil.rmtree(FETCH)
        FETCH.mkdir(parents=True)
        p = subprocess.run(["kaggle", "kernels", "output", KERNEL_SLUG,
                            "-p", str(FETCH), "-q"], capture_output=True, text=True)
        if p.returncode != 0:
            print(f"BLOCKED: fetch failed: {p.stderr[-500:]}", file=sys.stderr)
            return 2
        for z in FETCH.rglob("*.zip"):
            with zipfile.ZipFile(z) as zf:
                zf.extractall(z.parent / z.stem)
            z.unlink()

    root = find_output_root(FETCH)
    print(f"output root: {root}")

    done_path = next(iter(FETCH.rglob("DONE.json")), None)
    if done_path is None:
        raise SystemExit("BLOCKED: DONE.json missing (waiting rule violation)")
    done = json.loads(done_path.read_text(encoding="utf-8"))
    print(f"DONE.json: {done}")
    if done.get("status") != "ok":
        raise SystemExit(f"BLOCKED: DONE.json status={done.get('status')!r}")

    man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if man.get("generated") != man.get("total_requested"):
        raise SystemExit(f"BLOCKED: partial batch {man.get('generated')}/"
                         f"{man.get('total_requested')}")
    if man.get("total_requested") != args.expected:
        raise SystemExit(f"BLOCKED: kernel rendered {man.get('total_requested')}, "
                         f"expected {args.expected}")

    IMAGES.mkdir(parents=True, exist_ok=True)
    placed: List[Dict[str, Any]] = []
    problems: List[str] = []
    for entry in man["images"]:
        if not entry.get("file"):
            problems.append(f"{entry.get('render_id')}: no file")
            continue
        src = root / "images" / entry["file"]
        if not src.is_file():
            problems.append(f"{entry['file']}: missing on disk")
            continue
        got = sha256(src)
        if got != entry.get("sha256"):
            problems.append(f"{entry['file']}: sha256 mismatch")
            continue
        sid = entry["scene_id"]
        dst = IMAGES / f"{sid}.png"
        shutil.copy2(src, dst)
        placed.append({"sentence_id": sid, "sha256": got,
                       "bytes": src.stat().st_size,
                       "seed": entry.get("seed"), "seconds": entry.get("seconds")})
    if problems:
        for p in problems[:10]:
            print(f"  PROBLEM {p}", file=sys.stderr)
        raise SystemExit(f"BLOCKED: {len(problems)} image(s) failed verification")

    report = {
        "verdict": "PASS",
        "kernel": KERNEL_SLUG,
        "job_id": man.get("job_id"),
        "model_id": man.get("model_id"),
        "model_revision": man.get("model_revision"),
        "dtype": man.get("dtype"),
        "generated": man.get("generated"),
        "black_count": man.get("black_count"),
        "nan_count": man.get("nan_count"),
        "oom_count": man.get("oom_count"),
        "gpu_seconds": man.get("gpu_seconds"),
        "mean_sec_per_image": man.get("mean_sec_per_image"),
        "steady_state_sec_per_image": man.get("steady_state_sec_per_image"),
        "peak_vram_mb": man.get("peak_vram_mb"),
        "versions": man.get("versions"),
        "images": placed,
        "bytes_total": sum(p["bytes"] for p in placed),
    }
    (WORK / "fetch_report.json").write_text(json.dumps(report, indent=2) + "\n",
                                            encoding="utf-8")
    print(f"verified {len(placed)} images | {report['bytes_total'] / 1e6:.1f} MB | "
          f"gpu {man.get('gpu_seconds')}s | "
          f"{man.get('steady_state_sec_per_image')} s/image steady")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
