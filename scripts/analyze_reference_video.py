"""Create a reference-video replication package from a local video file or URL."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.frame_sampler import FrameSampler
from tools.analysis.reference_video_package import ReferenceVideoPackage
from tools.analysis.scene_detect import SceneDetect
from tools.analysis.transcriber import Transcriber
from tools.analysis.video_downloader import VideoDownloader


def _safe_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-video"


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(result.stdout or "{}")


def _fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return round(float(numerator) / float(denominator), 3)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _transcription_reason(error: str | None) -> str:
    message = (error or "").lower()
    if "not installed" in message or "install faster-whisper" in message:
        return "transcriber_unavailable_install_faster_whisper"
    if (
        "failed to load transcription model" in message
        or "connecterror" in message
        or "internet connection" in message
        or "snapshot folder" in message
        or "local disk" in message
    ):
        return "transcriber_model_download_required"
    return "transcription_failed"


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "www."))


class ReferenceDownloadError(RuntimeError):
    def __init__(
        self,
        *,
        url: str,
        reason: str,
        project_dir: Path,
        platform: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(reason)
        self.url = url
        self.reason = reason
        self.project_dir = project_dir
        self.platform = platform
        self.metadata = metadata or {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": "download_failed",
            "input": self.url,
            "reason": self.reason,
            "platform": self.platform or "unknown",
            "metadata": self.metadata,
            "fallback_required": "local_video_file",
            "message": (
                "URL ingestion failed. Provide a local video file path instead; "
                "OpenMontage will not bypass login, region, watermark, or platform protection."
            ),
            "project_dir": str(self.project_dir),
        }


def probe_video(path: Path) -> dict[str, Any]:
    data = _run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,avg_frame_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    streams = data.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    return {
        "duration_seconds": round(float((data.get("format") or {}).get("duration", 0.0)), 3),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": _fps(video_stream.get("avg_frame_rate")),
        "has_audio": has_audio,
    }


def _fixed_interval_scenes(duration: float, segment_seconds: float = 5.0) -> list[dict[str, Any]]:
    if duration <= 0:
        return []
    scenes: list[dict[str, Any]] = []
    start = 0.0
    index = 1
    while start < duration:
        end = min(duration, start + segment_seconds)
        scenes.append(
            {
                "scene_id": f"s{index}",
                "start": round(start, 3),
                "end": round(end, 3),
                "visual_summary": f"参考视频片段 {index}",
                "camera_motion": "",
                "pacing": "unknown",
                "keyframes": [],
                "production_hint": "seedance_remake",
            }
        )
        start = end
        index += 1
    return scenes


def _normalize_scenes(raw_scenes: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not raw_scenes:
        return _fixed_interval_scenes(duration)

    scenes: list[dict[str, Any]] = []
    for index, scene in enumerate(raw_scenes, start=1):
        start = float(scene.get("start_seconds", scene.get("start", 0.0)))
        end = float(scene.get("end_seconds", scene.get("end", start)))
        scenes.append(
            {
                "scene_id": scene.get("scene_id") or f"s{index}",
                "start": round(start, 3),
                "end": round(end, 3),
                "visual_summary": scene.get("visual_summary", f"参考视频片段 {index}"),
                "camera_motion": scene.get("camera_motion", ""),
                "pacing": scene.get("pacing", "unknown"),
                "keyframes": [],
                "production_hint": scene.get("production_hint", "seedance_remake"),
            }
        )
    return scenes


def _attach_keyframes(scenes: list[dict[str, Any]], frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for scene in scenes:
        start = float(scene.get("start", 0.0))
        end = float(scene.get("end", start))
        matched = [
            frame["path"]
            for frame in frames
            if start <= float(frame.get("timestamp_seconds", 0.0)) <= end
        ]
        scene["keyframes"] = matched[:3]
    return scenes


def analyze_scenes(video_path: Path, project_dir: Path, duration: float) -> dict[str, Any]:
    scene_output = project_dir / "analysis" / "scenes.json"
    scene_result = SceneDetect().execute(
        {
            "input_path": str(video_path),
            "method": "content",
            "min_scene_length_seconds": 1.0,
            "output_path": str(scene_output),
        }
    )
    if scene_result.success:
        raw_scenes = scene_result.data.get("scenes") or []
        method = scene_result.data.get("method", "scene_detect")
    else:
        raw_scenes = []
        method = "fixed_interval_fallback"

    scenes = _normalize_scenes(raw_scenes, duration)
    frame_boundaries = [
        {"start_seconds": scene["start"], "end_seconds": scene["end"]}
        for scene in scenes
    ]
    frame_result = FrameSampler().execute(
        {
            "input_path": str(video_path),
            "strategy": "scene_guided",
            "scene_boundaries": frame_boundaries,
            "max_frames": min(20, max(1, len(scenes) * 2)),
            "output_dir": str(project_dir / "keyframes"),
            "format": "jpg",
        }
    )
    frames = frame_result.data.get("frames", []) if frame_result.success else []
    return {
        "method": method,
        "scene_count": len(scenes),
        "scenes": _attach_keyframes(scenes, frames),
        "limitations": [] if scene_result.success else [scene_result.error or "scene detection failed"],
    }


def transcribe_reference(video_path: Path, project_dir: Path, has_audio: bool) -> dict[str, Any]:
    if not has_audio:
        return {"status": "pending_transcription", "reason": "no_audio_stream"}

    transcriber = Transcriber()
    if transcriber.get_status().value != "available":
        return {
            "status": "pending_transcription",
            "reason": "transcriber_unavailable_install_faster_whisper",
        }

    try:
        result = transcriber.execute(
            {
                "input_path": str(video_path),
                "model_size": "base",
                "language": "zh",
                "diarize": False,
                "output_dir": str(project_dir / "transcript"),
            }
        )
    except Exception as exc:
        return {
            "status": "pending_transcription",
            "reason": _transcription_reason(str(exc)),
        }

    if not result.success:
        return {
            "status": "pending_transcription",
            "reason": _transcription_reason(result.error),
        }

    segments = result.data.get("segments") or []
    raw_text = "".join(segment.get("text", "") for segment in segments).strip()
    if not raw_text:
        return {
            "status": "pending_transcription",
            "reason": "no_speech_detected",
        }

    return {
        "status": "ok",
        "raw_text": raw_text,
        "segments": [
            {
                "start": segment.get("start", 0.0),
                "end": segment.get("end", 0.0),
                "text": segment.get("text", ""),
            }
            for segment in segments
        ],
        "language": result.data.get("language"),
    }


def analyze_local_video(
    video_path: Path,
    project_dir: Path | None = None,
    source_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    video_path = video_path.expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if shutil.which("ffprobe") is None or shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg and ffprobe must be available on PATH")

    project_dir = (project_dir or Path("projects") / f"reference-{_safe_slug(video_path.stem)}").resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    metadata = probe_video(video_path)
    analysis = analyze_scenes(video_path, project_dir, float(metadata.get("duration_seconds") or 0.0))
    transcript = transcribe_reference(video_path, project_dir, bool(metadata.get("has_audio")))
    source = {
        "input_type": "local_file",
        "input": str(video_path),
        "local_video_path": str(video_path),
        "duration_seconds": metadata.get("duration_seconds"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "fps": metadata.get("fps"),
        "has_audio": metadata.get("has_audio"),
        "ingest_method": "local_file",
    }
    if source_overrides:
        source.update(source_overrides)

    package_result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(project_dir),
            "reference_source": source,
            "reference_analysis": analysis,
            "reference_transcript": transcript,
            "output_dir": str(project_dir / "artifacts"),
        }
    )
    if not package_result.success:
        raise RuntimeError(package_result.error or "reference package generation failed")
    return package_result.data


def analyze_reference_url(url: str, project_dir: Path | None = None) -> dict[str, Any]:
    project_dir = (project_dir or Path("projects") / f"reference-{_safe_slug(url)}").resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    download_dir = project_dir / "source"

    result = VideoDownloader().execute(
        {
            "url": url,
            "output_dir": str(download_dir),
            "format": "video",
            "max_resolution": "720p",
            "max_duration_seconds": 600,
        }
    )
    if not result.success or not result.data.get("video_path"):
        raise ReferenceDownloadError(
            url=url,
            reason=result.error or "video_downloader returned no video_path",
            project_dir=project_dir,
            platform=(result.data or {}).get("platform"),
            metadata=(result.data or {}).get("metadata"),
        )

    return analyze_local_video(
        video_path=Path(result.data["video_path"]),
        project_dir=project_dir,
        source_overrides={
            "input_type": "url",
            "input": url,
            "ingest_method": "video_downloader",
            "platform": result.data.get("platform"),
            "download_metadata": result.data.get("metadata", {}),
        },
    )


def analyze_reference_source(source: str, project_dir: Path | None = None) -> dict[str, Any]:
    if _is_url(source):
        return analyze_reference_url(source, project_dir=project_dir)
    return analyze_local_video(Path(source), project_dir=project_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local reference video path or video URL")
    parser.add_argument(
        "--project-dir",
        help="Output project directory. Defaults to projects/reference-<video-stem>",
    )
    args = parser.parse_args(argv)

    try:
        result = analyze_reference_source(
            source=args.source,
            project_dir=Path(args.project_dir) if args.project_dir else None,
        )
    except ReferenceDownloadError as exc:
        print(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Reference analysis failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
