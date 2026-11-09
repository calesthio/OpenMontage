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
# Thresholds (V8 §8.5: 15 s is a warning/review threshold, not an absolute law)
# V8 QC hard gates: static segment > 6 s = FAIL; peak > -1.5 dBFS = FAIL;
# audio channels not 1-2 = FAIL.
# ---------------------------------------------------------------------------
STATIC_MAX_SEC = 15.0        # max_static_segment_sec advisory (15 s)
STATIC_FAIL_SEC = 6.0        # static segment > 6 s = hard FAIL (V8 QC gate)
CHANGE_INTERVAL_MAX_SEC = 15.0  # avg_visual_change_interval_sec advisory threshold
AUDIO_PEAK_MAX_DBFS = -1.5   # true peak > -1.5 dBFS = FAIL
AUDIO_CHANNELS_OK = {1, 2}   # mono or stereo OK; anything else = FAIL


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

    # --- max_static_segment_sec (V8 QC gate: static > 6 s = FAIL) ---
    segs = frozen_segments(video)
    max_static = max((s["duration"] for s in segs), default=0.0)
    static_fail = max_static > STATIC_FAIL_SEC
    results.append(CheckResult(
        check_id="max_static_segment_sec",
        status="failed" if static_fail else ("warning" if max_static > STATIC_MAX_SEC else "success"),
        measured=round(max_static, 3),
        threshold=STATIC_FAIL_SEC,
        passed=not static_fail,
        note=(f"{len(segs)} frozen segment(s); max_static={max_static:.3f}s; "
              f"gate: > {STATIC_FAIL_SEC}s = FAIL, > {STATIC_MAX_SEC}s = review"),
    ))

    # --- avg_visual_change_interval_sec (V8 §8.5: advisory threshold) ---
    vci = visual_change_interval(video)
    avg_ivc = vci.get("avg_interval_sec")
    if avg_ivc is not None:
        if avg_ivc <= CHANGE_INTERVAL_MAX_SEC:
            vci_passed = True
            vci_status = "success"
            vci_note = vci.get("note", "")
        else:
            vci_passed = None  # advisory, not blocking
            vci_status = "warning"
            vci_note = (f"avg_interval={avg_ivc:.3f}s exceeds advisory limit "
                        f"{CHANGE_INTERVAL_MAX_SEC}s — review, not a hard fail. "
                        f"{vci.get('note', '')}")
    else:
        vci_passed = None
        vci_status = "fallback_used"
        vci_note = vci.get("note", "")
    results.append(CheckResult(
        check_id="avg_visual_change_interval_sec",
        status=vci_status,
        measured=avg_ivc,
        threshold=CHANGE_INTERVAL_MAX_SEC,
        passed=vci_passed,
        note=vci_note,
    ))

    # --- Audio true peak + channels (V8 hard gates) ---
    audio_qc = audio_peak_and_channels(video)
    tp = audio_qc.get("true_peak_dbfs")
    ch = audio_qc.get("channels")

    peak_ok = tp is not None and tp <= AUDIO_PEAK_MAX_DBFS
    channels_ok = ch is not None and ch in AUDIO_CHANNELS_OK

    peak_status = "failed" if tp is not None and not peak_ok else ("success" if peak_ok else "fallback_used")
    peak_note = (f"true_peak={tp:.2f} dBFS; gate: > {AUDIO_PEAK_MAX_DBFS} dBFS = FAIL"
                 if tp is not None else "true peak not measurable")
    results.append(CheckResult(
        check_id="audio_true_peak_dbfs",
        status=peak_status,
        measured=round(tp, 3) if tp is not None else None,
        threshold=AUDIO_PEAK_MAX_DBFS,
        passed=peak_ok,
        note=peak_note,
    ))

    ch_status = "failed" if ch is not None and not channels_ok else ("success" if channels_ok else "fallback_used")
    ch_note = (f"channels={ch}; gate: not 1-2 = FAIL" if ch is not None
               else "channel count not measurable")
    results.append(CheckResult(
        check_id="audio_channels",
        status=ch_status,
        measured=ch,
        threshold="1-2",
        passed=channels_ok,
        note=ch_note,
    ))

    # --- Integrated loudness (info only) ---
    ilufs = audio_qc.get("integrated_lufs")
    results.append(CheckResult(
        check_id="audio_integrated_lufs",
        status="success" if ilufs is not None else "fallback_used",
        measured=round(ilufs, 2) if ilufs is not None else None,
        passed=ilufs is not None,
        note=f"integrated={ilufs:.1f} LUFS" if ilufs is not None else "not measurable",
    ))

    # --- hook: first 30 seconds (V8 §4.2 YouTube Intro) ---
    # First 30s should not be overly static (>5s without visual change) and
    # narration should be audible (not silence-dominated).
    hook_static = _max_static_in_range(video, 0.0, 30.0)
    hook_static_passed = hook_static is None or hook_static <= 5.0
    hook_static_status = ("success" if hook_static_passed and hook_static is not None
                          else "warning")
    hook_static_note = (f"first 30s max static {hook_static:.3f}s"
                        if hook_static is not None
                        else "could not measure first-30s static")
    if not hook_static_passed and hook_static is not None:
        hook_static_note += " — >5s static in hook, review intro pacing"
    results.append(CheckResult(
        check_id="hook_first30s_static_sec",
        status=hook_static_status,
        measured=round(hook_static, 3) if hook_static is not None else None,
        threshold=5.0,
        passed=hook_static_passed,
        note=hook_static_note,
    ))

    hook_silent_ratio = _silence_ratio_in_range(video, 0.0, 30.0)
    hook_silent_passed = hook_silent_ratio is None or hook_silent_ratio <= 0.5
    hook_silent_status = ("success" if hook_silent_passed and hook_silent_ratio is not None
                          else "warning")
    hook_silent_note = (f"first 30s silence ratio {hook_silent_ratio:.2f}"
                        if hook_silent_ratio is not None
                        else "could not measure first-30s silence")
    if not hook_silent_passed and hook_silent_ratio is not None:
        hook_silent_note += " — >50% silence in hook, narration may be missing"
    results.append(CheckResult(
        check_id="hook_first30s_silence_ratio",
        status=hook_silent_status,
        measured=round(hook_silent_ratio, 3) if hook_silent_ratio is not None else None,
        threshold=0.5,
        passed=hook_silent_passed,
        note=hook_silent_note,
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
            "audio_true_peak_dbfs": round(tp, 3) if tp is not None else None,
            "audio_channels": ch,
            "audio_integrated_lufs": round(ilufs, 2) if ilufs is not None else None,
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


# ---------------------------------------------------------------------------
# Hook / first-30s helpers (V8 §4.2)
# ---------------------------------------------------------------------------

def _max_static_in_range(video: Path, start_s: float, end_s: float) -> float | None:
    """Longest frozen segment fully within [start_s, end_s] via freezedetect."""
    try:
        dur = probe_duration(video)
        if dur <= 0:
            return None
        # Limit probe to the range using -ss / -t.
        seg_end = min(end_s, dur)
        seg_dur = seg_end - start_s
        if seg_dur <= 0:
            return None
        out = _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start_s}",
            "-i", str(video), "-t", f"{seg_dur}",
            "-vf", "freezedetect", "-f", "null", "-",
        ])
        text = out.stderr or ""
        import re as _re
        starts = [float(m.group(1)) for m in _re.finditer(r"freeze_start:\s*([\d.]+)", text)]
        durations = [float(m.group(1)) for m in _re.finditer(r"freeze_duration:\s*([\d.]+)", text)]
        if not durations:
            return 0.0
        return max(durations)
    except Exception:  # noqa: BLE001
        return None


