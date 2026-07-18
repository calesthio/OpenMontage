"""Brand Kit CRUD — JSON file store under brand_kits/<slug>/kit.json."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

OM_ROOT = Path(__file__).parent.parent.parent.parent
BRAND_KITS_DIR = OM_ROOT / "brand_kits"

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9一-鿿]+", "-", name.lower()).strip("-")


def _kit_path(kit_id: str) -> Path:
    return BRAND_KITS_DIR / kit_id / "kit.json"


def _load(kit_id: str) -> dict | None:
    p = _kit_path(kit_id)
    return json.loads(p.read_text()) if p.exists() else None


def _list_all() -> list[dict]:
    if not BRAND_KITS_DIR.exists():
        return []
    kits = []
    for d in sorted(BRAND_KITS_DIR.iterdir()):
        p = d / "kit.json"
        if p.exists():
            try:
                kits.append(json.loads(p.read_text()))
            except Exception:
                pass
    kits.sort(key=lambda k: k.get("updated_at", 0), reverse=True)
    return kits


# ── schemas ───────────────────────────────────────────────────────────────────

class BrandKitCreate(BaseModel):
    brand_name: str
    slogan: str = ""
    industry: str = ""
    tone_keywords: list[str] = []
    color_palette: list[str] = []
    target_audience: str = ""
    logo_url: str = ""
    style_notes: str = ""
    extra: dict[str, Any] = {}


class BrandKitUpdate(BaseModel):
    brand_name: str | None = None
    slogan: str | None = None
    industry: str | None = None
    tone_keywords: list[str] | None = None
    color_palette: list[str] | None = None
    target_audience: str | None = None
    logo_url: str | None = None
    style_notes: str | None = None
    extra: dict[str, Any] | None = None


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_brand_kits():
    return {"brand_kits": _list_all()}


@router.post("", status_code=201)
async def create_brand_kit(req: BrandKitCreate):
    kit_id = f"{_slug(req.brand_name)}-{uuid.uuid4().hex[:6]}"
    now = time.time()
    kit = {
        "kit_id": kit_id,
        "created_at": now,
        "updated_at": now,
        **req.model_dump(),
    }
    kit_dir = BRAND_KITS_DIR / kit_id
    kit_dir.mkdir(parents=True, exist_ok=True)
    (kit_dir / "kit.json").write_text(json.dumps(kit, ensure_ascii=False, indent=2))
    return kit


@router.get("/{kit_id}")
async def get_brand_kit(kit_id: str):
    kit = _load(kit_id)
    if not kit:
        raise HTTPException(404, "Brand kit not found")
    return kit


@router.patch("/{kit_id}")
async def update_brand_kit(kit_id: str, req: BrandKitUpdate):
    kit = _load(kit_id)
    if not kit:
        raise HTTPException(404, "Brand kit not found")
    updates = req.model_dump(exclude_none=True)
    kit.update(updates)
    kit["updated_at"] = time.time()
    _kit_path(kit_id).write_text(json.dumps(kit, ensure_ascii=False, indent=2))
    return kit


@router.delete("/{kit_id}", status_code=204)
async def delete_brand_kit(kit_id: str):
    p = _kit_path(kit_id)
    if not p.exists():
        raise HTTPException(404, "Brand kit not found")
    p.unlink()
    return None
