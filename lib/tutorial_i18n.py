"""Per-language narration sidecars for Cypress tutorials.

The spoken lines live in the spec (cy.tutorialStep("…")). To voice and caption a
tutorial in another language we keep `<name>.i18n.<lang>.json` next to the spec
with one translated line per step index, plus translated recipe texts. Pure
helpers only (no I/O except load_sidecar) so everything is unit-testable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

LANG_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
TRANSLATABLE_RECIPE_KEYS = (
    "title", "subtitle", "intro_text", "intro_subtitle", "outro_text", "outro_subtitle",
)


def validate_lang(lang: str) -> str:
    lang = (lang or "").strip()
    if not LANG_RE.match(lang):
        raise ValueError("lang must be a code like de, fr or pt-BR")
    return lang


def timings_path(spec: Path, name: str, lang: str, source_lang: str) -> Path:
    if lang == source_lang:
        return spec.with_name(f"{name}.timings.json")
    return spec.with_name(f"{name}.timings.{lang}.json")


def i18n_path(spec: Path, name: str, lang: str) -> Path:
    return spec.with_name(f"{name}.i18n.{lang}.json")


def load_sidecar(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"translation sidecar not found: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON ({e})") from e
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return doc


def build_template(
    *,
    source_lang: str,
    lang: str,
    recipe: dict,
    source_steps: list[dict],
    existing: Optional[dict] = None,
) -> dict:
    """Skeleton for a translator (human or agent): every step with its current
    source line and the existing translation (if any), flagged stale when the
    source changed since it was translated."""
    prior_steps = {int(s.get("index", -1)): s for s in (existing or {}).get("steps", [])}
    prior_recipe = (existing or {}).get("recipe", {}) or {}
    steps = []
    for s in sorted(source_steps, key=lambda x: int(x.get("index", 0))):
        idx = int(s.get("index", 0))
        src = (s.get("narration") or "").strip()
        prev = prior_steps.get(idx) or {}
        steps.append({
            "index": idx,
            "source": src,
            "narration": (prev.get("narration") or "").strip(),
            "stale": bool(prev) and (prev.get("source") or "").strip() != src,
        })
    rec = {}
    for key in TRANSLATABLE_RECIPE_KEYS:
        if key in recipe and recipe.get(key) not in (None, ""):
            rec[key] = prior_recipe.get(key) or recipe[key]
    return {"lang": lang, "source_lang": source_lang, "recipe": rec, "steps": steps}


def validate_translation(doc: dict, *, lang: str, source_steps: list[dict]) -> list[str]:
    errs: list[str] = []
    if doc.get("lang") != lang:
        errs.append(f"lang mismatch: sidecar says {doc.get('lang')!r}, expected {lang!r}")
    steps = doc.get("steps")
    if not isinstance(steps, list):
        return errs + ["steps must be a list"]
    seen: dict[int, dict] = {}
    for s in steps:
        if not isinstance(s, dict) or "index" not in s:
            errs.append(f"step entry without index: {s!r}")
            continue
        idx = int(s["index"])
        text = s.get("narration")
        if not isinstance(text, str):
            errs.append(f"step {idx}: narration must be a string")
        elif not text.strip():
            errs.append(f"step {idx}: narration is empty")
        seen[idx] = s
    wanted = {int(s.get("index", 0)) for s in source_steps if (s.get("narration") or "").strip()}
    missing = sorted(wanted - set(seen))
    if missing:
        errs.append(f"missing translations for step(s) {', '.join(map(str, missing))}")
    rec = doc.get("recipe", {})
    if rec and not isinstance(rec, dict):
        errs.append("recipe must be an object")
    elif rec:
        for key, val in rec.items():
            if key not in TRANSLATABLE_RECIPE_KEYS:
                errs.append(f"recipe.{key} is not translatable")
            elif not isinstance(val, str):
                errs.append(f"recipe.{key} must be a string")
    return errs


def apply_translation(steps: list[Any], doc: dict) -> list[str]:
    """Replace each Step.narration with the sidecar line for its index."""
    warnings: list[str] = []
    by_idx = {int(s["index"]): s for s in doc.get("steps", []) if isinstance(s, dict) and "index" in s}
    present = set()
    for st in steps:
        present.add(st.index)
        entry = by_idx.get(st.index)
        if not entry or not (entry.get("narration") or "").strip():
            if st.narration:
                warnings.append(f"step {st.index}: missing translation — keeping source text")
            continue
        src = (entry.get("source") or "").strip()
        if src and src != st.narration.strip():
            warnings.append(f"step {st.index}: stale translation (source line changed since it was translated)")
        st.narration = entry["narration"].strip()
    for idx in sorted(set(by_idx) - present):
        warnings.append(f"step {idx}: extra translation (no such step in the spec) — ignored")
    return warnings


def localized_recipe(recipe: dict, doc: dict) -> dict:
    out = dict(recipe)
    for key, val in (doc.get("recipe") or {}).items():
        if key in TRANSLATABLE_RECIPE_KEYS and isinstance(val, str) and val.strip():
            out[key] = val
    out["lang"] = doc.get("lang") or out.get("lang", "en")
    return out
