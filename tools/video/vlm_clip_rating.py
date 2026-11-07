"""VLM clip rating: coarse semantic pass over a folder of video clips.

Rates every video in a folder with a local vision-language model (Ollama
served, e.g. Gemma 3n / Gemma 4 / Qwen-VL), producing one JSON record per
clip with behavior, camera, shot, product-of-interest visibility, segments,
and highlights. This is the layer CLIP cannot provide: temporal/behavioral
semantics instead of static frame similarity.

The tool is intentionally generic: ``focus_prompt`` lets a campaign describe
the subject that matters (a product, an animal behavior, a person), and the
rating schema stays neutral so downstream consumers (zoom pass, editorial
ranking) can operate on any footage.

Usage (as a tool)::

    {
      "input_dir": "/path/to/clips",
      "output_path": "/path/to/clip_tags.jsonl",
      "focus_prompt": "a black dog collar (the product being advertised)",
      "model": "gemma4:12b",
      "ollama_url": "http://127.0.0.1:11434",
      "frames_per_clip": 8
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
    build_behavior_taxonomy,
    extract_frames,
    images_b64,
    load_rated_ids,
    normalize_drift,
    ollama_generate,
    ollama_model_available,
    parse_vlm_json,
    validate_local_ollama_url,
)


class VlmClipRating(BaseTool):
    name = "vlm_clip_rating"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "semantic_clip_rating"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Install Ollama (ollama.com) and pull the tested model: "
        "`ollama pull gemma4:12b` (~8GB VRAM, recommended).\n"
        "Smaller models (gemma3n:e4b ~3.5GB, qwen2.5vl:3b ~3GB) are "
        "untested; pass frame_scale 384 with them for faster inference."
    )
    agent_skills = ["vlm-footage-rating"]

    capabilities = [
        "behavior_classification",
        "camera_quality_assessment",
        "shot_composition_scoring",
        "product_visibility_detection",
        "temporal_segmentation",
        "highlight_extraction",
    ]
    supports = {
        "resume": True,
        "custom_focus_prompt": True,
        "custom_behavior_taxonomy": True,
        "local_only": True,
    }
    best_for = [
        "pre-indexing a footage folder with behavior and camera semantics",
        "finding clips where a product or subject is visible",
        "building a searchable semantic index before montage assembly",
    ]
    not_good_for = [
        "frame-accurate timestamps (use vlm_zoom_rating)",
        "ranking clips against each other (use vlm_comparative_rank)",
        "editing or composing video (use video_compose)",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_dir", "output_path"],
        "properties": {
            "input_dir": {
                "type": "string",
                "description": "Folder containing video clips to rate.",
            },
            "output_path": {
                "type": "string",
                "description": "JSONL output path. Re-running skips already-rated clips.",
            },
            "focus_prompt": {
                "type": "string",
                "default": "",
                "description": "What the campaign cares about, e.g. 'a black collar (the product)'.",
            },
            "behavior_extra": {
                "type": "string",
                "default": "",
                "description": "Extra comma-separated behavior labels to add to the taxonomy.",
            },
            "model": {
                "type": "string",
                "default": "gemma4:12b",
                "description": "Ollama model name with vision support. "
                               "Default gemma4:12b is the tested/recommended model.",
            },
            "ollama_url": {
                "type": "string",
                "default": "http://127.0.0.1:11434",
                "description": "Local Ollama endpoint. Only localhost/loopback URLs are accepted.",
            },
            "frames_per_clip": {
                "type": "integer",
                "default": 8,
                "minimum": 3,
                "maximum": 24,
            },
            "frame_scale": {
                "type": "integer",
                "default": 640,
                "minimum": 320,
                "maximum": 1280,
                "description": "Frame width for the VLM. Smaller (384-480) is faster "
                               "and uses less VRAM; best for 4b models.",
            },
            "temperature": {"type": "number", "default": 0.1},
            "num_predict": {"type": "integer", "default": 1500},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=3584, disk_mb=200,
        network_required=False,
    )
    side_effects = ["writes JSONL output", "writes temporary frame jpgs"]
    user_visible_verification = [
        "Open output_path and check a few records have behavior/camera/shot fields.",
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
        n = 0
        import glob

        in_dir = inputs.get("input_dir", "")
        if in_dir:
            n = len(
                glob.glob(str(Path(in_dir) / "*"))
            )
        return max(10.0, n * 8.0)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            import glob

            input_dir = Path(inputs["input_dir"])
            output_path = str(inputs["output_path"])
            if not input_dir.is_dir():
                return ToolResult(
                    success=False,
                    error=f"input_dir {input_dir} is not a directory",
                )

            model = inputs.get("model", "gemma4:12b")
            ollama_url = validate_local_ollama_url(
                inputs.get("ollama_url", "http://127.0.0.1:11434")
            )
            frames_per_clip = int(inputs.get("frames_per_clip", 8))
            frame_scale = int(inputs.get("frame_scale", 640))
            temperature = float(inputs.get("temperature", 0.1))
            num_predict = int(inputs.get("num_predict", 1500))
            focus = str(inputs.get("focus_prompt", "")).strip()
            behavior_extra = str(inputs.get("behavior_extra", "")).strip()

            videos = sorted(
                p for p in glob.glob(str(input_dir / "*"))
                if p.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))
            )
            if not videos:
                return ToolResult(
                    success=False,
                    error=f"No video files found in {input_dir}",
                )

            rated = load_rated_ids(output_path)
            prompt = _build_prompt(frames_per_clip, focus, behavior_extra)

            done = 0
            skipped = 0
            failed = 0
            tmp_dir = Path(inputs.get("tmp_dir") or tempfile.gettempdir()) / "vlm_clip_frames"
            for video in videos:
                clip = Path(video).name
                if clip in rated:
                    skipped += 1
                    continue
                try:
                    paths, frame_map, dur = extract_frames(
                        video, str(tmp_dir), n_frames=frames_per_clip,
                        scale=frame_scale,
                    )
                    if len(paths) < 3:
                        failed += 1
                        append_record(output_path, {
                            "clip": clip, "file": video, "error": "too_few_frames",
                        })
                        continue
                    images = images_b64(paths)
                    filled = (
                        prompt.replace("{n}", str(len(paths)))
                        .replace("{frame_map}", frame_map)
                        .replace("{focus}", focus)
                    )
                    raw = ollama_generate(
                        ollama_url, model, filled, images,
                        temperature=temperature, num_predict=num_predict,
                    )
                    record = parse_vlm_json(raw)
                    if record.get("error"):
                        record = {"error": record["error"]}
                    record["clip"] = clip
                    record["file"] = video
                    record["duration_s"] = round(dur, 2)
                    normalize_drift(
                        record,
                        {
                            "collar_visibility": ["product_visibility"],
                            "shot_purpose": ["purpose"],
                        },
                    )
                    append_record(output_path, record)
                    done += 1
                except Exception as exc:  # noqa: BLE001 - batch resilience
                    failed += 1
                    append_record(output_path, {
                        "clip": clip, "file": video, "error": str(exc)[:300],
                    })

            return ToolResult(
                success=True,
                data={
                    "rated": done,
                    "skipped_existing": skipped,
                    "failed": failed,
                    "total": len(videos),
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


def _build_prompt(frames_per_clip: int, focus: str, behavior_extra: str) -> str:
    """Build the coarse-rating prompt template.

    Uses brace-safe token replacement (NOT str.format) so the JSON schema
    braces in the prompt survive untouched. Tokens: {n}, {frame_map},
    {focus} are replaced per clip by the caller.
    """
    taxonomy = build_behavior_taxonomy(behavior_extra or None)
    focus_line = ""
    if focus:
        focus_line = (
            f"\nA key subject of interest for this project is: {focus}. "
            "Rate its visibility explicitly in the product field.\n"
        )
    template = """You are a professional film editor's assistant reviewing video footage.
