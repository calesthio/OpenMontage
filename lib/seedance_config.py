"""Read Volcengine Seedance settings from the local skill config or environment."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("~/.seedance/config.json")
DEFAULT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_IMAGE_MODEL = "doubao-seedream-5-0-pro-260628"
DEFAULT_VIDEO_MODEL = "doubao-seedance-2-5-260628"
DEFAULT_DURATION = 8
DEFAULT_RATIO = "9:16"
SETUP_HINT = (
    "请先配置火山方舟 ARK API Key：运行 "
    "`python3 ~/.codex/skills/seedance-product-scene/scripts/seedance_client.py init`，"
    "或在环境中设置 ARK_API_KEY。"
)


class SeedanceConfigError(ValueError):
    """Raised when Seedance settings cannot be loaded safely."""


@dataclass(frozen=True)
class SeedanceConfig:
    api_key: str
    api_base: str
    image_model: str
    video_model: str
    default_duration: int
    default_ratio: str
    source: str


def mask_api_key(value: str) -> str:
    """Return a short preview that never exposes the middle of a secret."""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _resolve_config_path(config_path: Path | None) -> Path:
    if config_path is not None:
        return Path(config_path).expanduser()
    configured = os.environ.get("SEEDANCE_CONFIG_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_CONFIG_PATH.expanduser()


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SeedanceConfigError(
            f"火山方舟配置文件不是有效 JSON，请检查 {path}。"
        ) from exc
    if not isinstance(raw, dict):
        raise SeedanceConfigError(
            f"火山方舟配置文件必须是 JSON 对象，请检查 {path}。"
        )
    return raw


def _string_setting(
    *,
    name: str,
    env_name: str,
    file_data: dict[str, Any],
    default: str | None = None,
) -> str:
    value = os.environ.get(env_name) or file_data.get(name) or default
    if not isinstance(value, str) or not value.strip():
        raise SeedanceConfigError(f"火山方舟配置字段 {name} 缺失或格式不正确。")
    return value.strip()


def load_seedance_config(config_path: Path | None = None) -> SeedanceConfig:
    """Load settings with environment variables taking precedence over JSON."""
    path = _resolve_config_path(config_path)
    file_data = _read_config_file(path)

    api_key = os.environ.get("ARK_API_KEY") or file_data.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise SeedanceConfigError(f"尚未找到火山方舟 API Key。{SETUP_HINT}")

    api_base = _string_setting(
        name="api_base",
        env_name="ARK_BASE_URL",
        file_data=file_data,
        default=DEFAULT_API_BASE,
    )
    if not api_base.startswith("https://"):
        raise SeedanceConfigError("火山方舟配置字段 api_base 必须是 https 地址。")

    image_model = _string_setting(
        name="image_model",
        env_name="ARK_SEEDREAM_MODEL",
        file_data=file_data,
        default=DEFAULT_IMAGE_MODEL,
    )
    video_model = _string_setting(
        name="video_model",
        env_name="ARK_SEEDANCE_MODEL",
        file_data=file_data,
        default=DEFAULT_VIDEO_MODEL,
    )

    duration = file_data.get("default_duration", DEFAULT_DURATION)
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
        raise SeedanceConfigError(
            "火山方舟配置字段 default_duration 必须是大于 0 的整数。"
        )

    ratio = file_data.get("default_ratio", DEFAULT_RATIO)
    if not isinstance(ratio, str) or not ratio.strip():
        raise SeedanceConfigError(
            "火山方舟配置字段 default_ratio 必须是非空字符串。"
        )

    return SeedanceConfig(
        api_key=api_key.strip(),
        api_base=api_base.rstrip("/"),
        image_model=image_model,
        video_model=video_model,
        default_duration=duration,
        default_ratio=ratio.strip(),
        source=str(path) if path.is_file() else "environment/defaults",
    )
