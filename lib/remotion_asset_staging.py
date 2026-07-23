"""Stage local media into a project-scoped Remotion public dir for renders.

Headless Chromium blocks ``file://`` URIs for ``<Audio>`` (and can be flaky for
other media). Remotion's ``staticFile()`` only serves paths under a public
directory (default ``remotion-composer/public/``, or an explicit ``--public-dir``).

This module stages into a **project-scoped** public directory under
``projects/<id>/remotion-public/`` (never the shared composer tree), rewrites
props to relative ``staticFile()`` paths, and supports reliable cleanup after
render while leaving a debug report in the project workspace.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

_REMOTE_PREFIXES = ("http://", "https://", "data:")
_RESERVED_SLUGS = frozenset({".", ".."})
# Dots are disallowed so metadata project_id=".." cannot escape via Path join.
_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def derive_staging_slug(output_path: Path, composition_data: dict[str, Any] | None = None) -> str:
    """Derive a stable project slug for naming / reports (never a path segment from raw metadata)."""
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
    """Return a path-safe slug; reject reserved dot segments (``.``, ``..``)."""
    cleaned = _SLUG_SAFE.sub("-", value.strip()).strip("-_")
    if not cleaned or cleaned in _RESERVED_SLUGS:
        return "remotion-staged"
    # Reject any residual reserved segment if separators somehow survived.
    for part in cleaned.replace("\\", "/").split("/"):
        if part in _RESERVED_SLUGS or part == "":
            return "remotion-staged"
    return cleaned


def resolve_project_public_dir(
    output_path: Path,
    composition_data: dict[str, Any] | None = None,
) -> Path:
    """Resolve a project-scoped Remotion ``--public-dir`` (not remotion-composer/public).

    Prefer ``projects/<slug>/remotion-public/`` when the output lives under a
    project tree; otherwise use ``<output_parent>/.remotion-public/``.
    """
    del composition_data  # reserved for future metadata overrides
    resolved = output_path.resolve()
    parts = resolved.parts
    if "projects" in parts:
        idx = parts.index("projects")
        slug_idx = idx + 1
        if slug_idx < len(parts):
            # Climb from the output file up to projects/<slug>/.
            # parents[0] = one level up; we need (depth(file) - depth(slug)) - 1.
            levels_to_slug = (len(parts) - 1) - slug_idx
            project_dir = resolved.parents[levels_to_slug - 1] if levels_to_slug >= 1 else resolved.parent
            return project_dir / "remotion-public"
    return resolved.parent / ".remotion-public"


def ensure_contained(path: Path, root: Path) -> Path:
    """Resolve *path* and raise if it is not under *root*."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"staging path escapes root: {resolved} is not under {root_resolved}"
        ) from exc
    return resolved


def cleanup_staging_dir(public_dir: Path) -> None:
    """Remove a project-scoped Remotion public staging directory after render."""
    if not public_dir.exists():
        return
    # Only delete leaf staging dirs we created (name contract).
    if public_dir.name not in ("remotion-public", ".remotion-public"):
        return
    shutil.rmtree(public_dir, ignore_errors=True)


def _is_remote_asset(src: str) -> bool:
    return src.startswith(_REMOTE_PREFIXES)


def _looks_like_windows_drive(path_text: str) -> bool:
    """True for ``C:\\...``, ``C:/...``, or ``/C:/...`` drive paths."""
    text = path_text.replace("\\", "/")
    if text.startswith("/") and len(text) >= 3 and text[1].isalpha() and text[2] == ":":
        text = text[1:]
    return len(text) >= 2 and text[0].isalpha() and text[1] == ":"


def _as_filesystem_path(path_text: str) -> Path:
    """Build a ``Path`` from URI-derived text, normalizing Windows drive forms."""
    if _looks_like_windows_drive(path_text):
        # PureWindowsPath keeps drive + separators; as_posix() makes .name
        # correct on POSIX hosts (where ``\\`` is not a separator).
        text = path_text.replace("\\", "/")
        if text.startswith("/") and len(text) >= 3 and text[1].isalpha() and text[2] == ":":
            text = text[1:]
        return Path(PureWindowsPath(text).as_posix())
    return Path(path_text)


