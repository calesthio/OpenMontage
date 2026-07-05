"""Compose a ready reference final-edit plan into a local final video."""

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

from tools.audio.audio_mixer import AudioMixer
from tools.subtitle.oral_subtitle_planner import OralSubtitlePlanner
from tools.subtitle.subtitle_gen import SubtitleGen
from tools.video.video_compose import VideoCompose
from tools.video.video_stitch import VideoStitch


QUALITY_PROFILES: dict[str, dict[str, Any]] = {
    "standard": {"crf": 23, "preset": "medium"},
    "high": {"crf": 18, "preset": "medium"},
    "master": {"crf": 16, "preset": "slow"},
}

SUBTITLE_TERMINAL_PUNCTUATION = "，,。.!！?？、；;：:"


def _load_plan(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("final edit plan must be a JSON object")
    return data


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-final"


def _resolve_project_path(project_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def _quality_settings(profile: str) -> dict[str, Any]:
    if profile not in QUALITY_PROFILES:
        allowed = ", ".join(sorted(QUALITY_PROFILES))
        raise ValueError(f"quality must be one of: {allowed}")
    settings = QUALITY_PROFILES[profile]
    return {
        "profile": profile,
        "crf": int(settings["crf"]),
        "preset": str(settings["preset"]),
    }


def _timeline_entries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = plan.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("final edit plan timeline is empty")
    entries = [entry for entry in timeline if isinstance(entry, dict)]
    if len(entries) != len(timeline):
        raise ValueError("final edit plan timeline contains invalid entries")
    return sorted(entries, key=lambda entry: int(entry.get("order") or 0))


def _clip_paths(plan: dict[str, Any], project_dir: Path) -> list[str]:
    clips: list[str] = []
    missing: list[str] = []
    for entry in _timeline_entries(plan):
        clip_value = str(entry.get("clip_path") or "").strip()
        if not clip_value:
            entry_name = entry.get("scene_id") or entry.get("order")
            raise ValueError(f"timeline entry {entry_name} has no clip_path")
        clip_path = _resolve_project_path(project_dir, clip_value)
        if not clip_path.is_file():
            missing.append(str(clip_path))
        clips.append(str(clip_path))
    if missing:
        raise ValueError("missing generated clips: " + ", ".join(missing))
    return clips


def _audio_tracks(plan: dict[str, Any], project_dir: Path) -> list[dict[str, Any]]:
    handoff = plan.get("compose_handoff") if isinstance(plan.get("compose_handoff"), dict) else {}
    raw_tracks = handoff.get("audio_tracks") or plan.get("audio_tracks") or []
    if not isinstance(raw_tracks, list):
        raise ValueError("audio_tracks must be a list")

    tracks: list[dict[str, Any]] = []
    missing: list[str] = []
    for index, raw_track in enumerate(raw_tracks, start=1):
        if not isinstance(raw_track, dict):
            raise ValueError(f"audio track {index} must be an object")
        track_path_value = str(raw_track.get("path") or "").strip()
        if not track_path_value:
            raise ValueError(f"audio track {index} has no path")
        track_path = _resolve_project_path(project_dir, track_path_value)
        if not track_path.is_file():
            missing.append(str(track_path))
        track = dict(raw_track)
        track["path"] = str(track_path)
        track.setdefault("role", "speech")
        tracks.append(track)

    if missing:
        raise ValueError("missing audio tracks: " + ", ".join(missing))
    return tracks


def _output_path(plan: dict[str, Any], project_dir: Path, override: str | None) -> Path:
    if override:
        return _resolve_project_path(project_dir, override)
    handoff = plan.get("compose_handoff") if isinstance(plan.get("compose_handoff"), dict) else {}
    handoff_output = str(handoff.get("output_path") or "").strip()
    if handoff_output:
        return _resolve_project_path(project_dir, handoff_output)
    return (project_dir / "renders" / "reference-final.mp4").resolve()


def _report_paths(
    plan_path: Path, project_dir: Path, output_dir: str | None
) -> tuple[Path, Path]:
    report_dir = (
        Path(output_dir).expanduser()
        if output_dir
        else project_dir / "artifacts" / "reference-render"
    )
    if not report_dir.is_absolute():
        report_dir = project_dir / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_slug(plan_path.stem.replace("-final-edit-plan", ""))
    return (
        report_dir / f"{stem}-render-report.json",
        report_dir / f"{stem}-render-report.md",
    )


def _intermediate_video_path(plan_path: Path, project_dir: Path, suffix: str) -> Path:
    stem = _safe_slug(plan_path.stem.replace("-final-edit-plan", ""))
    path = project_dir / "artifacts" / "reference-render" / f"{stem}-{suffix}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _subtitle_path(plan_path: Path, project_dir: Path) -> Path:
    stem = _safe_slug(plan_path.stem.replace("-final-edit-plan", ""))
    return project_dir / "assets" / "subtitles" / f"{stem}-reference-final.srt"


def _mixed_audio_path(plan_path: Path, project_dir: Path) -> Path:
    stem = _safe_slug(plan_path.stem.replace("-final-edit-plan", ""))
    path = project_dir / "assets" / "audio" / f"{stem}-reference-final-mix.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _subtitle_style() -> dict[str, Any]:
    style: dict[str, Any] = {
        "font": "Hiragino Sans GB",
        "font_size": 12,
        "bold": True,
        "outline_width": 2,
        "shadow": 0,
        "margin_v": 44,
        "alignment": 2,
    }
    system_font_dir = Path("/System/Library/Fonts")
    if system_font_dir.is_dir():
        style["fontsdir"] = str(system_font_dir)
    return style


def _subtitle_segments(plan: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for entry in _timeline_entries(plan):
        text = str(entry.get("subtitle_text") or entry.get("script_text") or "").strip()
        if not text:
            continue
        start = float(entry.get("timeline_start", 0))
        end = float(entry.get("timeline_end", entry.get("duration", 0)))
        result = OralSubtitlePlanner().execute(
            {
                "text": text,
                "start": start,
                "end": end,
                "max_chars_per_line": 12,
                "max_lines_per_cue": 2,
                "min_duration": 0.8,
                "max_duration": 2.2,
            }
        )
        if result.success:
            for cue in (result.data or {}).get("cues", []):
                if isinstance(cue, dict) and str(cue.get("text") or "").strip():
                    segments.append(
                        {
                            "start": float(cue["start"]),
                            "end": float(cue["end"]),
                            "text": str(cue["text"]).strip(),
                        }
                    )
            continue

        chunks = _split_subtitle_text(text)
        segments.extend(_chunks_to_segments(chunks, start=start, end=end))
    return segments


def _subtitle_segments_from_polish_plan(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("subtitle polish plan must be a JSON object")
    timeline = data.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("subtitle polish plan timeline is empty")

    segments: list[dict[str, Any]] = []
    for entry_index, entry in enumerate(timeline, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"subtitle polish timeline entry {entry_index} must be an object")
        cues = entry.get("cues")
        if not isinstance(cues, list):
            raise ValueError(f"subtitle polish timeline entry {entry_index} has no cues list")
        for cue_index, cue in enumerate(cues, start=1):
            if not isinstance(cue, dict):
                raise ValueError(
                    f"subtitle polish cue {entry_index}.{cue_index} must be an object"
                )
            text = str(cue.get("text") or "").strip()
            if not text:
                continue
            try:
                start = float(cue["start"])
                end = float(cue["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"subtitle polish cue {entry_index}.{cue_index} must include numeric start/end"
                ) from exc
            if end <= start:
                raise ValueError(f"subtitle polish cue {entry_index}.{cue_index} has invalid timing")
            segments.append({"start": start, "end": end, "text": text})

    if not segments:
        raise ValueError("subtitle polish plan contains no usable cues")
    return sorted(segments, key=lambda segment: segment["start"])


def _chunks_to_segments(chunks: list[str], *, start: float, end: float) -> list[dict[str, Any]]:
    if not chunks:
        return []
    segments: list[dict[str, Any]] = []
    total_weight = sum(max(len(chunk), 1) for chunk in chunks)
    cursor = start
    for index, chunk in enumerate(chunks):
        if index == len(chunks) - 1:
            chunk_end = end
        else:
            chunk_end = cursor + (end - start) * max(len(chunk), 1) / total_weight
        segments.append(
            {
                "start": round(cursor, 3),
                "end": round(chunk_end, 3),
                "text": chunk,
            }
        )
        cursor = chunk_end
    return segments


def _split_subtitle_text(
    text: str,
    max_chars: int = 28,
    max_line_chars: int = 13,
) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentence_parts = [
        part.strip()
        for part in re.findall(r"[^。！？!?]+[。！？!?]?", normalized)
        if part.strip()
    ] or [normalized]
    chunks: list[str] = []
    for part in sentence_parts:
        if len(part) <= max_chars:
            chunks.append(_wrap_subtitle_chunk(part, max_line_chars=max_line_chars))
        else:
            chunks.extend(
                _split_long_subtitle_part(
                    part,
                    max_chars=max_chars,
                    max_line_chars=max_line_chars,
                )
            )
    return chunks


def _split_long_subtitle_part(
    text: str,
    *,
    max_chars: int,
    max_line_chars: int,
) -> list[str]:
    clause_parts = [
        part.strip()
        for part in re.findall(r"[^，,、；;：:]+[，,、；;：:]?", text)
        if part.strip()
    ] or [text]
    chunks: list[str] = []
    current = ""
    for part in clause_parts:
        if not current:
            current = part
        elif len(current) + len(part) <= max_chars:
            current += part
        else:
            chunks.append(current)
            current = part
    if current:
        chunks.append(current)

    fitted: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            fitted.append(_wrap_subtitle_chunk(chunk, max_line_chars=max_line_chars))
        else:
            fitted.extend(
                _wrap_subtitle_chunk(
                    chunk[index : index + max_chars],
                    max_line_chars=max_line_chars,
                )
                for index in range(0, len(chunk), max_chars)
            )
    return fitted


def _wrap_subtitle_chunk(text: str, *, max_line_chars: int) -> str:
    if len(text) <= max_line_chars:
        return text
    lines: list[str] = []
    remaining = text
    while len(remaining) > max_line_chars:
        split_at = _subtitle_wrap_index(remaining, max_line_chars=max_line_chars)
        lines.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        lines.append(remaining)
    return "\n".join(lines)


def _subtitle_wrap_index(text: str, *, max_line_chars: int) -> int:
    punctuation_breaks = "，,、；;：:。！？!?"
    for index in range(min(max_line_chars, len(text) - 1), 0, -1):
        if text[index - 1] in punctuation_breaks:
            return index

    preferred_break_before = [
        "靠谱",
        "今天",
        "留个",
        "法律",
        "刑事",
        "你的",
        "我会",
    ]
    lower_bound = max(4, max_line_chars // 2)
    for marker in preferred_break_before:
        index = text.find(marker)
        if lower_bound <= index <= max_line_chars:
            return index

    return max_line_chars


def _timeline_duration(plan: dict[str, Any]) -> float:
    try:
        return float(plan.get("total_duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def _write_subtitle_sidecar(
    plan: dict[str, Any],
    plan_path: Path,
    project_dir: Path,
    subtitle_polish_plan_path: str | None = None,
) -> dict[str, Any]:
    if subtitle_polish_plan_path:
        polish_path = _resolve_project_path(project_dir, subtitle_polish_plan_path)
        if not polish_path.is_file():
            raise ValueError(f"subtitle polish plan not found: {polish_path}")
        segments = _subtitle_segments_from_polish_plan(polish_path)
        source = "subtitle_polish_plan"
    else:
        segments = _subtitle_segments(plan)
        source = "timeline"
    segments = _strip_subtitle_terminal_punctuation(segments)
    output_path = _subtitle_path(plan_path, project_dir)
    if not segments:
        return {"subtitle_path": None, "subtitle_cue_count": 0, "subtitle_source": source}

    result = SubtitleGen().execute(
        {
            "segments": segments,
            "format": "srt",
            "output_path": str(output_path),
            "max_words_per_cue": 1,
        }
    )
    if not result.success:
        raise RuntimeError(result.error or "subtitle_gen failed")
    return {
        "subtitle_path": str(output_path),
        "subtitle_cue_count": int((result.data or {}).get("cue_count", 0)),
        "subtitle_source": source,
    }


def _strip_subtitle_terminal_punctuation(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned_segments: list[dict[str, Any]] = []
    for segment in segments:
        raw_text = str(segment.get("text") or "")
        cleaned_lines = [
            line.rstrip().rstrip(SUBTITLE_TERMINAL_PUNCTUATION).rstrip()
            for line in raw_text.splitlines()
        ]
        cleaned_text = "\n".join(line for line in cleaned_lines if line.strip()).strip()
        if not cleaned_text:
            continue
        cleaned_segment = dict(segment)
        cleaned_segment["text"] = cleaned_text
        cleaned_segments.append(cleaned_segment)
    return cleaned_segments


def _compose_single_cut_inputs(
    *,
    source_path: Path,
    output_path: Path,
    total_duration: float,
    subtitle_path: str | None = None,
    subtitle_style: dict[str, Any] | None = None,
    audio_path: str | None = None,
    crf: int | None = None,
    preset: str | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "operation": "compose",
        "edit_decisions": {
            "cuts": [
                {
                    "source": str(source_path),
                    "in_seconds": 0,
                    "out_seconds": total_duration,
                    "speed": 1.0,
                }
            ]
        },
        "output_path": str(output_path),
    }
    if subtitle_path:
        inputs["subtitle_path"] = subtitle_path
        inputs["subtitle_style"] = subtitle_style or _subtitle_style()
    if audio_path:
        inputs["audio_path"] = audio_path
    if crf is not None:
        inputs["crf"] = crf
    if preset is not None:
        inputs["preset"] = preset
    return inputs


def _render_report(
    *,
    plan: dict[str, Any],
    plan_path: Path,
    clips: list[str],
    audio_tracks: list[dict[str, Any]],
    subtitle_info: dict[str, Any],
    output_path: Path,
    status: str,
    dry_run: bool,
    quality_settings: dict[str, Any],
    stitch_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "status": status,
        "dry_run": dry_run,
        "tool": "video_stitch",
        "render_runtime": plan.get("render_runtime", "ffmpeg"),
        "final_edit_plan_path": str(plan_path),
        "output_path": str(output_path),
        "clip_count": len(clips),
        "clips": clips,
        "subtitle_path": subtitle_info["subtitle_path"],
        "subtitle_cue_count": subtitle_info["subtitle_cue_count"],
        "subtitle_source": subtitle_info.get("subtitle_source", "timeline"),
        "quality_profile": quality_settings["profile"],
        "video_crf": quality_settings["crf"],
        "video_preset": quality_settings["preset"],
        "audio_track_count": len(audio_tracks),
        "audio_tracks": audio_tracks,
        "burned_subtitles": bool(stitch_data and stitch_data.get("burned_subtitles")),
        "mixed_audio": bool(stitch_data and stitch_data.get("mixed_audio_path")),
        "mixed_audio_path": (stitch_data or {}).get("mixed_audio_path"),
        "transition": "cut",
        "auto_normalize": True,
        "total_duration": plan.get("total_duration"),
        "stitch_result": stitch_data or {},
        "verification": [
            "Play the final MP4 and verify clip order.",
            "Check subtitle/copy alignment against the approved reference plan.",
            "Confirm team-authorized likeness assets were used.",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Reference Final Render Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Dry run: `{report['dry_run']}`",
        f"- Tool: `{report['tool']}`",
        f"- Clip count: `{report['clip_count']}`",
        f"- Output: `{report['output_path']}`",
        f"- Subtitle sidecar: `{report['subtitle_path']}`",
        f"- Quality: `{report['quality_profile']}` (CRF `{report['video_crf']}`, preset `{report['video_preset']}`)",
        f"- Burned subtitles: `{report['burned_subtitles']}`",
        f"- Audio tracks: `{report['audio_track_count']}`",
        f"- Mixed audio: `{report['mixed_audio']}`",
        "",
        "## Clips",
    ]
    for index, clip in enumerate(report["clips"], start=1):
        lines.append(f"- `{index}` `{clip}`")
    lines.extend(["", "## Audio"])
    if report["audio_tracks"]:
        for track in report["audio_tracks"]:
            lines.append(f"- `{track.get('role', 'speech')}` `{track['path']}`")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Verification",
            *[f"- {item}" for item in report["verification"]],
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_render_report(
    *,
    plan_path: str | Path,
    project_dir: str | Path,
    output_path: str | None = None,
    output_dir: str | None = None,
    dry_run: bool = False,
    burn_subtitles: bool = False,
    mix_audio: bool = False,
    subtitle_polish_plan_path: str | None = None,
    quality_profile: str = "high",
) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    resolved_plan_path = Path(plan_path).expanduser().resolve()
    plan = _load_plan(resolved_plan_path)
    if plan.get("status") != "ready_for_compose":
        raise ValueError("final edit plan status must be ready_for_compose before composing")

    quality_settings = _quality_settings(quality_profile)
    clips = _clip_paths(plan, project_path)
    audio_tracks = _audio_tracks(plan, project_path)
    subtitle_info = _write_subtitle_sidecar(
        plan,
        resolved_plan_path,
        project_path,
        subtitle_polish_plan_path=subtitle_polish_plan_path,
    )
    subtitle_style = _subtitle_style()
    final_output = _output_path(plan, project_path, output_path)
    final_output.parent.mkdir(parents=True, exist_ok=True)
    stitched_output = (
        _intermediate_video_path(resolved_plan_path, project_path, "stitched-base")
        if burn_subtitles or mix_audio
        else final_output
    )

    stitch_data: dict[str, Any] | None = None
    status = "dry_run_ready"
    if not dry_run:
        if len(clips) == 1:
            source_clip = Path(clips[0])
            if burn_subtitles or mix_audio:
                stitched_output = source_clip
                stitch_data = {
                    "output_path": str(source_clip),
                    "method": "single_clip_passthrough",
                }
            else:
                if source_clip.resolve() != final_output.resolve():
                    shutil.copy2(source_clip, final_output)
                stitched_output = final_output
                stitch_data = {
                    "output_path": str(final_output),
                    "method": "single_clip_copy",
                }
        else:
            result = VideoStitch().execute(
                {
                    "operation": "stitch",
                    "clips": clips,
                    "transition": "cut",
                    "output_path": str(stitched_output),
                    "auto_normalize": True,
                    "crf": quality_settings["crf"],
                    "preset": quality_settings["preset"],
                }
            )
            if not result.success:
                raise RuntimeError(result.error or "video_stitch failed")
            stitch_data = result.data if isinstance(result.data, dict) else {}

        mixed_audio_path: Path | None = None
        if mix_audio:
            if not audio_tracks:
                raise ValueError("mix_audio requires compose_handoff.audio_tracks")
            mixed_audio_path = _mixed_audio_path(resolved_plan_path, project_path)
            mix_result = AudioMixer().execute(
                {
                    "operation": "full_mix",
                    "tracks": audio_tracks,
                    "ducking": {"enabled": True, "music_volume_during_speech": 0.15},
                    "normalize": True,
                    "output_path": str(mixed_audio_path),
                }
            )
            if not mix_result.success:
                raise RuntimeError(mix_result.error or "audio_mixer full_mix failed")
            stitch_data = {
                **stitch_data,
                "mixed_audio_path": str(mixed_audio_path),
                "audio_mix_result": mix_result.data if isinstance(mix_result.data, dict) else {},
            }

        if burn_subtitles and not mix_audio:
            subtitle_path = subtitle_info.get("subtitle_path")
            if not subtitle_path:
                raise ValueError("burn_subtitles requires subtitle text in the final edit plan")
            burn_result = VideoCompose().execute(
                {
                    "operation": "burn_subtitles",
                    "input_path": str(stitched_output),
                    "subtitle_path": subtitle_path,
                    "subtitle_style": subtitle_style,
                    "output_path": str(final_output),
                    "crf": quality_settings["crf"],
                    "preset": quality_settings["preset"],
                }
            )
            if not burn_result.success:
                raise RuntimeError(burn_result.error or "video_compose burn_subtitles failed")
            stitch_data = {
                **stitch_data,
                "burned_subtitles": True,
                "postprocess_result": burn_result.data if isinstance(burn_result.data, dict) else {},
            }
        elif mix_audio:
            subtitle_path = subtitle_info.get("subtitle_path") if burn_subtitles else None
            compose_result = VideoCompose().execute(
                _compose_single_cut_inputs(
                    source_path=stitched_output,
                    output_path=final_output,
                    total_duration=_timeline_duration(plan),
                    subtitle_path=subtitle_path,
                    subtitle_style=subtitle_style,
                    audio_path=str(mixed_audio_path) if mixed_audio_path else None,
                    crf=quality_settings["crf"],
                    preset=quality_settings["preset"],
                )
            )
            if not compose_result.success:
                raise RuntimeError(compose_result.error or "video_compose compose failed")
            stitch_data = {
                **stitch_data,
                "burned_subtitles": bool(subtitle_path),
                "postprocess_result": (
                    compose_result.data if isinstance(compose_result.data, dict) else {}
                ),
            }
        status = "rendered"

    report = _render_report(
        plan=plan,
        plan_path=resolved_plan_path,
        clips=clips,
        audio_tracks=audio_tracks,
        subtitle_info=subtitle_info,
        output_path=final_output,
        status=status,
        dry_run=dry_run,
        quality_settings=quality_settings,
        stitch_data=stitch_data,
    )
    json_path, markdown_path = _report_paths(resolved_plan_path, project_path, output_dir)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return {
        "dry_run": dry_run,
        "render_report": report,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "final_edit_plan_path",
        help="Final edit plan JSON from preview_reference_final_edit.py",
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument("--output-path", help="Override final MP4 output path")
    parser.add_argument("--output-dir", help="Optional render report output directory")
    parser.add_argument("--dry-run", action="store_true", help="Write render report without stitching")
    parser.add_argument(
        "--burn-subtitles",
        action="store_true",
        help="Burn generated SRT subtitles into the final MP4 after stitching",
    )
    parser.add_argument(
        "--mix-audio",
        action="store_true",
        help="Mix compose_handoff.audio_tracks and mux the result into the final MP4",
    )
    parser.add_argument(
        "--subtitle-polish-plan",
        help="Optional subtitle-polish-plan JSON to use instead of timeline[].subtitle_text",
    )
    parser.add_argument(
        "--quality",
        choices=sorted(QUALITY_PROFILES),
        default="high",
        help="Encoding quality profile for any re-encode. Defaults to high.",
    )
    args = parser.parse_args(argv)

    try:
        payload = write_render_report(
            plan_path=args.final_edit_plan_path,
            project_dir=args.project_dir,
            output_path=args.output_path,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            burn_subtitles=args.burn_subtitles,
            mix_audio=args.mix_audio,
            subtitle_polish_plan_path=args.subtitle_polish_plan,
            quality_profile=args.quality,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
