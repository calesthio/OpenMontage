#!/usr/bin/env python3
"""tools/illustration/style_kit.py - the machine-readable niche style.

Each niche profile has a `style.json` next to its STYLE_BIBLE.md:

  docs/openmontage/niches/<niche>/style.json

It carries the palette, the line style, the camera vocabulary, the style
constraints (with a POSITIVE and a NEGATIVE form), the label rule, the
anatomy rule and the seed policy.

Constraint forms: the locked model (klein) has no negative prompt, so every
constraint is written POSITIVELY into the prompt. A model that does accept a
negative prompt (the SDXL family) gets the negative forms in its negative
prompt instead.

Reference-image (img2img) support is only declared for a model whose official
card documents it, with the citation. Everything else falls back to
seed + prompt anchoring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
NICHE_ROOT = REPO / "docs/openmontage" / "niches"

#: Every niche with a finalized style.
NICHES: Tuple[str, ...] = (
    "art_history",
    "space_iss",
    "speculative_science",
    "speculative_evolution",
)

#: Prompt targets that accept a negative prompt (tools/prompting/builder.py).
NEGATIVE_PROMPT_TARGETS: Tuple[str, ...] = ("sdxl",)

#: Views every canonical creature sheet must contain.
CANONICAL_VIEWS: Tuple[str, ...] = ("front", "side", "three_quarter")

REQUIRED_KEYS: Tuple[str, ...] = (
    "schema_version", "niche_id", "style_name", "palette", "line_style",
    "light", "camera_vocabulary", "constraints", "label_rule",
    "anatomy_rule", "seed_policy", "aspect", "provenance",
)

#: Official-card evidence for the reference-image (img2img) workflow.
#: A model may only use the reference workflow when this table says so.
REFERENCE_IMAGE_SUPPORT: Dict[str, Dict[str, Any]] = {
    "klein": {
        "supported": True,
        "capability": "text-to-image and image-to-image multi-reference editing in one model",
        "card": "https://huggingface.co/black-forest-labs/FLUX.2-klein-4B",
        "accessed": "2026-10-22",
        "evidence": ("card, key features: \"Text-to-image and image-to-image "
                     "multi-reference editing in a single unified model\"; "
                     "Diffusers snippet: pipe(image=input_image, prompt=prompt)"),
    },
    "sdxl-lightning": {
        "supported": False,
        "reason": "the SDXL-Lightning / SDXL Base 1.0 cards document text-to-image; no multi-reference editing is documented for this checkpoint",
        "card": "https://huggingface.co/ByteDance/SDXL-Lightning",
        "accessed": "2026-10-22",
    },
    "dreamshaper-xl-lightning": {
        "supported": False,
        "reason": "the DreamShaper XL Lightning card documents text-to-image only; no reference-image editing is documented",
        "card": "https://huggingface.co/Lykon/dreamshaper-xl-lightning",
        "accessed": "2026-10-22",
    },
    "sdxl": {
        "supported": False,
        "reason": "the SDXL Base 1.0 card documents text-to-image; no reference-image editing is documented for this checkpoint",
        "card": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
        "accessed": "2026-10-22",
    },
    "zimage": {
        "supported": False,
        "reason": "BLOCKED model - no reference workflow may be used",
        "card": "https://huggingface.co/Tongyi-MAI/Z-Image-Turbo",
        "accessed": "2026-10-22",
    },
}


class StyleError(RuntimeError):
    """A style file is missing, invalid or unsafe to use."""


@dataclass(frozen=True)
class StyleSpec:
    """One niche style, loaded from its machine-readable file."""

    niche_id: str
    style_name: str
    display_name: str
    palette: Dict[str, str]
    line_style: Dict[str, Any]
    light: str
    camera_vocabulary: Dict[str, str]
    constraints: Tuple[Dict[str, Any], ...]
    label_rule: Dict[str, Any]
    anatomy_rule: Dict[str, Any]
    seed_policy: Dict[str, Any]
    aspect: Dict[str, Any]
    media_policy: Dict[str, Any]
    editorial_overlays: Tuple[str, ...]
    provenance: Dict[str, Any]
    path: str
    raw: Dict[str, Any]

    @property
    def style_phrase(self) -> str:
        return str(self.line_style.get("prompt_phrase") or "")

    def constraint(self, constraint_id: str) -> Dict[str, Any]:
        for entry in self.constraints:
            if entry.get("id") == constraint_id:
                return entry
        raise StyleError(f"{self.niche_id}: unknown constraint {constraint_id!r}")


def style_path(niche_id: str) -> Path:
    return NICHE_ROOT / niche_id / "style.json"


def load_style(niche_id: str, path: str | Path | None = None) -> StyleSpec:
    """Load a niche style. Raises StyleError (fail-closed)."""
    p = Path(path) if path else style_path(niche_id)
    if not p.is_file():
        raise StyleError(f"style file not found: {p}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise StyleError(f"style file is not readable JSON: {exc}")
    if not isinstance(doc, dict):
        raise StyleError(f"style file must be a JSON object: {p}")
    for key in REQUIRED_KEYS:
        if key not in doc:
            raise StyleError(f"{p}: required key {key!r} is missing")
    if doc["niche_id"] != niche_id:
        raise StyleError(
            f"{p}: niche_id {doc['niche_id']!r} does not match {niche_id!r}")
    spec = StyleSpec(
        niche_id=str(doc["niche_id"]),
        style_name=str(doc["style_name"]),
        display_name=str(doc.get("display_name") or doc["style_name"]),
        palette=dict(doc["palette"] or {}),
        line_style=dict(doc["line_style"] or {}),
        light=str(doc["light"]),
        camera_vocabulary=dict(doc["camera_vocabulary"] or {}),
        constraints=tuple(dict(c) for c in (doc["constraints"] or [])),
        label_rule=dict(doc["label_rule"] or {}),
        anatomy_rule=dict(doc["anatomy_rule"] or {}),
        seed_policy=dict(doc["seed_policy"] or {}),
        aspect=dict(doc["aspect"] or {}),
        media_policy=dict(doc.get("media_policy") or {}),
        editorial_overlays=tuple(doc.get("editorial_overlays") or ()),
        provenance=dict(doc["provenance"] or {}),
        path=str(p),
        raw=doc,
    )
    validate_style(spec)
    return spec


def _is_hex_colour(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in value[1:])


def validate_style(spec: StyleSpec) -> None:
    """Fail-closed checks on a style file."""
    if not spec.palette:
        raise StyleError(f"{spec.path}: the palette is empty")
    for token, hex_value in spec.palette.items():
        if not _is_hex_colour(hex_value):
            raise StyleError(
                f"{spec.path}: palette token {token!r} is not a #RRGGBB colour")
    if not spec.style_phrase:
        raise StyleError(f"{spec.path}: line_style.prompt_phrase is empty")
    if not spec.light:
        raise StyleError(f"{spec.path}: light is empty")
    for view in CANONICAL_VIEWS:
        if not spec.camera_vocabulary.get(view):
            raise StyleError(
                f"{spec.path}: camera_vocabulary has no {view!r} entry")
    if not spec.constraints:
        raise StyleError(f"{spec.path}: the constraint list is empty")
    seen = set()
    for entry in spec.constraints:
        cid = entry.get("id")
        if not cid:
            raise StyleError(f"{spec.path}: a constraint has no id")
        if cid in seen:
            raise StyleError(f"{spec.path}: duplicate constraint id {cid!r}")
        seen.add(cid)
        if not str(entry.get("positive") or "").strip():
            raise StyleError(
                f"{spec.path}: constraint {cid!r} has no positive form "
                "(the locked model has no negative prompt)")
        if entry.get("negative") is not None and \
                not str(entry["negative"]).strip():
            raise StyleError(
                f"{spec.path}: constraint {cid!r} has an empty negative form")
    if not spec.label_rule.get("label"):
        raise StyleError(f"{spec.path}: label_rule.label is empty")
    if "required" not in spec.anatomy_rule:
        raise StyleError(f"{spec.path}: anatomy_rule.required is missing")
    rng = spec.seed_policy.get("range")
    if not (isinstance(rng, (list, tuple)) and len(rng) == 2):
        raise StyleError(f"{spec.path}: seed_policy.range is missing")
    base = spec.seed_policy.get("base")
    if not isinstance(base, int) or not (rng[0] <= base <= rng[1]):
        raise StyleError(
            f"{spec.path}: seed_policy.base {base!r} is outside the range {rng}")


def supports_negative_prompt(adapter: Any) -> bool:
    """True when the model's prompt target accepts a negative prompt."""
    return str(getattr(adapter, "prompt_target", "")) in NEGATIVE_PROMPT_TARGETS


