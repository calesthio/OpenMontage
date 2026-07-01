"""WaveSpeed profile resolution for WaveSpeed gateway mode."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_TASK_TYPES = {
    "text_to_image",
    "image_to_video",
    "text_to_video",
    "text_to_audio",
    "digital_human",
    "image_edit",
    "image_upscale",
    "text_to_music",
    "background_removal",
    "lip_sync",
}
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class WaveSpeedConfigError(ValueError):
    """Raised when WaveSpeed config cannot resolve a usable model."""


@dataclass(frozen=True)
class WaveSpeedTaskConfig:
    """Resolved WaveSpeed config for one generation task."""

    mode: str
    profile: str
    task_type: str
    model_id: str
    params: dict[str, Any]


def _load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise WaveSpeedConfigError(f"Config file {path} must contain a YAML object.")
    return raw


def load_wavespeed_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load only the `wavespeed` block from OpenMontage config."""

    raw = _load_config(config_path)
    wavespeed = raw.get("wavespeed") or {}
    if not isinstance(wavespeed, dict):
        raise WaveSpeedConfigError("config.yaml wavespeed block must be an object.")
    return wavespeed


def active_wavespeed_profile(config_path: Path | None = None) -> str | None:
    """Resolve the active WaveSpeed profile.

    Returns:
        profile name (str): Use specific profile (e.g., "default", "quality")
        None: No profile set; selector uses all profiles as candidates

    `WAVESPEED_MODEL_PROFILE` overrides config.yaml `wavespeed.active_profile`.
    The API key is deliberately ignored; it is authentication only.
    """

    wavespeed = load_wavespeed_config(config_path)
    env_profile = os.environ.get("WAVESPEED_MODEL_PROFILE", "").strip()
    if env_profile:
        return env_profile

    config_profile = wavespeed.get("active_profile")
    if config_profile is None:
        return None
    return str(config_profile) if config_profile else None


def resolve_wavespeed_task(
    task_type: str,
    *,
    explicit_model_id: str | None = None,
    explicit_params: dict[str, Any] | None = None,
    explicit_profile: str | None = None,
    config_path: Path | None = None,
) -> WaveSpeedTaskConfig:
    """Resolve model and params for a WaveSpeed task.

    Resolution order:
    1. explicit_profile if provided (from selector)
    2. active_wavespeed_profile() from config/env
    3. fail clearly

    Model resolution order:
    1. explicit model_id argument
    2. profile's model_id for task_type
    3. fail clearly

    Param merge order:
    1. profile default params
    2. explicit params override profile params

    Note: This function requires an active profile. For selector-level
    model discovery when active_profile is null, use get_wavespeed_candidates_for_task().
    """

    if task_type not in SUPPORTED_TASK_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_TASK_TYPES))
        raise WaveSpeedConfigError(
            f"Unsupported WaveSpeed task_type {task_type!r}. Expected one of: {allowed}."
        )

    wavespeed = load_wavespeed_config(config_path)
    profile_name = explicit_profile or active_wavespeed_profile(config_path)

    # If no active profile, caller should use get_wavespeed_candidates_for_task()
    if profile_name is None:
        raise WaveSpeedConfigError(
            f"WaveSpeed profile required for resolve_wavespeed_task(). "
            "Set wavespeed.active_profile in config.yaml or WAVESPEED_MODEL_PROFILE env var. "
            "For multi-profile candidate generation, use get_wavespeed_candidates_for_task()."
        )

    profiles = wavespeed.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise WaveSpeedConfigError("config.yaml wavespeed.profiles must be an object.")

    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise WaveSpeedConfigError(
            f"Active WaveSpeed profile {profile_name!r} is not configured. "
            "Add it under config.yaml wavespeed.profiles or set WAVESPEED_MODEL_PROFILE to an existing profile."
        )

    task_cfg = profile.get(task_type) or {}
    if not isinstance(task_cfg, dict):
        raise WaveSpeedConfigError(
            f"config.yaml wavespeed.profiles.{profile_name}.{task_type} must be an object."
        )

    profile_model_id = str(task_cfg.get("model_id") or "").strip()
    model_id = str(explicit_model_id or "").strip() or profile_model_id
    if not model_id:
        raise WaveSpeedConfigError(
            f"WaveSpeed model_id is not configured for task_type={task_type!r} "
            f"in active profile {profile_name!r}. Configure "
            f"config.yaml wavespeed.profiles.{profile_name}.{task_type}.model_id "
            "or pass an explicit --model-id for this task. Do not guess model IDs."
        )

    profile_params = task_cfg.get("params") or {}
    if not isinstance(profile_params, dict):
        raise WaveSpeedConfigError(
            f"config.yaml wavespeed.profiles.{profile_name}.{task_type}.params must be an object."
        )

    merged_params = dict(profile_params)
    if explicit_params:
        merged_params.update(explicit_params)

    return WaveSpeedTaskConfig(
        mode=str(wavespeed.get("mode") or "wavespeed_only"),
        profile=profile_name,
        task_type=task_type,
        model_id=model_id,
        params=merged_params,
    )


