"""Bound-safety tests for every paid tool that declares max_cost_usd().

The hard cap is only real if each declared bound is a true ceiling: finite,
non-negative, and never below what the exact request can bill -- including
provider-side escalations the estimate does not price (duration coercion,
"auto" tiers, unknown variants). Selector bounds must be the SELECTED
provider's bound: the selector itself never adds a charge, and an unbounded
provider must stay blocked even when reached through a selector.
"""

from __future__ import annotations

import importlib
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.base_tool import BaseTool, BudgetGateError, ToolResult, ToolRuntime
from tools.cost_tracker import ApprovalRequiredError, format_usd


def _make(module: str, cls: str) -> BaseTool:
    return getattr(importlib.import_module(module), cls)()


def _case(module, cls, inputs, id_):
    return pytest.param(module, cls, inputs, id=id_)


# One entry per newly bounded tool, with the billable-parameter variations
# that could plausibly break the bound: durations, counts, quality tiers,
# resolution tiers, unknown variant strings, and provider-chosen "auto".
BOUND_CASES = [
    # veo_video -- explicit backend avoids env-dependent resolution
    _case("tools.video.veo_video", "VeoVideo", {"backend": "google", "duration": "4s"}, "veo-google-4s-coercible"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "google", "duration": "8s"}, "veo-google-8s"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "google", "duration": "16s"}, "veo-google-16s"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "google", "duration": "nonsense"}, "veo-google-badduration"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "fal", "duration": "8s"}, "veo-fal-audio-default"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "fal", "duration": "8s", "generate_audio": False}, "veo-fal-noaudio"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "fal", "resolution": "4k", "duration": "8s"}, "veo-fal-4k"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "fal", "resolution": "8K-weird", "duration": "8s"}, "veo-fal-unknown-resolution"),
    _case("tools.video.veo_video", "VeoVideo", {"backend": "fal", "model_variant": "veo3.1/fast", "duration": "8s"}, "veo-fal-fast"),
    # gemini_omni_video -- clamp ceiling
    _case("tools.video.gemini_omni_video", "GeminiOmniVideo", {"prompt": "x"}, "gemini-default"),
    _case("tools.video.gemini_omni_video", "GeminiOmniVideo", {"prompt": "x", "duration": "3"}, "gemini-3s"),
    _case("tools.video.gemini_omni_video", "GeminiOmniVideo", {"prompt": "x", "duration": "30"}, "gemini-30s-clamped"),
    # kling_official_video
    _case("tools.video.kling_official_video", "KlingOfficialVideo", {"prompt": "x"}, "klingvid-default"),
    _case("tools.video.kling_official_video", "KlingOfficialVideo", {"prompt": "x", "mode": "4k", "duration": "10", "sound": "on"}, "klingvid-4k-10s-sound"),
    _case("tools.video.kling_official_video", "KlingOfficialVideo", {"prompt": "x", "mode": "hyperreal-9000"}, "klingvid-unknown-mode"),
    _case("tools.video.kling_official_video", "KlingOfficialVideo", {"prompt": "x", "api_family": "next-gen"}, "klingvid-unknown-family"),
    _case("tools.video.kling_official_video", "KlingOfficialVideo",
          {"prompt": "x", "api_family": "omni", "multi_prompt": [{"prompt": "a"}, {"prompt": "b"}],
           "video_list": [{"video_url": "https://e/x.mp4"}], "element_list": [1, 2]},
          "klingvid-omni-references"),
    # kling_official_image
    _case("tools.graphics.kling_official_image", "KlingOfficialImage", {"prompt": "x"}, "klingimg-default"),
    _case("tools.graphics.kling_official_image", "KlingOfficialImage", {"prompt": "x", "n": 3, "resolution": "4k"}, "klingimg-n3-4k"),
    _case("tools.graphics.kling_official_image", "KlingOfficialImage", {"prompt": "x", "resolution": "16k"}, "klingimg-unknown-resolution"),
    _case("tools.graphics.kling_official_image", "KlingOfficialImage",
          {"prompt": "x", "result_type": "series", "series_amount": "4"}, "klingimg-series"),
    # kling_tts
    _case("tools.audio.kling_tts", "KlingTTS", {"text": "hi"}, "klingtts-short"),
    _case("tools.audio.kling_tts", "KlingTTS", {"text": "word " * 2000}, "klingtts-long"),
    # openai_image
    _case("tools.graphics.openai_image", "OpenAIImage", {"prompt": "x", "quality": "low", "n": 1}, "openaiimg-low"),
    _case("tools.graphics.openai_image", "OpenAIImage", {"prompt": "x", "quality": "high", "n": 4}, "openaiimg-high-n4"),
    _case("tools.graphics.openai_image", "OpenAIImage", {"prompt": "x", "quality": "auto", "n": 2}, "openaiimg-auto"),
    _case("tools.graphics.openai_image", "OpenAIImage", {"prompt": "x", "quality": "mystery"}, "openaiimg-unknown-quality"),
    # dashscope_image
    _case("tools.graphics.dashscope_image", "DashscopeImage", {"prompt": "x"}, "dashscope-1"),
    _case("tools.graphics.dashscope_image", "DashscopeImage", {"prompt": "x", "n": 5}, "dashscope-5"),
    # TTS providers
    _case("tools.audio.elevenlabs_tts", "ElevenLabsTTS", {"text": "hello world"}, "elevenlabs"),
    _case("tools.audio.openai_tts", "OpenAITTS", {"text": "hello world"}, "openaitts"),
    _case("tools.audio.doubao_tts", "DoubaoTTS", {"text": "hello world"}, "doubao"),
    _case("tools.audio.dashscope_tts", "DashscopeTTS", {"text": "hello world"}, "dashscopetts"),
    _case("tools.audio.google_tts", "GoogleTTS", {"text": "hello", "voice": "en-US-Chirp3-HD-Orus"}, "gtts-chirp"),
    _case("tools.audio.google_tts", "GoogleTTS", {"text": "hello", "voice": "en-US-Studio-O"}, "gtts-studio"),
    _case("tools.audio.google_tts", "GoogleTTS", {"text": "hello", "voice": "en-US-FutureVoice-X"}, "gtts-unknown-voice"),
    # music
    _case("tools.audio.suno_music", "SunoMusic", {"prompt": "calm"}, "suno"),
    _case("tools.audio.music_gen", "MusicGen", {"prompt": "calm", "duration_seconds": 30}, "musicgen-30s"),
    _case("tools.audio.music_gen", "MusicGen", {"prompt": "calm", "duration_seconds": 180}, "musicgen-180s"),
    # image providers
    _case("tools.graphics.flux_image", "FluxImage", {"prompt": "x", "model": "flux-pro/v1.1"}, "flux-pro"),
    _case("tools.graphics.flux_image", "FluxImage", {"prompt": "x", "model": "flux-dev"}, "flux-dev"),
    _case("tools.graphics.flux_image", "FluxImage", {"prompt": "x", "model": "flux-ultra-9"}, "flux-unknown"),
    _case("tools.graphics.recraft_image", "RecraftImage", {"prompt": "x", "model": "v4"}, "recraft-v4"),
    _case("tools.graphics.recraft_image", "RecraftImage", {"prompt": "x", "model": "v4-pro"}, "recraft-v4pro"),
    _case("tools.graphics.recraft_image", "RecraftImage", {"prompt": "x", "model": "v5"}, "recraft-unknown"),
    _case("tools.graphics.google_imagen", "GoogleImagen", {"prompt": "x"}, "imagen-default"),
    _case("tools.graphics.google_imagen", "GoogleImagen", {"prompt": "x", "model": "imagen-4.0-ultra-generate-001", "number_of_images": 3}, "imagen-ultra-n3"),
    _case("tools.graphics.google_imagen", "GoogleImagen", {"prompt": "x", "model": "imagen-5-mystery"}, "imagen-unknown-model"),
    _case("tools.graphics.grok_image", "GrokImage", {"prompt": "x", "n": 2}, "grokimg-n2"),
    _case("tools.graphics.image_gen", "ImageGen", {"prompt": "x", "provider": "openai"}, "imagegen-openai"),
    _case("tools.graphics.image_gen", "ImageGen", {"prompt": "x", "provider": "flux"}, "imagegen-flux"),
    # video providers
    _case("tools.video.grok_video", "GrokVideo", {"prompt": "x", "duration": 10}, "grokvid-10s"),
    _case("tools.video.grok_video", "GrokVideo", {"prompt": "x", "duration": 5, "resolution": "480p"}, "grokvid-480p"),
    _case("tools.video.kling_video", "KlingVideo", {"prompt": "x", "model_variant": "v2.1/master", "duration": "10"}, "klingfal-master-10s"),
    _case("tools.video.kling_video", "KlingVideo", {"prompt": "x", "model_variant": "v4/imaginary"}, "klingfal-unknown-variant"),
    _case("tools.video.minimax_video", "MiniMaxVideo", {"prompt": "x", "model_variant": "hailuo-02/fast"}, "minimax-fast"),
    _case("tools.video.minimax_video", "MiniMaxVideo", {"prompt": "x", "model_variant": "hailuo-03/unknown"}, "minimax-unknown"),
    _case("tools.video.seedance_video", "SeedanceVideo", {"prompt": "x", "duration": "5"}, "seedance-5s"),
    _case("tools.video.seedance_video", "SeedanceVideo", {"prompt": "x", "duration": "auto"}, "seedance-auto"),
    _case("tools.video.seedance_replicate", "SeedanceReplicate", {"prompt": "x", "duration": "auto"}, "seedance-repl-auto"),
    _case("tools.video.runway_video", "RunwayVideo", {"prompt": "x", "model": "gen4_turbo", "duration": 10}, "runway-gen4"),
    _case("tools.video.runway_video", "RunwayVideo", {"prompt": "x", "model": "gen9_future", "duration": 5}, "runway-unknown-model"),
    _case("tools.video.higgsfield_video", "HiggsFieldVideo", {"prompt": "x", "model": "kling_3.0", "duration": 5}, "higgs-kling"),
    _case("tools.video.higgsfield_video", "HiggsFieldVideo", {"prompt": "x", "model": "mystery_model", "duration": 5}, "higgs-unknown-model"),
    _case("tools.video.ltx_video_modal", "LTXVideoModal", {"prompt": "x"}, "ltx-modal"),
    _case("tools.video.heygen_video", "HeyGenVideo", {"prompt": "x"}, "heygen-default"),
    _case("tools.video.heygen_video", "HeyGenVideo", {"prompt": "x", "provider_variant": "not-a-variant"}, "heygen-unknown-variant"),
    # azure_stt (bounded when duration is supplied)
    _case("tools.analysis.azure_stt", "AzureSpeechToText", {"input_path": "a.wav", "duration_seconds": 3600}, "azurestt-1h"),
]


