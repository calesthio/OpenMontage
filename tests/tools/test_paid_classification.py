"""Paid/free classification: a zero estimate can no longer bypass the gate.

The gate previously trusted `estimate_cost() > 0` to decide whether a call
was paid, so a paid API whose estimate returned 0 -- sub-cent rounding,
unknown duration, missing billing info -- ran ungated. Classification now
comes from `BaseTool.paid` (API/HYBRID default to paid; genuinely free
tools declare `paid = False`), and a paid tool must produce a bound even
for a zero estimate. These tests pin that contract for the two real tools
that had the hole (azure_stt, dashscope_asr) and for selector routing.

No real provider client is constructed anywhere here: requests is
monkeypatched to explode on contact, and all audio is a local stdlib-`wave`
fixture.
"""

from __future__ import annotations

import shutil
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.analysis.azure_stt import AzureSpeechToText
from tools.analysis.dashscope_asr import DashscopeAsr
from tools.base_tool import BaseTool, BudgetGateError, ToolResult, ToolRuntime

HAS_FFPROBE = shutil.which("ffprobe") is not None


def _write_real_wav(path: Path, seconds: float = 2.0, rate: int = 8000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return path


def _forbid_network(monkeypatch):
    """Any HTTP attempt in these tests is a test failure, not a charge."""
    import requests

    def _explode(*args, **kwargs):
        raise AssertionError("network dispatch attempted -- gate failed")

    monkeypatch.setattr(requests, "post", _explode)
    monkeypatch.setattr(requests, "get", _explode)


# ---- The classification itself ----

class TestClassification:
    def test_azure_and_dashscope_are_explicitly_paid(self):
        assert AzureSpeechToText.paid is True
        assert DashscopeAsr.paid is True

    def test_stock_search_tools_are_explicitly_free(self):
        from tools.audio.freesound_music import FreesoundMusic
        from tools.graphics.pexels_image import PexelsImage
        from tools.graphics.pixabay_image import PixabayImage

        for cls in (FreesoundMusic, PexelsImage, PixabayImage):
            assert cls.paid is False, f"{cls.__name__} must stay declared-free"

    def test_every_free_declaration_estimates_zero(self):
        """A tool may only claim paid = False while its estimate agrees."""
        from tools.tool_registry import ToolRegistry

        registry = ToolRegistry()
        registry.discover()
        free_tools = [
            t for t in registry._tools.values() if getattr(t, "paid", None) is False
        ]
        assert free_tools, "expected explicit free classifications in the registry"
        for tool in free_tools:
            assert tool.estimate_cost({}) == 0.0, (
                f"{tool.name} declares paid=False but estimates money"
            )


# ---- Azure STT: locally derived bound ----

class TestAzureSttBound:
    @pytest.fixture
    def azure_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")

    @pytest.mark.skipif(not HAS_FFPROBE, reason="ffprobe not on PATH")
    def test_bound_derived_from_local_audio_probe(self, azure_env, tmp_path):
        audio = _write_real_wav(tmp_path / "two_seconds.wav", seconds=2.0)
        tool = AzureSpeechToText()
        inputs = {"input_path": str(audio)}

        bound = tool.max_cost_usd(inputs)
        assert bound is not None and bound > 0
        # ~2s at $1/audio-hour, allowing for container rounding.
        assert bound == pytest.approx(2.0 / 3600.0, rel=0.25)
        assert tool.estimate_cost(inputs) == pytest.approx(bound)

    def test_explicit_duration_still_priced_exactly(self):
        tool = AzureSpeechToText()
        assert tool.max_cost_usd({"duration_seconds": 3600}) == pytest.approx(1.0)
        assert tool.estimate_cost({"duration_seconds": 3600}) == pytest.approx(1.0)

    def test_unprobeable_file_is_unbounded_and_blocked_before_dispatch(
        self, azure_env, tmp_path, monkeypatch, budget_gate_isolated
    ):
        budget_gate_isolated.approve_tool("azure_stt")
        _forbid_network(monkeypatch)
        garbage = tmp_path / "garbage.wav"
        garbage.write_bytes(b"this is not audio")

        tool = AzureSpeechToText()
        assert tool.max_cost_usd({"input_path": str(garbage)}) is None
        with pytest.raises(BudgetGateError, match="azure_stt"):
            tool.execute({"input_path": str(garbage)})

    def test_missing_file_and_missing_credentials_stay_graceful(
        self, monkeypatch, tmp_path, budget_gate_isolated
    ):
        """Guaranteed-local refusals bill nothing and keep their error UX."""
        _forbid_network(monkeypatch)
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
        res = AzureSpeechToText().execute({"input_path": str(tmp_path / "nope.wav")})
        assert not res.success and "not found" in res.error.lower()

        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        existing = tmp_path / "exists.wav"
        existing.write_bytes(b"unprobeable")
        res = AzureSpeechToText().execute({"input_path": str(existing)})
        assert not res.success and "not configured" in res.error.lower()


# ---- DashScope ASR: paid, unbounded, blocked ----

class TestDashscopeAsrBlocked:
    def test_dispatchable_request_is_blocked_before_provider(
        self, monkeypatch, budget_gate_isolated
    ):
        """No repository-verified pricing exists, so a request that would
        reach DashScope must be refused as a paid tool without a declared
        maximum cost -- and the refusal must say so."""
        budget_gate_isolated.approve_tool("dashscope_asr")
        _forbid_network(monkeypatch)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")

        tool = DashscopeAsr()
        inputs = {"audio_url": "https://example.com/audio.mp3"}
        assert tool.max_cost_usd(inputs) is None
        with pytest.raises(BudgetGateError) as exc:
            tool.execute(inputs)
        message = str(exc.value)
        assert "dashscope_asr" in message
        assert "PAID" in message
        assert "bounded maximum cost" in message

    def test_local_guardrails_still_answer_gracefully(self, monkeypatch, budget_gate_isolated):
        _forbid_network(monkeypatch)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-key")
        res = DashscopeAsr().execute({"audio_url": "/local/path.mp3"})
        assert not res.success and "publicly accessible URL" in res.error

        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        res = DashscopeAsr().execute({"audio_url": "https://example.com/a.mp3"})
        assert not res.success and "DASHSCOPE_API_KEY" in res.error


# ---- Selector routing cannot launder a zero estimate ----

class _ZeroEstimatePaidProvider(BaseTool):
    """Paid API provider whose estimate is 0 and which declares no bound --
    the exact shape that used to bypass the gate."""

    name = "zero_estimate_paid_provider"
    provider = "fake"
    capability = "tts"
    runtime = ToolRuntime.API

    def __init__(self):
        self.executed = False

    def estimate_cost(self, inputs):
        return 0.0

    def execute(self, inputs):
        self.executed = True
        return ToolResult(success=True)


class _FreeProvider(_ZeroEstimatePaidProvider):
    name = "declared_free_provider"
    paid = False


def _tts_selector_with(monkeypatch, provider):
    from tools.audio.tts_selector import TTSSelector

    monkeypatch.setattr(TTSSelector, "_providers", lambda self: [provider])
    monkeypatch.setattr(
        TTSSelector, "_select_best_tool", lambda self, i, c, t: (provider, None)
    )
    return TTSSelector()


class TestSelectorRouting:
    def test_selector_routed_zero_estimate_paid_provider_is_blocked(
        self, monkeypatch, budget_gate_isolated
    ):
        provider = _ZeroEstimatePaidProvider()
        selector = _tts_selector_with(monkeypatch, provider)
        budget_gate_isolated.approve_tool("tts_selector")

        assert selector.max_cost_usd({"text": "x"}) is None
        with pytest.raises(BudgetGateError, match="tts_selector"):
            selector.execute({"text": "x"})
        assert provider.executed is False

    def test_selector_routed_declared_free_provider_still_runs(
        self, monkeypatch, budget_gate_isolated
    ):
        provider = _FreeProvider()
        selector = _tts_selector_with(monkeypatch, provider)

        assert selector.max_cost_usd({"text": "x"}) == 0.0
        result = selector.execute({"text": "x"})
        assert result.success and provider.executed
        # Free routing writes nothing to the ledger.
        import os
        assert not Path(os.environ["OPENMONTAGE_COST_LOG"]).exists()
