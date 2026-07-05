from pathlib import Path

from tools.analysis.reference_prompt_reverse import ReferencePromptReverse
from tools.base_tool import ToolStatus


def _package(frame_path: str) -> dict:
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 8.0,
        },
        "rewrite_draft": {"status": "needs_human_edit", "text": "原始口播文案。"},
        "editable_inputs": {"status": "needs_human_edit", "custom_assets": []},
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 8.0,
                "visual_summary": "参考视频片段 1",
                "speech": "原始口播文案。",
                "camera_motion": "",
                "keyframes": [frame_path],
                "production_inputs": {
                    "status": "needs_human_edit",
                    "script_text": "原始口播文案。",
                    "seedance_prompt": "旧提示词。",
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


class FakeVisionTool:
    def __init__(self):
        self.calls = []

    def execute(self, inputs):
        self.calls.append(inputs)
        from tools.base_tool import ToolResult

        return ToolResult(
            success=True,
            data={
                "parsed": {
                    "visual_summary": "人物正面口播，手持产品，办公室背景",
                    "camera_motion": "固定机位，轻微推近",
                    "seedance_prompt": "竖屏产品口播，人物面向镜头，办公室背景，轻微推近。",
                    "pacing": "fast_hook",
                }
            },
        )


def test_reverses_scene_prompts_from_keyframes_without_approving(tmp_path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake jpg")
    fake_tool = FakeVisionTool()

    result = ReferencePromptReverse(vision_tool=fake_tool).execute(
        {
            "project_dir": str(tmp_path / "project"),
            "replication_package": _package(str(frame)),
            "provider": "doubao",
        }
    )

    assert result.success, result.error
    package = result.data["replication_package"]
    scene = package["scenes"][0]
    assert scene["visual_summary"] == "人物正面口播，手持产品，办公室背景"
    assert scene["camera_motion"] == "固定机位，轻微推近"
    assert scene["pacing"] == "fast_hook"
    assert scene["production_inputs"]["seedance_prompt"].startswith("竖屏产品口播")
    assert package["approval"]["status"] == "pending_human_review"
    assert package["editable_inputs"]["status"] == "needs_human_edit"
    assert Path(result.data["json_path"]).is_file()
    assert fake_tool.calls[0]["image_paths"] == [str(frame)]


def test_rejects_prompt_reverse_for_approved_package(tmp_path):
    package = _package(str(tmp_path / "frame.jpg"))
    package["approval"]["status"] = "approved"

    result = ReferencePromptReverse(vision_tool=FakeVisionTool()).execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
        }
    )

    assert not result.success
    assert "already approved" in result.error


def test_reference_prompt_reverse_tool_is_available_without_external_dependencies():
    assert ReferencePromptReverse().get_status() == ToolStatus.AVAILABLE
