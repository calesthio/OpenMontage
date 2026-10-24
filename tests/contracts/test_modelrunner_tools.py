"""Contract and exact-schema tests for the ModelRunner media gateway."""

import ast
import inspect
from pathlib import Path

import pytest

from tools import modelrunner_client
from tools.modelrunner_models import (
    IMAGE_MODELS,
    MUSIC_MODELS,
    TTS_MODELS,
    VIDEO_MODELS,
)
from tools.base_tool import BaseTool, ExecutionMode, ToolRuntime, ToolStability, ToolStatus, ToolTier
from tools.audio.modelrunner_music import ModelRunnerMusic
from tools.audio.modelrunner_tts import ModelRunnerTTS
from tools.graphics.image_selector import ImageSelector
from tools.graphics.modelrunner_image import ModelRunnerImage
from tools.video.modelrunner_video import ModelRunnerVideo
from tools.video.video_selector import VideoSelector

TOOLS = [ModelRunnerImage, ModelRunnerVideo, ModelRunnerTTS, ModelRunnerMusic]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _clear_modelrunner_env(monkeypatch):
    for key in modelrunner_client.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("cls", TOOLS, ids=lambda cls: cls.name)
class TestContract:
    def test_contract_identity(self, cls):
        tool = cls()
        assert issubclass(cls, BaseTool)
        assert tool.provider == "modelrunner"
        expected_tier = ToolTier.VOICE if cls is ModelRunnerTTS else ToolTier.GENERATE
        assert tool.tier == expected_tier
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.API
        assert tool.execution_mode == ExecutionMode.SYNC
        primary_input = "text" if cls is ModelRunnerTTS else "prompt"
        assert primary_input in tool.input_schema["required"]
        assert "modelrunner" in tool.agent_skills
        assert "env:MODELRUNNER_KEY" in tool.dependencies

    def test_status_and_key_aliases(self, cls, monkeypatch):
        assert cls().get_status() == ToolStatus.UNAVAILABLE
        for key in modelrunner_client.ENV_KEYS:
            monkeypatch.setenv(key, "test")
            assert cls().get_status() == ToolStatus.AVAILABLE
            monkeypatch.delenv(key)

    def test_no_key_fails_before_network(self, cls):
        result = cls().execute({"prompt": "test", "text": "test"})
        assert not result.success
        assert "MODELRUNNER_KEY" in result.error
        assert result.cost_usd == 0.0

    def test_discovery_metadata_contains_catalog(self, cls):
        info = cls().get_info()
        assert info["model_catalog"]
        assert info["pricing_snapshot"]

    def test_side_effects_and_verification(self, cls):
        tool = cls()
        assert any("API" in effect for effect in tool.side_effects)
        assert tool.user_visible_verification
        assert tool.idempotency_key_fields
        assert tool.fallback_tools

    def test_lazy_imports_requests(self, cls):
        """No top-level `import requests` — registry discovery must stay fast."""
        for module_path in (
            Path(inspect.getfile(cls)),
            PROJECT_ROOT / "tools" / "modelrunner_client.py",
        ):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            top_level_imports = {
                alias.name
                for node in tree.body
                if isinstance(node, ast.Import)
                for alias in node.names
            } | {
                node.module
                for node in tree.body
                if isinstance(node, ast.ImportFrom) and node.module
            }
            assert "requests" not in top_level_imports, f"{module_path} imports requests at module level"

    def test_estimate_cost_never_raises(self, cls):
        tool = cls()
        for inputs in ({}, {"model": "not/a/real/route"}, {"duration": "oops"}):
            cost = tool.estimate_cost(inputs)
            assert isinstance(cost, float)
            assert cost >= 0


def test_layer3_skill_exists():
    skill = PROJECT_ROOT / ".agents" / "skills" / "modelrunner" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    for env_key in modelrunner_client.ENV_KEYS:
        assert env_key in text


def test_registry_discovers_modelrunner_tools(isolated_tool_registry):
    isolated_tool_registry.discover()
    for name in ("modelrunner_image", "modelrunner_video", "modelrunner_tts", "modelrunner_music"):
        assert isolated_tool_registry.get(name) is not None


