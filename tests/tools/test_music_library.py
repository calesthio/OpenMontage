"""Tests for the music_library tool.

Covers the tool contract, registry discovery, status behavior (folder
present/absent, with/without tracks), and the track listing returned by
execute().
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.music_library import MusicLibrary
from tools.base_tool import ToolStatus, ToolTier
from tools.tool_registry import ToolRegistry


def _make_track(path: Path, data: bytes = b"\x00\x01\x02\x03") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_contract_metadata():
    tool = MusicLibrary()
    info = tool.get_info()
    assert info["name"] == "music_library"
    assert info["capability"] == "music_library"
    assert info["provider"] == "local"
    assert info["runtime"] == "local"
    assert info["tier"] == ToolTier.SOURCE.value
    assert info["resource_profile"]["network_required"] is False
    # Read-only tool: no side effects, no cost.
    assert tool.side_effects == []
    assert tool.estimate_cost({}) == 0.0


def test_status_unavailable_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(tmp_path / "does_not_exist"))
    assert MusicLibrary().get_status() == ToolStatus.UNAVAILABLE


def test_status_unavailable_when_dir_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(tmp_path))
    assert MusicLibrary().get_status() == ToolStatus.UNAVAILABLE


def test_status_available_with_tracks(tmp_path, monkeypatch):
    _make_track(tmp_path / "calm_dawn.mp3")
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(tmp_path))
    assert MusicLibrary().get_status() == ToolStatus.AVAILABLE


def test_status_ignores_non_audio_files(tmp_path, monkeypatch):
    _make_track(tmp_path / "notes.txt")
    _make_track(tmp_path / "cover.jpg")
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(tmp_path))
    assert MusicLibrary().get_status() == ToolStatus.UNAVAILABLE


def test_execute_lists_tracks_sorted(tmp_path, monkeypatch):
    _make_track(tmp_path / "zebra.wav")
    _make_track(tmp_path / "alpha.mp3")
    _make_track(tmp_path / "nested" / "bravo.flac")
    _make_track(tmp_path / "ignore.txt")
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(tmp_path))

    result = MusicLibrary().execute({})
    assert result.success is True
    assert result.data["track_count"] == 3
    names = [t["name"] for t in result.data["tracks"]]
    assert names == ["alpha.mp3", "bravo.flac", "zebra.wav"]
    assert all(t["size_bytes"] > 0 for t in result.data["tracks"])
    assert result.data["exists"] is True


def test_execute_input_dir_overrides_env(tmp_path, monkeypatch):
    env_dir = tmp_path / "env"
    arg_dir = tmp_path / "arg"
    _make_track(env_dir / "env_track.mp3")
    _make_track(arg_dir / "arg_track.mp3")
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(env_dir))

    result = MusicLibrary().execute({"library_dir": str(arg_dir)})
    names = [t["name"] for t in result.data["tracks"]]
    assert names == ["arg_track.mp3"]


def test_execute_empty_library(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSIC_LIBRARY_DIR", str(tmp_path / "missing"))
    result = MusicLibrary().execute({})
    assert result.success is True
    assert result.data["track_count"] == 0
    assert result.data["tracks"] == []
    assert result.data["exists"] is False
    assert result.data["total_duration_seconds"] is None


def test_registry_discovers_music_library():
    reg = ToolRegistry()
    reg.discover()
    assert reg.get("music_library") is not None
    # Top-level capability family lookup.
    assert reg.get_by_capability("music_library")[0].name == "music_library"
    # Granular capability declared in capabilities[].
    assert reg.find_by_capability("list_user_music_tracks")[0].name == "music_library"
