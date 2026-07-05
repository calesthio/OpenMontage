from pathlib import Path

from tools.analysis.reference_production_plan import ReferenceProductionPlan
from tools.base_tool import ToolStatus


def _package():
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 12.0,
        },
        "rewrite_draft": {
            "status": "needs_human_edit",
            "text": "开头三秒提出痛点，然后展示团队产品卖点。",
        },
        "editable_inputs": {
            "custom_assets": [
                {
                    "id": "face-ref",
                    "type": "image",
                    "path": "assets/images/face.png",
                    "scene_id": "s1",
                    "role": "subject_or_face_reference",
                    "authorized": True,
                },
                {
                    "id": "product-ref",
                    "type": "image",
                    "path": "assets/images/product.png",
                    "scene_id": "s1",
                    "role": "product_or_brand_reference",
                    "authorized": True,
                },
            ]
        },
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 12.0,
                "visual_summary": "人物拿着产品正面口播",
                "production_inputs": {
                    "script_text": "这个产品适合每天通勤使用。",
                    "seedance_prompt": "人物拿着产品正面口播，固定机位，干净背景。",
                    "selected_assets": [
                        {"id": "face-ref", "authorized": True},
                        {"id": "product-ref", "authorized": True},
                    ],
                },
            }
        ],
        "approval": {
            "status": "approved",
            "required_before_production": True,
            "requires_team_authorized_face_or_avatar": True,
        },
    }


def test_builds_seedance_ready_plan_from_approved_edited_package(tmp_path):
    package = _package()
    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "replication_package": package,
            "target_mode": "seedance",
            "duration": "12",
            "resolution": "720p",
            "batch_size": 1,
        }
    )

    assert result.success, result.error
    plan = result.data["production_plan"]
    assert plan["status"] == "ready_for_production"
    assert plan["target_mode"] == "seedance"
    assert plan["seedance_constraints"]["duration"] == "12"
    assert plan["seedance_constraints"]["resolution"] == "720p"
    assert plan["seedance_constraints"]["batch_size"] == 1
    assert plan["scenes"][0]["script_text"] == "这个产品适合每天通勤使用。"
    assert plan["scenes"][0]["seedance_prompt"].startswith("人物拿着产品")
    assert plan["scenes"][0]["selected_asset_ids"] == ["face-ref", "product-ref"]
    assert Path(result.data["json_path"]).is_file()
    assert result.artifacts == [result.data["json_path"]]


def test_rejects_unapproved_package_before_production(tmp_path):
    package = _package()
    package["approval"]["status"] = "pending_human_review"

    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
        }
    )

    assert not result.success
    assert "approved" in result.error


def test_rejects_scene_without_editable_seedance_prompt(tmp_path):
    package = _package()
    package["scenes"][0]["production_inputs"]["seedance_prompt"] = " "

    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
        }
    )

    assert not result.success
    assert "seedance_prompt" in result.error


def test_rejects_unauthorized_selected_assets(tmp_path):
    package = _package()
    package["scenes"][0]["production_inputs"]["selected_assets"][0]["authorized"] = False

    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
        }
    )

    assert not result.success
    assert "team-authorized" in result.error


def test_rejects_plan_without_authorized_face_asset(tmp_path):
    package = _package()
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
        {"id": "product-ref", "authorized": True}
    ]

    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": package,
            "target_mode": "seedance",
        }
    )

    assert not result.success
    assert "face/presenter" in result.error


def test_rejects_seedance_batch_above_five(tmp_path):
    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _package(),
            "target_mode": "seedance",
            "batch_size": 6,
        }
    )

    assert not result.success
    assert "at most 5" in result.error


def test_v1_rejects_deferred_digital_human_target_mode(tmp_path):
    result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(tmp_path),
            "replication_package": _package(),
            "target_mode": "digital_human",
        }
    )

    assert not result.success
    assert "deferred in reference-video v1" in result.error
    assert "seedance" in result.error


def test_v1_advertises_seedance_as_only_supported_target_mode():
    assert ReferenceProductionPlan.supports["target_modes"] == ["seedance"]
    assert ReferenceProductionPlan.input_schema["properties"]["target_mode"]["enum"] == ["seedance"]


def test_reference_production_plan_tool_is_available_without_external_dependencies():
    assert ReferenceProductionPlan().get_status() == ToolStatus.AVAILABLE
