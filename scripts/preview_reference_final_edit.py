"""Preview final-edit readiness from a Seedance batch artifact.

This script is local-only. It does not render a final video; it turns a
Seedance dry-run or sample-result artifact into a final edit plan and reports
which generated clips are still missing.
"""

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


def _load_batch(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("seedance batch artifact must be a JSON object")
    return data


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-final-edit"


def _source_name(batch: dict[str, Any]) -> str:
    source = batch.get("source") or {}
    return _safe_slug(
        Path(str(source.get("local_video_path") or source.get("input") or "reference")).stem
    )


def _clip_path(project_dir: Path, task: dict[str, Any]) -> Path:
    output_path = Path(str(task.get("output_path", "")).strip())
    if not output_path:
        output_path = (
            project_dir
            / "assets"
            / "video"
            / f"{_safe_slug(str(task.get('scene_id') or task.get('task_id') or 'clip'))}.mp4"
        )
    if not output_path.is_absolute():
        parts = output_path.parts
        if project_dir.name in parts:
            project_name_index = len(parts) - 1 - list(reversed(parts)).index(project_dir.name)
            suffix = parts[project_name_index + 1 :]
            if suffix:
                output_path = project_dir.joinpath(*suffix)
            else:
                output_path = project_dir
        else:
            output_path = project_dir / output_path
    return output_path.resolve()


def _task_duration(task: dict[str, Any], fallback: str) -> float:
    value = task.get("duration", fallback)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_final_edit_plan(
    *,
    seedance_batch: dict[str, Any],
    project_dir: str | Path,
    render_runtime: str = "ffmpeg",
) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    tasks = [task for task in seedance_batch.get("tasks") or [] if isinstance(task, dict)]
    timeline: list[dict[str, Any]] = []
    missing_clips: list[dict[str, str]] = []
    ready_clips: list[dict[str, str]] = []
    cursor = 0.0
    fallback_duration = str(seedance_batch.get("duration", "0"))

    for index, task in enumerate(tasks, start=1):
        clip_path = _clip_path(project_path, task)
        duration = _task_duration(task, fallback_duration)
        clip_exists = clip_path.is_file()
        entry = {
            "order": index,
            "scene_id": str(task.get("scene_id") or f"s{index}"),
            "task_id": str(task.get("task_id") or f"task-{index}"),
            "clip_path": str(clip_path),
            "clip_exists": clip_exists,
            "timeline_start": round(cursor, 3),
            "timeline_end": round(cursor + duration, 3),
            "duration": duration,
            "script_text": str(task.get("script_text", "")).strip(),
            "subtitle_text": str(task.get("script_text", "")).strip(),
            "prompt": str(task.get("prompt", "")).strip(),
            "transition": "cut",
            "provider_tool": str(task.get("provider_tool", seedance_batch.get("provider_tool", ""))),
        }
        timeline.append(entry)
        clip_ref = {
            "scene_id": entry["scene_id"],
            "task_id": entry["task_id"],
            "clip_path": entry["clip_path"],
        }
        if clip_exists:
            ready_clips.append(clip_ref)
        else:
            missing_clips.append(clip_ref)
        cursor += duration

    status = "ready_for_compose" if tasks and not missing_clips else "waiting_for_generated_clips"
    return {
        "version": "1.0",
        "status": status,
        "source": seedance_batch.get("source", {}),
        "render_runtime": render_runtime,
        "provider": seedance_batch.get("provider"),
        "provider_tool": seedance_batch.get("provider_tool"),
        "dry_run_source": bool(seedance_batch.get("dry_run", False)),
        "paid_generation_started": bool(
            (seedance_batch.get("approval") or {}).get("paid_generation_started", False)
        ),
        "timeline": timeline,
        "ready_clips": ready_clips,
        "missing_clips": missing_clips,
        "ready_clip_count": len(ready_clips),
        "missing_clip_count": len(missing_clips),
        "total_duration": round(cursor, 3),
        "compose_handoff": {
            "video_paths": [entry["clip_path"] for entry in timeline],
            "subtitle_strategy": "use timeline[].subtitle_text",
            "output_path": str(project_path / "renders" / "reference-final.mp4"),
            "requires_all_clips": True,
        },
        "next_step": "compose_final_video" if status == "ready_for_compose" else "generate_missing_clips",
    }


def _markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Reference Final Edit Preview",
        "",
        f"- Status: `{plan['status']}`",
        f"- Ready clips: `{plan['ready_clip_count']}`",
        f"- Missing clips: `{plan['missing_clip_count']}`",
        f"- Total duration: `{plan['total_duration']}s`",
        f"- Paid generation started: `{plan['paid_generation_started']}`",
        "",
        "## Timeline",
    ]
    for entry in plan["timeline"]:
        mark = "✅" if entry["clip_exists"] else "⏳"
        lines.append(
            f"- {mark} `{entry['scene_id']}` {entry['timeline_start']}s–{entry['timeline_end']}s "
            f"`{entry['clip_path']}`"
        )
    lines.extend(["", "## Missing Clips"])
    if plan["missing_clips"]:
        for clip in plan["missing_clips"]:
            lines.append(f"- `{clip['scene_id']}` `{clip['clip_path']}`")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Compose Handoff",
            f"- Render runtime: `{plan['render_runtime']}`",
            f"- Output path: `{plan['compose_handoff']['output_path']}`",
            "- This preview does not render or call paid providers.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_final_edit_preview(
    *,
    seedance_batch_path: str | Path,
    project_dir: str | Path,
    output_dir: str | Path | None = None,
    render_runtime: str = "ffmpeg",
) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    batch = _load_batch(seedance_batch_path)
    plan = build_final_edit_plan(
        seedance_batch=batch,
        project_dir=project_path,
        render_runtime=render_runtime,
    )
    out_dir = Path(output_dir) if output_dir else project_path / "artifacts" / "reference-final-edit"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_name = _source_name(batch)
    json_path = out_dir / f"{source_name}-final-edit-plan.json"
    markdown_path = out_dir / f"{source_name}-final-edit-preview.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(plan), encoding="utf-8")
    return {
        "final_edit_plan": plan,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seedance_batch_path", help="Seedance dry-run or sample-result JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument("--output-dir", help="Optional final-edit artifact output directory")
    parser.add_argument(
        "--render-runtime",
        choices=["ffmpeg", "remotion", "hyperframes"],
        default="ffmpeg",
        help="Preferred downstream compose runtime to record. Defaults to ffmpeg.",
    )
    args = parser.parse_args(argv)

    try:
        payload = write_final_edit_preview(
            seedance_batch_path=args.seedance_batch_path,
            project_dir=args.project_dir,
            output_dir=args.output_dir,
            render_runtime=args.render_runtime,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
