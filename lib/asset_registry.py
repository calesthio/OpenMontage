"""Asset Registry — single source of truth for generated project images.

For each project it maintains:

  * ``manifest.json``   — project-level manifest (all assets + status)
  * ``prompts.json``    — sentence_id -> source prompt (+ prompt_id)
  * ``generation_jobs.json`` — job_id -> generation job record
  * ``assets/``         — generated image files
  * ``qc_reports/``     — per-asset QC reports
  * ``generation_logs/`` — per-attempt generation logs

The path to an image is unambiguously tied to a ``sentence_id``:
``assets/<sentence_id>.png`` (one image per sentence, never shared).

All operations are local and zero-cost: no generation, no credits.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AssetRecord:
    """One registered image asset."""

    asset_id: str            # unique, e.g. "pilot-AST-S001"
    sentence_id: str         # one-to-one with a sentence
    prompt_id: str           # unique prompt id
    job_id: str | None       # flow job id (None until planned)
    file_path: str           # absolute path under assets/
    file_sha256: str | None  # sha256 of the image file
    source_prompt: str       # verbatim prompt used
    model: str
    aspect_ratio: str
    references: list[str]    # reference entity ids used
    generation_params: dict[str, Any]
    status: str              # planned | generated | qc_passed | qc_failed | duplicate | failed
    qc_result: dict[str, Any] | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetRegisterResult:
    """Outcome of registering / updating one asset."""

    asset: AssetRecord
    created: bool
    updated: bool
    message: str


class AssetRegistry:
    """Project-scoped asset registry with integrity and uniqueness checks."""

    def __init__(
        self,
        project_id: str,
        *,
        base_dir: str | Path = "projects",
    ) -> None:
        self.project_id = project_id
        self.root = Path(base_dir) / project_id
        self.assets_dir = self.root / "assets"
        self.prompts_dir = self.root / "prompts"
        self.jobs_dir = self.root / "jobs"
        self.qc_dir = self.root / "qc_reports"
        self.logs_dir = self.root / "generation_logs"
        for d in (
            self.root,
            self.assets_dir,
            self.prompts_dir,
            self.jobs_dir,
            self.qc_dir,
            self.logs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        self.manifest_path = self.root / "manifest.json"
        self.prompts_path = self.prompts_dir / "prompts.json"
        self.jobs_path = self.jobs_dir / "generation_jobs.json"

        self._assets: dict[str, AssetRecord] = {}      # asset_id -> record
        self._by_sentence: dict[str, str] = {}          # sentence_id -> asset_id
        self._by_prompt: dict[str, str] = {}            # prompt_id -> asset_id
        self._by_file: dict[str, str] = {}              # file_path -> asset_id
        self._load()

    # ------------------------------------------------------------------
    # Loading / persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self.manifest_path.exists():
            try:
                data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
            for entry in data.get("assets", []):
                rec = AssetRecord(**entry)
                self._assets[rec.asset_id] = rec
                self._by_sentence[rec.sentence_id] = rec.asset_id
                if rec.prompt_id:
                    self._by_prompt[rec.prompt_id] = rec.asset_id
                if rec.file_path:
                    self._by_file[rec.file_path] = rec.asset_id

    def _save_manifest(self) -> None:
        payload = {
            "project_id": self.project_id,
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "assets": [r.to_dict() for r in self._assets.values()],
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _save_prompts(self) -> None:
        data = {
            "project_id": self.project_id,
            "version": "1.0",
            "prompts": [
                {
                    "prompt_id": r.prompt_id,
                    "sentence_id": r.sentence_id,
                    "prompt": r.source_prompt,
                    "asset_id": r.asset_id,
                }
                for r in self._assets.values()
                if r.prompt_id
            ],
        }
        self.prompts_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _save_jobs(self) -> None:
        data = {
            "project_id": self.project_id,
            "version": "1.0",
            "jobs": [
                {
                    "job_id": r.job_id,
                    "sentence_id": r.sentence_id,
                    "asset_id": r.asset_id,
                    "status": r.status,
                    "model": r.model,
                    "aspect_ratio": r.aspect_ratio,
                    "references": r.references,
                    "file_path": r.file_path,
                }
                for r in self._assets.values()
                if r.job_id
            ],
        }
        self.jobs_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_asset(
        self,
        *,
        sentence_id: str,
        prompt_id: str,
        source_prompt: str,
        model: str = "nano2",
        aspect_ratio: str = "16:9",
        references: list[str] | None = None,
        generation_params: dict[str, Any] | None = None,
        job_id: str | None = None,
        file_path: str | None = None,
        status: str = "planned",
    ) -> AssetRegisterResult:
        """Register (or update) one asset.  Enforces one-image-per-sentence.

        Raises ``ValueError`` if the sentence already has a different asset
        (one image cannot serve two sentences) or if asset_id / prompt_id
        collide with an unrelated record.
        """
        references = references or []
        generation_params = generation_params or {}
        asset_id = f"{self.project_id}-AST-{sentence_id}"

        # --- One image per sentence -------------------------------------
        existing_asset_id = self._by_sentence.get(sentence_id)
        if existing_asset_id and existing_asset_id != asset_id:
            raise ValueError(
                f"Sentence {sentence_id} already bound to asset "
                f"{existing_asset_id}; one image per sentence."
            )

        # --- ID uniqueness ---------------------------------------------
        if asset_id in self._assets and self._assets[asset_id].sentence_id != sentence_id:
            raise ValueError(f"Asset id {asset_id} already used by another sentence")
        if prompt_id in self._by_prompt and self._by_prompt[prompt_id] != asset_id:
            raise ValueError(f"Prompt id {prompt_id} already bound to another asset")
        if file_path and file_path in self._by_file and self._by_file[file_path] != asset_id:
            raise ValueError(f"File path {file_path} already bound to another asset")

        # --- file sha256 ----------------------------------------------
        file_sha256 = None
        if file_path:
            p = Path(file_path)
            if p.exists():
                file_sha256 = self._sha256(p)

        now = datetime.now(timezone.utc).isoformat()
        rec = AssetRecord(
            asset_id=asset_id,
            sentence_id=sentence_id,
            prompt_id=prompt_id,
            job_id=job_id,
            file_path=str(file_path) if file_path else "",
            file_sha256=file_sha256,
            source_prompt=source_prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            references=list(references),
            generation_params=generation_params,
            status=status,
            updated_at=now,
        )
        created = asset_id not in self._assets
        self._assets[asset_id] = rec
        self._by_sentence[sentence_id] = asset_id
        self._by_prompt[prompt_id] = asset_id
        if file_path:
            self._by_file[file_path] = asset_id

        self._save_manifest()
        self._save_prompts()
        self._save_jobs()
        return AssetRegisterResult(
            asset=rec, created=created, updated=(not created),
            message=("created" if created else "updated"),
        )

    def link_job(self, *, sentence_id: str, job_id: str) -> AssetRecord | None:
        """Bind a flow job id to an existing planned asset."""
        asset_id = self._by_sentence.get(sentence_id)
        if not asset_id:
            return None
        rec = self._assets[asset_id]
        rec.job_id = job_id
        rec.status = "planned"
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_manifest()
        self._save_jobs()
        return rec

    def record_generation(
        self,
        *,
        sentence_id: str,
        file_path: str,
        gflow_result: dict[str, Any] | None = None,
    ) -> AssetRecord | None:
        """Mark an asset as generated after a successful image call."""
        asset_id = self._by_sentence.get(sentence_id)
        if not asset_id:
            return None
        rec = self._assets[asset_id]
        rec.file_path = str(file_path)
        rec.file_sha256 = self._sha256(Path(file_path)) if Path(file_path).exists() else None
        rec.status = "generated"
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        if gflow_result:
            rec.generation_params = dict(rec.generation_params or {})
            rec.generation_params["gflow_result"] = gflow_result
        self._save_manifest()
        self._save_jobs()
        return rec

    def record_qc(self, *, sentence_id: str, qc_result: dict[str, Any]) -> AssetRecord | None:
        """Attach a QC result and update status."""
        asset_id = self._by_sentence.get(sentence_id)
        if not asset_id:
            return None
        rec = self._assets[asset_id]
        rec.qc_result = qc_result
        rec.status = "qc_passed" if qc_result.get("passed") else "qc_failed"
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        qc_path = self.qc_dir / f"{sentence_id}.json"
        qc_path.write_text(
            json.dumps(qc_result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._save_manifest()
        return rec

    def record_failure(self, *, sentence_id: str, error: str) -> AssetRecord | None:
        """Mark an asset as failed (retryable)."""
        asset_id = self._by_sentence.get(sentence_id)
        if not asset_id:
            return None
        rec = self._assets[asset_id]
        rec.status = "failed"
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        rec.generation_params = dict(rec.generation_params or {})
        rec.generation_params["last_error"] = error
        self._save_manifest()
        self._save_jobs()
        return rec

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_asset(self, *, sentence_id: str | None = None, asset_id: str | None = None) -> AssetRecord | None:
        if sentence_id is not None:
            aid = self._by_sentence.get(sentence_id)
            return self._assets.get(aid) if aid else None
        if asset_id is not None:
            return self._assets.get(asset_id)
        return None

    def get_by_status(self, status: str) -> list[AssetRecord]:
        return [r for r in self._assets.values() if r.status == status]

    def list_assets(self) -> list[AssetRecord]:
        return list(self._assets.values())

    def missing_images(self) -> list[str]:
        """Sentence ids whose asset has no existing image file."""
        missing = []
        for rec in self._assets.values():
            if rec.file_path and not Path(rec.file_path).exists():
                missing.append(rec.sentence_id)
            elif rec.status in ("generated", "qc_passed") and not rec.file_path:
                missing.append(rec.sentence_id)
        return missing

    def integrity_check(self) -> dict[str, Any]:
        """Full integrity: unique IDs, one-image-per-sentence, file presence."""
        problems: list[str] = []
        asset_ids = set(self._assets.keys())
        if len(asset_ids) != len(self._assets):
            problems.append("duplicate asset ids detected")
        sentence_ids = set(self._by_sentence.keys())
        if len(sentence_ids) != len(self._by_sentence):
            problems.append("duplicate sentence bindings detected")
        prompt_ids = set(self._by_prompt.keys())
        if len(prompt_ids) != len(self._by_prompt):
            problems.append("duplicate prompt ids detected")
        # one image per sentence
        for sid, aid in self._by_sentence.items():
            rec = self._assets[aid]
            if rec.sentence_id != sid:
                problems.append(f"asset {aid} bound to wrong sentence {rec.sentence_id}")
        # file presence for generated/qc_passed
        for rec in self._assets.values():
            if rec.status in ("generated", "qc_passed") and rec.file_path:
                if not Path(rec.file_path).exists():
                    problems.append(f"missing image file for {rec.sentence_id}: {rec.file_path}")
        return {
            "ok": len(problems) == 0,
            "problems": problems,
            "total_assets": len(self._assets),
            "by_status": {s: len(self.get_by_status(s)) for s in
                          {r.status for r in self._assets.values()}},
            "missing_images": self.missing_images(),
        }

    @staticmethod
    def _sha256(path: Path) -> str | None:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None
