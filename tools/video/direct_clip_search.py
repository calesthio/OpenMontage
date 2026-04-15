"""Direct clip search: lightweight provider-agnostic stock footage acquisition.

This tool replaces the heavy corpus_builder → clip_search pipeline when
you already know what you want and just need clips downloaded fast. It
uses the same StockSource adapter protocol (Pexels, Archive.org, NASA,
Wikimedia, Unsplash, ...) but skips CLIP embeddings, motion scoring,
index.jsonl, and .npy files entirely.

When to use this instead of corpus_builder
------------------------------------------
- You have a shot list and know the queries for each slot.
- You want clips downloaded in minutes, not tens of minutes.
- You plan to inspect thumbnails yourself (or via a sub-agent) rather
  than relying on CLIP similarity ranking.
- You are doing act-by-act production and can reuse clips across acts
  by pointing at previously downloaded directories.

When to use corpus_builder instead
----------------------------------
- You need CLIP-based semantic ranking (clip_search.rank_for_slot).
- You have 50+ slots and want automated diversification.
- The visual match between query text and actual footage matters more
  than speed.

What it does per query
----------------------
1. Fan out across all available (or specified) StockSource adapters.
2. Download up to `clips_per_query` clips per query.
3. Extract one thumbnail per clip via ffmpeg (for visual inspection).
4. Return full metadata: paths, durations, sources, thumbnails.

No CLIP model. No embeddings. No corpus index. Just files on disk.
"""
from __future__ import annotations