def get_wavespeed_candidates_for_task(
    task_type: str,
    config_path: Path | None = None,
) -> list[tuple[str, str]]:
    """Get WaveSpeed model candidates for a task type.

    Used by selector when active_profile is null (multi-profile mode).
    Returns all profiles' models for the task as candidates.

    Args:
        task_type: One of "text_to_image", "image_to_video", "text_to_video"
        config_path: Config file path (default: config.yaml)

    Returns:
        List of (model_id, profile_name) tuples.
        Empty if active_profile is set or no profiles configured.

    Example:
        >>> candidates = get_wavespeed_candidates_for_task("text_to_image")
        >>> # Returns [("google/nano-banana-2/text-to-image", "default"),
        >>>           ("openai/gpt-image-2/text-to-image", "quality")]
    """

    if task_type not in SUPPORTED_TASK_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_TASK_TYPES))
        raise WaveSpeedConfigError(
            f"Unsupported task_type {task_type!r}. Expected one of: {allowed}."
        )

    wavespeed = load_wavespeed_config(config_path)
    active_profile = active_wavespeed_profile(config_path)

    # If active_profile is set, selector should not use this function
    # Instead, use resolve_wavespeed_task with the active profile
    if active_profile is not None:
        return []

    profiles = wavespeed.get("profiles") or {}
    if not isinstance(profiles, dict):
        return []

    candidates: list[tuple[str, str]] = []

    for profile_name, profile_cfg in profiles.items():
        if not isinstance(profile_cfg, dict):
            continue

        task_cfg = profile_cfg.get(task_type) or {}
        if not isinstance(task_cfg, dict):
            continue

        model_id = str(task_cfg.get("model_id") or "").strip()
        if model_id:
            candidates.append((model_id, profile_name))

    return candidates


def wavespeed_doctor_report(config_path: Path | None = None) -> dict[str, Any]:
    """Return a no-network diagnostic report for WaveSpeed setup."""

    config_path = config_path or DEFAULT_CONFIG_PATH
    report: dict[str, Any] = {
        "config_path": str(config_path),
        "api_key_present": bool(os.environ.get("WAVESPEED_API_KEY")),
        "active_profile": None,
        "profile_found": False,
        "tasks": {},
        "ok": False,
        "next_steps": [],
    }

    try:
        wavespeed = load_wavespeed_config(config_path)
        profile_name = active_wavespeed_profile(config_path)
        report["active_profile"] = profile_name
        profiles = wavespeed.get("profiles") or {}
        profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
        report["profile_found"] = isinstance(profile, dict)
        if not report["profile_found"]:
            report["next_steps"].append(
                f"Add wavespeed.profiles.{profile_name} to config.yaml or set WAVESPEED_MODEL_PROFILE to an existing profile."
            )
            profile = {}

        for task_type in sorted(SUPPORTED_TASK_TYPES):
            task_cfg = profile.get(task_type) if isinstance(profile, dict) else None
            model_id = ""
            if isinstance(task_cfg, dict):
                model_id = str(task_cfg.get("model_id") or "").strip()
            present = bool(model_id)
            report["tasks"][task_type] = {
                "model_id_present": present,
                "model_id": model_id,
            }
            if not present:
                report["next_steps"].append(
                    f"Configure wavespeed.profiles.{profile_name}.{task_type}.model_id."
                )
    except WaveSpeedConfigError as exc:
        report["next_steps"].append(str(exc))

    if not report["api_key_present"]:
        report["next_steps"].append(
            "Set WAVESPEED_API_KEY in your environment or .env file."
        )

    report["ok"] = (
        report["api_key_present"]
        and report["profile_found"]
        and all(task["model_id_present"] for task in report["tasks"].values())
    )
    return report