def test_exact_model_pins_video_selector_candidate():
    tool = ModelRunnerVideo()
    unrelated = type("Unrelated", (), {
        "input_schema": {"properties": {"model": {"enum": ["vendor/other"]}}},
        "get_info": lambda self: {},
        "supports": {"text_to_video": True},
        "is_operation_available": lambda self, operation: True,
    })()
    filtered = VideoSelector()._filter_candidates(
        {"model": "alibaba/happy-horse/v1.1/text-to-video", "operation": "text_to_video"},
        [unrelated, tool],
    )
    assert filtered == [tool]


def test_exact_model_pins_image_selector_candidate():
    tool = ModelRunnerImage()
    unrelated = type("Unrelated", (), {
        "input_schema": {"properties": {"model": {"enum": ["vendor/other"]}}},
        "get_info": lambda self: {},
        "supports": {},
    })()
    filtered = ImageSelector()._filter_candidates(
        {"model": "bytedance/seedream-v5/text-to-image"},
        [unrelated, tool],
    )
    assert filtered == [tool]


def test_video_schema_hides_image_url_so_selector_keeps_local_paths():
    """The video_selector fal-uploads local references for tools that
    advertise `image_url`. This tool hosts local media itself via ModelRunner
    storage (the seedance_ark convention), so the schema must expose only the
    canonical reference keys — a ModelRunner-only machine (no FAL_KEY) must be
    able to run image_to_video through the selector, and a local image must
    never leave for a third-party host.
    """
    props = ModelRunnerVideo.input_schema["properties"]
    assert "image_url" not in props
    assert "reference_image_path" in props
    assert "reference_image_url" in props


class TestDefaultsAreConsistent:
    """The module default, the schema default, and the no-input estimate agree."""

    @pytest.mark.parametrize(
        "cls,catalog",
        [
            (ModelRunnerVideo, VIDEO_MODELS),
            (ModelRunnerImage, IMAGE_MODELS),
            (ModelRunnerTTS, TTS_MODELS),
            (ModelRunnerMusic, MUSIC_MODELS),
        ],
        ids=lambda value: getattr(value, "name", "catalog"),
    )
    def test_schema_default_model_is_in_catalog(self, cls, catalog):
        schema_default = cls.input_schema["properties"]["model"]["default"]
        assert schema_default in catalog
        # The enum lists every exact endpoint id, plus (for tools with
        # friendly aliases) each documented alias — and nothing else.
        module = inspect.getmodule(cls)
        aliases = getattr(module, "_MODEL_ALIASES", {})
        enum = set(cls.input_schema["properties"]["model"]["enum"])
        assert enum == set(catalog) | set(aliases)
        assert all(target in catalog for target in aliases.values())

    def test_video_default_estimate_matches_default_route(self):
        # wan 2.7 t2v at the tool's 720P/5s defaults: 0.10 * 5
        assert ModelRunnerVideo().estimate_cost({}) == pytest.approx(0.50)

    def test_tts_default_estimate_uses_kokoro(self):
        cost = ModelRunnerTTS().estimate_cost({"text": "x" * 150})
        assert 0 < cost < 0.01  # Kokoro bills compute time: a fraction of a cent

    def test_music_default_estimate_uses_lyria2(self):
        assert ModelRunnerMusic().estimate_cost({"prompt": "p"}) == pytest.approx(0.06)


