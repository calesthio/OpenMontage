"""VLM comparative rank: relative clip comparison with editorial reasoning.

Absolute per-clip scores (from ``vlm_clip_rating``) are not calibrated:
a 0.9 means nothing until the model has seen what 0.6 and 0.95 look like.
This tool shows several clips together in one VLM context (4 clips x 5
frames, labeled A/B/C/D), asks for a relative ranking, calibrated scores,
and *reasons* for best/worst picks. The reasons are the deliverable an
editor or downstream agent can act on.

This is an optional second-opinion pass, not part of the core pipeline:
run it when two clips score close and you want the model to argue about
which is better for a specific purpose.

Usage (as a tool)::

    {
      "rankings_path": "/path/to/editorial_rankings.json",
      "output_path": "/path/to/comparative_rankings.jsonl",
      "purpose": "subject_hero",       // leaderboard key to sample from
      "batch_size": 4,
      "model": "gemma4:12b",
      "ollama_url": "http://127.0.0.1:11434"
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
    extract_frames,
    images_b64,
    ollama_generate,
    ollama_model_available,
    parse_vlm_json,
    validate_local_ollama_url,
)


PURPOSES = {
    "subject_hero": (
        "footage that showcases the subject of interest (product, person, "
        "or animal): visibility, close-ups, quality, framing that sells it"
    ),
    "lifestyle": (
        "natural lifestyle footage: authentic behavior, engagement, "
        "usability in a narrative"
    ),
    "action_energy": (
        "high-energy action: movement, excitement, dynamic shots for "
        "energetic montage segments"
    ),
    "establishing": (
        "wide establishing shots: environment, setting, composition for "
        "opening or closing scenes"
    ),
    "stability": (
        "the steadiest, most usable footage: minimal shake, clean framing, "
        "consistent exposure"
    ),
}


class VlmComparativeRank(BaseTool):
    name = "vlm_comparative_rank"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "comparative_clip_ranking"
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
        "relative_ranking",
        "calibrated_scores",
        "editorial_reasoning",
        "purpose_aware_comparison",
    ]
    supports = {"local_only": True}
    best_for = [
        "tie-breaking clips that score close on absolute ratings",
        "getting a second opinion with reasoning before committing a cut",
        "comparing candidates for a specific editorial purpose",
    ]
    not_good_for = [
        "bulk semantic indexing (use vlm_clip_rating)",
        "frame-accurate timestamps (use vlm_zoom_rating)",
        "scoring every clip (this is for shortlists)",
    ]

    input_schema = {
        "type": "object",
        "required": ["rankings_path", "output_path"],
        "properties": {
            "rankings_path": {
                "type": "string",
                "description": "JSON from vlm_editorial_ranking.",
            },
            "output_path": {"type": "string"},
            "purpose": {
                "type": "string",
                "enum": list(PURPOSES),
                "default": "subject_hero",
            },
            "batch_size": {"type": "integer", "default": 4, "minimum": 2, "maximum": 8},
            "max_candidates": {"type": "integer", "default": 16},
            "model": {"type": "string", "default": "gemma4:12b"},
            "ollama_url": {
                "type": "string",
                "default": "http://127.0.0.1:11434",
                "description": "Local Ollama endpoint. Only localhost/loopback URLs are accepted.",
            },
            "frames_per_clip": {"type": "integer", "default": 5},
            "frame_scale": {
                "type": "integer",
                "default": 480,
                "minimum": 320,
                "maximum": 1280,
                "description": "Frame width for the VLM. Smaller (384) is faster "
                               "and uses less VRAM; best for 4b models.",
            },
            "temperature": {"type": "number", "default": 0.1},
            "num_predict": {"type": "integer", "default": 800},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=3584, disk_mb=200,
        network_required=False,
    )
    side_effects = ["writes JSONL output", "writes temporary frame jpgs"]
    user_visible_verification = [
        "Open output_path and check ranking + best_reason fields.",
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
        n_batches = max(
            1, (int(inputs.get("max_candidates", 16)) // int(inputs.get("batch_size", 4)))
        )
        return n_batches * 40.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            rankings_path = inputs["rankings_path"]
            output_path = str(inputs["output_path"])
            if not Path(rankings_path).exists():
                return ToolResult(
                    success=False,
                    error=f"rankings_path {rankings_path} does not exist",
                )

            purpose = inputs.get("purpose", "subject_hero")
            batch_size = int(inputs.get("batch_size", 4))
            max_candidates = int(inputs.get("max_candidates", 16))
            model = inputs.get("model", "gemma4:12b")
            ollama_url = validate_local_ollama_url(
                inputs.get("ollama_url", "http://127.0.0.1:11434")
            )
            frames_per_clip = int(inputs.get("frames_per_clip", 5))
            frame_scale = int(inputs.get("frame_scale", 480))
            temperature = float(inputs.get("temperature", 0.1))
            num_predict = int(inputs.get("num_predict", 800))
            tmp_dir = Path(inputs.get("tmp_dir") or tempfile.gettempdir()) / "vlm_cmp_frames"

            candidates = _candidate_paths(rankings_path, purpose, max_candidates)
            if not candidates:
                return ToolResult(
                    success=False,
                    error=(
                        f"No candidate clips found for purpose {purpose!r}. "
                        f"Check rankings_path and that leaderboards exist."
                    ),
                )

            batches = [
                candidates[i : i + batch_size]
                for i in range(0, len(candidates), batch_size)
            ]
            prompt = _build_prompt(frames_per_clip, purpose)
            results = []
            for batch in batches:
                labels, images, clip_map = _load_batch(
                    batch, tmp_dir, frames_per_clip, frame_scale
                )
                if not clip_map:
                    continue
                used = list(clip_map)
                filled = prompt.format(
                    n=len(used),
                    f=frames_per_clip,
                    labels=", ".join(labels),
                    clip_map=", ".join(
                        f"{l} = {clip_map[l]}" for l in used
                    ),
                    purpose=PURPOSES.get(purpose, purpose),
                )
                raw = ollama_generate(
                    ollama_url, model, filled, images,
                    temperature=temperature, num_predict=num_predict,
                )
                result = parse_vlm_json(raw)
                result["_clips"] = clip_map
                result["_purpose"] = purpose
                results.append(result)
                append_record(output_path, result)

            return ToolResult(
                success=True,
                data={
                    "batches": len(results),
                    "purpose": purpose,
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


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _candidate_paths(
    rankings_path: str, purpose: str, max_candidates: int
) -> list[str]:
    with open(rankings_path) as fh:
        data = json.load(fh)
    leaderboards = data.get("leaderboards", {})
    board = leaderboards.get(purpose) or leaderboards.get("overall", [])
    paths: list[str] = []
    for entry in board:
        clip = entry.get("clip")
        if not clip:
            continue
        # Recover the file path from all_rows if present.
        file_path = None
        for row in data.get("all_rows", []):
            if row.get("clip") == clip:
                file_path = row.get("file")
                break
        if file_path and Path(file_path).exists():
            paths.append(file_path)
        if len(paths) >= max_candidates:
            break
    return paths


def _load_batch(
    clips: list[str],
    tmp_dir: Path,
    frames_per_clip: int,
    frame_scale: int = 480,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Extract frames for a batch; returns (labels, images, clip_map)."""
    labels: list[str] = []
    images: list[str] = []
    clip_map: dict[str, str] = {}
    for i, video in enumerate(clips):
        letter = "ABCDEFGH"[i]
        try:
            paths, _map, _dur = extract_frames(
                video, str(tmp_dir / letter), n_frames=frames_per_clip,
                scale=frame_scale,
            )
        except Exception:  # noqa: BLE001
            continue
        if not paths:
            continue
        clip_map[letter] = Path(video).name
        for j, p in enumerate(paths):
            images.extend(images_b64([p]))
            labels.append(f"{letter}{j + 1}")
    return labels, images, clip_map


def _build_prompt(frames_per_clip: int, purpose: str) -> str:
    return """You are a professional film editor choosing shots for a video project.
You are shown {n} candidate clips, each as {f} frames. Frame labels: {labels}.
Clips: {clip_map}.

The comparison purpose is: {purpose}

Rank the clips for this purpose and explain your reasoning. Return ONLY valid JSON (no markdown):
{{
  "ranking": ["A", "B", "C", "D"],
  "scores": {{"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}},
  "best_clip": "A",
  "best_reason": "why this clip wins for this purpose; be specific about framing, subject, behavior, composition",
  "worst_clip": "C",
  "worst_reason": "why this clip loses",
  "notes": "one comparison insight"
}}

RULES:
- scores 0.0-1.0, calibrated RELATIVE to the other clips in this batch.
- be specific: reference actual visual details (subject visibility, framing, behavior, stability).
- ranking must contain exactly the clip labels used.
"""
