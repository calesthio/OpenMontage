"""Corpus builder: fan out across stock sources, download, thumb, embed, index.

This is the tool the agent calls to populate a local clip corpus for
the documentary-montage pipeline. It is deliberately the ONLY place
where adapters, embedding, and the `Corpus` class meet — everything
downstream (retrieval, selection, edit planning) reads from the corpus
on disk and never touches sources directly.

What it does, per query, per source, per candidate
---------------------------------------------------
1. Call `source.search(query, filters)` to get a flat list of
   `Candidate`s normalised across sources.
2. Skip candidates whose `clip_id` is already in the corpus (unless
   `skip_existing=false`).
3. Download the file to ``<corpus_dir>/clips/<clip_id>.<ext>``.
4. For videos: extract N evenly-spaced frames to
   ``<corpus_dir>/thumbnails/<clip_id>/frame_NN.jpg``, probe real
   dimensions and duration, and compute a cheap motion score
   (mean-abs-diff between first and middle frame).
5. For images: copy the image as ``frame_00.jpg`` in the same thumb
   directory so the embedder has a consistent input.
6. Run CLIP on the thumbnails, pool frames to one 512-d vector for the
   visual channel. Run CLIP on `source_tags` (falling back to the
   query itself) for the tag channel.
7. Materialise a `ClipRecord` with every provenance field and append
   it to the corpus via `Corpus.add()`.
8. After ALL candidates are processed, call `Corpus.save()` once. Per-
   add saves would burn disk I/O for large runs.

Caps
----
- `max_new_clips` halts the whole run once that many new rows have
  been added. The remaining candidates in the current loop iteration
  are discarded.
- Per-source search errors and per-candidate processing errors are
  caught and collected into `errors` in the return payload. One flaky
  URL or one broken codec must not poison the whole run.

Idempotence
-----------
Re-running with the same inputs is safe. `skip_existing=True` (default)
causes the tool to short-circuit on any `clip_id` already in the
corpus JSONL. Crash-recovery is handled by `Corpus.load()`, which
truncates the in-memory state to the shorter of the JSONL and the
`.npy` lengths.

Agent surface
-------------
Input schema keeps the agent's decisions at the top: WHAT to search
for (`queries`), WHERE to search (`sources`), WHAT to filter
(`filters`), and HOW MUCH (`max_new_clips`). Everything else has
sensible defaults.
"""
from __future__ import annotations

import time
import urllib.parse
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


