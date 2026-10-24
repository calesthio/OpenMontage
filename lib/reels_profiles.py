"""Load editing profiles, client brand profiles and correction lexicons.

Layout (all YAML):

    config/reels/editing_profiles/<profile_id>.yaml   pacing / cut / caption style
    config/reels/corrections/az_common.yaml          shared Azerbaijani lexicon
    brand_profiles/<client_id>/brand.yaml            one client's brand identity
    brand_profiles/<client_id>/corrections.yaml      that client's names & terms

Editing profiles never carry brand colours: palette, fonts and logo come only
from the client's approved brand profile. A brand profile that is still
``approved: false`` resolves with neutral styling so unapproved colours never
reach a deliverable.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EDITING_PROFILES_DIR = REPO_ROOT / "config" / "reels" / "editing_profiles"
CORRECTIONS_DIR = REPO_ROOT / "config" / "reels" / "corrections"
BRAND_PROFILES_DIR = REPO_ROOT / "brand_profiles"
NEUTRAL_CLIENT_ID = "neutral_test"

_CLIENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Brand keys an editing profile is not allowed to set.
_BRAND_ONLY_KEYS = {"primary_colors", "secondary_colors", "logo_asset", "font_preferences"}

BRAND_REQUIRED_FIELDS = [
    "client_id",
    "brand_name",
    "industry",
    "target_audience",
    "brand_positioning",
    "primary_colors",
    "secondary_colors",
    "font_preferences",
    "subtitle_style",
    "preferred_editing_profile",
    "editing_pace",
    "transition_preferences",
    "music_preferences",
    "logo_asset",
    "CTA_preferences",
    "forbidden_visual_elements",
    "export_settings",
]


class ProfileError(ValueError):
    """Raised for a missing, malformed or unsafe profile."""


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProfileError(f"Profile file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ProfileError(f"{path} must contain a YAML mapping")
    return data


def validate_client_id(client_id: str) -> str:
    """Reject ids that could escape brand_profiles/ (path traversal)."""
    if not isinstance(client_id, str) or not _CLIENT_ID_RE.match(client_id):
        raise ProfileError(
            f"Invalid client_id {client_id!r}: use 2-64 chars of a-z, 0-9, '_' or '-'"
        )
    return client_id


def list_editing_profiles(root: Path = EDITING_PROFILES_DIR) -> list[str]:
    return sorted(p.stem for p in root.glob("*.yaml"))


def load_editing_profile(profile_id: str, root: Path = EDITING_PROFILES_DIR) -> dict[str, Any]:
    profile = _read_yaml(root / f"{profile_id}.yaml")
    leaked = _BRAND_ONLY_KEYS & set(profile)
    if leaked:
        raise ProfileError(
            f"Editing profile {profile_id} sets brand-only keys {sorted(leaked)}; "
            "colours, fonts and logos belong in the client's brand profile"
        )
    if profile.get("profile_id") != profile_id:
        raise ProfileError(f"{profile_id}.yaml declares profile_id={profile.get('profile_id')!r}")
    return profile


def list_clients(root: Path = BRAND_PROFILES_DIR) -> list[str]:
    return sorted(
        p.parent.name
        for p in root.glob("*/brand.yaml")
        if not p.parent.name.startswith("_")
    )


def validate_brand_profile(brand: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means the profile is structurally valid."""
    problems = [f"missing field: {f}" for f in BRAND_REQUIRED_FIELDS if f not in brand]
    for key in ("primary_colors", "secondary_colors"):
        for colour in brand.get(key) or []:
            if not isinstance(colour, str) or not _HEX_RE.match(colour):
                problems.append(f"{key}: {colour!r} is not a #RRGGBB hex colour")
    if "client_id" in brand:
        try:
            validate_client_id(brand["client_id"])
        except ProfileError as exc:
            problems.append(str(exc))
    return problems


