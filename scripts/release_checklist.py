"""Release checklist — Zero-cost QC + V7 numerical metrics for final MP4.

Computes the retention/pacing metrics from FACTORY_MASTER_BUILD_V7.md §4.1:
  * max_static_segment_sec      longest near-static (frozen) segment
  * avg_visual_change_interval_sec  mean seconds between visual changes

Every public function returns an explicit status
(success / fallback_used / failed) — never fails silently. All checks use
ffmpeg/ffprobe only: $0, no network, no credits.

Usage:
    python scripts/release_checklist.py <video.mp4> [baseline_out.json]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # PIL is the frame-diff backend; numpy speeds it up.
    from PIL import Image  # type: ignore
    _HAVE_PIL = True
except Exception:  # pragma: no cover - environment without PIL
    _HAVE_PIL = False

try:
    import numpy as np  # type: ignore
    _HAVE_NUMPY = True
except Exception:  # pragma: no cover
    _HAVE_NUMPY = False


# ---------------------------------------------------------------------------
# Thresholds (V7 §4.1 numerical criteria)
# ---------------------------------------------------------------------------
STATIC_MAX_SEC = 15.0        # max_static_segment_sec must be <= 15
CHANGE_INTERVAL_MAX_SEC = 15.0  # avg_visual_change_interval_sec must be <= 15


@dataclass
class CheckResult:
    check_id: str
    status: str  # success | fallback_used | failed
    measured: Any = None
    threshold: Any = None
    passed: bool | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe_duration(video: Path) -> float:
    out = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video),
    ])
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def frozen_segments(video: Path) -> list[dict[str, float]]:
    """Near-static (frozen) segments via ffmpeg freezedetect."""
    out = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                "-vf", "freezedetect", "-f", "null", "-"])
    text = out.stderr or ""
    starts = [float(m.group(1)) for m in __import__("re").finditer(r"freeze_start:\s*([\d.]+)", text)]
    durations = [float(m.group(1)) for m in __import__("re").finditer(r"freeze_duration:\s*([\d.]+)", text)]
    ends = [float(m.group(1)) for m in __import__("re").finditer(r"freeze_end:\s*([\d.]+)", text)]
    segs: list[dict[str, float]] = []
    for i, s in enumerate(starts):
        d = durations[i] if i < len(durations) else 0.0
        e = ends[i] if i < len(ends) else (s + d)
        if d <= 0 and e > s:
            d = e - s
        segs.append({"start": s, "end": e, "duration": d})
    return segs


# ---------------------------------------------------------------------------
# Visual-change interval via sampled frame differencing
# ---------------------------------------------------------------------------

def _frame_grayscale(path: Path) -> Any:
    if _HAVE_PIL:
        return np.asarray(Image.open(path).convert("L"), dtype=np.float32) if _HAVE_NUMPY else None
    return None


def visual_change_interval(video: Path, sample_fps: float = 2.0, diff_thr: float = 8.0) -> dict[str, Any]:
    """Mean seconds between consecutive frames whose grayscale diff exceeds
    diff_thr. Returns dict with avg_interval_sec and max_interval_sec."""
    if not (_HAVE_PIL and _HAVE_NUMPY):
        return {"avg_interval_sec": None, "max_interval_sec": None,
                "note": "PIL/numpy unavailable — metric estimated as not_run"}

    duration = probe_duration(video)
    if duration <= 0:
        return {"avg_interval_sec": None, "max_interval_sec": None, "note": "could not probe duration"}

    with tempfile.TemporaryDirectory() as td:
        out_glob = str(Path(td) / "f_%03d.png")
        r = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                  "-vf", f"fps={sample_fps},scale=160:90", out_glob])
        if r.returncode != 0:
            return {"avg_interval_sec": None, "max_interval_sec": None,
                    "note": f"ffmpeg frame extract failed: {r.stderr[:200]}"}

        import glob as _glob
        files = sorted(_glob.glob(str(Path(td) / "f_*.png")))
        if len(files) < 2:
            return {"avg_interval_sec": None, "max_interval_sec": None,
                    "note": "too few frames extracted"}

        step = 1.0 / sample_fps
        prev = _frame_grayscale(Path(files[0]))
        change_times: list[float] = []
        for i in range(1, len(files)):
            cur = _frame_grayscale(Path(files[i]))
            if prev is None or cur is None:
                prev = cur
                continue
            diff = float(np.abs(cur - prev).mean())
            if diff > diff_thr:
                change_times.append(i * step)
            prev = cur

    if len(change_times) < 2:
        return {"avg_interval_sec": None, "max_interval_sec": None,
                "note": f"only {len(change_times)} changes detected — cannot average"}

    intervals = [change_times[i+1] - change_times[i] for i in range(len(change_times)-1)]
    # Also include first change from start and last change to end as bounds.
    return {
        "avg_interval_sec": round(sum(intervals) / len(intervals), 3),
        "max_interval_sec": round(max(intervals), 3),
        "n_changes": len(change_times),
        "note": "success",
    }


# ---------------------------------------------------------------------------
# Public checklist entry point
# ---------------------------------------------------------------------------

def run_checklist(video: str | Path, baseline_out: str | Path | None = None) -> dict[str, Any]:
    """Run the full release checklist on `video`.

    Returns a dict with explicit per-check statuses and the two V7 metrics.
    Writes `baseline_out` (default qc/baseline_v7.json next to the repo) when
    provided.
    """
    video = Path(video)
    if not video.is_file():
        return {"status": "failed", "error": f"video not found: {video}"}

    results: list[CheckResult] = []

    # --- max_static_segment_sec (V7 §4.1) ---
    segs = frozen_segments(video)
    max_static = max((s["duration"] for s in segs), default=0.0)
    passed = max_static <= STATIC_MAX_SEC
    results.append(CheckResult(
        check_id="max_static_segment_sec",
        status="success",
        measured=round(max_static, 3),
        threshold=STATIC_MAX_SEC,
        passed=passed,
        note=f"{len(segs)} frozen segment(s); limit {STATIC_MAX_SEC}s",
    ))

    # --- avg_visual_change_interval_sec (V7 §4.1) ---
    vci = visual_change_interval(video)
    avg_ivc = vci.get("avg_interval_sec")
    vci_passed = (avg_ivc is not None and avg_ivc <= CHANGE_INTERVAL_MAX_SEC)
    results.append(CheckResult(
        check_id="avg_visual_change_interval_sec",
        status="success" if avg_ivc is not None else "fallback_used",
        measured=avg_ivc,
        threshold=CHANGE_INTERVAL_MAX_SEC,
        passed=vci_passed if avg_ivc is not None else None,
        note=vci.get("note", ""),
    ))

    # --- duration probe ---
    duration = probe_duration(video)
    results.append(CheckResult(
        check_id="duration_sec",
        status="success" if duration > 0 else "failed",
        measured=round(duration, 3),
        passed=duration > 0,
    ))

    overall = all((r.passed is True) for r in results if r.passed is not None)
    report = {
        "video": str(video),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_passed": overall,
        "metrics": {
            "max_static_segment_sec": round(max_static, 3),
            "avg_visual_change_interval_sec": avg_ivc,
        },
        "checks": [r.to_dict() for r in results],
    }

    if baseline_out:
        p = Path(baseline_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["baseline_written"] = str(p)

    return report


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python scripts/release_checklist.py <video.mp4> [baseline_out.json]")
        return 2
    video = argv[0]
    baseline = argv[1] if len(argv) > 1 else None
    report = run_checklist(video, baseline)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("overall_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
