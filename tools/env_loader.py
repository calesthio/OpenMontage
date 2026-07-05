"""Shared .env loading for OpenMontage tools."""

from __future__ import annotations

import os
import re
from pathlib import Path


ENV_FILENAMES = (".env", ".env.local")


def _parse_env_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        value = value[1:end] if end != -1 else value[1:]
    else:
        match = re.search(r"(^|\s)#", value)
        if match:
            value = value[: match.start()]
        value = value.strip()
    if not key:
        return None
    return key, value


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parsed = _parse_env_line(line)
        if parsed:
            key, value = parsed
            values[key] = value
    return values


def load_dotenv_files(root: Path | str | None = None) -> None:
    """Load `.env` and `.env.local` without overriding process env.

    `.env.local` overrides `.env` for file-provided values. Existing process
    environment variables remain authoritative.
    """
    root_path = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    existing_keys = set(os.environ)
    loaded_values: dict[str, str] = {}
    for filename in ENV_FILENAMES:
        loaded_values.update(_read_env_file(root_path / filename))
    for key, value in loaded_values.items():
        if key not in existing_keys:
            os.environ[key] = value
