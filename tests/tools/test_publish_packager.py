from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from schemas.artifacts import load_schema, validate_artifact
from tools.publishers.publish_packager import PublishPackager
from tools.tool_registry import ToolRegistry


def test_final_package_manifest_schema_is_registered():
    schema = load_schema("final_package_manifest")

    assert schema["title"] == "Final Package Manifest"


def test_package_copies_assets_and_writes_manifest(tmp_path: Path):
    video = tmp_path / "render.mp4"
    cover = tmp_path / "cover.jpg"
    captions = tmp_path / "captions.srt"
    script = tmp_path / "script.json"
    video.write_bytes(b"fake video")
    cover.write_bytes(b"fake cover")
    captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    script.write_text(
        json.dumps(
            {
                "version": "1.0",
                "title": "Demo",
                "total_duration_seconds": 10,
                "cover_direction": {
                    "primary_message": "A clear promise before playback",
                    "visual_anchor": "A product UI close-up",
                    "candidate_source": "generated_image",
                },
                "cover_policy": {
                    "required": True,
                    "reason": "Embedded product page video",
                    "user_decision": "review_final_cover",
                    "first_frame_mode": "replace_first_frame",
                    "triggers": ["page_embed", "product_marketing"],
                },
                "sections": [
                    {
                        "id": "s1",
                        "text": "Hello",
                        "start_seconds": 0,
                        "end_seconds": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = PublishPackager().execute(
        {
            "video_path": str(video),
            "cover_path": str(cover),
            "script_path": str(script),
            "output_dir": str(tmp_path / "final"),
            "project_id": "demo",
            "variant_id": "v1",
            "channel": "default",
            "cover_mode": "none",
            "cover_source_kind": "generated_image",
            "cover_generator": {"provider": "image2", "model": "example"},
            "extra_files": [{"path": str(captions), "role": "captions"}],
        }
    )

    assert result.success, result.error
    manifest_path = tmp_path / "final" / "final_package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_artifact("final_package_manifest", manifest)
    assert manifest["cover_direction"]["primary_message"] == "A clear promise before playback"
    assert manifest["cover_policy"]["user_decision"] == "review_final_cover"
    assert manifest["cover_policy"]["first_frame_mode"] == "replace_first_frame"
    assert manifest["cover"]["source_kind"] == "generated_image"
    assert manifest["cover"]["generator"]["provider"] == "image2"
    assert manifest["video"]["cover_mode"] == "none"
    assert manifest["video"]["cover_first_frame"] is False
    roles = {entry["role"] for entry in manifest["files"]}
    assert roles == {"video", "cover", "captions"}
    assert (tmp_path / "final" / "video" / "render.mp4").exists()
    assert (tmp_path / "final" / "cover" / "cover.jpg").exists()
    assert (tmp_path / "final" / "sidecars" / "captions.srt").exists()


def test_script_schema_accepts_cover_policy():
    script = {
        "version": "1.0",
        "title": "Cover Policy Demo",
        "total_duration_seconds": 30,
        "cover_policy": {
            "required": False,
            "reason": "Internal timing smoke test",
            "user_decision": "none",
            "first_frame_mode": "none",
            "triggers": ["draft_or_internal_only"],
        },
        "sections": [
            {
                "id": "s1",
                "text": "Hello",
                "start_seconds": 0,
                "end_seconds": 30,
            }
        ],
    }

    validate_artifact("script", script)


def test_package_blocks_nonempty_output_without_overwrite(tmp_path: Path):
    video = tmp_path / "render.mp4"
    video.write_bytes(b"fake video")
    output_dir = tmp_path / "final"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep", encoding="utf-8")

    result = PublishPackager().execute(
        {"video_path": str(video), "output_dir": str(output_dir)}
    )

    assert not result.success
    assert "not empty" in result.error


def test_package_requires_cover_for_first_frame_mode(tmp_path: Path):
    video = tmp_path / "render.mp4"
    video.write_bytes(b"fake video")

    result = PublishPackager().execute(
        {
            "video_path": str(video),
            "output_dir": str(tmp_path / "final"),
            "cover_mode": "replace_first_frame",
        }
    )

    assert not result.success
    assert "cover_path is required" in result.error


def test_package_uses_cover_policy_first_frame_mode_when_cover_mode_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    video = tmp_path / "render.mp4"
    cover = tmp_path / "cover.jpg"
    script = tmp_path / "script.json"
    video.write_bytes(b"fake video")
    cover.write_bytes(b"fake cover")
    script.write_text(
        json.dumps(
            {
                "version": "1.0",
                "title": "Demo",
                "total_duration_seconds": 10,
                "cover_policy": {
                    "required": True,
                    "reason": "Page embed",
                    "user_decision": "review_final_cover",
                    "first_frame_mode": "replace_first_frame",
                },
                "sections": [
                    {
                        "id": "s1",
                        "text": "Hello",
                        "start_seconds": 0,
                        "end_seconds": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_replace_first_frame(self, video_path: Path, cover_path: Path, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_path.read_bytes())

    monkeypatch.setattr(PublishPackager, "_replace_first_frame", fake_replace_first_frame)

    result = PublishPackager().execute(
        {
            "video_path": str(video),
            "cover_path": str(cover),
            "script_path": str(script),
            "output_dir": str(tmp_path / "final"),
        }
    )

    assert result.success, result.error
    assert result.data["video"]["cover_mode"] == "replace_first_frame"
    assert result.data["video"]["cover_first_frame"] is True


def test_dry_run_reports_first_frame_ffmpeg_need(tmp_path: Path):
    plan = PublishPackager().dry_run(
        {
            "video_path": str(tmp_path / "render.mp4"),
            "output_dir": str(tmp_path / "final"),
            "cover_mode": "replace_first_frame",
        }
    )

    assert plan["requires_ffmpeg"] is True
    assert any(path.endswith("final_package_manifest.json") for path in plan["would_write"])


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
def test_replace_first_frame_keeps_duration_stable(tmp_path: Path):
    video = tmp_path / "source.mp4"
    cover = tmp_path / "cover.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=44100",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=320x180",
            "-frames:v",
            "1",
            str(cover),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    result = PublishPackager().execute(
        {
            "video_path": str(video),
            "cover_path": str(cover),
            "output_dir": str(tmp_path / "final"),
            "cover_mode": "replace_first_frame",
            "duration_tolerance_seconds": 0.15,
        }
    )

    assert result.success, result.error
    assert result.data["video"]["cover_first_frame"] is True
    assert abs(result.data["video"]["duration_delta_seconds"]) <= 0.15


def test_publish_packager_is_discoverable():
    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("publish_packager")
    assert tool is not None
    assert "write_final_package_manifest" in tool.capabilities
