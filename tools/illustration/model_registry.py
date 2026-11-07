#!/usr/bin/env python3
"""tools/illustration/model_registry.py - the CONFIG-locked image engine.

The image model is a config entry, not code. `config/image_engine.json` holds
one entry per model with

  * its verified library versions (from the S7/S8 kernel manifests),
  * its prompt rules (tools/prompting is OpenCode-owned -> read only),
  * its measured seconds/image (from the same manifests).

Changing the model is a JSON edit. This module is the adapter interface that
turns a config entry into the contract the rest of the pipeline consumes:

    engine   = load_engine(path)            # fail-closed
    adapter  = active_adapter(engine)        # the locked model
    renders  = plan_renders(specs, adapter.key, ...)
    job      = build_job(episode, adapter.key, renders, ...)
    fetched  = generator.generate(job, adapter)
    verify_fetched(fetched, job)             # fail-closed
    label_and_qc(fetched, job, out)         # label + image QC + manifest

Fail-closed rules (never a silent PASS):
  * a missing / unreadable / invalid config raises EngineConfigError,
  * a missing lock field, an unknown active model or an active model whose
    status is not OWNER_CONFIRMED / OWNER_GATED raises EngineConfigError,
  * a model entry without usable measurements cannot be projected,
  * a timing claim is only made for a model with usable (non-black) images.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO / "config" / "image_engine.json"

#: The lock fields the owner asked for. All of them must be present.
LOCK_FIELDS: Tuple[str, ...] = (
    "model", "scheduler", "steps", "guidance", "dtype", "seed_policy",
    "prompt_variant", "status",
)

#: Statuses that may be the ACTIVE model.
ACTIVE_STATUSES: Tuple[str, ...] = ("OWNER_CONFIRMED", "OWNER_GATED")

#: Statuses a registered model may carry.
MODEL_STATUSES: Tuple[str, ...] = ("OWNER_CONFIRMED", "OWNER_GATED", "BLOCKED")

#: Prompt targets understood by tools/prompting/builder.py (read only).
PROMPT_TARGETS: Tuple[str, ...] = ("sdxl", "klein", "zimage")


class EngineConfigError(RuntimeError):
    """The image engine config is missing, invalid or unsafe to use."""


# ---------------------------------------------------------------- adapters
@dataclass(frozen=True)
class ModelAdapter:
    """One model, as configured. Immutable: the config file is the lock."""

    key: str
    status: str
    display_name: str
    model_id: str
    pipeline_class: str
    pipeline_candidates: Tuple[str, ...]
    prompt_target: str
    prompt_variant: str
    prompt_rules: Dict[str, Any]
    steps: int
    guidance: Optional[float]
    scheduler: Dict[str, Any]
    dtype: str
    vae_model_id: Optional[str]
    unet_checkpoint: Optional[Dict[str, str]]
    cpu_offload: bool
    low_cpu_mem_usage: Optional[bool]
    extra_kwargs: Dict[str, Any]
    install_ladder: Tuple[str, ...]
    versions: Dict[str, str]
    measured: Dict[str, Any]
    license: Dict[str, Any]
    notes: str = ""

    # -- derived ---------------------------------------------------------
    @property
    def usable(self) -> bool:
        """True when the measured run produced usable (non-black) images."""
        return bool(self.measured.get("images_usable"))

    @property
    def sec_per_image(self) -> Optional[float]:
        value = self.measured.get("steady_state_sec_per_image")
        return float(value) if value is not None else None

    @property
    def load_seconds(self) -> float:
        return float(self.measured.get("load_seconds") or 0.0)

    def load_config(self) -> Dict[str, Any]:
        """The kernel-side `load_config` block for this model."""
        cfg: Dict[str, Any] = {
            "offload": bool(self.cpu_offload),
            "low_cpu_mem_usage": self.low_cpu_mem_usage,
            "extra_kwargs": dict(self.extra_kwargs),
            "guidance_override": self.guidance,
            # class=null means "pipeline default" - the kernel side then keeps
            # the scheduler the pipeline was loaded with.
            "scheduler": {
                "class": self.scheduler.get("class"),
                "kwargs": dict(self.scheduler.get("kwargs") or {}),
            },
        }
        return cfg

    def job_model_config(self) -> Dict[str, Any]:
        """The `model_config` block embedded into a job payload.

        It carries everything the Kaggle-side runner needs, so the runner does
        not need a hard-coded table per model.
        """
        return {
            "pipeline_candidates": list(self.pipeline_candidates),
            "load_config": self.load_config(),
            "install_ladder": list(self.install_ladder),
            "dtype": self.dtype,
            "prompt_target": self.prompt_target,
            "prompt_variant": self.prompt_variant,
            "steps": self.steps,
            "guidance": self.guidance,
            "scheduler": dict(self.scheduler),
            "versions": dict(self.versions),
        }


@dataclass(frozen=True)
class ImageEngine:
    """The whole config: the active lock plus every registered model."""

    model: str
    scheduler: Dict[str, Any]
    steps: int
    guidance: Optional[float]
    dtype: str
    seed_policy: Dict[str, Any]
    prompt_variant: str
    status: str
    fallback: Optional[Dict[str, Any]]
    selection: Dict[str, Any] = field(default_factory=dict)
    models: Dict[str, ModelAdapter] = field(default_factory=dict)
    path: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------- loader
def _require(doc: Dict[str, Any], key: str, where: str) -> Any:
    if key not in doc or doc[key] is None:
        raise EngineConfigError(f"{where}: required field {key!r} is missing")
    return doc[key]


def _build_adapter(key: str, entry: Dict[str, Any]) -> ModelAdapter:
    where = f"models.{key}"
    if not isinstance(entry, dict):
        raise EngineConfigError(f"{where}: entry must be an object")

    status = str(_require(entry, "status", where))
    if status not in MODEL_STATUSES:
        raise EngineConfigError(
            f"{where}: status {status!r} is not one of {list(MODEL_STATUSES)}")

    prompt_rules = entry.get("prompt_rules") or {}
    if not str(prompt_rules.get("source", "")).startswith("tools/prompting"):
        raise EngineConfigError(
            f"{where}: prompt_rules.source must point at tools/prompting "
            "(OpenCode-owned, read only)")

    versions = entry.get("versions") or {}
    for pkg in ("diffusers", "transformers"):
        if not versions.get(pkg):
            raise EngineConfigError(
                f"{where}: verified versions are missing {pkg!r}")

    measured = entry.get("measured") or {}
    if measured.get("steady_state_sec_per_image") is None:
        raise EngineConfigError(
            f"{where}: measured.steady_state_sec_per_image is missing")
    if not measured.get("source"):
        raise EngineConfigError(f"{where}: measured.source is missing")

    prompt_target = str(_require(entry, "prompt_target", where))
    if prompt_target not in PROMPT_TARGETS:
        raise EngineConfigError(
            f"{where}: prompt_target {prompt_target!r} is not a tools/prompting "
            f"target {list(PROMPT_TARGETS)}")

    prompt_variant = str(_require(entry, "prompt_variant", where)).upper()
    if prompt_variant not in {"A", "B", "C"}:
        raise EngineConfigError(
            f"{where}: prompt_variant {prompt_variant!r} is not A/B/C")

    steps = int(_require(entry, "steps", where))
    if steps <= 0:
        raise EngineConfigError(f"{where}: steps must be > 0")

    scheduler = entry.get("scheduler") or {}
    if not isinstance(scheduler, dict):
        raise EngineConfigError(f"{where}: scheduler must be an object")

    guidance = entry.get("guidance")
    if guidance is not None:
        guidance = float(guidance)

    return ModelAdapter(
        key=key,
        status=status,
        display_name=str(entry.get("display_name") or key),
        model_id=str(_require(entry, "model_id", where)),
        pipeline_class=str(_require(entry, "pipeline_class", where)),
        pipeline_candidates=tuple(
            entry.get("pipeline_candidates") or
            [str(_require(entry, "pipeline_class", where))]),
        prompt_target=prompt_target,
        prompt_variant=prompt_variant,
        prompt_rules=dict(prompt_rules),
        steps=steps,
        guidance=guidance,
        scheduler=dict(scheduler),
        dtype=str(entry.get("dtype") or "float16"),
        vae_model_id=entry.get("vae_model_id"),
        unet_checkpoint=entry.get("unet_checkpoint"),
        cpu_offload=bool(entry.get("cpu_offload")),
        low_cpu_mem_usage=(None if entry.get("low_cpu_mem_usage") is None
                           else bool(entry["low_cpu_mem_usage"])),
        extra_kwargs=dict(entry.get("extra_kwargs") or {}),
        install_ladder=tuple(entry.get("install_ladder") or ()),
        versions=dict(versions),
        measured=dict(measured),
        license=dict(entry.get("license") or {}),
        notes=str(entry.get("notes") or ""),
    )


def load_engine(path: str | Path = DEFAULT_CONFIG_PATH) -> ImageEngine:
    """Load the image engine config. Raises EngineConfigError (fail-closed)."""
    p = Path(path)
    if not p.is_file():
        raise EngineConfigError(f"image engine config not found: {p}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise EngineConfigError(f"image engine config is not readable JSON: {exc}")
    if not isinstance(doc, dict):
        raise EngineConfigError("image engine config must be a JSON object")

    for field_name in LOCK_FIELDS:
        if field_name not in doc:
            raise EngineConfigError(
                f"lock field {field_name!r} is missing from {p}")

    raw_models = doc.get("models")
    if not isinstance(raw_models, dict) or not raw_models:
        raise EngineConfigError("config has no 'models' registry")

    models = {key: _build_adapter(key, entry)
              for key, entry in raw_models.items()}

    model_key = str(doc["model"])
    if model_key not in models:
        raise EngineConfigError(
            f"active model {model_key!r} is not a registered model entry")
    active = models[model_key]
    if active.status not in ACTIVE_STATUSES:
        raise EngineConfigError(
            f"active model {model_key!r} has status {active.status!r}; "
            f"only {list(ACTIVE_STATUSES)} may be locked")

    guidance = doc["guidance"]
    if guidance is not None:
        guidance = float(guidance)

    return ImageEngine(
        model=model_key,
        scheduler=dict(doc["scheduler"] or {}),
        steps=int(doc["steps"]),
        guidance=guidance,
        dtype=str(doc["dtype"]),
        seed_policy=dict(doc["seed_policy"] or {}),
        prompt_variant=str(doc["prompt_variant"]).upper(),
        status=str(doc["status"]),
        fallback=dict(doc["fallback"]) if doc.get("fallback") else None,
        selection=dict(doc.get("selection") or {}),
        models=models,
        path=str(p),
        raw=doc,
    )


def adapter_for(engine: ImageEngine, key: str) -> ModelAdapter:
    try:
        return engine.models[key]
    except KeyError:
        raise EngineConfigError(
            f"unknown model {key!r}; registered: {sorted(engine.models)}")


def active_adapter(engine: ImageEngine) -> ModelAdapter:
    return adapter_for(engine, engine.model)


# ------------------------------------------------------------- projections
def project_gpu_minutes(adapter: ModelAdapter, count: int) -> Dict[str, Any]:
    """Projected GPU minutes for `count` images, from the measured speed.

    Fails closed: a model without usable measured images cannot be projected.
    """
    if count <= 0:
        raise EngineConfigError("count must be > 0")
    if not adapter.usable or adapter.sec_per_image is None:
        raise EngineConfigError(
            f"model {adapter.key!r} has no usable measured images "
            f"(images_usable={adapter.measured.get('images_usable')}); "
            "no timing projection can be claimed")
    per = adapter.sec_per_image
    render_seconds = per * count
    total_seconds = render_seconds + adapter.load_seconds
    return {
        "model": adapter.key,
        "images": count,
        "sec_per_image": per,
        "render_seconds": round(render_seconds, 1),
        "render_minutes": round(render_seconds / 60.0, 2),
        "load_seconds": round(adapter.load_seconds, 1),
        "total_seconds": round(total_seconds, 1),
        "total_minutes": round(total_seconds / 60.0, 2),
        "usable_images_per_minute": adapter.measured.get("usable_images_per_minute"),
        "peak_vram_mb": adapter.measured.get("peak_vram_mb"),
        "measured_job": adapter.measured.get("job_id"),
    }


# ------------------------------------------------------------ owner decision
def _load_tally_module(repo_root: Path | None = None):
    """Import scripts/s7_tally.py without importing it as a package.

    The tally script is part of THIS repository (code), so it is always read
    from the repo the agent runs in. Only the owner's CSVs and mappings are
    read from `repo_root` (the pack the owner filled).
    """
    path = (Path(repo_root) if repo_root else REPO) / "scripts" / "s7_tally.py"
    if not path.is_file():
        path = REPO / "scripts" / "s7_tally.py"
    if not path.is_file():
        raise EngineConfigError(f"tally script not found: {path}")
    spec = importlib.util.spec_from_file_location("om_s7_tally", path)
    if spec is None or spec.loader is None:
        raise EngineConfigError(f"cannot load the tally script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _csv_is_filled(path: Path, tally) -> bool:
    """True when every scene row carries a best_panel."""
    try:
        results = tally.load_results(path)
    except (ValueError, OSError):
        return False
    if not results:
        return False
    return all(row.get("best") for row in results)


def owner_decision(repo_root: str | Path = REPO,
                   advisory: str | None = None,
                   config_path: str | Path | None = None) -> Dict[str, Any]:
    """Decide the locked model from the owner's blind scores, if they exist.

    * a filled owner CSV -> the owner's winner, status OWNER_CONFIRMED,
    * no filled CSV        -> the agent advisory pick, status OWNER_GATED,
    * a tie or a partial CSV -> no winner, status stays OWNER_GATED.
    """
    root = Path(repo_root)
    tally = _load_tally_module(REPO)

    if advisory is None:
        try:
            advisory = (load_engine(config_path or DEFAULT_CONFIG_PATH)
                        .selection.get("decision"))
        except EngineConfigError:
            advisory = None

    for pack in ("s8_blind", "s7_blind"):
        csv_path = root / "projects" / pack / "results.csv"
        mapping_path = root / "projects" / pack / "mapping.json"
        if not csv_path.is_file() or not mapping_path.is_file():
            continue
        if not _csv_is_filled(csv_path, tally):
            continue
        try:
            mapping = tally.load_mapping(mapping_path)
            results = tally.load_results(csv_path)
        except (ValueError, OSError) as exc:
            raise EngineConfigError(f"owner CSV {csv_path} is not readable: {exc}")
        stats = tally.tally(results, mapping)
        scenes = len(mapping["panels_by_scene"])
        winner, second, gap = tally._owner_winner(stats, scenes)
        if winner is None:
            return {
                "status": "OWNER_GATED",
                "model": advisory,
                "basis": f"owner CSV {pack}/results.csv produced a TIE "
                         f"({second} is within {gap} win) - no owner winner, "
                         "the advisory pick stays in place",
                "owner_result": {"winner": None, "tie": True, "stats": stats,
                                 "wins": 0},
                "pack": pack,
            }
        return {
            "status": "OWNER_CONFIRMED",
            "model": winner,
            "basis": f"owner CSV {pack}/results.csv: {winner} won "
                     f"{stats[winner]['wins']}/{scenes} scenes",
            "owner_result": {"winner": winner, "tie": False, "stats": stats,
                             "wins": stats[winner]["wins"], "scenes": scenes},
            "pack": pack,
        }

    return {
        "status": "OWNER_GATED",
        "model": advisory,
        "basis": "agent advisory pick only - the owner's blind CSV is not filled",
        "owner_result": None,
        "pack": None,
    }


# ------------------------------------------------------------- generators
class Generator(Protocol):
    """Anything that can turn a job payload into a fetched output tree."""

    def generate(self, job: Dict[str, Any], adapter: ModelAdapter,
                 out_dir: str | Path) -> Path:  # pragma: no cover - protocol
        ...


class FakeGenerator:
    """Offline stand-in for the Kaggle kernel.

    Writes the same tree shape the kernel writes (manifest.json + images/),
    so the fetch verification, the label burn and the image QC can be
    exercised without a GPU, a network or a Kaggle job.
    """

    def __init__(self, width: int | None = None, height: int | None = None):
        self.width = width
        self.height = height

    def generate(self, job: Dict[str, Any], adapter: ModelAdapter,
                 out_dir: str | Path) -> Path:
        from PIL import Image, ImageDraw

        root = Path(out_dir)
        images_dir = root / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        width = int(self.width or job.get("width") or 320)
        height = int(self.height or job.get("height") or 180)

        entries: List[Dict[str, Any]] = []
        for render in job["renders"]:
            name = f"{render['render_id']}.png"
            path = images_dir / name
            seed = int(render.get("seed") or 0)
            img = Image.new("RGB", (width, height), (20, 69, 92))
            draw = ImageDraw.Draw(img)
            for i in range(0, width, 4):
                shade = (seed * 37 + i * 13) % 255
                draw.line([(i, 0), (i, height)],
                          fill=(shade, (shade * 3) % 255, (shade * 7) % 255))
            img.save(path)
            data = path.read_bytes()
            entries.append({
                "render_id": render["render_id"],
                "scene_id": render.get("scene_id"),
                "variant": render.get("variant"),
                "file": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "width": width,
                "height": height,
                "seed": render.get("seed"),
                "steps": render.get("steps"),
                "guidance_scale": render.get("guidance_scale"),
                "prompt": render.get("prompt"),
                "black": False,
                "nonfinite": False,
            })

        manifest = {
            "job_id": job["job_id"],
            "model": adapter.key,
            "model_id": adapter.model_id,
            "pipeline_class": adapter.pipeline_class,
            "dtype": adapter.dtype,
            "cpu_fallback": False,
            "cpu_offload_used": adapter.cpu_offload,
            "width": width,
            "height": height,
            "requested": len(job["renders"]),
            "generated": len(entries),
            "load_seconds": adapter.load_seconds,
            "steady_state_sec_per_image": adapter.sec_per_image,
            "usable_images_per_minute": adapter.measured.get("usable_images_per_minute"),
            "peak_vram_mb": adapter.measured.get("peak_vram_mb"),
            "black_count": 0,
            "nan_count": 0,
            "oom_count": 0,
            "load_notes": {"source": "fake generator (no GPU, no Kaggle)"},
            "versions": dict(adapter.versions),
            "images": entries,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        return root
