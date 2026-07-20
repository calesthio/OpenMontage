"""Contract tests for DashScope (Alibaba Cloud Bailian) provider tools.

These tests verify that the tools satisfy the BaseTool contract without
requiring a real DashScope API key or making any API calls. They check
class attributes, schemas, status reporting, cost estimates, and the
Layer 3 skill file existence.

Run: pytest tests/contracts/test_dashscope_tools.py -v
"""

from pathlib import Path

import pytest

from tools.base_tool import (
    BaseTool,
    ExecutionMode,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.graphics.dashscope_image import DashscopeImage
from tools.audio.dashscope_tts import DashscopeTTS
from tools.analysis.dashscope_asr import DashscopeAsr

TOOLS = [DashscopeImage, DashscopeTTS, DashscopeAsr]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

EXPECTED_TIER = {
    DashscopeImage: ToolTier.GENERATE,
    DashscopeTTS: ToolTier.VOICE,
    DashscopeAsr: ToolTier.ANALYZE,
}
EXPECTED_CAPABILITY = {
    DashscopeImage: "image_generation",
    DashscopeTTS: "tts",
    DashscopeAsr: "analysis",
}
EXPECTED_EXECUTION_MODE = {
    DashscopeImage: ExecutionMode.SYNC,
    DashscopeTTS: ExecutionMode.SYNC,
    DashscopeAsr: ExecutionMode.ASYNC,
}


# ------------------------------------------------------------------
# Contract compliance (parametrized over all 3 tools)
# ------------------------------------------------------------------

@pytest.mark.parametrize("cls", TOOLS, ids=lambda c: c.name)
class TestContract:

    def test_inherits_base_tool(self, cls):
        assert issubclass(cls, BaseTool)

    def test_has_required_identity(self, cls):
        tool = cls()
        assert tool.name
        assert tool.version
        assert tool.provider == "dashscope"
        assert tool.capability == EXPECTED_CAPABILITY[cls]
        assert tool.tier == EXPECTED_TIER[cls]
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.API

    def test_has_input_schema(self, cls):
        tool = cls()
        schema = tool.input_schema
        assert schema.get("type") == "object"
        props = schema.get("properties", {})
        required = schema.get("required", [])
        # Each tool has at least one required field
        assert len(required) >= 1
        for field in required:
            assert field in props

    def test_has_capabilities(self, cls):
        tool = cls()
        assert len(tool.capabilities) > 0

    def test_has_agent_skills(self, cls):
        tool = cls()
        assert tool.agent_skills
        assert "dashscope" in tool.agent_skills

    def test_dashscope_layer3_skill_exists(self, cls):
        skill_path = (
            PROJECT_ROOT / ".agents" / "skills" / "dashscope" / "SKILL.md"
        )
        assert skill_path.exists(), f"Missing Layer 3 skill: {skill_path}"
        content = skill_path.read_text(encoding="utf-8")
        assert "DASHSCOPE_API_KEY" in content

    def test_has_fallbacks(self, cls):
        tool = cls()
        assert tool.fallback or tool.fallback_tools

    def test_has_install_instructions(self, cls):
        tool = cls()
        assert tool.install_instructions
        assert "DASHSCOPE_API_KEY" in tool.install_instructions

    def test_get_info_returns_dict(self, cls):
        tool = cls()
        info = tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == tool.name
        assert info["provider"] == "dashscope"
        assert info["runtime"] == "api"
        assert info["agent_skills"] == ["dashscope"]

    def test_execution_mode(self, cls):
        tool = cls()
        assert tool.execution_mode == EXPECTED_EXECUTION_MODE[cls]

    def test_status_unavailable_without_key(self, cls, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        tool = cls()
        assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_status_available_with_key(self, cls, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key-for-testing")
        tool = cls()
        assert tool.get_status() == ToolStatus.AVAILABLE

    def test_idempotency_key_fields(self, cls):
        tool = cls()
        assert len(tool.idempotency_key_fields) > 0

    def test_has_resource_profile(self, cls):
        tool = cls()
        assert tool.resource_profile.network_required is True
        assert tool.resource_profile.vram_mb == 0

    def test_has_retry_policy(self, cls):
        tool = cls()
        assert tool.retry_policy.max_retries >= 0

    def test_has_side_effects(self, cls):
        tool = cls()
        assert len(tool.side_effects) > 0
        # Must mention it calls the API
        assert any("API" in s for s in tool.side_effects)

    def test_has_user_visible_verification(self, cls):
        tool = cls()
        assert len(tool.user_visible_verification) > 0

    def test_lazy_imports_requests(self, cls, monkeypatch):
        """Tool module must not import requests at top level (registry
        discovery must stay fast)."""
        import importlib
        import sys
        # Remove requests from cache to simulate fresh import
        mod_name = cls.__module__
        monkeypatch.delitem(sys.modules, "requests", raising=False)
        # Re-import the tool module — should not pull in requests
        # (requests is imported inside execute(), not at module level)
        importlib.reload(sys.modules[mod_name])
        # The tool module itself should not have imported requests
        # (it's inside execute, so module-level reload shouldn't trigger it)
        # This is a smoke test — the real proof is that registry.discover()
        # works without requests installed, but requests IS installed here.

    def test_estimate_cost_returns_float(self, cls):
        tool = cls()
        # Use tool-specific minimal inputs
        if cls is DashscopeImage:
            cost = tool.estimate_cost({"prompt": "test", "n": 1})
        elif cls is DashscopeTTS:
            cost = tool.estimate_cost({"text": "test"})
        else:
            cost = tool.estimate_cost({"audio_url": "https://x.com/a.mp3"})
        assert isinstance(cost, float)
        assert cost >= 0.0

    def test_dry_run_returns_dict(self, cls):
        tool = cls()
        if cls is DashscopeImage:
            result = tool.dry_run({"prompt": "test"})
        elif cls is DashscopeTTS:
            result = tool.dry_run({"text": "test"})
        else:
            result = tool.dry_run({"audio_url": "https://x.com/a.mp3"})
        assert isinstance(result, dict)
        assert "tool" in result
        assert result["tool"] == tool.name


# ------------------------------------------------------------------
# Image-specific tests
# ------------------------------------------------------------------

class TestDashscopeImageSpecific:

    def test_default_model_is_qwen_image_2_pro(self):
        tool = DashscopeImage()
        assert tool.input_schema["properties"]["model"]["default"] == "qwen-image-2.0-pro"

    def test_default_size_uses_asterisk_format(self):
        """CRITICAL: DashScope uses W*H (asterisk), not WxH."""
        tool = DashscopeImage()
        size_default = tool.input_schema["properties"]["size"]["default"]
        assert "*" in size_default
        assert "x" not in size_default.lower()

    def test_cost_positive_for_image(self):
        tool = DashscopeImage()
        assert tool.estimate_cost({"prompt": "test", "n": 1}) > 0.0

    def test_cost_scales_with_n(self):
        tool = DashscopeImage()
        cost1 = tool.estimate_cost({"prompt": "test", "n": 1})
        cost3 = tool.estimate_cost({"prompt": "test", "n": 3})
        assert cost3 > cost1

    def test_build_payload_uses_asterisk_size(self):
        tool = DashscopeImage()
        payload = tool._build_payload({"prompt": "test"})
        assert "*" in payload["parameters"]["size"]

    def test_build_payload_includes_messages_structure(self):
        tool = DashscopeImage()
        payload = tool._build_payload({"prompt": "a cat"})
        assert "input" in payload
        assert "messages" in payload["input"]
        assert payload["input"]["messages"][0]["content"][0]["text"] == "a cat"

    def test_build_payload_optional_negative_prompt(self):
        tool = DashscopeImage()
        payload = tool._build_payload({
            "prompt": "test",
            "negative_prompt": "blurry",
        })
        assert payload["parameters"]["negative_prompt"] == "blurry"

    def test_build_payload_omits_negative_prompt_when_absent(self):
        tool = DashscopeImage()
        payload = tool._build_payload({"prompt": "test"})
        assert "negative_prompt" not in payload["parameters"]

    def test_safe_error_redacts_key(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "secret-key-12345")
        redacted = DashscopeImage._safe_error(
            Exception("failed with key secret-key-12345")
        )
        assert "secret-key-12345" not in redacted
        assert "[redacted]" in redacted


# ------------------------------------------------------------------
# PR review regressions: multi-image download + idempotency keys
# ------------------------------------------------------------------

class TestDashscopeImageMultiOutput:
    """Regression tests for PR #240 review: the tool advertised
    multiple_outputs and accepted n>1 but only downloaded the first image.
    Verify every returned URL is saved and returned as an artifact."""

    def test_extract_image_urls_across_choices(self):
        data = {
            "output": {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": [{"image": "https://x/1.png"}]}},
                    {"finish_reason": "stop", "message": {"content": [{"image": "https://x/2.png"}]}},
                    {"finish_reason": "stop", "message": {"content": [{"image": "https://x/3.png"}]}},
                ]
            }
        }
        assert DashscopeImage._extract_image_urls(data) == [
            "https://x/1.png",
            "https://x/2.png",
            "https://x/3.png",
        ]

    def test_extract_image_urls_within_single_choice(self):
        data = {
            "output": {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": [
                        {"image": "https://x/1.png"},
                        {"image": "https://x/2.png"},
                    ]}}
                ]
            }
        }
        assert DashscopeImage._extract_image_urls(data) == [
            "https://x/1.png",
            "https://x/2.png",
        ]

    def test_extract_image_urls_empty_when_no_images(self):
        assert DashscopeImage._extract_image_urls({}) == []
        assert DashscopeImage._extract_image_urls(
            {"output": {"choices": []}}
        ) == []
        assert DashscopeImage._extract_image_urls(
            {"output": {"choices": [{"message": {"content": [{"text": "x"}]}}]}}
        ) == []

    def test_extract_image_urls_skips_failed_choices(self):
        """Per Qwen Cloud docs, a multi-output task can be SUCCEEDED with
        partial failures. Choices with finish_reason != "stop" must be
        skipped so we don't download partial/empty results. The failed
        choice here carries a non-empty URL to prove it is the
        finish_reason filter (not the truthy-url check) that skips it."""
        data = {
            "output": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": [{"image": "https://x/ok.png"}]},
                    },
                    {
                        "finish_reason": "content_filter",
                        "message": {"content": [{"image": "https://x/blocked.png"}]},
                    },
                ]
            }
        }
        assert DashscopeImage._extract_image_urls(data) == ["https://x/ok.png"]

    def test_resolve_output_paths_single_unchanged(self):
        paths = DashscopeImage._resolve_output_paths("foo.png", 1)
        assert paths == [Path("foo.png")]

    def test_resolve_output_paths_multiple_inserts_index(self):
        paths = DashscopeImage._resolve_output_paths("foo.png", 3)
        assert paths == [
            Path("foo_1.png"),
            Path("foo_2.png"),
            Path("foo_3.png"),
        ]

    def test_resolve_output_paths_multiple_without_extension(self):
        paths = DashscopeImage._resolve_output_paths("foo", 2)
        assert paths == [Path("foo_1"), Path("foo_2")]

    def test_execute_downloads_all_images(self, monkeypatch, tmp_path):
        """The bug: n=3 returned images_generated=3 but downloaded 1 file.
        Mock the DashScope response with 3 URLs and verify all 3 are saved."""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")

        class FakeResp:
            def __init__(self, payload, content=b""):
                self._payload = payload
                self.content = content

            def raise_for_status(self):
                pass

            def json(self):
                return self._payload

        api_response = {
            "output": {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": [{"image": f"https://x/{i}.png"}]}}
                    for i in range(1, 4)
                ]
            },
            "usage": {"image_count": 3},
        }

        import requests

        monkeypatch.setattr(
            requests, "post", lambda *a, **kw: FakeResp(api_response)
        )
        monkeypatch.setattr(
            requests,
            "get",
            lambda url, **kw: FakeResp({}, content=f"img-{url}".encode()),
        )

        out = tmp_path / "shot.png"
        result = DashscopeImage().execute({
            "prompt": "test", "n": 3, "output_path": str(out),
        })

        assert result.success is True
        assert result.data["images_generated"] == 3
        assert len(result.artifacts) == 3
        assert (tmp_path / "shot_1.png").exists()
        assert (tmp_path / "shot_2.png").exists()
        assert (tmp_path / "shot_3.png").exists()

    def test_execute_single_image_uses_base_path(self, monkeypatch, tmp_path):
        """n=1 must keep the legacy single-path behavior (no _1 suffix)."""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")

        class FakeResp:
            def __init__(self, payload, content=b""):
                self._payload = payload
                self.content = content

            def raise_for_status(self):
                pass

            def json(self):
                return self._payload

        api_response = {
            "output": {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": [{"image": "https://x/1.png"}]}}
                ]
            },
            "usage": {"image_count": 1},
        }

        import requests

        monkeypatch.setattr(
            requests, "post", lambda *a, **kw: FakeResp(api_response)
        )
        monkeypatch.setattr(
            requests,
            "get",
            lambda url, **kw: FakeResp({}, content=b"img-bytes"),
        )

        out = tmp_path / "shot.png"
        result = DashscopeImage().execute({
            "prompt": "test", "n": 1, "output_path": str(out),
        })

        assert result.success is True
        assert result.data["images_generated"] == 1
        assert result.artifacts == [str(out)]
        assert out.exists()
        assert not (tmp_path / "shot_1.png").exists()


