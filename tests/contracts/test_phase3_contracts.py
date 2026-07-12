"""Phase 3 contract tests — instruction-driven architecture.

Tests the new tools (TTS, music gen), pipeline manifests, style playbooks,
stage director skills, meta skills, and the animated-explainer pipeline.
"""

import sys
import builtins
import base64
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_loader import (
    load_pipeline,
    get_stage_order,
    get_required_tools,
    get_stage_skill,
    get_stage_review_focus,
    list_pipelines,
)
from lib.checkpoint import STAGES
from schemas.artifacts import list_schemas
from styles.playbook_loader import load_playbook, list_playbooks, validate_playbook
from tools.base_tool import ToolTier, ToolStatus
from tools.audio.music_gen import MusicGen
from tools.tool_registry import ToolRegistry
from tools.audio.elevenlabs_tts import ElevenLabsTTS
from tools.audio.openai_tts import OpenAITTS
from tools.audio.piper_tts import PiperTTS
from tools.audio.tts_selector import TTSSelector
from tools.audio.google_tts import GoogleTTS
from tools.graphics.google_imagen import GoogleImagen
from tools.audio.google_music import GoogleMusic
from tools.video.veo_video import VeoVideo


# ---- Google Credentials ----


class TestGoogleCredentials:
    def test_get_genai_client_with_google_api_key(self):
        from tools.google_credentials import get_genai_client
        from google.genai import types

        mock_client = MagicMock()
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "my_google_key",
                    "GEMINI_API_KEY": "",
                    "GOOGLE_GENAI_USE_VERTEXAI": "false",
                },
            ),
            patch("google.genai.Client", return_value=mock_client) as mock_genai_client,
        ):
            # 1. Call with default options (None)
            client = get_genai_client()
            assert client is not None
            kwargs = mock_genai_client.call_args[1]
            assert kwargs["api_key"] == "my_google_key"
            assert kwargs["http_options"] is None

            # 2. Call with explicit options
            my_opts = types.HttpOptions(timeout=12345)
            client_custom = get_genai_client(http_options=my_opts)
            assert client_custom is not None
            kwargs_custom = mock_genai_client.call_args[1]
            assert kwargs_custom["api_key"] == "my_google_key"
            assert kwargs_custom["http_options"].timeout == 12345


# ---- TTS Provider Tools ----


class TestElevenLabsTTS:
    def test_identity(self):
        tool = ElevenLabsTTS()
        info = tool.get_info()
        assert info["name"] == "elevenlabs_tts"
        assert info["tier"] == "voice"
        assert info["capability"] == "tts"
        assert info["provider"] == "elevenlabs"

    def test_cost_estimate(self):
        tool = ElevenLabsTTS()
        cost = tool.estimate_cost({"text": "Hello world, this is a test."})
        assert cost > 0
        assert cost < 0.01  # short text should be cheap

    def test_capabilities(self):
        tool = ElevenLabsTTS()
        assert "text_to_speech" in tool.capabilities
        assert "voice_selection" in tool.capabilities


class TestPiperTTS:
    def test_identity(self):
        tool = PiperTTS()
        info = tool.get_info()
        assert info["name"] == "piper_tts"
        assert info["tier"] == "voice"
        assert info["capability"] == "tts"
        assert info["provider"] == "piper"

    def test_cost_is_free(self):
        tool = PiperTTS()
        assert tool.estimate_cost({"text": "anything"}) == 0.0

    def test_capabilities(self):
        tool = PiperTTS()
        assert "text_to_speech" in tool.capabilities
        assert "offline_generation" in tool.capabilities

    def test_status_requires_piper_executable_even_if_python_package_imports(self, monkeypatch):
        """F-12 regression: Piper generation shells out to `piper`, so importing
        the Python package is not enough to mark the provider available."""
        original_import = builtins.__import__
        original_which = shutil.which

        def fake_import(name, *args, **kwargs):
            if name == "piper":
                return object()
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "piper" else original_which(cmd))
        monkeypatch.setattr(builtins, "__import__", fake_import)

        assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