class TestVideoRoutes:
    def test_exact_live_catalog(self):
        assert set(VIDEO_MODELS) == {
            "wan-video/wan/v2.7/text-to-video",
            "wan-video/wan/v2.7/image-to-video",
            "alibaba/happy-horse/v1.1/text-to-video",
            "bytedance/seedance-v2-mini/text-to-video",
            "bytedance/seedance-v2-mini/image-to-video",
        }

    def test_operation_rerouted_within_family(self):
        tool = ModelRunnerVideo()
        resolved = tool._resolve_model("wan-video/wan/v2.7/text-to-video", "image_to_video")
        assert resolved == "wan-video/wan/v2.7/image-to-video"
        with pytest.raises(ValueError, match="does not expose"):
            tool._resolve_model("alibaba/happy-horse/v1.1/text-to-video", "image_to_video")

    def test_wan_t2v_payload(self):
        payload = ModelRunnerVideo()._build_payload(
            {"prompt": "p", "duration": 8, "resolution": "1080P", "aspect_ratio": "9:16", "seed": 7},
            "wan-video/wan/v2.7/text-to-video",
        )
        assert payload == {
            "prompt": "p", "duration": 8, "resolution": "1080P", "aspect_ratio": "9:16", "seed": 7,
        }

    def test_wan_i2v_uses_start_and_end_image_and_no_ratio(self):
        payload = ModelRunnerVideo()._build_payload(
            {
                "prompt": "p", "duration": 5, "image_url": "https://x/a.png",
                "end_image_url": "https://x/b.png", "aspect_ratio": "16:9",
            },
            "wan-video/wan/v2.7/image-to-video",
        )
        assert payload["start_image_url"] == "https://x/a.png"
        assert payload["end_image_url"] == "https://x/b.png"
        assert "aspect_ratio" not in payload and "ratio" not in payload

    def test_wan_i2v_prompt_is_optional(self):
        payload = ModelRunnerVideo()._build_payload(
            {"duration": 5, "image_url": "https://x/a.png"},
            "wan-video/wan/v2.7/image-to-video",
        )
        assert "prompt" not in payload

    def test_happy_horse_uses_ratio_key(self):
        payload = ModelRunnerVideo()._build_payload(
            {"prompt": "p", "duration": 5, "resolution": "720P", "aspect_ratio": "21:9"},
            "alibaba/happy-horse/v1.1/text-to-video",
        )
        assert payload["ratio"] == "21:9"
        assert "aspect_ratio" not in payload

    def test_seedance_i2v_requires_prompt_and_defaults_adaptive(self):
        tool = ModelRunnerVideo()
        payload = tool._build_payload(
            {"prompt": "p", "duration": 5, "image_url": "https://x/a.png"},
            "bytedance/seedance-v2-mini/image-to-video",
        )
        assert payload["image"] == "https://x/a.png"
        assert payload["aspect_ratio"] == "adaptive"
        with pytest.raises(ValueError, match="prompt"):
            tool._build_payload(
                {"duration": 5, "image_url": "https://x/a.png"},
                "bytedance/seedance-v2-mini/image-to-video",
            )

    def test_invalid_enum_and_range_fail_loudly(self):
        tool = ModelRunnerVideo()
        with pytest.raises(ValueError, match="duration"):
            tool._build_payload({"prompt": "p", "duration": 30}, "wan-video/wan/v2.7/text-to-video")
        with pytest.raises(ValueError, match="resolution"):
            tool._build_payload(
                {"prompt": "p", "duration": 5, "resolution": "4K"},
                "wan-video/wan/v2.7/text-to-video",
            )
        with pytest.raises(ValueError, match="end_image_url"):
            tool._build_payload(
                {"prompt": "p", "duration": 5, "image_url": "https://x/a.png", "end_image_url": "https://x/b.png"},
                "bytedance/seedance-v2-mini/image-to-video",
            )
        with pytest.raises(ValueError, match="text-to-video route"):
            tool._build_payload(
                {"prompt": "p", "duration": 5, "image_url": "https://x/a.png"},
                "alibaba/happy-horse/v1.1/text-to-video",
            )

    @pytest.mark.parametrize(
        "inputs,expected",
        [
            ({"model": "wan-video/wan/v2.7/text-to-video", "duration": 5}, 0.50),
            ({"model": "wan-video/wan/v2.7/text-to-video", "duration": 10, "resolution": "1080P"}, 1.50),
            ({"model": "alibaba/happy-horse/v1.1/text-to-video", "duration": 5, "resolution": "720P"}, 0.70),
            ({"model": "alibaba/happy-horse/v1.1/text-to-video", "duration": 5, "resolution": "1080P"}, 0.90),
            ({"model": "bytedance/seedance-v2-mini/text-to-video", "duration": 10, "resolution": "480p"}, 0.53),
            ({"model": "bytedance/seedance-v2-mini/text-to-video", "duration": 10, "resolution": "720p"}, 1.13),
        ],
    )
    def test_verified_resolution_tiered_costs(self, inputs, expected):
        assert ModelRunnerVideo().estimate_cost(inputs) == pytest.approx(expected)


