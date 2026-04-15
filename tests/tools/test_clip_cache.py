"""Tests for the shared clip bytes cache (tools/video/clip_cache.py).

These tests do not touch the network and do not require filelock —
they exercise the cache's public surface (try_link, ingest, stats)
plus the LRU eviction and manifest-persistence paths. Cache dirs are
scoped to pytest's ``tmp_path`` so nothing escapes the test session.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.video.clip_cache import (
    CacheEntry,
    ClipCache,
    _link_or_copy,
    default_cache_dir,
    default_max_total_bytes,
    get_default_cache,
    reset_default_cache,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _fake_clip(path: Path, size_bytes: int) -> Path:
    """Write a fixed-size dummy file and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use a repeating pattern so hex dumps of the file are readable
    # but the size is exactly what we asked for.
    with open(path, "wb") as f:
        f.write(b"x" * size_bytes)
    return path


def _default_metadata(clip_id: str = "test_001") -> dict:
    return {
        "source": "test_source",
        "source_id": clip_id.split("_", 1)[-1],
        "source_url": f"https://example.test/{clip_id}",
        "license": "CC0",
        "creator": "test_rig",
        "source_tags": "smoke test metadata",
    }


# ----------------------------------------------------------------------
# Config resolution
# ----------------------------------------------------------------------


def test_default_cache_dir_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENMONTAGE_CACHE_DIR", str(tmp_path / "overridden"))
    assert default_cache_dir() == tmp_path / "overridden"


def test_default_cache_dir_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_CACHE_DIR", raising=False)
    result = default_cache_dir()
    assert result == Path.home() / ".openmontage" / "clips_cache"


