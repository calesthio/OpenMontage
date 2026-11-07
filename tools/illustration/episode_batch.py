#!/usr/bin/env python3
"""tools/illustration/episode_batch.py — episode-scale illustration engine (L4).

Pure planning/verification code (no network, no Kaggle call):

  specs (creature/scene YAML)  ->  per-model prompt plan
  plan                         ->  ONE kernel job per model (batched)
  fetched output               ->  manifest verification (job_id, sha256, bytes)
  verified images              ->  Illustration label + image QC + local manifest

The Kaggle submission itself lives in `scripts/run_illustrations.py`, because
the agent must control when a status call happens (never poll in a loop).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from PIL import Image

from tools.illustration.illustration_qc import qc_batch
from tools.illustration.model_registry import (
    DEFAULT_CONFIG_PATH,
    EngineConfigError,
    ImageEngine,
    ModelAdapter,
    adapter_for,
    load_engine,
    project_gpu_minutes,
)
from tools.prompting.builder import AnatomySpec, CreatureSpec, PromptBuilder

# The image model is CONFIG, not code: config/image_engine.json holds one
# entry per model (verified versions, prompt rules, measured seconds/image).
# The three legacy tables below are derived from that registry on demand
# (PEP 562 __getattr__), so there is a single source of truth.
_ENGINE_CACHE: Dict[str, ImageEngine] = {}


def get_engine(path: str | Path | None = None) -> ImageEngine:
    """Load (and cache) the image engine config."""
    key = str(path or DEFAULT_CONFIG_PATH)
    if key not in _ENGINE_CACHE:
        _ENGINE_CACHE[key] = load_engine(key)
    return _ENGINE_CACHE[key]


def resolve_adapter(model: str, engine: ImageEngine | None = None) -> ModelAdapter:
    """The adapter for `model`. Unknown models raise ValueError (as before)."""
    try:
        return adapter_for(engine or get_engine(), model)
    except EngineConfigError as exc:
        raise ValueError(str(exc)) from exc


def _legacy_maps() -> Dict[str, Any]:
    engine = get_engine()
    return {
        "MEASURED_SEC_PER_IMAGE": {
            key: (adapter.sec_per_image if adapter.usable else None)
            for key, adapter in engine.models.items()
        },
        "MODEL_IDS": {
            key: {"model_id": a.model_id, "pipeline_class": a.pipeline_class,
                  "vae_model_id": a.vae_model_id}
            for key, a in engine.models.items()
        },
        "DEFAULT_INSTALL_LADDER": {
            key: list(a.install_ladder) for key, a in engine.models.items()
        },
    }


def __getattr__(name: str) -> Any:
    # PEP 562: the legacy tables stay importable but come from the config.
    if name in {"MEASURED_SEC_PER_IMAGE", "MODEL_IDS", "DEFAULT_INSTALL_LADDER"}:
        return _legacy_maps()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

IMAGE_LABEL = "Illustration"
SPECULATIVE_LABEL = "Speculative illustration"

# Field-guide plate defaults, mirrored from the niche manifest
# (docs/openmontage/niches/speculative_evolution/speculative_evolution.yaml).
# The niche YAML is the source of truth; these are the fallback so a spec
# directory still plans without its parent manifest.
NICHE_DEFAULTS = {
    "style": (
        "flat vector illustration, field-guide plate, silhouette-first, "
        "minimal detail, clean geometric lines, not photorealistic"
    ),
    "palette": {
        "deep teal": "#14455C",
        "bioluminescent lime": "#A8E06F",
        "basalt charcoal": "#3B444B",
        "pale bone": "#EDE7D8",
    },
    "light": "flat even lighting, no gradients, no photographic depth",
    "camera": "wide 16:9 plate, centered subject with copy space",
}


class BudgetError(RuntimeError):
    """The requested image count violates the per-episode budget."""


@dataclass
class Spec:
    name: str
    creature: CreatureSpec
    raw: Dict[str, Any]


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _feature_names(value: Any) -> List[str]:
    """`dominant_features` is a list of mappings in the niche specs."""
    out: List[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                out.append(name)
        elif str(item).strip():
            out.append(str(item).strip())
    return out


def adapt_niche_spec(data: Dict[str, Any], niche: Dict[str, Any] | None = None) -> CreatureSpec:
    """Map a niche creature/habitat YAML onto the prompt builder's contract.

    Niche specs describe `name` + `role` + `canonical_silhouette` (not the
    builder's `subject`/`environment`/`style`); this adapter keeps the fixed
    silhouette in the prompt so one creature stays recognisable shot to shot.
    """
    niche = niche or {}
    anatomy_raw = data.get("anatomy") or {}
    name = str(data.get("name", "")).strip()
    role = str(data.get("role", "")).strip()
    subject = f"{name} — {role}" if role else name

    environment = data.get("environment")
    if isinstance(environment, (list, tuple)):
        environment = "; ".join(str(e) for e in environment)
    environment = str(environment or data.get("pilot") or "").strip()

    features = _feature_names(anatomy_raw.get("dominant_features") if anatomy_raw else None)
    silhouette = str(data.get("canonical_silhouette", "")).strip()
    if silhouette:
        features = features + [f"silhouette: {silhouette}"]

    palette = {str(k).replace("_", " "): str(v)
               for k, v in (niche.get("palette") or NICHE_DEFAULTS["palette"]).items()}

    style = NICHE_DEFAULTS["style"]
    if niche.get("style"):
        style = f"{NICHE_DEFAULTS['style']}, {niche['style']}".replace("_", " ")

    return CreatureSpec(
        subject=subject,
        anatomy=AnatomySpec(
            limb_count=int(anatomy_raw.get("limb_count", 0) or 0),
            eye_count=int(anatomy_raw.get("eye_count", 0) or 0),
            horn_count=int(anatomy_raw.get("horn_count", 0) or 0),
            dominant_features=features,
        ),
        environment=environment,
        light=str(data.get("light") or NICHE_DEFAULTS["light"]),
        style=style,
        palette=palette,
        camera=str(data.get("camera") or NICHE_DEFAULTS["camera"]),
        constraints={"no_text": True, "no_people": True, "no_logos": True,
                     "not_photorealistic": True},
    )


def _load_niche_manifest(spec_dir: Path) -> Dict[str, Any]:
    """The niche manifest sits next to the creatures/scenes directory."""
    import yaml

    for candidate in (spec_dir.parent / f"{spec_dir.parent.name}.yaml",
                      spec_dir.parent / "niche.yaml"):
        if candidate.is_file():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    return {}


def load_specs(spec_dir: str | Path) -> List[Spec]:
    """Load every *.yaml creature/scene spec in a directory (sorted by name).

    Specs are niche YAMLs (`name`, `role`, `anatomy`, `canonical_silhouette`),
    adapted to the prompt builder's CreatureSpec via `adapt_niche_spec`.
    """
    import yaml

    root = Path(spec_dir)
    niche = _load_niche_manifest(root)
    out: List[Spec] = []
    for path in sorted(root.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: spec must be a mapping")
        out.append(Spec(path.stem, adapt_niche_spec(data, niche), data))
    if not out:
        raise ValueError(f"no YAML specs in {spec_dir}")
    return out


def images_for_minutes(minutes: float, per_minute: float = 8.0) -> int:
    """Per-episode image budget: `per_minute` illustrations per finished minute."""
    if minutes <= 0:
        raise ValueError("minutes must be > 0")
    if per_minute <= 0:
        raise ValueError("per_minute must be > 0")
    return int(round(minutes * per_minute))


def check_budget(count: int, cap: int = 120) -> None:
    if count <= 0:
        raise BudgetError("image plan is empty")
    if count > cap:
        raise BudgetError(f"{count} images exceeds the per-episode cap {cap}")


def plan_renders(
    specs: Sequence[Spec],
    model: str,
    *,
    per_spec: int = 1,
    seed_base: int = 7000,
    variants: Iterable[str] | None = None,
    engine: ImageEngine | None = None,
) -> List[Dict[str, Any]]:
    """Build the batched render plan for ONE model.

    The model entry in config/image_engine.json decides the prompt target
    (tools/prompting), the prompt variant, the steps and the guidance, so the
    plan follows the config lock instead of a code-side table.
    """
    adapter = resolve_adapter(model, engine)
    variant_list = [v.upper() for v in
                    (variants if variants is not None else [adapter.prompt_variant])]
    if not variant_list:
        raise ValueError("at least one variant is required")
    renders: List[Dict[str, Any]] = []
    i = 0
    for spec in specs:
        for rep in range(per_spec):
            variant = variant_list[rep % len(variant_list)]
            seed = seed_base + i
            built = PromptBuilder(seed=seed).build(
                adapter.prompt_target, variant, spec.creature)
            renders.append({
                "render_id": f"r{len(renders) + 1:04d}",
                "scene_id": spec.name,
                "variant": variant,
                "prompt": built["prompt"],
                "negative_prompt": built.get("negative_prompt"),
                "guidance_scale": adapter.guidance,
                "steps": adapter.steps,
                "seed": seed,
                "prompt_sha256": hashlib.sha256(
                    f"{model}|{built['prompt']}|{seed}".encode("utf-8")
                ).hexdigest(),
            })
            i += 1
    return renders


def build_job(
    episode_id: str,
    model: str,
    renders: List[Dict[str, Any]],
    *,
    width: int = 1344,
    height: int = 768,
    ladder: Sequence[str] | None = None,
    max_wall_seconds: int = 5400,
    attempt: int = 1,
    engine: ImageEngine | None = None,
) -> Dict[str, Any]:
    adapter = resolve_adapter(model, engine)
    job_ladder = list(ladder or adapter.install_ladder)
    return {
        "job_id": f"ill-{episode_id}-{model}-{attempt}",
        "episode_id": episode_id,
        "model": adapter.key,
        "model_id": adapter.model_id,
        "pipeline_class": adapter.pipeline_class,
        "vae_model_id": adapter.vae_model_id,
        "unet_checkpoint": adapter.unet_checkpoint,
        "revision": "main",
        "dtype": adapter.dtype,
        "width": width,
        "height": height,
        "output_dir": f"illustrations_{episode_id}_{model}",
        "install_ladder": job_ladder,
        "load_config": adapter.load_config(),
        "model_config": adapter.job_model_config(),
        "max_wall_seconds": max_wall_seconds,
        "attempt": attempt,
        "changed_from_previous": (
            f"attempt {attempt}: batched episode plan "
            f"{len(renders)} renders, ladder {job_ladder}"
        ),
        "renders": renders,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def estimate_wall_seconds(model: str, count: int,
                           engine: ImageEngine | None = None) -> float | None:
    """Measured seconds/image x count + ~150 s model load. None if unmeasured."""
    adapter = resolve_adapter(model, engine)
    per = adapter.sec_per_image if adapter.usable else None
    if per is None:
        return None
    return round(per * count + 150.0, 1)


def project_images(adapter: ModelAdapter, count: int) -> Dict[str, Any]:
    """Projected GPU minutes for `count` images (fail-closed)."""
    return project_gpu_minutes(adapter, count)


def cache_index(cache_dir: str | Path) -> Dict[str, str]:
    """Map prompt_sha256 -> local image path for already-approved images."""
    index: Dict[str, str] = {}
    root = Path(cache_dir)
    manifest = root / "illustration_manifest.json"
    if not manifest.is_file():
        return index
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return index
    for ent in data.get("images", []):
        key = ent.get("prompt_sha256")
        path = root / str(ent.get("file", ""))
        if key and path.is_file():
            index[key] = str(path)
    return index


def split_cached(renders: List[Dict[str, Any]], cache_dir: str | Path):
    """Return (to_generate, reused) using prompt_sha256 + model + seed."""
    index = cache_index(cache_dir)
    todo, reused = [], []
    for r in renders:
        hit = index.get(r["prompt_sha256"])
        (reused if hit else todo).append({**r, "cached_path": hit} if hit else r)
    return todo, reused


def verify_fetched(fetched_dir: str | Path, job: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a fetched kernel output against the plan (fail-closed).

    Rejects: missing manifest, job_id mismatch, missing render, sha256/bytes
    mismatch, black frames, and fewer images than requested.
    """
    root = Path(fetched_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        matches = list(root.rglob("manifest.json"))
        if not matches:
            return {"ok": False, "error": f"manifest.json not found under {root}"}
        manifest_path = matches[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("job_id") != job["job_id"]:
        return {"ok": False, "error": f"job_id mismatch: {manifest.get('job_id')!r} != {job['job_id']!r}"}
    images = {i.get("render_id"): i for i in manifest.get("images", [])}
    problems: List[str] = []
    for r in job["renders"]:
        ent = images.get(r["render_id"])
        if not ent or not ent.get("file"):
            problems.append(f"{r['render_id']}: missing image")
            continue
        if ent.get("sha256") != r.get("expected_sha256") and r.get("expected_sha256"):
            problems.append(f"{r['render_id']}: sha256 != plan")
        if ent.get("black"):
            problems.append(f"{r['render_id']}: black frame")
        fpath = manifest_path.parent / "images" / ent["file"]
        if not fpath.is_file():
            fpath = manifest_path.parent / ent["file"]
        if not fpath.is_file():
            problems.append(f"{r['render_id']}: file not fetched")
            continue
        data = fpath.read_bytes()
        if hashlib.sha256(data).hexdigest() != ent.get("sha256"):
            problems.append(f"{r['render_id']}: fetched sha256 mismatch")
        if ent.get("bytes") is not None and len(data) != ent["bytes"]:
            problems.append(f"{r['render_id']}: fetched byte count mismatch")
    if manifest.get("generated") != len(job["renders"]):
        problems.append(f"generated {manifest.get('generated')} != requested {len(job['renders'])}")
    return {"ok": not problems, "error": "; ".join(problems)[:500] if problems else None,
            "manifest": manifest, "manifest_path": str(manifest_path)}


def label_and_qc(
    fetched_dir: str | Path,
    job: Dict[str, Any],
    out_dir: str | Path,
    *,
    speculative: bool = False,
) -> Dict[str, Any]:
    """Copy verified images into out_dir, burn the label, run image QC."""
    from tools.illustration.illustration_batch import apply_illustration_label

    root = Path(fetched_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        found = list(root.rglob("manifest.json"))
        if not found:
            raise FileNotFoundError("manifest.json not found")
        manifest_path = found[0]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    label = SPECULATIVE_LABEL if speculative else IMAGE_LABEL
    by_id = {i.get("render_id"): i for i in json.loads(
        manifest_path.read_text(encoding="utf-8")).get("images", [])}
    entries = []
    for r in job["renders"]:
        ent = by_id.get(r["render_id"])
        if not ent or not ent.get("file"):
            continue
        src = manifest_path.parent / "images" / ent["file"]
        if not src.is_file():
            src = manifest_path.parent / ent["file"]
        dst = out / f"{r['scene_id']}_{r['render_id']}.png"
        apply_illustration_label(src, dst, text=label)
        entries.append({
            "render_id": r["render_id"],
            "scene_id": r["scene_id"],
            "file": dst.name,
            "prompt": r["prompt"],
            "prompt_sha256": r["prompt_sha256"],
            "seed": r["seed"],
            "model": job["model"],
            "generator": "AI",
            "label": label,
            "rights_basis": "ai_generated_illustration",
            "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
        })
    qc = qc_batch([str(out / e["file"]) for e in entries],
                  int(job.get("width", 1344)), int(job.get("height", 768)))
    for e, q in zip(entries, qc.get("results", [])):
        e["qc"] = q
    manifest = {
        "job_id": job["job_id"],
        "episode_id": job.get("episode_id", ""),
        "model": job["model"],
        "generator": "AI",
        "rights_basis": "ai_generated_illustration",
        "label": label,
        "images": entries,
        "qc": {k: v for k, v in qc.items() if k != "results"},
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "illustration_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
