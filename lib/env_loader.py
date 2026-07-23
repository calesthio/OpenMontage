"""Environment variable loader for OpenMontage.

Loads .env file and provides typed access to environment configuration.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

# Try to import python-dotenv, but fall back gracefully
try:
    from dotenv import load_dotenv as _load_dotenv_lib
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


def load_env(project_root: Optional[Path] = None, use_dotenv: bool = False) -> None:
    """Load .env file from project root.
    
    Args:
        project_root: Project root directory (defaults to parent of this file)
        use_dotenv: If True, use python-dotenv if available; otherwise use manual parsing
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    
    if not env_path.exists():
        return
    
    if use_dotenv and HAS_DOTENV:
        _load_dotenv_lib(env_path)
    else:
        _load_env_manual(env_path)


def _load_env_manual(env_path: Path) -> None:
    """Manual .env parsing (no dependencies) - matches original behavior."""
    with open(env_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            
            # Quoted value: take the content inside the quotes verbatim
            if value[:1] in ("'", '"'):
                quote = value[0]
                end = value.find(quote, 1)
                value = value[1:end] if end != -1 else value[1:]
            else:
                # Strip an inline comment ('#' at line start or after
                # whitespace) so "VAR=   # note" yields "" not "# note"
                match = re.search(r"(^|\s)#", value)
                if match:
                    value = value[: match.start()]
                value = value.strip()
            
            if key and key not in os.environ:
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
