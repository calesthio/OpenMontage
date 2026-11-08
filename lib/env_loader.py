"""Environment variable loader for OpenMontage.

Loads .env file and provides typed access to environment configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values


def load_env(project_root: Optional[Path] = None) -> None:
    """Load .env file from project root."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        for key, value in dotenv_values(env_path).items():
            if key and value is not None and not os.environ.get(key, "").strip():
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
