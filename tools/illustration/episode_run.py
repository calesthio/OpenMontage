#!/usr/bin/env python3
"""tools/illustration/episode_run.py - episode-scale image production.

One episode = one brief = one budget = a few batches = one Kaggle kernel per
batch. Everything is resumable and fail-closed:

  * budget: images per minute of video (default 7, allowed band 6-8),
  * batches of 40-100 prompts, balanced, one kernel per batch,
  * per-image seed log (append only, one line per planned render),
  * resume: an image already verified by sha256 is never regenerated,
  * retry: only the failed prompts go into the next submission,
  * hard fail: fewer usable images than prompts -> RunError,
  * owner-approved cache: approved images are never regenerated,
  * manifest: model, params, verified versions, per-image evidence.

The bridge is injected: the real one is the Kaggle bridge, the tests use
`FakeBridge` (no network, no GPU).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tools.illustration.image_brief import ImageBriefError, build_brief
from tools.illustration.owner_review import (
    decisions_by_render,
    ledger_path as owner_ledger_path,
)
from tools.illustration.model_registry import ModelAdapter
from tools.illustration.style_kit import StyleSpec

#: Allowed band for the episode image budget (images per minute of video).
IMAGES_PER_MINUTE_MIN = 6
IMAGES_PER_MINUTE_MAX = 8
IMAGES_PER_MINUTE_DEFAULT = 7

#: How often a rejected image may be re-generated before the run gives up
#: (the episode then fails closed and the owner has to supply a replacement).
MAX_OWNER_REJECTION_ATTEMPTS = 4

#: A retry must change something concrete: the seed is re-drawn inside the
#: reserved range with this stride (prime-ish, bigger than the largest beat
#: offset, so two renders never land on the same seed).
RETRY_SEED_STRIDE = 64

#: Production batch size (prompts per kernel).
BATCH_SIZE_MIN = 40
BATCH_SIZE_MAX = 100
BATCH_SIZE_DEFAULT = 60


class BudgetError(RuntimeError):
    """The episode image budget is missing or out of range."""


class RunError(RuntimeError):
    """The episode run cannot continue (fail closed)."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value: str) -> str:
    import re
    out = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return out.strip("_") or "item"


class FakeBridge:
    """A deterministic stand-in for the Kaggle bridge (tests only).

    * `fail`  - render ids that are not produced at all,
    * `black` - render ids that come back as black frames,
    * `corrupt_sha` - the manifest sha256 does not match the file.
    """

    def __init__(self, *, fail: Sequence[str] = (), black: Sequence[str] = (),
                 width: int = 320, height: int = 180,
                 corrupt_sha: bool = False) -> None:
        self.fail = set(fail)
        self.black = set(black)
        self.width = width
        self.height = height
        self.corrupt_sha = corrupt_sha
        self.submissions = 0
        self.jobs: List[Dict[str, Any]] = []
        self.runs: Dict[str, Dict[str, Any]] = {}

    def submit(self, job: Dict[str, Any]) -> Dict[str, Any]:
        self.submissions += 1
        self.jobs.append(job)
        run_id = f"fake-run-{self.submissions}"
        self.runs[run_id] = job
        return {"run_id": run_id, "job_id": job["job_id"]}

    def fetch(self, job: Dict[str, Any], run_id: str) -> Path:
        from PIL import Image, ImageDraw

        out = Path("/tmp/kilo/fake_bridge") / run_id
        images_dir = out / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        entries: List[Dict[str, Any]] = []
        for render in job["renders"]:
            rid = render["render_id"]
            if rid in self.fail:
                continue
            path = images_dir / f"{rid}.png"
            if rid in self.black:
                Image.new("RGB", (self.width, self.height), (0, 0, 0)).save(path)
            else:
                seed = int(render.get("seed") or 0)
                img = Image.new("RGB", (self.width, self.height), (24, 60, 84))
                draw = ImageDraw.Draw(img)
                for x in range(0, self.width, 4):
                    shade = (seed * 31 + x * 17) % 255
                    draw.line([(x, 0), (x, self.height)],
                              fill=(shade, (shade * 3) % 255, (shade * 7) % 255))
                img.save(path)
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            entries.append({
                "render_id": rid,
                "scene_id": render.get("scene_id"),
                "variant": render.get("variant"),
                "file": path.name,
                "sha256": "0" * 64 if self.corrupt_sha else sha,
                "bytes": len(data),
                "width": self.width,
                "height": self.height,
                "seed": render.get("seed"),
                "steps": render.get("steps"),
                "guidance_scale": render.get("guidance_scale"),
                "prompt": render.get("prompt"),
                "black": rid in self.black,
                "nonfinite": False,
            })
        manifest = {
            "job_id": job["job_id"],
            "model": job.get("model"),
            "model_id": job.get("model_id"),
            "pipeline_class": job.get("pipeline_class"),
            "dtype": job.get("dtype"),
            "width": self.width,
            "height": self.height,
            "requested": len(job["renders"]),
            "generated": len(entries),
            "load_seconds": 0.0,
            "steady_state_sec_per_image": 0.0,
            "usable_images_per_minute": 0.0,
            "peak_vram_mb": 0,
            "black_count": len(self.black),
            "nan_count": 0,
            "oom_count": 0,
            "images": entries,
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                           encoding="utf-8")
        return out


