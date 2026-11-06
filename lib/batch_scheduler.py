"""Batch Scheduler — chunks image-generation sentences into gflow-cli batches.

Respects the confirmed gflow-cli 0.92.0 limits:

  * ``gflow image t2i`` accepts 1-4 prompts per call (``-n``/``--count``).
  * ``gflow run --config`` runs a JSON batch sequentially with
    ``--continue-on-error`` (default) and supports ``--resume`` (needs
    ``--project``).
  * Aspect ratio ``16:9``, model ``nano2`` (Nano Banana 2.1).

The scheduler never calls gflow itself — it builds batch manifests and
delegates execution to :class:`lib.gflow_wrapper.GflowWrapper`, which
enforces the zero-cost gate and ``READY_FOR_APPROVAL``.

All scheduling logic is local and zero-cost.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Max prompts per gflow image t2i call (observed: 1-4).
MAX_PROMPTS_PER_CALL = 4


@dataclass
class BatchPrompt:
    """One image-generation request inside a batch."""

    sentence_id: str
    prompt: str
    prompt_id: str
    asset_id: str
    output_filename: str
    aspect_ratio: str = "16:9"
    model: str = "nano2"
    count: int = 1
    reference_entity: str | None = None


@dataclass
class BatchManifest:
    """One batch's generation plan."""

    batch_id: str
    project_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    prompts: list[BatchPrompt] = field(default_factory=list)
    output_dir: str = ""
    status: str = "planned"  # planned | running | completed | failed | partial
    completed_sentences: list[str] = field(default_factory=list)
    failed_sentences: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def total(self) -> int:
        return len(self.prompts)

    @property
    def remaining(self) -> int:
        done = set(self.completed_sentences) | set(self.failed_sentences)
        return self.total - len(done)


class BatchScheduler:
    """Split sentences into batches and track per-batch progress.

    Concurrency is capped (default 1) because gflow-cli is a single
    sequential process; multiple batch configs may be queued but only one
    executes at a time.
    """

    def __init__(
        self,
        *,
        max_prompts_per_call: int = MAX_PROMPTS_PER_CALL,
        max_concurrent_batches: int = 1,
    ) -> None:
        self.max_prompts_per_call = max(1, min(4, max_prompts_per_call))
        self.max_concurrent_batches = max(1, max_concurrent_batches)
        self.batches: dict[str, BatchManifest] = {}
        self._running = 0

    # ------------------------------------------------------------------
    # Batch creation
    # ------------------------------------------------------------------

    def create_batch(
        self,
        *,
        batch_id: str,
        project_id: str,
        items: list[BatchPrompt],
        output_dir: str | Path,
    ) -> BatchManifest:
        """Create a batch, splitting into sub-chunks of ``max_prompts_per_call``.

        Each BatchPrompt becomes one row in the gflow run config.  Batches
        larger than ``max_prompts_per_call`` are still a single manifest
        (gflow run handles them sequentially); the per-call limit is honored
        by the executor when it invokes ``gflow image t2i -n`` per prompt or
        groups rows.
        """
        manifest = BatchManifest(
            batch_id=batch_id,
            project_id=project_id,
            prompts=list(items),
            output_dir=str(output_dir),
        )
        self.batches[batch_id] = manifest
        return manifest

    def chunk_for_t2i(self, manifest: BatchManifest) -> list[list[BatchPrompt]]:
        """Split a manifest's prompts into chunks callable by one t2i call.

        Returns chunks of at most ``max_prompts_per_call`` prompts so the
        executor can invoke ``gflow image t2i`` once per chunk (or one
        ``gflow run --config`` per chunk).
        """
        chunks: list[list[BatchPrompt]] = []
        for i in range(0, len(manifest.prompts), self.max_prompts_per_call):
            chunks.append(manifest.prompts[i : i + self.max_prompts_per_call])
        return chunks

    # ------------------------------------------------------------------
    # Queue / concurrency
    # ------------------------------------------------------------------

    def mark_running(self, batch_id: str) -> bool:
        """Mark a batch running; returns False if concurrency cap reached."""
        if self._running >= self.max_concurrent_batches:
            return False
        if batch_id in self.batches:
            self.batches[batch_id].status = "running"
        self._running += 1
        return True

    def mark_complete(self, batch_id: str) -> None:
        if batch_id in self.batches:
            self.batches[batch_id].status = "completed"
        self._running = max(0, self._running - 1)

    def mark_failed(self, batch_id: str) -> None:
        if batch_id in self.batches:
            self.batches[batch_id].status = "failed"
        self._running = max(0, self._running - 1)

    def mark_partial(self, batch_id: str) -> None:
        if batch_id in self.batches:
            self.batches[batch_id].status = "partial"
        self._running = max(0, self._running - 1)

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    def record_success(self, batch_id: str, sentence_id: str) -> None:
        m = self.batches.get(batch_id)
        if m and sentence_id not in m.completed_sentences:
            m.completed_sentences.append(sentence_id)

    def record_failure(self, batch_id: str, sentence_id: str) -> None:
        m = self.batches.get(batch_id)
        if m and sentence_id not in m.failed_sentences:
            m.failed_sentences.append(sentence_id)

    def retryable_sentences(self, batch_id: str) -> list[str]:
        """Sentences in a batch that failed and can be retried."""
        m = self.batches.get(batch_id)
        if not m:
            return []
        done = set(m.completed_sentences) | set(m.failed_sentences)
        return [p.sentence_id for p in m.prompts if p.sentence_id not in done]

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_prompts_per_call": self.max_prompts_per_call,
            "max_concurrent_batches": self.max_concurrent_batches,
            "running": self._running,
            "batches": {bid: m.to_dict() for bid, m in self.batches.items()},
        }

    # ------------------------------------------------------------------
    # Serialization (for resume across Codespace restart)
    # ------------------------------------------------------------------

    def save_state(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load_state(
        cls, path: str | Path,
        max_prompts_per_call: int = MAX_PROMPTS_PER_CALL,
        max_concurrent_batches: int = 1,
    ) -> "BatchScheduler":
        p = Path(path)
        if not p.exists():
            return cls(
                max_prompts_per_call=max_prompts_per_call,
                max_concurrent_batches=max_concurrent_batches,
            )
        data = json.loads(p.read_text(encoding="utf-8"))
        sched = cls(
            max_prompts_per_call=data.get("max_prompts_per_call", max_prompts_per_call),
            max_concurrent_batches=data.get(
                "max_concurrent_batches", max_concurrent_batches
            ),
        )
        for bid, bdata in data.get("batches", {}).items():
            prompts = [
                BatchPrompt(**pp) for pp in bdata.get("prompts", [])
            ]
            m = BatchManifest(
                batch_id=bid,
                project_id=bdata.get("project_id", ""),
                created_at=bdata.get("created_at", ""),
                prompts=prompts,
                output_dir=bdata.get("output_dir", ""),
                status=bdata.get("status", "planned"),
                completed_sentences=bdata.get("completed_sentences", []),
                failed_sentences=bdata.get("failed_sentences", []),
            )
            sched.batches[bid] = m
        return sched
