"""VLM zoom rating: frame-accurate sub-beat extraction inside flagged windows.

Takes the coarse ratings from ``vlm_clip_rating`` (segments/highlights
anchored to a few sampled frames) and re-examines each promising window at
high frame density (4 fps), producing sub-beats with precise timestamps,
camera angle, subject facing direction, deep-dive descriptions, and vibe.

This is the layer that turns "a good moment somewhere around 34-41s" into
"the collar interaction starts at 38.5s and ends at 41.6s", which is what a
real editor needs to cut without watching.

Usage (as a tool)::

    {
      "ratings_path": "/path/to/clip_tags.jsonl",
      "output_path": "/path/to/clip_zooms.jsonl",
      "model": "gemma4:12b",
      "ollama_url": "http://127.0.0.1:11434",
      "max_windows_per_clip": 4
    }
"""

from __future__ import annotations

import json
import tempfile
import time
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
    ToolStatus,
    ToolTier,
)
from tools.video.vlm_rating_common import (
    append_record,
    extract_window,
    images_b64,
    load_rated_ids,
    ollama_generate,
    ollama_model_available,
    parse_vlm_json,
    safe_float,
    validate_local_ollama_url,
)


class VlmZoomRating(BaseTool):
    name = "vlm_zoom_rating"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "temporal_zoom_rating"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Install Ollama and pull the tested model: `ollama pull gemma4:12b` "
        "(~8GB VRAM, recommended). Smaller models are untested; see the "
        "vlm-footage-rating skill for guidance."
    )
    agent_skills = ["vlm-footage-rating"]

    capabilities = [
        "frame_accurate_timestamps",
        "sub_beat_segmentation",
        "camera_angle_detection",
        "subject_facing_detection",
        "deep_dive_description",
        "vibe_classification",
    ]
    supports = {"resume": True, "local_only": True}
    best_for = [
        "getting cut-precise timestamps for a highlight window",
        "describing a promising moment in enough detail to edit without watching",
        "match-cut continuity via subject facing direction",
    ]
    not_good_for = [
        "first-pass semantic indexing (use vlm_clip_rating)",
        "ranking clips against each other (use vlm_comparative_rank)",
    ]

    input_schema = {
        "type": "object",
        "required": ["ratings_path", "output_path"],
        "properties": {
            "ratings_path": {
                "type": "string",
                "description": "JSONL from vlm_clip_rating (coarse pass).",
            },
            "output_path": {
                "type": "string",
                "description": "JSONL output. Re-running skips done clips.",
            },
            "model": {"type": "string", "default": "gemma4:12b"},
            "ollama_url": {
                "type": "string",
                "default": "http://127.0.0.1:11434",
                "description": "Local Ollama endpoint. Only localhost/loopback URLs are accepted.",
            },
            "max_windows_per_clip": {"type": "integer", "default": 4, "minimum": 1},
            "zoom_fps": {"type": "number", "default": 4.0},
            "max_frames_per_window": {"type": "integer", "default": 12},
            "frame_scale": {
                "type": "integer",
                "default": 640,
                "minimum": 320,
                "maximum": 1280,
                "description": "Frame width for the VLM. Smaller (384-480) is faster "
                               "and uses less VRAM; best for 4b models.",
            },
            "temperature": {"type": "number", "default": 0.1},
            "num_predict": {"type": "integer", "default": 900},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=3584, disk_mb=200,
        network_required=False,
    )
    side_effects = ["writes JSONL output", "writes temporary frame jpgs"]
    user_visible_verification = [
        "Open output_path and check sub_beats have precise start_s/end_s.",
    ]

    def get_status(self) -> ToolStatus:
        import shutil

        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            return ToolStatus.UNAVAILABLE
        return (
            ToolStatus.AVAILABLE
            if ollama_model_available(model="gemma4:12b")
            else ToolStatus.UNAVAILABLE
        )

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return max(30.0, self._count_windows(inputs) * 30.0)

    def _count_windows(self, inputs: dict[str, Any]) -> int:
        import glob

        n = 0
        ratings = inputs.get("ratings_path", "")
        if ratings and Path(ratings).exists():
            with open(ratings) as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    n += len(rec.get("highlights", []) or []) + len(
                        rec.get("segments", []) or []
                    )
        return n

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            ratings_path = inputs["ratings_path"]
            output_path = str(inputs["output_path"])
            if not Path(ratings_path).exists():
                return ToolResult(
                    success=False,
                    error=f"ratings_path {ratings_path} does not exist",
                )

            model = inputs.get("model", "gemma4:12b")
            ollama_url = validate_local_ollama_url(
                inputs.get("ollama_url", "http://127.0.0.1:11434")
            )
            max_windows = int(inputs.get("max_windows_per_clip", 4))
            zoom_fps = float(inputs.get("zoom_fps", 4.0))
            max_frames = int(inputs.get("max_frames_per_window", 12))
            frame_scale = int(inputs.get("frame_scale", 640))
            temperature = float(inputs.get("temperature", 0.1))
            num_predict = int(inputs.get("num_predict", 900))
            tmp_dir = Path(inputs.get("tmp_dir") or tempfile.gettempdir()) / "vlm_zoom_frames"

            clips = self._load_coarse(ratings_path)
            done = load_rated_ids(output_path)
            prompt = _build_prompt()

            zoomed = 0
            failed = 0
            for clip, rec in clips.items():
                if clip in done:
                    continue
                windows = self._pick_windows(rec, max_windows)
                if not windows:
                    continue
                video = rec.get("file") or rec.get("path")
                if not video or not Path(video).exists():
                    failed += 1
                    continue
                clip_result = {
                    "clip": clip,
                    "file": video,
                    "duration_s": rec.get("duration_s"),
                    "zooms": [],
                }
                for (t0, t1, wtype) in windows:
                    try:
                        paths, frame_map, win_dur = extract_window(
                            video, t0, t1, str(tmp_dir),
                            zoom_fps=zoom_fps, max_frames=max_frames,
                            scale=frame_scale,
                        )
                        if len(paths) < 2:
                            continue
                        images = images_b64(paths)
                        filled = prompt.format(
                            n=len(paths), dur=win_dur, t0=t0, frame_map=frame_map
                        )
                        raw = ollama_generate(
                            ollama_url, model, filled, images,
                            temperature=temperature, num_predict=num_predict,
                        )
                        result = parse_vlm_json(raw)
                        result["window_start_s"] = round(t0, 2)
                        result["window_end_s"] = round(t1, 2)
                        result["window_type"] = wtype
                        clip_result["zooms"].append(result)
                    except Exception as exc:  # noqa: BLE001
                        clip_result["zooms"].append({
                            "error": str(exc)[:300],
                            "window_start_s": round(t0, 2),
                            "window_end_s": round(t1, 2),
                        })
                successful_zooms = [
                    zoom for zoom in clip_result["zooms"] if not zoom.get("error")
                ]
                if successful_zooms:
                    append_record(output_path, clip_result)
                    zoomed += 1
                elif clip_result["zooms"]:
                    clip_result["error"] = "all_windows_failed"
                    append_record(output_path, clip_result)
                    failed += 1

            return ToolResult(
                success=True,
                data={
                    "zoomed": zoomed,
                    "failed": failed,
                    "output_path": output_path,
                },
                duration_seconds=round(time.time() - start, 3),
                cost_usd=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            import traceback

            return ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_coarse(ratings_path: str) -> dict[str, dict[str, Any]]:
        clips: dict[str, dict[str, Any]] = {}
        with open(ratings_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("error"):
                    continue
                clip = rec.get("clip")
                if clip:
                    clips[clip] = rec
        return clips

    @staticmethod
    def _pick_windows(
        rec: dict[str, Any], max_windows: int
    ) -> list[tuple[float, float, str]]:
        windows: list[tuple[float, float, str]] = []
        dur = rec.get("duration_s") or 10.0
        for h in rec.get("highlights", []) or []:
            if not isinstance(h, dict):
                continue
            windows.append((
                safe_float(h.get("start_s"), 0.0),
                safe_float(h.get("end_s"), dur),
                h.get("type", "highlight"),
            ))
        for s in rec.get("segments", []) or []:
            if not isinstance(s, dict):
                continue
            windows.append((
                safe_float(s.get("start_s"), 0.0),
                safe_float(s.get("end_s"), dur),
                "segment",
            ))
        # Dedupe near-identical windows, clamp to duration, cap count.
        seen: set[tuple[float, float]] = set()
        unique: list[tuple[float, float, str]] = []
        for (t0, t1, wtype) in windows:
            t0 = max(0.0, min(t0, dur - 0.5))
            t1 = max(t0 + 0.5, min(t1, dur))
            key = (round(t0, 1), round(t1, 1))
            if key in seen:
                continue
            seen.add(key)
            unique.append((t0, t1, wtype))
            if len(unique) >= max_windows:
                break
        return unique


def _build_prompt() -> str:
    return """You are a professional film editor's assistant. You are given {n} consecutive frames from a
SHORT WINDOW of video footage (a {dur:.1f}s segment starting at {t0:.2f}s).
The window was flagged as interesting. Find the precise sub-beats inside it and describe the promising moments IN DEPTH.

FRAME TIMESTAMPS (seconds into this window):
{frame_map}

Return ONLY valid JSON (no markdown) with this schema:
{{
  "sub_beats": [
    {{
      "start_s": 0.0,
      "end_s": 0.0,
      "action": "precise description of what happens",
      "deep_dive": "2-3 sentence in-depth description: body language, interaction, what makes it usable",
      "behavior": "walking_calm"|"pulling"|"sniffing"|"trotting"|"sitting"|"lying"|"greeting"|"playing"|
"expression"|"other",
      "camera_angle": "eye_level"|"low"|"high"|"dutch",
      "subject_facing": "camera"|"left"|"right"|"away"|"other_subject",
      "subject_visibility": "not_visible"|"partial"|"clear"|"featured",
      "quality_score": 0.0,
      "vibe": "calm"|"candid"|"playful"|"energetic"|"tender"|"tense"|"neutral",
      "use": "slow_mo"|"cutaway"|"b-roll"|"hero_subject"|"opening"|"closing"
    }}
  ],
  "best_moment_s": 0.0,
  "best_moment_desc": "the single best frame time and why (in depth)",
  "window_vibe": "one-word vibe of the whole window",
  "notes": "one sentence"
}}

RULES:
- start_s/end_s are REAL seconds INTO THE WINDOW (0 = window start). Use frame timestamps to anchor.
- Split into as many sub-beats as genuinely distinct (1-6).
- quality_score 0.0-1.0.
- deep_dive is the most important field: describe what is actually happening with enough detail an editor can cut without watching.
- subject_facing is for match cuts: which direction is the main subject facing/moving.
- Only mark subject_visibility featured/clear if the subject is actually prominent.
"""
