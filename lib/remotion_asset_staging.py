"""Stage local media into remotion-composer/public/ for Remotion renders.

Headless Chromium blocks ``file://`` URIs for ``<Audio>`` (and can be flaky for
other media). Remotion's ``staticFile()`` only serves paths under ``public/``.
Copy local cut sources and audio into ``public/<project_slug>/`` and rewrite
props to relative paths the Explainer composition can resolve.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

_REMOTE_PREFIXES = ("http://", "https://", "data:")


def derive_staging_slug(output_path: Path, composition_data: dict[str, Any] | None = None) -> str:
    """Derive a stable public/ subdirectory name for staged assets."""
    composition_data = composition_data or {}
    meta = composition_data.get("metadata") or {}
    for key in ("project_id", "project_slug", "slug"):
        raw = meta.get(key)
        if raw:
            return _sanitize_slug(str(raw))

    resolved = output_path.resolve()
    parts = resolved.parts
    if "projects" in parts:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            return _sanitize_slug(parts[idx + 1])

    return _sanitize_slug(resolved.parent.name or "remotion-staged")


def _sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return cleaned or "remotion-staged"


def _is_remote_asset(src: str) -> bool:
    return src.startswith(_REMOTE_PREFIXES)


def _resolve_local_path(src: str) -> Path | None:
    """Return a filesystem path when *src* refers to local media."""
    if not src or _is_remote_asset(src):
        return None

    if src.startswith("file://"):
        raw = src[len("file://") :]
        if raw.startswith("/"):
            candidate = Path(raw)
        else:
            candidate = Path("/" + raw)
        return candidate.resolve() if candidate.exists() else None

    path = Path(src)
    if path.is_absolute():
        return path.resolve() if path.exists() else None

    # Already a public-relative path (e.g. "my-project/narration.mp3") — do not
    # treat as a filesystem path unless it exists relative to cwd.
    if "/" in src and not path.exists():
        return None

    resolved = path.resolve()
    return resolved if resolved.exists() else None


def _stage_file(src: Path, staging_dir: Path) -> Path:
    """Copy *src* into *staging_dir*, disambiguating basename collisions."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    dest = staging_dir / src.name
    if dest.exists():
        try:
            if dest.resolve() == src.resolve():
                return dest
        except OSError:
            pass
        digest = hashlib.sha256(str(src.resolve()).encode()).hexdigest()[:8]
        dest = staging_dir / f"{src.stem}_{digest}{src.suffix}"

    shutil.copy2(src, dest)
    return dest


def _set_nested(props: dict[str, Any], key: str, value: str) -> None:
    if key == "audio.narration.src":
        props.setdefault("audio", {}).setdefault("narration", {})["src"] = value
    elif key == "audio.music.src":
        props.setdefault("audio", {}).setdefault("music", {})["src"] = value
    elif key.startswith("cuts."):
        _, idx_s, field = key.split(".", 2)
        props["cuts"][int(idx_s)][field] = value


def _collect_staging_targets(props: dict[str, Any]) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for i, cut in enumerate(props.get("cuts") or []):
        source = cut.get("source")
        if source:
            targets.append((f"cuts.{i}.source", str(source)))

    audio = props.get("audio") or {}
    narration = audio.get("narration")
    if isinstance(narration, dict) and narration.get("src"):
        targets.append(("audio.narration.src", str(narration["src"])))

    music = audio.get("music")
    if isinstance(music, dict) and music.get("src"):
        targets.append(("audio.music.src", str(music["src"])))

    return targets


def stage_local_assets_for_remotion(
    props: dict[str, Any],
    *,
    public_dir: Path,
    project_slug: str,
) -> dict[str, Any]:
    """Stage local media and rewrite *props* paths for Remotion ``staticFile()``.

    Mutates *props* in place. Returns a report dict with ``staged`` and
    ``skipped`` lists for render metadata / debugging.
    """
    staging_dir = public_dir / project_slug
    staged: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    already_staged: dict[str, str] = {}

    for key, src in _collect_staging_targets(props):
        if _is_remote_asset(src):
            skipped.append({"key": key, "src": src, "reason": "remote"})
            continue

        local = _resolve_local_path(src)
        if local is None:
            skipped.append({"key": key, "src": src, "reason": "not_local_or_missing"})
            continue

        src_key = str(local.resolve())
        if src_key in already_staged:
            relative = already_staged[src_key]
        else:
            dest = _stage_file(local, staging_dir)
            relative = f"{project_slug}/{dest.name}"
            already_staged[src_key] = relative

        _set_nested(props, key, relative)
        staged.append({"key": key, "from": str(local), "to": relative})

    return {
        "project_slug": project_slug,
        "staging_dir": str(staging_dir),
        "staged": staged,
        "skipped": skipped,
    }
