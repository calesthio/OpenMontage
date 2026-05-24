"""Tests for the DAM auto-registration hook (B8 P2).

Covers the contract documented in ``tools/dam_hook.py``:

  - dam_register=False → no-op
  - missing tenant_key → no-op
  - unmapped capability → no-op
  - exception inside registry.register → swallowed, returns None
  - artifact path does not exist → no-op
  - sovereign_swarm.dam not importable → no-op

All tests reset the lazy-singleton registry between runs so import state
from the previous test never leaks. Real registration is exercised against
a tmp_path-rooted DAM via the ``SOVEREIGN_DAM_ROOT`` env var.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pytest


# ---------------------------------------------------------------------------
# Minimal ToolResult stand-in. We avoid importing OpenMontage's BaseTool so
# these tests stay fast (no .env loading, no PIL, no FFmpeg sniffing) — the
# hook only touches .data and .artifacts duck-style.
# ---------------------------------------------------------------------------

@dataclass
class FakeResult:
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    seed: Optional[int] = None
    model: Optional[str] = None


@pytest.fixture(autouse=True)
def _reset_registry_singleton():
    """Ensure each test starts with a fresh singleton."""
    from tools import dam_hook
    dam_hook.reset_registry_for_tests()
    yield
    dam_hook.reset_registry_for_tests()


@pytest.fixture
def dam_env(tmp_path, monkeypatch):
    """Point AssetRegistry at a tmp DAM root for real-registration tests."""
    monkeypatch.setenv("SOVEREIGN_DAM_ROOT", str(tmp_path / "dam"))
    return tmp_path


@pytest.fixture
def artifact(tmp_path) -> Path:
    """A small fake image file we can register."""
    p = tmp_path / "artifact.png"
    # Minimal PNG bytes — content doesn't need to render.
    p.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\nIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return p


# ---------------------------------------------------------------------------
# Negative paths — these should all return None without touching the DAM.
# ---------------------------------------------------------------------------

def test_opt_out_dam_register_false(dam_env, artifact):
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[str(artifact)])
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats", "dam_register": False},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is None


def test_missing_tenant_key_skips(dam_env, artifact):
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[str(artifact)])
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={},  # no tenant_key
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is None


def test_unmapped_capability_skips(dam_env, artifact):
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[str(artifact)])
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="garbage_unknown_capability",
        created_by_tool="test_tool",
    )
    assert asset_id is None


def test_missing_artifact_file_skips(dam_env, tmp_path):
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[str(tmp_path / "does_not_exist.png")])
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is None


def test_no_artifact_path_anywhere_skips(dam_env):
    from tools.dam_hook import maybe_register_artifact

    # No artifacts list, no data.output, no explicit artifact_path
    result = FakeResult(artifacts=[], data={})
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is None


def test_dam_not_importable_skips(monkeypatch, artifact):
    """Hook must no-op when sovereign_swarm.dam can't be imported."""
    from tools import dam_hook

    # Block sovereign_swarm.dam.registry import. Hide already-imported submodule
    # and the parent package, then guard re-imports with a meta_path finder.
    for mod in list(sys.modules):
        if mod == "sovereign_swarm" or mod.startswith("sovereign_swarm."):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    class _Blocker:
        def find_spec(self, name, path=None, target=None):
            if name == "sovereign_swarm" or name.startswith("sovereign_swarm"):
                raise ImportError("blocked for test")
            return None

    blocker = _Blocker()
    monkeypatch.setattr(sys, "meta_path", [blocker, *sys.meta_path])

    dam_hook.reset_registry_for_tests()

    result = FakeResult(artifacts=[str(artifact)])
    asset_id = dam_hook.maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is None


def test_register_exception_is_swallowed(dam_env, artifact, monkeypatch):
    """If registry.register raises, hook must log and return None — never re-raise."""
    from tools import dam_hook
    from sovereign_swarm.dam.registry import AssetRegistry

    # Warm the singleton so we can patch its .register
    reg = dam_hook._resolve_registry()
    assert isinstance(reg, AssetRegistry)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(reg, "register", boom)

    result = FakeResult(artifacts=[str(artifact)])
    asset_id = dam_hook.maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is None


# ---------------------------------------------------------------------------
# Happy path — confirm a real registration produces an asset_id and that
# the SOVEREIGN_DAM_ROOT override is honored.
# ---------------------------------------------------------------------------

def test_happy_path_registers_and_returns_asset_id(dam_env, artifact):
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[str(artifact)])
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={
            "tenant_key": "atx_mats",
            "brand_key": "atx_mats",
            "prompt": "studio photo of an atx mat",
            "dam_tags": ["test", "studio"],
        },
        capability="image_generation",
        created_by_tool="test_tool",
        width=1024,
        height=1024,
    )
    assert asset_id is not None
    # DAM root should live under the env-overridden path
    assert (dam_env / "dam").exists()


def test_artifacts_list_used_when_no_explicit_path(dam_env, artifact):
    """Hook should pick up artifact_path from ToolResult.artifacts[0]."""
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[str(artifact)])  # only artifacts, no .data['output']
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is not None


def test_data_output_path_used_when_no_artifacts(dam_env, artifact):
    """Hook should fall back to data['output'] when artifacts is empty."""
    from tools.dam_hook import maybe_register_artifact

    result = FakeResult(artifacts=[], data={"output": str(artifact)})
    asset_id = maybe_register_artifact(
        tool_result=result,
        inputs={"tenant_key": "atx_mats"},
        capability="image_generation",
        created_by_tool="test_tool",
    )
    assert asset_id is not None
