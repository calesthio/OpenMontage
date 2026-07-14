"""Sound-effect / Foley generation offloaded to a free Google Colab GPU.

A free, no-API-key alternative to `sfx_gen` (ElevenLabs). Two modes:

  mode="text"  → AudioGen (facebook/audiogen-medium): text prompt to SFX,
                 e.g. "a single mechanical clock tick", "cinematic whoosh",
                 "keyboard typing". Best for discrete effects you place at a
                 timestamp yourself (Remotion audio.sfx cues).

  mode="video" → MMAudio (Sony, CVPR 2025): watches a rendered clip and
                 generates Foley SYNCED to the motion it sees. Feed it a
                 clock-hand clip and it produces ticks already aligned to the
                 hand — the natural fit for "sound follows what's on screen".

The heavy GPU compute runs on a free Colab T4 exposed over an HTTPS tunnel;
this tool is a thin client. Start the server by pasting
`tools/audio/colab/sfx_server.py` into a Colab GPU notebook — it prints the
public URL to set as COLAB_SFX_URL.

LICENSING (important): AudioGen weights are CC-BY-NC 4.0; MMAudio weights are
trained on mixed datasets (AudioSet/VGGSound/Freesound) with non-commercial
constraints. Both are marked commercial_safe=false and verdict REVIEW by
license_validator — do NOT treat as safe for monetized videos without human
sign-off. For a genuinely commercial-clean free path, use `freesound_music`
with commercial_safe=true (CC0 clips).
"""

from __future__ import annotations

import os
import time
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
from tools.audio._ratelimit import call_with_backoff


