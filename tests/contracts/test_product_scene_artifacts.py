"""Schema tests for product copy and final delivery artifacts."""

from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from schemas.artifacts import ARTIFACT_NAMES, validate_artifact


def _copy_variants():
    return {
        "grassroots": {
            "title": "这瓶精华，把日常仪式感拉满",
            "subtitle": "清透质地，轻松融入每日护肤",
            "highlights": [
                "轻盈质地，使用感清爽",
                "适合日常护肤步骤",
                "包装简洁，方便收纳",
            ],
            "social_copy": "今天也要认真照顾自己，日常护肤从这一步开始。",
        },
        "premium": {
            "title": "克制而精致的选择",
            "subtitle": "为简洁生活方式而设计",
            "highlights": [
                "极简视觉语言",
                "贴合现代居家空间",
                "注重每一次使用体验",
            ],
            "social_copy": "真正的高级感，来自恰到好处的细节。",
        },
        "conversion": {
            "title": "日常护肤，选对这一步",
            "subtitle": "了解卖点、适用场景与使用方法",
            "highlights": [
                "产品信息清晰",
                "使用步骤简单",
                "适合作为日常护理选择",
                "购买前可确认规格信息",
            ],
            "social_copy": "想升级日常护肤流程，可以从这款产品开始了解。",
        },
    }


def _product_copy():
    return {
        "version": "1.0",
        "product_name": "精华液",
        "generation_source": "codex_active_session",
        "assumptions": [],
        "styles": [
            {
                "style": "luxury",
                "variants": _copy_variants(),
            }
        ],
    }


def _product_delivery():
    return {
        "version": "1.0",
        "product_name": "精华液",
        "selected_styles": ["luxury"],
        "packages": [
            {
                "style": "luxury",
                "images": [
                    {
                        "path": "assets/images/luxury/scene_luxury_1.png",
                        "candidate_index": 1,
                        "approved": False,
                    },
                    {
                        "path": "assets/images/luxury/scene_luxury_2.png",
                        "candidate_index": 2,
                        "approved": True,
                    },
                ],
                "selected_image": {
                    "path": "assets/images/luxury/scene_luxury_2.png",
                    "candidate_index": 2,
                    "approved": True,
                },
                "video": {
                    "path": "assets/video/luxury/source.mp4",
                    "task_id": "cgt-test-123",
                    "model": "doubao-seedance-2-5-260628",
                    "duration_seconds": 8,
                    "ratio": "9:16",
                    "resolution": "720p",
                    "approved": True,
                },
                "music": {
                    "path": "assets/music/luxury/selected.mp3",
                    "title": "Quiet Product Reveal",
                    "artist": "Example Artist",
                    "license": "Pixabay Content License",
                    "approved": True,
                },
                "music_candidates": [
                    {
                        "index": 1,
                        "title": "Quiet Product Reveal",
                        "artist": "Example Artist",
                        "duration_seconds": 34,
                        "license": "Pixabay Content License",
                        "download_url": "https://cdn.pixabay.com/audio/one.mp3",
                    },
                    {
                        "index": 2,
                        "title": "Soft Luxury Motion",
                        "artist": "Example Artist",
                        "duration_seconds": 45,
                        "license": "Pixabay Content License",
                        "download_url": "https://cdn.pixabay.com/audio/two.mp3",
                    },
                    {
                        "index": 3,
                        "title": "Elegant Brand Bed",
                        "artist": "Example Artist",
                        "duration_seconds": 52,
                        "license": "Pixabay Content License",
                        "download_url": "https://cdn.pixabay.com/audio/three.mp3",
                    },
                ],
                "copy": {
                    "path": "artifacts/product_copy.json",
                    "style": "luxury",
                },
                "output": {
                    "video_path": "renders/luxury/final.mp4",
                    "copy_path": "artifacts/product_copy.json",
                },
            }
        ],
        "approvals": {
            "proposal": True,
            "style_selection": True,
            "images": True,
            "videos": True,
            "copy": True,
            "music": True,
            "delivery": False,
        },
        "total_estimated_cost_usd": None,
    }


def test_product_scene_schemas_are_registered():
    assert "product_copy" in ARTIFACT_NAMES
    assert "product_delivery" in ARTIFACT_NAMES


def test_valid_product_copy_and_delivery_validate():
    validate_artifact("product_copy", _product_copy())
    validate_artifact("product_delivery", _product_delivery())


def test_product_copy_requires_product_name():
    artifact = _product_copy()
    artifact.pop("product_name")

    with pytest.raises(ValidationError):
        validate_artifact("product_copy", artifact)


def test_product_copy_rejects_unknown_variant():
    artifact = _product_copy()
    artifact["styles"][0]["variants"]["promotional"] = copy.deepcopy(
        artifact["styles"][0]["variants"]["grassroots"]
    )

    with pytest.raises(ValidationError):
        validate_artifact("product_copy", artifact)


def test_product_delivery_rejects_unlicensed_music():
    artifact = _product_delivery()
    artifact["packages"][0]["music"].pop("license")

    with pytest.raises(ValidationError):
        validate_artifact("product_delivery", artifact)


def test_product_delivery_rejects_video_without_selected_image():
    artifact = _product_delivery()
    artifact["packages"][0].pop("selected_image")

    with pytest.raises(ValidationError):
        validate_artifact("product_delivery", artifact)


def test_product_delivery_requires_three_music_candidates():
    artifact = _product_delivery()
    artifact["packages"][0].pop("music_candidates")

    with pytest.raises(ValidationError):
        validate_artifact("product_delivery", artifact)
