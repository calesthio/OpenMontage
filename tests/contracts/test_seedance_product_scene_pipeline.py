"""Contract tests for the Seedance product-scene pipeline manifest."""

from __future__ import annotations

from pathlib import Path

from lib.pipeline_loader import get_stage_order, load_pipeline


def test_manifest_stage_order_and_approval_gates():
    manifest = load_pipeline("seedance-product-scene")

    assert get_stage_order(manifest) == [
        "idea",
        "proposal",
        "style_preview",
        "scene_plan",
        "assets",
        "video_assets",
        "copy",
        "music",
        "compose",
        "publish",
    ]
    gates = {
        stage["name"]: stage.get("human_approval_default", False)
        for stage in manifest["stages"]
    }
    assert gates == {
        "idea": True,
        "proposal": True,
        "style_preview": True,
        "scene_plan": True,
        "assets": True,
        "video_assets": True,
        "copy": True,
        "music": True,
        "compose": False,
        "publish": True,
    }


def test_manifest_tools_follow_ark_and_ffmpeg_boundaries():
    manifest = load_pipeline("seedance-product-scene")
    stages = {stage["name"]: stage for stage in manifest["stages"]}

    assert "seedream_ark_image" in stages["style_preview"]["required_tools"]
    assert "seedream_ark_image" in stages["assets"]["required_tools"]
    assert "seedance_ark" in stages["video_assets"]["required_tools"]
    assert "pixabay_music" in stages["music"]["required_tools"]
    assert "audio_mixer" in stages["compose"]["required_tools"]
    assert "video_compose" in stages["compose"]["required_tools"]


def test_manifest_persists_required_artifacts_and_product_choices():
    manifest = load_pipeline("seedance-product-scene")
    stages = {stage["name"]: stage for stage in manifest["stages"]}

    assert stages["idea"]["produces"] == ["brief"]
    assert "proposal_packet" in stages["proposal"]["produces"]
    assert stages["style_preview"]["produces"] == ["asset_manifest"]
    assert stages["scene_plan"]["produces"] == ["scene_plan"]
    assert stages["assets"]["produces"] == ["asset_manifest"]
    assert stages["video_assets"]["produces"] == ["asset_manifest"]
    assert stages["copy"]["produces"] == ["product_copy"]
    assert "product_delivery" in stages["music"]["produces"]
    assert "render_report" in stages["compose"]["produces"]
    assert "final_review" in stages["compose"]["produces"]
    assert "publish_log" in stages["publish"]["produces"]

    assert manifest["metadata"]["text_generation"] == "codex_active_session"
    assert manifest["metadata"]["image_generation"] == "ark_seedream"
    assert manifest["metadata"]["video_generation"] == "ark_seedance"
    assert manifest["metadata"]["motion_required"] is True
    assert manifest["metadata"]["default_duration_seconds"] == 8
    assert manifest["metadata"]["default_ratio"] == "9:16"
    assert manifest["metadata"]["default_resolution"] == "720p"
    assert manifest["metadata"]["storyboard"] == "three_shot"
    assert manifest["metadata"]["burned_text"] is False


def test_manifest_proposal_requires_style_and_cost_approval():
    manifest = load_pipeline("seedance-product-scene")
    proposal = next(
        stage for stage in manifest["stages"] if stage["name"] == "proposal"
    )
    review_focus = " ".join(proposal["review_focus"])

    assert "1–3" in review_focus
    assert "成本" in review_focus
    assert "音乐" in review_focus
    assert "文案" in review_focus


def test_music_compose_and_delivery_chain_is_explicit():
    manifest = load_pipeline("seedance-product-scene")
    stages = {stage["name"]: stage for stage in manifest["stages"]}

    assert stages["music"]["required_artifacts_in"] == [
        "asset_manifest",
        "product_copy",
    ]
    assert stages["music"]["produces"] == ["product_delivery"]
    assert stages["compose"]["required_tools"] == [
        "audio_mixer",
        "video_compose",
    ]
    assert stages["compose"]["produces"] == ["render_report", "final_review"]
    assert "product_delivery" in stages["publish"]["required_artifacts_in"]
    assert "publish_log" in stages["publish"]["produces"]


def test_video_skill_requires_user_confirmed_seedance_25_price():
    body = Path(
        "skills/pipelines/seedance-product-scene/video-director.md"
    ).read_text(encoding="utf-8")

    assert "custom_price_cny_per_million_tokens" in body
    assert "报价" in body
    assert "停止" in body
