from pathlib import Path

from lib.pipeline_loader import get_required_tools, get_stage_order, list_pipelines, load_pipeline


def test_creator_video_pipeline_loads_with_expected_stage_order():
    manifest = load_pipeline("creator-video")

    assert manifest["name"] == "creator-video"
    assert get_stage_order(manifest) == [
        "research",
        "proposal",
        "script",
        "scene_plan",
        "assets",
        "edit",
        "compose",
        "publish",
    ]


def test_creator_video_pipeline_is_listed_and_uses_seedance_and_user_assets():
    manifest = load_pipeline("creator-video")
    tools = get_required_tools(manifest)

    assert "creator-video" in list_pipelines()
    assert "custom_asset_import" in tools
    assert "video_selector" in tools
    assert "runninghub_seedance_video" in tools
    assert "seedance_video" in tools
    assert "seedance_replicate" in tools
    assert "video_compose" in tools


def test_creator_video_required_skills_exist():
    manifest = load_pipeline("creator-video")
    root = Path(__file__).resolve().parent.parent.parent

    for skill_ref in manifest.get("required_skills", []):
        assert (root / "skills" / f"{skill_ref}.md").is_file(), skill_ref