class TestImageRoutes:
    def test_exact_live_catalog(self):
        assert set(IMAGE_MODELS) == {
            "bytedance/seedream-v5/text-to-image",
            "bytedance/seedream-v5-pro/text-to-image",
            "recraft/v4.1/text-to-image",
            "recraft/v4.1/pro/text-to-image",
            "stability-ai/stable-diffusion-v3.5-large",
        }

    def test_seedream_exact_size_is_validated_strictly(self):
        tool = ModelRunnerImage()
        payload = tool._build_payload(
            {"prompt": "p", "size": "2752x1536"}, "bytedance/seedream-v5/text-to-image"
        )
        assert payload["size"] == "2752x1536"
        with pytest.raises(ValueError, match="size"):
            tool._build_payload(
                {"prompt": "p", "size": "1920x1080"}, "bytedance/seedream-v5/text-to-image"
            )

    def test_seedream_canonical_dims_snap_to_closest_size(self):
        payload = ModelRunnerImage()._build_payload(
            {"prompt": "p", "width": 1920, "height": 1080}, "bytedance/seedream-v5/text-to-image"
        )
        assert payload["size"] == "2752x1536"  # closest 16:9-ish 2K canvas

    def test_recraft_accepts_preset_and_custom_dims(self):
        tool = ModelRunnerImage()
        preset = tool._build_payload(
            {"prompt": "p", "image_size": "landscape_16_9"}, "recraft/v4.1/text-to-image"
        )
        custom = tool._build_payload(
            {"prompt": "p", "width": 2048, "height": 1024}, "recraft/v4.1/text-to-image"
        )
        assert preset["image_size"] == "landscape_16_9"
        assert custom["image_size"] == {"width": 2048, "height": 1024}
        with pytest.raises(ValueError, match="out of range"):
            tool._build_payload(
                {"prompt": "p", "width": 4096, "height": 4096}, "recraft/v4.1/text-to-image"
            )
        with pytest.raises(ValueError, match="preset"):
            tool._build_payload(
                {"prompt": "p", "image_size": "cinema_scope"}, "recraft/v4.1/text-to-image"
            )

    def test_sd35_passes_generation_controls_through(self):
        payload = ModelRunnerImage()._build_payload(
            {
                "prompt": "p", "image_size": "landscape_4_3", "negative_prompt": "blurry",
                "guidance_scale": 5.0, "num_inference_steps": 40, "seed": 3,
            },
            "stability-ai/stable-diffusion-v3.5-large",
        )
        assert payload["negative_prompt"] == "blurry"
        assert payload["guidance_scale"] == 5.0
        assert payload["num_inference_steps"] == 40
        assert payload["seed"] == 3

    @pytest.mark.parametrize(
        "inputs,expected",
        [
            ({"model": "bytedance/seedream-v5/text-to-image"}, 0.035),
            ({"model": "bytedance/seedream-v5-pro/text-to-image"}, 0.045),  # default 1024x1024
            ({"model": "bytedance/seedream-v5-pro/text-to-image", "size": "2048x2048"}, 0.09),
            ({"model": "recraft/v4.1/text-to-image"}, 0.035),
            ({"model": "recraft/v4.1/pro/text-to-image"}, 0.21),
            # SD 3.5 bills per output megapixel: 1024x768 = 0.786MP * $0.065
            ({"model": "stability-ai/stable-diffusion-v3.5-large", "width": 1024, "height": 768}, 0.0511),
        ],
    )
    def test_verified_costs(self, inputs, expected):
        assert ModelRunnerImage().estimate_cost(inputs) == pytest.approx(expected, abs=1e-3)


