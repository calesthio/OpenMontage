"""Create a local final-render review package before delivery export."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from fractions import Fraction
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


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _command(*parts: str | Path) -> str:
    return " ".join(_quote(part) for part in parts)


def _resolve_project_path(project_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def _latest_render_report(project_dir: Path) -> Path | None:
    report_dir = project_dir / "artifacts" / "reference-render"
    candidates = [
        path for path in report_dir.glob("*-render-report.json") if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def _validate_report(report: dict[str, Any], project_dir: Path) -> Path:
    if report.get("status") != "rendered" or report.get("dry_run") is not False:
        raise ValueError("final review requires a non-dry-run rendered report")
    output_value = str(report.get("output_path") or "").strip()
    if not output_value:
        raise ValueError("render report has no final MP4 output_path")
    final_video = _resolve_project_path(project_dir, output_value)
    if not final_video.is_file():
        raise ValueError(f"final MP4 does not exist: {final_video}")
    return final_video


def _report_paths(
    *,
    project_dir: Path,
    render_report_path: Path,
    output_dir: str | Path | None,
) -> tuple[Path, Path]:
    report_dir = (
        Path(output_dir).expanduser()
        if output_dir
        else project_dir / "artifacts" / "reference-final-review"
    )
    if not report_dir.is_absolute():
        report_dir = project_dir / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_slug(render_report_path.stem.replace("-render-report", ""))
    return (
        report_dir / f"{stem}-final-review.json",
        report_dir / f"{stem}-final-review.md",
    )


def _fraction_to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        fraction = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    if not fraction.denominator:
        return None
    return round(float(fraction), 3)


def _probe_media(final_video: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {
            "ffprobe_available": False,
            "probe_status": "unavailable",
        }

    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(final_video),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {
            "ffprobe_available": True,
            "probe_status": "failed",
            "probe_error": completed.stderr.strip(),
        }

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "ffprobe_available": True,
            "probe_status": "failed",
            "probe_error": "ffprobe returned invalid JSON",
        }

    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
        ),
        {},
    )
    format_info = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    duration_value = format_info.get("duration")
    bitrate_value = format_info.get("bit_rate")
    return {
        "ffprobe_available": True,
        "probe_status": "ok",
        "duration_seconds": _safe_float(duration_value),
        "width": _safe_int(video_stream.get("width")),
        "height": _safe_int(video_stream.get("height")),
        "fps": _fraction_to_float(video_stream.get("avg_frame_rate")),
        "bitrate_bps": _safe_int(bitrate_value),
        "video_codec": video_stream.get("codec_name"),
    }


def _safe_float(value: Any) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _checklist(report: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "id": "play_final_mp4",
            "label": "Play the final MP4 from start to finish.",
            "status": "needs_human_review",
        },
        {
            "id": "verify_subtitles",
            "label": "Verify burned subtitles are readable, correctly timed, and not garbled.",
            "status": "needs_human_review"
            if report.get("burned_subtitles")
            else "needs_attention",
        },
        {
            "id": "verify_audio_mix",
            "label": "Verify speech, music, and original audio balance on the final MP4.",
            "status": "needs_human_review"
            if report.get("mixed_audio")
            else "not_applicable_or_needs_attention",
        },
        {
            "id": "verify_authorized_assets",
            "label": "Confirm all likeness, face, source, product, music, and voice assets are team-authorized.",
            "status": "needs_human_review",
        },
        {
            "id": "approve_delivery_export",
            "label": f"Export delivery only with exact phrase: {APPROVAL_PHRASE}.",
            "status": "blocked_until_human_approval",
        },
    ]


def _export_command(project_dir: Path, render_report_path: Path, reviewer: str) -> str:
    return _command(
        ".venv/bin/python",
        "scripts/export_reference_delivery.py",
        project_dir,
        "--render-report",
        render_report_path,
        "--reviewer",
        reviewer,
        "--approval-phrase",
        APPROVAL_PHRASE,
    )


def _review_payload(
    *,
    project_dir: Path,
    render_report_path: Path,
    report: dict[str, Any],
    final_video: Path,
    json_report_path: Path,
    markdown_report_path: Path,
    reviewer: str,
) -> dict[str, Any]:
    media_probe = _probe_media(final_video)
    return {
        "version": "1.0",
        "status": "final_review_ready_for_delivery",
        "project_dir": str(project_dir),
        "source_render_report_path": str(render_report_path),
        "review_report_path": str(json_report_path),
        "markdown_report_path": str(markdown_report_path),
        "render": {
            "output_path": str(final_video),
            "exists": final_video.is_file(),
            "file_size_bytes": final_video.stat().st_size,
            "duration_seconds": media_probe.get("duration_seconds")
            or report.get("total_duration"),
            "width": media_probe.get("width"),
            "height": media_probe.get("height"),
            "fps": media_probe.get("fps"),
            "bitrate_bps": media_probe.get("bitrate_bps"),
            "video_codec": media_probe.get("video_codec"),
            "burned_subtitles": bool(report.get("burned_subtitles")),
            "subtitle_path": report.get("subtitle_path"),
            "mixed_audio": bool(report.get("mixed_audio")),
            "mixed_audio_path": report.get("mixed_audio_path"),
            "quality_profile": report.get("quality_profile"),
            "video_crf": report.get("video_crf"),
            "video_preset": report.get("video_preset"),
            "clip_count": report.get("clip_count"),
            "total_duration": report.get("total_duration"),
            "ffprobe": media_probe,
        },
        "human_review": {
            "required": True,
            "reviewer": reviewer,
            "delivery_export_phrase": APPROVAL_PHRASE,
        },
        "checklist": _checklist(report),
        "next_export_command": _export_command(project_dir, render_report_path, reviewer),
        "safety": {
            "local_only": True,
            "network_calls_started": False,
            "paid_generation_started_by_review": False,
            "delivery_export_started_by_review": False,
            "requires_team_authorized_assets": True,
        },
    }


def _markdown(payload: dict[str, Any]) -> str:
    render = payload["render"]
    lines = [
        "# Final Render Review",
        "",
        f"- Status: `{payload['status']}`",
        f"- Final MP4: `{render['output_path']}`",
        f"- File size: `{render['file_size_bytes']}` bytes",
        f"- Duration: `{render.get('duration_seconds', 'n/a')}`",
        f"- Resolution: `{render.get('width') or 'n/a'}x{render.get('height') or 'n/a'}`",
        f"- FPS: `{render.get('fps', 'n/a')}`",
        f"- Bitrate: `{render.get('bitrate_bps', 'n/a')}`",
        f"- Quality: `{render.get('quality_profile', 'n/a')}`",
        f"- Burned subtitles: `{render['burned_subtitles']}`",
        f"- Subtitle sidecar: `{render.get('subtitle_path') or 'n/a'}`",
        f"- Mixed audio: `{render['mixed_audio']}`",
        "",
        "## Checklist",
    ]
    for item in payload["checklist"]:
        lines.append(f"- `{item['status']}` — {item['label']}")
    lines.extend(
        [
            "",
            "## Next Step",
            "- Play and manually review the final MP4 before export.",
            f"- Delivery export remains locked behind `{APPROVAL_PHRASE}`.",
            f"- Command: `{payload['next_export_command']}`",
            "",
            "## Safety",
            "- Local review only; no network calls and no paid generation.",
            "- Do not publish until all likeness and source assets are confirmed team-authorized.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def review_final_render(
    *,
    project_dir: str | Path,
    render_report_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    reviewer: str = "operator",
) -> dict[str, Any]:
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
    json_report_path, markdown_report_path = _report_paths(
        project_dir=project_path,
        render_report_path=report_path,
        output_dir=output_dir,
    )
    payload = _review_payload(
        project_dir=project_path,
        render_report_path=report_path,
        report=report,
        final_video=final_video,
        json_report_path=json_report_path,
        markdown_report_path=markdown_report_path,
        reviewer=reviewer,
    )
    json_report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_report_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    parser.add_argument("--render-report", help="Specific render-report JSON to review")
    parser.add_argument("--output-dir", help="Optional review artifact directory override")
    parser.add_argument("--reviewer", default="operator", help="Human reviewer name")
    args = parser.parse_args(argv)
    result = review_final_render(
        project_dir=args.project_dir,
        render_report_path=args.render_report,
        output_dir=args.output_dir,
        reviewer=args.reviewer,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