import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class DirectClipSearch(BaseTool):
    name = "direct_clip_search"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "clip_acquisition"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.HYBRID  # local disk + network APIs

    dependencies = [
        "python:requests",
    ]
    install_instructions = (
        "At least one stock source must be configured:\n"
        "  PEXELS_API_KEY for Pexels (free at https://www.pexels.com/api/)\n"
        "  UNSPLASH_ACCESS_KEY for Unsplash (see https://unsplash.com/documentation)\n"
        "  archive.org, nasa, and wikimedia work without API keys"
    )
    agent_skills = []

    capabilities = [
        "multi_source_search",
        "clip_download",
        "thumbnail_extraction",
    ]
    supports = {
        "multi_source": True,
        "video_and_image": True,
        "provider_agnostic": True,
        "cross_act_reuse": True,
    }
    best_for = [
        "act-by-act documentary production with manual clip selection",
        "fast B-roll acquisition when you know what you need",
        "downloading clips from multiple providers in one call",
        "building clip libraries without CLIP embedding overhead",
    ]
    not_good_for = [
        "semantic similarity ranking (use corpus_builder + clip_search)",
        "automated slot filling without human review",
    ]
    fallback_tools = ["corpus_builder", "pexels_video"]

    input_schema = {
        "type": "object",
        "required": ["output_dir", "queries"],
        "properties": {
            "output_dir": {
                "type": "string",
                "description": (
                    "Directory where clips and thumbnails are saved. "
                    "e.g. projects/foo/assets/video/raw_act2"
                ),
            },
            "queries": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term for stock APIs",
                        },
                        "slot_id": {
                            "type": "string",
                            "description": (
                                "Optional slot reference (e.g. 'slot_03'). "
                                "Used to organize output and track provenance."
                            ),
                        },
                        "kind": {
                            "type": "string",
                            "enum": ["video", "image", "any"],
                            "default": "video",
                        },
                    },
                },
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Source adapter names to search (e.g. ['pexels','archive_org']). "
                    "Defaults to all available sources."
                ),
            },
            "clips_per_query": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "maximum": 20,
                "description": (
                    "How many clips to download per query (across all sources). "
                    "Lower = faster. 2-3 is enough for manual selection."
                ),
            },
            "filters": {
                "type": "object",
                "properties": {
                    "min_duration": {"type": "number"},
                    "max_duration": {"type": "number"},
                    "orientation": {
                        "type": "string",
                        "enum": ["landscape", "portrait", "square"],
                    },
                    "min_width": {"type": "integer"},
                },
            },
            "extract_thumbnails": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Extract a mid-frame thumbnail from each video for visual "
                    "inspection. Uses ffmpeg, not CLIP."
                ),
            },
            "skip_existing": {
                "type": "boolean",
                "default": True,
                "description": "Skip download if a file with the same clip_id already exists.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=2000, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "rate_limit"])
    side_effects = [
        "downloads clips to <output_dir>/clips/",
        "extracts thumbnails to <output_dir>/thumbnails/",
        "calls external stock APIs",
    ]
    user_visible_verification = [
        "Browse <output_dir>/thumbnails/ to visually verify clip matches",
        "Play clips from <output_dir>/clips/ to check quality",
    ]

    def get_status(self) -> ToolStatus:
        try:
            from tools.video.stock_sources import available_sources
        except Exception:
            return ToolStatus.UNAVAILABLE
        if len(available_sources()) == 0:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        try:
            from tools.video.stock_sources import source_catalog, source_summary
            info["source_provider_menu"] = source_catalog()
            info["source_provider_summary"] = source_summary()
        except Exception:
            info["source_provider_menu"] = []
            info["source_provider_summary"] = {
                "configured": 0,
                "total": 0,
                "available_source_names": [],
                "unavailable_source_names": [],
            }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # all sources are free-tier

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            from tools.video.stock_sources import (
                SearchFilters,
                all_sources,
                available_sources,
                get_source,
                source_summary,
            )

            output_dir = Path(inputs["output_dir"])
            queries: list[dict] = list(inputs["queries"])
            source_names: Optional[list[str]] = inputs.get("sources")
            filters_in: dict = inputs.get("filters") or {}
            clips_per_query = int(inputs.get("clips_per_query", 3))
            extract_thumbs = bool(inputs.get("extract_thumbnails", True))
            skip_existing = bool(inputs.get("skip_existing", True))

            clips_dir = output_dir / "clips"
            thumbs_dir = output_dir / "thumbnails"
            clips_dir.mkdir(parents=True, exist_ok=True)
            if extract_thumbs:
                thumbs_dir.mkdir(parents=True, exist_ok=True)

            # --- Resolve sources ---
            if source_names:
                sources = []
                unavailable: list[str] = []
                known = {src.name: src for src in all_sources()}
                for name in source_names:
                    s = known.get(name)
                    if s is None:
                        try:
                            s = get_source(name)
                        except KeyError:
                            return ToolResult(
                                success=False,
                                error=f"Unknown stock source: {name!r}. "
                                      f"Available: {[src.name for src in all_sources()]}",
                            )
                    if s.is_available():
                        sources.append(s)
                    else:
                        unavailable.append(name)
                if unavailable:
                    summary = source_summary()
                    return ToolResult(
                        success=False,
                        error=(
                            f"Requested sources unavailable: {', '.join(unavailable)}. "
                            f"Available: {', '.join(summary['available_source_names']) or 'none'}."
                        ),
                    )
            else:
                sources = available_sources()

            if not sources:
                return ToolResult(
                    success=False,
                    error="No stock sources available. " + self.install_instructions,
                )

            # --- Search and download ---
            downloaded: list[dict] = []
            errors: list[dict] = []
            skipped = 0
            per_source_counts: dict[str, int] = {s.name: 0 for s in sources}

            for q_spec in queries:
                query = q_spec["query"]
                slot_id = q_spec.get("slot_id", "")
                kind = q_spec.get("kind", "video")
                collected_for_query = 0

                filters = SearchFilters(
                    kind=kind,
                    per_page=max(clips_per_query * 2, 10),  # fetch extra for filtering
                    min_duration=filters_in.get("min_duration"),
                    max_duration=filters_in.get("max_duration"),
                    orientation=filters_in.get("orientation"),
                    min_width=filters_in.get("min_width"),
                )

                for src in sources:
                    if collected_for_query >= clips_per_query:
                        break

                    try:
                        candidates = src.search(query, filters)
                    except Exception as e:
                        errors.append({
                            "phase": "search",
                            "source": src.name,
                            "query": query,
                            "error": f"{type(e).__name__}: {e}",
                        })
                        continue

                    for cand in candidates:
                        if collected_for_query >= clips_per_query:
                            break

                        clip_id = cand.clip_id
                        ext = _guess_ext(cand)
                        clip_path = clips_dir / f"{clip_id}{ext}"

                        # Skip if already downloaded
                        if skip_existing and clip_path.exists() and clip_path.stat().st_size > 1024:
                            skipped += 1
                            # Still record it in results so the agent knows it's there
                            thumb_path = thumbs_dir / f"{clip_id}.jpg"
                            downloaded.append({
                                "clip_id": clip_id,
                                "source": cand.source,
                                "source_id": cand.source_id,
                                "source_url": cand.source_url,
                                "query": query,
                                "slot_id": slot_id,
                                "kind": cand.kind,
                                "path": str(clip_path),
                                "thumbnail": str(thumb_path) if thumb_path.exists() else "",
                                "duration": cand.duration,
                                "width": cand.width,
                                "height": cand.height,
                                "creator": cand.creator,
                                "license": cand.license,
                                "source_tags": cand.source_tags,
                                "skipped_existing": True,
                            })
                            collected_for_query += 1
                            continue

                        # Download
                        try:
                            src.download(cand, clip_path)
                        except Exception as e:
                            errors.append({
                                "phase": "download",
                                "clip_id": clip_id,
                                "source": src.name,
                                "error": f"{type(e).__name__}: {e}",
                            })
                            continue

                        if not clip_path.exists() or clip_path.stat().st_size < 1024:
                            errors.append({
                                "phase": "download",
                                "clip_id": clip_id,
                                "source": src.name,
                                "error": "Download produced empty or tiny file",
                            })
                            try:
                                if clip_path.exists():
                                    clip_path.unlink()
                            except OSError:
                                pass
                            continue

                        # Extract thumbnail
                        thumb_path_str = ""
                        if extract_thumbs and cand.kind == "video":
                            thumb_path = thumbs_dir / f"{clip_id}.jpg"
                            try:
                                _extract_mid_thumbnail(clip_path, thumb_path)
                                if thumb_path.exists():
                                    thumb_path_str = str(thumb_path)
                            except Exception:
                                pass  # thumbnail failure is non-fatal

                        per_source_counts[src.name] = per_source_counts.get(src.name, 0) + 1
                        collected_for_query += 1

                        downloaded.append({
                            "clip_id": clip_id,
                            "source": cand.source,
                            "source_id": cand.source_id,
                            "source_url": cand.source_url,
                            "query": query,
                            "slot_id": slot_id,
                            "kind": cand.kind,
                            "path": str(clip_path),
                            "thumbnail": thumb_path_str,
                            "duration": cand.duration,
                            "width": cand.width,
                            "height": cand.height,
                            "creator": cand.creator,
                            "license": cand.license,
                            "source_tags": cand.source_tags,
                            "skipped_existing": False,
                        })

            elapsed = time.time() - start

            return ToolResult(
                success=True,
                data={
                    "output_dir": str(output_dir),
                    "clips_downloaded": len([d for d in downloaded if not d.get("skipped_existing")]),
                    "clips_reused": skipped,
                    "total_clips": len(downloaded),
                    "per_source_counts": per_source_counts,
                    "queries_run": len(queries),
                    "resolved_sources": [s.name for s in sources],
                    "clips": downloaded,
                    "errors": errors[:25],
                },
                cost_usd=0.0,
                duration_seconds=round(elapsed, 2),
            )

        except Exception as e:
            import traceback
            return ToolResult(
                success=False,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}",
            )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _guess_ext(cand) -> str:
    """Extract a sensible file extension from a candidate's URL."""
    known = {".mp4", ".mov", ".mkv", ".webm", ".ogv", ".m4v",
             ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    path = urllib.parse.urlparse(cand.download_url).path
    ext = Path(path).suffix.lower()
    if ext in known:
        return ".jpg" if ext == ".jpeg" else ext
    return ".mp4" if cand.kind == "video" else ".jpg"


def _extract_mid_thumbnail(video_path: Path, thumb_path: Path) -> None:
    """Extract a single frame from the middle of the video via ffmpeg.

    This is deliberately simple — one frame, no CLIP, no motion score.
    The agent or user inspects the thumbnail visually to decide if the
    clip is a good match.
    """
    thumb_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe duration first
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            probe_cmd, capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip() or "0")
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        duration = 0

    # Seek to the middle (or 2 seconds in if duration unknown)
    seek_time = max(0.5, duration / 2) if duration > 1 else 2.0

    extract_cmd = [
        "ffmpeg", "-y",
        "-ss", str(round(seek_time, 2)),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "3",
        str(thumb_path),
    ]
    subprocess.run(
        extract_cmd, capture_output=True, timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