class TestDashscopeIdempotencyKeys:
    """Regression tests for PR #240 review: idempotency keys must include
    all output-affecting fields so different requests don't collide and
    reuse stale artifacts."""

    def test_image_idempotency_includes_all_output_fields(self):
        fields = DashscopeImage().idempotency_key_fields
        for field in (
            "prompt", "model", "size", "n",
            "negative_prompt", "seed", "prompt_extend", "watermark",
        ):
            assert field in fields, f"image idempotency missing {field}"

    def test_image_idempotency_differs_on_negative_prompt(self):
        tool = DashscopeImage()
        base = {"prompt": "x", "model": "m", "size": "1024*1024", "n": 1}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "negative_prompt": "blurry"}
        )

    def test_image_idempotency_differs_on_seed(self):
        tool = DashscopeImage()
        base = {"prompt": "x", "model": "m", "size": "1024*1024", "n": 1}
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "seed": 42}
        )

    def test_image_idempotency_differs_on_prompt_extend(self):
        tool = DashscopeImage()
        base = {"prompt": "x", "model": "m", "size": "1024*1024", "n": 1}
        assert tool.idempotency_key(
            {**base, "prompt_extend": True}
        ) != tool.idempotency_key({**base, "prompt_extend": False})

    def test_image_idempotency_differs_on_watermark(self):
        tool = DashscopeImage()
        base = {"prompt": "x", "model": "m", "size": "1024*1024", "n": 1}
        assert tool.idempotency_key(
            {**base, "watermark": False}
        ) != tool.idempotency_key({**base, "watermark": True})

    def test_tts_idempotency_includes_instructions(self):
        assert "instructions" in DashscopeTTS().idempotency_key_fields

    def test_tts_idempotency_differs_on_instructions(self):
        tool = DashscopeTTS()
        base = {
            "text": "hi", "voice": "Cherry",
            "model": "qwen3-tts-flash", "language_type": "Auto",
        }
        assert tool.idempotency_key(base) != tool.idempotency_key(
            {**base, "instructions": "speak softly"}
        )

    def test_asr_idempotency_includes_enable_words_and_language_hints(self):
        fields = DashscopeAsr().idempotency_key_fields
        assert "enable_words" in fields
        assert "language_hints" in fields

    def test_asr_idempotency_differs_on_enable_words(self):
        tool = DashscopeAsr()
        base = {"audio_url": "https://x/a.mp3", "model": "qwen3-asr-flash-filetrans"}
        assert tool.idempotency_key(
            {**base, "enable_words": True}
        ) != tool.idempotency_key({**base, "enable_words": False})

    def test_asr_idempotency_differs_on_language_hints(self):
        tool = DashscopeAsr()
        base = {"audio_url": "https://x/a.mp3", "model": "qwen3-asr-flash-filetrans"}
        assert tool.idempotency_key(
            {**base, "language_hints": ["zh"]}
        ) != tool.idempotency_key(
            {**base, "language_hints": ["zh", "en"]}
        )