def load_brand_profile(client_id: str, root: Path = BRAND_PROFILES_DIR) -> dict[str, Any]:
    validate_client_id(client_id)
    brand = _read_yaml(root / client_id / "brand.yaml")
    problems = validate_brand_profile(brand)
    if problems:
        raise ProfileError(f"Brand profile {client_id} is invalid: " + "; ".join(problems))
    if brand["client_id"] != client_id:
        raise ProfileError(
            f"brand_profiles/{client_id}/brand.yaml declares client_id={brand['client_id']!r}"
        )
    return brand


def resolve_style(
    client_id: str,
    profile_id: str | None = None,
    *,
    brand_root: Path = BRAND_PROFILES_DIR,
    profile_root: Path = EDITING_PROFILES_DIR,
) -> dict[str, Any]:
    """Merge an editing profile with a client's brand into one render style.

    The profile supplies pacing, cut rules and caption layout; the brand
    supplies colours, fonts and logo. Unapproved brands fall back to the
    neutral palette and report it in ``warnings``.
    """
    brand = load_brand_profile(client_id, brand_root)
    profile_id = profile_id or brand["preferred_editing_profile"]
    profile = load_editing_profile(profile_id, profile_root)
    neutral = load_brand_profile(NEUTRAL_CLIENT_ID, brand_root)

    warnings: list[str] = []
    approved = bool(brand.get("approved"))
    palette_source = brand if approved else neutral
    if not approved:
        warnings.append(
            f"Brand profile '{client_id}' is not approved; neutral colours, fonts "
            "and no logo are used. Confirm the brand data before final delivery."
        )

    caption = copy.deepcopy(profile.get("captions", {}))
    brand_caption = palette_source.get("subtitle_style") or {}
    caption.update({k: v for k, v in brand_caption.items() if v is not None})

    fonts = palette_source.get("font_preferences") or {}
    caption.setdefault("font", fonts.get("caption") or fonts.get("primary") or "Inter")

    return {
        "client_id": client_id,
        "brand_name": brand["brand_name"],
        "brand_approved": approved,
        "profile_id": profile_id,
        "profile": profile,
        "captions": caption,
        "colors": {
            "primary": list(palette_source.get("primary_colors") or []),
            "secondary": list(palette_source.get("secondary_colors") or []),
        },
        "logo_asset": palette_source.get("logo_asset") if approved else None,
        "cta": brand.get("CTA_preferences") or {},
        "forbidden_visual_elements": list(brand.get("forbidden_visual_elements") or []),
        "music": brand.get("music_preferences") or {},
        "export": {**(profile.get("export") or {}), **(brand.get("export_settings") or {})},
        "warnings": warnings,
    }


def load_lexicon(
    client_id: str | None = None,
    *,
    corrections_root: Path = CORRECTIONS_DIR,
    brand_root: Path = BRAND_PROFILES_DIR,
) -> dict[str, Any]:
    """Merge the shared Azerbaijani lexicon with a client's own lexicon.

    Client entries win over shared ones. ``protected_terms`` are folded into
    ``replacements`` so "smm" and "Smm" both become "SMM", and listed in
    ``protected_terms`` so their exact spelling survives casing changes.
    """
    sources = [corrections_root / "az_common.yaml"]
    if client_id:
        validate_client_id(client_id)
        sources.append(brand_root / client_id / "corrections.yaml")

    merged: dict[str, Any] = {
        "replacements": {}, "protected_terms": [], "hotwords": [], "initial_prompt": "",
    }
    prompts: list[str] = []
    for path in sources:
        if not path.is_file():
            continue
        data = _read_yaml(path)
        for term in data.get("protected_terms") or []:
            merged["replacements"][str(term)] = str(term)
            if str(term) not in merged["protected_terms"]:
                merged["protected_terms"].append(str(term))
        for wrong, right in (data.get("replacements") or {}).items():
            merged["replacements"][str(wrong)] = str(right)
        for word in data.get("hotwords") or []:
            if word not in merged["hotwords"]:
                merged["hotwords"].append(str(word))
        if data.get("initial_prompt"):
            prompts.append(str(data["initial_prompt"]).strip())
    merged["initial_prompt"] = " ".join(prompts)
    return merged
