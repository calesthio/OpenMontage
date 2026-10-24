"""Technical quality gate for an Instagram Reels deliverable.

Checks the file the client will receive, not the plan: container and codecs,
1080x1920 / 9:16, frame rate, full decode without errors, A/V duration
drift, black frames, black borders, audio clipping and integrated loudness.
Every check reports its measured value so a failure is explainable.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolCommandError,
    ToolStability,
    ToolTier,
)


class ReelsQC(BaseTool):
    name = "reels_qc"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg"]

    capabilities = ["deliverable_qc", "loudness_check", "black_frame_check", "format_check"]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string"},
            "width": {"type": "integer", "default": 1080},
            "height": {"type": "integer", "default": 1920},
            "fps": {"type": "number", "default": 30},
            "max_duration_s": {"type": "number", "default": 90},
            "loudness_target_lufs": {"type": "number", "default": -14},
            "loudness_tolerance": {"type": "number", "default": 2.0},
            "max_true_peak_db": {"type": "number", "default": -1.0},
            "report_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=1)
    idempotency_key_fields = ["input_path", "width", "height", "fps", "max_duration_s"]
    side_effects = ["writes QC report JSON to report_path"]
    user_visible_verification = ["Read failed and warning checks before delivery"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        path = Path(inputs["input_path"])
        if not path.is_file():
            return ToolResult(success=False, error=f"Input not found: {path}")

        checks: list[dict[str, Any]] = []

        def check(name: str, ok: bool, value: Any, expected: Any, severity: str = "fail") -> None:
            checks.append({
                "check": name,
                "status": "pass" if ok else severity,
                "value": value,
                "expected": expected,
            })

        try:
            probe = json.loads(self.run_command([
                "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path),
            ]).stdout or "{}")
        except ToolCommandError as exc:
            report = {
                "input": str(path),
                "passed": False,
                "failed": ["readable"],
                "warnings": [],
                "checks": [{
                    "check": "readable",
                    "status": "fail",
                    "value": (exc.stderr or "").strip().splitlines()[-1:] or str(exc),
                    "expected": "a playable MP4",
                }],
            }
            return ToolResult(success=True, data=report, duration_seconds=round(time.time() - start, 2))
        fmt = probe.get("format", {})
        video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
        audio = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})

        w, h = int(inputs.get("width", 1080)), int(inputs.get("height", 1920))
        check("container_mp4", "mp4" in fmt.get("format_name", ""), fmt.get("format_name"), "mp4")
        check("video_codec_h264", video.get("codec_name") == "h264", video.get("codec_name"), "h264")
        check("pixel_format", video.get("pix_fmt") == "yuv420p", video.get("pix_fmt"), "yuv420p")
        check("resolution", (video.get("width"), video.get("height")) == (w, h),
              f"{video.get('width')}x{video.get('height')}", f"{w}x{h}")
        sar = video.get("sample_aspect_ratio") or "1:1"
        check("square_pixels", sar in ("1:1", "0:1"), sar, "1:1")
        fps = self._rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        check("frame_rate", fps is not None and abs(fps - float(inputs.get("fps", 30))) < 0.05,
              fps, inputs.get("fps", 30))
        check("audio_codec_aac", audio.get("codec_name") == "aac", audio.get("codec_name"), "aac")

        duration = float(fmt.get("duration") or 0)
        check("duration", 0 < duration <= float(inputs.get("max_duration_s", 90)),
              round(duration, 2), f"<= {inputs.get('max_duration_s', 90)} s", severity="warning")

        v_dur = float(video.get("duration") or 0)
        a_dur = float(audio.get("duration") or 0)
        drift = abs(v_dur - a_dur) if v_dur and a_dur else None
        check("av_duration_drift", drift is not None and drift <= 0.1,
              None if drift is None else round(drift, 3), "<= 0.1 s")

        # One decode pass gathers decode errors, black frames, borders and loudness.
        graph = "[0:v]blackdetect=d=0.2:pix_th=0.08,cropdetect=limit=24:round=2:reset=0[v]"
        maps = ["-map", "[v]"]
        if audio:
            graph += ";[0:a]ebur128=peak=true[a]"
            maps += ["-map", "[a]"]
        try:
            log = self.run_command([
                "ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(path),
                "-filter_complex", graph, *maps, "-f", "null", "-",
            ], timeout=1800).stderr or ""
            returncode = 0
        except ToolCommandError as exc:
            log, returncode = exc.stderr or "", exc.returncode

        errors = [ln for ln in log.splitlines() if re.search(r"\b(error|corrupt|invalid)\b", ln, re.I)
                  and "blackdetect" not in ln and "cropdetect" not in ln]
        check("decodes_cleanly", returncode == 0 and not errors, len(errors), 0)

        blacks = [
            {"start": float(m.group(1)), "end": float(m.group(2))}
            for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", log)
        ]
        check("black_frames", not blacks, blacks, "none", severity="warning")

        crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", log)
        if crops:
            cw, ch, _, _ = map(int, crops[-1])
            bordered = cw < w - 8 or ch < h - 8
            check("black_borders", not bordered, f"{cw}x{ch} active of {w}x{h}", "full frame")

        lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
        peak = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", log)
        integrated = float(lufs[-1]) if lufs else None
        true_peak = float(peak[-1]) if peak and peak[-1] != "-inf" else None
        target = float(inputs.get("loudness_target_lufs", -14))
        tol = float(inputs.get("loudness_tolerance", 2.0))
        check("loudness_lufs", integrated is not None and abs(integrated - target) <= tol,
              integrated, f"{target} ± {tol}", severity="warning")
        max_peak = float(inputs.get("max_true_peak_db", -1.0))
        check("true_peak_no_clipping", true_peak is not None and true_peak <= max_peak,
              true_peak, f"<= {max_peak} dBTP")

        failed = [c for c in checks if c["status"] == "fail"]
        warnings = [c for c in checks if c["status"] == "warning"]
        report = {
            "input": str(path),
            "passed": not failed,
            "failed": [c["check"] for c in failed],
            "warnings": [c["check"] for c in warnings],
            "checks": checks,
            "duration_s": round(duration, 3),
            "file_size_mb": round(path.stat().st_size / 1_048_576, 2),
        }
        if inputs.get("report_path"):
            out = Path(inputs["report_path"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(success=True, data=report, duration_seconds=round(time.time() - start, 2))

    @staticmethod
    def _rate(value: str | None) -> float | None:
        if not value or value == "0/0":
            return None
        if "/" in value:
            num, den = value.split("/")
            return float(num) / float(den) if float(den) else None
        return float(value)
