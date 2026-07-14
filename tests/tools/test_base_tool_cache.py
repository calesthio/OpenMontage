"""Integration tests for content-addressed caching in BaseTool.execute().

A fake tool counts how many times its real ``execute()`` body runs. With the
cache enabled, a repeat of a reproducible call must be served from disk without
running the body again, at zero cost, with byte-identical output, while
stochastic tools, seed-unpinned calls, publishers, and failures are never
cached. The cache is off unless OPENMONTAGE_ASSET_CACHE is set, so the whole
existing suite is unaffected; these tests opt in explicitly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import (  # noqa: E402
    BaseTool,
    Determinism,
    ToolResult,
    ToolRuntime,
    ToolTier,
)
from lib.asset_cache import (  # noqa: E402
    get_default_asset_cache,
    reset_default_asset_cache,
)


# ----------------------------------------------------------------------
# Fake tools: one base implementation; subclasses vary only class attrs.
# The wrapper reads determinism/tier/name/version off ``self`` at call time,
# so subclasses need no execute() of their own.
# ----------------------------------------------------------------------


class _GenBase(BaseTool):
    name = "gen_base"
    version = "1.0.0"
    tier = ToolTier.GENERATE
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    idempotency_key_fields = ["prompt"]

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def estimate_cost(self, inputs: dict) -> float:
        return 0.05

    def execute(self, inputs: dict) -> ToolResult:
        self.calls += 1
        out = Path(inputs["output_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            f"{self.name}|v{self.version}|{inputs.get('prompt')}"
            f"|seed={inputs.get('seed')}|call={self.calls}"
        )
        out.write_bytes(payload.encode())
        return ToolResult(
            success=True,
            data={"output": str(out), "prompt": inputs.get("prompt")},
            artifacts=[str(out)],
            cost_usd=self.estimate_cost(inputs),
            seed=inputs.get("seed"),
            model="fake-model-1",
        )


class _DetGen(_GenBase):
    name = "det_gen"


class _DetGenV2(_GenBase):
    name = "det_gen"          # same name, bumped version -> different key
    version = "2.0.0"


class _OtherGen(_GenBase):
    name = "other_gen"


class _SeededGen(_GenBase):
    name = "seeded_gen"
    determinism = Determinism.SEEDED
    idempotency_key_fields = ["prompt", "seed"]


class _StochGen(_GenBase):
    name = "stoch_gen"
    determinism = Determinism.STOCHASTIC


class _PubTool(_GenBase):
    name = "pub_tool"
    tier = ToolTier.PUBLISH


class _MultiArtGen(_GenBase):
    name = "multi_art_gen"

    def execute(self, inputs: dict) -> ToolResult:
        self.calls += 1
        out = Path(inputs["output_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"primary")
        side = out.with_suffix(".meta.json")
        side.write_bytes(b"{}")
        return ToolResult(
            success=True,
            data={"output": str(out)},
            artifacts=[str(out), str(side)],
            cost_usd=0.05,
        )


class _FailingGen(_GenBase):
    name = "failing_gen"

    def execute(self, inputs: dict) -> ToolResult:
        self.calls += 1
        return ToolResult(success=False, error="boom")


class _NoPathGen(_GenBase):
    name = "nopath_gen"
    out_dir = "."  # set by the test

    def execute(self, inputs: dict) -> ToolResult:
        self.calls += 1
        out = Path(self.out_dir) / f"gen_{self.calls}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"data")
        return ToolResult(
            success=True, data={"output": str(out)},
            artifacts=[str(out)], cost_usd=0.05,
        )


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def cache_on(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "asset_cache"))
    reset_default_asset_cache()
    yield tmp_path
    reset_default_asset_cache()


# ----------------------------------------------------------------------
# The core win: reproducible repeat is free and identical
# ----------------------------------------------------------------------


def test_identical_call_is_served_from_cache(cache_on):
    tool = _DetGen()
    inp = {"prompt": "a red fox", "output_path": str(cache_on / "out1.png")}
    r1 = tool.execute(inp)
    assert r1.success and r1.from_cache is False and tool.calls == 1
    first_bytes = Path(inp["output_path"]).read_bytes()

    # Same content, different destination -> content-addressed hit.
    inp2 = {"prompt": "a red fox", "output_path": str(cache_on / "out2.png")}
    r2 = tool.execute(inp2)
    assert r2.from_cache is True
    assert r2.cost_usd == 0.0
    assert tool.calls == 1, "cache hit must not re-run the tool body"
    assert Path(inp2["output_path"]).read_bytes() == first_bytes
    assert r2.data["output"] == inp2["output_path"]  # output ref repointed
    assert r2.data.get("cached") is True

    stats = get_default_asset_cache().stats()
    assert stats["hits_this_session"] == 1
    assert stats["cost_saved_usd_this_session"] == 0.05


def test_disabled_by_default_does_not_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_ASSET_CACHE", raising=False)
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "asset_cache"))
    reset_default_asset_cache()
    tool = _DetGen()
    tool.execute({"prompt": "x", "output_path": str(tmp_path / "a.png")})
    tool.execute({"prompt": "x", "output_path": str(tmp_path / "b.png")})
    assert tool.calls == 2
    reset_default_asset_cache()


# ----------------------------------------------------------------------
# Determinism gating
# ----------------------------------------------------------------------


def test_seeded_with_pinned_seed_is_cached(cache_on):
    tool = _SeededGen()
    a = {"prompt": "p", "seed": 42, "output_path": str(cache_on / "a.png")}
    b = {"prompt": "p", "seed": 42, "output_path": str(cache_on / "b.png")}
    tool.execute(a)
    r = tool.execute(b)
    assert r.from_cache is True
    assert tool.calls == 1


def test_seeded_without_seed_is_not_cached(cache_on):
    tool = _SeededGen()
    tool.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    tool.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert tool.calls == 2, "an unpinned seed is effectively stochastic"


def test_seeded_different_seed_regenerates(cache_on):
    tool = _SeededGen()
    tool.execute({"prompt": "p", "seed": 1, "output_path": str(cache_on / "a.png")})
    r = tool.execute({"prompt": "p", "seed": 2, "output_path": str(cache_on / "b.png")})
    assert r.from_cache is False
    assert tool.calls == 2


def test_stochastic_is_never_cached(cache_on):
    tool = _StochGen()
    tool.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    tool.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert tool.calls == 2


def test_publisher_is_never_cached(cache_on):
    tool = _PubTool()
    tool.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    tool.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert tool.calls == 2, "publishers have side effects beyond the file"


# ----------------------------------------------------------------------
# Key correctness: identity + version isolation
# ----------------------------------------------------------------------


def test_version_bump_invalidates(cache_on):
    v1 = _DetGen()
    v1.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    v2 = _DetGenV2()
    r = v2.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert r.from_cache is False
    assert v2.calls == 1, "a version bump must not serve the old blob"


def test_different_tools_do_not_collide(cache_on):
    a = _DetGen()
    b = _OtherGen()
    a.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    r = b.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert r.from_cache is False
    assert b.calls == 1


# ----------------------------------------------------------------------
# What must NOT be stored
# ----------------------------------------------------------------------


def test_multi_artifact_is_not_stored(cache_on):
    tool = _MultiArtGen()
    tool.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    tool.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert tool.calls == 2, "multi-artifact tools are deferred, not cached"


def test_failure_is_not_stored(cache_on):
    tool = _FailingGen()
    tool.execute({"prompt": "p", "output_path": str(cache_on / "a.png")})
    tool.execute({"prompt": "p", "output_path": str(cache_on / "b.png")})
    assert tool.calls == 2


def test_no_output_path_is_not_cached(cache_on):
    tool = _NoPathGen()
    tool.out_dir = str(cache_on)
    # Without an output_path there is nowhere to materialize a hit.
    tool.execute({"prompt": "p"})
    tool.execute({"prompt": "p"})
    assert tool.calls == 2
