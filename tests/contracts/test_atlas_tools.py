"""Contract and exact-schema tests for the Atlas Cloud media gateway."""

from pathlib import Path

import pytest

from tools import atlas_client
from tools.atlas_models import IMAGE_MODELS, VIDEO_MODELS
from tools.base_tool import BaseTool, ExecutionMode, ToolRuntime, ToolStability, ToolStatus, ToolTier
from tools.graphics.atlas_image import AtlasImage
from tools.graphics.image_selector import ImageSelector
from tools.video.atlas_video import AtlasVideo
from tools.video.video_selector import VideoSelector

TOOLS = [AtlasImage, AtlasVideo]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _clear_atlas_env(monkeypatch):
    for key in atlas_client.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("cls", TOOLS, ids=lambda cls: cls.name)
class TestContract:
    def test_contract_identity(self, cls):
        tool = cls()
        assert issubclass(cls, BaseTool)
        assert tool.provider == "atlascloud"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.API
        assert tool.execution_mode == ExecutionMode.SYNC
        assert "prompt" in tool.input_schema["required"]
        assert "atlas-cloud" in tool.agent_skills
        assert "env:ATLASCLOUD_API_KEY" in tool.dependencies

    def test_status_and_key_aliases(self, cls, monkeypatch):
        assert cls().get_status() == ToolStatus.UNAVAILABLE
        for key in atlas_client.ENV_KEYS:
            monkeypatch.setenv(key, "test")
            assert cls().get_status() == ToolStatus.AVAILABLE
            monkeypatch.delenv(key)

    def test_no_key_fails_before_network(self, cls):
        result = cls().execute({"prompt": "test"})
        assert not result.success
        assert "ATLASCLOUD_API_KEY" in result.error

    def test_discovery_metadata_contains_catalog(self, cls):
        info = cls().get_info()
        assert info["model_catalog"]
        assert info["provider_matrix"]


def test_layer3_skill_exists():
    skill = PROJECT_ROOT / ".agents" / "skills" / "atlas-cloud" / "SKILL.md"
    assert skill.exists()
    assert "ATLASCLOUD_API_KEY" in skill.read_text(encoding="utf-8")


def test_registry_discovers_atlas_tools(isolated_tool_registry):
    isolated_tool_registry.discover()
    assert isolated_tool_registry.get("atlas_image") is not None
    assert isolated_tool_registry.get("atlas_video") is not None


def test_exact_atlas_model_pins_video_selector_candidate():
    atlas = AtlasVideo()
    unrelated = type("Unrelated", (), {
        "input_schema": {"properties": {"model": {"enum": ["vendor/other"]}}},
        "get_info": lambda self: {},
        "supports": {"text_to_video": True},
        "is_operation_available": lambda self, operation: True,
    })()
    filtered = VideoSelector()._filter_candidates(
        {"model": "minimax/h3/text-to-video", "operation": "text_to_video"},
        [unrelated, atlas],
    )
    assert filtered == [atlas]


def test_exact_atlas_model_pins_image_selector_candidate():
    atlas = AtlasImage()
    unrelated = type("Unrelated", (), {
        "input_schema": {"properties": {"model": {"enum": ["vendor/other"]}}},
        "get_info": lambda self: {},
        "supports": {},
    })()
    filtered = ImageSelector()._filter_candidates(
        {"model": "openai/gpt-image-2/text-to-image"},
        [unrelated, atlas],
    )
    assert filtered == [atlas]