class ColabSFX(BaseTool):
    name = "colab_sfx"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "sfx_generation"
    provider = "colab-sfx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API  # remote free GPU via HTTPS tunnel

    dependencies = []  # thin HTTP client; only needs `requests`
    install_instructions = (
        "1. Open a Google Colab notebook with a T4 GPU runtime.\n"
        "2. Paste and run tools/audio/colab/sfx_server.py (see its header) —\n"
        "   it loads AudioGen (text->SFX) and optionally MMAudio (video->foley).\n"
        "3. Set COLAB_SFX_URL to the printed tunnel URL, and\n"
        "   COLAB_SFX_TOKEN to the token the server prints.\n"
        "Colab sessions are ephemeral (~90 min idle timeout) — the URL changes "
        "per session.\n"
        "Commercial-clean free alternative with no GPU: freesound_music "
        "(commercial_safe=true, CC0 clips)."
    )

    agent_skills = ["sound-effects", "elevenlabs"]

    capabilities = ["generate_sfx", "video_to_foley", "free_gpu_offload"]
    supports = {
        "seeded_generation": True,
        "text_to_sfx": True,
        "video_to_foley": True,
        "min_seconds": 0.5,
        "max_seconds": 30,
        "commercial_safe": False,  # CC-BY-NC / mixed weights — see module docstring
    }
    best_for = [
        "free SFX when no ElevenLabs key is configured (whoosh, impact, click, tick)",
        "video->foley: sound synced to on-screen motion (MMAudio) — e.g. tick to a clock hand",
        "offloading GPU compute from low-power local machines",
    ]
    not_good_for = [
        "monetized videos without human license sign-off (non-commercial weights)",
        "background music beds (use music_selector / colab_musicgen)",
        "unattended batch runs (Colab tunnel is ephemeral)",
    ]

    fallback_tools = ["sfx_gen", "freesound_music"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["text", "video"],
                "default": "text",
                "description": (
                    "'text' = AudioGen prompt->SFX. 'video' = MMAudio, generate "
                    "Foley synced to the motion in video_path."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "SFX description (text mode) or a caption hint (video mode), "
                    "e.g. 'a single mechanical clock tick', 'cinematic whoosh'."
                ),
            },
            "video_path": {
                "type": "string",
                "description": "Local path to the clip to score. Required when mode='video'.",
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 30,
                "default": 3.0,
                "description": "Target length (text mode). Video mode uses the clip length.",
            },
            "seed": {"type": "integer", "description": "Seed for reproducibility."},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, backoff_seconds=5.0,
        retryable_errors=["rate_limit", "timeout"],
    )
    idempotency_key_fields = ["mode", "prompt", "video_path", "duration_seconds", "seed"]
    side_effects = ["writes audio file to output_path", "calls Colab tunnel endpoint"]
    user_visible_verification = [
        "Listen: does the effect match the prompt / land on the on-screen action?",
        "License verdict is REVIEW — confirm monetization policy before shipping",
    ]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("COLAB_SFX_URL"):
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # free Colab tier

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # AudioGen ~a few seconds of audio in ~10-30s on a T4; MMAudio ~1.2s
        # per 8s clip + upload overhead.
        return 45.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        info = super().dry_run(inputs)
        info["endpoint_healthy"] = self._health_check()
        info["would_execute"] = info["endpoint_healthy"]
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        endpoint = os.environ.get("COLAB_SFX_URL", "").rstrip("/")
        if not endpoint:
            return ToolResult(
                success=False,
                error="COLAB_SFX_URL not set. " + self.install_instructions,
            )

        mode = inputs.get("mode", "text")
        prompt = inputs["prompt"]
        seed = inputs.get("seed")
        output_path = Path(inputs.get("output_path", "colab_sfx_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start = time.time()
        try:
            if mode == "video":
                video_path = inputs.get("video_path")
                if not video_path or not Path(video_path).exists():
                    return ToolResult(
                        success=False,
                        error="mode='video' requires an existing video_path.",
                    )
                wav_bytes, server_meta = self._foley_from_video(
                    endpoint, Path(video_path), prompt, seed
                )
            else:
                wav_bytes, server_meta = self._generate_text(
                    endpoint, prompt,
                    float(inputs.get("duration_seconds", 3.0)), seed,
                )
            output_path.write_bytes(wav_bytes)
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Colab SFX generation failed: {e}",
                duration_seconds=round(time.time() - start, 2),
            )

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "mode": mode,
                "prompt": prompt,
                "output": str(output_path),
                "format": "wav",
                "server": server_meta,
                # Consumed by license_validator.validate_assets:
                "license_url": None,
                "commercial_safe": False,
                "license_note": (
                    "AudioGen (CC-BY-NC 4.0) / MMAudio (mixed non-commercial "
                    "training data) — verdict REVIEW for monetized use. Run "
                    "license_validator before compositing; use freesound_music "
                    "(CC0) for a commercial-clean path."
                ),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=server_meta.get("model"),
        )

    # ---- remote calls ----

    def _health_check(self) -> bool:
        import requests

        endpoint = os.environ.get("COLAB_SFX_URL", "").rstrip("/")
        if not endpoint:
            return False
        try:
            response = requests.get(
                f"{endpoint}/health", headers=self._headers(), timeout=15
            )
            return response.ok
        except requests.RequestException:
            return False

    def _generate_text(
        self, endpoint: str, prompt: str, seconds: float, seed: int | None
    ) -> tuple[bytes, dict]:
        import requests

        payload: dict[str, Any] = {"prompt": prompt, "duration_seconds": seconds}
        if seed is not None:
            payload["seed"] = seed

        response = call_with_backoff(
            lambda: requests.post(
                f"{endpoint}/generate",
                json=payload,
                headers=self._headers(),
                timeout=600,  # cold model load + generation on a T4
            ),
            provider=self.provider,
            max_retries=self.retry_policy.max_retries,
            base_delay=self.retry_policy.backoff_seconds,
        )
        return self._extract_audio(response, default_model="facebook/audiogen-medium")

    def _foley_from_video(
        self, endpoint: str, video_path: Path, prompt: str, seed: int | None
    ) -> tuple[bytes, dict]:
        import requests

        data: dict[str, Any] = {"prompt": prompt}
        if seed is not None:
            data["seed"] = str(seed)

        with open(video_path, "rb") as fh:
            files = {"video": (video_path.name, fh, "video/mp4")}
            response = call_with_backoff(
                lambda: requests.post(
                    f"{endpoint}/foley",
                    data=data,
                    files=files,
                    headers=self._headers(),
                    timeout=900,  # upload + MMAudio inference
                ),
                provider=self.provider,
                max_retries=self.retry_policy.max_retries,
                base_delay=self.retry_policy.backoff_seconds,
            )
        return self._extract_audio(response, default_model="MMAudio")

    @staticmethod
    def _extract_audio(response: Any, default_model: str) -> tuple[bytes, dict]:
        content_type = response.headers.get("Content-Type", "")
        if "audio" not in content_type:
            raise RuntimeError(
                f"Server returned {content_type!r} instead of audio: "
                f"{response.text[:300]}"
            )
        meta = {
            "model": response.headers.get("X-Model", default_model),
            "device": response.headers.get("X-Device", "unknown"),
        }
        return response.content, meta

    @staticmethod
    def _headers() -> dict[str, str]:
        headers = {"User-Agent": "OpenMontage/0.1 (colab_sfx)"}
        token = os.environ.get("COLAB_SFX_TOKEN")
        if token:
            headers["X-Auth-Token"] = token
        return headers
