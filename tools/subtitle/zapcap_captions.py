"""ZapCap captioning provider tool.

ZapCap (https://zapcap.ai) is a video-captioning API: you upload a
video, pick a styled caption *template* (Hormozi, Beast, Devin, ...), and
ZapCap transcribes the audio and renders animated, word-synced subtitles
burned into the video. This tool wraps the full REST flow as a single
OpenMontage subtitle provider.

End-to-end flow (the default ``action="caption"``):

    1. Upload the video        -> POST /videos        (local file, multipart)
                               or POST /videos/url    (public URL)            -> videoId
    2. Create a render task     -> POST /videos/{id}/task  (templateId, ...)   -> taskId
    3. Poll until completed     -> GET  /videos/{id}/task/{taskId}            -> downloadUrl
    4. Download the rendered MP4 -> stream downloadUrl to output_path

Granular actions (``list_templates``, ``upload``, ``create_task``,
``get_task``, ``approve_transcript``, ``balance``) expose each step so the
agent can drive fan-out flows (caption one video into N templates/languages
while transcribing only once via ``transcript_task_id``).

## Configuration

- ``ZAPCAP_API_KEY`` (required) — auth, sent as the ``x-api-key`` header.

This matches the env-var contract of the official ``zapcap-mcp`` server so a
single ``.env`` configures both.
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

BASE_URL = "https://api.zapcap.ai"

# Terminal task states returned by GET /videos/{id}/task/{taskId}
_TERMINAL = {"completed", "failed"}


class ZapCapCaptions(BaseTool):
    name = "zapcap_captions"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "zapcap"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC  # backend is async; execute() blocks via polling
    determinism = Determinism.STOCHASTIC  # transcription is ML-based
    runtime = ToolRuntime.API

    dependencies = ["env:ZAPCAP_API_KEY", "python:requests"]
    install_instructions = (
        "Set ZAPCAP_API_KEY to your ZapCap API key "
        "(get one at https://platform.zapcap.ai/dashboard/api-key; requires a "
        "Pro subscription + API credits)."
    )
    # No OpenMontage fallback: ZapCap's styled-caption rendering is unique.
    # For local burn-in use remotion_caption_burn (Remotion) or subtitle_gen (SRT/VTT).
    fallback_tools = ["remotion_caption_burn", "subtitle_gen"]
    agent_skills = ["zapcap-captions"]

    capabilities = [
        "upload_video",
        "list_templates",
        "create_caption_task",
        "auto_caption",
        "translate_captions",
        "approve_transcript",
        "burn_styled_captions",
    ]
    supports = {
        "styled_templates": True,
        "word_level_highlight": True,
        "translation": True,
        "emoji_captions": True,
        "byo_transcript": True,
        "offline": False,
    }
    best_for = [
        "social-ready animated, word-synced captions (TikTok/Reels/Shorts)",
        "viral caption styles (Hormozi, Beast, Devin, ...) out of the box",
        "translating + captioning the same video into many languages (fan-out)",
    ]
    not_good_for = [
        "fully offline production (requires the ZapCap API)",
        "videos longer than 30 minutes (API limit)",
        "non-speech videos (captions need an audio track to transcribe)",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "caption",
                    "list_templates",
                    "upload",
                    "create_task",
                    "get_task",
                    "approve_transcript",
                    "balance",
                ],
                "default": "caption",
                "description": (
                    "'caption' (default) runs the full flow: upload -> task -> "
                    "poll -> download. The others expose individual steps for "
                    "fan-out or manual control."
                ),
            },
            # --- source (one of) ---
            "input_path": {
                "type": "string",
                "description": "Absolute/relative path to a local video file (mp4 or mov).",
            },
            "video_url": {
                "type": "string",
                "description": "Publicly reachable video/mp4 or video/quicktime URL.",
            },
            "video_id": {
                "type": "string",
                "description": "An already-uploaded ZapCap videoId (skip the upload step).",
            },
            # --- template ---
            "template_id": {
                "type": "string",
                "description": "ZapCap template UUID (from list_templates).",
            },
            "template_name": {
                "type": "string",
                "description": (
                    "Template name (case-insensitive, e.g. 'Hormozi 1'). Resolved "
                    "to an id via /templates if template_id is not given."
                ),
            },
            # --- task options ---
            "language": {
                "type": "string",
                "description": "ISO code of the source audio (e.g. 'en'). Auto-detected if omitted.",
            },
            "translate_to": {
                "type": "string",
                "description": "Target language code to translate captions into (e.g. 'es', 'fr').",
            },
            "transcript_task_id": {
                "type": "string",
                "description": (
                    "Reuse an existing task's transcript instead of re-transcribing "
                    "(key for multi-template / multi-language fan-out)."
                ),
            },
            "auto_approve": {
                "type": "boolean",
                "default": True,
                "description": "Auto-approve the transcript so rendering starts immediately.",
            },
            "render_options": {
                "type": "object",
                "description": (
                    "Subtitle appearance overrides passed through to ZapCap: "
                    "{subsOptions, styleOptions, highlightOptions}. See the "
                    "zapcap-captions skill for the full schema."
                ),
            },
            "transcribe_settings": {
                "type": "object",
                "description": "Transcription-time options (e.g. b-roll insertion).",
            },
            "export_settings": {
                "type": "object",
                "description": "Export FPS/quality/codec/dimensions overrides.",
            },
            "dictionary": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Domain words/brand names to bias transcription toward.",
            },
            "ttl": {
                "type": "string",
                "enum": ["1d", "7d", "30d"],
                "description": "Retention for ZapCap-stored artifacts. Omit to keep indefinitely.",
            },
            # --- task id (for get_task / approve_transcript) ---
            "task_id": {
                "type": "string",
                "description": "Existing taskId (for get_task / approve_transcript).",
            },
            # --- output + polling ---
            "output_path": {
                "type": "string",
                "description": "Where to save the rendered captioned MP4 (action='caption').",
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 600,
                "description": "Max seconds to poll for completion.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "default": 3.0,
                "description": "Initial poll interval; doubles to a 15s cap.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "input_path",
        "video_url",
        "video_id",
        "template_id",
        "template_name",
        "language",
        "translate_to",
    ]
    side_effects = [
        "uploads the video to the ZapCap API",
        "creates a render task (consumes ZapCap credits)",
        "downloads the rendered video to output_path",
    ]
    user_visible_verification = [
        "Play the output video and confirm captions are burned in and synced to speech",
        "Verify the chosen template style matches expectation",
    ]

    # ------------------------------------------------------------------ #
    #  Config / status
    # ------------------------------------------------------------------ #

    def _api_key(self) -> str | None:
        return os.environ.get("ZAPCAP_API_KEY")

    def get_status(self) -> ToolStatus:
        if not self._api_key():
            return ToolStatus.UNAVAILABLE
        try:
            __import__("requests")
        except ImportError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key() or "", "accept": "application/json"}

    # ------------------------------------------------------------------ #
    #  Low-level HTTP
    # ------------------------------------------------------------------ #

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
        timeout: int = 120,
    ) -> Any:
        import requests

        url = f"{BASE_URL}{path if path.startswith('/') else '/' + path}"
        headers = self._headers()
        # Strip None query params
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body if files is None else None,
            params=clean_params or None,
            files=files,
            timeout=timeout,
        )
        if resp.status_code < 200 or resp.status_code >= 300:
            body = resp.text[:500]
            try:
                j = resp.json()
                if isinstance(j, dict) and "message" in j:
                    body = j["message"]
            except Exception:
                pass
            raise RuntimeError(
                f"ZapCap {method} {path} -> {resp.status_code} {resp.reason}: {body}"
            )
        if resp.status_code == 204 or not resp.text:
            return None
        try:
            return resp.json()
        except Exception:
            return resp.text

    # ------------------------------------------------------------------ #
    #  API operations
    # ------------------------------------------------------------------ #

    def _list_templates(self) -> list[dict]:
        data = self._request("GET", "/templates")
        return data if isinstance(data, list) else []

    def _resolve_template_id(
        self, template_id: str | None, template_name: str | None
    ) -> str:
        if template_id:
            return template_id
        if not template_name:
            raise ValueError("Provide template_id or template_name.")
        templates = self._list_templates()
        want = template_name.strip().lower()
        for t in templates:
            if str(t.get("name", "")).strip().lower() == want:
                return t["id"]
        available = ", ".join(sorted(str(t.get("name")) for t in templates))
        raise ValueError(
            f"Template named {template_name!r} not found. Available: {available}"
        )

    def _upload(
        self,
        *,
        input_path: str | None,
        video_url: str | None,
        ttl: str | None,
    ) -> dict:
        params = {"ttl": ttl} if ttl else None
        if video_url:
            return self._request("POST", "/videos/url", json_body={"url": video_url}, params=params)
        if input_path:
            p = Path(input_path)
            if not p.is_file():
                raise FileNotFoundError(f"Video file not found: {input_path}")
            with open(p, "rb") as fh:
                files = {"file": (p.name, fh, "video/mp4")}
                return self._request("POST", "/videos", files=files, params=params, timeout=600)
        raise ValueError("Provide input_path or video_url to upload.")

    def _create_task(self, video_id: str, inputs: dict[str, Any]) -> dict:
        template_id = self._resolve_template_id(
            inputs.get("template_id"), inputs.get("template_name")
        )
        body: dict[str, Any] = {"templateId": template_id}
        # autoApprove defaults to True for agentic flows
        body["autoApprove"] = inputs.get("auto_approve", True)
        for key, api_key in (
            ("language", "language"),
            ("translate_to", "translateTo"),
            ("transcript_task_id", "transcriptTaskId"),
            ("render_options", "renderOptions"),
            ("transcribe_settings", "transcribeSettings"),
            ("export_settings", "exportSettings"),
            ("dictionary", "dictionary"),
        ):
            if inputs.get(key) is not None:
                body[api_key] = inputs[key]
        params = {"ttl": inputs["ttl"]} if inputs.get("ttl") else None
        data = self._request(
            "POST", f"/videos/{video_id}/task", json_body=body, params=params
        )
        return {"taskId": data["taskId"], "templateId": template_id}

    def _get_task(self, video_id: str, task_id: str) -> dict:
        return self._request("GET", f"/videos/{video_id}/task/{task_id}")

    def _approve_transcript(self, video_id: str, task_id: str) -> Any:
        return self._request(
            "POST", f"/videos/{video_id}/task/{task_id}/approve-transcript"
        )

    def _poll(
        self,
        video_id: str,
        task_id: str,
        *,
        wait_for: str = "completed",
        timeout_seconds: int = 600,
        poll_interval_seconds: float = 3.0,
    ) -> dict:
        deadline = time.time() + timeout_seconds
        interval = poll_interval_seconds
        last: dict = {}
        while True:
            last = self._get_task(video_id, task_id)
            status = last.get("status")
            if status == "failed":
                raise RuntimeError(
                    f"ZapCap task failed: {last.get('error') or last}"
                )
            if status == wait_for:
                return last
            if wait_for == "transcriptionCompleted" and status in _TERMINAL:
                return last
            if time.time() >= deadline:
                raise TimeoutError(
                    f"ZapCap task {task_id} did not reach '{wait_for}' within "
                    f"{timeout_seconds}s (last status: {status})."
                )
            time.sleep(min(interval, max(0.0, deadline - time.time())))
            interval = min(interval * 2, 15.0)

    def _download(self, url: str, output_path: str) -> str:
        import requests

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(out, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
        return str(out)

    # ------------------------------------------------------------------ #
    #  Execute
    # ------------------------------------------------------------------ #

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._api_key():
            return ToolResult(
                success=False,
                error="ZAPCAP_API_KEY not set. " + self.install_instructions,
            )

        action = inputs.get("action", "caption")
        start = time.time()
        try:
            if action == "list_templates":
                templates = self._list_templates()
                return ToolResult(
                    success=True,
                    data={
                        "count": len(templates),
                        "templates": [
                            {
                                "id": t.get("id"),
                                "name": t.get("name"),
                                "categories": t.get("categories", []),
                            }
                            for t in templates
                        ],
                    },
                    duration_seconds=round(time.time() - start, 2),
                )

            if action == "balance":
                data = self._request("GET", "/credits/balance")
                return ToolResult(success=True, data={"balance": data})

            if action == "upload":
                up = self._upload(
                    input_path=inputs.get("input_path"),
                    video_url=inputs.get("video_url"),
                    ttl=inputs.get("ttl"),
                )
                return ToolResult(
                    success=True,
                    data={"videoId": up.get("id"), "status": up.get("status")},
                    duration_seconds=round(time.time() - start, 2),
                )

            if action == "get_task":
                task = self._get_task(inputs["video_id"], inputs["task_id"])
                return ToolResult(success=True, data=task)

            if action == "approve_transcript":
                self._approve_transcript(inputs["video_id"], inputs["task_id"])
                return ToolResult(success=True, data={"approved": True})

            if action == "create_task":
                video_id = inputs["video_id"]
                created = self._create_task(video_id, inputs)
                return ToolResult(
                    success=True,
                    data={"videoId": video_id, **created},
                    duration_seconds=round(time.time() - start, 2),
                )

            # --- default: full caption flow ---
            return self._caption_flow(inputs, start)

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"ZapCap {action} failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

    def _caption_flow(self, inputs: dict[str, Any], start: float) -> ToolResult:
        # 1. Resolve / upload to get a videoId
        video_id = inputs.get("video_id")
        upload_status = "reused"
        if not video_id:
            up = self._upload(
                input_path=inputs.get("input_path"),
                video_url=inputs.get("video_url"),
                ttl=inputs.get("ttl"),
            )
            video_id = up.get("id")
            upload_status = up.get("status", "uploaded")

        # 2. Create the render task
        created = self._create_task(video_id, inputs)
        task_id = created["taskId"]

        # 3. Poll until completed
        task = self._poll(
            video_id,
            task_id,
            wait_for="completed",
            timeout_seconds=inputs.get("timeout_seconds", 600),
            poll_interval_seconds=inputs.get("poll_interval_seconds", 3.0),
        )
        download_url = task.get("downloadUrl")
        if not download_url:
            return ToolResult(
                success=False,
                error=f"Task completed but no downloadUrl present: {task}",
            )

        # 4. Download the rendered video
        output_path = inputs.get("output_path")
        if not output_path:
            output_path = f"zapcap_captioned_{task_id[:8]}.mp4"
        local_path = self._download(download_url, output_path)

        return ToolResult(
            success=True,
            data={
                "videoId": video_id,
                "taskId": task_id,
                "templateId": created["templateId"],
                "uploadStatus": upload_status,
                "status": task.get("status"),
                "downloadUrl": download_url,
                "transcriptUrl": task.get("transcript"),
                "output": local_path,
            },
            artifacts=[local_path],
            model="zapcap",
            duration_seconds=round(time.time() - start, 2),
        )