class CorpusBuilder(BaseTool):
    name = "corpus_builder"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "corpus_population"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.HYBRID  # local compute + network APIs

    dependencies = [
        "python:cv2",
        "python:numpy",
        "python:requests",
        "python:PIL",
        "python:transformers",
        "python:torch",
    ]
    install_instructions = (
        "pip install opencv-python numpy requests pillow transformers torch\n"
        "At least one stock source must be configured:\n"
        "  PEXELS_API_KEY for Pexels (free at https://www.pexels.com/api/)\n"
        "  UNSPLASH_ACCESS_KEY for Unsplash (see https://unsplash.com/documentation)\n"
        "  archive.org, nasa, and wikimedia work without API keys"
    )
    agent_skills = []

    capabilities = [
        "stock_fanout_search",
        "corpus_population",
        "clip_indexing",
        "clip_embedding",
    ]
    supports = {
        "multi_source": True,
        "video_and_image": True,
        "append_only": True,
        "resumable": True,
    }
    best_for = [
        "documentary-montage retrieval corpora",
        "topic-based offline clip indexing",
        "collecting candidate B-roll without repeated API calls per edit",
    ]
    not_good_for = [
        "single-clip downloads (use pexels_video instead)",
        "semantic retrieval itself (use clip_search)",
    ]
    fallback_tools = []

    input_schema = {
        "type": "object",
        "required": ["corpus_dir", "queries"],
        "properties": {
            "corpus_dir": {
                "type": "string",
                "description": "Project-local corpus directory, e.g. projects/foo/corpus",
            },
            "queries": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": ["video", "image", "any"],
                            "default": "video",
                        },
                        "per_source": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 80,
                        },
                    },
                },
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Source names to use (e.g. ['pexels','archive_org']). "
                               "Defaults to all available.",
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
            "max_new_clips": {
                "type": "integer",
                "default": 100,
                "minimum": 1,
                "description": "Halt after this many NEW rows have been added.",
            },
            "skip_existing": {"type": "boolean", "default": True},
            "thumbs_per_video": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=2048, vram_mb=0, disk_mb=4000, network_required=True
    )
    side_effects = [
        "downloads clips to <corpus_dir>/clips",
        "writes thumbnails under <corpus_dir>/thumbnails",
        "appends rows to <corpus_dir>/index.jsonl + embedding .npy files",
        "calls external stock APIs",
    ]
    user_visible_verification = [
        "Open <corpus_dir>/index.jsonl and inspect a few added rows",
        "Open <corpus_dir>/thumbnails/<some_clip_id>/frame_02.jpg visually",
    ]

    def get_status(self) -> ToolStatus:
        try:
            from tools.video.stock_sources import all_sources, available_sources
        except Exception:
            return ToolStatus.UNAVAILABLE
        total = len(all_sources())
        available = len(available_sources())
        if available == 0:
            return ToolStatus.UNAVAILABLE
        if available < total:
            return ToolStatus.DEGRADED
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
            from lib.corpus import Corpus
            from tools.video.clip_cache import get_default_cache
            from tools.video.stock_sources import (
                SearchFilters,
                all_sources,
                available_sources,
                get_source,
                source_summary,
            )

            corpus_dir = Path(inputs["corpus_dir"])
            queries: list[dict] = list(inputs["queries"])
            source_names: Optional[list[str]] = inputs.get("sources")
            filters_in: dict = inputs.get("filters") or {}
            max_new = int(inputs.get("max_new_clips", 100))
            skip_existing = bool(inputs.get("skip_existing", True))
            thumbs_per_video = int(inputs.get("thumbs_per_video", 5))

            # Resolve sources. If the caller passed an explicit list we
            # must not silently degrade: pinned-but-unavailable sources
            # are a provider substitution the agent needs to surface.
            if source_names:
                requested: list = []
                unavailable_requested: list[str] = []
                known_sources = {src.name: src for src in all_sources()}
                for name in source_names:
                    s = known_sources.get(name)
                    if s is None:
                        try:
                            s = get_source(name)
                        except KeyError as e:
                            return ToolResult(success=False, error=str(e))
                    if s.is_available():
                        requested.append(s)
                    else:
                        unavailable_requested.append(name)
                if unavailable_requested:
                    summary = source_summary()
                    return ToolResult(
                        success=False,
                        error=(
                            "Requested stock sources are unavailable: "
                            f"{', '.join(unavailable_requested)}. "
                            "Available now: "
                            f"{', '.join(summary['available_source_names']) or 'none'}. "
                            "Check corpus_builder.source_provider_menu during preflight "
                            "before rerunning."
                        ),
                    )
                sources = requested
            else:
                sources = available_sources()

            if not sources:
                return ToolResult(
                    success=False,
                    error="No stock sources available. " + self.install_instructions,
                )

            corp = Corpus(corpus_dir)
            corp.load()
            corp.ensure_dirs()

            # Shared clip bytes cache (Phase 1). Hits hard-link blobs
            # from a previous run's download into this corpus dir so we
            # don't re-hit the source API or re-download megabytes.
            # Faults never block the pipeline — a cache miss just means
            # we download like before.
            cache = get_default_cache()
            run_cache_stats = {"hits": 0, "misses": 0, "bytes_saved": 0}

            per_source_counts: dict[str, int] = {s.name: 0 for s in sources}
            added_ids: list[str] = []
            errors: list[dict] = []
            skipped = 0
            failed = 0
            candidates_seen = 0

            def filters_for(q_spec: dict) -> SearchFilters:
                return SearchFilters(
                    kind=q_spec.get("kind", "video"),
                    per_page=int(q_spec.get("per_source", 10)),
                    min_duration=filters_in.get("min_duration"),
                    max_duration=filters_in.get("max_duration"),
                    orientation=filters_in.get("orientation"),
                    min_width=filters_in.get("min_width"),
                )

            for q_spec in queries:
                if len(added_ids) >= max_new:
                    break
                query = q_spec["query"]
                f = filters_for(q_spec)

                for src in sources:
                    if len(added_ids) >= max_new:
                        break
                    try:
                        cands = src.search(query, f)
                    except Exception as e:
                        errors.append({
                            "phase": "search",
                            "source": src.name,
                            "query": query,
                            "error": f"{type(e).__name__}: {e}",
                        })
                        continue

                    candidates_seen += len(cands)
                    for cand in cands:
                        if len(added_ids) >= max_new:
                            break

                        if skip_existing and corp.has(cand.clip_id):
                            skipped += 1
                            continue

                        try:
                            rec = self._process_candidate(
                                cand=cand,
                                src=src,
                                corp=corp,
                                query=query,
                                thumbs_per_video=thumbs_per_video,
                                cache=cache,
                                run_cache_stats=run_cache_stats,
                            )
                        except Exception as e:
                            failed += 1
                            errors.append({
                                "phase": "process",
                                "clip_id": cand.clip_id,
                                "error": f"{type(e).__name__}: {e}",
                            })
                            continue

                        if rec is None:
                            failed += 1
                            continue
                        added_ids.append(rec.clip_id)
                        per_source_counts[src.name] = per_source_counts.get(src.name, 0) + 1

            # Single save at the end. Corpus.save() writes JSONL first
            # (source of truth) then both .npy files, so a crash mid-save
            # still leaves a loadable corpus.
            corp.save()

            elapsed = time.time() - start
            try:
                cache_snapshot = cache.stats()
            except Exception as e:
                cache_snapshot = {"error": f"{type(e).__name__}: {e}"}

            return ToolResult(
                success=True,
                data={
                    "corpus_dir": str(corpus_dir),
                    "queries_run": len(queries),
                    "candidates_seen": candidates_seen,
                    "clips_added": len(added_ids),
                    "clips_skipped_existing": skipped,
                    "clips_failed": failed,
                    "per_source_counts": per_source_counts,
                    "added_ids": added_ids,
                    "total_corpus_size": len(corp),
                    "requested_sources": source_names or [],
                    "resolved_sources": [s.name for s in sources],
                    "source_provider_summary": source_summary(),
                    # Shared clip bytes cache (Phase 1): per-run
                    # counters plus a full stats snapshot for the
                    # agent to display in the production report.
                    "cache_hits": run_cache_stats["hits"],
                    "cache_misses": run_cache_stats["misses"],
                    "cache_bytes_saved": run_cache_stats["bytes_saved"],
                    "cache_stats": cache_snapshot,
                    "errors": errors[:25],  # cap log noise
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

    # ------------------------------------------------------------------
    # Per-candidate pipeline
    # ------------------------------------------------------------------

    def _process_candidate(
        self,
        cand,
        src,
        corp,
        query: str,
        thumbs_per_video: int,
        cache,
        run_cache_stats: dict,
    ):
        """Download → thumb → embed → add one Candidate to the corpus.

        Returns the created `ClipRecord` on success, None if the clip
        was rejected (download empty, thumb extraction failed, etc.).
        Raises on unexpected errors (the caller logs them).

        Before downloading, consults the shared clip bytes cache at
        ``~/.openmontage/clips_cache/``: if the file is already on
        disk from a previous run (the same clip surfaced for a
        different project), the cache hard-links it straight into
        ``local_abs`` and we skip the network fetch entirely. On a
        miss we download as before and ingest the fresh file so the
        next run benefits. Cache faults never block the pipeline —
        they degrade gracefully to normal downloads.
        """
        import cv2

        from lib.clip_embedder import embed_images, embed_texts, pool_frames
        from lib.corpus import ClipRecord

        # Pick file extension from the URL path (sources give us
        # stable .mp4/.jpg/.png URLs) with a kind-aware fallback.
        ext = _guess_ext(cand)
        local_rel = Path("clips") / f"{cand.clip_id}{ext}"
        local_abs = corp.corpus_dir / local_rel

        # Try the shared cache first. A hit links the cached blob
        # into local_abs (same filesystem → hard link, cross-drive
        # → copy) and we skip the source fetch entirely.
        cache_hit = False
        try:
            cache_hit = cache.try_link(cand.clip_id, local_abs)
        except Exception:
            # Never let a cache fault block the pipeline — fall
            # through to a fresh download. The cache surfaces faults
            # via its own stats counters.
            cache_hit = False

        if cache_hit:
            run_cache_stats["hits"] += 1
            try:
                run_cache_stats["bytes_saved"] += local_abs.stat().st_size
            except OSError:
                pass
        else:
            run_cache_stats["misses"] += 1
            # Download. Any HTTP/IO exception propagates up to the
            # per-candidate try in execute().
            src.download(cand, local_abs)
            if not local_abs.exists() or local_abs.stat().st_size < 1024:
                # Empty / near-empty file = bad download. Clean up so a
                # retry doesn't mistake it for success.
                try:
                    if local_abs.exists():
                        local_abs.unlink()
                except OSError:
                    pass
                return None

            # Ingest the fresh file into the shared cache so the
            # next run can hit it. Swallow ingest failures — the
            # current run already has the bytes locally, which is
            # what matters for this build.
            try:
                cache.ingest(
                    cand.clip_id,
                    local_abs,
                    metadata={
                        "source": cand.source,
                        "source_id": cand.source_id,
                        "source_url": cand.source_url,
                        "license": cand.license,
                        "creator": cand.creator,
                        "source_tags": cand.source_tags,
                    },
                )
            except Exception:
                pass

        thumb_dir_rel = Path("thumbnails") / cand.clip_id
        thumb_dir_abs = corp.corpus_dir / thumb_dir_rel
        thumb_dir_abs.mkdir(parents=True, exist_ok=True)

        width = cand.width
        height = cand.height
        duration = cand.duration
        motion_score = 0.0

        if cand.kind == "video":
            thumb_paths, probe = _extract_video_thumbs(
                local_abs, thumb_dir_abs, thumbs_per_video
            )
            if not thumb_paths:
                return None
            if probe:
                width = probe.get("width") or width
                height = probe.get("height") or height
                duration = probe.get("duration") or duration
                motion_score = float(probe.get("motion_score", 0.0))
        else:
            dst = thumb_dir_abs / "frame_00.jpg"
            if not _save_as_jpeg(local_abs, dst):
                return None
            thumb_paths = [dst]
            img = cv2.imread(str(local_abs))
            if img is not None:
                height, width = img.shape[:2]

        # CLIP embeddings. embed_images loads the model lazily on
        # first call; subsequent candidates reuse the cached model.
        clip_frames = embed_images(thumb_paths)
        clip_vec = pool_frames(clip_frames)

        # Tag channel: prefer source-supplied tags/description,
        # fall back to the query so the row still carries SOME text
        # signal. pool_frames returns zeros if empty so this never
        # breaks the fused ranking math.
        tag_text = cand.source_tags or query
        tag_vec = embed_texts([tag_text])[0]

        rec = ClipRecord(
            clip_id=cand.clip_id,
            source=cand.source,
            source_id=cand.source_id,
            source_url=cand.source_url,
            local_path=str(local_rel).replace("\\", "/"),
            kind=cand.kind,
            thumb_dir=str(thumb_dir_rel).replace("\\", "/"),
            query=query,
            creator=cand.creator,
            license=cand.license,
            duration=float(duration or 0.0),
            width=int(width or 0),
            height=int(height or 0),
            motion_score=motion_score,
            dominant_colors=[],
            source_tags=cand.source_tags,
        )
        corp.add(rec, clip_vec, tag_vec)
        return rec


# ----------------------------------------------------------------------
# Module-level helpers (kept outside the class so tests can hit them)
# ----------------------------------------------------------------------


def _guess_ext(cand) -> str:
    """Extract a sensible file extension from a candidate's URL."""
    known = {".mp4", ".mov", ".mkv", ".webm", ".ogv", ".m4v",
             ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    path = urllib.parse.urlparse(cand.download_url).path
    ext = Path(path).suffix.lower()
    if ext in known:
        # Normalise .jpeg→.jpg for consistent clip paths
        return ".jpg" if ext == ".jpeg" else ext
    return ".mp4" if cand.kind == "video" else ".jpg"


def _extract_video_thumbs(
    video_path: Path, out_dir: Path, n_frames: int
) -> tuple[list[Path], dict]:
    """Extract `n` evenly-spaced JPEG thumbnails from a video.

    Returns ``(thumb_paths, probe_dict)``. The probe dict carries the
    real dimensions, duration, and a cheap motion score (mean abs
    pixel diff between frame 0 and the middle frame). Used to backfill
    `ClipRecord` fields that the source API didn't give us.
    """
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return [], {}

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = total / fps if fps > 0 else 0.0

    if total < 2:
        cap.release()
        return [], {}

    n = max(1, min(n_frames, total))
    # Space positions at the midpoints of equal segments so we skip the
    # first/last frame (often black or a splash).
    positions = [int(round((i + 0.5) * total / n)) for i in range(n)]

    thumb_paths: list[Path] = []
    captured: list = []
    for idx, pos in enumerate(positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(pos, total - 1)))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        dst = out_dir / f"frame_{idx:02d}.jpg"
        cv2.imwrite(str(dst), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        thumb_paths.append(dst)
        captured.append(frame)
    cap.release()

    motion = 0.0
    if len(captured) >= 2:
        import numpy as np
        a = cv2.cvtColor(captured[0], cv2.COLOR_BGR2GRAY).astype(np.float32)
        b = cv2.cvtColor(captured[len(captured) // 2], cv2.COLOR_BGR2GRAY).astype(np.float32)
        motion = float(np.abs(a - b).mean())

    return thumb_paths, {
        "width": width,
        "height": height,
        "duration": duration,
        "motion_score": motion,
    }


def _save_as_jpeg(src_path: Path, dst_path: Path) -> bool:
    """Load an arbitrary image file and re-save as JPEG.

    Handles PNG/JPEG/TIFF/WebP inputs — anything cv2.imread understands.
    Returns True on success, False on unreadable input (so the caller
    can reject the candidate cleanly).
    """
    import cv2

    img = cv2.imread(str(src_path))
    if img is None:
        return False
    cv2.imwrite(str(dst_path), img, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return True
