from pathlib import Path

from tools.analysis.reference_video_package import ReferenceVideoPackage
from tools.base_tool import ToolStatus


def test_reference_video_package_writes_json_and_markdown(tmp_path):
    project_dir = tmp_path / "project"
    output_dir = project_dir / "artifacts"

    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(project_dir),
            "reference_source": {
                "input_type": "local_file",
                "input": "source.mp4",
                "local_video_path": str(project_dir / "reference" / "source.mp4"),
                "duration_seconds": 6.0,
                "width": 720,
                "height": 1280,
                "fps": 30,
            },
            "reference_analysis": {
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 3.0,
                        "visual_summary": "人物正面口播，办公室背景",
                        "camera_motion": "固定机位",
                        "keyframes": ["keyframes/s1.jpg"],
                    },
                    {
                        "scene_id": "s2",
                        "start": 3.0,
                        "end": 6.0,
                        "visual_summary": "产品特写和字幕强调",
                        "camera_motion": "轻微推近",
                        "keyframes": ["keyframes/s2.jpg"],
                    },
                ]
            },
            "reference_transcript": {
                "status": "ok",
                "raw_text": "前三秒给出钩子，然后展示产品卖点。",
                "segments": [
                    {"start": 0.0, "end": 3.0, "text": "前三秒给出钩子"},
                    {"start": 3.0, "end": 6.0, "text": "然后展示产品卖点"},
                ],
            },
            "output_dir": str(output_dir),
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["approval"]["status"] == "pending_human_review"
    assert package["rewrite_draft"]["status"] == "needs_human_edit"
    assert package["replication_strategy"]["recommended_mode"] == "seedance"
    assert package["replication_strategy"]["alternatives"] == ["seedance"]
    assert "数字人" not in package["replication_strategy"]["reason"]
    assert len(package["scenes"]) == 2
    assert Path(result.data["json_path"]).is_file()
    assert Path(result.data["markdown_path"]).is_file()
    assert "前三秒给出钩子" in Path(result.data["markdown_path"]).read_text(encoding="utf-8")
    assert result.artifacts == [result.data["json_path"], result.data["markdown_path"]]


def test_reference_video_package_handles_pending_transcription(tmp_path):
    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(tmp_path),
            "reference_source": {
                "input_type": "local_file",
                "input": "silent.mp4",
                "local_video_path": str(tmp_path / "silent.mp4"),
                "duration_seconds": 4.0,
            },
            "reference_analysis": {
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 4.0,
                        "visual_summary": "无音频产品展示",
                        "keyframes": [],
                    }
                ]
            },
            "reference_transcript": {
                "status": "pending_transcription",
                "reason": "no_audio_stream",
            },
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["transcript"]["status"] == "pending_transcription"
    assert package["rewrite_draft"]["text"] == ""
    assert "no_audio_stream" in Path(result.data["markdown_path"]).read_text(encoding="utf-8")


def test_reference_video_package_does_not_treat_empty_ok_transcript_as_speech(tmp_path):
    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(tmp_path),
            "reference_source": {
                "input_type": "local_file",
                "input": "music-only.mp4",
                "local_video_path": str(tmp_path / "music-only.mp4"),
                "duration_seconds": 4.0,
            },
            "reference_analysis": {
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 4.0,
                        "visual_summary": "音乐背景产品展示",
                        "keyframes": [],
                    }
                ]
            },
            "reference_transcript": {
                "status": "ok",
                "raw_text": "",
                "segments": [],
            },
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["replication_strategy"]["recommended_mode"] == "seedance"
    assert "未获得可用口播转写" in package["replication_strategy"]["reason"]


def test_reference_video_package_exposes_editable_prompts_and_asset_slots(tmp_path):
    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(tmp_path),
            "reference_source": {
                "input_type": "local_file",
                "input": "reference.mp4",
                "local_video_path": str(tmp_path / "reference.mp4"),
                "duration_seconds": 5.0,
            },
            "reference_analysis": {
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 5.0,
                        "visual_summary": "人物拿着产品正面口播",
                        "camera_motion": "固定机位",
                        "keyframes": ["keyframes/s1.jpg"],
                    }
                ]
            },
            "reference_transcript": {
                "status": "ok",
                "raw_text": "这个产品适合每天通勤使用。",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "这个产品适合每天通勤使用。",
                    }
                ],
            },
            "custom_assets": [
                {
                    "id": "brand-product",
                    "type": "image",
                    "path": "assets/images/product.png",
                    "scene_id": "s1",
                    "role": "product_reference",
                }
            ],
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["editable_inputs"]["status"] == "needs_human_edit"
    assert "rewrite_draft.text" in package["editable_inputs"]["editable_fields"]
    assert package["editable_inputs"]["custom_assets"][0]["id"] == "brand-product"

    scene_inputs = package["scenes"][0]["production_inputs"]
    assert scene_inputs["script_text"] == "这个产品适合每天通勤使用。"
    assert "人物拿着产品正面口播" in scene_inputs["seedance_prompt"]
    assert scene_inputs["asset_slots"][0]["slot"] == "subject_or_face_reference"
    assert "avatar" not in scene_inputs["asset_slots"][0]["description"].lower()
    assert "brand-product" in Path(result.data["markdown_path"]).read_text(encoding="utf-8")


def test_reference_video_package_tool_is_available_without_external_dependencies():
    assert ReferenceVideoPackage().get_status() == ToolStatus.AVAILABLE
