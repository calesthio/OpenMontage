"""Tests for the export_bundle publisher tool.

Covers the tool contract, registry discovery, the export bundle layout, a
schema-valid publish_log, chapter formatting, and the missing-video error path.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.publishers.export_bundle import ExportBundle
from tools.base_tool import ToolStatus, ToolTier
from tools.tool_registry import ToolRegistry
from schemas.artifacts import validate_artifact


def _make_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42fakevideo")


def test_contract_metadata():
    tool = ExportBundle()
    info = tool.get_info()
    assert info["name"] == "export_bundle"
    assert info["capability"] == "publish"
    assert info["tier"] == ToolTier.PUBLISH.value
    assert info["provider"] == "local"
    assert info["resource_profile"]["network_required"] is False
    assert tool.get_status() == ToolStatus.AVAILABLE
    assert tool.estimate_cost({}) == 0.0


def test_missing_video_errors(tmp_path):
    result = ExportBundle().execute(
        {"video_path": str(tmp_path / "nope.mp4"), "title": "X"}
    )
    assert result.success is False
    assert "not found" in (result.error or "")


def test_export_bundle_layout_and_publish_log(tmp_path):
    video = tmp_path / "projects" / "demo" / "renders" / "final.mp4"
    _make_video(video)
    subs = tmp_path / "subs.srt"
    subs.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")

    result = ExportBundle().execute(
        {
            "video_path": str(video),
            "title": "Vector Databases Explained in 60 Seconds",
            "export_dir": str(tmp_path / "out"),
            "description": "A quick explainer.",
            "tags": ["vector db", "explainer"],
            "hashtags": ["#ai", "#database"],
            "chapters": [
                {"start_seconds": 0, "title": "Intro"},
                {"start_seconds": 75, "title": "How it works"},
            ],
            "subtitles_path": str(subs),
            "thumbnail_concept": {"text_overlay": "100x FASTER"},
            "platform": "youtube",
            "visibility": "unlisted",
            "timestamp": "2026-06-29T10:30:00+00:00",
        }
    )
    assert result.success is True
    root = Path(result.data["export_path"])

    # Layout
    assert (root / "video" / "output.mp4").is_file()
    assert (root / "video" / "subtitles.srt").is_file()
    assert (root / "metadata" / "metadata.json").is_file()
    assert (root / "metadata" / "description.txt").is_file()
    assert (root / "metadata" / "tags.txt").is_file()
    assert (root / "metadata" / "chapters.txt").is_file()
    assert (root / "thumbnails" / "concept.json").is_file()

    # tags one-per-line
    assert (root / "metadata" / "tags.txt").read_text().splitlines() == ["vector db", "explainer"]
    # chapter formatting (75s -> 1:15)
    assert "1:15 - How it works" in (root / "metadata" / "chapters.txt").read_text()

    # publish_log is schema-valid and shaped right
    plog = result.data["publish_log"]
    validate_artifact("publish_log", plog)
    entry = plog["entries"][0]
    assert entry["status"] == "exported"
    assert entry["platform"] == "youtube"
    assert entry["visibility"] == "unlisted"
    assert entry["export_path"] == str(root)
    assert entry["metadata_used"]["title"].startswith("Vector Databases")


def test_chapter_time_formatting_hours(tmp_path):
    video = tmp_path / "p" / "renders" / "final.mp4"
    _make_video(video)
    result = ExportBundle().execute(
        {
            "video_path": str(video),
            "title": "Long",
            "export_dir": str(tmp_path / "out"),
            "chapters": [{"time_seconds": 3725, "label": "Deep dive"}],  # 1:02:05
        }
    )
    assert result.success is True
    txt = (Path(result.data["export_path"]) / "metadata" / "chapters.txt").read_text()
    assert "1:02:05 - Deep dive" in txt


def test_infer_project_name(tmp_path):
    video = tmp_path / "projects" / "my-cool-video" / "renders" / "final.mp4"
    _make_video(video)
    result = ExportBundle().execute(
        {"video_path": str(video), "title": "T", "export_dir": str(tmp_path / "out")}
    )
    # export still works; project name inference exercised via no-export_dir path below
    assert result.success is True


def test_missing_optional_asset_errors(tmp_path):
    video = tmp_path / "p" / "renders" / "final.mp4"
    _make_video(video)
    for key in ("subtitles_path", "thumbnail_path"):
        result = ExportBundle().execute(
            {
                "video_path": str(video),
                "title": "T",
                "export_dir": str(tmp_path / "out"),
                key: str(tmp_path / "does_not_exist.x"),
            }
        )
        assert result.success is False, key
        assert key in (result.error or "")


def test_default_export_dir_inside_project_workspace(tmp_path):
    # projects/<name>/renders/final.mp4 -> projects/<name>/exports (no export_dir given)
    video = tmp_path / "projects" / "demo" / "renders" / "final.mp4"
    _make_video(video)
    result = ExportBundle().execute({"video_path": str(video), "title": "T"})
    assert result.success is True
    assert Path(result.data["export_path"]) == (tmp_path / "projects" / "demo" / "exports").resolve()


def test_registry_discovers_export_bundle():
    reg = ToolRegistry()
    reg.discover()
    assert reg.get("export_bundle") is not None
    assert reg.get_by_capability("publish")[0].name == "export_bundle"