def constraint_fragments(spec: StyleSpec, adapter: Any) -> Dict[str, Any]:
    """The constraint phrases for one model.

    * `positive` - phrases injected into the prompt (all models),
    * `negative` - phrases for the negative prompt (only for models that
      accept one; empty otherwise),
    * `builder_enforced` - ids the read-only prompt builder already applies.
    """
    positive = [str(c["positive"]) for c in spec.constraints if c.get("inject")]
    negative: List[str] = []
    if supports_negative_prompt(adapter):
        negative = [str(c["negative"]) for c in spec.constraints
                    if c.get("negative")]
    return {
        "supports_negative_prompt": supports_negative_prompt(adapter),
        "positive": positive,
        "negative": negative,
        "builder_enforced": [str(c["id"]) for c in spec.constraints
                             if c.get("enforced_by", "").startswith("tools/prompting")],
    }


def reference_policy(model_key: str) -> Dict[str, Any]:
    """The reference-image (img2img) policy for one model, with the citation."""
    support = REFERENCE_IMAGE_SUPPORT.get(model_key)
    if support is None:
        return {"supported": False,
                "reason": f"no card evidence for {model_key!r}",
                "fallback": "seed + prompt anchoring"}
    out = dict(support)
    out["fallback"] = "seed + prompt anchoring"
    out["workflow"] = ("reference image (img2img) from the canonical front view"
                       if support.get("supported") else "seed + prompt anchoring")
    return out


def style_digest(spec: StyleSpec) -> str:
    """Stable digest of the style file (for manifests and job files)."""
    import hashlib
    raw = Path(spec.path).read_bytes()
    return hashlib.sha256(raw).hexdigest()


def all_styles() -> Dict[str, StyleSpec]:
    """Load every niche style (fail-closed)."""
    return {niche: load_style(niche) for niche in NICHES}
