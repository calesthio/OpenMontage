from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from jsonschema import validate

from lib.pipeline_loader import get_required_tools, load_pipeline
from schemas.artifacts import validate_artifact
from tools.tool_registry import registry
from tools.video.bmts_lite import BgmMontageLite


def _inputs(tmp_path: Path, output: Path) -> dict:
    audio = tmp_path / "music.mp3"
    clips = [tmp_path / "clip-a.mp4", tmp_path / "clip-b.mp4"]
    audio.write_bytes(b"audio fixture")
    for clip in clips:
        clip.write_bytes(b"video fixture")
    return {
        "audio_path": str(audio),
        "video_paths": [str(path) for path in clips],
        "output_path": str(output),
        "aspect_ratio": "auto",
    }


def test_schema_and_registry_expose_a_reference_free_local_tool() -> None:
    tool = BgmMontageLite()
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "tools" / "bgm_montage_lite.schema.json"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert tool.input_schema["properties"] == schema["properties"]
    assert tool.input_schema["required"] == schema["required"]
    assert "reference_video" not in tool.input_schema["properties"]
    assert tool.supports["reference_video_required"] is False
    assert tool.supports["api_key_required"] is False

    registry.discover()
    assert registry.get("bgm_montage_lite") is not None


def test_cinematic_compose_advertises_lite_as_an_optional_route() -> None:
    manifest = load_pipeline("cinematic")
    compose = next(stage for stage in manifest["stages"] if stage["name"] == "compose")

    assert "bgm_montage_lite" in compose["optional_tools"]
    assert "bgm_montage_lite" in get_required_tools(manifest)
    assert "video_compose" in compose["required_tools"]


def test_run_emits_mp4_timeline_audiomap_and_openmontage_report(tmp_path: Path) -> None:
    tool = BgmMontageLite()
    output = tmp_path / "renders" / "montage.mp4"
    inputs = _inputs(tmp_path, output)
    engine = tmp_path / "engine"
    engine.mkdir()
    for name in ("worker.py", "analyze_bgm.py", "timeline_planner.py", "montage.py", "visual_intelligence.py"):
        target = tmp_path / name if name == "worker.py" else engine / name
        target.write_text("", encoding="utf-8")
    seen_request: dict = {}

    def fake_run(command: list[str], *, timeout: int | None = None, cwd: Path | None = None):
        if "--request" in command:
            request_path = Path(command[command.index("--request") + 1])
            workspace = Path(command[command.index("--workspace") + 1])
            seen_request.update(json.loads(request_path.read_text(encoding="utf-8")))
            (workspace / "result.mp4").write_bytes(b"rendered mp4")
            (workspace / "timeline.json").write_text('{"shots":[]}', encoding="utf-8")
            (workspace / "audiomap.json").write_text('{"beats":[]}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, '{"duration":2.0,"ratio":"16:9","shots":3}', "")

        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "format": {"duration": "2.0", "format_name": "mov,mp4"},
                    "streams": [
                        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"},
                        {"codec_type": "audio", "codec_name": "aac"},
                    ],
                }
            ),
            "",
        )

    with (
        patch.dict("os.environ", {"BGM_MONTAGE_LITE_ROOT": str(tmp_path), "BGM_MONTAGE_LITE_PYTHON": "python"}),
        patch.object(tool, "check_dependencies"),
        patch.object(tool, "run_command", side_effect=fake_run),
    ):
        result = tool.execute(inputs)

    assert result.success, result.error
    assert result.data["aspect_ratio"] == "16:9"
    assert result.data["shot_count"] == 3
    assert result.data["render_report"]["outputs"][0]["resolution"] == "1920x1080"
    validate(instance=result.data, schema=tool.output_schema)
    validate_artifact("render_report", result.data["render_report"])
    assert [Path(path).name for path in result.artifacts] == [
        "montage.mp4",
        "montage.timeline.json",
        "montage.audiomap.json",
    ]
    assert all(Path(path).is_file() for path in result.artifacts)
    assert seen_request["ratio"] == "auto"
    assert seen_request["media"][-1]["file"] == str(Path(inputs["audio_path"]).resolve())
    assert len(seen_request["media"]) == 3


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    tool = BgmMontageLite()
    output = tmp_path / "montage.mp4"
    output.write_bytes(b"user data")
    inputs = _inputs(tmp_path, output)

    with patch.object(tool, "check_dependencies", side_effect=AssertionError("must fail before launch")):
        result = tool.execute(inputs)

    assert not result.success
    assert "already exists" in result.error
    assert output.read_bytes() == b"user data"


def test_missing_video_fails_before_runtime_checks(tmp_path: Path) -> None:
    tool = BgmMontageLite()
    audio = tmp_path / "music.mp3"
    audio.write_bytes(b"audio fixture")

    with patch.object(tool, "check_dependencies", side_effect=AssertionError("must fail before launch")):
        result = tool.execute({"audio_path": str(audio), "video_paths": []})

    assert not result.success
    assert "at least one" in result.error.lower()
