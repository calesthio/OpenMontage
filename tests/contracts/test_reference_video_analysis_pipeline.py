from pathlib import Path

from lib.pipeline_loader import get_required_tools, get_stage_order, list_pipelines, load_pipeline


def test_reference_video_analysis_pipeline_loads_with_expected_stage_order():
    manifest = load_pipeline("reference-video-analysis")

    assert manifest["name"] == "reference-video-analysis"
    assert get_stage_order(manifest) == [
        "ingest",
        "analyze",
        "transcribe",
        "package",
        "review",
    ]


def test_reference_video_analysis_pipeline_is_listed_and_uses_existing_analysis_tools():
    manifest = load_pipeline("reference-video-analysis")
    tools = get_required_tools(manifest)

    assert "reference-video-analysis" in list_pipelines()
    assert "video_downloader" in tools
    assert "custom_asset_import" in tools
    assert "scene_detect" in tools
    assert "frame_sampler" in tools
    assert "transcriber" in tools
    assert "reference_video_package" in tools
    assert "reference_prompt_reverse" in tools
    assert "reference_text_edit" in tools
    assert "reference_asset_binding" in tools
    assert "reference_review_approval" in tools
    assert "reference_production_plan" in tools
    assert "seedance_batch" in tools


def test_reference_video_analysis_required_skills_exist():
    manifest = load_pipeline("reference-video-analysis")
    root = Path(__file__).resolve().parent.parent.parent

    for skill_ref in manifest.get("required_skills", []):
        assert (root / "skills" / f"{skill_ref}.md").is_file(), skill_ref