class TestTTSRoutes:
    def test_exact_live_catalog(self):
        assert set(TTS_MODELS) == {
            "hexgrad/kokoro-82m",
            "google/gemini-3.1-flash-tts",
            "elevenlabs/tts/multilingual-v2",
            "resemble-ai/chatterbox/text-to-speech/multilingual",
        }

    def test_selector_style_model_id_aliases_resolve(self):
        tool = ModelRunnerTTS()
        assert tool._resolve_model({"model_id": "eleven_multilingual_v2"}) == "elevenlabs/tts/multilingual-v2"
        assert tool._resolve_model({"model_id": "kokoro"}) == "hexgrad/kokoro-82m"
        assert tool._resolve_model({}) == "hexgrad/kokoro-82m"
        with pytest.raises(ValueError, match="Unsupported"):
            tool._resolve_model({"model": "vendor/other-tts"})

    def test_kokoro_payload_uses_text_and_voice(self):
        payload = ModelRunnerTTS()._build_payload(
            {"text": "hello", "voice_id": "ff_siwis", "speed": 1.2}, "hexgrad/kokoro-82m"
        )
        assert payload == {"text": "hello", "voice": "ff_siwis", "speed": 1.2}

    def test_gemini_combines_instructions_into_prompt(self):
        tool = ModelRunnerTTS()
        directed = tool._build_payload(
            {"text": "hello there", "instructions": "Say the following in a whisper", "voice": "Puck"},
            "google/gemini-3.1-flash-tts",
        )
        plain = tool._build_payload({"text": "hello there"}, "google/gemini-3.1-flash-tts")
        assert directed["prompt"] == "Say the following in a whisper: hello there"
        assert directed["voice"] == "Puck"
        assert plain["prompt"] == "hello there"
        assert "text" not in directed

    def test_chatterbox_maps_language_code_and_caps_length(self):
        tool = ModelRunnerTTS()
        payload = tool._build_payload(
            {"text": "bonjour", "language_code": "fr"},
            "resemble-ai/chatterbox/text-to-speech/multilingual",
        )
        assert payload["voice"] == "french"
        with pytest.raises(ValueError, match="300"):
            tool._build_payload(
                {"text": "x" * 301}, "resemble-ai/chatterbox/text-to-speech/multilingual"
            )

    def test_elevenlabs_speed_range_fails_loudly(self):
        tool = ModelRunnerTTS()
        with pytest.raises(ValueError, match="speed"):
            tool._build_payload(
                {"text": "hello", "speed": 2.0}, "elevenlabs/tts/multilingual-v2"
            )

    def test_per_audio_second_estimates(self):
        # 150 chars ~= 10s of speech
        tool = ModelRunnerTTS()
        text = "x" * 150
        assert tool.estimate_cost({"text": text, "model_id": "multilingual-v2"}) == pytest.approx(0.015)
        assert tool.estimate_cost({"text": text, "model_id": "gemini-tts"}) == pytest.approx(0.006)
        assert tool.estimate_cost({"text": text, "model_id": "chatterbox"}) == pytest.approx(0.00375)


class TestMusicRoutes:
    def test_exact_live_catalog(self):
        assert set(MUSIC_MODELS) == {
            "google/lyria2",
            "google/lyria-3/clip",
            "stability-ai/stable-audio-2.5/text-to-audio",
        }

    def test_stable_audio_owns_duration_control(self):
        payload = ModelRunnerMusic()._build_payload(
            {"prompt": "lofi", "duration_seconds": 60},
            "stability-ai/stable-audio-2.5/text-to-audio",
        )
        assert payload["seconds_total"] == 60
        with pytest.raises(ValueError, match="1-190"):
            ModelRunnerMusic()._build_payload(
                {"prompt": "lofi", "duration_seconds": 300},
                "stability-ai/stable-audio-2.5/text-to-audio",
            )

    def test_lyria_rejects_unhonorable_durations(self):
        tool = ModelRunnerMusic()
        # The fixed ~30s length is accepted; anything else names the fix.
        payload = tool._build_payload({"prompt": "jazz", "duration_seconds": 30}, "google/lyria2")
        assert "seconds_total" not in payload
        with pytest.raises(ValueError, match="stable-audio-2.5"):
            tool._build_payload({"prompt": "jazz", "duration_seconds": 60}, "google/lyria2")

    def test_lyria2_passes_negative_prompt(self):
        payload = ModelRunnerMusic()._build_payload(
            {"prompt": "jazz", "negative_prompt": "vocals"}, "google/lyria2"
        )
        assert payload["negative_prompt"] == "vocals"

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("google/lyria2", 0.06),
            ("google/lyria-3/clip", 0.04),
            ("stability-ai/stable-audio-2.5/text-to-audio", 0.20),
        ],
    )
    def test_verified_costs(self, model, expected):
        assert ModelRunnerMusic().estimate_cost({"model": model}) == pytest.approx(expected)
