from __future__ import annotations

import json
import subprocess
import sys

from lib.pipeline_loader import get_required_tools, load_pipeline
from schemas.artifacts import validate_artifact
from tools.tool_registry import registry
from tools.video.bgm_montage import (
    BgmMontage,
    _canonical_asset_manifest,
    _canonical_edit_decisions,
    _canonical_render_report,
    _parse_last_json,
    _project_output_path,
)


def test_parse_last_json_prefers_the_outer_run_summary() -> None:
    output = "\n".join(
        [
            "[1/7] analyzing",
            json.dumps({"status": "partial", "artifacts": {"run_report": "old"}}),
            json.dumps(
                {
                    "status": "passed",
                    "passed": True,
                    "artifacts": {"run_report": "run_report.json", "video": "final.mp4"},
                },
                indent=2,
            ),
        ]
    )

    assert _parse_last_json(output)["artifacts"]["video"] == "final.mp4"


def test_generated_paths_must_stay_inside_the_project(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    try:
        _project_output_path(project, tmp_path / "outside.json", project / "inside.json", "output_path")
    except ValueError as error:
        assert "inside project_dir" in str(error)
    else:
        raise AssertionError("external output path was accepted")


def test_canonical_artifacts_validate(tmp_path) -> None:
    clip = tmp_path / "clip.mp4"
    bgm = tmp_path / "music.wav"
    clip.touch()
    bgm.touch()
    assets = _canonical_asset_manifest(
        {
            "provider": "local-library",
            "assets": [
                {
                    "id": "clip_1",
                    "type": "video",
                    "local_path": str(clip),
                    "license": "CC0",
                    "quality_score": 0.8,
                }
            ],
        },
        bgm_path=str(bgm),
        source_manifest_path=str(tmp_path / "asset_manifest.json"),
    )
    validate_artifact("asset_manifest", assets)

    edit = _canonical_edit_decisions(
        {
            "schema_version": "1.3",
            "shots": [
                {
                    "source_path": str(clip),
                    "source_start": 0,
                    "source_end": 2,
                    "duration": 2,
                    "reason": "beat-aligned",
                }
            ],
        },
        assets=assets,
        audiomap_path=str(tmp_path / "audiomap.json"),
        timeline_path=str(tmp_path / "timeline.json"),
        bgm_path=str(bgm),
    )
    validate_artifact("edit_decisions", edit)

    render = _canonical_render_report(
        {
            "path": str(tmp_path / "final.mp4"),
            "duration_seconds": 2,
            "size_bytes": 100,
            "video": {
                "codec": "h264",
                "width": 1920,
                "height": 1080,
                "frame_rate_fps": 30,
                "duration_seconds": 2,
            },
            "audio": {"codec": "aac"},
            "checks": {"full_decode": True},
            "passed": True,
        },
        run_report_path=str(tmp_path / "run_report.json"),
        bgm_artifacts={"render_report": str(tmp_path / "render_report.json")},
        status="passed",
    )
    assert render is not None
    validate_artifact("render_report", render)


def test_tool_and_pipeline_are_discoverable(monkeypatch) -> None:
    monkeypatch.delenv("BGM_MONTAGE_ROOT", raising=False)
    assert BgmMontage().name == "bgm_montage"
    assert BgmMontage().get_status().value == "unavailable"

    registry.discover()
    assert registry.get("bgm_montage") is not None

    manifest = load_pipeline("bgm-montage")
    assert "bgm_montage" in get_required_tools(manifest)


def test_canonical_edit_decisions_clamp_negative_source_start() -> None:
    decisions = _canonical_edit_decisions(
        {"shots": [{"source_path": "clip.mp4", "source_start": -1, "source_end": -0.5, "duration": 2}]},
        assets={"metadata": {"path_to_id": {}}},
        audiomap_path=None,
        timeline_path=None,
        bgm_path=None,
    )

    assert decisions["cuts"][0]["in_seconds"] == 0
    assert decisions["cuts"][0]["out_seconds"] == 2


def test_run_forwards_optional_jianying_export(monkeypatch, tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    bgm = tmp_path / "music.wav"
    bgm.touch()
    tool = BgmMontage()
    captured: dict[str, object] = {}
    monkeypatch.setattr(tool, "_context", lambda inputs: (tmp_path, project, sys.executable))

    def fake_run_script(root, python, script_name, args, *, timeout):
        captured["script_name"] = script_name
        captured["args"] = args
        return subprocess.CompletedProcess(
            args=[python, script_name],
            returncode=0,
            stdout=json.dumps({"status": "passed", "passed": True, "artifacts": {}}),
            stderr="",
        )

    monkeypatch.setattr(tool, "_run_script", fake_run_script)
    monkeypatch.setattr(tool, "_write_canonical_artifacts", lambda *args, **kwargs: [])
    result = tool._run(
        {
            "project_dir": str(project),
            "bgm": str(bgm),
            "theme": "test",
            "duration_seconds": 8,
            "ratio": "16:9",
            "source_provider": "local-library",
            "local_library_dir": str(tmp_path / "library"),
            "jianying_draft": True,
            "jianying_draft_name": "test draft",
            "jianying_draft_root": str(tmp_path / "drafts"),
            "jianying_python": sys.executable,
        }
    )

    assert result.success
    assert captured["script_name"] == "bgm_montage.py"
    args = captured["args"]
    assert isinstance(args, list)
    assert "--jianying-draft" in args
    assert args[args.index("--jianying-draft-name") + 1] == "test draft"
    assert args[args.index("--jianying-draft-root") + 1] == str(tmp_path / "drafts")
    assert args[args.index("--jianying-python") + 1] == sys.executable
