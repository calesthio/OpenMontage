"""Tests for the content-addressed asset cache (lib/asset_cache.py).

These do not touch the network and do not require filelock. They exercise the
cache's public surface (try_restore, store, stats), content-vs-path keying,
LRU eviction, manifest persistence, and the enable/config env vars. Cache dirs
are scoped to pytest's ``tmp_path`` so nothing escapes the test session.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.asset_cache import (  # noqa: E402
    AssetCache,
    AssetCacheEntry,
    _copy_file,
    asset_cache_enabled,
    default_asset_cache_dir,
    default_max_total_bytes,
    get_default_asset_cache,
    reset_default_asset_cache,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _fake_asset(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(payload)
    return path


# ----------------------------------------------------------------------
# Enable / config resolution
# ----------------------------------------------------------------------


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_ASSET_CACHE", raising=False)
    assert asset_cache_enabled() is False


def test_enabled_by_truthy_values(monkeypatch):
    for val in ("1", "true", "TRUE", "yes", "On"):
        monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", val)
        assert asset_cache_enabled() is True
    for val in ("0", "false", "no", "", "off"):
        monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", val)
        assert asset_cache_enabled() is False


def test_default_cache_dir_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "overridden"))
    assert default_asset_cache_dir() == tmp_path / "overridden"


def test_default_cache_dir_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_ASSET_CACHE_DIR", raising=False)
    assert default_asset_cache_dir() == Path.home() / ".openmontage" / "asset_cache"


def test_default_max_total_bytes_respects_and_guards_env(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_MAX_GB", "5")
    assert default_max_total_bytes() == 5 * 1024 * 1024 * 1024
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_MAX_GB", "not-a-number")
    assert default_max_total_bytes() == 20 * 1024 * 1024 * 1024


# ----------------------------------------------------------------------
# Entry round-trip
# ----------------------------------------------------------------------


def test_entry_round_trip_through_dict():
    entry = AssetCacheEntry(
        key="abc123",
        file_name="abc123.png",
        size_bytes=42,
        added_at=1000.0,
        last_access_at=2000.0,
        tool_name="flux_image",
        tool_version="0.1.0",
        model="fal-ai/flux-pro/v1.1",
        seed=7,
        cost_usd=0.05,
        data_json='{"provider": "flux"}',
    )
    assert AssetCacheEntry.from_dict(entry.to_dict()) == entry


def test_entry_from_dict_tolerates_missing_and_bad_fields():
    entry = AssetCacheEntry.from_dict(
        {"key": "x", "file_name": "x.png", "seed": "not-an-int"}
    )
    assert entry.key == "x"
    assert entry.size_bytes == 0
    assert entry.seed is None
    assert entry.cost_usd == 0.0


# ----------------------------------------------------------------------
# store / try_restore core flow
# ----------------------------------------------------------------------


def test_miss_on_empty_cache(tmp_path):
    cache = AssetCache(cache_dir=tmp_path / "cache")
    dest = tmp_path / "project" / "out.png"
    assert cache.try_restore("nope", dest) is None
    assert not dest.exists()
    assert cache.misses == 1 and cache.hits == 0


def test_store_then_restore_round_trip(tmp_path):
    cache = AssetCache(cache_dir=tmp_path / "cache")
    src = _fake_asset(tmp_path / "gen" / "img.png", b"PIXELS-red-fox")
    ok = cache.store(
        "k1", src, tool_name="flux_image", tool_version="0.1.0",
        model="flux-pro", seed=7, cost_usd=0.05, data={"output": str(src), "provider": "flux"},
    )
    assert ok is True

    dest = tmp_path / "project" / "scene1.png"
    meta = cache.try_restore("k1", dest)
    assert meta is not None
    assert dest.exists()
    assert dest.read_bytes() == b"PIXELS-red-fox"
    assert meta["cost_usd"] == 0.05
    assert meta["seed"] == 7
    assert meta["model"] == "flux-pro"
    assert meta["data"]["provider"] == "flux"
    assert cache.hits == 1
    assert cache.cost_saved_usd == 0.05


def test_same_key_restores_to_any_output_path(tmp_path):
    """Content-addressed: the same key materializes wherever asked."""
    cache = AssetCache(cache_dir=tmp_path / "cache")
    src = _fake_asset(tmp_path / "gen" / "img.png", b"BYTES")
    cache.store("k1", src, cost_usd=0.10)

    d1 = tmp_path / "a" / "x.png"
    d2 = tmp_path / "b" / "y.png"
    assert cache.try_restore("k1", d1) is not None
    assert cache.try_restore("k1", d2) is not None
    assert d1.read_bytes() == d2.read_bytes() == b"BYTES"
    assert cache.hits == 2
    assert round(cache.cost_saved_usd, 2) == 0.20


def test_restored_blob_is_immutable_when_destination_overwritten(tmp_path):
    # Overwriting a restored file in place (a normal regeneration) must not
    # mutate the stored blob. Hard links would share an inode and corrupt the
    # cache; the store keeps immutable copies instead.
    cache = AssetCache(cache_dir=tmp_path / "cache")
    src = _fake_asset(tmp_path / "gen" / "img.bin", b"ORIGINAL")
    cache.store("k1", src)

    dest = tmp_path / "project" / "scene.bin"
    assert cache.try_restore("k1", dest) is not None
    assert dest.read_bytes() == b"ORIGINAL"

    dest.write_bytes(b"REWRITTEN-IN-PLACE-DIFFERENT-BYTES")

    blob = cache.cache_dir / "k1.bin"
    assert blob.read_bytes() == b"ORIGINAL"
    dest2 = tmp_path / "project2" / "scene.bin"
    cache.try_restore("k1", dest2)
    assert dest2.read_bytes() == b"ORIGINAL"


def test_store_source_rewrite_does_not_mutate_blob(tmp_path):
    # The other direction: rewriting the tool's own output after it was stored
    # must not reach back into the cache blob.
    cache = AssetCache(cache_dir=tmp_path / "cache")
    src = _fake_asset(tmp_path / "gen" / "img.bin", b"ORIGINAL")
    cache.store("k1", src)
    src.write_bytes(b"REGENERATED")
    assert (cache.cache_dir / "k1.bin").read_bytes() == b"ORIGINAL"


def test_store_rejects_missing_source(tmp_path):
    cache = AssetCache(cache_dir=tmp_path / "cache")
    assert cache.store("k", tmp_path / "nope.png") is False


def test_manifest_drift_prunes_and_misses(tmp_path):
    cache = AssetCache(cache_dir=tmp_path / "cache")
    src = _fake_asset(tmp_path / "gen" / "img.png", b"BYTES")
    cache.store("k1", src)
    (cache.cache_dir / "k1.png").unlink()  # simulate filesystem drift

    assert cache.try_restore("k1", tmp_path / "out.png") is None
    assert "k1" not in cache._read_manifest()


def test_store_same_key_twice_keeps_single_entry(tmp_path):
    cache = AssetCache(cache_dir=tmp_path / "cache")
    src = _fake_asset(tmp_path / "gen" / "img.png", b"BYTES")
    assert cache.store("k1", src) is True
    assert cache.store("k1", src) is True
    assert len(cache._read_manifest()) == 1


# ----------------------------------------------------------------------
# LRU eviction
# ----------------------------------------------------------------------


def test_lru_eviction_evicts_oldest_first(tmp_path):
    import time
    cache = AssetCache(cache_dir=tmp_path / "cache", max_total_bytes=30 * 1024)
    for i in range(1, 4):
        src = _fake_asset(tmp_path / f"a{i}.png", b"z" * (10 * 1024))
        cache.store(f"k{i}", src)
        time.sleep(0.01)
    # Bump k2 so k1 is the LRU victim.
    cache.try_restore("k2", tmp_path / "proj" / "k2.png")

    src4 = _fake_asset(tmp_path / "a4.png", b"z" * (10 * 1024))
    cache.store("k4", src4)

    entries = cache._read_manifest()
    assert "k1" not in entries
    assert {"k2", "k3", "k4"} <= set(entries)
    assert cache.evictions_count == 1
    assert not (cache.cache_dir / "k1.png").exists()


# ----------------------------------------------------------------------
# Persistence + resilience
# ----------------------------------------------------------------------


def test_manifest_survives_process_boundary(tmp_path):
    cache_dir = tmp_path / "cache"
    src = _fake_asset(tmp_path / "img.png", b"BYTES")
    assert AssetCache(cache_dir=cache_dir).store("k1", src) is True

    dest = tmp_path / "project" / "img.png"
    assert AssetCache(cache_dir=cache_dir).try_restore("k1", dest) is not None
    assert dest.read_bytes() == b"BYTES"


def test_manifest_tolerates_corrupt_lines(tmp_path):
    cache_dir = tmp_path / "cache"
    cache = AssetCache(cache_dir=cache_dir)
    good = AssetCacheEntry(
        key="good", file_name="good.png", size_bytes=5,
        added_at=1.0, last_access_at=1.0,
    )
    _fake_asset(cache_dir / "good.png", b"BYTES")
    with open(cache_dir / AssetCache.MANIFEST_NAME, "w", encoding="utf-8") as f:
        f.write("not json\n")
        f.write(json.dumps(good.to_dict()) + "\n")
        f.write('{"missing": true}\n')
    assert list(cache._read_manifest().keys()) == ["good"]


def test_copy_file_makes_independent_copy(tmp_path):
    src = _fake_asset(tmp_path / "src.bin", b"BYTES")
    dst = tmp_path / "other" / "dst.bin"
    dst.parent.mkdir(exist_ok=True)
    assert _copy_file(src, dst) is True
    assert dst.read_bytes() == b"BYTES"
    # Independent: overwriting the copy must not touch the source (no shared inode).
    dst.write_bytes(b"CHANGED")
    assert src.read_bytes() == b"BYTES"


# ----------------------------------------------------------------------
# stats + singleton
# ----------------------------------------------------------------------


def test_stats_reports_state_and_counters(tmp_path):
    cache = AssetCache(cache_dir=tmp_path / "cache", max_total_bytes=10 * 1024 * 1024)
    src = _fake_asset(tmp_path / "img.png", b"z" * 2000)
    cache.store("k1", src, cost_usd=0.30)
    cache.try_restore("k1", tmp_path / "proj" / "img.png")
    cache.try_restore("missing", tmp_path / "proj" / "missing.png")

    s = cache.stats()
    assert s["entry_count"] == 1
    assert s["total_bytes"] == 2000
    assert s["hits_this_session"] == 1
    assert s["misses_this_session"] == 1
    assert s["cost_saved_usd_this_session"] == 0.30
    assert s["filelock_backend"] in ("filelock", "o_excl_fallback")


def test_get_default_asset_cache_honors_env_and_is_singleton(monkeypatch, tmp_path):
    reset_default_asset_cache()
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "envcache"))
    a = get_default_asset_cache()
    b = get_default_asset_cache()
    assert a is b
    assert Path(a.cache_dir) == tmp_path / "envcache"
    reset_default_asset_cache()
