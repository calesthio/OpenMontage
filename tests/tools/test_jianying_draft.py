"""Unit tests for the jianying_draft tool (issue #621)."""

import json
import os
from pathlib import Path
import pytest

from tools.video.jianying_draft import (
    JianYingDraftExport,
    get_default_jianying_drafts_path,
    get_default_jianying_exe,
    register_draft_in_root_meta,
    build_jianying_draft,
)
from tools.base_tool import ToolTier, ToolStability, ToolResult


def test_tool_metadata():
    tool = JianYingDraftExport()
    assert tool.name == "jianying_draft"
    assert tool.capability == "video_post"
    assert tool.tier == ToolTier.CORE
    assert tool.stability == ToolStability.PRODUCTION
    assert "draft_name" in tool.input_schema["properties"]
    assert "clips" in tool.input_schema["properties"]
    assert "voiceover" in tool.input_schema["properties"]
    assert "bgm" in tool.input_schema["properties"]
    assert "srt_path" in tool.input_schema["properties"]


def test_get_default_jianying_drafts_path_from_env(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_drafts"
    custom_dir.mkdir()
    monkeypatch.setenv("JIANYING_DRAFTS_PATH", str(custom_dir))
    assert get_default_jianying_drafts_path() == custom_dir.resolve()


def test_get_default_jianying_exe_from_env(tmp_path, monkeypatch):
    custom_exe = tmp_path / "JianyingPro.exe"
    custom_exe.write_text("dummy exe")
    monkeypatch.setenv("JIANYING_EXE", str(custom_exe))
    assert get_default_jianying_exe() == custom_exe.resolve()


def test_register_draft_in_root_meta(tmp_path):
    draft_dir = tmp_path / "drafts" / "Project_A"
    draft_dir.mkdir(parents=True)
    root_meta = tmp_path / "drafts" / "root_meta_info.json"

    ok = register_draft_in_root_meta(
        draft_dir=draft_dir,
        draft_id="TEST-ID-1234",
        draft_name="Project_A",
        duration_us=5000000,
        root_meta_file=root_meta,
    )

    assert ok is True
    assert root_meta.exists()

    with open(root_meta, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["draft_ids"] == 1
    assert len(meta["all_draft_store"]) == 1
    entry = meta["all_draft_store"][0]
    assert entry["draft_id"] == "TEST-ID-1234"
    assert entry["draft_name"] == "Project_A"
    assert entry["tm_duration"] == 5000000

    # Register a second draft
    draft_dir_b = tmp_path / "drafts" / "Project_B"
    draft_dir_b.mkdir(parents=True)
    ok_b = register_draft_in_root_meta(
        draft_dir=draft_dir_b,
        draft_id="TEST-ID-5678",
        draft_name="Project_B",
        duration_us=8000000,
        root_meta_file=root_meta,
    )
    assert ok_b is True

    with open(root_meta, "r", encoding="utf-8") as f:
        meta2 = json.load(f)

    assert meta2["draft_ids"] == 2
    assert meta2["all_draft_store"][0]["draft_id"] == "TEST-ID-5678"


def test_build_jianying_draft_and_execute(tmp_path, monkeypatch):
    draft_root = tmp_path / "jianying_projects"
    draft_root.mkdir()
    monkeypatch.setenv("JIANYING_DRAFTS_PATH", str(draft_root))

    # Create dummy image clip
    img_path = tmp_path / "scene1.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    tool = JianYingDraftExport()
    result = tool.execute(
        {
            "draft_name": "Test_Draft_Unit",
            "clips": [{"path": str(img_path), "duration_sec": 2.5}],
            "width": 1920,
            "height": 1080,
            "fps": 30,
        }
    )

    assert result.success is True
    assert result.data["draft_name"] == "Test_Draft_Unit"
    assert result.data["clips_count"] == 1
    assert result.data["total_duration_sec"] == 2.5
    assert (draft_root / "Test_Draft_Unit").exists()
    assert (draft_root / "root_meta_info.json").exists()


def test_execute_with_manifest_file(tmp_path, monkeypatch):
    draft_root = tmp_path / "jianying_projects"
    draft_root.mkdir()
    monkeypatch.setenv("JIANYING_DRAFTS_PATH", str(draft_root))

    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "draft_name": "Manifest_Project",
                "clips": [],
                "width": 1080,
                "height": 1920,
            }
        ),
        encoding="utf-8",
    )

    tool = JianYingDraftExport()
    result = tool.execute({"manifest_path": str(manifest_file)})

    assert result.success is True
    assert result.data["draft_name"] == "Manifest_Project"
    assert (draft_root / "Manifest_Project").exists()
