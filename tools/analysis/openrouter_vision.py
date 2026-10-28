"""Frame-sampled visual understanding through an OpenRouter vision model.

The sibling ``video_understand`` tool runs CLIP / BLIP-2 / LLaVA locally, which
is the right default when the box has the weights and a GPU. This is the
API-side alternative, and it exists for two reasons:

  * No local dependencies. ``video_understand`` reports UNAVAILABLE without
    transformers and torch installed; this needs an API key and ffmpeg.
  * One call sees every frame. The local path captions each frame in isolation
    and stitches the strings together, so nothing can answer "what changes
    between the first shot and the last". A long-context model gets all the
    sampled frames in a single message and can reason across them.

What this is NOT: video input. OpenRouter's chat API rejects ``video_url`` for
every model tested — "No endpoints found that support video URLs" — regardless
of what a model card claims about video modality. Frames are extracted with
ffmpeg here and sent as images, which is a real limitation: no audio, no motion
between samples, and cuts shorter than the sampling interval are invisible.

Cost is whatever the routed model charges. Free-tier slugs make this $0, and
``stealth/*`` slugs are provider-cloaked and retired without notice — set
OPENROUTER_VISION_MODEL to move off one that disappears.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "stealth/ox-alpha"
_DEFAULT_MAX_FRAMES = 8
# Frames go over the wire base64-encoded, so this is a real transfer cost even
# when the tokens are free. 12 frames of 1080p is already ~25 MB of request.
_MAX_FRAMES_CEILING = 24

_MODE_INSTRUCTIONS = {
    "describe": (
        "Describe what these frames show as one continuous shot sequence. "
        "Say what changes across them, not what each one contains in isolation."
    ),
    "qa": "Answer this question about the frames: {query}",
    "quality": (
        "Assess these frames for technical and craft problems a video editor "
        "would care about: exposure, focus, framing, motion blur, colour cast, "
        "compression artefacts, and continuity between frames."
    ),
    "classify": (
        "Classify the scene. Return the shot type, setting, lighting, and "
        "subject matter."
    ),
}


class OpenRouterVision(BaseTool):
    name = "openrouter_vision"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "openrouter"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    # Same frames, same prompt, temperature 0 — but a hosted model behind a
    # rotating slug is not something to promise determinism for.
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["binary:ffmpeg"]
    install_instructions = (
        "Set OPENROUTER_API_KEY to an OpenRouter key (https://openrouter.ai/keys).\n"
        "  Optionally set OPENROUTER_VISION_MODEL to route to a different model\n"
        f"  (default {_DEFAULT_MODEL}).\n"
        "  ffmpeg must be on PATH for video input; image input needs nothing else."
    )
    agent_skills = ["video-understand"]

    capabilities = [
        "image_description",
        "visual_qa",
        "quality_assessment",
        "scene_classification",
    ]
    supports = {
        "cross_frame_reasoning": True,
        "multi_image": True,
        "local_inference": False,
        # Proven by probe, not by model card: OpenRouter answers video_url with
        # 404 "No endpoints found that support video URLs".
        "native_video_input": False,
        "audio": False,
    }
    best_for = [
        "reasoning about change across frames in one call",
        "visual QA on a box with no GPU or no transformers/torch install",
    ]
    not_good_for = [
        "true video understanding — motion between samples and audio are lost",
        "offline or air-gapped runs",
        "frame-accurate work: sampling is thumbnail-based, not exhaustive",
    ]
    fallback_tools = ["video_understand"]
    quality_score = 0.8

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Path to image or video file"},
            "query": {"type": "string", "description": "Question to answer (qa mode)"},
            "mode": {
                "type": "string",
                "enum": ["describe", "qa", "quality", "classify"],
                "default": "describe",
            },
            "model": {
                "type": "string",
                "description": f"OpenRouter model slug (default {_DEFAULT_MODEL})",
            },
            "max_frames": {
                "type": "integer",
                "default": _DEFAULT_MAX_FRAMES,
                "description": f"Frames sampled from video, capped at {_MAX_FRAMES_CEILING}",
            },
            "frame_height": {
                "type": "integer",
                "default": 720,
                "description": "Frames are downscaled to this height before upload",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "mode": {"type": "string"},
            "model": {"type": "string"},
            "frame_count": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=1024, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["input_path", "mode", "model", "query", "max_frames"]
    side_effects = ["uploads sampled frames to the OpenRouter API"]
    user_visible_verification = [
        "Check the summary against the actual footage — sampled frames miss short cuts",
        "Confirm nothing in the answer depends on audio, which was never sent",
    ]

    @staticmethod
    def _api_key() -> str | None:
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        return key or None

    @staticmethod
    def _model(inputs: dict[str, Any]) -> str:
        return (inputs.get("model")
                or os.environ.get("OPENROUTER_VISION_MODEL")
                or _DEFAULT_MODEL)

    def get_status(self) -> ToolStatus:
        if self._api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        frames = min(int(inputs.get("max_frames", _DEFAULT_MAX_FRAMES)), _MAX_FRAMES_CEILING)
        # One API call regardless of frame count; frames only add upload time.
        return 20.0 + frames * 2.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        mode = inputs.get("mode", "describe")
        query = inputs.get("query")
        model = self._model(inputs)
        max_frames = max(1, min(int(inputs.get("max_frames", _DEFAULT_MAX_FRAMES)),
                                _MAX_FRAMES_CEILING))
        frame_height = int(inputs.get("frame_height", 720))

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input file not found: {input_path}")

        suffix = input_path.suffix.lower()
        is_video = suffix in VIDEO_EXTENSIONS
        if not is_video and suffix not in IMAGE_EXTENSIONS:
            return ToolResult(
                success=False,
                error=(f"Unsupported file type: {suffix}. "
                       f"Supported: {sorted(VIDEO_EXTENSIONS | IMAGE_EXTENSIONS)}"),
            )
        if mode == "qa" and not query:
            return ToolResult(success=False, error="Query is required for 'qa' mode.")
        if mode not in _MODE_INSTRUCTIONS:
            return ToolResult(success=False, error=f"Unknown mode: {mode}")

        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False,
                              error="OPENROUTER_API_KEY not set. " + self.install_instructions)

        start = time.time()
        try:
            frames = (self._sample_video(input_path, max_frames, frame_height)
                      if is_video else [input_path.read_bytes()])
        except FileNotFoundError:
            return ToolResult(success=False,
                              error="ffmpeg not found on PATH — required for video input.")
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="ffmpeg timed out extracting frames.")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"Failed to extract frames: {exc}")

        if not frames:
            return ToolResult(success=False, error="No frames could be extracted.")

        instruction = _MODE_INSTRUCTIONS[mode].format(query=query or "")
        if is_video and len(frames) > 1:
            instruction += (
                f"\n\nThese are {len(frames)} frames sampled in order from one video. "
                "They are not consecutive, so do not describe motion you cannot see."
            )

        try:
            summary = self._ask(api_key, model, instruction, frames)
        except _APIError as exc:
            return ToolResult(success=False, error=str(exc))

        return ToolResult(
            success=True,
            data={"summary": summary, "mode": mode, "model": model,
                  "frame_count": len(frames)},
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _duration_seconds(path: Path) -> float | None:
        """Video duration via ffprobe, or None if it cannot be determined."""
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, timeout=30, check=False,
            ).stdout.strip()
            value = float(out)
            return value if value > 0 else None
        except (ValueError, OSError, subprocess.SubprocessError):
            return None

    @classmethod
    def _sample_video(cls, path: Path, max_frames: int, height: int) -> list[bytes]:
        """Frames spread across the whole clip, downscaled, JPEG-encoded.

        Sampling is timestamp-driven rather than ffmpeg's `thumbnail=N` filter.
        thumbnail=N picks the most representative frame out of each N-frame
        BATCH, so combined with `-frames:v N` it never looks past the opening
        seconds: a two-second red / two-second blue test clip returned four red
        frames and a confident "nothing changes across the sequence".

        JPEG rather than PNG because these are uploaded base64-encoded and a
        1080p PNG frame is ~3 MB on the wire; the request is the bottleneck,
        not the decode.
        """
        duration = cls._duration_seconds(path)
        if duration:
            # Land inside each 1/N slice rather than on its edge — a cut exactly
            # on the boundary otherwise samples the frame before or after it,
            # depending on rounding.
            stamps = [duration * (i + 0.5) / max_frames for i in range(max_frames)]
        else:
            stamps = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            if stamps:
                for index, stamp in enumerate(stamps):
                    # -ss before -i seeks by keyframe, which is fast and close
                    # enough for sampling; accuracy here is not frame-exact.
                    subprocess.run(
                        ["ffmpeg", "-ss", f"{stamp:.3f}", "-i", str(path),
                         "-frames:v", "1", "-vf", f"scale=-2:{height}", "-q:v", "4",
                         str(tmp / f"frame_{index:04d}.jpg"), "-y", "-loglevel", "error"],
                        capture_output=True, text=True, timeout=60, check=False,
                    )
            else:
                # No duration (stream, or ffprobe missing): fall back to an even
                # frame-interval pass over the whole file.
                subprocess.run(
                    ["ffmpeg", "-i", str(path),
                     "-vf", f"scale=-2:{height}", "-vsync", "vfr",
                     "-frames:v", str(max_frames), "-q:v", "4",
                     str(tmp / "frame_%04d.jpg"), "-y", "-loglevel", "error"],
                    capture_output=True, text=True, timeout=120, check=False,
                )
            return [f.read_bytes() for f in sorted(tmp.glob("frame_*.jpg"))[:max_frames]]

    @staticmethod
    def _ask(api_key: str, model: str, instruction: str, frames: list[bytes]) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
        for blob in frames:
            mime = "image/png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{base64.b64encode(blob).decode()}"},
            })

        body = json.dumps({
            "model": model, "temperature": 0,
            "messages": [{"role": "user", "content": content}],
        }).encode()
        req = urllib.request.Request(
            _API_URL, data=body,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise _APIError(f"OpenRouter {exc.code}: {exc.read().decode()[:400]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise _APIError(f"OpenRouter unreachable: {exc}") from exc

        # A routed provider failure comes back as a 200 with an error member.
        if isinstance(data, dict) and data.get("error"):
            raise _APIError(f"OpenRouter upstream error: {str(data['error'])[:400]}")
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise _APIError(f"Unexpected response shape: {str(data)[:300]}") from exc
        if not text:
            raise _APIError("Model returned empty content.")
        return text


class _APIError(RuntimeError):
    pass