class TestGoogleTTS:
    def test_identity(self):
        tool = GoogleTTS()
        info = tool.get_info()
        assert info["name"] == "google_tts"
        assert info["tier"] == "voice"
        assert info["capability"] == "tts"
        assert info["provider"] == "google_tts"

    def test_cost_estimate(self):
        tool = GoogleTTS()
        cost = tool.estimate_cost({"text": "Hello world, this is a test."})
        assert cost > 0
        assert cost < 0.01  # short text should be cheap

    def test_capabilities(self):
        tool = GoogleTTS()
        assert "text_to_speech" in tool.capabilities
        assert "voice_selection" in tool.capabilities


# ---- Music Generation Tools ----


class TestMusicGen:
    def test_identity(self):
        tool = MusicGen()
        info = tool.get_info()
        assert info["name"] == "music_gen"
        assert info["tier"] == "generate"

    def test_cost_estimate_scales_with_duration(self):
        tool = MusicGen()
        cost_30 = tool.estimate_cost({"prompt": "ambient", "duration_seconds": 30})
        cost_60 = tool.estimate_cost({"prompt": "ambient", "duration_seconds": 60})
        assert cost_60 > cost_30

    def test_capabilities(self):
        tool = MusicGen()
        assert "generate_background_music" in tool.capabilities


