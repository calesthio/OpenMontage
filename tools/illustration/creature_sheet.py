#!/usr/bin/env python3
"""tools/illustration/creature_sheet.py - the canonical creature sheet kit.

The consistency kit turns OpenCode's YAML creature specs (READ ONLY) into a
canonical sheet per creature: the same creature in the **front**, **side** and
**three-quarter** view, with the anatomy counts and the canonical silhouette
written into every prompt, one fixed seed per creature+view, and (when the
locked model's official card documents it) the other views generated from the
front view as a reference image.

    style    = load_style("speculative_evolution")
    adapter  = active_adapter(load_engine())
    sheet    = build_creature_sheet(creature, style, adapter)
    job      = build_sheet_job("speculative_evolution", creature, sheet, adapter)

The job file is deterministic: the same spec + style + model produce a
byte-identical file (no timestamps inside).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tools.illustration.model_registry import ModelAdapter
from tools.illustration.style_kit import (
    CANONICAL_VIEWS,
    StyleSpec,
    constraint_fragments,
    load_style,
    reference_policy,
    style_digest,
)
from tools.prompting.builder import AnatomySpec, CreatureSpec, PromptBuilder

try:  # pragma: no cover - yaml is a hard dependency of the builder
    import yaml
except Exception:  # pragma: no cover
    yaml = None

REPO = Path(__file__).resolve().parents[2]


def _slug(value: str) -> str:
    """A file-name safe slug (creature names contain spaces)."""
    out = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return out.strip("_") or "item"


# ------------------------------------------------------------------ inputs
def load_creature_specs(spec_dir: str | Path) -> List[Dict[str, Any]]:
    """Load the OpenCode creature/habitat YAML specs (read only)."""
    if yaml is None:
        raise RuntimeError("PyYAML is required to load the creature specs")
    directory = Path(spec_dir)
    if not directory.is_dir():
        raise ValueError(f"creature spec directory not found: {directory}")
    out: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("name"):
            raise ValueError(f"{path}: not a creature spec mapping")
        data["_source"] = str(path)
        out.append(data)
    if not out:
        raise ValueError(f"no creature specs in {directory}")
    return out


def _first_clause(text: str, limit: int = 110) -> str:
    """The first clause of a sentence-like field, capped in length.

    The prompt builder repeats the anatomy phrase twice (variant C), so the
    long canonical silhouette is trimmed to its first clause. The full text
    stays in the YAML spec (the source of truth); the anatomy COUNTS are
    always written out separately, so nothing about the anatomy is lost.
    """
    for clause in str(text).split(";"):
        if clause.strip():
            trimmed = clause.strip()
            if len(trimmed) > limit:
                trimmed = trimmed[:limit].rsplit(" ", 1)[0] + " ..."
            return trimmed
    return str(text).strip()


def _style_phrase(style: StyleSpec, adapter: ModelAdapter | None = None) -> str:
    """The style phrase: the line style plus the injected positive constraints."""
    frags = constraint_fragments(style, adapter)
    parts = [style.style_phrase] + frags["positive"]
    return ", ".join(p for p in parts if p)


def creature_spec_from_yaml(data: Dict[str, Any], style: StyleSpec,
                            adapter: ModelAdapter | None = None) -> CreatureSpec:
    """Map one YAML spec onto the read-only prompt-builder contract."""
    anatomy = data.get("anatomy") or {}
    features: List[str] = []
    for feature in anatomy.get("dominant_features") or []:
        name = feature.get("name") if isinstance(feature, dict) else str(feature)
        if name:
            features.append(str(name))
    silhouette = str(data.get("canonical_silhouette") or "").strip()
    if silhouette:
        features.append(f"silhouette: {_first_clause(silhouette)}")

    role = str(data.get("role") or "").strip()
    environment_list = [str(e) for e in (data.get("environment") or [])]
    if environment_list:
        environment = "; ".join(environment_list)
    elif role:
        environment = f"as a {role}"
    else:
        environment = "in its habitat"

    subject = str(data["name"])
    if role:
        subject = f"{subject} - {role}"

    return CreatureSpec(
        subject=subject,
        anatomy=AnatomySpec(
            limb_count=int(anatomy.get("limb_count", 0)),
            eye_count=int(anatomy.get("eye_count", 0)),
            horn_count=int(anatomy.get("horn_count", 0)),
            dominant_features=features,
        ),
        environment=environment,
        light=style.light,
        style=_style_phrase(style, adapter),
        palette=dict(style.palette),
        camera="",
        constraints={"no_text": True, "not_photoreal": True,
                     "no_people": True, "no_logos": True},
    )


# ------------------------------------------------------------------- seeds
def _creature_dir(style: StyleSpec) -> Path:
    raw = str(style.provenance.get("creature_specs") or "")
    if "*" in raw:
        return (REPO / raw).parent
    return (REPO / "docs/openmontage/niches" / style.niche_id / "creatures")


def _seed_for(style: StyleSpec, creature_name: str, view_index: int,
              views: Sequence[str]) -> int:
    """One fixed seed per creature+view, inside the reserved range."""
    base = int(style.seed_policy.get("base", 3000))
    try:
        names = sorted(c["name"] for c in load_creature_specs(_creature_dir(style)))
        index = names.index(creature_name)
    except (ValueError, OSError):
        index = 0
    seed = base + index * len(views) + view_index
    low, high = style.seed_policy.get("range", [3000, 3999])
    if not (int(low) <= seed <= int(high)):
        raise ValueError(
            f"seed {seed} for {creature_name}/{views[view_index]} is outside "
            f"the reserved range {low}-{high}")
    return seed


# ------------------------------------------------------------------- sheet
def build_creature_sheet(creature: Dict[str, Any], style: StyleSpec,
                          adapter: ModelAdapter,
                          views: Sequence[str] = CANONICAL_VIEWS,
                          ) -> List[Dict[str, Any]]:
    """The canonical sheet of one creature (front, side, three-quarter)."""
    views = list(views)
    frags = constraint_fragments(style, adapter)
    spec = creature_spec_from_yaml(creature, style, adapter)
    renders: List[Dict[str, Any]] = []
    for index, view in enumerate(views):
        camera = style.camera_vocabulary.get(view)
        if not camera:
            raise ValueError(
                f"{style.niche_id}: the style has no camera vocabulary for "
                f"the {view!r} view")
        spec.camera = camera
        seed = _seed_for(style, str(creature["name"]), index, views)
        built = PromptBuilder(seed=seed).build(
            adapter.prompt_target, adapter.prompt_variant, spec)
        negative = built.get("negative_prompt")
        if negative and frags["negative"]:
            negative = negative + ", " + ", ".join(frags["negative"])
        renders.append({
            "render_id": f"r{index + 1:04d}",
            "scene_id": str(creature["name"]),
            "view": view,
            "variant": adapter.prompt_variant,
            "prompt": built["prompt"],
            "negative_prompt": negative,
            "guidance_scale": adapter.guidance,
            "steps": adapter.steps,
            "seed": seed,
            "prompt_sha256": hashlib.sha256(
                f"{adapter.key}|{built['prompt']}|{seed}".encode("utf-8")
            ).hexdigest(),
        })
    return renders


def build_sheet_job(niche_id: str, creature: Dict[str, Any],
                    renders: List[Dict[str, Any]], adapter: ModelAdapter,
                    *, width: int = 1024, height: int = 1024,
                    max_wall_seconds: int = 900,
                    ) -> Dict[str, Any]:
    """The deterministic job file for one creature sheet."""
    style = load_style(niche_id)
    policy = reference_policy(adapter.key)
    job_renders = [dict(r) for r in renders]
    if policy.get("supported") and job_renders:
        front = job_renders[0]["render_id"]
        front_scene = job_renders[0].get("scene_id")
        for render in job_renders[1:]:
            # only the SAME creature reuses the canonical front view
            if render.get("scene_id") == front_scene:
                render["reference_render_id"] = front

    return {
        "job_id": f"sheet-{niche_id}-{_slug(creature['name'])}-{adapter.key}-1",
        "job_kind": "canonical_creature_sheet",
        "niche_id": niche_id,
        "creature": str(creature["name"]),
        "model": adapter.key,
        "model_id": adapter.model_id,
        "pipeline_class": adapter.pipeline_class,
        "vae_model_id": adapter.vae_model_id,
        "unet_checkpoint": adapter.unet_checkpoint,
        "revision": "main",
        "dtype": adapter.dtype,
        "width": width,
        "height": height,
        "output_dir": f"sheet_{niche_id}_{_slug(creature['name'])}",
        "install_ladder": list(adapter.install_ladder),
        "load_config": adapter.load_config(),
        "model_config": adapter.job_model_config(),
        "max_wall_seconds": max_wall_seconds,
        "attempt": 1,
        "changed_from_previous": (
            "canonical sheet: front, side, three-quarter view of one creature"),
        "style": {
            "niche_id": style.niche_id,
            "style_name": style.style_name,
            "path": style.path,
            "sha256": style_digest(style),
            "label": style.label_rule.get("label"),
            "speculative": style.label_rule.get("label") == "Speculative illustration",
        },
        "seed_policy": dict(style.seed_policy),
        "reference_policy": policy,
        "views": list(CANONICAL_VIEWS),
        "renders": job_renders,
    }


def build_sheet_plan(niche_id: str, adapter: ModelAdapter,
                     spec_dir: str | Path | None = None,
                     creature: str | None = None,
                     ) -> Dict[str, Any]:
    """The plan for every creature of a niche (or one named creature)."""
    style = load_style(niche_id)
    directory = Path(spec_dir) if spec_dir else _creature_dir(style)
    specs = load_creature_specs(directory)
    if creature:
        specs = [s for s in specs if s["name"] == creature]
        if not specs:
            raise ValueError(f"unknown creature {creature!r} in {directory}")
    entries = []
    for data in specs:
        renders = build_creature_sheet(data, style, adapter)
        entries.append({
            "name": str(data["name"]),
            "type": str(data.get("type") or "species"),
            "source": str(data.get("_source") or ""),
            "renders": renders,
        })
    return {
        "niche_id": niche_id,
        "style": {
            "niche_id": style.niche_id,
            "style_name": style.style_name,
            "path": style.path,
            "sha256": style_digest(style),
            "label": style.label_rule.get("label"),
        },
        "model": adapter.key,
        "views": list(CANONICAL_VIEWS),
        "creatures": entries,
    }


def sheet_prompt_check(render: Dict[str, Any]) -> bool:
    """True when the render's prompt carries the anatomy counts."""
    prompt = str(render.get("prompt") or "")
    return "limbs," in prompt and "eyes," in prompt and "horns" in prompt
