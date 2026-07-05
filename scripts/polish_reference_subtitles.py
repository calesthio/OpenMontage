"""Create a reviewable subtitle-polish plan for a reference final edit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.subtitle.doubao_subtitle_polish import DoubaoSubtitlePolish


def _load_plan(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("final edit plan must be a JSON object")
    return data


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-subtitles"


def _timeline_entries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = plan.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("final edit plan timeline is empty")
    entries = [entry for entry in timeline if isinstance(entry, dict)]
    if len(entries) != len(timeline):
        raise ValueError("final edit plan timeline contains invalid entries")
    return sorted(entries, key=lambda entry: int(entry.get("order") or 0))


def _output_path(plan_path: Path, project_dir: Path, output_dir: str | None) -> Path:
    out_dir = (
        Path(output_dir).expanduser()
        if output_dir
        else project_dir / "artifacts" / "reference-subtitles"
    )
    if not out_dir.is_absolute():
        out_dir = project_dir / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_slug(plan_path.stem.replace("-final-edit-plan", ""))
    return out_dir / f"{stem}-subtitle-polish-plan.json"


def build_subtitle_polish_plan(
    *,
    final_edit_plan_path: str | Path,
    project_dir: str | Path,
    output_dir: str | None = None,
    live: bool = False,
    allow_paid_api: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    if live and not allow_paid_api:
        raise ValueError("Live Doubao subtitle polish requires --allow-paid-api")

    project_path = Path(project_dir).expanduser().resolve()
    plan_path = Path(final_edit_plan_path).expanduser().resolve()
    plan = _load_plan(plan_path)
    dry_run = not live

    timeline: list[dict[str, Any]] = []
    api_called = False
    for entry in _timeline_entries(plan):
        text = str(entry.get("subtitle_text") or entry.get("script_text") or "").strip()
        if not text:
            continue
        start = float(entry.get("timeline_start", 0))
        end = float(entry.get("timeline_end", entry.get("duration", 0)))
        inputs: dict[str, Any] = {
            "text": text,
            "start": start,
            "end": end,
            "dry_run": dry_run,
            "max_chars_per_line": 12,
            "max_lines_per_cue": 2,
            "min_duration": 0.8,
            "max_duration": 2.2,
        }
        if model:
            inputs["model"] = model
        result = DoubaoSubtitlePolish().execute(inputs)
        if not result.success:
            scene_id = entry.get("scene_id") or entry.get("order")
            raise RuntimeError(f"subtitle polish failed for {scene_id}: {result.error}")
        data = result.data if isinstance(result.data, dict) else {}
        api_called = api_called or bool(data.get("api_called"))
        timeline.append(
            {
                "order": entry.get("order"),
                "scene_id": entry.get("scene_id"),
                "timeline_start": start,
                "timeline_end": end,
                "source_text": text,
                "cue_count": data.get("cue_count", 0),
                "cues": data.get("cues", []),
                "notes": data.get("notes", []),
                "prompt": data.get("prompt"),
            }
        )

    if not timeline:
        raise ValueError("no subtitle_text or script_text found in final edit plan timeline")

    artifact = {
        "version": "1.0",
        "provider": "doubao",
        "mode": "live" if live else "dry_run",
        "dry_run": dry_run,
        "api_called": api_called,
        "model": model,
        "final_edit_plan_path": str(plan_path),
        "timeline": timeline,
        "review_notes": [
            "Review cue text before burning subtitles into final video.",
            "Timing is allocated locally; Doubao is not trusted for exact timestamps.",
            "Use --live --allow-paid-api only after approving a paid Doubao call.",
        ],
    }
    path = _output_path(plan_path, project_path, output_dir)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "dry_run": dry_run,
        "subtitle_polish_plan_path": str(path),
        "subtitle_polish_plan": artifact,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_edit_plan_path")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--model", help="Optional Doubao/Ark model or endpoint id")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call Doubao/Ark instead of local dry-run planning",
    )
    parser.add_argument(
        "--allow-paid-api",
        action="store_true",
        help="Required together with --live to allow a paid API call",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_subtitle_polish_plan(
            final_edit_plan_path=args.final_edit_plan_path,
            project_dir=args.project_dir,
            output_dir=args.output_dir,
            live=args.live,
            allow_paid_api=args.allow_paid_api,
            model=args.model,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
