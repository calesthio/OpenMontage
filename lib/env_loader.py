"""Environment variable loader for OpenMontage.

Loads .env file and provides typed access to environment configuration.

NOTE — bypassed by most production entry points: server/app/runner/stage_runner.py
and spike_agent_runner.py call python-dotenv's ``load_dotenv`` directly instead
of ``load_env`` here, and tools/base_tool.py / tools/tool_registry.py each
hand-roll their own private ``.env`` parser rather than using this module or
python-dotenv. Only the tests/qa/* scripts currently use ``load_env``. See
lib-config review finding ``libconfig-env-loader-unused-triplicated`` — those
call sites live outside lib/ and are recommended follow-up, not fixed here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class MissingEnvironmentVariable(RuntimeError):
    """Raised by require_env when a required environment variable is not set.

    A dedicated exception rather than EnvironmentError (an OSError alias),
    so this can't be silently swallowed by a broad ``except OSError`` clause
    elsewhere in the codebase.
    """


def load_env(project_root: Optional[Path] = None) -> None:
    """Load .env file from project root."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable with optional default."""
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    """Get a required environment variable. Raises if missing."""
    value = os.environ.get(key)
    if value is None:
        raise MissingEnvironmentVariable(f"Required environment variable {key!r} is not set")
    return value