class EpisodeImages:
    """The episode-scale illustration run."""

    def __init__(self, episode_root: str | Path, adapter: ModelAdapter,
                 style: StyleSpec, bridge: Any = None, *,
                 images_per_minute: int = IMAGES_PER_MINUTE_DEFAULT,
                 narration_minutes: Optional[float] = None,
                 script_path: Optional[str | Path] = None,
                 ledger_path: Optional[str | Path] = None,
                 spec_dir: Optional[str | Path] = None,
                 width: int = 1344, height: int = 768) -> None:
        self.episode_root = Path(episode_root)
        self.adapter = adapter
        self.style = style
        self.bridge = bridge
        self.images_per_minute = int(images_per_minute)
        self._narration_minutes = narration_minutes
        self.script_path = Path(script_path) if script_path else \
            self.episode_root / "script.md"
        self.ledger_path = Path(ledger_path) if ledger_path else \
            self.episode_root / "claim_ledger.md"
        self.spec_dir = Path(spec_dir) if spec_dir else \
            (Path("docs/openmontage/niches") / style.niche_id / "creatures")
        self.width = int(width)
        self.height = int(height)
        if not (IMAGES_PER_MINUTE_MIN <= self.images_per_minute
                <= IMAGES_PER_MINUTE_MAX):
            raise BudgetError(
                f"images_per_minute must be between {IMAGES_PER_MINUTE_MIN} "
                f"and {IMAGES_PER_MINUTE_MAX}, got {self.images_per_minute}")
        self.asset_dir = self.episode_root / "assets" / "illustrations"
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.asset_dir
        self.state_path = self.asset_dir / "run_state.json"
        self.seed_log_path = self.asset_dir / "seed_log.jsonl"
        self.approved_path = self.asset_dir / "approved.json"
        self.owner_ledger_path = owner_ledger_path(self.episode_root)
        self.manifest_path = self.asset_dir / "episode_manifest.json"

    # ------------------------------------------------------------- state
    def load_state(self) -> Dict[str, Any]:
        if not self.state_path.is_file():
            return {"schema_version": 1, "renders": {}, "batches": {},
                    "model": self.adapter.key}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RunError(f"the run state is not readable JSON: {exc}")

    def save_state(self, state: Dict[str, Any]) -> None:
        state["updated_utc"] = _now()
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load_approved(self) -> List[Dict[str, Any]]:
        if not self.approved_path.is_file():
            return []
        doc = json.loads(self.approved_path.read_text(encoding="utf-8"))
        return list(doc.get("approved") or [])

    def approved_count(self) -> int:
        return len(self.load_approved())

    def approve(self, render_id: str, approved_by: str = "owner") -> Dict[str, Any]:
        """Mark an image as owner-approved (it is never regenerated)."""
        state = self.load_state()
        entry = state["renders"].get(render_id)
        if entry is None:
            raise RunError(f"unknown render {render_id!r}")
        if entry.get("status") != "verified":
            raise RunError(
                f"render {render_id!r} is not verified (status "
                f"{entry.get('status')!r}); only verified images can be approved")
        approved = self.load_approved()
        record = {
            "render_id": render_id,
            "prompt_sha256": entry.get("prompt_sha256"),
            "sha256": entry.get("sha256"),
            "file": entry.get("file"),
            "approved_by": approved_by,
            "approved_utc": _now(),
        }
        approved = [a for a in approved if a.get("render_id") != render_id]
        approved.append(record)
        self.approved_path.write_text(
            json.dumps({"approved": approved}, indent=2), encoding="utf-8")
        entry["status"] = "approved"
        self.save_state(state)
        return record

    # --------------------------------------------------------- seed log
    def seed_log_lines(self) -> List[Dict[str, Any]]:
        if not self.seed_log_path.is_file():
            return []
        lines = []
        for line in self.seed_log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                lines.append(json.loads(line))
        return lines

    def _log_seed(self, record: Dict[str, Any]) -> None:
        logged = {(l.get("render_id"), l.get("prompt_sha256"))
                  for l in self.seed_log_lines()}
        key = (record.get("render_id"), record.get("prompt_sha256"))
        if key in logged:
            return
        with self.seed_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    # ----------------------------------------------------------- budget
    def narration_minutes(self) -> float:
        if self._narration_minutes is not None:
            return float(self._narration_minutes)
        manifest = (self.episode_root / "artifacts" / "narration_manifest.json")
        if manifest.is_file():
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            seconds = float(doc.get("expected_duration") or 0.0)
            if seconds > 0:
                return seconds / 60.0
        raise BudgetError(
            "the episode has no narration duration (artifacts/"
            "narration_manifest.json); pass narration_minutes explicitly")

    def budget(self) -> Dict[str, Any]:
        minutes = self.narration_minutes()
        max_images = int(round(minutes * self.images_per_minute))
        return {
            "images_per_minute": self.images_per_minute,
            "narration_minutes": round(minutes, 3),
            "max_images": max_images,
            "source": "narration duration x images per minute of video",
        }

    # ------------------------------------------------------------ brief
    def build_brief(self, *, max_images: Optional[int] = None,
                    required_beats: Sequence[str] = ()) -> Dict[str, Any]:
        return build_brief(self.script_path, self.ledger_path, self.spec_dir,
                           self.style, self.adapter, max_images=max_images,
                           required_beats=required_beats)

    # ------------------------------------------------------------- plan
    def plan(self, brief: Optional[Dict[str, Any]] = None, *,
             batch_size: int = BATCH_SIZE_DEFAULT,
             max_images: Optional[int] = None,
             select: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """Plan the episode: budget, batches, seeds, state."""
        if not (BATCH_SIZE_MIN <= int(batch_size) <= BATCH_SIZE_MAX):
            raise RunError(
                f"batch_size must be between {BATCH_SIZE_MIN} and "
                f"{BATCH_SIZE_MAX}, got {batch_size}")
        if brief is None:
            brief = self.build_brief(max_images=max_images)
        budget = self.budget()
        cap = int(max_images) if max_images else budget["max_images"]

        state = self.load_state()
        state["model"] = self.adapter.key
        state.setdefault("renders", {})
        state.setdefault("batches", {})
        approved = {a.get("prompt_sha256") for a in self.load_approved()}
        ledger = decisions_by_render(self.owner_ledger_path)

        entries = list(brief.get("entries") or [])
        dropped: List[str] = []
        if select:
            wanted = list(select)
            known = {e["render_id"] for e in entries}
            unknown = [r for r in wanted if r not in known]
            if unknown:
                raise RunError(f"unknown render ids in the selection: {unknown}")
            dropped = [e["beat_id"] for e in entries
                       if e["render_id"] not in wanted]
            entries = [e for e in entries if e["render_id"] in wanted]
        if len(entries) > cap:
            dropped += [e["beat_id"] for e in entries[cap:]]
            entries = entries[:cap]

        renders: List[Dict[str, Any]] = []
        for entry in entries:
            render_id = entry["render_id"]
            record = {
                "render_id": render_id,
                "beat_id": entry["beat_id"],
                "subject": entry["subject"],
                "subject_type": entry["subject_type"],
                "tag": entry["tag"],
                "view": entry["view"],
                "prompt": entry["prompt"],
                "negative_prompt": entry.get("negative_prompt"),
                "prompt_sha256": entry["prompt_sha256"],
                "seed": entry["seed"],
                "steps": entry["steps"],
                "guidance": entry["guidance"],
                "status": "pending",
                "sha256": None,
                "file": None,
                "error": None,
            }
            previous = state["renders"].get(render_id)
            if previous and previous.get("prompt_sha256") == record["prompt_sha256"]:
                record["status"] = previous.get("status", "pending")
                record["sha256"] = previous.get("sha256")
                record["file"] = previous.get("file")
                record["error"] = previous.get("error")
                if record["status"] in {"verified", "approved"} and record["file"]:
                    cached = self.asset_dir / record["file"]
                    if not cached.is_file():
                        record["status"] = "pending"
                        record["error"] = "cached file missing"
                    elif _sha256(cached) != record["sha256"]:
                        record["status"] = "pending"
                        record["error"] = "hash mismatch: the cached file no " \
                                          "longer matches the verified sha256"
            decision = ledger.get(render_id)
            if decision:
                record["owner_decision"] = decision.get("decision")
                record["owner_reviewer"] = decision.get("reviewer")
                record["owner_reviewed_utc"] = decision.get("reviewed_utc")
                if decision.get("decision") == "approved":
                    record["status"] = "approved"
                elif decision.get("decision") == "rejected":
                    attempt = int(record.get("attempts", 0)) + 1
                    record["attempts"] = attempt
                    record["last_error"] = "owner_rejected"
                    if attempt > MAX_OWNER_REJECTION_ATTEMPTS:
                        record["status"] = "rejected_exhausted"
                    else:
                        record["status"] = "pending"
                        self._reseed(record, attempt)
            if record["prompt_sha256"] in approved:
                record["status"] = "approved"
            state["renders"][render_id] = record
            renders.append(record)
            self._log_seed({
                "ts": _now(),
                "render_id": render_id,
                "beat_id": entry["beat_id"],
                "prompt_sha256": entry["prompt_sha256"],
                "seed": entry["seed"],
                "model": self.adapter.key,
                "status": "planned",
            })

        pending = [r for r in renders if r["status"] == "pending"]
        batches = self._batches(pending, int(batch_size))
        for batch in batches:
            state["batches"][str(batch["batch_id"])] = {
                "batch_id": batch["batch_id"],
                "render_ids": list(batch["render_ids"]),
                "partial": batch["partial"],
                "status": "planned",
            }

        plan = {
            "schema_version": 1,
            "episode": self.episode_root.name,
            "model": self.adapter.key,
            "budget": budget,
            "brief_sha256": brief.get("brief_sha256"),
            "tags": brief.get("tags"),
            "renders": renders,
            "batches": batches,
            "truncated": bool(dropped),
            "dropped_beats": dropped,
            "planned_utc": _now(),
        }
        state["plan"] = {k: v for k, v in plan.items() if k != "renders"}
        state["batch_size"] = int(batch_size)
        state["brief_sha256"] = brief.get("brief_sha256")
        state["budget"] = budget
        self.save_state(state)
        return plan

    def _batches(self, pending: List[Dict[str, Any]],
                 batch_size: int) -> List[Dict[str, Any]]:
        """Balanced batches: no batch above `batch_size`, none below 40 if the
        total allows it."""
        total = len(pending)
        if total == 0:
            return []
        count = max(1, (total + batch_size - 1) // batch_size)
        per_batch = (total + count - 1) // count
        batches = []
        for index in range(count):
            chunk = pending[index * per_batch:(index + 1) * per_batch]
            if not chunk:
                continue
            batches.append({
                "batch_id": index + 1,
                "render_ids": [r["render_id"] for r in chunk],
                "partial": len(chunk) < BATCH_SIZE_MIN,
            })
        return batches

    # ---------------------------------------------------------- pending
    def pending(self) -> List[Dict[str, Any]]:
        """The renders that still have to be generated.

        A render that was verified earlier is re-queued when its cached file
        no longer matches the verified sha256: the state alone is never
        trusted (fail closed).
        """
        state = self.load_state()
        changed = False
        for entry in state.get("renders", {}).values():
            if entry.get("status") not in {"verified", "approved"}:
                continue
            name = entry.get("file")
            if not name:
                continue
            cached = self.asset_dir / name
            if not cached.is_file():
                entry["status"] = "pending"
                entry["error"] = "cached file missing"
                changed = True
            elif _sha256(cached) != entry.get("sha256"):
                entry["status"] = "pending"
                entry["error"] = ("hash mismatch: the cached file no longer "
                                  "matches the verified sha256")
                changed = True
        if changed:
            self.save_state(state)
        return [r for r in state.get("renders", {}).values()
                if r.get("status") == "pending"]

    def batch(self, batch_id: int) -> Dict[str, Any]:
        state = self.load_state()
        batches = state.get("batches") or {}
        key = str(batch_id)
        if key not in batches:
            raise RunError(f"unknown batch {batch_id!r}")
        return batches[key]

    # ----------------------------------------------------------- submit
    def _reseed(self, entry: Dict[str, Any], attempt: int) -> bool:
        """Draw a new seed inside the reserved range (a retry must change
        something concrete). Returns True when the seed changed."""
        low, high = self.style.seed_policy.get("range", [3000, 3999])
        size = int(high) - int(low) + 1
        old_seed = int(entry.get("seed") or low)
        new_seed = int(low) + ((old_seed - int(low) + attempt * RETRY_SEED_STRIDE)
                               % size)
        if new_seed == old_seed:
            return False
        entry["brief_seed"] = entry.get("brief_seed", old_seed)
        entry["seed"] = new_seed
        entry["prompt_sha256"] = hashlib.sha256(
            f"{self.adapter.key}|{entry.get('prompt')}|{new_seed}"
            .encode("utf-8")).hexdigest()
        self._log_seed({
            "ts": _now(),
            "render_id": entry["render_id"],
            "prompt_sha256": entry["prompt_sha256"],
            "seed": new_seed,
            "model": self.adapter.key,
            "attempt": attempt,
            "status": "retry",
            "reason": entry.get("last_error") or "owner_rejected",
        })
        return True

    def _job_for(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        state = self.load_state()
        renders = [state["renders"][rid] for rid in batch["render_ids"]
                   if rid in state["renders"]]
        job = {
            "job_id": f"ill-{self.episode_root.name}-b{batch['batch_id']}-"
                      f"{self.adapter.key}",
            "episode_id": self.episode_root.name,
            "batch_id": batch["batch_id"],
            "model": self.adapter.key,
            "model_id": self.adapter.model_id,
            "pipeline_class": self.adapter.pipeline_class,
            "vae_model_id": self.adapter.vae_model_id,
            "unet_checkpoint": self.adapter.unet_checkpoint,
            "revision": "main",
            "dtype": self.adapter.dtype,
            "width": self.width,
            "height": self.height,
            "output_dir": f"illustrations_{self.episode_root.name}_"
                          f"b{batch['batch_id']}_{self.adapter.key}",
            "install_ladder": list(self.adapter.install_ladder),
            "load_config": self.adapter.load_config(),
            "model_config": self.adapter.job_model_config(),
            "max_wall_seconds": 5400,
            "attempt": 1,
            "changed_from_previous": f"batch {batch['batch_id']}: "
                                     f"{len(renders)} prompts",
            "renders": [
                {
                    "render_id": r["render_id"],
                    "scene_id": r["subject"],
                    "variant": self.style.niche_id,
                    "view": r["view"],
                    "prompt": r["prompt"],
                    "negative_prompt": r.get("negative_prompt"),
                    "guidance_scale": r.get("guidance"),
                    "steps": r.get("steps"),
                    "seed": r.get("seed"),
                    "prompt_sha256": r.get("prompt_sha256"),
                    "tag": r.get("tag"),
                    "beat_id": r.get("beat_id"),
                }
                for r in renders
            ],
        }
        return job

    def submit(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """Submit one batch (one kernel). No polling inside."""
        job = self._job_for(batch)
        if not job["renders"]:
            raise RunError("the batch has no renders to generate")
        result = self.bridge.submit(job)
        state = self.load_state()
        record = state["batches"].setdefault(str(batch["batch_id"]), {})
        record.update({
            "batch_id": batch["batch_id"],
            "render_ids": batch["render_ids"],
            "job_id": job["job_id"],
            "run_id": result.get("run_id"),
            "status": "submitted",
            "attempt": int(record.get("attempt", 0)) + 1,
            "submitted_utc": _now(),
        })
        for render in job["renders"]:
            entry = state["renders"].get(render["render_id"])
            if entry:
                entry["status"] = "submitted"
                entry["attempt"] = record["attempt"]
            self._log_seed({
                "ts": _now(),
                "render_id": render["render_id"],
                "prompt_sha256": render["prompt_sha256"],
                "seed": render["seed"],
                "model": self.adapter.key,
                "batch": batch["batch_id"],
                "attempt": record["attempt"],
                "status": "submitted",
            })
        self.save_state(state)
        return {"job_id": job["job_id"], "run_id": result.get("run_id"),
                "renders": len(job["renders"])}

    # ------------------------------------------------------------ fetch
    def fetch(self, batch: Dict[str, Any], *, qc: bool = False) -> Dict[str, Any]:
        """Fetch one batch and verify it (fail closed)."""
        state = self.load_state()
        record = state["batches"].get(str(batch["batch_id"])) or {}
        run_id = record.get("run_id")
        if not run_id:
            raise RunError(f"batch {batch['batch_id']} was never submitted")
        job = self._job_for(batch)
        fetched = Path(self.bridge.fetch(job, run_id))
        manifest_path = fetched / "manifest.json"
        if not manifest_path.is_file():
            raise RunError(f"the fetched tree has no manifest: {fetched}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_id = {str(i.get("render_id")): i for i in manifest.get("images") or []}

        verified: List[str] = []
        failed: List[str] = []
        errors: Dict[str, str] = {}
        for render in job["renders"]:
            rid = render["render_id"]
            entry = state["renders"].get(rid) or {}
            image = by_id.get(rid)
            if image is None:
                failed.append(rid)
                errors[rid] = "missing_image"
                entry.update({"status": "failed", "error": "missing_image"})
                continue
            source = fetched / "images" / str(image.get("file"))
            if not source.is_file():
                failed.append(rid)
                errors[rid] = "missing_file"
                entry.update({"status": "failed", "error": "missing_file"})
                continue
            actual = _sha256(source)
            if actual != str(image.get("sha256")):
                failed.append(rid)
                errors[rid] = "hash_mismatch"
                entry.update({"status": "failed", "error": "hash_mismatch"})
                continue
            if self._is_black(source):
                failed.append(rid)
                errors[rid] = "black_image"
                entry.update({"status": "failed", "error": "black_image"})
                continue
            target = self.asset_dir / \
                f"{_slug(entry.get('subject') or rid)}_{rid}.png"
            shutil.copyfile(source, target)
            entry.update({
                "status": "verified",
                "sha256": actual,
                "file": target.name,
                "error": None,
                "verified_utc": _now(),
            })
            if qc:
                entry["qc"] = self._qc(target)
                if not entry["qc"].get("passed", False):
                    entry["status"] = "failed"
                    entry["error"] = "qc_failed"
                    failed.append(rid)
                    errors[rid] = "qc_failed"
                    continue
            verified.append(rid)
            state["renders"][rid] = entry

        record.update({"status": "fetched", "verified": verified,
                       "failed": failed, "fetched_utc": _now()})
        state["batches"][str(batch["batch_id"])] = record

        # retry only the failed prompts: they go back into the queue and a
        # new batch is planned for them (verified images are never repeated)
        retry = []
        low, high = self.style.seed_policy.get("range", [3000, 3999])
        size = int(high) - int(low) + 1
        for rid in failed:
            entry = state["renders"].get(rid)
            if entry is None:
                continue
            entry["status"] = "pending"
            attempt = int(entry.get("attempts", 0)) + 1
            entry["attempts"] = attempt
            entry["last_error"] = errors.get(rid)
            self._reseed(entry, attempt)
            retry.append(entry)
        if retry:
            retry_ids = {r["render_id"] for r in retry}
            # a planned (never submitted) batch that covers the same renders
            # is superseded, not duplicated
            for key, other in list(state["batches"].items()):
                if other.get("status") != "planned":
                    continue
                ids = set(other.get("render_ids") or [])
                if ids and ids <= retry_ids:
                    other["status"] = "superseded"
                    other["superseded_utc"] = _now()
            next_id = max((int(k) for k in state["batches"]), default=0) + 1
            size = int(state.get("batch_size") or BATCH_SIZE_DEFAULT)
            for chunk in self._batches(retry, size):
                chunk["batch_id"] = next_id
                state["batches"][str(next_id)] = {
                    "batch_id": next_id,
                    "render_ids": list(chunk["render_ids"]),
                    "partial": chunk["partial"],
                    "status": "planned",
                    "retry_of": batch["batch_id"],
                }
                next_id += 1
        self.save_state(state)
        return {"verified": verified, "failed": failed, "errors": errors,
                "manifest": {k: manifest.get(k) for k in
                             ("load_seconds", "steady_state_sec_per_image",
                              "usable_images_per_minute", "peak_vram_mb",
                              "generated", "requested", "black_count",
                              "nan_count", "oom_count")}}

    def _is_black(self, path: Path) -> bool:
        try:
            from PIL import Image
            with Image.open(path) as img:
                grey = img.convert("L")
                extrema = grey.getextrema()
            return bool(extrema and extrema[1] < 8)
        except Exception:  # noqa: BLE001
            return False

    def _qc(self, path: Path) -> Dict[str, Any]:
        try:
            from tools.illustration.illustration_qc import qc_batch
            report = qc_batch([str(path)], self.width, self.height)
            results = report.get("results") or []
            if not results:
                return {"passed": False, "error": "qc produced no result"}
            first = results[0]
            return {
                "passed": bool(first.get("passed")),
                "blur_variance": first.get("blur_variance"),
                "blur_ok": first.get("blur_ok"),
                "aspect_ok": first.get("aspect_ok"),
                "text_like": first.get("text_like"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"passed": False, "error": str(exc)}

    # --------------------------------------------------------- finalize
    def finalize(self) -> Dict[str, Any]:
        """Hard fail when fewer usable images than prompts; else the manifest."""
        state = self.load_state()
        renders = list(state.get("renders", {}).values())
        usable = [r for r in renders
                  if r.get("status") in {"verified", "approved"}]
        expected = len(renders)
        if len(usable) < expected:
            raise RunError(
                f"only {len(usable)} usable images for {expected} prompts "
                f"({expected - len(usable)} failed) - the episode image set is "
                "incomplete, so the run fails closed")
        manifest = {
            "schema_version": 1,
            "episode": self.episode_root.name,
            "model": self.adapter.key,
            "model_id": self.adapter.model_id,
            "pipeline_class": self.adapter.pipeline_class,
            "versions": dict(self.adapter.versions),
            "params": {
                "steps": self.adapter.steps,
                "guidance": self.adapter.guidance,
                "dtype": self.adapter.dtype,
                "scheduler": dict(self.adapter.scheduler),
                "prompt_target": self.adapter.prompt_target,
                "prompt_variant": self.adapter.prompt_variant,
                "vae_model_id": self.adapter.vae_model_id,
                "unet_checkpoint": self.adapter.unet_checkpoint,
                "install_ladder": list(self.adapter.install_ladder),
            },
            "budget": state.get("budget"),
            "brief_sha256": state.get("brief_sha256"),
            "tags": (state.get("plan") or {}).get("tags"),
            "images": [
                {
                    "render_id": r["render_id"],
                    "beat_id": r.get("beat_id"),
                    "subject": r.get("subject"),
                    "view": r.get("view"),
                    "tag": r.get("tag"),
                    "prompt": r.get("prompt"),
                    "prompt_sha256": r.get("prompt_sha256"),
                    "seed": r.get("seed"),
                    "sha256": r.get("sha256"),
                    "file": r.get("file"),
                    "status": r.get("status"),
                    "qc": r.get("qc"),
                }
                for r in sorted(usable, key=lambda x: x["render_id"])
            ],
            "finalized_utc": _now(),
        }
        self.manifest_path.write_text(json.dumps(manifest, indent=2),
                                      encoding="utf-8")
        return manifest
