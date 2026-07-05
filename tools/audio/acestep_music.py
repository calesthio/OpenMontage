"""ACE-Step open-weight music generation (self-hosted, ~free at scale).

ACE-Step 1.5 (MIT license) renders full instrumental/vocal tracks on a GPU in
seconds — ~2-3s of inference on an A100, 15x+ realtime on a consumer 4090.
Run as a RunPod serverless endpoint, it costs fractions of a cent per track
versus paid music APIs (ElevenLabs `music_gen`, Suno `suno_music`), so it is
the bulk/background-music default. Reserve the paid APIs for hero tracks.

Backend: a RunPod serverless endpoint running an ACE-Step worker. The tool
reports UNAVAILABLE until both env vars are set, so it never disturbs existing
flows — it simply joins the `music_generation` menu once configured.

    RUNPOD_API_KEY            — RunPod account key
    RUNPOD_ACESTEP_ENDPOINT_ID — the deployed ACE-Step serverless endpoint id

The RunPod REST envelope (runsync + status, Bearer auth, {"input": ...} /
{"output": ...}) is standard. The *inner* input/output field names are
worker-specific — they are isolated in `_build_input` / `_extract_audio` and
marked with `ponytail:` so they are the one knob to confirm against your
deployed worker on first run.
"""

from __future__ import annotations

import base64
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

_RUNPOD_BASE = "https://api.runpod.ai/v2"
# A100 80GB serverless ≈ $2.50/hr; a track needs only a few GPU-seconds.
_SERVERLESS_USD_PER_HOUR = 2.50


