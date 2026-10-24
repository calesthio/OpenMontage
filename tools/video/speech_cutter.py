"""Transcript-driven jump cuts: tighten pauses and drop hesitation sounds.

Unlike silence_cutter (audio level only), this cuts on word timings, so it
can remove fillers ("əə", "ee", "ımm", "hmm") that are not silent, and it
re-maps every kept word onto the new timeline. Captions built from the
remapped words stay in sync with the cut video.

Needs a word-level transcript (transcriber -> transcript_corrector). When no
transcript is available, use silence_cutter instead.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from lib import az_text
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)

# Hesitation sounds only. Discourse words ("yəni", "bax", "necə deyim") carry
# meaning often enough that they are never removed automatically.
DEFAULT_FILLER_PATTERN = r"^(e{2,}|ə{2,}|ı{2,}|ı?m{2,}|h+m+|e+h+|ə+h+|a{2,}h*)$"


class SpeechCutter(BaseTool):
    name = "speech_cutter"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg"]

    capabilities = ["jump_cut", "filler_removal", "pause_tightening", "timeline_remap"]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Source video (never modified)."},
            "output_path": {"type": "string"},
            "transcript_path": {
                "type": "string",
                "description": "Transcript JSON with segments[].words[] (start/end/word).",
            },
            "words": {
                "type": "array",
                "description": "Word list, used when transcript_path is omitted.",
            },
            "min_silence_s": {
                "type": "number",
                "default": 0.5,
                "description": "Gaps between words longer than this are cut.",
            },
            "keep_pause_s": {
                "type": "number",
                "default": 0.2,
                "description": "Breathing room kept around each cut (split before/after).",
            },
            "remove_fillers": {"type": "boolean", "default": True},
            "filler_words": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Extra filler tokens to drop (matched Azerbaijani-case-insensitively).",
            },
            "render": {
                "type": "boolean",
                "default": True,
                "description": "False returns the cut plan without rendering.",
            },
            "crf": {"type": "integer", "default": 18},
            "preset": {"type": "string", "default": "fast"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "keep_segments": {"type": "array"},
            "removed": {"type": "array"},
            "words": {"type": "array"},
            "input_duration": {"type": "number"},
            "output_duration": {"type": "number"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500)
    idempotency_key_fields = [
        "input_path", "transcript_path", "words", "min_silence_s",
        "keep_pause_s", "remove_fillers", "filler_words",
    ]
    side_effects = ["writes cut video to output_path", "writes remapped transcript JSON"]
    user_visible_verification = [
        "Watch every cut point: no clipped words, no audible clicks",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        input_path = Path(inputs["input_path"])
        if not input_path.is_file():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        words = self._load_words(inputs)
        if words is None:
            return ToolResult(success=False, error="Provide transcript_path or words")
        if not words:
            return ToolResult(
                success=False,
                error="Transcript has no timed words; use silence_cutter instead",
            )

        duration = self._probe_duration(input_path)
        plan = self.plan_cuts(
            words,
            duration,
            min_silence_s=float(inputs.get("min_silence_s", 0.5)),
            keep_pause_s=float(inputs.get("keep_pause_s", 0.2)),
            remove_fillers=bool(inputs.get("remove_fillers", True)),
            extra_fillers=inputs.get("filler_words") or [],
        )

        output_path = Path(
            inputs.get("output_path") or input_path.with_name(f"{input_path.stem}_speechcut.mp4")
        )
        if output_path.resolve() == input_path.resolve():
            return ToolResult(success=False, error="output_path must differ from input_path")

        artifacts: list[str] = []
        if inputs.get("render", True):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._render(input_path, output_path, plan["keep_segments"], inputs)
            artifacts.append(str(output_path))

        transcript_out = output_path.with_suffix(".transcript.json")
        transcript_out.parent.mkdir(parents=True, exist_ok=True)
        transcript_out.write_text(
            json.dumps(
                {"source": str(input_path), "segments": [{"id": 0, "words": plan["words"],
                 "start": 0.0, "end": plan["output_duration"],
                 "text": " ".join(w["word"] for w in plan["words"])}], **plan},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        artifacts.append(str(transcript_out))

        return ToolResult(
            success=True,
            data={
                **plan,
                "output": str(output_path) if inputs.get("render", True) else None,
                "transcript_output": str(transcript_out),
            },
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )

    @staticmethod
    def _load_words(inputs: dict[str, Any]) -> list[dict] | None:
        if inputs.get("transcript_path"):
            path = Path(inputs["transcript_path"])
            if not path.is_file():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            words = [w for s in data.get("segments", []) for w in s.get("words", [])]
            if not words:
                words = data.get("word_timestamps") or []
        elif inputs.get("words") is not None:
            words = inputs["words"]
        else:
            return None
        return [
            w for w in words
            if w.get("start") is not None and w.get("end") is not None and str(w.get("word", "")).strip()
        ]

    @staticmethod
    def plan_cuts(
        words: list[dict],
        duration: float,
        *,
        min_silence_s: float = 0.5,
        keep_pause_s: float = 0.2,
        remove_fillers: bool = True,
        extra_fillers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pure cut planning; returns keep segments, removals and remapped words."""
        filler_re = re.compile(DEFAULT_FILLER_PATTERN)
        extra = {az_text.match_key(f) for f in (extra_fillers or [])}
        half = keep_pause_s / 2

        words = sorted(words, key=lambda w: float(w["start"]))
        kept: list[dict] = []
        removed: list[dict] = []
        for w in words:
            key = az_text.match_key(str(w["word"]))
            if remove_fillers and key and (filler_re.match(key) or key in extra):
                removed.append({"start": w["start"], "end": w["end"], "reason": "filler", "word": w["word"]})
            else:
                kept.append(w)

        segments: list[list[float]] = []
        for w in kept:
            ws, we = float(w["start"]), float(w["end"])
            if segments and ws - segments[-1][1] <= min_silence_s:
                segments[-1][1] = max(segments[-1][1], we)
            else:
                segments.append([ws, we])

        padded: list[list[float]] = []
        for s, e in segments:
            s = max(0.0, s - half)
            e = min(duration, e + half) if duration else e + half
            if padded and s <= padded[-1][1]:
                padded[-1][1] = max(padded[-1][1], e)
            else:
                padded.append([s, e])

        cursor = 0.0
        for s, e in padded:
            if s - cursor > 0.01:
                removed.append({"start": round(cursor, 3), "end": round(s, 3), "reason": "pause"})
            cursor = e
        if duration and duration - cursor > 0.01:
            removed.append({"start": round(cursor, 3), "end": round(duration, 3), "reason": "pause"})

        # Remap kept words onto the cut timeline.
        remapped: list[dict] = []
        offset_base = 0.0
        seg_idx = 0
        for w in kept:
            ws = float(w["start"])
            while seg_idx < len(padded) and ws >= padded[seg_idx][1]:
                offset_base += padded[seg_idx][1] - padded[seg_idx][0]
                seg_idx += 1
            if seg_idx >= len(padded):
                break
            seg_start = padded[seg_idx][0]
            remapped.append({
                **w,
                "start": round(offset_base + ws - seg_start, 3),
                "end": round(offset_base + float(w["end"]) - seg_start, 3),
                "source_start": w["start"],
                "source_end": w["end"],
            })

        out_duration = sum(e - s for s, e in padded)
        return {
            "keep_segments": [{"start": round(s, 3), "end": round(e, 3)} for s, e in padded],
            "removed": sorted(removed, key=lambda r: r["start"]),
            "words": remapped,
            "input_duration": round(duration, 3),
            "output_duration": round(out_duration, 3),
            "removed_seconds": round(max(0.0, duration - out_duration), 3) if duration else None,
        }

    def _probe_duration(self, path: Path) -> float:
        result = self.run_command([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ])
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0.0

    def _render(self, src: Path, dst: Path, segments: list[dict], inputs: dict[str, Any]) -> None:
        fade = 0.01  # 10 ms fades remove clicks at every audio cut
        parts = []
        labels = []
        for i, seg in enumerate(segments):
            s, e = seg["start"], seg["end"]
            d = max(0.0, e - s)
            parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
            parts.append(
                f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d={fade},afade=t=out:st={max(0.0, d - fade):.3f}:d={fade}[a{i}]"
            )
            labels.append(f"[v{i}][a{i}]")
        parts.append(f"{''.join(labels)}concat=n={len(segments)}:v=1:a=1[v][a]")

        script = dst.with_suffix(".filter.txt")
        script.write_text(";\n".join(parts), encoding="utf-8")
        try:
            self.run_command([
                "ffmpeg", "-y", "-i", str(src),
                "-filter_complex_script", str(script),
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", str(inputs.get("crf", 18)),
                "-preset", inputs.get("preset", "fast"), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(dst),
            ], timeout=1800)
        finally:
            script.unlink(missing_ok=True)