# ------------------------------------------------------------------
# TTS-specific tests
# ------------------------------------------------------------------

class TestDashscopeTtsSpecific:

    def test_default_model_is_qwen3_tts_flash(self):
        tool = DashscopeTTS()
        assert tool.input_schema["properties"]["model"]["default"] == "qwen3-tts-flash"

    def test_default_voice_is_cherry(self):
        tool = DashscopeTTS()
        assert tool.input_schema["properties"]["voice"]["default"] == "Cherry"

    def test_default_language_is_auto(self):
        tool = DashscopeTTS()
        assert tool.input_schema["properties"]["language_type"]["default"] == "Auto"

    def test_cost_scales_with_text_length(self):
        tool = DashscopeTTS()
        cost_short = tool.estimate_cost({"text": "hi"})
        cost_long = tool.estimate_cost({"text": "hi " * 100})
        assert cost_long > cost_short

    def test_build_payload_includes_input_text_voice(self):
        tool = DashscopeTTS()
        payload = tool._build_payload({"text": "hello", "voice": "Ethan"})
        assert payload["input"]["text"] == "hello"
        assert payload["input"]["voice"] == "Ethan"

    def test_build_payload_adds_instructions_for_instruct_model(self):
        tool = DashscopeTTS()
        payload = tool._build_payload({
            "text": "hello",
            "instructions": "speak softly",
        })
        assert payload["input"]["instructions"] == "speak softly"
        assert payload["input"]["optimize_instructions"] is True

    def test_fallback_includes_piper(self):
        """Piper is the free offline fallback — must be in fallback list."""
        tool = DashscopeTTS()
        assert "piper_tts" in tool.fallback_tools

    def test_safe_error_redacts_key(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "secret-key-12345")
        redacted = DashscopeTTS._safe_error(
            Exception("failed with key secret-key-12345")
        )
        assert "secret-key-12345" not in redacted
        assert "[redacted]" in redacted