class TestGoogleMusic:
    def test_identity(self):
        tool = GoogleMusic()
        info = tool.get_info()
        assert info["name"] == "google_music"
        assert info["tier"] == "generate"
        assert info["capability"] == "music_generation"
        assert info["provider"] == "google"

    def test_duration_validation(self):
        tool = GoogleMusic()
        mock_client = MagicMock()

        mock_interaction = MagicMock()
        mock_interaction.status = "completed"
        mock_interaction.output_audio.data = base64.b64encode(b"audio_bytes").decode(
            "utf-8"
        )
        mock_client.interactions.create.return_value = mock_interaction

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
            patch("pathlib.Path.write_bytes"),
        ):
            # 1. duration > 184 and auto_fix is True -> coerced to 184
            inputs = {
                "prompt": "melodic pop",
                "duration_seconds": 200,
                "auto_fix": True,
                "output_path": "test_out.mp3",
            }
            res = tool.execute(inputs)
            assert res.success is True
            assert res.data["duration_seconds"] == 184.0

            # 2. duration > 184 and auto_fix is False -> raises error
            inputs = {
                "prompt": "melodic pop",
                "duration_seconds": 200,
                "auto_fix": False,
            }
            res = tool.execute(inputs)
            assert res.success is False
            assert res.error is not None
            assert "maximum duration is 184" in res.error

    def test_execute_success_convenience_extraction(self, tmp_path):
        tool = GoogleMusic()
        mock_client = MagicMock()

        mock_interaction = MagicMock()
        mock_interaction.status = "completed"
        mock_interaction.output_audio.data = base64.b64encode(
            b"my_fake_google_lyria_audio"
        ).decode("utf-8")
        mock_client.interactions.create.return_value = mock_interaction

        output_file = tmp_path / "test_music.mp3"

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            inputs = {
                "prompt": "atmospheric electronic ambient beat",
                "duration_seconds": 30,
                "output_path": str(output_file),
            }
            res = tool.execute(inputs)
            assert res.success is True
            assert res.data["provider"] == "google"
            assert res.data["model"] == "lyria-3-pro-preview"
            assert res.data["output"] == str(output_file)
            assert output_file.read_bytes() == b"my_fake_google_lyria_audio"

    def test_execute_success_fallback_extraction(self, tmp_path):
        tool = GoogleMusic()
        mock_client = MagicMock()

        mock_interaction = MagicMock()
        mock_interaction.status = "completed"
        del mock_interaction.output_audio

        mock_part = MagicMock()
        mock_part.type = "audio"
        mock_part.data = base64.b64encode(b"raw_step_audio").decode("utf-8")

        mock_step = MagicMock()
        mock_step.type = "model_output"
        mock_step.content = [mock_part]
        mock_interaction.steps = [mock_step]

        mock_client.interactions.create.return_value = mock_interaction

        output_file = tmp_path / "test_music_step.mp3"

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            inputs = {
                "prompt": "jazz piano solo",
                "duration_seconds": 30,
                "output_path": str(output_file),
            }
            res = tool.execute(inputs)
            assert res.success is True
            assert res.data["output"] == str(output_file)
            assert output_file.read_bytes() == b"raw_step_audio"

    @patch("os.path.exists")
    @patch("requests.get")
    def test_multimodal_image(self, mock_get, mock_exists, tmp_path):
        tool = GoogleMusic()
        mock_client = MagicMock()

        mock_interaction = MagicMock()
        mock_interaction.status = "completed"
        mock_interaction.output_audio.data = base64.b64encode(b"audio_bytes").decode(
            "utf-8"
        )
        mock_client.interactions.create.return_value = mock_interaction

        mock_exists.return_value = True

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.content = b"url_image_bytes"
        mock_get.return_value = mock_resp

        local_image = tmp_path / "ref.png"
        with open(local_image, "wb") as f:
            f.write(b"local_image_bytes")

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            # 1. Local image path
            inputs = {
                "prompt": "music inspired by image",
                "image_path": str(local_image),
                "output_path": str(tmp_path / "out1.mp3"),
            }
            res = tool.execute(inputs)
            assert res.success is True

            called_input = mock_client.interactions.create.call_args[1]["input"]
            assert len(called_input) == 2
            assert called_input[0] == {
                "type": "text",
                "text": "music inspired by image\n\n[Target Duration: 30 seconds]",
            }
            assert called_input[1]["type"] == "image"
            assert called_input[1]["mime_type"] == "image/png"
            assert called_input[1]["data"] == base64.b64encode(
                b"local_image_bytes"
            ).decode("utf-8")

            # 2. Remote image URL
            inputs = {
                "prompt": "music inspired by url",
                "image_url": "https://example.com/art.jpg",
                "output_path": str(tmp_path / "out2.mp3"),
            }
            res = tool.execute(inputs)
            assert res.success is True

            called_input = mock_client.interactions.create.call_args[1]["input"]
            assert len(called_input) == 2
            assert called_input[0] == {
                "type": "text",
                "text": "music inspired by url\n\n[Target Duration: 30 seconds]",
            }
            assert called_input[1]["type"] == "image"
            assert called_input[1]["mime_type"] == "image/jpeg"
            assert called_input[1]["data"] == base64.b64encode(
                b"url_image_bytes"
            ).decode("utf-8")

    def test_minimum_duration_validation(self, caplog):
        import logging

        tool = GoogleMusic()
        mock_client = MagicMock()

        mock_interaction = MagicMock()
        mock_interaction.status = "completed"
        mock_interaction.output_audio.data = base64.b64encode(b"audio_bytes").decode(
            "utf-8"
        )
        mock_client.interactions.create.return_value = mock_interaction

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
            patch("pathlib.Path.write_bytes"),
            caplog.at_level(logging.WARNING),
        ):
            # 1. duration < 5 and auto_fix is True -> coerced to 5 with warning logged
            inputs = {
                "prompt": "melodic pop",
                "duration_seconds": 3,
                "auto_fix": True,
                "output_path": "test_out.mp3",
            }
            res = tool.execute(inputs)
            assert res.success is True
            assert res.data["duration_seconds"] == 5.0

            warnings = [
                rec.message
                for rec in caplog.records
                if "minimum duration" in rec.message
            ]
            assert len(warnings) == 1
            assert "minimum duration of 5 seconds" in warnings[0]

            # Clear records for next check
            caplog.clear()

            # 2. duration < 5 and auto_fix is False -> raises error
            inputs = {
                "prompt": "melodic pop",
                "duration_seconds": 3,
                "auto_fix": False,
            }
            res = tool.execute(inputs)
            assert res.success is False
            assert res.error is not None
            assert "minimum duration is 5" in res.error

    def test_missing_image_path_error(self, tmp_path):
        tool = GoogleMusic()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            inputs = {
                "prompt": "music with missing image",
                "image_path": str(tmp_path / "does_not_exist.png"),
                "output_path": str(tmp_path / "out.mp3"),
            }
            res = tool.execute(inputs)
            assert res.success is False
            assert res.error is not None
            assert "Failed to load visual conditioning image" in res.error
            assert "Local reference image not found" in res.error