def test_default_max_total_bytes_respects_env_override(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_CACHE_MAX_GB", "5")
    assert default_max_total_bytes() == 5 * 1024 * 1024 * 1024


def test_default_max_total_bytes_ignores_garbage_override(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_CACHE_MAX_GB", "not-a-number")
    assert default_max_total_bytes() == 20 * 1024 * 1024 * 1024


# ----------------------------------------------------------------------
# CacheEntry dataclass round-trip
# ----------------------------------------------------------------------


def test_cache_entry_round_trip_through_dict():
    entry = CacheEntry(
        clip_id="test_001",
        file_name="test_001.mp4",
        size_bytes=42,
        added_at=1000.0,
        last_access_at=2000.0,
        source="test_source",
        source_id="001",
        source_url="https://example.test/001",
        license="CC0",
        creator="rig",
        source_tags="smoke test",
    )
    d = entry.to_dict()
    restored = CacheEntry.from_dict(d)
    assert restored == entry


def test_cache_entry_from_dict_tolerates_missing_fields():
    minimal = {"clip_id": "x", "file_name": "x.mp4"}
    entry = CacheEntry.from_dict(minimal)
    assert entry.clip_id == "x"
    assert entry.file_name == "x.mp4"
    assert entry.size_bytes == 0
    assert entry.source == ""
    assert entry.license == ""


# ----------------------------------------------------------------------
# try_link / ingest core flow
# ----------------------------------------------------------------------


def test_miss_on_empty_cache(tmp_path):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    dest = tmp_path / "project" / "clips" / "pexels_1.mp4"
    assert cache.try_link("pexels_1", dest) is False
    assert not dest.exists()
    assert cache.misses == 1
    assert cache.hits == 0


def test_ingest_then_hit_round_trip(tmp_path):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    project = tmp_path / "project1"
    src = _fake_clip(project / "clips" / "pexels_1.mp4", 5000)

    ok = cache.ingest("pexels_1", src, _default_metadata("pexels_1"))
    assert ok is True

    # A second project should get a cache hit linking the SAME blob in.
    project2 = tmp_path / "project2"
    dest2 = project2 / "clips" / "pexels_1.mp4"
    assert cache.try_link("pexels_1", dest2) is True
    assert dest2.exists()
    assert dest2.stat().st_size == 5000
    assert cache.hits == 1
    assert cache.misses == 0


def test_cache_hit_is_a_hard_link_not_a_copy_when_possible(tmp_path):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    project = tmp_path / "project1"
    src = _fake_clip(project / "clips" / "pexels_1.mp4", 2048)
    cache.ingest("pexels_1", src, _default_metadata("pexels_1"))

    project2 = tmp_path / "project2"
    dest2 = project2 / "clips" / "pexels_1.mp4"
    cache.try_link("pexels_1", dest2)

    # Same filesystem → hard link → same inode.
    cache_blob = cache.cache_dir / "pexels_1.mp4"
    assert cache_blob.exists()
    if os.name != "nt" or (
        cache_blob.stat().st_dev == dest2.stat().st_dev
    ):
        # Hard links have identical inode numbers on the same FS.
        assert cache_blob.stat().st_ino == dest2.stat().st_ino
        assert cache_blob.stat().st_nlink >= 2


def test_ingest_rejects_missing_source(tmp_path):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    missing = tmp_path / "does_not_exist.mp4"
    assert cache.ingest("pexels_missing", missing, {}) is False


def test_ingest_rejects_too_small_file(tmp_path):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    tiny = _fake_clip(tmp_path / "tiny.mp4", 100)  # < 1024-byte threshold
    assert cache.ingest("pexels_tiny", tiny, {}) is False


def test_ingest_same_clip_twice_bumps_last_access(tmp_path):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    src = _fake_clip(tmp_path / "a.mp4", 2000)
    cache.ingest("pexels_dup", src, _default_metadata("pexels_dup"))

    # Read the initial last_access_at
    entries = cache._read_manifest()
    first_access = entries["pexels_dup"].last_access_at

    # Wait a tick, then ingest again with a "fresh" source that
    # simulates a rebuild. The existing entry should have its
    # last_access bumped and the blob on disk kept intact.
    import time
    time.sleep(0.01)
    src2 = _fake_clip(tmp_path / "b.mp4", 2000)
    ok = cache.ingest("pexels_dup", src2, _default_metadata("pexels_dup"))
    assert ok is True

    entries2 = cache._read_manifest()
    assert entries2["pexels_dup"].last_access_at > first_access
    # And the cache still only has one entry (the rebuild replaced itself).
    assert len(entries2) == 1


def test_manifest_drift_falls_back_to_miss(tmp_path):
    """If the manifest has a row but the blob file is gone, report
    a miss and prune the stale entry."""
    cache = ClipCache(cache_dir=tmp_path / "cache")
    src = _fake_clip(tmp_path / "real.mp4", 2000)
    cache.ingest("pexels_drift", src, _default_metadata("pexels_drift"))

    # Manually delete the blob to simulate filesystem drift.
    blob_path = cache.cache_dir / "pexels_drift.mp4"
    assert blob_path.exists()
    blob_path.unlink()

    # try_link should miss AND prune the stale row.
    dest = tmp_path / "project" / "clips" / "pexels_drift.mp4"
    assert cache.try_link("pexels_drift", dest) is False
    entries = cache._read_manifest()
    assert "pexels_drift" not in entries


# ----------------------------------------------------------------------
# LRU eviction
# ----------------------------------------------------------------------


def test_lru_eviction_evicts_oldest_first(tmp_path):
    # Cap at 30 KB. Ingest three 10 KB clips, then a fourth — the
    # oldest should be evicted to make room.
    cache = ClipCache(
        cache_dir=tmp_path / "cache",
        max_total_bytes=30 * 1024,
    )

    import time
    for i in range(1, 4):
        src = _fake_clip(tmp_path / f"clip_{i}.mp4", 10 * 1024)
        cache.ingest(f"test_{i}", src, _default_metadata(f"test_{i}"))
        time.sleep(0.01)  # ensure distinct last_access_at

    # Bump access on clip_2 so clip_1 is the LRU victim.
    dest = tmp_path / "project" / "clip_2.mp4"
    cache.try_link("test_2", dest)

    # Add a fourth 10 KB clip — should evict clip_1 (the LRU).
    src4 = _fake_clip(tmp_path / "clip_4.mp4", 10 * 1024)
    cache.ingest("test_4", src4, _default_metadata("test_4"))

    entries = cache._read_manifest()
    assert "test_1" not in entries, "LRU victim should have been evicted"
    assert "test_2" in entries
    assert "test_3" in entries
    assert "test_4" in entries
    assert cache.evictions_count == 1
    assert cache.bytes_evicted == 10 * 1024
    # Blob file for the evicted clip should be gone.
    assert not (cache.cache_dir / "test_1.mp4").exists()


def test_eviction_multiple_victims_when_single_clip_is_large(tmp_path):
    cache = ClipCache(
        cache_dir=tmp_path / "cache",
        max_total_bytes=50 * 1024,
    )

    import time
    # Five 10 KB clips fit exactly at the cap.
    for i in range(1, 6):
        src = _fake_clip(tmp_path / f"small_{i}.mp4", 10 * 1024)
        cache.ingest(f"small_{i}", src, _default_metadata(f"small_{i}"))
        time.sleep(0.005)

    # A 30 KB incoming clip forces eviction of the 3 oldest.
    big = _fake_clip(tmp_path / "big.mp4", 30 * 1024)
    cache.ingest("big_1", big, _default_metadata("big_1"))

    entries = cache._read_manifest()
    # big_1 + small_4 + small_5 survive → 3 entries.
    assert "big_1" in entries
    assert "small_4" in entries
    assert "small_5" in entries
    assert "small_1" not in entries
    assert "small_2" not in entries
    assert "small_3" not in entries
    assert cache.evictions_count == 3


# ----------------------------------------------------------------------
# Manifest persistence across ClipCache instances
# ----------------------------------------------------------------------


def test_manifest_survives_process_boundary(tmp_path):
    """A second ClipCache instance pointing at the same dir should see
    entries written by the first instance. This simulates the common
    multi-process scenario where two corpus_builder runs share the
    cache via filesystem."""
    cache_dir = tmp_path / "cache"
    src = _fake_clip(tmp_path / "clip.mp4", 4000)

    cache_a = ClipCache(cache_dir=cache_dir)
    assert cache_a.ingest("test_persist", src, _default_metadata("test_persist")) is True

    cache_b = ClipCache(cache_dir=cache_dir)
    dest = tmp_path / "project" / "clip.mp4"
    assert cache_b.try_link("test_persist", dest) is True
    assert dest.stat().st_size == 4000


def test_manifest_tolerates_corrupt_lines(tmp_path):
    cache_dir = tmp_path / "cache"
    cache = ClipCache(cache_dir=cache_dir)

    # Write a manifest with one good row and two malformed rows.
    good = CacheEntry(
        clip_id="good_1",
        file_name="good_1.mp4",
        size_bytes=1234,
        added_at=1000.0,
        last_access_at=1000.0,
    )
    _fake_clip(cache_dir / "good_1.mp4", 1234)
    manifest_path = cache_dir / ClipCache.MANIFEST_NAME
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("this is not json\n")
        f.write(json.dumps(good.to_dict()) + "\n")
        f.write('{"missing_required_fields": true}\n')

    entries = cache._read_manifest()
    assert list(entries.keys()) == ["good_1"]


# ----------------------------------------------------------------------
# Cross-drive / link-fail fallback
# ----------------------------------------------------------------------


def test_link_or_copy_falls_back_to_copy_when_link_fails(tmp_path, monkeypatch):
    src = _fake_clip(tmp_path / "src.mp4", 3000)
    dst = tmp_path / "other" / "dst.mp4"
    dst.parent.mkdir(exist_ok=True)

    def broken_link(a, b):
        raise OSError("simulated cross-device link failure")

    monkeypatch.setattr(os, "link", broken_link)
    ok = _link_or_copy(src, dst)
    assert ok is True
    assert dst.exists()
    assert dst.read_bytes() == src.read_bytes()


def test_link_or_copy_returns_false_when_both_fail(tmp_path, monkeypatch):
    src = _fake_clip(tmp_path / "src.mp4", 3000)
    dst = tmp_path / "other" / "dst.mp4"
    dst.parent.mkdir(exist_ok=True)

    def broken_link(a, b):
        raise OSError("no link")

    def broken_copy(a, b):
        raise OSError("no copy")

    monkeypatch.setattr(os, "link", broken_link)

    import shutil
    monkeypatch.setattr(shutil, "copy2", broken_copy)

    ok = _link_or_copy(src, dst)
    assert ok is False
    assert not dst.exists()


def test_try_link_falls_back_to_copy_and_still_bumps_access(tmp_path, monkeypatch):
    cache = ClipCache(cache_dir=tmp_path / "cache")
    src = _fake_clip(tmp_path / "src.mp4", 3000)
    cache.ingest("pexels_x", src, _default_metadata("pexels_x"))

    def broken_link(a, b):
        raise OSError("cross-drive")

    monkeypatch.setattr(os, "link", broken_link)

    dest = tmp_path / "project" / "clips" / "pexels_x.mp4"
    ok = cache.try_link("pexels_x", dest)
    assert ok is True
    assert dest.exists()
    assert cache.hits == 1


# ----------------------------------------------------------------------
# Stats
# ----------------------------------------------------------------------


def test_stats_reports_cache_state_and_session_counters(tmp_path):
    cache = ClipCache(
        cache_dir=tmp_path / "cache",
        max_total_bytes=10 * 1024 * 1024,
    )
    _fake_clip(tmp_path / "a.mp4", 2000)
    cache.ingest("test_stats_a", tmp_path / "a.mp4", _default_metadata("test_stats_a"))

    dest = tmp_path / "project" / "a.mp4"
    cache.try_link("test_stats_a", dest)
    cache.try_link("missing_clip", tmp_path / "project" / "missing.mp4")

    s = cache.stats()
    assert s["entry_count"] == 1
    assert s["total_bytes"] == 2000
    assert s["hits_this_session"] == 1
    assert s["misses_this_session"] == 1
    assert s["evictions_this_session"] == 0
    assert s["max_total_bytes"] == 10 * 1024 * 1024
    assert "cache_dir" in s
    assert s["filelock_backend"] in ("filelock", "o_excl_fallback")


# ----------------------------------------------------------------------
# get_default_cache singleton
# ----------------------------------------------------------------------


def test_get_default_cache_honors_env_var(monkeypatch, tmp_path):
    reset_default_cache()
    monkeypatch.setenv("OPENMONTAGE_CACHE_DIR", str(tmp_path / "envcache"))
    cache = get_default_cache()
    assert Path(cache.cache_dir) == tmp_path / "envcache"
    reset_default_cache()


def test_get_default_cache_returns_same_instance(monkeypatch, tmp_path):
    reset_default_cache()
    monkeypatch.setenv("OPENMONTAGE_CACHE_DIR", str(tmp_path / "singleton"))
    a = get_default_cache()
    b = get_default_cache()
    assert a is b
    reset_default_cache()