def _parse_file_uri(uri: str) -> Path | None:
    """Parse a ``file:`` URI into a filesystem ``Path`` (no existence check).

    Handles common forms agents and tooling produce:

    - POSIX: ``file:///Users/me/voice.mp3``
    - Windows drive (RFC-ish): ``file:///C:/Users/me/voice.mp3``
    - Windows drive as authority: ``file://C:/Users/me/voice.mp3``
    - Windows drive (naive ``f"file://{path}"``): ``file://C:\\Users\\me\\voice.mp3``
    """
    if not uri.lower().startswith("file:"):
        return None

    parsed = urlparse(uri)
    if parsed.scheme.lower() != "file":
        return None

    netloc = unquote(parsed.netloc or "")
    path_part = unquote(parsed.path or "")

    if netloc and netloc.lower() not in ("localhost",):
        # Naive Windows URI file://C:\Users\... — urlparse (esp. on POSIX)
        # may stuff the entire path into netloc with an empty path.
        if not path_part and ("\\" in netloc or (len(netloc) >= 2 and netloc[1] in ":|")):
            drive_path = (
                netloc.replace("|", ":", 1)
                if len(netloc) >= 2 and netloc[1] == "|"
                else netloc
            )
            if _looks_like_windows_drive(drive_path):
                return _as_filesystem_path(drive_path)

        # Windows drive as authority: netloc="C:", path="/Users/..." or "\Users\..."
        if len(netloc) == 2 and netloc[1] == ":":
            return _as_filesystem_path(netloc + path_part)
        if len(netloc) == 2 and netloc[1] == "|":
            return _as_filesystem_path(netloc[0] + ":" + path_part)
        return Path(f"//{netloc}{path_part}")

    if not path_part:
        return None
    try:
        converted = url2pathname(path_part)
    except (OSError, ValueError):
        converted = path_part
    return _as_filesystem_path(converted)


def _file_uri_to_path(uri: str) -> Path | None:
    """Convert a ``file://`` URI to an existing filesystem path, or None."""
    candidate = _parse_file_uri(uri)
    if candidate is None:
        return None
    try:
        return candidate.resolve() if candidate.exists() else None
    except OSError:
        return None


def _resolve_local_path(src: str) -> Path | None:
    """Return a filesystem path when *src* refers to local media."""
    if not src or _is_remote_asset(src):
        return None

    if src.lower().startswith("file:"):
        return _file_uri_to_path(src)

    path = Path(src)
    if path.is_absolute():
        return path.resolve() if path.exists() else None

    # Already a public-relative path (e.g. "narration.mp3") — do not treat as
    # a filesystem path unless it exists relative to cwd.
    if "/" in src and not path.exists():
        return None

    resolved = path.resolve()
    return resolved if resolved.exists() else None


def _stage_file(src: Path, staging_dir: Path, *, staging_root: Path) -> Path:
    """Copy *src* into *staging_dir*, disambiguating basename collisions.

    Destination is verified to remain under *staging_root* after resolve.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    ensure_contained(staging_dir, staging_root)

    dest = staging_dir / src.name
    ensure_contained(dest, staging_root)

    if dest.exists():
        try:
            if dest.resolve() == src.resolve():
                return ensure_contained(dest, staging_root)
        except OSError:
            pass
        digest = hashlib.sha256(str(src.resolve()).encode()).hexdigest()[:8]
        dest = staging_dir / f"{src.stem}_{digest}{src.suffix}"
        ensure_contained(dest, staging_root)

    shutil.copy2(src, dest)
    return ensure_contained(dest, staging_root)


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
    project_slug: str | None = None,
) -> dict[str, Any]:
    """Stage local media into *public_dir* and rewrite props for ``staticFile()``.

    *public_dir* is the Remotion ``--public-dir`` root (project-scoped). Files are
    copied directly into that root; props get basename-relative paths
    (``narration.mp3``), not shared ``remotion-composer/public/<slug>/`` paths.

    Mutates *props* in place. Returns a report dict for render metadata / debugging.
    """
    slug = _sanitize_slug(project_slug) if project_slug else "remotion-staged"
    staging_root = public_dir.resolve()
    staging_root.mkdir(parents=True, exist_ok=True)
    ensure_contained(staging_root, staging_root)

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
            dest = _stage_file(local, staging_root, staging_root=staging_root)
            relative = dest.name
            already_staged[src_key] = relative

        _set_nested(props, key, relative)
        staged.append({"key": key, "from": str(local), "to": relative})

    return {
        "project_slug": slug,
        "public_dir": str(staging_root),
        "staging_dir": str(staging_root),
        "staged": staged,
        "skipped": skipped,
        "lifecycle": "project-scoped; caller should cleanup_staging_dir after render",
    }