# ---- Image Generation Tools ----


class TestGoogleImagen:
    def test_identity(self):
        tool = GoogleImagen()
        info = tool.get_info()
        assert info["name"] == "google_imagen"
        assert info["tier"] == "generate"
        assert info["capability"] == "image_generation"
        assert info["provider"] == "google_imagen"

    def test_capabilities(self):
        tool = GoogleImagen()
        assert "text_to_image" in tool.capabilities


# ---- Video Generation Tools ----


class TestVeoVideo:
    def test_identity(self):
        tool = VeoVideo()
        info = tool.get_info()
        assert info["name"] == "veo_video"
        assert info["tier"] == "generate"
        assert info["capability"] == "video_generation"
        assert info["provider"] == "veo"

    def test_backend_auto_detect(self):
        tool = VeoVideo()

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "FAL_KEY": ""}):
            if "FAL_KEY" in os.environ:
                del os.environ["FAL_KEY"]
            if "FAL_AI_API_KEY" in os.environ:
                del os.environ["FAL_AI_API_KEY"]
            assert tool._get_google_credentials_status() is True
            assert not tool._get_fal_api_key()
            assert tool.get_status() == ToolStatus.AVAILABLE

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "FAL_KEY": "test_fal_key"},
        ):
            assert tool._get_google_credentials_status() is False
            assert tool._get_fal_api_key() == "test_fal_key"
            assert tool.get_status() == ToolStatus.AVAILABLE

    @patch("tools.video._shared.probe_output")
    def test_duration_coercion(self, mock_probe):
        tool = VeoVideo()
        mock_probe.return_value = {"width": 1920, "height": 1080, "duration": 8.0}

        mock_client = MagicMock()
        mock_client._api_client.vertexai = False
        mock_operation = MagicMock()
        mock_operation.done = True
        mock_operation.error = None

        mock_video_result = MagicMock()
        mock_video_result.video = MagicMock()
        mock_operation.response.generated_videos = [mock_video_result]
        mock_client.models.generate_videos.return_value = mock_operation

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            # auto_fix = True -> coerced to 8s
            inputs = {
                "prompt": "Test prompt",
                "backend": "google",
                "resolution": "1080p",
                "duration": "4s",
                "auto_fix": True,
                "output_path": "test_out.mp4",
            }
            res = tool.execute(inputs)
            assert res.success is True

            called_config = mock_client.models.generate_videos.call_args[1]["config"]
            assert called_config.duration_seconds == 8

    @patch("tools.video._shared.probe_output")
    @patch("PIL.Image.open")
    @patch("os.path.exists")
    @patch("requests.get")
    def test_operations_mapping(
        self, mock_req_get, mock_exists, mock_img_open, mock_probe
    ):
        tool = VeoVideo()
        mock_probe.return_value = {"width": 1920, "height": 1080, "duration": 8.0}
        mock_exists.return_value = True

        mock_img = MagicMock()
        mock_img.format = "PNG"
        mock_img_open.return_value = mock_img

        mock_resp = MagicMock()
        mock_resp.content = b"fake_image_bytes"
        mock_req_get.return_value = mock_resp

        mock_client = MagicMock()
        mock_client._api_client.vertexai = False
        mock_operation = MagicMock()
        mock_operation.done = True
        mock_operation.error = None
        mock_video_result = MagicMock()
        mock_video_result.video = MagicMock()
        mock_operation.response.generated_videos = [mock_video_result]
        mock_client.models.generate_videos.return_value = mock_operation

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            # text_to_video
            inputs = {
                "prompt": "Test text to video",
                "backend": "google",
                "operation": "text_to_video",
                "duration": "8s",
            }
            res = tool.execute(inputs)
            assert res.success is True

            called_kwargs = mock_client.models.generate_videos.call_args[1]
            assert called_kwargs["image"] is None

            # image_to_video
            inputs = {
                "prompt": "Test image to video",
                "backend": "google",
                "operation": "image_to_video",
                "image_path": "local_img.png",
                "duration": "8s",
            }
            res = tool.execute(inputs)
            assert res.success is True

            called_kwargs = mock_client.models.generate_videos.call_args[1]
            assert called_kwargs["image"] is not None

    def test_vertex_ai_mode_rejection(self):
        tool = VeoVideo()
        mock_client = MagicMock()
        mock_client.vertexai = True
        if hasattr(mock_client, "_api_client"):
            delattr(mock_client, "_api_client")

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}),
            patch("google.genai.Client", return_value=mock_client),
        ):
            inputs = {
                "prompt": "cinematic shot",
                "backend": "google",
            }
            res = tool.execute(inputs)
            assert res.success is False
            assert res.error is not None
            assert "only supported using the Gemini Developer API" in res.error

    def test_missing_local_image_paths(self):
        tool = VeoVideo()
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test_key", "GOOGLE_GENAI_USE_VERTEXAI": "false"},
        ):
            inputs = {
                "prompt": "cinematic shot",
                "backend": "google",
                "operation": "image_to_video",
                "image_path": "non_existent_file_path_12345.png",
            }
            res = tool.execute(inputs)
            assert res.success is False
            assert "Local input image not found" in res.error

    def test_missing_reference_image_paths(self):
        tool = VeoVideo()
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test_key", "GOOGLE_GENAI_USE_VERTEXAI": "false"},
        ):
            inputs = {
                "prompt": "cinematic shot",
                "backend": "google",
                "operation": "reference_to_video",
                "reference_image_paths": ["non_existent_reference_12345.png"],
            }
            res = tool.execute(inputs)
            assert res.success is False
            assert "Local reference image not found" in res.error