class TestVideoRoutes:
    @pytest.mark.parametrize(
        "family,operations",
        [
            ("bytedance/seedance-2.5", {"text_to_video", "image_to_video", "reference_to_video"}),
            ("bytedance/seedance-2.0", {"text_to_video", "image_to_video", "reference_to_video"}),
            ("minimax/h3", {"text_to_video", "image_to_video", "reference_to_video"}),
            ("google/gemini-omni-flash", {"text_to_video", "image_to_video", "reference_to_video", "video_edit"}),
        ],
    )
    def test_family_operations_are_discoverable(self, family, operations):
        assert operations <= set(AtlasVideo.provider_matrix[family])

    def test_exact_live_catalog(self):
        assert len(VIDEO_MODELS) == 16
        assert "minimax/h3/reference-to-video" in VIDEO_MODELS
        assert "google/gemini-omni-flash/video-edit" in VIDEO_MODELS

    def test_seedance_25_payload(self):
        payload = AtlasVideo()._build_payload(
            {"prompt": "p", "duration": 10, "aspect_ratio": "21:9", "resolution": "720p", "generate_audio": True},
            "bytedance/seedance-2.5/text-to-video",
        )
        assert payload == {
            "model": "bytedance/seedance-2.5/text-to-video", "prompt": "p", "duration": 10,
            "ratio": "21:9", "resolution": "720p", "generate_audio": True,
        }

    def test_seedance_i2v_uses_image_and_last_image(self):
        payload = AtlasVideo()._build_payload(
            {"prompt": "p", "duration": 10, "resolution": "720p", "image_url": "https://x/a.png", "last_image_url": "https://x/b.png"},
            "bytedance/seedance-2.5/image-to-video",
        )
        assert payload["image"] == "https://x/a.png"
        assert payload["last_image"] == "https://x/b.png"
        assert "image_url" not in payload

    def test_seedance_25_accepts_audio_only_and_30_images(self):
        tool = AtlasVideo()
        audio = tool._build_payload(
            {"prompt": "cut to the beat", "duration": 10, "reference_audios": ["https://x/beat.mp3"]},
            "bytedance/seedance-2.5/reference-to-video",
        )
        assert audio["reference_audios"] == ["https://x/beat.mp3"]
        payload = tool._build_payload(
            {"prompt": "p", "duration": 10, "reference_images": [f"https://x/{i}.png" for i in range(30)]},
            "bytedance/seedance-2.5/reference-to-video",
        )
        assert len(payload["reference_images"]) == 30

    def test_gemini_standard_and_developer_have_distinct_schemas(self):
        standard = AtlasVideo()._build_payload(
            {"prompt": "p", "duration": 10, "reference_images": ["https://x/a.png"]},
            "google/gemini-omni-flash/reference-to-video",
        )
        developer = AtlasVideo()._build_payload(
            {"prompt": "p", "duration": 10, "video_url": "https://x/a.mp4"},
            "google/gemini-omni-flash/reference-to-video-developer",
        )
        assert standard["images"] == ["https://x/a.png"]
        assert developer["video_clips"] == [{"url": "https://x/a.mp4", "start": 0, "ends": 10}]

    def test_gemini_video_edit_uses_video(self):
        payload = AtlasVideo()._build_payload(
            {"prompt": "make it dusk", "video_url": "https://x/a.mp4"},
            "google/gemini-omni-flash/video-edit",
        )
        assert payload["video"] == "https://x/a.mp4"
        assert "duration" not in payload and "aspect_ratio" not in payload

    def test_h3_refers_objects(self):
        payload = AtlasVideo()._build_payload(
            {"prompt": "p", "duration": 10, "resolution": "2K", "reference_images": ["https://x/a.png"], "reference_audios": ["https://x/a.mp3"]},
            "minimax/h3/reference-to-video",
        )
        assert payload["refers"] == [
            {"url": "https://x/a.png", "type": "image"},
            {"url": "https://x/a.mp3", "type": "audio"},
        ]

    def test_h3_i2v_uses_end_image(self):
        payload = AtlasVideo()._build_payload(
            {"prompt": "p", "duration": 10, "resolution": "2K", "image_url": "https://x/a.png", "end_image_url": "https://x/b.png"},
            "minimax/h3/image-to-video",
        )
        assert payload["image"] == "https://x/a.png"
        assert payload["end_image"] == "https://x/b.png"

    def test_invalid_route_and_enum_fail_loudly(self):
        tool = AtlasVideo()
        with pytest.raises(ValueError, match="does not expose"):
            tool._resolve_model("minimax/h3/text-to-video", "video_edit")
        with pytest.raises(ValueError, match="duration"):
            tool._build_payload({"prompt": "p", "duration": 30}, "minimax/h3/text-to-video")

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("bytedance/seedance-2.5/text-to-video", 1.34),
            ("bytedance/seedance-2.0/text-to-video", 1.12),
            ("google/gemini-omni-flash/text-to-video", 1.25),
            ("google/gemini-omni-flash/text-to-video-developer", 1.12),
            ("minimax/h3/text-to-video", 1.00),
        ],
    )
    def test_verified_costs(self, model, expected):
        assert AtlasVideo().estimate_cost({"model": model, "duration": 10}) == pytest.approx(expected)


class TestImageRoutes:
    def test_exact_live_catalog(self):
        assert set(IMAGE_MODELS) == {
            "bytedance/seedream-v5.0-pro/text-to-image", "bytedance/seedream-v5.0-pro/edit",
            "bytedance/seedream-v5.0-pro/layer-decomposition", "bytedance/seedream-v5.0-lite/edit",
            "openai/gpt-image-2/text-to-image", "openai/gpt-image-2/edit",
            "google/nano-banana-2/text-to-image", "google/nano-banana-2/edit",
        }

    def test_seedream_uses_star_size_and_images(self):
        tool = AtlasImage()
        generated = tool._build_payload({"prompt": "p", "width": 2048, "height": 1152}, "bytedance/seedream-v5.0-pro/text-to-image")
        edited = tool._build_payload({"prompt": "p", "width": 2048, "height": 1152, "image_urls": ["https://x/a.png"]}, "bytedance/seedream-v5.0-pro/edit")
        assert generated["size"] == "2048*1152"
        assert edited["images"] == ["https://x/a.png"]

    def test_gpt_image_uses_x_size(self):
        payload = AtlasImage()._build_payload({"prompt": "p", "width": 1536, "height": 1024}, "openai/gpt-image-2/text-to-image")
        assert payload["size"] == "1536x1024"
        assert "aspect_ratio" not in payload

    def test_nano_banana_uses_ratio_and_resolution(self):
        payload = AtlasImage()._build_payload(
            {"prompt": "p", "width": 1920, "height": 1080, "resolution": "2k", "thinking_level": "high"},
            "google/nano-banana-2/text-to-image",
        )
        assert payload["aspect_ratio"] == "16:9"
        assert payload["resolution"] == "2k"
        assert payload["thinking_level"] == "high"

    def test_decomposition_requires_one_image(self):
        with pytest.raises(ValueError, match="exactly one"):
            AtlasImage()._build_payload({"prompt": ""}, "bytedance/seedream-v5.0-pro/layer-decomposition")

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("bytedance/seedream-v5.0-pro/text-to-image", 0.045),
            ("openai/gpt-image-2/text-to-image", 0.009),
            ("google/nano-banana-2/text-to-image", 0.080),
        ],
    )
    def test_verified_costs(self, model, expected):
        assert AtlasImage().estimate_cost({"model": model}) == pytest.approx(expected)
