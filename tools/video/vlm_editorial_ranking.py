"""VLM editorial ranking: composite scores, leaderboards, and match cuts.

Consumes the coarse ratings (``vlm_clip_rating``) plus optional zoom data
(``vlm_zoom_rating``) and produces a structured editorial view: composite
scores blending stability, quality, subject visibility, composition, and
vibe; per-purpose leaderboards; and match-cut chains from subject facing
direction.

The composite weighting is configurable so a campaign can bias toward
product shots, stability, or energy.

Usage (as a tool)::

    {
      "ratings_path": "/path/to/clip_tags.jsonl",
      "zooms_path": "/path/to/clip_zooms.jsonl",   // optional
      "output_path": "/path/to/editorial_rankings.json",
      "weights": {"stability": 0.25, "quality": 0.25, "subject": 0.25,
                  "composition": 0.15, "vibe": 0.10}
    }
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

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
from tools.video.vlm_rating_common import safe_float


DEFAULT_WEIGHTS = {
    "stability": 0.25,
    "quality": 0.25,
    "subject": 0.25,
    "composition": 0.15,
    "vibe": 0.10,
}

VIBE_SCORE = {
    "calm": 0.7, "candid": 0.8, "playful": 0.9, "energetic": 1.0,
    "tender": 0.85, "tense": 0.5, "neutral": 0.6, "excited": 0.95,
    "hyper": 0.9,
}


class VlmEditorialRanking(BaseTool):
    name = "vlm_editorial_ranking"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "editorial_ranking"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies (pure Python)."
    agent_skills = ["vlm-footage-rating"]

    capabilities = [
        "composite_editorial_scoring",
        "per_purpose_leaderboards",
        "best_moment_extraction",
        "match_cut_chains",
    ]
    supports = {"configurable_weights": True, "local_only": True}
    best_for = [
        "deciding which clips go where in a montage",
        "surfacing the best subject/product moments",
        "building directional continuity for match cuts",
    ]
    not_good_for = [
        "semantic indexing (use vlm_clip_rating)",
        "frame-accurate timestamps (use vlm_zoom_rating)",
        "relative clip comparison with reasoning (use vlm_comparative_rank)",
    ]

    input_schema = {
        "type": "object",
        "required": ["ratings_path", "output_path"],
        "properties": {
            "ratings_path": {"type": "string"},
            "zooms_path": {"type": "string", "default": ""},
            "output_path": {"type": "string"},
            "weights": {
                "type": "object",
                "description": "Composite score weights (must sum to 1.0).",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=50,
        network_required=False,
    )
    side_effects = ["writes JSON output"]
    user_visible_verification = [
        "Open output_path and check leaderboards + match_cuts exist.",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 2.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            ratings_path = inputs["ratings_path"]
            output_path = str(inputs["output_path"])
            zooms_path = str(inputs.get("zooms_path", "") or "")
            if not Path(ratings_path).exists():
                return ToolResult(
                    success=False,
                    error=f"ratings_path {ratings_path} does not exist",
                )

            weights = {**DEFAULT_WEIGHTS, **(inputs.get("weights") or {})}
            total = sum(weights.values())
            if abs(total - 1.0) > 0.001:
                return ToolResult(
                    success=False,
                    error=f"Weights must sum to 1.0 (got {total:.3f})",
                )

            ratings = _load_jsonl(ratings_path)
            zooms = _load_jsonl(zooms_path) if zooms_path and Path(zooms_path).exists() else {}
            zoom_lookup = {z["clip"]: z for z in zooms.values() if isinstance(z, dict)}

            rows = [_rank_row(r, zoom_lookup.get(r["clip"]), weights) for r in ratings.values()]
            rows.sort(key=lambda r: r["composite"], reverse=True)

            leaderboards = {
                "overall": _rank(rows, lambda r: r["composite"]),
                "subject_hero": _rank(
                    rows,
                    lambda r: r["subject_quality"] * 0.7 + r["composite"] * 0.3,
                ),
                "stable": _rank(
                    rows,
                    lambda r: r["stability"] * 0.5 + r["composite"] * 0.3,
                ),
                "energy": _rank(
                    rows,
                    lambda r: (0.6 if r["energy"] in ("excited", "hyper") else 0)
                    + r["composite"] * 0.4,
                ),
                "subject_closeup": _rank(
                    rows,
                    lambda r: (1.0 if r["subject_visibility"] in ("featured", "clear") else 0)
                    + r["subject_quality"],
                ),
            }

            match_cuts = _match_cuts(zooms)

            out = {
                "n_clips": len(rows),
                "weights": weights,
                "leaderboards": {
                    k: [r["summary"] for r in v] for k, v in leaderboards.items()
                },
                "match_cuts": match_cuts,
                "all_rows": rows,
            }
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as fh:
                json.dump(out, fh, indent=2)

            return ToolResult(
                success=True,
                data={
                    "n_clips": len(rows),
                    "leaderboards": list(leaderboards),
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


def _load_jsonl(path: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    p = Path(path)
    if not p.exists():
        return out
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict) or rec.get("error"):
                continue
            key = rec.get("clip") or rec.get("id")
            if key:
                out[key] = rec
    return out


def _rank(
    rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], float]
) -> list[dict[str, Any]]:
    return sorted(rows, key=key_fn, reverse=True)


def _rank_row(
    rec: dict[str, Any], zoom: dict[str, Any] | None, weights: dict[str, float]
) -> dict[str, Any]:
    overall = rec.get("overall", {})
    cam = rec.get("camera", {})
    shot = rec.get("shot", {})
    prod = rec.get("product", {})
    qual = rec.get("quality", {})

    stability = safe_float(cam.get("stability_score"), 0.8)
    quality = safe_float(qual.get("overall_score"), 0.7)
    subject_quality = safe_float(prod.get("subject_quality_score"), 0.0)
    composition = safe_float(shot.get("rule_of_thirds_score"), 0.5)
    energy = overall.get("energy", "neutral")
    vibe = VIBE_SCORE.get(energy, 0.6)

    composite = (
        weights["stability"] * stability
        + weights["quality"] * quality
        + weights["subject"] * subject_quality
        + weights["composition"] * composition
        + weights["vibe"] * vibe
    )

    best_moment = _best_moment(zoom)

    return {
        "clip": rec.get("clip"),
        "file": rec.get("file") or rec.get("path"),
        "behavior": overall.get("behavior"),
        "energy": energy,
        "stability": round(stability, 2),
        "composition": round(composition, 2),
        "subject_quality": round(subject_quality, 2),
        "subject_visibility": prod.get("subject_visibility")
        or prod.get("collar_visibility"),
        "shot_type": shot.get("type"),
        "shot_purpose": shot.get("shot_purpose") or shot.get("purpose"),
        "quality": round(quality, 2),
        "duration_s": rec.get("duration_s"),
        "composite": round(composite, 3),
        "best_moment": best_moment,
        "summary": {
            "clip": rec.get("clip"),
            "composite": round(composite, 3),
            "behavior": overall.get("behavior"),
            "energy": energy,
            "stability": round(stability, 2),
            "subject_quality": round(subject_quality, 2),
            "subject_visibility": prod.get("subject_visibility")
            or prod.get("collar_visibility"),
            "shot_type": shot.get("type"),
            "duration_s": rec.get("duration_s"),
        },
    }


def _best_moment(zoom: dict[str, Any] | None) -> list[Any] | None:
    """Extract the highest-quality zoom sub-beat with absolute timestamp."""
    if not zoom:
        return None
    best: list[Any] | None = None
    for z in zoom.get("zooms", []) or []:
        if not isinstance(z, dict):
            continue
        ws = safe_float(z.get("window_start_s"), 0.0)
        for b in z.get("sub_beats", []) or []:
            if not isinstance(b, dict):
                continue
            q = safe_float(b.get("quality_score"), 0.0)
            if q < 0.8:
                continue
            abs_start = ws + safe_float(b.get("start_s"), 0.0)
            if best is None or q > best[0]:
                best = [
                    q,
                    round(abs_start, 2),
                    b.get("deep_dive") or b.get("action") or "",
                    b.get("subject_visibility") or b.get("collar_visibility"),
                    b.get("subject_facing"),
                    b.get("vibe"),
                ]
    return best


def _match_cuts(zooms: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build directional continuity chains from zoom sub-beats."""
    facing_seq: list[dict[str, Any]] = []
    for clip, z in zooms.items():
        for zz in z.get("zooms", []) or []:
            if not isinstance(zz, dict):
                continue
            ws = safe_float(zz.get("window_start_s"), 0.0)
            for b in zz.get("sub_beats", []) or []:
                if not isinstance(b, dict):
                    continue
                facing = b.get("subject_facing")
                if facing not in ("left", "right"):
                    continue
                facing_seq.append({
                    "clip": clip,
                    "t": round(ws + safe_float(b.get("start_s"), 0.0), 1),
                    "facing": facing,
                    "q": safe_float(b.get("quality_score"), 0.0),
                    "action": b.get("action", ""),
                })
    chains = []
    for direction in ("left", "right"):
        chain = sorted(
            [fs for fs in facing_seq if fs["facing"] == direction],
            key=lambda x: -x["q"],
        )[:10]
        if chain:
            chains.append({"direction": direction, "chain": chain})
    return chains
