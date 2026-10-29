"""Environment variable loader for OpenMontage.

Thin typed accessors over os.environ. The actual .env parsing lives in
`tools.base_tool.load_dotenv` — the single parser in the project — and this
module delegates to it so a value cannot depend on which loader happened to
run first.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from tools.base_tool import load_dotenv


def load_env(project_root: Optional[Path] = None) -> None:
    """Load .env from the project root (or a caller-supplied root)."""
    env_path = None
    if project_root is not None:
        env_path = Path(project_root) / ".env"
    load_dotenv(env_path)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable with optional default."""
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Get a required environment variable. Raises if missing."""
    value = os.environ.get(key)
    if value is None:
        raise EnvironmentError(f"Required environment variable {key!r} is not set")
    return value