class AceStepMusic(BaseTool):
    name = "acestep_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "acestep"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID  # self-hosted GPU reached over the RunPod API

    dependencies = []  # checked dynamically via env vars
    install_instructions = (
        "Deploy an ACE-Step RunPod serverless endpoint, then set:\n"
        "  export RUNPOD_API_KEY=your_runpod_key\n"
        "  export RUNPOD_ACESTEP_ENDPOINT_ID=your_endpoint_id\n"
        "ACE-Step is MIT-licensed and open-weight — https://ace-step.github.io/"
    )

    agent_skills = ["acestep", "music", "sound-effects"]

    capabilities = [
        "generate_background_music",
        "generate_instrumental",
        "generate_vocal_track",
    ]

    # best_for drives task_fit + signals the bulk/cheap lane to the scorer.
    best_for = [
        "bulk background music generation",
        "instrumental underscore for narration",
        "high-volume music at near-zero cost",
        "self-hosted open-weight music (MIT license)",
        "draft and iteration music",
    ]
    supports = {
        "instrumental": True,
        "lyrics": True,
        "bpm_control": True,
        "key_control": True,
        "seed": True,
    }

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Caption = overall style: genre, instruments, mood, "
                    "production quality. Do NOT write BPM/key here — use the "
                    "dedicated params. See the `acestep` skill for prompt craft."
                ),
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 10,
                "maximum": 600,
                "description": (
                    "Target duration in seconds (10-600). Match the target "
                    "video/scene duration from the script/proposal."
                ),
            },
            "bpm": {
                "type": "number",
                "minimum": 30,
                "maximum": 300,
                "description": "Tempo. Pass as metadata, not in the prompt.",
            },
            "key": {
                "type": "string",
                "description": "Musical key/mode, e.g. 'C Major', 'A Minor'.",
            },
            "lyrics": {
                "type": "string",
                "description": (
                    "Optional. Structure tags ([Verse]/[Chorus]) drive temporal "
                    "flow; omit for instrumental. Empty => force_instrumental."
                ),
            },
            "force_instrumental": {
                "type": "boolean",
                "default": True,
                "description": "True for background beds under narration.",
            },
            "seed": {
                "type": "integer",
                "description": "Lock randomness when iterating on prompt/lyrics.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "duration_seconds", "bpm", "key", "lyrics", "seed"]
    side_effects = ["writes audio file to output_path", "calls RunPod ACE-Step endpoint"]
    user_visible_verification = [
        "Listen to generated music for mood, tempo, and quality",
    ]

    # ---- availability ----

    def get_status(self) -> ToolStatus:
        if os.environ.get("RUNPOD_API_KEY") and os.environ.get("RUNPOD_ACESTEP_ENDPOINT_ID"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # ---- estimates ----

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Near-free: a few serverless GPU-seconds per track.

        ACE-Step needs roughly a tenth of the target duration in inference time
        (a 60s track ≈ ~6s of GPU). That is fractions of a cent — which is the
        whole point: the scorer's cost_efficiency lane ranks this above the
        paid music APIs for bulk work.
        """
        duration = inputs.get("duration_seconds") or 60
        inference_seconds = max(3.0, float(duration) * 0.1)
        return round(inference_seconds / 3600.0 * _SERVERLESS_USD_PER_HOUR, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # A few seconds of inference, plus serverless queue/cold-start headroom.
        return 12.0

    # ---- execution ----

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("RUNPOD_API_KEY")
        endpoint_id = os.environ.get("RUNPOD_ACESTEP_ENDPOINT_ID")
        if not (api_key and endpoint_id):
            return ToolResult(
                success=False,
                error="ACE-Step not configured. " + self.install_instructions,
            )

        start = time.time()
        try:
            audio_bytes, fmt = self._run_runpod(inputs, api_key, endpoint_id)
        except Exception as e:  # noqa: BLE001 - surface any backend failure to the agent
            return ToolResult(success=False, error=f"ACE-Step generation failed: {e}")

        output_path = Path(inputs.get("output_path", f"acestep_music.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        return ToolResult(
            success=True,
            data={
                "provider": "acestep",
                "prompt": inputs["prompt"],
                "duration_seconds": inputs.get("duration_seconds"),
                "output": str(output_path),
                "format": fmt,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            seed=inputs.get("seed"),
            model="ace-step-1.5",
            duration_seconds=round(time.time() - start, 2),
        )

    # ---- RunPod plumbing ----

    def _run_runpod(
        self, inputs: dict[str, Any], api_key: str, endpoint_id: str
    ) -> tuple[bytes, str]:
        import requests

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": self._build_input(inputs)}

        resp = requests.post(
            f"{_RUNPOD_BASE}/{endpoint_id}/runsync",
            headers=headers,
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        body = resp.json()

        # runsync may still return before completion for a queued job — poll status.
        status = body.get("status")
        job_id = body.get("id")
        deadline = time.time() + 180
        while status in {"IN_QUEUE", "IN_PROGRESS"} and job_id and time.time() < deadline:
            time.sleep(2)
            s = requests.get(
                f"{_RUNPOD_BASE}/{endpoint_id}/status/{job_id}",
                headers=headers,
                timeout=30,
            )
            s.raise_for_status()
            body = s.json()
            status = body.get("status")

        if status and status != "COMPLETED":
            raise RuntimeError(f"RunPod job status={status}: {body.get('error', body)}")

        return self._extract_audio(body.get("output", body))

    @staticmethod
    def _build_input(inputs: dict[str, Any]) -> dict[str, Any]:
        """Map tool inputs to the ACE-Step worker's input schema.

        ponytail: worker-specific field names — this is the one knob to confirm
        against your deployed ACE-Step RunPod worker. The envelope around it
        (runsync/status, Bearer auth) is standard RunPod and needs no changes.
        """
        lyrics = (inputs.get("lyrics") or "").strip()
        payload: dict[str, Any] = {
            "task": "text2music",
            "prompt": inputs["prompt"],
            "duration": inputs.get("duration_seconds") or 60,
            "force_instrumental": inputs.get("force_instrumental", not lyrics),
            "format": "mp3",
        }
        if inputs.get("bpm") is not None:
            payload["bpm"] = inputs["bpm"]
        if inputs.get("key"):
            payload["key"] = inputs["key"]
        if lyrics:
            payload["lyrics"] = lyrics
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        return payload

    @staticmethod
    def _extract_audio(output: Any) -> tuple[bytes, str]:
        """Pull audio bytes + format from a worker output.

        ponytail: handles the common worker shapes — base64 string, a dict with
        an audio/audio_base64 field, or a downloadable URL. Confirm which your
        worker emits and this covers it; extend here if it returns something else.
        """
        import requests

        def _from_value(val: Any, fmt: str) -> tuple[bytes, str] | None:
            if isinstance(val, str):
                if val.startswith("http://") or val.startswith("https://"):
                    r = requests.get(val, timeout=120)
                    r.raise_for_status()
                    return r.content, val.rsplit(".", 1)[-1].split("?")[0] or fmt
                # assume base64-encoded audio
                return base64.b64decode(val), fmt
            return None

        if isinstance(output, dict):
            fmt = output.get("format", "mp3")
            for key in ("audio", "audio_base64", "audio_url", "url", "output"):
                if key in output and output[key]:
                    got = _from_value(output[key], fmt)
                    if got:
                        return got
        else:
            got = _from_value(output, "mp3")
            if got:
                return got

        raise RuntimeError(f"Could not find audio in ACE-Step output: {type(output)}")
