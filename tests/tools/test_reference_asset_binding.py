from pathlib import Path

from tools.analysis.reference_asset_binding import ReferenceAssetBinding
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
                    "script_text": "人工改好的文案。",
                    "seedance_prompt": "竖屏产品口播，人物面向镜头。",
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


def test_imports_and_binds_team_authorized_image_to_scene(tmp_path):
    source = tmp_path / "face.png"
    source.write_bytes(b"fake image")

    result = ReferenceAssetBinding().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "replication_package": _pending_package(),
            "assets": [
                {
                    "path": str(source),
                    "scene_id": "s1",
                    "id": "face-ref",
                    "role": "subject_or_face_reference",
                    "authorized": True,
                }
            ],
        }
    )

    assert result.success, result.error
    package = result.data["replication_package"]
    asset = package["editable_inputs"]["custom_assets"][0]
    selected = package["scenes"][0]["production_inputs"]["selected_assets"][0]
    project_dir = Path(tmp_path / "project")

    assert package["approval"]["status"] == "pending_human_review"
    assert package["editable_inputs"]["status"] == "needs_human_edit"
    assert asset["id"] == "face-ref"
    assert asset["role"] == "subject_or_face_reference"
    assert asset["authorized"] is True
    assert selected["id"] == "face-ref"
    assert selected["path"] == asset["path"]
    assert selected["authorized"] is True
    assert (project_dir / asset["path"]).read_bytes() == b"fake image"
    assert Path(result.data["json_path"]).is_file()


def test_rejects_binding_to_already_approved_package(tmp_path):
    package = _pending_package()
    package["approval"]["status"] = "approved"

    result = ReferenceAssetBinding().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "assets": [
                {
                    "path": str(tmp_path / "face.png"),
                    "scene_id": "s1",
                    "id": "face-ref",
                    "authorized": True,
                }
            ],
        }
    )

    assert not result.success
    assert "already approved" in result.error


def test_rejects_unknown_scene_binding(tmp_path):
    source = tmp_path / "face.png"
    source.write_bytes(b"fake image")

    result = ReferenceAssetBinding().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _pending_package(),
            "assets": [
                {
                    "path": str(source),
                    "scene_id": "missing",
                    "id": "face-ref",
                    "authorized": True,
                }
            ],
        }
    )

    assert not result.success
    assert "Unknown scene_id" in result.error


def test_reference_asset_binding_tool_is_available_without_external_dependencies():
    assert ReferenceAssetBinding().get_status() == ToolStatus.AVAILABLE