class TestNewToolsRegistry:
    def test_all_register(self):
        reg = ToolRegistry()
        reg.register(ElevenLabsTTS())
        reg.register(PiperTTS())
        reg.register(MusicGen())
        assert len(reg.list_all()) == 3

    def test_voice_tier_tools(self):
        reg = ToolRegistry()
        reg.register(ElevenLabsTTS())
        reg.register(OpenAITTS())
        reg.register(PiperTTS())
        voice_tools = reg.get_by_tier(ToolTier.VOICE)
        assert len(voice_tools) == 3
        names = {t.name for t in voice_tools}
        assert names == {"elevenlabs_tts", "openai_tts", "piper_tts"}


class TestCapabilityMetadata:
    def test_tts_tools_expose_capability_provider_and_location(self):
        tool = ElevenLabsTTS()
        info = tool.get_info()
        assert info["capability"] == "tts"
        assert info["provider"] == "elevenlabs"
        assert info["usage_location"].endswith(
            "tools\\audio\\elevenlabs_tts.py"
        ) or info["usage_location"].endswith("tools/audio/elevenlabs_tts.py")
        assert "related_skills" in info
        assert "fallback_tools" in info

    def test_provider_specific_tts_tools_register(self):
        reg = ToolRegistry()
        reg.register(ElevenLabsTTS())
        reg.register(OpenAITTS())
        reg.register(PiperTTS())
        reg.register(TTSSelector())
        assert {tool.name for tool in reg.get_by_capability("tts")} == {
            "elevenlabs_tts",
            "openai_tts",
            "piper_tts",
            "tts_selector",
        }
        assert {tool.name for tool in reg.get_by_provider("elevenlabs")} == {
            "elevenlabs_tts"
        }

    def test_registry_catalog_views(self):
        reg = ToolRegistry()
        reg.register(ElevenLabsTTS())
        reg.register(OpenAITTS())
        reg.register(PiperTTS())
        catalog = reg.capability_catalog()
        assert "tts" in catalog
        providers = {item["provider"] for item in catalog["tts"] if item["provider"] != "selector"}
        assert providers == {
            "dashscope",
            "doubao",
            "elevenlabs",
            "google_tts",
            "openai",
            "piper",
        }


