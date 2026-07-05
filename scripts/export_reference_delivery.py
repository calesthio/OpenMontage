"""Export a reviewed reference-video render into a local delivery package."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


APPROVAL_PHRASE = "APPROVE FINAL DELIVERY"


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("render report must be a JSON object")
    return data


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-final"


def _resolve_project_path(project_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def _latest_render_report(project_dir: Path) -> Path | None:
    candidates = [
        path
        for path in (project_dir / "artifacts" / "reference-render").glob("*-render-report.json")
        if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def _delivery_dir(
    *,
    project_dir: Path,
    report: dict[str, Any],
    render_report_path: Path,
    output_dir: str | Path | None,
) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser()
        if not path.is_absolute():
            path = project_dir / path
        return path.resolve()
    output_path = Path(str(report.get("output_path") or render_report_path.stem))
    return (project_dir / "deliveries" / _safe_slug(output_path.stem)).resolve()


def _validate_report(report: dict[str, Any], project_dir: Path) -> Path:
    if report.get("status") != "rendered" or report.get("dry_run") is not False:
        raise ValueError("delivery export requires a non-dry-run rendered report")
    output_value = str(report.get("output_path") or "").strip()
    if not output_value:
        raise ValueError("render report has no final MP4 output_path")
    final_video = _resolve_project_path(project_dir, output_value)
    if not final_video.is_file():
        raise ValueError(f"final MP4 does not exist: {final_video}")
    return final_video


def _copy_file(source: Path, destination: Path, role: str) -> dict[str, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "role": role,
        "filename": destination.name,
        "path": str(destination),
        "source_path": str(source),
    }


def _copy_optional_project_path(
    *,
    report: dict[str, Any],
    project_dir: Path,
    delivery_dir: Path,
    key: str,
    filename: str,
    role: str,
) -> dict[str, str] | None:
    value = str(report.get(key) or "").strip()
    if not value:
        return None
    source = _resolve_project_path(project_dir, value)
    if not source.is_file():
        return None
    return _copy_file(source, delivery_dir / filename, role)


def _manifest(
    *,
    project_dir: Path,
    delivery_dir: Path,
    render_report_path: Path,
    report: dict[str, Any],
    final_video_path: Path,
    included_files: list[dict[str, str]],
    reviewer: str,
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "status": "ready_for_distribution",
        "project_dir": str(project_dir),
        "delivery_dir": str(delivery_dir),
        "video_path": str(delivery_dir / final_video_path.name),
        "source_render_report_path": str(render_report_path),
        "human_review": {
            "required": True,
            "approval_phrase": APPROVAL_PHRASE,
            "reviewer": reviewer,
        },
        "render": {
            "output_path": str(final_video_path),
            "burned_subtitles": bool(report.get("burned_subtitles")),
            "mixed_audio": bool(report.get("mixed_audio")),
            "clip_count": report.get("clip_count"),
            "total_duration": report.get("total_duration"),
        },
        "included_files": included_files,
        "safety": {
            "local_only": True,
            "paid_generation_started_by_export": False,
            "requires_team_authorized_assets": True,
        },
    }


def _readme(manifest: dict[str, Any]) -> str:
    render = manifest["render"]
    lines = [
        "# Reference Video Delivery Package",
        "",
        "## Deliverable",
        f"- Final video: `{Path(manifest['video_path']).name}`",
        f"- Duration: `{render.get('total_duration', 'n/a')}`",
        f"- Clip count: `{render.get('clip_count', 'n/a')}`",
        f"- Burned subtitles: `{render.get('burned_subtitles')}`",
        f"- Mixed audio: `{render.get('mixed_audio')}`",
        "",
        "## Review Gate",
        "- This package is exported only after a human final-render review phrase.",
        "- Play the final MP4 before upload or distribution.",
        "- Confirm all likeness, face, product, music, and source assets are team-authorized.",
        "",
        "## Files",
    ]
    for item in manifest["included_files"]:
        lines.append(f"- `{item['filename']}` — {item['role']}")
    return "\n".join(lines).rstrip() + "\n"


def export_delivery_package(
    *,
    project_dir: str | Path,
    render_report_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    reviewer: str = "operator",
    approval_phrase: str = "",
) -> dict[str, Any]:
    if approval_phrase != APPROVAL_PHRASE:
        raise ValueError(f"approval_phrase must be exactly {APPROVAL_PHRASE!r}")

    project_path = Path(project_dir).expanduser().resolve()
    report_path = (
        Path(render_report_path).expanduser().resolve()
        if render_report_path
        else _latest_render_report(project_path)
    )
    if not report_path:
        raise ValueError("no rendered report found under artifacts/reference-render")

    report = _load_json(report_path)
    final_video = _validate_report(report, project_path)
    delivery_path = _delivery_dir(
        project_dir=project_path,
        report=report,
        render_report_path=report_path,
        output_dir=output_dir,
    )
    delivery_path.mkdir(parents=True, exist_ok=True)

    included_files = [
        _copy_file(final_video, delivery_path / final_video.name, "final_video"),
        _copy_file(report_path, delivery_path / "render-report.json", "render_report_json"),
    ]
    markdown_report = report_path.with_suffix(".md")
    if markdown_report.is_file():
        included_files.append(
            _copy_file(markdown_report, delivery_path / "render-report.md", "render_report_markdown")
        )

    for optional_file in [
        _copy_optional_project_path(
            report=report,
            project_dir=project_path,
            delivery_dir=delivery_path,
            key="final_edit_plan_path",
            filename="final-edit-plan.json",
            role="final_edit_plan",
        ),
        _copy_optional_project_path(
            report=report,
            project_dir=project_path,
            delivery_dir=delivery_path,
            key="subtitle_path",
            filename="subtitles.srt",
            role="subtitle_sidecar",
        ),
        _copy_optional_project_path(
            report=report,
            project_dir=project_path,
            delivery_dir=delivery_path,
            key="mixed_audio_path",
            filename="mixed-audio.wav",
            role="mixed_audio",
        ),
    ]:
        if optional_file:
            included_files.append(optional_file)

    manifest = _manifest(
        project_dir=project_path,
        delivery_dir=delivery_path,
        render_report_path=report_path,
        report=report,
        final_video_path=final_video,
        included_files=included_files,
        reviewer=reviewer,
    )
    manifest_path = delivery_path / "delivery-manifest.json"
    readme_path = delivery_path / "README.md"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    readme_path.write_text(_readme(manifest), encoding="utf-8")
    manifest["included_files"].extend(
        [
            {
                "role": "delivery_manifest",
                "filename": manifest_path.name,
                "path": str(manifest_path),
                "source_path": str(manifest_path),
            },
            {
                "role": "delivery_readme",
                "filename": readme_path.name,
                "path": str(readme_path),
                "source_path": str(readme_path),
            },
        ]
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": manifest["status"],
        "delivery_dir": str(delivery_path),
        "manifest_path": str(manifest_path),
        "readme_path": str(readme_path),
        "video_path": manifest["video_path"],
        "included_files": manifest["included_files"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    parser.add_argument("--render-report", help="Specific render-report JSON to export")
    parser.add_argument("--output-dir", help="Optional delivery directory override")
    parser.add_argument("--reviewer", default="operator", help="Human reviewer name")
    parser.add_argument("--approval-phrase", required=True, help=f"Must equal {APPROVAL_PHRASE!r}")
    args = parser.parse_args(argv)
    result = export_delivery_package(
        project_dir=args.project_dir,
        render_report_path=args.render_report,
        output_dir=args.output_dir,
        reviewer=args.reviewer,
        approval_phrase=args.approval_phrase,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
