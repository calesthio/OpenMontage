"""Pipeline manifest access for the web platform.

Wraps the engine's strict loader but degrades to a lenient raw YAML read when a
manifest fails schema validation (some engine manifests have drifted from the
schema — e.g. a category value or an extra key). This keeps every pipeline in
pipeline_defs/ runnable and listable from the web platform without editing the
engine's manifests, while still preferring strict validation when it passes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# server/app/pipeline_catalog.py → repo root is three parents up.
OM_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_DEFS_DIR = OM_ROOT / "pipeline_defs"


def list_manifest_names() -> list[str]:
    if not PIPELINE_DEFS_DIR.exists():
        return []
    return sorted(p.stem for p in PIPELINE_DEFS_DIR.glob("*.yaml"))


def load_manifest(name: str) -> dict[str, Any]:
    """Return a manifest dict. Strict validation first, lenient YAML on drift.

    Raises FileNotFoundError if the manifest file doesn't exist OR isn't one of
    the known pipeline names — `name` reaches here from user-controlled input
    (POST /jobs "pipeline" field, GET /pipelines/{name}), so it is validated
    against the real manifest set before touching the filesystem. This blocks
    "../" traversal / arbitrary-path reads that an f-string path join alone
    would not.
    """
    if name not in list_manifest_names():
        raise FileNotFoundError(f"Unknown pipeline: {name!r}")
    path = PIPELINE_DEFS_DIR / f"{name}.yaml"
    try:
        # readonly = mtime-cached; the uncached load_pipeline re-parses and
        # re-validates on every call, and this serves GET /pipelines (see the
        # same fix in backlot/state.py's _load_pipeline_meta). Returns a deep
        # copy, so the mutation below can't poison the cache.
        from lib.pipeline_loader import load_pipeline_readonly
        manifest = load_pipeline_readonly(name)
    except FileNotFoundError:
        raise
    except Exception:
        # Schema drift or a loader hiccup — fall back to a raw read so the
        # pipeline stays usable. Validation is best-effort, not a gate here.
        import yaml
        manifest = yaml.safe_load(path.read_text())
    # yaml.safe_load on an empty/null-only file returns None — never hand that
    # back to callers that assume a dict (GET /pipelines would 500 for ALL
    # pipelines, not just the malformed one).
    return manifest or {}