@pytest.mark.parametrize("module,cls,inputs", BOUND_CASES)
def test_bound_is_declared_finite_and_covers_estimate(module, cls, inputs):
    tool = _make(module, cls)
    bound = tool.max_cost_usd(inputs)
    estimate = tool.estimate_cost(inputs)

    assert bound is not None, f"{tool.name} must declare a bound for {inputs}"
    assert isinstance(bound, (int, float)) and not isinstance(bound, bool)
    assert math.isfinite(bound)
    assert bound >= 0
    assert bound + 1e-9 >= estimate, (
        f"{tool.name}: bound {bound} below its own estimate {estimate} for {inputs}"
    )


# ---- Escalations the estimate does not price ----

def test_veo_bound_covers_auto_fix_duration_coercion():
    """auto_fix can raise a 4s request to 8 billed seconds; the bound for the
    4s request must cover the 8s reality."""
    from tools.video.veo_video import VeoVideo

    tool = VeoVideo()
    short = {"backend": "google", "duration": "4s"}
    coerced = {"backend": "google", "duration": "8s"}
    assert tool.max_cost_usd(short) >= tool.estimate_cost(coerced)


def test_openai_image_auto_quality_bounded_at_dearest_tier():
    from tools.graphics.openai_image import OpenAIImage

    tool = OpenAIImage()
    auto = {"prompt": "x", "quality": "auto", "n": 2}
    high = {"prompt": "x", "quality": "high", "n": 2}
    assert tool.max_cost_usd(auto) >= tool.estimate_cost(high)