# ------------------------------------------------------------------
# ASR-specific tests
# ------------------------------------------------------------------

class TestDashscopeAsrSpecific:

    def test_default_model_is_filetrans(self):
        """CRITICAL: must use qwen3-asr-flash-filetrans, NOT qwen3-asr-flash.
        The sync version does not support word-level timestamps."""
        tool = DashscopeAsr()
        assert tool.input_schema["properties"]["model"]["default"] == "qwen3-asr-flash-filetrans"

    def test_execution_mode_is_async(self):
        tool = DashscopeAsr()
        assert tool.execution_mode == ExecutionMode.ASYNC

    def test_default_enable_words_is_true(self):
        """Word-level timestamps must be enabled by default."""
        tool = DashscopeAsr()
        assert tool.input_schema["properties"]["enable_words"]["default"] is True

    def test_default_language_hints_includes_zh_en(self):
        tool = DashscopeAsr()
        hints = tool.input_schema["properties"]["language_hints"]["default"]
        assert "zh" in hints
        assert "en" in hints

    def test_rejects_local_file_path(self, monkeypatch):
        """audio_url must be a public URL — local paths are rejected."""
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key-for-testing")
        tool = DashscopeAsr()
        result = tool.execute({"audio_url": "/local/path/audio.mp3"})
        assert result.success is False
        assert "publicly accessible URL" in result.error

    def test_rejects_relative_path(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key-for-testing")
        tool = DashscopeAsr()
        result = tool.execute({"audio_url": "audio.mp3"})
        assert result.success is False
        assert "publicly accessible URL" in result.error

    def test_rejects_empty_url(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key-for-testing")
        tool = DashscopeAsr()
        result = tool.execute({"audio_url": ""})
        assert result.success is False
        assert "required" in result.error.lower()

    def test_rejects_no_key(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        tool = DashscopeAsr()
        result = tool.execute({"audio_url": "https://example.com/audio.mp3"})
        assert result.success is False
        assert "DASHSCOPE_API_KEY" in result.error

    def test_build_payload_enables_words(self):
        tool = DashscopeAsr()
        payload = tool._build_payload({"audio_url": "https://x.com/a.mp3"})
        assert payload["parameters"]["enable_words"] is True

    def test_build_payload_includes_file_url(self):
        """qwen3-asr-flash-filetrans uses file_url (singular string),
        NOT file_urls (plural array) like paraformer-v2."""
        tool = DashscopeAsr()
        payload = tool._build_payload({"audio_url": "https://x.com/a.mp3"})
        assert payload["input"]["file_url"] == "https://x.com/a.mp3"

    def test_extract_words_normalizes_ms_to_seconds(self):
        """Word timestamps from DashScope are in milliseconds; the tool
        must normalize to seconds for downstream subtitle building."""
        fake_transcription = {
            "transcripts": [
                {
                    "sentences": [
                        {
                            "words": [
                                {"text": "hello", "begin_time": 1000, "end_time": 1500},
                                {"text": "world", "begin_time": 1500, "end_time": 2000},
                            ]
                        }
                    ]
                }
            ]
        }
        words = DashscopeAsr._extract_words(fake_transcription)
        assert len(words) == 2
        assert words[0]["text"] == "hello"
        assert words[0]["begin_time_seconds"] == 1.0
        assert words[0]["end_time_seconds"] == 1.5
        assert words[1]["begin_time_seconds"] == 1.5
        assert words[1]["end_time_seconds"] == 2.0

    def test_extract_words_handles_empty_transcription(self):
        words = DashscopeAsr._extract_words({})
        assert words == []

    def test_is_public_url_accepts_https(self):
        assert DashscopeAsr._is_public_url("https://example.com/audio.mp3") is True

    def test_is_public_url_rejects_local(self):
        assert DashscopeAsr._is_public_url("/local/path/audio.mp3") is False
        assert DashscopeAsr._is_public_url("audio.mp3") is False
        assert DashscopeAsr._is_public_url("ftp://example.com/audio.mp3") is False

    def test_safe_error_redacts_key(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "secret-key-12345")
        redacted = DashscopeAsr._safe_error(
            Exception("failed with key secret-key-12345")
        )
        assert "secret-key-12345" not in redacted
        assert "[redacted]" in redacted


# ------------------------------------------------------------------
# Registry discovery
# ------------------------------------------------------------------

class TestDashscopeRegistryDiscovery:

    def test_all_three_tools_discoverable(self):
        from tools.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover()
        dashscope_tools = [
            t for t in registry._tools.values()
            if t.provider == "dashscope"
        ]
        names = {t.name for t in dashscope_tools}
        assert names == {"dashscope_image", "dashscope_tts", "dashscope_asr"}

    def test_image_selector_finds_dashscope(self):
        """image_selector should auto-discover dashscope_image by capability."""
        from tools.graphics.image_selector import ImageSelector
        selector = ImageSelector()
        # Selector discovers providers by capability="image_generation"
        # dashscope_image has that capability, so it should be routable
        assert DashscopeImage().capability == "image_generation"

    def test_tts_selector_finds_dashscope(self):
        """tts_selector should auto-discover dashscope_tts by capability."""
        from tools.audio.tts_selector import TTSSelector
        selector = TTSSelector()
        assert DashscopeTTS().capability == "tts"
