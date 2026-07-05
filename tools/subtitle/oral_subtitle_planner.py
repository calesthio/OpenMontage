"""Readable oral-caption cue planning for short-form Chinese videos."""

from __future__ import annotations

import re
import time
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


PROTECTED_TERMS = [
    "徐律师",
    "法律顾问",
    "合法权益",
    "刑事案件",
    "工程扯皮",
    "律师朋友",
    "实战经验",
    "这条视频",
]

PREFERRED_BREAK_BEFORE = [
    "靠谱",
    "今天",
    "不妨",
    "留个",
    "私人",
    "刑事",
    "我会",
    "你的",
]

PUNCTUATION_BREAKS = "，,、；;：:。！？!?"


class OralSubtitlePlanner(BaseTool):
    name = "oral_subtitle_planner"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies required."
    capabilities = ["plan_oral_subtitle_cues", "split_chinese_short_video_captions"]
    supports = {
        "local_dry_run": True,
        "network_required": False,
        "max_lines_per_cue": True,
        "character_weighted_timing": True,
    }
    best_for = [
        "short-form Chinese口播 subtitles",
        "turning approved copy into readable SRT cue plans",
        "local subtitle dry-runs before paid model polishing",
    ]
    not_good_for = ["word-accurate ASR alignment", "model-based rewrite without provider integration"]
    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "start": {"type": "number", "default": 0},
            "end": {"type": "number"},
            "duration": {"type": "number"},
            "max_chars_per_line": {"type": "integer", "default": 12},
            "max_lines_per_cue": {"type": "integer", "default": 2},
            "min_duration": {"type": "number", "default": 0.8},
            "max_duration": {"type": "number", "default": 2.2},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "requires_api_call": {"type": "boolean"},
            "cue_count": {"type": "integer"},
            "cues": {"type": "array"},
        },
    }
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=1)
    idempotency_key_fields = ["text", "start", "end", "duration", "max_chars_per_line"]
    side_effects: list[str] = []
    user_visible_verification = [
        "Review generated SRT visually after burn-in",
        "Confirm subtitles show no more than two short lines at a time",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        text = _normalize_text(str(inputs.get("text") or ""))
        if not text:
            return ToolResult(success=False, error="text is required")

        try:
            start = float(inputs.get("start", 0))
            if inputs.get("end") is not None:
                end = float(inputs["end"])
            else:
                end = start + float(inputs.get("duration", 0))
        except (TypeError, ValueError):
            return ToolResult(success=False, error="start/end/duration must be numeric")

        if end <= start:
            return ToolResult(success=False, error="end must be greater than start")

        max_chars_per_line = max(4, int(inputs.get("max_chars_per_line", 12)))
        max_lines_per_cue = max(1, int(inputs.get("max_lines_per_cue", 2)))
        min_duration = max(0.1, float(inputs.get("min_duration", 0.8)))
        max_duration = max(min_duration, float(inputs.get("max_duration", 2.2)))

        raw_cues = _split_for_oral_display(
            text,
            max_chars_per_line=max_chars_per_line,
            max_lines_per_cue=max_lines_per_cue,
        )
        cues = _assign_cue_times(
            raw_cues,
            start=start,
            end=end,
            max_chars_per_line=max_chars_per_line,
            min_duration=min_duration,
            max_duration=max_duration,
        )

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "requires_api_call": False,
                "style": "oral_short",
                "cue_count": len(cues),
                "cues": cues,
            },
            duration_seconds=round(time.time() - start_time, 3),
        )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _split_for_oral_display(
    text: str,
    *,
    max_chars_per_line: int,
    max_lines_per_cue: int,
) -> list[str]:
    parts = [
        part.strip()
        for part in re.findall(r"[^。！？!?，,、；;：:]+[。！？!?，,、；;：:]?", text)
        if part.strip()
    ] or [text]
    max_chars_per_cue = max_chars_per_line * max_lines_per_cue
    cues: list[str] = []
    for part in parts:
        cues.extend(
            _split_part(
                part,
                max_chars_per_line=max_chars_per_line,
                max_chars_per_cue=max_chars_per_cue,
            )
        )
    return [cue for cue in cues if cue]


