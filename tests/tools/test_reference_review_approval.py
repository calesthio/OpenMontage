from pathlib import Path

from tools.base_tool import ToolStatus
from tools.analysis.reference_review_approval import (
    APPROVAL_PHRASE,
    ReferenceReviewApproval,
)


def _edited_package() -> dict:
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 9.0,
        },
        "rewrite_draft": {
            "status": "needs_human_edit",
            "text": "人工改好的复刻文案。",
        },
        "editable_inputs": {
            "status": "needs_human_edit",
            "custom_assets": [
                {
                    "id": "face-ref",
                    "type": "image",
                    "path": "assets/images/face.png",
                    "scene_id": "s1",
                    "role": "subject_or_face_reference",
                    "authorized": True,
                }
            ],
        },
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 9.0,
                "production_inputs": {
                    "script_text": "这是人工确认后的口播文案。",
                    "seedance_prompt": "竖屏创作者口播，干净背景，人物面向镜头。",
                    "selected_assets": [{"id": "face-ref"}],
                },
            }
        ],
        "approval": {
            "status": "pending_human_review",
            "required_before_production": True,
            "requires_team_authorized_face_or_avatar": True,
        },
    }


def test_approves_edited_reference_package_with_explicit_phrase(tmp_path):
    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "replication_package": _edited_package(),
            "target_mode": "seedance",
            "reviewer": "operator",
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert result.success, result.error
    approved = result.data["approved_package"]
    assert approved["approval"]["status"] == "approved"
    assert approved["approval"]["target_mode"] == "seedance"
    assert approved["approval"]["reviewed_by"] == "operator"
    assert approved["editable_inputs"]["status"] == "approved_for_production"
    assert Path(result.data["json_path"]).is_file()
    assert result.artifacts == [result.data["json_path"]]


def test_rejects_approval_without_explicit_phrase(tmp_path):
    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _edited_package(),
            "target_mode": "seedance",
            "reviewer": "operator",
            "approval_phrase": "approve",
        }
    )

    assert not result.success
    assert APPROVAL_PHRASE in result.error


def test_rejects_seedance_package_without_prompt(tmp_path):
    package = _edited_package()
    package["scenes"][0]["production_inputs"]["seedance_prompt"] = " "

    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
            "reviewer": "operator",
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert not result.success
    assert "seedance_prompt" in result.error


def test_rejects_unapproved_selected_assets(tmp_path):
    package = _edited_package()
    package["editable_inputs"]["custom_assets"][0]["authorized"] = False

    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
            "reviewer": "operator",
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert not result.success
    assert "team-authorized" in result.error


def test_rejects_seedance_package_without_authorized_face_asset(tmp_path):
    package = _edited_package()
    package["editable_inputs"]["custom_assets"] = [
        {
            "id": "product-ref",
            "type": "image",
            "path": "assets/images/product.png",
            "scene_id": "s1",
            "role": "product_or_brand_reference",
            "authorized": True,
        }
    ]
    package["scenes"][0]["production_inputs"]["selected_assets"] = [
        {"id": "product-ref"}
    ]

    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
            "reviewer": "operator",
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert not result.success
    assert "face/presenter" in result.error


def test_v1_does_not_accept_avatar_reference_as_face_asset(tmp_path):
    package = _edited_package()
    package["editable_inputs"]["custom_assets"][0]["id"] = "avatar-ref"
    package["editable_inputs"]["custom_assets"][0]["role"] = "avatar_reference"
    package["scenes"][0]["production_inputs"]["selected_assets"] = [
        {"id": "avatar-ref"}
    ]

    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
            "reviewer": "operator",
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert not result.success
    assert "face/presenter" in result.error


def test_v1_rejects_deferred_digital_human_approval_mode(tmp_path):
    result = ReferenceReviewApproval().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _edited_package(),
            "target_mode": "digital_human",
            "reviewer": "operator",
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert not result.success
    assert "deferred in reference-video v1" in result.error
    assert "seedance" in result.error


def test_v1_approval_tool_advertises_seedance_as_only_target_mode():
    assert ReferenceReviewApproval.supports["target_modes"] == ["seedance"]
    assert ReferenceReviewApproval.input_schema["properties"]["target_mode"]["enum"] == ["seedance"]


def test_reference_review_approval_tool_is_available_without_external_dependencies():
    assert ReferenceReviewApproval().get_status() == ToolStatus.AVAILABLE
