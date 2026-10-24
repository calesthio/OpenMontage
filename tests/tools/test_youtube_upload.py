"""Tests for the youtube_upload publisher: contract, validation, the never-public rule,
publishAt handling and the dry-run / confirm gates. No network is touched."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import ToolTier
from tools.publishers.youtube_upload import (
    UploadInputError,
    YouTubeUpload,
    build_request,
    main,
    parse_publish_at,
)
from tools.tool_registry import ToolRegistry

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def _meta(tmp_path, **over):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42fakevideo")
    thumb = tmp_path / "thumbnail.png"
    thumb.write_bytes(b"\x89PNG\r\n\x1a\n")
    meta = {"title": "TILES HOP EXE | A EXE 🆚 B EXE", "description": "desc", "tags": ["tiles hop", "exe"],
            "categoryId": "20", "video": str(video), "thumbnail": str(thumb), **over}
    p = tmp_path / "metadata.json"
    p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return p


def test_contract_metadata():
    info = YouTubeUpload().get_info()
    assert info["name"] == "youtube_upload"
    assert info["capability"] == "publish"
    assert info["tier"] == ToolTier.PUBLISH.value
    assert info["resource_profile"]["network_required"] is True
    assert YouTubeUpload().estimate_cost({}) == 0.0


def test_request_from_metadata_defaults_private(tmp_path):
    req = build_request({"metadata_path": str(_meta(tmp_path))}, NOW)
    assert req["body"]["status"]["privacyStatus"] == "private"
    assert "publishAt" not in req["body"]["status"]
    assert req["body"]["snippet"]["title"].startswith("TILES HOP")
    assert req["thumbnail"].endswith("thumbnail.png")


def test_public_is_refused(tmp_path):
    with pytest.raises(UploadInputError):
        build_request({"metadata_path": str(_meta(tmp_path)), "privacy": "public"}, NOW)


def test_schedule_forces_private_and_utc(tmp_path):
    req = build_request({"metadata_path": str(_meta(tmp_path)), "privacy": "unlisted",
                         "publish_at": "2026-10-20T18:00:00+05:00"}, NOW)
    st = req["body"]["status"]
    assert st["privacyStatus"] == "private"
    assert st["publishAt"] == "2026-10-20T13:00:00.000Z"


def test_publish_at_must_be_future():
    with pytest.raises(UploadInputError):
        parse_publish_at("2026-10-17T12:05:00+00:00", NOW)


@pytest.mark.parametrize("over", [{"title": "x" * 101}, {"title": "a <b>"}, {"tags": ["t" * 60] * 10}])
def test_metadata_limits(tmp_path, over):
    with pytest.raises(UploadInputError):
        build_request({"metadata_path": str(_meta(tmp_path, **over))}, NOW)


def test_execute_needs_confirm(tmp_path):
    res = YouTubeUpload().execute({"metadata_path": str(_meta(tmp_path))})
    assert res.success is False
    assert "confirm" in res.error


def test_execute_dry_run(tmp_path):
    res = YouTubeUpload().execute({"metadata_path": str(_meta(tmp_path)), "dry_run": True})
    assert res.success is True
    assert res.data["dry_run"] is True


def test_cli_dry_run(tmp_path, capsys):
    assert main(["--metadata", str(_meta(tmp_path)), "--dry-run",
                 "--client-secret", str(tmp_path / "none.json")]) == 0
    assert "--dry-run" in capsys.readouterr().out


def test_registry_discovers_youtube_upload():
    reg = ToolRegistry()
    reg.discover()
    assert reg.get("youtube_upload") is not None