# ---- Animated Explainer Pipeline ----


class TestAnimatedExplainerManifest:
    def test_loads(self):
        manifest = load_pipeline("animated-explainer")
        assert manifest["name"] == "animated-explainer"
        assert manifest["version"] == "2.0"

    def test_all_stages_present(self):
        manifest = load_pipeline("animated-explainer")
        stage_names = get_stage_order(manifest)
        expected = [
            "research",
            "proposal",
            "script",
            "scene_plan",
            "assets",
            "edit",
            "compose",
            "publish",
        ]
        assert stage_names == expected

    def test_every_stage_has_skill(self):
        manifest = load_pipeline("animated-explainer")
        for stage in manifest["stages"]:
            assert "skill" in stage, f"Stage {stage['name']} missing skill"
            skill = get_stage_skill(manifest, stage["name"])
            assert skill is not None
            assert skill.startswith("pipelines/explainer/")

    def test_every_stage_has_review_focus(self):
        manifest = load_pipeline("animated-explainer")
        for stage in manifest["stages"]:
            focus = get_stage_review_focus(manifest, stage["name"])
            assert len(focus) >= 3, (
                f"Stage {stage['name']} needs more review focus items"
            )

    def test_required_tools_complete(self):
        manifest = load_pipeline("animated-explainer")
        tools = get_required_tools(manifest)
        expected = {"tts_selector", "image_selector", "video_compose", "audio_mixer"}
        for t in expected:
            assert t in tools, f"Missing required tool: {t}"

    def test_creative_stages_require_human_approval(self):
        manifest = load_pipeline("animated-explainer")
        approval_stages = {"proposal", "script", "scene_plan", "publish"}
        for stage in manifest["stages"]:
            if stage["name"] in approval_stages:
                assert stage.get("human_approval_default") is True, (
                    f"Stage {stage['name']} should require human approval"
                )

    def test_listed(self):
        assert "animated-explainer" in list_pipelines()


# ---- Style Playbooks ----


class TestStylePlaybooks:
    def test_all_listed(self):
        playbooks = list_playbooks()
        assert "clean-professional" in playbooks
        assert "flat-motion-graphics" in playbooks
        assert "minimalist-diagram" in playbooks

    @pytest.mark.parametrize(
        "name", ["clean-professional", "flat-motion-graphics", "minimalist-diagram"]
    )
    def test_loads_and_validates(self, name):
        pb = load_playbook(name)
        assert pb["identity"]["name"]
        assert pb["identity"]["category"]

    @pytest.mark.parametrize(
        "name", ["clean-professional", "flat-motion-graphics", "minimalist-diagram"]
    )
    def test_has_required_sections(self, name):
        pb = load_playbook(name)
        assert "visual_language" in pb
        assert "typography" in pb
        assert "motion" in pb
        assert "audio" in pb
        assert "asset_generation" in pb
        assert "quality_rules" in pb
        assert len(pb["quality_rules"]) >= 3

    @pytest.mark.parametrize(
        "name", ["clean-professional", "flat-motion-graphics", "minimalist-diagram"]
    )
    def test_color_palette_complete(self, name):
        pb = load_playbook(name)
        palette = pb["visual_language"]["color_palette"]
        assert "primary" in palette
        assert "accent" in palette
        assert "background" in palette
        assert "text" in palette

    @pytest.mark.parametrize(
        "name", ["clean-professional", "flat-motion-graphics", "minimalist-diagram"]
    )
    def test_pacing_rules_present(self, name):
        pb = load_playbook(name)
        pacing = pb["motion"]["pacing_rules"]
        assert "min_scene_hold_seconds" in pacing
        assert "max_scene_hold_seconds" in pacing

    def test_compatible_with_manifest(self):
        manifest = load_pipeline("animated-explainer")
        available = list_playbooks()
        compat = manifest.get("compatible_playbooks", {})
        # compatible_playbooks is a dict with recommended/also_works lists
        playbook_names = compat.get("recommended", []) + compat.get("also_works", [])
        for name in playbook_names:
            assert name in available, (
                f"Manifest references unavailable playbook: {name}"
            )


