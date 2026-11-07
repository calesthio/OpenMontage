"""Scaffold a new episode folder by copying the first_video structure.

Creates projects/<slug>/ with the standard sub-directories (images/, audio/,
qc/, manifests/, script/, footage/, prompts/) so future releases reuse the
pilot layout without hardcoding pilot file names or copying pilot media.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = REPO_ROOT / "projects"
PILOT_TEMPLATE = PROJECTS_DIR / "pilot" / "first_video"

# Directories to recreate (empty) for a new episode.
EMPTY_DIRS = ("images", "audio", "qc", "manifests", "script", "footage", "prompts")


def slugify(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug or "episode"


def scaffold(topic: str, force: bool = False) -> Path:
    slug = slugify(topic)
    target = PROJECTS_DIR / "pilot" / slug

    if target.exists() and not force:
        raise FileExistsError(f"episode folder already exists: {target}")

    if not PILOT_TEMPLATE.exists():
        raise FileNotFoundError(f"pilot template not found: {PILOT_TEMPLATE}")

    target.mkdir(parents=True, exist_ok=True)

    for d in EMPTY_DIRS:
        (target / d).mkdir(parents=True, exist_ok=True)

    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new episode folder modeled on pilot/first_video."
    )
    parser.add_argument("topic", help="Episode topic (used to derive the folder slug).")
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing folder."
    )
    args = parser.parse_args()
    try:
        created = scaffold(args.topic, force=args.force)
    except (FileExistsError, FileNotFoundError) as exc:
        raise SystemExit(str(exc))
    print(f"scaffolded: {created}")


if __name__ == "__main__":
    main()