def test_seedance_auto_duration_bounded_at_schema_maximum():
    from tools.video.seedance_video import SeedanceVideo

    tool = SeedanceVideo()
    auto = {"prompt": "x", "duration": "auto"}
    longest = {"prompt": "x", "duration": "15"}
    assert tool.max_cost_usd(auto) >= tool.estimate_cost(longest)


@pytest.mark.parametrize("known_mode", ["std", "pro", "4k"])
def test_kling_video_unknown_mode_bounds_above_every_known_mode(known_mode):
    from tools.video.kling_official_video import KlingOfficialVideo

    tool = KlingOfficialVideo()
    unknown = {"prompt": "x", "mode": "definitely-not-a-mode"}
    known = {"prompt": "x", "mode": known_mode}
    assert tool.max_cost_usd(unknown) >= tool.estimate_cost(known)


def test_google_tts_unknown_voice_bounds_at_dearest_family():
    from tools.audio.google_tts import GoogleTTS

    tool = GoogleTTS()
    text = "hello " * 100
    unknown = {"text": text, "voice": "en-US-FutureVoice-X"}
    studio = {"text": text, "voice": "en-US-Studio-O"}
    assert tool.max_cost_usd(unknown) >= tool.estimate_cost(studio)


# ---- Fail-closed paths that must stay fail-closed ----

