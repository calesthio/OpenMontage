"""Brand Kit CRUD — JSON file store under brand_kits/<slug>/kit.json."""

from __future__ import annotations

import io
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

OM_ROOT = Path(__file__).parent.parent.parent.parent
BRAND_KITS_DIR = OM_ROOT / "brand_kits"

# Reference images get embedded as a base64 data URI directly in the LLM
# prompt at generation time (stage_runner.py's _brand_reference_image_data_uri
# — MAAS_API_BASE is a remote gateway that can't reach back into this box's
# localhost to fetch a served URL, so base64 is the only path that works
# regardless of deployment). That data URI gets replayed in every turn's
# message history for the rest of the assets stage, so an unbounded upload
# would silently balloon token cost — resize down before ever writing to
# disk rather than relying on the runner-side size cap to catch it later.
_REFERENCE_IMAGE_MAX_DIMENSION = 768

# Explicit cap on the raw upload body, enforced BEFORE it's fully read into
# memory and handed to PIL for decoding. Without this, an arbitrarily large
# (or maliciously crafted decompression-bomb) upload gets read + decoded in
# full before the post-decode resize ever has a chance to shrink it.
_REFERENCE_IMAGE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    # Unicode-aware: keep any letter/number character (str.isalnum(), which
    # covers Latin, CJK, Korean/Japanese, Cyrillic, Arabic, etc.), collapsing
    # everything else (spaces, punctuation, emoji) to a single hyphen. A
    # hardcoded "[^a-z0-9<CJK-range>]" allowlist collapsed any other script
    # (Korean, Japanese kana, Cyrillic, Arabic, emoji) entirely to hyphens,
    # leaving a kit_id that's just a random hex suffix with no trace of the
    # brand name.
    lowered = name.lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in lowered)
    return re.sub(r"-+", "-", slug).strip("-")


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
    # Role-tagged colors (roadmap 3.2): {"bg","fg","accent","text"} — a flat
    # palette list can't tell a renderer WHICH color is the background vs
    # the accent, so brand colors were decorative, not enforceable.
    colors: dict[str, str] = {}
    # Brand voice (roadmap 3.2): the TTS voice id every video of this brand
    # narrates with — two videos of one brand previously had no guarantee of
    # the same narrator. Applied as the default `voice` on TTS calls
    # (tool_bridge) whenever the agent doesn't explicitly pick one.
    voice_id: str = ""
    target_audience: str = ""
    logo_url: str = ""
    # Light/dark logo variants (roadmap 3.2) — one logo can't sit on both a
    # light and a dark scene.
    logo_light_url: str = ""
    logo_dark_url: str = ""
    style_notes: str = ""
    # Relative path under brand_kits/<kit_id>/ — set via the reference-image
    # upload endpoint below, not by the client directly (there's nowhere for
    # a client to get a valid value for this before the kit_id exists).
    reference_image_path: str = ""
    extra: dict[str, Any] = {}


class BrandKitUpdate(BaseModel):
    brand_name: str | None = None
    slogan: str | None = None
    industry: str | None = None
    tone_keywords: list[str] | None = None
    color_palette: list[str] | None = None
    colors: dict[str, str] | None = None
    voice_id: str | None = None
    target_audience: str | None = None
    logo_url: str | None = None
    logo_light_url: str | None = None
    logo_dark_url: str | None = None
    style_notes: str | None = None
    reference_image_path: str | None = None
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
    # Remove the whole kit directory, not just kit.json — reference.png (and
    # anything else written under it) would otherwise stay on disk forever
    # AND stay publicly servable via the /brand-media mount, which has no
    # existence check tied to kit.json.
    shutil.rmtree(p.parent)
    return None


@router.post("/{kit_id}/reference-image")
async def upload_reference_image(kit_id: str, file: UploadFile):
    """Upload/replace this kit's reference image (used for character/product
    consistency across generated shots — see stage_runner.py's
    _brand_reference_image_data_uri). The raw upload is capped at
    _REFERENCE_IMAGE_MAX_BYTES before it's ever fully read/decoded, then the
    decoded image is resized to at most _REFERENCE_IMAGE_MAX_DIMENSION per
    side and always re-saved as PNG — so the file this endpoint writes is
    already safely small for the base64 data URI it becomes at generation
    time, and no separate size check is needed downstream for anything
    uploaded through this path.
    """
    kit = _load(kit_id)
    if not kit:
        raise HTTPException(404, "Brand kit not found")

    # Read in bounded chunks and bail out as soon as the cap is exceeded,
    # rather than trusting a (spoofable, sometimes absent) Content-Length
    # header — this guarantees we never hold more than
    # _REFERENCE_IMAGE_MAX_BYTES + one chunk in memory before rejecting.
    chunks: list[bytes] = []
    total = 0
    chunk_size = 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > _REFERENCE_IMAGE_MAX_BYTES:
            raise HTTPException(
                400,
                f"Reference image too large (max {_REFERENCE_IMAGE_MAX_BYTES // (1024 * 1024)}MB)",
            )
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        raise HTTPException(400, "Empty file")

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        img.load()  # force full decode now — fail here, not on first use
    except Exception:
        raise HTTPException(400, "Could not read file as an image")

    if img.mode in ("RGBA", "LA", "P"):
        # .convert("RGB") on an image with an alpha channel drops the alpha
        # and keeps whatever RGB values happened to sit underneath it —
        # frequently black for a logo exported with a transparent
        # background, silently turning "transparent" into "black backdrop".
        # Composite onto white first so a transparent-background upload
        # actually looks like the intended subject on a plain background.
        img = img.convert("RGBA")
        flattened = Image.new("RGB", img.size, (255, 255, 255))
        flattened.paste(img, mask=img.getchannel("A"))
        img = flattened
    else:
        img = img.convert("RGB")
    img.thumbnail((_REFERENCE_IMAGE_MAX_DIMENSION, _REFERENCE_IMAGE_MAX_DIMENSION))

    kit_dir = BRAND_KITS_DIR / kit_id
    kit_dir.mkdir(parents=True, exist_ok=True)
    rel_path = "reference.png"
    img.save(kit_dir / rel_path, format="PNG")

    kit["reference_image_path"] = rel_path
    kit["updated_at"] = time.time()
    _kit_path(kit_id).write_text(json.dumps(kit, ensure_ascii=False, indent=2))

    return {
        "reference_image_path": rel_path,
        "reference_image_url": f"/brand-media/{kit_id}/{rel_path}",
        "width": img.width,
        "height": img.height,
    }
