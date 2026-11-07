#!/usr/bin/env python3
"""tools/packaging/rights_records.py — asset records for QC, credits, packaging.

Every cut in the EDL must resolve to a record with an explicit rights_basis.
AI illustrations carry the generator model + its licence so the credit block
(and the AI disclosure) is derived, never hand-written. Own-graphics cards
are marked as own work: QC exempts them from sha256/source_url but still
requires a credit line.

Fail closed: an unknown cut kind or an illustration with no sha256 raises.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

# Model cards are the licence evidence for generated art (Apache-2.0).
MODEL_LICENSES = {
    "klein": {
        "model_id": "black-forest-labs/FLUX.2-klein-4B",
        "license": "Apache-2.0",
        "license_url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-4B",
        "credit": "AI-generated illustration (FLUX.2 klein 4B, Apache-2.0)",
    },
    "sdxl": {
        "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "license": "CreativeML Open RAIL++-M",
        "license_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
        "credit": "AI-generated illustration (SDXL Base 1.0, Open RAIL++-M)",
    },
}
OWN_GRAPHICS = {
    "rights_basis": "explicit_license",
    "center": "Original graphics by the channel owner (own work)",
    "license": "Own work, all rights held by the channel owner; used by permission.",
    "license_url": "",
}


def _sha256(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_rights_records(
    edl: Dict[str, Any],
    illustration_manifest: Dict[str, Any] | None = None,
    *,
    model: str = "klein",
    access_date: str = "2026-10-22",
) -> List[Dict[str, Any]]:
    if model not in MODEL_LICENSES:
        raise ValueError(f"unknown illustration model {model!r}")
    lic = MODEL_LICENSES[model]
    manifest_by_file = {}
    for ent in (illustration_manifest or {}).get("images", []):
        manifest_by_file[str(Path(ent["file"]).name)] = ent

    records: List[Dict[str, Any]] = []
    for cut in edl.get("cuts", []):
        kind = cut.get("kind")
        source = str(cut.get("source", ""))
        if kind == "ai_illustration":
            ent = manifest_by_file.get(Path(source).name, {})
            sha = str(ent.get("sha256") or cut.get("source_sha256") or "")
            if len(sha) != 64:
                sha = _sha256(source)
            if len(sha) != 64:
                raise ValueError(
                    f"illustration without a verifiable sha256: {source}")
            records.append({
                "asset_id": cut["asset_id"],
                "kind": "ai_illustration",
                "rights_basis": "ai_generated_illustration",
                "generator": "AI",
                "model": lic["model_id"],
                "license": lic["license"],
                "license_url": lic["license_url"],
                "credit": lic["credit"],
                "source_url": lic["license_url"],
                "sha256": sha,
                "label": cut.get("label") or "Speculative illustration",
                "description": cut.get("description", ""),
                "flags": {},
                "usable": True,
                "access_date": access_date,
            })
        elif kind == "graphics":
            records.append({
                "asset_id": cut["asset_id"],
                "kind": "graphics",
                "rights_basis": OWN_GRAPHICS["rights_basis"],
                "center": OWN_GRAPHICS["center"],
                "credit": OWN_GRAPHICS["center"],
                "license": OWN_GRAPHICS["license"],
                "license_url": OWN_GRAPHICS["license_url"],
                "flags": {},
                "usable": True,
                "access_date": access_date,
            })
        else:
            raise ValueError(f"unresolved cut kind {kind!r} for {cut.get('asset_id')}")
    return records


def credits_lines(records: List[Dict[str, Any]]) -> List[str]:
    """Human-readable credit block, derived from the records (no copy-paste)."""
    lines: List[str] = []
    seen = set()
    for rec in records:
        credit = str(rec.get("credit") or rec.get("center") or "").strip()
        if not credit or credit in seen:
            continue
        seen.add(credit)
        lic = str(rec.get("license") or "").strip()
        url = str(rec.get("license_url") or "").strip()
        line = f"- {credit}"
        if lic:
            line += f" — {lic}"
        if url:
            line += f" — {url}"
        lines.append(line)
    return lines


def write_rights_records(path: str | Path, records: List[Dict[str, Any]]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"assets": records}, indent=2), encoding="utf-8")
    return out