@pytest.mark.parametrize(
    "module,cls",
    [
        ("tools.video.kling_official_video", "KlingOfficialVideo"),
        ("tools.graphics.kling_official_image", "KlingOfficialImage"),
        ("tools.audio.kling_tts", "KlingTTS"),
    ],
)
def test_kling_account_usage_requests_remain_unbounded(module, cls):
    """The account-usage diagnostic's billing is unverified: requesting it
    must return None (fail closed), never a number and never zero."""
    tool = _make(module, cls)
    inputs = {"prompt": "x", "text": "x", "include_account_usage": True}
    assert tool.max_cost_usd(inputs) is None


# ---- Selector bound contract ----

class _RecordingProvider(BaseTool):
    """Fake bounded paid provider; records whether execute was reached."""

    name = "fake_paid_provider"
    provider = "fake"
    capability = "image_generation"
    runtime = ToolRuntime.API

    def __init__(self):
        self.executed = False

    def estimate_cost(self, inputs):
        return 0.10

    def max_cost_usd(self, inputs):
        return 0.20

    def execute(self, inputs):
        self.executed = True
        return ToolResult(success=True, cost_usd=0.10)


class _UnboundedProvider(_RecordingProvider):
    name = "fake_unbounded_provider"

    def max_cost_usd(self, inputs):
        return None


def _selector_with(monkeypatch, provider):
    from tools.graphics.image_selector import ImageSelector

    monkeypatch.setattr(ImageSelector, "_providers", lambda self: [provider])
    monkeypatch.setattr(ImageSelector, "_filter_candidates", lambda self, i, c: c)
    monkeypatch.setattr(
        ImageSelector, "_select_best_tool", lambda self, i, c, t: (provider, None)
    )
    return ImageSelector()


