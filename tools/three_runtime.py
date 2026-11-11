"""Where the Three.js world loads three.js from.

The world runtime imports `three` and `three/addons/...` by bare specifier;
an import map in index.html resolves them. `make setup` installs the pinned
`three` npm package in remotion-composer/; `stage_three` copies the modules
the runtime needs (and every module they import by relative path) into
`vendor/three/` in the workspace, so a render needs no network. Without the
install the import map points at the pinned CDN.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

THREE_VERSION = "0.181.2"
THREE_CDN_ROOT = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/"
VENDOR_DIR = "vendor/three"

# Modules world-runtime.js imports, relative to the package root.
THREE_ENTRY = "build/three.module.js"
ADDONS_DIR = "examples/jsm/"
ADDON_ENTRIES = ("examples/jsm/loaders/GLTFLoader.js",)

_REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_THREE_ROOT = _REPO_ROOT / "remotion-composer" / "node_modules" / "three"

_RELATIVE_IMPORT = re.compile(r"""(?:\bfrom|\bimport)\s*\(?\s*["'](\.{1,2}/[^"']+)["']""")

logger = logging.getLogger(__name__)


def _module_closure(root: Path, entries: tuple[str, ...]) -> list[str]:
    """Entry modules plus everything they import by relative path."""
    seen: set[str] = set()
    pending = list(entries)
    while pending:
        rel = pending.pop()
        path = root / rel
        if rel in seen or not path.is_file():
            continue
        seen.add(rel)
        for spec in _RELATIVE_IMPORT.findall(path.read_text(encoding="utf-8")):
            target = (path.parent / spec).resolve()
            try:
                pending.append(target.relative_to(root.resolve()).as_posix())
            except ValueError:
                continue  # outside the package
    return sorted(seen)


def stage_three(workspace: Path) -> tuple[dict[str, str], list[str]]:
    """Copy the three.js modules into ``workspace``; return (imports, files).

    ``imports`` is the import map's "imports" object. ``files`` lists the
    copied paths and is empty when three is not installed locally, in which
    case the map points at the pinned CDN and the render needs network.
    """
    if not (LOCAL_THREE_ROOT / THREE_ENTRY).is_file():
        logger.warning(
            "three is not installed locally (%s); the Three.js world imports it from %s, "
            "which needs network at render time. Run `make setup` or `npm install` in "
            "remotion-composer/.",
            LOCAL_THREE_ROOT,
            THREE_CDN_ROOT,
        )
        return {"three": THREE_CDN_ROOT + THREE_ENTRY, "three/addons/": THREE_CDN_ROOT + ADDONS_DIR}, []

    vendor = Path(workspace) / VENDOR_DIR
    files: list[str] = []
    for rel in _module_closure(LOCAL_THREE_ROOT, (THREE_ENTRY, *ADDON_ENTRIES)):
        dest = vendor / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LOCAL_THREE_ROOT / rel, dest)
        files.append(str(dest))
    base = f"./{VENDOR_DIR}/"
    return {"three": base + THREE_ENTRY, "three/addons/": base + ADDONS_DIR}, files
