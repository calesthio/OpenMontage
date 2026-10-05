"""Tests for the xhs_publisher tool.

Covers contract metadata, registry discovery, dry-run mode, and missing-video
error path.  Real-device end-to-end tests are excluded from CI.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.publishers.xhs_publisher import XHSPublisher
from tools.base_tool import ToolStatus, ToolTier
from tools.tool_registry import ToolRegistry
from schemas.artifacts import validate_artifact


def test_contract_metadata():
    tool = XHSPublisher()
    info = tool.get_info()
    assert info["name"] == "xhs_publisher"
    assert info["capability"] == "publish"
    assert info["tier"] == ToolTier.PUBLISH.value
    assert info["provider"] == "xiaohongshu"
    assert tool.get_status() in (ToolStatus.AVAILABLE, ToolStatus.UNAVAILABLE)


def test_missing_video_errors():
    result = XHSPublisher().execute({})
    assert not result.success
    assert "video_path" in (result.error or "")


def test_dry_run_returns_publish_log():
    tool = XHSPublisher()
    result = tool.execute({
        "video_path": "/fake/path.mp4",
        "title": "Dry Run Test",
        "content": "Dry run content",
        "hashtags": ["test", "dryrun"],
        "dry_run": True,
    })
    assert result.success
    data = result.data or {}
    log = data.get("publish_log", {})
    entries = log.get("entries", [])
    assert len(entries) == 1
    entry = entries[0]
    assert entry["platform"] == "xiaohongshu"
    assert entry["status"] == "draft"
    assert entry["metadata_used"]["title"] == "Dry Run Test"
    assert "dryrun" in entry["metadata_used"]["hashtags"]


def test_dry_run_publish_log_schema():
    """Dry-run publish_log must validate against the publish_log schema."""
    result = XHSPublisher().execute({
        "video_path": "/fake/path.mp4",
        "title": "Schema Test",
        "content": "Checking schema compliance",
        "dry_run": True,
    })
    data = result.data or {}
    log = data.get("publish_log", {})
    errors = validate_artifact("publish_log", log)
    assert not errors, f"Schema errors: {errors}"


def test_registry_discovers_xhs_publisher():
    reg = ToolRegistry()
    reg.discover()
    assert reg.get("xhs_publisher") is not None