You are given {n} consecutive frames from a single video clip, sampled evenly across its duration.
FRAME TIMESTAMPS (seconds into the clip):
{frame_map}{focus_line}

Analyze EVERYTHING about this clip and return ONLY valid JSON (no markdown) with this schema:
{
  "overall": {
    "behavior": "{taxonomy}",
    "behavior_confidence": 0.0,
    "energy": "calm"|"neutral"|"excited"|"hyper",
    "engagement": "focused"|"distracted"|"interacting"|"disengaged",
    "subject_in_frame": "yes"|"partial"|"no",
    "activity": "short phrase describing the main activity"
  },
  "camera": {
    "mount": "tripod"|"handheld"|"gimbal"|"unknown",
    "movement": "static"|"pan"|"tilt"|"track"|"handheld_shake",
    "stability_score": 0.0,
    "stability_note": "short phrase",
    "zoom": "none"|"push_in"|"pull_out",
    "exposure": "well_exposed"|"overexposed"|"underexposed"|"mixed"
  },
  "shot": {
    "type": "extreme_wide"|"wide"|"medium"|"medium_close"|"close_up"|"extreme_close_up",
    "subject": "primary subject of the shot",
    "subject_position": "left_third"|"center"|"right_third",
    "rule_of_thirds_score": 0.0,
    "lighting": "sunny"|"overcast"|"shade"|"golden_hour"|"harsh"|"indoor",
    "focus": "sharp"|"soft"|"missed",
    "background": "short description"
  },
  "product": {
    "subject_visible": true|false,
    "subject_visibility": "not_visible"|"partial"|"clear"|"featured",
    "is_subject_closeup": true|false,
    "subject_quality_score": 0.0,
    "details": "describe how visible and how well framed the subject of interest is"
  },
  "segments": [
    {
      "start_s": 0.0,
      "end_s": 0.0,
      "action": "what happens in this segment",
      "behavior": "{taxonomy}",
      "interest": 0.0,
      "note": "why interesting or not"
    }
  ],
  "highlights": [
    {
      "start_s": 0.0,
      "end_s": 0.0,
      "type": "action"|"expression"|"interaction"|"environment"|"subject",
      "why": "why this is a keeper",
      "quality_score": 0.0
    }
  ],
  "quality": {
    "overall_score": 0.0,
    "usable_for_edit": "yes"|"trim"|"no",
    "issues": ["list any: shake, motion blur, obstruction"]
  },
  "notes": "2-3 sentences describing what happens"
}

RULES:
- start_s/end_s must be real seconds into the clip, anchored to the FRAME TIMESTAMPS.
- interest/quality/stability/rule_of_thirds are 0.0-1.0 scores.
- If no notable highlight, return highlights: [].
- segments should cover the main beats (1-4 max).
- Be specific: describe what the subject and camera are actually doing.
"""
    return template.replace("{focus_line}", focus_line).replace(
        "{taxonomy}", taxonomy
    )
