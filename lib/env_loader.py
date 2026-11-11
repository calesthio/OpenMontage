"""Environment variable loader for OpenMontage.

The one place a ``.env`` file is read. ``tools/base_tool.py`` (at import) and
``ToolRegistry.discover()`` both call ``load_env()``; there used to be three
parsers with three slightly different ideas of what a ``.env`` line means.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

_INLINE_COMMENT = re.compile(r"(^|\s)#")


def _parse_env_text(text: str) -> dict[str, str]:
    """Minimal ``.env`` parser, used only when python-dotenv is unavailable.

    ``KEY=value`` per line, optional ``export`` prefix, ``#`` comments, quoted
    values taken verbatim, and an inline comment stripped from an unquoted
    value so ``KEY=   # note`` yields ``""`` rather than ``"# note"``.
    """
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if value[:1] in ("'", '"'):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            match = _INLINE_COMMENT.search(value)
            if match:
                value = value[: match.start()]
            value = value.strip()
        if key:
            values[key] = value
    return values


def read_env_file(env_path: Path) -> dict[str, str]:
    """Key/value pairs of a ``.env`` file. Empty when the file is absent."""
    if not env_path.is_file():
        return {}
    try:
        from dotenv import dotenv_values

        return {
            key: value
            for key, value in dotenv_values(env_path, encoding="utf-8").items()
            if key and value is not None
        }
    except Exception:
        # python-dotenv missing, or a file it cannot decode: tools must still
        # find their keys, so fall back to the built-in parser.
        with open(env_path, encoding="utf-8", errors="ignore") as handle:
            return _parse_env_text(handle.read())


def load_env(project_root: Optional[Path] = None) -> None:
    """Load ``<project_root>/.env`` into ``os.environ``.

    A variable that is already set to a non-blank value is left alone; one
    that is unset or blank takes the file's value.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    for key, value in read_env_file(Path(project_root) / ".env").items():
        if not os.environ.get(key, "").strip():
            os.environ[key] = value


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable with optional default."""
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Get a required environment variable. Raises if missing."""
    value = os.environ.get(key)
    if value is None:
        raise EnvironmentError(f"Required environment variable {key!r} is not set")
    return value
