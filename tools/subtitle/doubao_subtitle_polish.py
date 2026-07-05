"""Doubao subtitle polishing with local timing control."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from tools.analysis.doubao_vision_understand import _extract_content, _parse_json_content
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
from tools.subtitle.oral_subtitle_planner import (
    OralSubtitlePlanner,
    _assign_cue_times,
    _split_for_oral_display,
)


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def _api_key() -> str | None:
    return (
        os.environ.get("DOUBAO_SUBTITLE_API_KEY")
        or os.environ.get("DOUBAO_VISION_API_KEY")
        or os.environ.get("ARK_API_KEY")
    )


def _base_url() -> str:
    return (
        os.environ.get("DOUBAO_SUBTITLE_BASE_URL")
        or os.environ.get("DOUBAO_VISION_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def _model_name(inputs: dict[str, Any]) -> str:
    model = str(
        inputs.get("model")
        or os.environ.get("DOUBAO_SUBTITLE_MODEL")
        or os.environ.get("DOUBAO_VISION_MODEL")
        or ""
    ).strip()
    if not model:
        raise ValueError("DOUBAO_SUBTITLE_MODEL, DOUBAO_VISION_MODEL, or model input is required")
    return model


class DoubaoSubtitlePolish(BaseTool):
    name = "doubao_subtitle_polish"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "doubao"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies: list[str] = []
    install_instructions = (
        "Set DOUBAO_SUBTITLE_API_KEY or DOUBAO_VISION_API_KEY or ARK_API_KEY.\n"
        "Set DOUBAO_SUBTITLE_MODEL or DOUBAO_VISION_MODEL to the Ark model/endpoint id.\n"
        "Use dry_run=true to preview local fallback without any API call."
    )
    capabilities = ["polish_oral_subtitle_cues", "doubao_subtitle_segmentation"]
    supports = {
        "dry_run_without_key": True,
        "volcengine_responses_api": True,
        "json_output": True,
        "local_timing_allocation": True,
    }
    best_for = [
        "using Doubao to segment and polish Chinese口播 subtitles",
        "keeping subtitle timestamps deterministic and locally controlled",
        "previewing paid subtitle polish prompts before calling Ark",
    ]
    not_good_for = ["word-accurate forced alignment", "unreviewed copy rewriting"]
    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "start": {"type": "number", "default": 0},
            "end": {"type": "number"},
            "duration": {"type": "number"},
            "dry_run": {"type": "boolean", "default": True},
            "model": {"type": "string"},
            "max_chars_per_line": {"type": "integer", "default": 12},
            "max_lines_per_cue": {"type": "integer", "default": 2},
            "min_duration": {"type": "number", "default": 0.8},
            "max_duration": {"type": "number", "default": 2.2},
            "temperature": {"type": "number", "default": 0.1},
            "max_tokens": {"type": "integer", "default": 1200},
            "timeout_seconds": {"type": "integer", "default": 120},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "mode": {"type": "string"},
            "api_called": {"type": "boolean"},
            "cue_count": {"type": "integer"},
            "cues": {"type": "array"},
            "prompt": {"type": "string"},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=2,
        network_required=True,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "start", "end", "duration", "model"]
    side_effects = ["may call Doubao/Volcengine Ark Responses API when dry_run=false"]
    user_visible_verification = [
        "Review the generated cue list before burning subtitles",
        "Confirm paid API calls are explicitly approved before dry_run=false",
    ]

    def get_status(self) -> ToolStatus:
        if _api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.DEGRADED

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        if inputs.get("dry_run", True):
            return 0.0
        text_length = len(str(inputs.get("text") or ""))
        return round(max(text_length, 1) / 1000 * 0.001, 6)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        text = str(inputs.get("text") or "").strip()
        if not text:
            return ToolResult(success=False, error="text is required")

        try:
            window = _timing_window(inputs)
            constraints = _constraints(inputs)
        except (TypeError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc))

        prompt = _build_prompt(text, constraints)
        if inputs.get("dry_run", True):
            return _dry_run_result(
                text=text,
                prompt=prompt,
                window=window,
                constraints=constraints,
                duration_seconds=round(time.time() - start_time, 3),
            )

        api_key = _api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="Doubao subtitle API key not set. " + self.install_instructions,
            )

        try:
            payload = _build_payload(inputs, prompt)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        import requests

        try:
            response = requests.post(
                f"{_base_url()}/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=int(inputs.get("timeout_seconds", 120)),
            )
            response.raise_for_status()
            response_payload = response.json()
            content = _extract_content(response_payload)
            parsed = _parse_json_content(content)
        except json.JSONDecodeError:
            excerpt = (content if "content" in locals() else "").strip()
            if not excerpt and "response_payload" in locals():
                excerpt = json.dumps(response_payload, ensure_ascii=False)[:800]
            excerpt = excerpt.replace(api_key, "[redacted]")
            return ToolResult(
                success=False,
                error=f"Doubao subtitle response was not valid JSON. Response excerpt: {excerpt}",
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Doubao subtitle request failed: {exc}")

        try:
            cue_texts = _cue_texts_from_parsed(parsed, constraints)
            cues = _assign_cue_times(
                cue_texts,
                start=window["start"],
                end=window["end"],
                max_chars_per_line=constraints["max_chars_per_line"],
                min_duration=constraints["min_duration"],
                max_duration=constraints["max_duration"],
            )
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "mode": "live",
                "api_called": True,
                "model": payload["model"],
                "prompt": prompt,
                "cue_count": len(cues),
                "cues": cues,
                "notes": parsed.get("notes", []),
                "usage": response_payload.get("usage", {}),
            },
            duration_seconds=round(time.time() - start_time, 3),
            model=payload["model"],
        )


def _timing_window(inputs: dict[str, Any]) -> dict[str, float]:
    start = float(inputs.get("start", 0))
    if inputs.get("end") is not None:
        end = float(inputs["end"])
    else:
        end = start + float(inputs.get("duration", 0))
    if end <= start:
        raise ValueError("end must be greater than start")
    return {"start": start, "end": end}


def _constraints(inputs: dict[str, Any]) -> dict[str, Any]:
    max_chars_per_line = max(4, int(inputs.get("max_chars_per_line", 12)))
    return {
        "max_chars_per_line": max_chars_per_line,
        "max_lines_per_cue": max(1, int(inputs.get("max_lines_per_cue", 2))),
        "min_duration": max(0.1, float(inputs.get("min_duration", 0.8))),
        "max_duration": max(0.1, float(inputs.get("max_duration", 2.2))),
    }


def _build_prompt(text: str, constraints: dict[str, Any]) -> str:
    return (
        "你是短视频口播字幕编辑。请把下面中文口播文案切成适合竖屏短视频的字幕 cue。"
        "只输出 JSON，不要输出 Markdown。不要编造时间戳，时间轴会由本地系统分配。\n"
        "规则：\n"
        f"- 每条 cue 最多 {constraints['max_lines_per_cue']} 行；\n"
        f"- 每行最多 {constraints['max_chars_per_line']} 个中文字符；\n"
        "- 一条 cue 尽量是一口气能说完的短语；\n"
        "- 不要拆开固定词：法律顾问、合法权益、刑事案件、工程扯皮、律师朋友；\n"
        "- 保留原意，不新增事实，不改人名；\n"
        '- JSON 格式：{"cues":[{"text":"字幕文本"}],"notes":["可选说明"]}\n'
        f"文案：{text}"
    )


def _build_payload(inputs: dict[str, Any], prompt: str) -> dict[str, Any]:
    return {
        "model": _model_name(inputs),
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "temperature": float(inputs.get("temperature", 0.1)),
        "max_output_tokens": int(inputs.get("max_tokens", 1200)),
    }


def _dry_run_result(
    *,
    text: str,
    prompt: str,
    window: dict[str, float],
    constraints: dict[str, Any],
    duration_seconds: float,
) -> ToolResult:
    result = OralSubtitlePlanner().execute(
        {
            "text": text,
            "start": window["start"],
            "end": window["end"],
            **constraints,
        }
    )
    if not result.success:
        return result
    return ToolResult(
        success=True,
        data={
            "provider": "doubao",
            "mode": "dry_run",
            "api_called": False,
            "prompt": prompt,
            "cue_count": (result.data or {}).get("cue_count", 0),
            "cues": (result.data or {}).get("cues", []),
            "notes": ["dry_run 使用本地 oral_subtitle_planner；未调用豆包 API。"],
        },
        duration_seconds=duration_seconds,
    )


def _cue_texts_from_parsed(parsed: dict[str, Any], constraints: dict[str, Any]) -> list[str]:
    raw_cues = parsed.get("cues")
    if not isinstance(raw_cues, list) or not raw_cues:
        raise ValueError("Doubao subtitle response must include a non-empty cues list")

    cue_texts: list[str] = []
    for raw in raw_cues:
        text = ""
        if isinstance(raw, str):
            text = raw
        elif isinstance(raw, dict):
            text = str(raw.get("text") or "")
        text = text.strip()
        if not text:
            continue
        cue_texts.extend(
            _split_for_oral_display(
                text,
                max_chars_per_line=constraints["max_chars_per_line"],
                max_lines_per_cue=constraints["max_lines_per_cue"],
            )
        )

    if not cue_texts:
        raise ValueError("Doubao subtitle response had no usable cue text")
    return cue_texts
