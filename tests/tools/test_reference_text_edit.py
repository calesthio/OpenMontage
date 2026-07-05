from pathlib import Path

from tools.analysis.reference_text_edit import ReferenceTextEdit
from tools.base_tool import ToolStatus


def _pending_package() -> dict:
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 8.0,
        },
        "rewrite_draft": {
            "status": "needs_human_edit",
            "text": "原始复刻稿。",
        },
        "editable_inputs": {
            "status": "needs_human_edit",
            "custom_assets": [],
        },
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 8.0,
                "production_inputs": {
                    "status": "needs_human_edit",
                    "script_text": "旧脚本。",
                    "seedance_prompt": "旧 Seedance 提示词。",
                    "selected_assets": [],
                },
            }
        ],
        "approval": {
            "status": "pending_human_review",
            "required_before_production": True,
            "requires_team_authorized_face_or_avatar": True,
        },
    }


def test_updates_rewrite_and_scene_script_prompt_without_approving(tmp_path):
    result = ReferenceTextEdit().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "replication_package": _pending_package(),
            "rewrite_text": "人工确认后的复刻稿。",
            "scene_edits": [
                {
                    "scene_id": "s1",
                    "script_text": "前三秒提出痛点，然后给出解决方案。",
                    "seedance_prompt": "竖屏近景口播，干净背景，轻微推近。",
                }
            ],
        }
    )

    assert result.success, result.error
    package = result.data["replication_package"]
    production_inputs = package["scenes"][0]["production_inputs"]
    assert package["rewrite_draft"]["text"] == "人工确认后的复刻稿。"
    assert production_inputs["script_text"] == "前三秒提出痛点，然后给出解决方案。"
    assert production_inputs["seedance_prompt"] == "竖屏近景口播，干净背景，轻微推近。"
    assert package["approval"]["status"] == "pending_human_review"
    assert package["approval"]["paid_generation_started"] is False
    assert package["editable_inputs"]["status"] == "needs_human_edit"
    assert package["edit_history"][-1]["tool"] == "reference_text_edit"
    assert Path(result.data["json_path"]).is_file()


def test_rejects_editing_already_approved_package(tmp_path):
    package = _pending_package()
    package["approval"]["status"] = "approved"

    result = ReferenceTextEdit().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "rewrite_text": "新文案。",
        }
    )

    assert not result.success
    assert "already approved" in result.error


def test_rejects_unknown_scene_edit(tmp_path):
    result = ReferenceTextEdit().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _pending_package(),
            "scene_edits": [{"scene_id": "missing", "script_text": "新文案。"}],
        }
    )

    assert not result.success
    assert "Unknown scene_id" in result.error


def test_rejects_no_text_edits(tmp_path):
    result = ReferenceTextEdit().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _pending_package(),
        }
    )

    assert not result.success
    assert "at least one" in result.error


def test_reference_text_edit_tool_is_available_without_external_dependencies():
    assert ReferenceTextEdit().get_status() == ToolStatus.AVAILABLE
