"""Shared asset policy checks for reference-video production gates."""

from __future__ import annotations

from typing import Any


FACE_OR_AVATAR_ROLE_KEYWORDS = (
    "face",
    "likeness",
    "portrait",
    "presenter",
    "headshot",
    "肖像",
    "脸",
    "面部",
    "真人",
)


def asset_lookup(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    custom_assets = (package.get("editable_inputs") or {}).get("custom_assets") or []
    return {
        str(asset.get("id")): asset
        for asset in custom_assets
        if isinstance(asset, dict) and str(asset.get("id", "")).strip()
    }


def selected_assets(scene: dict[str, Any]) -> list[dict[str, Any]]:
    production_inputs = scene.get("production_inputs") or {}
    assets = production_inputs.get("selected_assets") or []
    return [asset for asset in assets if isinstance(asset, dict)]


def is_authorized_asset(asset: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> bool:
    if asset.get("authorized") is True:
        return True
    if asset.get("authorized") is False:
        return False
    asset_id = str(asset.get("id", ""))
    return bool(asset_id and lookup.get(asset_id, {}).get("authorized") is True)


def _role_text(asset: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> str:
    asset_id = str(asset.get("id", ""))
    canonical = lookup.get(asset_id, {})
    values = [
        asset.get("role"),
        asset.get("slot"),
        asset.get("subtype"),
        canonical.get("role"),
        canonical.get("slot"),
        canonical.get("subtype"),
    ]
    return " ".join(str(value).lower() for value in values if value)


def is_face_or_avatar_reference(
    asset: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
) -> bool:
    role_text = _role_text(asset, lookup)
    return any(keyword in role_text for keyword in FACE_OR_AVATAR_ROLE_KEYWORDS)


def validate_required_face_or_avatar_asset(package: dict[str, Any]) -> list[str]:
    approval = package.get("approval") or {}
    if approval.get("requires_team_authorized_face_or_avatar") is not True:
        return []

    lookup = asset_lookup(package)
    for scene in package.get("scenes") or []:
        for asset in selected_assets(scene):
            if is_authorized_asset(asset, lookup) and is_face_or_avatar_reference(asset, lookup):
                return []

    return [
        "replication_package requires at least one selected team-authorized face/presenter asset"
    ]
