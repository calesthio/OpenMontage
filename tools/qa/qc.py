"""Media-level QC tool per docs/openmontage/QA_SPEC.md.

Stdlib + ffmpeg/ffprobe only. No network, no model downloads.
Fail-closed: a check that cannot run => BLOCKED, never PASS.
Optional checks whose inputs are absent => NOT_RUN (listed explicitly).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

# ---- Thresholds (INITIAL GUESSES from QA_SPEC.md; tune after human review) ----
DEFAULT_THRESHOLDS = {
    "black_ratio_max": 0.05,            # fraction of frames that are black
    "freeze_duration_max": 2.0,         # seconds; max single frozen segment
    "silence_ratio_max": 0.10,          # fraction of audio that is silent
    "lufs_target": -14.0,               # integrated loudness target (LUFS)
    "lufs_tolerance": 2.0,              # allowed deviation from LUFS target
    "true_peak_max": -1.5,              # true peak max (dBTP)
    "duration_tolerance": 1.0,          # seconds; script vs actual duration
    "subtitle_drift_max": 0.5,          # seconds; subtitle vs audio drift
}

REQUIRED_CREDIT_FIELDS = ("title", "director", "production")
VALID_RIGHTS = ("explicit_license", "source_policy_us_gov")

VALID_STATUSES = ("PASS", "REVIEW", "BLOCKED", "FAILED", "NOT_RUN")


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tool_version(cmd: str) -> str:
    """Return ffmpeg/ffprobe version string observed, or empty if unreadable."""
    try:
        out = subprocess.run(
            [cmd, "-version"], capture_output=True, text=True, timeout=30
        )
        text = out.stdout or out.stderr or ""
        return text.splitlines()[0] if text else ""
    except Exception:
        return ""


def _find_binary(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _parse_blackdetect(stderr: str, duration: float) -> float:
    """Sum black-detected segment durations / total duration -> black ratio."""
    total_black = 0.0
    for m in re.finditer(r"black_duration:([\d.]+)", stderr):
        total_black += float(m.group(1))
    if duration <= 0:
        return 0.0
    return min(1.0, total_black / duration)


def _parse_freezedetect(stderr: str, duration: float = 0.0) -> float:
    """Max single freeze duration in seconds.

    ffmpeg's freezedetect emits ``freeze_start`` when a frozen region begins and
    ``freeze_end``/``freeze_duration`` when it ends. For a clip that is frozen
    until its end, only ``freeze_start`` appears; treat the remainder of the
    clip as one frozen segment.
    """
    best = 0.0
    durations = [float(m.group(1)) for m in re.finditer(r"freeze_duration:\s*([\d.]+)", stderr)]
    if durations:
        best = max(durations)
    elif re.search(r"freeze_start:\s*", stderr):
        # Frozen from freeze_start to end of clip (or a large fraction).
        m = re.search(r"freeze_start:\s*([\d.]+)", stderr)
        if m and duration > 0:
            start = float(m.group(1))
            best = max(best, duration - start)
    return best


def _parse_silencedetect(stderr: str, duration: float) -> float:
    """Sum silence segment durations / total duration -> silence ratio."""
    total_silent = 0.0
    for m in re.finditer(r"silence_duration:\s*([\d.]+)", stderr):
        total_silent += float(m.group(1))
    if duration <= 0:
        return 0.0
    return min(1.0, total_silent / duration)


def _parse_ebur128(stderr: str) -> dict[str, float | None]:
    """Parse ffmpeg 6.x ebur128 summary block.

    Format (ffmpeg 6.1):
        [Parsed_ebur128_0 @ ...] Summary:

          Integrated loudness:
            I:         -21.8 LUFS
            Threshold: -31.8 LUFS

          Loudness range:
            ...

          True peak:
            Peak:      -12.0 dBFS
    """
    result: dict[str, float | None] = {"integrated_lufs": None, "true_peak": None}
    m = re.search(
        r"Integrated loudness:\s*\n\s*I:\s*([-\d.]+)\s*LUFS", stderr
    )
    if m:
        result["integrated_lufs"] = float(m.group(1))
    m = re.search(r"True peak:\s*\n\s*Peak:\s*([-\d.]+)\s*dB", stderr)
    if m:
        result["true_peak"] = float(m.group(1))
    return result


def _parse_srt_end_times(text: str) -> list[float]:
    """Return the end-time (seconds) of each SRT cue."""
    ends: list[float] = []
    # SRT cue: index\nstart --> end\ntext\n
    for m in re.finditer(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", text
    ):
        ends.append(_hmsms_to_seconds(m.group(2)))
    return ends


def _hmsms_to_seconds(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _load_json(path: str | None):
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _check_entry(
    check_id: str,
    status: str,
    evidence: str,
    measured_value: Any = None,
    threshold: Any = None,
    tool_version: str = "",
) -> dict[str, Any]:
    assert status in VALID_STATUSES, status
    return {
        "job_id": "",  # filled by caller
        "check_id": check_id,
        "status": status,
        "evidence": evidence,
        "measured_value": measured_value,
        "threshold": threshold,
        "tool_version": tool_version,
        "timestamp": _now_utc(),
    }


class QCTool(BaseTool):
    name = "qc"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "quality_control"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install ffmpeg (provides ffprobe). No API keys needed."
    agent_skills = ["ffmpeg"]

    capabilities = [
        "ffprobe_streams",
        "full_decode",
        "blackdetect",
        "freezedetect",
        "silencedetect",
        "ebur128",
        "duration_vs_script",
        "subtitle_sync",
        "credits_complete",
        "claim_ids",
        "rights_basis",
        "added_value",
    ]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50)
    idempotency_key_fields = ["input_path"]
    side_effects = ["writes qa_report.json to output_path"]
    user_visible_verification = [
        "Open qa_report.json and confirm every check has a status and evidence",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path", "output_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "config_path": {"type": "string"},
            "expected_width": {"type": "integer", "default": 1920},
            "expected_height": {"type": "integer", "default": 1080},
            "expected_fps": {"type": "number", "default": 30},
            "narration_manifest": {"type": "string"},
            "subtitle_path": {"type": "string"},
            "credits_path": {"type": "string"},
            "claim_ids_path": {"type": "string"},
            "rights_records_path": {"type": "string"},
            "edit_decisions_path": {"type": "string"},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = inputs["input_path"]
        output_path = inputs["output_path"]
        expected_width = inputs.get("expected_width", 1920)
        expected_height = inputs.get("expected_height", 1080)
        expected_fps = float(inputs.get("expected_fps", 30))

        # Thresholds (INITIAL GUESSES, documented per QA_SPEC.md).
        thresholds = dict(DEFAULT_THRESHOLDS)
        config_path = inputs.get("config_path")
        if config_path:
            loaded = _load_json(config_path)
            if isinstance(loaded, dict):
                thresholds.update(loaded)

        ffprobe_bin = _find_binary("ffprobe")
        ffmpeg_bin = _find_binary("ffmpeg")
        tools_available = bool(ffprobe_bin and ffmpeg_bin)
        tool_version = _tool_version("ffprobe") if tools_available else ""

        report: list[dict[str, Any]] = []
        job_id = os.path.basename(input_path)

        def entry(check_id, status, evidence, measured=None, threshold=None):
            return _check_entry(
                check_id, status, evidence, measured, threshold, tool_version
            )

        # ---- 1. ffprobe_streams ----
        if not tools_available:
            report.append(
                entry("ffprobe_streams", "BLOCKED", "ffprobe/ffmpeg not available")
            )
        else:
            try:
                probe = _run(
                    [
                        ffprobe_bin, "-v", "quiet", "-print_format", "json",
                        "-show_streams", "-show_format", input_path,
                    ],
                )
                if probe.returncode != 0:
                    report.append(
                        entry(
                            "ffprobe_streams", "FAILED",
                            f"ffprobe exit {probe.returncode}: {probe.stderr.strip()[:200]}",
                        )
                    )
                else:
                    info = json.loads(probe.stdout or "{}")
                    streams = info.get("streams", [])
                    fmt = info.get("format", {})
                    video = [s for s in streams if s.get("codec_type") == "video"]
                    audio = [s for s in streams if s.get("codec_type") == "audio"]
                    problems: list[str] = []
                    measured = {
                        "width": video[0].get("width") if video else None,
                        "height": video[0].get("height") if video else None,
                        "fps": video[0].get("r_frame_rate") if video else None,
                        "duration": fmt.get("duration"),
                        "video_streams": len(video),
                        "audio_streams": len(audio),
                    }
                    if not video:
                        problems.append("no video stream")
                    if not audio:
                        problems.append("no audio stream")
                    v = video[0] if video else {}
                    if v.get("width") != expected_width:
                        problems.append(
                            f"width {v.get('width')} != expected {expected_width}"
                        )
                    if v.get("height") != expected_height:
                        problems.append(
                            f"height {v.get('height')} != expected {expected_height}"
                        )
                    # fps: parse "num/den"
                    fps_raw = v.get("r_frame_rate") or "0/1"
                    try:
                        num, den = fps_raw.split("/")
                        fps_val = float(num) / float(den) if float(den) else 0.0
                    except Exception:
                        fps_val = 0.0
                    if abs(fps_val - expected_fps) > 1.0:
                        problems.append(f"fps {fps_val} != expected {expected_fps}")
                    for key in ("width", "height", "duration"):
                        if measured[key] in (None, ""):
                            problems.append(f"empty {key}")
                    if problems:
                        report.append(
                            entry(
                                "ffprobe_streams", "FAILED",
                                "; ".join(problems), measured,
                                f"w={expected_width},h={expected_height},fps={expected_fps}",
                            )
                        )
                    else:
                        report.append(
                            entry(
                                "ffprobe_streams", "PASS",
                                "video+audio streams present; fields resolved",
                                measured,
                                f"w={expected_width},h={expected_height},fps={expected_fps}",
                            )
                        )
            except Exception as exc:  # noqa: BLE001
                report.append(
                    entry("ffprobe_streams", "BLOCKED", f"ffprobe unreadable: {exc}")
                )

        duration = 0.0
        # recover duration for downstream checks if we have probe info
        try:
            if tools_available:
                probe2 = _run(
                    [
                        ffprobe_bin, "-v", "quiet", "-print_format", "json",
                        "-show_format", input_path,
                    ],
                )
                if probe2.returncode == 0:
                    dur = json.loads(probe2.stdout or "{}").get("format", {}).get("duration")
                    if dur is not None:
                        duration = float(dur)
        except Exception:  # noqa: BLE001
            pass

        # ---- 2. full_decode ----
        if not tools_available:
            report.append(entry("full_decode", "BLOCKED", "ffmpeg not available"))
        else:
            try:
                dec = _run(
                    [ffmpeg_bin, "-i", input_path, "-f", "null", "-"],
                )
                if dec.returncode == 0:
                    report.append(
                        entry("full_decode", "PASS", "full decode, no errors")
                    )
                else:
                    report.append(
                        entry(
                            "full_decode", "FAILED",
                            f"decode exit {dec.returncode}: {(dec.stderr or dec.stdout or '').strip()[:200]}",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("full_decode", "BLOCKED", f"decode unrunnable: {exc}"))

        # ---- 3. blackdetect ----
        if not tools_available:
            report.append(entry("blackdetect", "BLOCKED", "ffmpeg not available"))
        else:
            try:
                bd = _run(
                    [ffmpeg_bin, "-i", input_path, "-vf", "blackdetect", "-f", "null", "-"],
                )
                ratio = _parse_blackdetect(bd.stderr, duration)
                thr = thresholds["black_ratio_max"]
                if bd.returncode != 0 and ratio == 0.0:
                    report.append(
                        entry(
                            "blackdetect", "FAILED",
                            f"blackdetect error: {(bd.stderr or '').strip()[:200]}",
                            ratio, thr,
                        )
                    )
                elif ratio <= thr:
                    report.append(
                        entry(
                            "blackdetect", "PASS",
                            f"black ratio {ratio:.4f} <= {thr}", ratio, thr,
                        )
                    )
                else:
                    report.append(
                        entry(
                            "blackdetect", "FAILED",
                            f"black ratio {ratio:.4f} > {thr}", ratio, thr,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("blackdetect", "BLOCKED", f"blackdetect unrunnable: {exc}"))

        # ---- 4. freezedetect ----
        if not tools_available:
            report.append(entry("freezedetect", "BLOCKED", "ffmpeg not available"))
        else:
            try:
                fd = _run(
                    [ffmpeg_bin, "-i", input_path, "-vf", "freezedetect", "-f", "null", "-"],
                )
                freeze_dur = _parse_freezedetect(fd.stderr, duration)
                thr = thresholds["freeze_duration_max"]
                if freeze_dur <= thr:
                    report.append(
                        entry(
                            "freezedetect", "PASS",
                            f"max freeze {freeze_dur:.2f}s <= {thr}s",
                            freeze_dur, f"{thr}s",
                        )
                    )
                else:
                    report.append(
                        entry(
                            "freezedetect", "FAILED",
                            f"max freeze {freeze_dur:.2f}s > {thr}s",
                            freeze_dur, f"{thr}s",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("freezedetect", "BLOCKED", f"freezedetect unrunnable: {exc}"))

        # ---- 5. silencedetect ----
        if not tools_available:
            report.append(entry("silencedetect", "BLOCKED", "ffmpeg not available"))
        else:
            try:
                sd = _run(
                    [ffmpeg_bin, "-i", input_path, "-af", "silencedetect", "-f", "null", "-"],
                )
                ratio = _parse_silencedetect(sd.stderr, duration)
                thr = thresholds["silence_ratio_max"]
                if ratio <= thr:
                    report.append(
                        entry(
                            "silencedetect", "PASS",
                            f"silence ratio {ratio:.4f} <= {thr}", ratio, thr,
                        )
                    )
                else:
                    report.append(
                        entry(
                            "silencedetect", "FAILED",
                            f"silence ratio {ratio:.4f} > {thr}", ratio, thr,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("silencedetect", "BLOCKED", f"silencedetect unrunnable: {exc}"))

        # ---- 6. ebur128 ----
        if not tools_available:
            report.append(entry("ebur128", "BLOCKED", "ffmpeg not available"))
        else:
            try:
                eb = _run(
                    [ffmpeg_bin, "-i", input_path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                )
                parsed = _parse_ebur128(eb.stderr)
                i_lufs = parsed["integrated_lufs"]
                tp = parsed["true_peak"]
                thr_lufs = thresholds["lufs_target"]
                thr_tp = thresholds["true_peak_max"]
                tol = thresholds["lufs_tolerance"]
                parts: list[str] = []
                ok = True
                if i_lufs is None:
                    parts.append("integrated LUFS not reported"); ok = False
                else:
                    parts.append(f"I={i_lufs:.1f} LUFS (target {thr_lufs} +/- {tol})")
                    if abs(i_lufs - thr_lufs) > tol:
                        ok = False
                if tp is None:
                    parts.append("true peak not reported"); ok = False
                else:
                    parts.append(f"TP={tp:.1f} dBTP (max {thr_tp})")
                    if tp > thr_tp:
                        ok = False
                status = "PASS" if ok else "FAILED"
                report.append(
                    entry(
                        "ebur128", status,
                        "; ".join(parts),
                        f"I={i_lufs}, TP={tp}",
                        f"I={thr_lufs} +/- {tol} LUFS, TP<={thr_tp} dBTP",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("ebur128", "BLOCKED", f"ebur128 unrunnable: {exc}"))

        # ---- 7. duration_vs_script ----
        manifest = _load_json(inputs.get("narration_manifest"))
        if manifest is None:
            report.append(
                entry("duration_vs_script", "NOT_RUN", "narration_manifest not provided")
            )
        else:
            expected_dur = manifest.get("expected_duration")
            tol = manifest.get("tolerance", thresholds["duration_tolerance"])
            if expected_dur is None or duration <= 0:
                report.append(
                    entry(
                        "duration_vs_script", "FAILED",
                        "cannot compare duration (no manifest duration or probe duration)",
                    )
                )
            else:
                drift = abs(duration - float(expected_dur))
                if drift <= float(tol):
                    report.append(
                        entry(
                            "duration_vs_script", "PASS",
                            f"duration {duration:.2f}s vs script {expected_dur}s (drift {drift:.2f}s <= {tol}s)",
                            drift, f"{tol}s",
                        )
                    )
                else:
                    report.append(
                        entry(
                            "duration_vs_script", "FAILED",
                            f"duration {duration:.2f}s vs script {expected_dur}s (drift {drift:.2f}s > {tol}s)",
                            drift, f"{tol}s",
                        )
                    )

        # ---- 8. subtitle_sync ----
        sub_path = inputs.get("subtitle_path")
        if not sub_path or not Path(sub_path).is_file():
            report.append(
                entry("subtitle_sync", "NOT_RUN", "subtitle file not provided")
            )
        else:
            try:
                text = Path(sub_path).read_text(encoding="utf-8")
                ends = _parse_srt_end_times(text)
                thr = thresholds["subtitle_drift_max"]
                if not ends:
                    report.append(
                        entry("subtitle_sync", "FAILED", "no subtitle cues parsed")
                    )
                else:
                    last_end = max(ends)
                    drift = max(0.0, last_end - duration)
                    if drift <= thr:
                        report.append(
                            entry(
                                "subtitle_sync", "PASS",
                                f"last cue ends {last_end:.2f}s <= audio {duration:.2f}s (+{thr}s tolerance)",
                                drift, f"{thr}s",
                            )
                        )
                    else:
                        report.append(
                            entry(
                                "subtitle_sync", "FAILED",
                                f"last cue ends {last_end:.2f}s, audio {duration:.2f}s, drift {drift:.2f}s > {thr}s",
                                drift, f"{thr}s",
                            )
                        )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("subtitle_sync", "BLOCKED", f"subtitle parse failed: {exc}"))

        # ---- 9. credits_complete ----
        credits_path = inputs.get("credits_path")
        if not credits_path or not Path(credits_path).is_file():
            report.append(
                entry("credits_complete", "NOT_RUN", "credits.txt not provided")
            )
        else:
            try:
                text = Path(credits_path).read_text(encoding="utf-8").lower()
                missing = [f for f in REQUIRED_CREDIT_FIELDS if f not in text]
                if missing:
                    report.append(
                        entry(
                            "credits_complete", "FAILED",
                            f"missing credit fields: {', '.join(missing)}",
                            None, ", ".join(REQUIRED_CREDIT_FIELDS),
                        )
                    )
                else:
                    report.append(
                        entry(
                            "credits_complete", "PASS",
                            "all required credit fields present",
                            None, ", ".join(REQUIRED_CREDIT_FIELDS),
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("credits_complete", "BLOCKED", f"credits unreadable: {exc}"))

        # ---- 10. claim_ids ----
        claims_path = inputs.get("claim_ids_path")
        if not claims_path or not Path(claims_path).is_file():
            report.append(
                entry("claim_ids", "NOT_RUN", "claim_ids ledger not provided")
            )
        else:
            try:
                data = _load_json(claims_path)
                if not isinstance(data, list):
                    report.append(
                        entry("claim_ids", "FAILED", "claim_ids ledger is not a list")
                    )
                else:
                    total = len(data)
                    missing = [i for i, c in enumerate(data) if not c.get("claim_id")]
                    if missing:
                        report.append(
                            entry(
                                "claim_ids", "FAILED",
                                f"{len(missing)}/{total} sentences lack claim_id",
                                total, "100% with claim_id",
                            )
                        )
                    else:
                        report.append(
                            entry(
                                "claim_ids", "PASS",
                                f"{total}/{total} sentences have claim_id",
                                total, "100% with claim_id",
                            )
                        )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("claim_ids", "BLOCKED", f"claim_ids unreadable: {exc}"))

        # ---- 11. rights_basis ----
        rights_path = inputs.get("rights_records_path")
        if not rights_path or not Path(rights_path).is_file():
            report.append(
                entry("rights_basis", "NOT_RUN", "rights records not provided")
            )
        else:
            try:
                data = _load_json(rights_path)
                if not isinstance(data, list):
                    report.append(
                        entry("rights_basis", "FAILED", "rights records is not a list")
                    )
                else:
                    total = len(data)
                    bad = [
                        i for i, c in enumerate(data)
                        if c.get("rights_basis") not in VALID_RIGHTS
                    ]
                    if bad:
                        report.append(
                            entry(
                                "rights_basis", "FAILED",
                                f"{len(bad)}/{total} clips lack valid rights_basis",
                                total, f"100% in {VALID_RIGHTS}",
                            )
                        )
                    else:
                        report.append(
                            entry(
                                "rights_basis", "PASS",
                                f"{total}/{total} clips have valid rights_basis",
                                total, f"100% in {VALID_RIGHTS}",
                            )
                        )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("rights_basis", "BLOCKED", f"rights unreadable: {exc}"))

        # ---- 12. added_value ----
        edit_path = inputs.get("edit_decisions_path")
        if not edit_path or not Path(edit_path).is_file():
            report.append(
                entry("added_value", "NOT_RUN", "edit_decisions not provided")
            )
        else:
            try:
                data = _load_json(edit_path)
                if not isinstance(data, dict) or "cuts" not in data:
                    report.append(
                        entry("added_value", "FAILED", "edit_decisions missing cuts[]")
                    )
                else:
                    cuts = data["cuts"]
                    unannotated_long = [
                        c for c in cuts
                        if c.get("duration", 0) > 20 and not c.get("annotation")
                    ]
                    if unannotated_long:
                        report.append(
                            entry(
                                "added_value", "FAILED",
                                f"{len(unannotated_long)} unannotated clips > 20s",
                                len(unannotated_long), "0 unannotated > 20s",
                            )
                        )
                    else:
                        report.append(
                            entry(
                                "added_value", "PASS",
                                "no unannotated clips > 20s",
                                0, "0 unannotated > 20s",
                            )
                        )
            except Exception as exc:  # noqa: BLE001
                report.append(entry("added_value", "BLOCKED", f"added_value unrunnable: {exc}"))

        # ---- overall verdict ----
        statuses = [e["status"] for e in report]
        if any(s in ("FAILED", "BLOCKED") for s in statuses):
            verdict = "FAILED"
        elif any(s == "NOT_RUN" for s in statuses):
            verdict = "NOT_RUN"
        else:
            verdict = "PASS"

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "verdict": verdict,
                "report": str(out),
                "check_count": len(report),
                "thresholds": thresholds,
            },
            artifacts=[str(out)],
            duration_seconds=0.0,
        )
