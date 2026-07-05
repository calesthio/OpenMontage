"""Check local readiness before running the reference-video demo workflow."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.env_loader import load_dotenv_files


SEEDANCE_ENV_BY_PROVIDER = {
    "runninghub": ["RUNNINGHUB_API_KEY"],
    "fal": ["FAL_KEY"],
    "replicate": ["REPLICATE_API_TOKEN"],
}
VISION_ENV_KEYS = ["DOUBAO_VISION_API_KEY", "ARK_API_KEY"]


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "www."))


def _configured(keys: list[str]) -> bool:
    return any(bool(os.environ.get(key, "").strip()) for key in keys)


def _project_dir_status(path: Path) -> dict[str, Any]:
    path.mkdir(parents=True, exist_ok=True)
    writable = os.access(path, os.W_OK)
    return {
        "path": str(path),
        "exists": path.exists(),
        "writable": writable,
    }


def _source_status(source: str) -> dict[str, Any]:
    if _is_url(source):
        return {
            "input": source,
            "type": "url",
            "exists": None,
            "fallback_may_be_required": True,
            "note": "URL ingestion may require a local video fallback if the platform blocks download.",
        }
    path = Path(source).expanduser()
    return {
        "input": source,
        "type": "local_file",
        "path": str(path),
        "exists": path.is_file(),
        "fallback_may_be_required": False,
    }


def _ffmpeg_status() -> dict[str, Any]:
    return {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
    }


def _provider_status(*, reverse_prompts: bool, seedance_provider: str) -> dict[str, Any]:
    seedance_keys = SEEDANCE_ENV_BY_PROVIDER[seedance_provider]
    return {
        "seedance": {
            "provider": seedance_provider,
            "required": False,
            "configured": _configured(seedance_keys),
            "env_keys": seedance_keys,
            "note": "Needed only when running paid Seedance generation, not for local demo dry-runs.",
        },
        "vision": {
            "provider": "doubao",
            "required": reverse_prompts,
            "configured": _configured(VISION_ENV_KEYS),
            "env_keys": VISION_ENV_KEYS,
            "note": "Needed only when --reverse-prompts is used.",
        },
    }


def _issues(
    *,
    source: dict[str, Any],
    project_dir: dict[str, Any],
    binaries: dict[str, Any],
    providers: dict[str, Any],
    reverse_prompts: bool,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if source["type"] == "local_file" and not source["exists"]:
        issues.append(
            {
                "level": "blocker",
                "code": "missing_local_source",
                "message": "Local reference video file does not exist.",
            }
        )
    if not project_dir["writable"]:
        issues.append(
            {
                "level": "blocker",
                "code": "project_dir_not_writable",
                "message": "Project directory is not writable.",
            }
        )
    if not binaries["ffmpeg"] or not binaries["ffprobe"]:
        issues.append(
            {
                "level": "blocker",
                "code": "missing_ffmpeg",
                "message": "ffmpeg and ffprobe are required for local analysis/composition.",
            }
        )
    if reverse_prompts and not providers["vision"]["configured"]:
        issues.append(
            {
                "level": "blocker",
                "code": "missing_doubao_vision_key",
                "message": "Set DOUBAO_VISION_API_KEY or ARK_API_KEY before using --reverse-prompts.",
            }
        )
    if not providers["seedance"]["configured"]:
        issues.append(
            {
                "level": "warning",
                "code": "seedance_key_not_configured",
                "message": "Seedance paid generation is not configured; local dry-runs still work.",
            }
        )
    return issues


def _overall_status(issues: list[dict[str, str]]) -> str:
    if any(issue["level"] == "blocker" for issue in issues):
        return "blocked"
    if issues:
        return "degraded"
    return "ready"


def run_preflight(
    *,
    source: str,
    project_dir: str | Path,
    reverse_prompts: bool = False,
    seedance_provider: str = "runninghub",
    root: str | Path | None = None,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve() if root else ROOT
    load_dotenv_files(root_path)

    project_path = Path(project_dir).expanduser().resolve()
    source_info = _source_status(source)
    project_info = _project_dir_status(project_path)
    binary_info = _ffmpeg_status()
    provider_info = _provider_status(
        reverse_prompts=reverse_prompts,
        seedance_provider=seedance_provider,
    )
    issues = _issues(
        source=source_info,
        project_dir=project_info,
        binaries=binary_info,
        providers=provider_info,
        reverse_prompts=reverse_prompts,
    )
    return {
        "status": _overall_status(issues),
        "source": source_info,
        "project_dir": project_info,
        "binaries": binary_info,
        "providers": provider_info,
        "issues": issues,
        "safety": {
            "secrets_redacted": True,
            "network_calls_started": False,
            "paid_generation_started": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local reference video path or video URL")
    parser.add_argument("--project-dir", required=True, help="Output project directory")
    parser.add_argument("--reverse-prompts", action="store_true")
    parser.add_argument(
        "--seedance-provider",
        choices=["runninghub", "fal", "replicate"],
        default="runninghub",
    )
    args = parser.parse_args(argv)
    payload = run_preflight(
        source=args.source,
        project_dir=args.project_dir,
        reverse_prompts=args.reverse_prompts,
        seedance_provider=args.seedance_provider,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
