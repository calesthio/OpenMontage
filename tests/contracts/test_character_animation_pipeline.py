"""Contract tests for the local character-animation pipeline."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_loader import get_required_tools, get_stage_order, load_pipeline
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact
from tools.character.character_animation import (
    ActionTimelineCompiler,
    CharacterAnimationReviewer,
    CharacterRigRenderer,
    CharacterSpecGenerator,
    PoseLibraryBuilder,
    SvgRigBuilder,
)
from tools.tool_registry import registry
from tools.video.hyperframes_compose import HyperFramesCompose
from tools.video.video_compose import VideoCompose


def test_character_animation_manifest_contract():
    manifest = load_pipeline("character-animation")

    assert manifest["name"] == "character-animation"
    assert get_stage_order(manifest) == [
        "research",
        "proposal",
        "script",
        "character_design",
        "rig_plan",
        "scene_plan",
        "assets",
        "edit",
        "compose",
        "publish",
    ]
    assert {
        "character_spec_generator",
        "svg_rig_builder",
        "pose_library_builder",
        "action_timeline_compiler",
        "character_rig_renderer",
        "character_animation_reviewer",
    }.issubset(set(get_required_tools(manifest)))


def test_character_artifacts_are_registered():
    assert {
        "character_design",
        "rig_plan",
        "pose_library",
        "action_timeline",
        "character_qa_report",
    }.issubset(set(ARTIFACT_NAMES))


def test_character_tools_discover_in_registry():
    registry.discover()

    names = {tool.name for tool in registry.get_by_capability("character_animation")}
    assert {
        "character_spec_generator",
        "svg_rig_builder",
        "pose_library_builder",
        "action_timeline_compiler",
        "character_rig_renderer",
        "character_animation_reviewer",
    }.issubset(names)


def test_character_animation_smoke_flow(tmp_path):
    character_result = CharacterSpecGenerator().execute(
        {
            "characters": [
                {
                    "id": "mouse_lead",
                    "role": "curious lead",
                    "body_type": "mouse with tail",
                    "required_actions": ["idle", "gesture", "tail_swish"],
                },
                {
                    "id": "bird_friend",
                    "role": "expressive sidekick",
                    "body_type": "round bird",
                    "required_actions": ["idle", "wing_flap", "react"],
                },
            ],
            "output_path": str(tmp_path / "character_design.json"),
        }
    )
    assert character_result.success
    character_design = character_result.data["character_design"]
    validate_artifact("character_design", character_design)

    rig_result = SvgRigBuilder().execute(
        {
            "character_design": character_design,
            "output_path": str(tmp_path / "rig_plan.json"),
        }
    )
    assert rig_result.success
    rig_plan = rig_result.data["rig_plan"]
    validate_artifact("rig_plan", rig_plan)

    pose_result = PoseLibraryBuilder().execute(
        {"rig_plan": rig_plan, "output_path": str(tmp_path / "pose_library.json")}
    )
    assert pose_result.success
    pose_library = pose_result.data["pose_library"]
    validate_artifact("pose_library", pose_library)

    scene_plan = {
        "version": "1.0",
        "scenes": [
            {
                "id": "scene-1",
                "type": "character_scene",
                "start_seconds": 0,
                "end_seconds": 4,
                "description": "The mouse discovers a glowing seed while the bird reacts.",
                "hero_moment": True,
                "character_actions": [
                    {
                        "character_id": "mouse_lead",
                        "emotion": "surprised",
                        "action_sequence": ["anticipate", "perform", "settle"],
                    },
                    {
                        "character_id": "bird_friend",
                        "emotion": "surprised",
                        "action_sequence": ["react", "follow", "settle"],
                    },
                ],
            }
        ],
    }
    validate_artifact("scene_plan", scene_plan)
    timeline_result = ActionTimelineCompiler().execute(
        {
            "scene_plan": scene_plan,
            "character_ids": ["mouse_lead", "bird_friend"],
            "output_path": str(tmp_path / "action_timeline.json"),
        }
    )
    assert timeline_result.success
    action_timeline = timeline_result.data["action_timeline"]
    validate_artifact("action_timeline", action_timeline)
    assert {action["character_id"] for action in action_timeline["scenes"][0]["actions"]} == {
        "mouse_lead",
        "bird_friend",
    }

    preview_path = tmp_path / "preview.html"
    render_result = CharacterRigRenderer().execute(
        {
            "rig_plan": rig_plan,
            "pose_library": pose_library,
            "action_timeline": action_timeline,
            "output_path": str(preview_path),
        }
    )
    assert render_result.success
    assert preview_path.exists()
    preview_html = preview_path.read_text(encoding="utf-8")
    assert "character_mouse-lead" in preview_html
    assert "character_bird-friend" in preview_html

    qa_result = CharacterAnimationReviewer().execute(
        {
            "rig_plan": rig_plan,
            "pose_library": pose_library,
            "action_timeline": action_timeline,
            "preview_path": str(preview_path),
            "output_path": str(tmp_path / "character_qa_report.json"),
        }
    )
    assert qa_result.success
    qa_report = qa_result.data["character_qa_report"]
    validate_artifact("character_qa_report", qa_report)
    assert qa_report["status"] == "pass"
    assert qa_report["checks"]["schema_valid"] is True


def test_character_style_is_normalized_for_schema(tmp_path):
    result = CharacterSpecGenerator().execute(
        {
            "characters": [{"id": "style_test", "role": "lead", "body_type": "round"}],
            "style": {
                "name": "flat-motion-graphics",
                "palette": ["#ff8f68", "#75b8ff"],
                "unexpected": "should not leak into artifact",
            },
            "output_path": str(tmp_path / "character_design.json"),
        }
    )

    assert result.success
    character_design = result.data["character_design"]
    validate_artifact("character_design", character_design)
    assert character_design["style"] == {
        "visual_style": "flat-motion-graphics",
        "palette": ["#ff8f68", "#75b8ff"],
    }


def test_character_renderer_can_handoff_to_video_compose(tmp_path):
    hyperframes = HyperFramesCompose()
    runtime = hyperframes._runtime_check()
    if not runtime["runtime_available"]:
        pytest.skip("HyperFrames runtime is required for character render handoff")

    character_design = CharacterSpecGenerator().execute(
        {"characters": [{"id": "mouse_lead", "role": "lead", "body_type": "mouse with tail"}]}
    ).data["character_design"]
    rig_plan = SvgRigBuilder().execute({"character_design": character_design}).data["rig_plan"]
    pose_library = PoseLibraryBuilder().execute({"rig_plan": rig_plan}).data["pose_library"]
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {
                "id": "scene-1",
                "type": "character_scene",
                "description": "Mouse reacts to a tiny surprise.",
                "start_seconds": 0,
                "end_seconds": 1,
                "character_actions": [
                    {
                        "character_id": "mouse_lead",
                        "emotion": "surprised",
                        "action_sequence": ["anticipate", "perform", "settle"],
                    }
                ],
            }
        ],
    }
    validate_artifact("scene_plan", scene_plan)
    action_timeline = ActionTimelineCompiler().execute(
        {"scene_plan": scene_plan, "character_ids": ["mouse_lead"]}
    ).data["action_timeline"]

    render_result = CharacterRigRenderer().execute(
        {
            "rig_plan": rig_plan,
            "pose_library": pose_library,
            "action_timeline": action_timeline,
            "output_path": str(tmp_path / "preview.html"),
            "workspace_path": str(tmp_path / "hyperframes"),
        }
    )
    assert render_result.success
    validate_artifact("asset_manifest", render_result.data["asset_manifest"])
    validate_artifact("edit_decisions", render_result.data["edit_decisions"])
    assert render_result.data["edit_decisions"]["render_runtime"] == "hyperframes"
    assert Path(render_result.data["composition_path"]).exists()

    output_path = tmp_path / "renders" / "final.mp4"
    compose_result = VideoCompose().execute(
        {
            "operation": "render",
            "asset_manifest": render_result.data["asset_manifest"],
            "edit_decisions": render_result.data["edit_decisions"],
            "workspace_path": render_result.data["hyperframes_workspace"],
            "output_path": str(output_path),
            "skip_contrast": True,
            "quality": "draft",
            "fps": 24,
        }
    )

    assert compose_result.success, compose_result.error
    assert output_path.exists()
