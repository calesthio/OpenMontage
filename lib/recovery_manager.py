"""Recovery Manager — resume image generation after interruption / restart.

Tracks which sentences are planned, generated, QC-passed, failed, or
duplicate.  On resume it skips completed work and re-attempts only failed or
missing-image sentences.  All state lives in the Asset Registry (single
source of truth); this module adds a lightweight checkpoint file so a
Codespace restart can continue without regenerating completed images.

Zero-cost: no generation, no credits.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RecoveryCheckpoint:
    """Persisted resume point for one project."""

    project_id: str
    version: str = "1.0"
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_sentences: list[str] = field(default_factory=list)
    failed_sentences: list[str] = field(default_factory=list)
    pending_sentences: list[str] = field(default_factory=list)
    duplicate_sentences: list[str] = field(default_factory=list)
    total_planned: int = 0
    total_generated: int = 0
    total_qc_passed: int = 0
    total_failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecoveryManager:
    """Build and consume resume checkpoints from an AssetRegistry."""

    def __init__(self, registry) -> None:
        self.registry = registry
        self.checkpoint_path = registry.root / "recovery_checkpoint.json"

    # ------------------------------------------------------------------
    # Checkpoint IO
    # ------------------------------------------------------------------

    def save(self, checkpoint: RecoveryCheckpoint) -> None:
        checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
        self.checkpoint_path.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> RecoveryCheckpoint | None:
        if not self.checkpoint_path.exists():
            return None
        try:
            data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return RecoveryCheckpoint(**data)

    # ------------------------------------------------------------------
    # Build checkpoint from current registry state
    # ------------------------------------------------------------------

    def snapshot(self) -> RecoveryCheckpoint:
        assets = self.registry.list_assets()
        completed: list[str] = []
        failed: list[str] = []
        pending: list[str] = []
        duplicates: list[str] = []
        total_generated = 0
        total_qc = 0
        total_failed = 0

        for rec in assets:
            sid = rec.sentence_id
            if rec.status in ("qc_passed",):
                completed.append(sid)
                total_qc += 1
            elif rec.status == "generated":
                pending.append(sid)   # needs QC
                total_generated += 1
            elif rec.status == "failed":
                failed.append(sid)
                total_failed += 1
            elif rec.status == "duplicate":
                duplicates.append(sid)
            else:
                pending.append(sid)   # planned / unknown

        return RecoveryCheckpoint(
            project_id=self.registry.project_id,
            completed_sentences=completed,
            failed_sentences=failed,
            pending_sentences=pending,
            duplicate_sentences=duplicates,
            total_planned=len(assets),
            total_generated=total_generated,
            total_qc_passed=total_qc,
            total_failed=total_failed,
        )

    # ------------------------------------------------------------------
    # Resume planning
    # ------------------------------------------------------------------

    def sentences_to_process(self, all_sentence_ids: list[str]) -> dict[str, list[str]]:
        """Partition *all_sentence_ids* by resume state.

        Returns dict with keys:
          * ``process``   — sentences that need generation (pending/failed/missing)
          * ``skip``      — sentences already QC-passed (complete)
          * ``retry``     — sentences previously failed (retry once)
        """
        ckpt = self.load() or self.snapshot()
        completed_set = set(ckpt.completed_sentences)
        failed_set = set(ckpt.failed_sentences)
        pending_set = set(ckpt.pending_sentences)

        process: list[str] = []
        skip: list[str] = []
        retry: list[str] = []

        for sid in all_sentence_ids:
            if sid in completed_set:
                skip.append(sid)
                continue
            if sid in failed_set:
                retry.append(sid)
                continue
            # not recorded yet -> needs generation
            if sid not in pending_set:
                process.append(sid)
            else:
                # recorded pending but image may be missing after restart
                rec = self.registry.get_asset(sentence_id=sid)
                if rec and rec.file_path and Path(rec.file_path).exists():
                    # image present; needs QC
                    process.append(sid)
                else:
                    process.append(sid)  # regenerate / re-QC

        return {"process": process, "skip": skip, "retry": retry}

    def mark_resumed(self, checkpoint: RecoveryCheckpoint) -> None:
        self.save(checkpoint)