# ---- Skills Existence ----


class TestSkillsExist:
    SKILLS_DIR = PROJECT_ROOT / "skills"

    @pytest.mark.parametrize(
        "skill_path",
        [
            "pipelines/explainer/idea-director.md",
            "pipelines/explainer/script-director.md",
            "pipelines/explainer/scene-director.md",
            "pipelines/explainer/asset-director.md",
            "pipelines/explainer/edit-director.md",
            "pipelines/explainer/compose-director.md",
            "pipelines/explainer/publish-director.md",
        ],
    )
    def test_director_skills_exist(self, skill_path):
        full_path = self.SKILLS_DIR / skill_path
        assert full_path.exists(), f"Missing director skill: {skill_path}"
        content = full_path.read_text(encoding="utf-8")
        assert len(content) > 500, f"Skill too short to be useful: {skill_path}"

    @pytest.mark.parametrize(
        "skill_path",
        [
            "meta/reviewer.md",
            "meta/checkpoint-protocol.md",
            "meta/skill-creator.md",
        ],
    )
    def test_meta_skills_exist(self, skill_path):
        full_path = self.SKILLS_DIR / skill_path
        assert full_path.exists(), f"Missing meta skill: {skill_path}"
        content = full_path.read_text(encoding="utf-8")
        assert len(content) > 500, f"Skill too short to be useful: {skill_path}"

    @pytest.mark.parametrize(
        "skill_path",
        [
            "pipelines/explainer/idea-director.md",
            "pipelines/explainer/script-director.md",
            "pipelines/explainer/scene-director.md",
            "pipelines/explainer/asset-director.md",
            "pipelines/explainer/edit-director.md",
            "pipelines/explainer/compose-director.md",
            "pipelines/explainer/publish-director.md",
        ],
    )
    def test_director_skills_have_required_sections(self, skill_path):
        content = (self.SKILLS_DIR / skill_path).read_text(encoding="utf-8")
        assert "## When to Use" in content
        assert "## Process" in content or "## Protocol" in content
        assert "Self-Evaluate" in content or "self-evaluate" in content.lower()

    @pytest.mark.parametrize(
        "skill_path",
        [
            "meta/reviewer.md",
            "meta/checkpoint-protocol.md",
            "meta/skill-creator.md",
        ],
    )
    def test_meta_skills_have_required_sections(self, skill_path):
        content = (self.SKILLS_DIR / skill_path).read_text(encoding="utf-8")
        assert "## When to Use" in content
        assert "## Protocol" in content or "## Process" in content


# ---- Remotion Scaffold ----


class TestRemotionScaffold:
    REMOTION_DIR = PROJECT_ROOT / "remotion-composer"

    def test_package_json_exists(self):
        assert (self.REMOTION_DIR / "package.json").exists()

    def test_entry_point_exists(self):
        assert (self.REMOTION_DIR / "src" / "index.tsx").exists()

    def test_root_composition_exists(self):
        assert (self.REMOTION_DIR / "src" / "Root.tsx").exists()

    def test_explainer_component_exists(self):
        assert (self.REMOTION_DIR / "src" / "Explainer.tsx").exists()

    def test_text_card_component_exists(self):
        assert (self.REMOTION_DIR / "src" / "components" / "TextCard.tsx").exists()

    def test_stat_card_component_exists(self):
        assert (self.REMOTION_DIR / "src" / "components" / "StatCard.tsx").exists()


# ---- Video Compose Operations ----


class TestVideoComposeOperations:
    def test_render_operation_exists(self):
        from typing import Any
        from tools.video.video_compose import VideoCompose

        tool = VideoCompose()
        schema: Any = tool.input_schema
        ops = schema["properties"]["operation"]["enum"]
        assert "render" in ops
        assert "remotion_render" in ops

    def test_render_rejects_missing_inputs(self):
        from tools.video.video_compose import VideoCompose

        tool = VideoCompose()
        result = tool.execute({"operation": "render"})
        assert not result.success
        assert result.error is not None
        assert "edit_decisions" in result.error
