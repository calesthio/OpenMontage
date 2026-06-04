"""Project-agnostic Wikimedia Commons archival fetcher.

Replaces the per-project `fetch_archival.py` pattern. All requests go
through `tools.video.stock_sources.wikimedia.WikimediaSource`, which
enforces the four protections Wikimedia's anonymous-client policy
requires (compliant UA, ≥1.2s pacing, Retry-After on 429s, visible
status codes). Fix the adapter once, every project benefits.

## Usage

    python scripts/fetch_archival.py --config <path/to/queries.{yaml,json}>

The config drives everything: the queries to run, the substring allow-
list, and the output paths. Minimal config:

    project: example-project
    queries:
      - "Coastal harbor lighthouse"
      - "Old stone bridge"
    keep_keywords:
      - "lighthouse"
      - "bridge"

If `project` is set, paths default to
  out_dir  = projects/<project>/assets/images/archival/
  manifest = projects/<project>/artifacts/wikimedia_manifest.json

Override either explicitly with `out_dir:` / `manifest:` in the config.

## Behavior

- **Additive by default.** Existing manifest entries are preserved;
  re-running won't redo successful downloads. Pass `--clean` to start
  fresh.
- **Title-deduped.** Same Commons file from multiple queries is fetched
  once.
- **Substring filtering.** `keep_keywords` is a list of case-insensitive
  substrings; titles must contain at least one to be kept. Empty list /
  omitted = no filter.
- **Image MIME gate.** Only `image/jpeg` and `image/png` by default
  (override with `mime_allow:` in the config).
- **Status code visibility.** Adapter raises with HTTP status on
  unrecoverable failures; this script catches per-query and per-file so
  one bad query doesn't sink the run, but the cause is logged.

## Config schema

```yaml
# Either `project` OR both `out_dir` and `manifest` required.
project: <kebab-name>

queries:                              # required, non-empty
  - "..."

keep_keywords: []                     # optional; case-insensitive substrings
mime_allow:                           # optional; default below
  - image/jpeg
  - image/png
per_query_limit: 15                   # optional; default 15
min_width: 0                          # optional; passed to SearchFilters.min_width

out_dir: <path>                       # optional; default projects/<project>/assets/images/archival
manifest: <path>                      # optional; default projects/<project>/artifacts/wikimedia_manifest.json
```

JSON configs are also supported — the file extension determines the parser.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.video.stock_sources.base import Candidate, SearchFilters  # noqa: E402
from tools.video.stock_sources.wikimedia import WikimediaSource  # noqa: E402


DEFAULT_MIME_ALLOW = ("image/jpeg", "image/png")
DEFAULT_PER_QUERY_LIMIT = 15


def _load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    ext = path.suffix.lower()
    if ext in (".yaml", ".yml"):
        import yaml  # local import — keep script importable without yaml
        return yaml.safe_load(text) or {}
    if ext == ".json":
        return json.loads(text)
    raise ValueError(
        f"Unsupported config extension {ext!r} for {path}. Use .yaml/.yml/.json."
    )


def _resolve_paths(config: dict[str, Any]) -> tuple[Path, Path]:
    """Return (out_dir, manifest_path), resolving `project:` defaults."""
    project = config.get("project")
    out_dir = config.get("out_dir")
    manifest = config.get("manifest")

    if out_dir is None and project:
        out_dir = REPO / "projects" / project / "assets" / "images" / "archival"
    if manifest is None and project:
        manifest = REPO / "projects" / project / "artifacts" / "wikimedia_manifest.json"

    if out_dir is None or manifest is None:
        raise ValueError(
            "Config must set either `project:` (for default paths) "
            "or both `out_dir:` and `manifest:` explicitly."
        )

    return Path(out_dir), Path(manifest)


def _safe_name(title: str) -> str:
    cleaned = title.replace("File:", "", 1)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._")
    return cleaned[:120] or "untitled"


def _matches_keep_filter(title: str, keep_keywords: list[str]) -> bool:
    if not keep_keywords:
        return True
    lower = title.lower()
    return any(kw.lower() in lower for kw in keep_keywords)


def _candidate_mime(cand: Candidate) -> str:
    return (cand.extra or {}).get("mime", "").lower()


def _candidate_title(cand: Candidate) -> str:
    return (cand.extra or {}).get("title") or cand.source_id or "untitled"


def _manifest_entry(
    cand: Candidate,
    dest: Path,
    repo: Path,
) -> dict[str, Any]:
    try:
        rel_path = dest.relative_to(repo).as_posix()
    except ValueError:
        rel_path = str(dest)
    return {
        "title": _candidate_title(cand),
        "path": rel_path,
        "size_bytes": dest.stat().st_size,
        "mime": _candidate_mime(cand),
        "width": cand.width or None,
        "height": cand.height or None,
        "source_url": cand.source_url,
        "license_name": cand.license,
        "image_description": (cand.source_tags or "")[:300],
    }


def fetch(
    config: dict[str, Any],
    *,
    clean: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the fetcher per the config. Returns a summary dict."""
    queries: list[str] = list(config.get("queries") or [])
    if not queries:
        raise ValueError("Config must contain a non-empty `queries:` list.")

    keep_keywords: list[str] = list(config.get("keep_keywords") or [])
    mime_allow = tuple(
        m.lower() for m in (config.get("mime_allow") or DEFAULT_MIME_ALLOW)
    )
    per_query_limit = int(config.get("per_query_limit") or DEFAULT_PER_QUERY_LIMIT)
    min_width = int(config.get("min_width") or 0)

    out_dir, manifest_path = _resolve_paths(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing manifest (additive merge).
    existing: list[dict[str, Any]] = []
    if not clean and manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                print(
                    f"[fetch_archival] manifest {manifest_path} is not a list; "
                    f"starting fresh",
                    file=sys.stderr,
                )
                existing = []
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"[fetch_archival] could not read existing manifest "
                f"({exc}); starting fresh",
                file=sys.stderr,
            )
            existing = []
    existing_titles = {entry.get("title") for entry in existing}

    ws = WikimediaSource()
    filters = SearchFilters(
        kind="image",
        per_page=per_query_limit,
        page=1,
        min_width=min_width or None,
        min_duration=None,
        max_duration=None,
        orientation=None,
    )

    seen: dict[str, Candidate] = {}
    query_errors: list[tuple[str, str]] = []
    for q in queries:
        try:
            candidates = ws.search(q, filters)
        except Exception as exc:
            query_errors.append((q, str(exc)))
            print(
                f"[fetch_archival] query failed: {q!r}: {exc}",
                file=sys.stderr,
            )
            continue
        for cand in candidates:
            title = _candidate_title(cand)
            if title in seen:
                continue
            seen[title] = cand
        print(
            f"[fetch_archival] query {q!r}: {len(candidates)} candidates "
            f"(total unique so far: {len(seen)})"
        )

    # Filter by mime + keep_keywords; skip titles already in manifest.
    plan: list[Candidate] = []
    skipped_filter = 0
    skipped_existing = 0
    for title, cand in seen.items():
        if title in existing_titles:
            skipped_existing += 1
            continue
        if _candidate_mime(cand) not in mime_allow:
            skipped_filter += 1
            continue
        if not _matches_keep_filter(title, keep_keywords):
            skipped_filter += 1
            continue
        plan.append(cand)

    print(
        f"[fetch_archival] plan: {len(plan)} new download(s); "
        f"{skipped_existing} already in manifest; {skipped_filter} filtered out"
    )

    if dry_run:
        for cand in plan:
            print(f"  DRY-RUN would download: {_candidate_title(cand)}")
        return {
            "out_dir": str(out_dir),
            "manifest": str(manifest_path),
            "queries_run": len(queries),
            "query_errors": query_errors,
            "candidates_after_dedupe": len(seen),
            "would_download": len(plan),
            "skipped_existing": skipped_existing,
            "skipped_filter": skipped_filter,
            "dry_run": True,
        }

    downloaded: list[dict[str, Any]] = []
    download_errors: list[tuple[str, str]] = []
    for cand in plan:
        title = _candidate_title(cand)
        mime = _candidate_mime(cand)
        ext = ".jpg" if mime == "image/jpeg" else ".png"
        dest = out_dir / (_safe_name(title) + ext)

        if dest.exists() and dest.stat().st_size > 0:
            # Found on disk but missing from manifest — capture it.
            downloaded.append(_manifest_entry(cand, dest, REPO))
            print(f"  found existing {dest.name} ({dest.stat().st_size // 1024} KiB)")
            continue

        try:
            ws.download(cand, dest)
        except Exception as exc:
            download_errors.append((title, str(exc)))
            print(f"  FAIL download {title}: {exc}", file=sys.stderr)
            # Clean up partial file if any.
            if dest.exists() and dest.stat().st_size == 0:
                dest.unlink(missing_ok=True)
            continue
        downloaded.append(_manifest_entry(cand, dest, REPO))
        print(f"  saved {dest.name} ({dest.stat().st_size // 1024} KiB)")

    final_manifest = existing + downloaded
    manifest_path.write_text(
        json.dumps(final_manifest, indent=2), encoding="utf-8"
    )
    print(
        f"\n[fetch_archival] wrote {len(final_manifest)} manifest entries "
        f"({len(downloaded)} new) -> {manifest_path}"
    )

    return {
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "queries_run": len(queries),
        "query_errors": query_errors,
        "candidates_after_dedupe": len(seen),
        "downloaded": len(downloaded),
        "download_errors": download_errors,
        "skipped_existing": skipped_existing,
        "skipped_filter": skipped_filter,
        "manifest_total": len(final_manifest),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Wikimedia Commons images for a project via the "
            "central rate-limited WikimediaSource adapter."
        ),
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to YAML or JSON config (see module docstring for schema).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Ignore any existing manifest at the destination. "
        "Default: additive merge.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the plan without downloading.",
    )
    args = parser.parse_args(argv)

    config_path = args.config.resolve()
    if not config_path.is_file():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        config = _load_config(config_path)
    except Exception as exc:
        print(f"failed to load config {config_path}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(config, dict):
        print(f"config root must be a mapping, got {type(config).__name__}", file=sys.stderr)
        return 2

    try:
        summary = fetch(config, clean=args.clean, dry_run=args.dry_run)
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    print("\n" + json.dumps(summary, indent=2, default=str))

    # Exit code: 1 if any query OR download produced errors, else 0.
    if summary.get("query_errors") or summary.get("download_errors"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
