"""Shared helpers for generated web output (HyperFrames compositions, previews).

The HTML we generate for HyperFrames / browser previews depends on the GSAP
animation runtime. Loading GSAP from a CDN (jsdelivr) is fragile: it breaks
behind a restricted-egress proxy and is fail-closed in distributed/cloud
renders. We vendor a pinned copy under ``lib/vendor/`` and stage it into the
output directory so generated compositions render offline and deterministically.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

# Used only when the vendored copy is somehow unavailable, so generated output
# degrades to the (online) CDN rather than breaking outright.
GSAP_CDN_FALLBACK = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"

_VENDOR_DIR = Path(__file__).resolve().parent / "vendor"


def vendored_gsap() -> Optional[Path]:
    """Path to the vendored GSAP runtime, or None if it isn't present."""
    candidate = _VENDOR_DIR / "gsap.min.js"
    return candidate if candidate.is_file() else None


def stage_gsap(target_dir: Path) -> Optional[str]:
    """Copy the vendored GSAP into ``target_dir``.

    Returns the staged file name (``gsap.min.js``) so the caller can build a
    relative ``<script src>``, or None if no vendored copy is available (in
    which case the caller should fall back to ``GSAP_CDN_FALLBACK``).
    """
    src = vendored_gsap()
    if not src:
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / "gsap.min.js"
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    return dest.name
