#!/usr/bin/env python3
"""Kling Official animated-explainer E2E smoke script.

This script validates the official Kling provider path through OpenMontage
selectors and the animated-explainer asset/compose surface.

Default mode is a no-cost dry run. Use --live-tts for one paid TTS sample,
--live-full for TTS + image + image-to-video + local FFmpeg compose, or
--live-all to add avatar and lip-sync provider smokes.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from lib.env_loader import load_env  # noqa: E402

load_env(ROOT)

from lib.pipeline_loader import load_pipeline  # noqa: E402
from tools.tool_registry import registry  # noqa: E402
from tools.video.video_compose import VideoCompose  # noqa: E402


DEFAULT_PROJECT = "kling-animated-explainer-e2e"
DEFAULT_VOICE_ID = "oversea_male1"
DEFAULT_TTS_TEXT = (
    "Throughout my time in college, several memorable events left a significant impact on my life."
)
REQUIRED_LIVE_ENV = ("KLING_API_KEY",)
RELEVANT_ENV = ("KLING_API_KEY", "KLING_API_BASE_URL", "FAL_KEY", "OPENAI_API_KEY")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(data), indent=2, ensure_ascii=False), encoding="utf-8")


def _probe_media(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,sample_rate,channels,duration",
        "-show_entries",
        "format=format_name,duration,size,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(completed.stdout or "{}")
    except Exception as exc:
        return {"error": str(exc)}


def _env_status(environ: Mapping[str, str | None] | None = None) -> dict[str, dict[str, Any]]:
    source = environ if environ is not None else os.environ
    status: dict[str, dict[str, Any]] = {}
    for key in RELEVANT_ENV:
        value = source.get(key)
        present = bool(value)
        if not present:
            display = "<missing>"
        elif key == "KLING_API_BASE_URL":
            display = str(value)
        else:
            display = f"<set:{len(str(value))} chars>"
        status[key] = {"present": present, "length": len(str(value or "")), "display": display}
    return status


def _missing_required_env() -> list[str]:
    return [key for key in REQUIRED_LIVE_ENV if not os.environ.get(key)]


def _discover() -> None:
    registry.clear()
    registry.discover("tools")


def _tool_statuses() -> dict[str, str]:
    names = [
        "tts_selector",
        "image_selector",
        "video_selector",
        "video_compose",
        "kling_tts",
        "kling_official_image",
        "kling_official_video",
        "kling_avatar",
        "kling_lip_sync",
    ]
    statuses: dict[str, str] = {}
    for name in names:
        tool = registry.get(name)
        statuses[name] = tool.get_status().value if tool else "missing"
    return statuses


def _capability_summary() -> dict[str, Any]:
    summary = registry.provider_menu_summary()
    wanted = {"tts", "image_generation", "video_generation", "avatar", "video_post"}
    return {
        "composition_runtimes": summary.get("composition_runtimes", {}),
        "capabilities": [
            item for item in summary.get("capabilities", []) if item.get("capability") in wanted
        ],
        "runtime_warnings": summary.get("runtime_warnings", []),
    }


def _kling_entry(rank_result: dict[str, Any]) -> dict[str, Any] | None:
    for item in rank_result.get("rankings", []):
        if item.get("provider") == "kling_official":
            return item
    return None


def _rank_selectors(voice_id: str, voice_language: str, voice_speed: float) -> dict[str, Any]:
    tts = registry.get("tts_selector")
    image = registry.get("image_selector")
    video = registry.get("video_selector")
    assert tts and image and video

    tts_rank = tts.execute(
        {
            "operation": "rank",
            "allowed_providers": ["kling_official"],
            "text": "Kling official TTS selector smoke test.",
            "voice_id": voice_id,
            "voice_language": voice_language,
            "voice_speed": voice_speed,
        }
    ).data
    image_rank = image.execute(
        {
            "operation": "rank",
            "allowed_providers": ["kling_official"],
            "prompt": "Clean minimal explainer visual about AI video production.",
            "api_family": "generation",
            "model_name": "kling-v3",
        }
    ).data
    video_rank = video.execute(
        {
            "operation": "rank",
            "target_operation": "image_to_video",
            "allowed_providers": ["kling_official"],
            "prompt": "Slow camera push over a clean explainer visual.",
            "api_family": "classic",
            "model_name": "kling-v3",
            "duration": "3",
            "mode": "std",
            "sound": "off",
        }
    ).data

    return {
        "note": (
            "Rank mode is advisory. Live modes use preferred_provider and "
            "allowed_providers to force kling_official selection."
        ),
        "kling_official_entries": {
            "tts": _kling_entry(tts_rank),
            "image": _kling_entry(image_rank),
            "video": _kling_entry(video_rank),
        },
        "tts_rank_all": tts_rank,
        "image_rank_all": image_rank,
        "video_rank_all": video_rank,
    }


def _dry_run(voice_id: str, voice_language: str, voice_speed: float, text: str) -> dict[str, Any]:
    dry: dict[str, Any] = {}
    cases = {
        "kling_tts": {
            "text": text,
            "voice_id": voice_id,
            "voice_language": voice_language,
            "voice_speed": voice_speed,
        },
        "kling_official_image": {
            "prompt": "Clean minimal explainer visual about AI video production.",
            "api_family": "generation",
            "model_name": "kling-v3",
            "resolution": "1k",
            "aspect_ratio": "16:9",
            "n": 1,
        },
        "kling_official_video": {
            "prompt": "Slow camera push over a clean explainer visual.",
            "operation": "image_to_video",
            "api_family": "classic",
            "model_name": "kling-v3",
            "duration": "3",
            "mode": "std",
            "sound": "off",
        },
    }
    for name, payload in cases.items():
        tool = registry.get(name)
        dry[name] = tool.dry_run(payload) if tool else {"status": "missing"}
    return dry


def _require_success(name: str, result: Any) -> None:
    if not result.success:
        raise RuntimeError(f"{name} failed: {result.error}")


def _aligned_video_duration(requested_duration: str, narration_seconds: float | None) -> str:
    requested = int(requested_duration)
    if narration_seconds:
        requested = max(requested, int(math.ceil(narration_seconds)))
    return str(min(max(requested, 3), 15))


def _announce_paid_call(tool: str, provider: str, model: str, reason: str, run_type: str) -> None:
    print(f"[paid:{run_type}] tool={tool} provider={provider} model={model}")
    print(f"[paid:{run_type}] reason={reason}")


def _run_live_tts(
    project_dir: Path,
    *,
    voice_id: str,
    voice_language: str,
    voice_speed: float,
    text: str,
    timeout_seconds: int,
    poll_interval: float,
    include_account_usage: bool,
) -> dict[str, Any]:
    tts = registry.get("tts_selector")
    assert tts

    audio_dir = project_dir / "assets" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    _announce_paid_call(
        "tts_selector -> kling_tts",
        "kling_official",
        "kling-official-tts",
        "Validate official Kling TTS through OpenMontage selector routing.",
        "sample",
    )
    result = tts.execute(
        {
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
            "text": text,
            "voice_id": voice_id,
            "voice_language": voice_language,
            "voice_speed": voice_speed,
            "sample_mode": True,
            "include_account_usage": include_account_usage,
            "timeout_seconds": timeout_seconds,
            "poll_interval": poll_interval,
            "output_path": str(audio_dir / "narration.mp3"),
        }
    )
    _require_success("tts_selector", result)
    output_path = Path(result.data["output_path"])
    return {
        "result": result.data,
        "artifacts": {"narration": str(output_path)},
        "ffprobe": _probe_media(output_path),
        "estimated_cost_usd": float(result.cost_usd or 0),
    }


def _run_live_full(
    project_dir: Path,
    *,
    voice_id: str,
    voice_language: str,
    voice_speed: float,
    text: str,
    timeout_seconds: int,
    poll_interval: float,
    include_account_usage: bool,
    video_duration: str,
) -> dict[str, Any]:
    image = registry.get("image_selector")
    video = registry.get("video_selector")
    assert image and video

    assets = project_dir / "assets"
    image_dir = assets / "images"
    video_dir = assets / "video"
    renders_dir = project_dir / "renders"
    for path in (image_dir, video_dir, renders_dir):
        path.mkdir(parents=True, exist_ok=True)

    tts_data = _run_live_tts(
        project_dir,
        voice_id=voice_id,
        voice_language=voice_language,
        voice_speed=voice_speed,
        text=text,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        include_account_usage=include_account_usage,
    )
    narration_path = Path(tts_data["artifacts"]["narration"])
    target_video_duration = _aligned_video_duration(
        video_duration,
        tts_data.get("result", {}).get("audio_duration_seconds"),
    )

    _announce_paid_call(
        "image_selector -> kling_official_image",
        "kling_official",
        "kling-v3",
        "Generate one reference frame for the animated-explainer E2E smoke.",
        "sample",
    )
    image_result = image.execute(
        {
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
            "prompt": (
                "A clean 16:9 animated-explainer hero frame: a luminous production "
                "pipeline diagram on a dark desk, small cards labeled script, voice, "
                "image, video, render, realistic yet crisp, no text artifacts."
            ),
            "negative_prompt": "blurry, unreadable text, distorted interface, watermark",
            "api_family": "generation",
            "model_name": "kling-v3",
            "resolution": "1k",
            "aspect_ratio": "16:9",
            "n": 1,
            "output_path": str(image_dir / "hero_frame.png"),
        }
    )
    _require_success("image_selector", image_result)
    image_path = Path(image_result.data["output_path"])

    _announce_paid_call(
        "video_selector -> kling_official_video",
        "kling_official",
        "kling-v3 classic image_to_video",
        "Animate the generated reference frame for a minimal provider E2E smoke.",
        "sample",
    )
    video_result = video.execute(
        {
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
            "prompt": (
                "A slow cinematic push-in over the explainer pipeline diagram. "
                "Cards glow softly in sequence, subtle parallax, stable camera, smooth motion."
            ),
            "operation": "image_to_video",
            "api_family": "classic",
            "model_name": "kling-v3",
            "reference_image_path": str(image_path),
            "duration": target_video_duration,
            "mode": "std",
            "sound": "off",
            "output_path": str(video_dir / "kling_i2v_clip.mp4"),
            "timeout_seconds": max(timeout_seconds, 900),
            "poll_interval": poll_interval,
        }
    )
    _require_success("video_selector", video_result)
    clip_path = Path(video_result.data["output_path"])

    print("[local] tool=video_compose runtime=ffmpeg reason=minimal one-clip provider smoke")
    edit_decisions = {
        "version": "1.0",
        "render_runtime": "ffmpeg",
        "renderer_family": "video_concat_smoke",
        "cuts": [
            {
                "id": "cut-001",
                "source": str(clip_path),
                "in_seconds": 0,
                "out_seconds": float(target_video_duration),
                "speed": 1.0,
            }
        ],
        "subtitles": {"enabled": False},
        "metadata": {
            "pipeline": "animated-explainer",
            "compose_target": {"width": 1280, "height": 720, "fit": "pad"},
            "provider_smoke": True,
            "approved_runtime_reason": "Minimal provider integration smoke uses ffmpeg compose for one clip.",
        },
    }
    compose_result = VideoCompose().execute(
        {
            "operation": "compose",
            "edit_decisions": edit_decisions,
            "audio_path": str(narration_path),
            "output_path": str(renders_dir / "final_kling_e2e_smoke.mp4"),
            "profile": "youtube_landscape",
            "crf": 23,
            "preset": "medium",
        }
    )
    _require_success("video_compose", compose_result)
    final_path = Path(compose_result.data["output"])

    return {
        "tts": tts_data,
        "image": image_result.data,
        "video": video_result.data,
        "compose": compose_result.data,
        "requested_video_duration": video_duration,
        "aligned_video_duration": target_video_duration,
        "artifacts": {
            "narration": str(narration_path),
            "image": str(image_path),
            "clip": str(clip_path),
            "final": str(final_path),
        },
        "ffprobe": {
            "narration": _probe_media(narration_path),
            "image": _probe_media(image_path),
            "clip": _probe_media(clip_path),
            "final": _probe_media(final_path),
        },
        "estimated_cost_usd": sum(
            float(getattr(result, "cost_usd", 0) or 0)
            for result in (image_result, video_result)
        )
        + float(tts_data.get("estimated_cost_usd") or 0),
    }


def _first_remote_url(result_data: dict[str, Any]) -> str:
    direct = result_data.get("remote_url")
    if direct:
        return str(direct)
    for item in result_data.get("remote_outputs") or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("video_url") or item.get("resource_url")
        if url:
            return str(url)
    raise RuntimeError("Kling result did not include a remote video URL for lip-sync input.")


def _run_live_avatar_suite(
    project_dir: Path,
    *,
    timeout_seconds: int,
    poll_interval: float,
) -> dict[str, Any]:
    image = registry.get("image_selector")
    avatar = registry.get("kling_avatar")
    lip_sync = registry.get("kling_lip_sync")
    assert image and avatar and lip_sync

    assets_dir = project_dir / "assets"
    image_dir = assets_dir / "images"
    video_dir = assets_dir / "video"
    artifacts_dir = project_dir / "artifacts"
    narration_path = assets_dir / "audio" / "narration.mp3"
    if not narration_path.is_file():
        raise RuntimeError(
            f"Avatar smoke requires an existing narration file: {narration_path}. "
            "Run --live-full or --live-all first."
        )

    _announce_paid_call(
        "image_selector -> kling_official_image",
        "kling_official",
        "kling-v3 generation",
        "Create one synthetic single-face portrait for the avatar provider smoke.",
        "sample",
    )
    portrait_result = image.execute(
        {
            "preferred_provider": "kling_official",
            "allowed_providers": ["kling_official"],
            "prompt": (
                "Photorealistic studio portrait of one fictional adult presenter, front-facing, "
                "head and shoulders centered, neutral expression, mouth closed, even soft lighting, "
                "plain background, no text, no watermark."
            ),
            "negative_prompt": "multiple people, profile view, open mouth, obscured face, text, watermark",
            "api_family": "generation",
            "model_name": "kling-v3",
            "resolution": "1k",
            "aspect_ratio": "1:1",
            "n": 1,
            "output_path": str(image_dir / "avatar_portrait.png"),
        }
    )
    _require_success("avatar portrait", portrait_result)
    portrait_path = Path(portrait_result.data["output_path"])

    _announce_paid_call(
        "kling_avatar",
        "kling_official",
        "kling-official-avatar std",
        "Validate photo-and-audio to avatar video through the official provider.",
        "sample",
    )
    avatar_result = avatar.execute(
        {
            "image_path": str(portrait_path),
            "audio_path": str(narration_path),
            "prompt": "Natural presenter delivery with subtle head movement and stable identity.",
            "mode": "std",
            "timeout_seconds": max(timeout_seconds, 900),
            "poll_interval": poll_interval,
            "output_path": str(video_dir / "kling_avatar_smoke.mp4"),
        }
    )
    _require_success("kling_avatar", avatar_result)
    avatar_path = Path(avatar_result.data["output_path"])
    partial_report_path = artifacts_dir / "kling_avatar_live_partial.json"
    _write_json(
        partial_report_path,
        {
            "portrait": portrait_result.data,
            "avatar": avatar_result.data,
            "artifacts": {
                "narration": str(narration_path),
                "portrait": str(portrait_path),
                "avatar": str(avatar_path),
            },
            "ffprobe": {
                "portrait": _probe_media(portrait_path),
                "avatar": _probe_media(avatar_path),
            },
        },
    )

    _announce_paid_call(
        "kling_lip_sync",
        "kling_official",
        "kling-official-lip-sync full_lip_sync",
        "Validate identify-face, explicit auto-selection, and advanced lip-sync as one smoke.",
        "sample",
    )
    lip_sync_result = lip_sync.execute(
        {
            "operation": "full_lip_sync",
            "video_url": _first_remote_url(avatar_result.data),
            "audio_path": str(narration_path),
            "auto_select_face": True,
            "faces_artifact_path": str(artifacts_dir / "kling_lip_sync_faces.json"),
            "timeout_seconds": max(timeout_seconds, 900),
            "poll_interval": poll_interval,
            "output_path": str(video_dir / "kling_lip_sync_smoke.mp4"),
        }
    )
    _require_success("kling_lip_sync", lip_sync_result)
    lip_sync_path = Path(lip_sync_result.data["output_path"])

    estimated_cost = sum(
        float(getattr(result, "cost_usd", 0) or 0)
        for result in (portrait_result, avatar_result, lip_sync_result)
    )
    return {
        "portrait": portrait_result.data,
        "avatar": avatar_result.data,
        "lip_sync": lip_sync_result.data,
        "artifacts": {
            "narration": str(narration_path),
            "portrait": str(portrait_path),
            "avatar": str(avatar_path),
            "lip_sync": str(lip_sync_path),
            "faces": str(artifacts_dir / "kling_lip_sync_faces.json"),
            "avatar_partial_report": str(partial_report_path),
        },
        "ffprobe": {
            "portrait": _probe_media(portrait_path),
            "avatar": _probe_media(avatar_path),
            "lip_sync": _probe_media(lip_sync_path),
        },
        "estimated_cost_usd": estimated_cost,
    }


def _run_live_all(
    project_dir: Path,
    *,
    voice_id: str,
    voice_language: str,
    voice_speed: float,
    text: str,
    timeout_seconds: int,
    poll_interval: float,
    include_account_usage: bool,
    video_duration: str,
) -> dict[str, Any]:
    core = _run_live_full(
        project_dir,
        voice_id=voice_id,
        voice_language=voice_language,
        voice_speed=voice_speed,
        text=text,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        include_account_usage=include_account_usage,
        video_duration=video_duration,
    )
    avatar_suite = _run_live_avatar_suite(
        project_dir,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
    )
    return {
        "core": core,
        "avatar_suite": avatar_suite,
        "artifacts": {
            **core["artifacts"],
            **avatar_suite["artifacts"],
        },
        "ffprobe": {
            "core": core["ffprobe"],
            "avatar_suite": avatar_suite["ffprobe"],
        },
        "estimated_cost_usd": float(core.get("estimated_cost_usd") or 0)
        + float(avatar_suite.get("estimated_cost_usd") or 0),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    live = parser.add_mutually_exclusive_group()
    live.add_argument("--live-tts", action="store_true", help="Run one paid Kling TTS sample.")
    live.add_argument(
        "--live",
        "--live-full",
        dest="live_full",
        action="store_true",
        help="Run paid Kling TTS, image, video, and local compose.",
    )
    live.add_argument(
        "--live-avatar",
        action="store_true",
        help="Use existing narration to run paid Kling portrait, avatar, and lip-sync samples.",
    )
    live.add_argument(
        "--live-all",
        action="store_true",
        help="Run the full smoke plus paid Kling avatar and lip-sync samples.",
    )
    parser.add_argument("--voice-id", default=DEFAULT_VOICE_ID)
    parser.add_argument("--voice-language", choices=["en", "zh"], default="en")
    parser.add_argument("--voice-speed", type=float, default=1.0)
    parser.add_argument("--text", default=DEFAULT_TTS_TEXT)
    parser.add_argument("--video-duration", choices=[str(v) for v in range(3, 16)], default="3")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--include-account-usage", action="store_true")
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    return parser.parse_args(argv)


def _execution_mode(args: argparse.Namespace) -> str:
    if getattr(args, "live_tts", False):
        return "live_tts"
    if getattr(args, "live_full", False):
        return "live_full"
    if getattr(args, "live_avatar", False):
        return "live_avatar"
    if getattr(args, "live_all", False):
        return "live_all"
    return "dry_run"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    mode = _execution_mode(args)
    project_dir = ROOT / "projects" / args.project
    report_path = project_dir / "artifacts" / "kling_official_animated_explainer_e2e_report.json"

    manifest = load_pipeline("animated-explainer")
    _discover()

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline": manifest["name"],
        "purpose": "Kling official selector-level E2E smoke for animated-explainer assets + compose.",
        "mode": mode,
        "voice_id": args.voice_id,
        "voice_language": args.voice_language,
        "voice_speed": args.voice_speed,
        "project_dir": str(project_dir),
        "env_status": _env_status(),
        "tool_statuses": _tool_statuses(),
        "capability_summary": _capability_summary(),
        "selector_rankings": _rank_selectors(args.voice_id, args.voice_language, args.voice_speed),
        "dry_run": _dry_run(args.voice_id, args.voice_language, args.voice_speed, args.text),
    }

    missing_env = _missing_required_env()
    if mode != "dry_run" and missing_env:
        report["blocked"] = {
            "reason": "missing required live environment variables",
            "missing_env": missing_env,
        }
        _write_json(report_path, report)
        print(f"blocked: missing required live env vars: {', '.join(missing_env)}")
        print(f"report: {report_path}")
        return 2

    try:
        if mode == "live_tts":
            report["live_tts_result"] = _run_live_tts(
                project_dir,
                voice_id=args.voice_id,
                voice_language=args.voice_language,
                voice_speed=args.voice_speed,
                text=args.text,
                timeout_seconds=args.timeout_seconds,
                poll_interval=args.poll_interval,
                include_account_usage=args.include_account_usage,
            )
        elif mode == "live_full":
            report["live_full_result"] = _run_live_full(
                project_dir,
                voice_id=args.voice_id,
                voice_language=args.voice_language,
                voice_speed=args.voice_speed,
                text=args.text,
                timeout_seconds=args.timeout_seconds,
                poll_interval=args.poll_interval,
                include_account_usage=args.include_account_usage,
                video_duration=args.video_duration,
            )
        elif mode == "live_avatar":
            report["live_avatar_result"] = _run_live_avatar_suite(
                project_dir,
                timeout_seconds=args.timeout_seconds,
                poll_interval=args.poll_interval,
            )
        elif mode == "live_all":
            report["live_all_result"] = _run_live_all(
                project_dir,
                voice_id=args.voice_id,
                voice_language=args.voice_language,
                voice_speed=args.voice_speed,
                text=args.text,
                timeout_seconds=args.timeout_seconds,
                poll_interval=args.poll_interval,
                include_account_usage=args.include_account_usage,
                video_duration=args.video_duration,
            )
        else:
            report["next_steps"] = [
                "Run with --live-tts to make one paid Kling TTS sample call.",
                "Run with --live-full to make paid Kling TTS/image/video calls and compose final_kling_e2e_smoke.mp4.",
                "Run with --live-avatar to reuse narration for paid Kling avatar and lip-sync provider smokes.",
                "Run with --live-all to add paid Kling avatar and lip-sync provider smokes.",
            ]
    except Exception as exc:
        report["failed"] = {"error": str(exc)}
        _write_json(report_path, report)
        print(f"failed: {exc}")
        print(f"report: {report_path}")
        return 1

    _write_json(report_path, report)
    print(f"report: {report_path}")
    if mode == "live_tts":
        print(f"narration: {report['live_tts_result']['artifacts']['narration']}")
    elif mode == "live_full":
        print(f"final: {report['live_full_result']['artifacts']['final']}")
    elif mode == "live_avatar":
        print(f"avatar: {report['live_avatar_result']['artifacts']['avatar']}")
        print(f"lip_sync: {report['live_avatar_result']['artifacts']['lip_sync']}")
    elif mode == "live_all":
        print(f"avatar: {report['live_all_result']['artifacts']['avatar']}")
        print(f"lip_sync: {report['live_all_result']['artifacts']['lip_sync']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
