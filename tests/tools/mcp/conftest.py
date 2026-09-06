import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from tools.mcp.mcp_config import McpServerConfig

FAKE_SERVER = Path(__file__).resolve().parent.parent.parent / "fixtures" / "mcp" / "fake_server.py"


@pytest.fixture(autouse=True)
def isolated_mcp_cache(tmp_path, monkeypatch):
    """Point the list_tools disk cache at a per-test temp dir.

    Keeps tests hermetic: the real ~/.cache/openmontage is never written to or
    read, and a changed fake server can never be masked by a stale cached tool
    list keyed on an unchanged config signature.
    """
    from tools.mcp import mcp_registry
    monkeypatch.setattr(mcp_registry, "_CACHE_ROOT", tmp_path / "mcp-cache")


@pytest.fixture
def fake_server_params() -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=[str(FAKE_SERVER)])


@pytest.fixture
def fake_server_config() -> McpServerConfig:
    return McpServerConfig(
        slug="fake",
        transport="stdio",
        command=sys.executable,
        args=[str(FAKE_SERVER)],
        timeout_seconds=20.0,
    )
