"""Clip search: unified retrieval interface over a local clip corpus.

This is the tool the documentary-montage director calls at edit time.
It loads a corpus built by `corpus_builder` and exposes every
retrieval operation the agent needs through a single dispatch
interface.

Operations
----------
- **rank_for_slot**: embed a text description of a scene slot and
  return the top-k clips by fused visual+tag similarity. The agent's
  main building block — "for this slot in the montage, what clips
  match?"
- **find_similar_set**: given one seed clip, return N clips that share
  the seed's visual register but are diverse from each other (MMR).
  Used for "collection" shots — all the doorways, all the footsteps,
  all the keys-in-locks.
- **diversify**: given a pre-selected list of clip_ids, greedily keep
  the most mutually-dissimilar subset. Used at arrangement time to
  prevent visually-redundant adjacent cuts.
- **get**: look up one clip_id and return its full provenance dict.
- **stats**: summary counts (rows, per-source breakdown, mean motion).

All operations return JSON-serialisable dicts so the tool contract
stays clean across process boundaries. ClipRecords are converted via
`dataclasses.asdict`.

The corpus is loaded fresh on every call. This keeps the tool
stateless — the agent can call it from multiple stages without
worrying about caches drifting out of sync. For a 1000-row corpus
the load cost is <50 ms.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

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


class ClipSearch(BaseTool):
    name = "clip_search"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "clip_retrieval"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = [
        "python:numpy",
        "python:transformers",
        "python:torch",
    ]
    install_instructions = (
        "pip install numpy transformers torch\n"
        "Requires a corpus built by corpus_builder at <corpus_dir>."
    )
    agent_skills = []

    capabilities = [
        "text_to_clip_ranking",
        "visual_knn",
        "mmr_diversification",
        "provenance_lookup",
    ]
    supports = {
        "fused_visual_tag_scoring": True,
        "motion_filter": True,
        "kind_filter": True,
        "exclude_list": True,
    }
    best_for = [
        "picking clips for a specific slot in a montage",
        "finding collection-style sets from one seed clip",
        "de-duplicating a candidate list before edit arrangement",
    ]
    not_good_for = [
        "searching the internet (use corpus_builder to populate first)",
        "editing or composing video (use video_compose)",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation", "corpus_dir"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "rank_for_slot",
                    "find_similar_set",
                    "diversify",
                    "get",
                    "stats",
                ],
            },
            "corpus_dir": {
                "type": "string",
                "description": "Path to the corpus built by corpus_builder.",
            },
            # rank_for_slot
            "query_text": {
                "type": "string",
                "description": "Text description of the scene slot. "
                               "Embedded by CLIP for similarity ranking.",
            },
            "k": {"type": "integer", "default": 10, "minimum": 1},
            "tag_weight": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Blend between visual (1-w) and tag (w) channels.",
            },
            "motion_min": {
                "type": "number",
                "description": "Reject clips with motion_score below this. "
                               "Use ~1.5 to filter dead-still clips.",
            },
            "kind": {
                "type": "string",
                "enum": ["video", "image"],
                "description": "Filter to only one media type.",
            },
            "exclude_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Clip ids to skip (already used in this edit).",
            },
            # find_similar_set
            "seed_clip_id": {"type": "string"},
            "n": {"type": "integer", "default": 5, "minimum": 1},
            "diversity": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "candidate_pool": {"type": "integer", "default": 30},
            # diversify
            "candidate_ids": {"type": "array", "items": {"type": "string"}},
            # get
            "clip_id": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=1024, vram_mb=0, disk_mb=50, network_required=False
    )
    side_effects = []
    user_visible_verification = [
        "Inspect returned clip_ids and visit thumb_dir/frame_02.jpg "
        "to verify the retrieval matches the slot description.",
    ]

    def get_status(self) -> ToolStatus:
        try:
            import numpy  # noqa: F401
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            from lib.corpus import Corpus

            operation = inputs["operation"]
            corpus_dir = Path(inputs["corpus_dir"])

            corp = Corpus(corpus_dir)
            corp.load()

            if operation == "stats":
                payload = _op_stats(corp)
            elif operation == "rank_for_slot":
                payload = _op_rank_for_slot(corp, inputs)
            elif operation == "find_similar_set":
                payload = _op_find_similar_set(corp, inputs)
            elif operation == "diversify":
                payload = _op_diversify(corp, inputs)
            elif operation == "get":
                payload = _op_get(corp, inputs)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown operation: {operation!r}",
                )

            return ToolResult(
                success=True,
                data={
                    "operation": operation,
                    "corpus_dir": str(corpus_dir),
                    "corpus_size": len(corp),
                    **payload,
                },
                duration_seconds=round(time.time() - start, 3),
                cost_usd=0.0,
            )
        except Exception as e:
            import traceback
            return ToolResult(
                success=False,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}",
            )


# ----------------------------------------------------------------------
# Operations
# ----------------------------------------------------------------------


def _op_stats(corp) -> dict[str, Any]:
    """Summary counts and per-source breakdown.

    Useful as a sanity check before running expensive retrieval loops —
    "does the corpus I loaded actually have enough clips to satisfy the
    edit plan?"
    """
    import numpy as np

    if len(corp) == 0:
        return {
            "rows": 0,
            "per_source": {},
            "per_kind": {},
            "mean_motion_score": 0.0,
            "mean_duration": 0.0,
        }

    per_source: dict[str, int] = {}
    per_kind: dict[str, int] = {}
    motion_scores: list[float] = []
    durations: list[float] = []
    for rec in corp.records:
        per_source[rec.source] = per_source.get(rec.source, 0) + 1
        per_kind[rec.kind] = per_kind.get(rec.kind, 0) + 1
        motion_scores.append(rec.motion_score)
        durations.append(rec.duration)

    return {
        "rows": len(corp),
        "per_source": per_source,
        "per_kind": per_kind,
        "mean_motion_score": float(np.mean(motion_scores)) if motion_scores else 0.0,
        "mean_duration": float(np.mean(durations)) if durations else 0.0,
    }


def _op_rank_for_slot(corp, inputs: dict[str, Any]) -> dict[str, Any]:
    """Embed `query_text` and return top-k clips by fused similarity.

    This is the agent's main retrieval move. The returned list is
    ordered best-first and every entry carries a score so the agent
    can decide whether the match is strong enough (>= 0.25 is a rough
    "acceptable" threshold for CLIP ViT-B/32).
    """
    from lib.clip_embedder import embed_texts

    query_text = inputs.get("query_text", "").strip()
    if not query_text:
        raise ValueError("rank_for_slot requires 'query_text'")

    q_vec = embed_texts([query_text])[0]

    results = corp.rank_by_text(
        query_embedding=q_vec,
        k=int(inputs.get("k", 10)),
        tag_weight=float(inputs.get("tag_weight", 0.3)),
        motion_min=inputs.get("motion_min"),
        kind=inputs.get("kind"),
        exclude_ids=inputs.get("exclude_ids") or [],
    )
    return {
        "query_text": query_text,
        "results": [
            {"score": score, "record": asdict(rec)}
            for rec, score in results
        ],
    }


def _op_find_similar_set(corp, inputs: dict[str, Any]) -> dict[str, Any]:
    """MMR-based similar-set retrieval from one seed clip."""
    seed = inputs.get("seed_clip_id")
    if not seed:
        raise ValueError("find_similar_set requires 'seed_clip_id'")

    results = corp.find_similar_set(
        seed_clip_id=seed,
        n=int(inputs.get("n", 5)),
        diversity=float(inputs.get("diversity", 0.3)),
        candidate_pool=int(inputs.get("candidate_pool", 30)),
        exclude_ids=inputs.get("exclude_ids") or [],
    )
    return {
        "seed_clip_id": seed,
        "results": [
            {"score": score, "record": asdict(rec)}
            for rec, score in results
        ],
    }


def _op_diversify(corp, inputs: dict[str, Any]) -> dict[str, Any]:
    """Pick the most mutually-dissimilar subset of a candidate list."""
    candidate_ids = inputs.get("candidate_ids") or []
    if not candidate_ids:
        raise ValueError("diversify requires 'candidate_ids'")

    kept = corp.diversify(
        candidate_ids=list(candidate_ids),
        n=int(inputs.get("n", 5)),
        diversity=float(inputs.get("diversity", 0.5)),
    )
    return {
        "input_count": len(candidate_ids),
        "kept_count": len(kept),
        "kept_ids": kept,
    }


def _op_get(corp, inputs: dict[str, Any]) -> dict[str, Any]:
    """Look up one clip_id and return its full record."""
    clip_id = inputs.get("clip_id")
    if not clip_id:
        raise ValueError("get requires 'clip_id'")

    rec = corp.get(clip_id)
    if rec is None:
        return {"clip_id": clip_id, "found": False, "record": None}
    return {"clip_id": clip_id, "found": True, "record": asdict(rec)}