def test_selector_bound_is_selected_providers_bound(monkeypatch):
    provider = _RecordingProvider()
    selector = _selector_with(monkeypatch, provider)
    assert selector.max_cost_usd({"prompt": "x"}) == pytest.approx(0.20)


def test_selector_bound_is_none_when_selected_provider_is_unbounded(monkeypatch):
    provider = _UnboundedProvider()
    selector = _selector_with(monkeypatch, provider)
    assert selector.max_cost_usd({"prompt": "x"}) is None


@pytest.mark.parametrize(
    "module,cls",
    [
        ("tools.graphics.image_selector", "ImageSelector"),
        ("tools.audio.tts_selector", "TTSSelector"),
        ("tools.video.video_selector", "VideoSelector"),
    ],
)
def test_selector_rank_mode_is_free_and_unbounded_by_zero(module, cls):
    """Rank mode never dispatches a provider: estimate and bound are both 0,
    so the gate treats it as the free call it is."""
    selector = _make(module, cls)
    inputs = {"prompt": "x", "text": "x", "operation": "rank"}
    assert selector.estimate_cost(inputs) == 0.0
    assert selector.max_cost_usd(inputs) == 0.0


def test_selector_with_no_candidates_is_free(monkeypatch):
    from tools.graphics.image_selector import ImageSelector

    monkeypatch.setattr(ImageSelector, "_providers", lambda self: [])
    selector = ImageSelector()
    assert selector.estimate_cost({"prompt": "x"}) == 0.0
    assert selector.max_cost_usd({"prompt": "x"}) == 0.0


def test_selector_cannot_silently_dispatch_unapproved_provider(monkeypatch, budget_gate_isolated):
    """Environment keys alone must never let a selector reach a paid provider:
    with the gate active and the selector unapproved, execute() is refused by
    the first-paid-use safeguard BEFORE the provider runs."""
    provider = _RecordingProvider()
    selector = _selector_with(monkeypatch, provider)
    with pytest.raises(ApprovalRequiredError):
        selector.execute({"prompt": "x"})
    assert provider.executed is False


def test_selector_with_unbounded_provider_is_blocked_even_when_approved(
    monkeypatch, budget_gate_isolated
):
    provider = _UnboundedProvider()
    selector = _selector_with(monkeypatch, provider)
    budget_gate_isolated.approve_tool("image_selector")
    with pytest.raises(BudgetGateError, match="image_selector"):
        selector.execute({"prompt": "x"})
    assert provider.executed is False


# ---- Operator message formatting ----

class TestUsdFormatting:
    def test_normal_amounts_keep_two_decimals(self):
        assert format_usd(3.2) == "$3.20"
        assert format_usd(10) == "$10.00"
        assert format_usd(0.5) == "$0.50"
        assert format_usd(0) == "$0.00"

    def test_sub_cent_positives_never_display_as_zero(self):
        assert format_usd(0.0018) == "$0.0018"
        assert format_usd(0.004) == "$0.0040"
        assert format_usd(0.000018) == "$0.000018"
        for value in (0.0049, 0.0001, 0.00003):
            assert format_usd(value) != "$0.00"
            assert float(format_usd(value).lstrip("$")) > 0

    def test_gate_refusal_shows_sub_cent_estimate(self):
        """The unbounded-tool refusal must show the true sub-cent estimate,
        not a misleading $0.00."""

        class TinyPaidTool(BaseTool):
            name = "tiny_paid"
            runtime = ToolRuntime.API

            def estimate_cost(self, inputs):
                return 0.0018

            def execute(self, inputs):
                return ToolResult(success=True)

        with pytest.raises(BudgetGateError) as exc:
            TinyPaidTool().execute({})
        assert "$0.0018" in str(exc.value)
        assert "$0.00 " not in str(exc.value)
