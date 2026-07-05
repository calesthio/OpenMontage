"""Shared product constraints for Seedance-compatible video providers."""

from __future__ import annotations

from typing import Any


ALLOWED_DURATIONS = tuple(str(seconds) for seconds in range(4, 16))
DEFAULT_DURATION = "15"
MAX_DURATION_SECONDS = 15
ALLOWED_RESOLUTIONS = ("480p", "720p")
DEFAULT_RESOLUTION = "480p"
MAX_GENERATIONS_PER_BATCH = 5


def seedance_duration(inputs: dict[str, Any]) -> str:
    return str(inputs.get("duration", DEFAULT_DURATION))


def seedance_duration_seconds(inputs: dict[str, Any]) -> int:
    try:
        return int(seedance_duration(inputs))
    except (TypeError, ValueError):
        return MAX_DURATION_SECONDS


def seedance_resolution(inputs: dict[str, Any]) -> str:
    return str(inputs.get("resolution", DEFAULT_RESOLUTION))


def validate_seedance_constraints(inputs: dict[str, Any]) -> str | None:
    duration = seedance_duration(inputs)
    if duration not in ALLOWED_DURATIONS:
        return f"Seedance duration must be between 4s and 15s; got {duration!r}"

    resolution = seedance_resolution(inputs)
    if resolution not in ALLOWED_RESOLUTIONS:
        return "Seedance resolution must be 480p or 720p"

    raw_batch_size = inputs.get("batch_size", 1)
    try:
        batch_size = int(raw_batch_size)
    except (TypeError, ValueError):
        return f"Seedance batch_size must be an integer; got {raw_batch_size!r}"
    if batch_size < 1:
        return "Seedance batch_size must be at least 1"
    if batch_size > MAX_GENERATIONS_PER_BATCH:
        return "Seedance supports at most 5 generations per batch"

    return None