def _split_part(
    text: str,
    *,
    max_chars_per_line: int,
    max_chars_per_cue: int,
) -> list[str]:
    if len(text) <= max_chars_per_line:
        return [text]
    if len(text) <= max_chars_per_cue:
        split_at = _best_split_index(text, max_chars_per_line)
        if split_at and 0 < split_at < len(text):
            left = text[:split_at]
            right = text[split_at:]
            if len(left) >= 4 and len(right) >= 4:
                return [left, *_split_part(
                    right,
                    max_chars_per_line=max_chars_per_line,
                    max_chars_per_cue=max_chars_per_cue,
                )]
        return [_wrap_two_line(text, max_chars_per_line=max_chars_per_line)]

    split_at = _best_split_index(text, max_chars_per_line) or max_chars_per_line
    return [
        text[:split_at],
        *_split_part(
            text[split_at:],
            max_chars_per_line=max_chars_per_line,
            max_chars_per_cue=max_chars_per_cue,
        ),
    ]


def _best_split_index(text: str, max_chars_per_line: int) -> int | None:
    lower_bound = max(4, max_chars_per_line // 2)

    for marker in PREFERRED_BREAK_BEFORE:
        index = text.find(marker)
        if lower_bound <= index <= max_chars_per_line and len(text) - index >= 4:
            return _protect_split_index(text, index, max_chars_per_line)

    for index in range(min(max_chars_per_line, len(text) - 1), lower_bound - 1, -1):
        if text[index - 1] in PUNCTUATION_BREAKS:
            return _protect_split_index(text, index, max_chars_per_line)

    return _protect_split_index(text, min(max_chars_per_line, len(text)), max_chars_per_line)


def _protect_split_index(text: str, split_at: int, max_chars_per_line: int) -> int:
    for term in PROTECTED_TERMS:
        start = text.find(term)
        while start >= 0:
            end = start + len(term)
            if start < split_at < end:
                if start >= 4:
                    return start
                if end <= max_chars_per_line:
                    return end
            start = text.find(term, start + 1)
    return split_at


def _wrap_two_line(text: str, *, max_chars_per_line: int) -> str:
    split_at = _best_split_index(text, max_chars_per_line)
    if not split_at or split_at >= len(text):
        return text
    return f"{text[:split_at]}\n{text[split_at:]}"


def _assign_cue_times(
    cue_texts: list[str],
    *,
    start: float,
    end: float,
    max_chars_per_line: int,
    min_duration: float,
    max_duration: float,
) -> list[dict[str, Any]]:
    if not cue_texts:
        return []

    total_duration = end - start
    weight_floor = max(1, int(max_chars_per_line * 0.65))
    weights = [max(len(text.replace("\n", "")), weight_floor) for text in cue_texts]
    total_weight = sum(weights)

    cues: list[dict[str, Any]] = []
    cursor = start
    for index, (text, weight) in enumerate(zip(cue_texts, weights), start=1):
        if index == len(cue_texts):
            cue_end = end
        else:
            duration = total_duration * weight / total_weight
            duration = min(max(duration, min_duration), max_duration)
            remaining_cues = len(cue_texts) - index
            remaining_min = remaining_cues * min_duration
            latest_end = end - remaining_min
            cue_end = min(cursor + duration, latest_end)
            if cue_end <= cursor:
                cue_end = cursor + total_duration * weight / total_weight

        cues.append(
            {
                "index": index,
                "start": round(cursor, 3),
                "end": round(cue_end, 3),
                "text": text,
            }
        )
        cursor = cue_end

    cues[-1]["end"] = round(end, 3)
    return cues