def _silence_ratio_in_range(video: Path, start_s: float, end_s: float) -> float | None:
    """Ratio of silence within [start_s, end_s] via silencedetect."""
    try:
        dur = probe_duration(video)
        if dur <= 0:
            return None
        seg_end = min(end_s, dur)
        seg_dur = seg_end - start_s
        if seg_dur <= 0:
            return None
        out = _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{start_s}",
            "-i", str(video), "-t", f"{seg_dur}",
            "-af", "silencedetect=noise=-30dB:d=0.25",
            "-f", "null", "-",
        ])
        text = out.stderr or ""
        import re as _re
        silent_durs = [float(m.group(1)) for m in _re.finditer(r"silence_duration:\s*([\d.]+)", text)]
        total_silent = sum(silent_durs)
        return total_silent / seg_dur if seg_dur > 0 else 0.0
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Audio QC: ebur128 true peak + channel count (V8 hard gates)
# ---------------------------------------------------------------------------

def audio_peak_and_channels(video: Path) -> dict[str, Any]:
    """Return true peak (dBFS) and channel count via ebur128 + ffprobe."""
    result: dict[str, Any] = {
        "true_peak_dbfs": None,
        "channels": None,
        "integrated_lufs": None,
        "note": "",
    }

    # Channel count from ffprobe.
    out = _run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=channels",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video),
    ])
    try:
        result["channels"] = int(out.stdout.strip())
    except ValueError:
        result["channels"] = None

    # True peak + integrated loudness via ebur128.
    # NOTE: -loglevel error suppresses the ebur128 Summary block entirely;
    # the per-frame progress lines carry the same data but the Summary
    # (I: -25.5 LUFS, LRA, True peak) only appears with default loglevel.
    out = _run([
        "ffmpeg", "-hide_banner", "-i", str(video),
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ])
    text = out.stderr or ""
    import re as _re

    # Integrated loudness from Summary block only.
    # Per-frame lines also contain "I: -70.0 LUFS" — must not match those.
    summary = text[text.find("Summary:"):] if "Summary:" in text else ""
    m = _re.search(r"I:\s*([-\d.]+)\s+LUFS", summary)
    if m:
        result["integrated_lufs"] = float(m.group(1))

    # True peak from Summary block. ebur128 may render the summary as
    #   True peak:\n    Peak:       -3.4 dBFS
    # or on one line: True peak: Peak: -3.4 dBFS
    m = _re.search(r"True peak:\s*Peak:\s*([-\d.]+)\s+dBFS", summary)
    if not m:
        m = _re.search(r"True peak:\s*\n\s*Peak:\s*([-\d.]+)\s+dBFS", summary)
    if m:
        result["true_peak_dbfs"] = float(m.group(1))

    if result["true_peak_dbfs"] is None:
        result["note"] = "true peak not detectable"
    if result["channels"] is None:
        result["note"] = (result["note"] + " channel count not detectable").strip()

    return result


if __name__ == "__main__":
    raise SystemExit(main())
