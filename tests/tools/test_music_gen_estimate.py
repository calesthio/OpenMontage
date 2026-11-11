"""music_gen: the estimate prices the track _generate() asks for.

``estimate_cost`` raises without ``duration_seconds`` while ``_generate``
returns a clean failure for the same input. ``execute()`` used to price every
result, so a call with no duration raised the estimator's ValueError instead of
returning _generate's error. A stub ``requests`` module stands in for the API.
"""

from __future__ import annotations

import sys
import types

import pytest

from tools.audio.music_gen import MusicGen


class _FakeResponse:
    content = b"audio"

    def raise_for_status(self) -> None:
        return None


def _stub_requests(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        captured["payload"] = json
        return _FakeResponse()

    fake.post = fake_post  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "requests", fake)


@pytest.fixture()
def tool(monkeypatch: pytest.MonkeyPatch) -> MusicGen:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-not-real")
    return MusicGen()


def test_missing_duration_returns_the_generate_error(
    tool: MusicGen, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}
    _stub_requests(monkeypatch, captured)

    result = tool.execute({"prompt": "calm piano"})

    assert result.success is False
    assert "duration_seconds is required" in (result.error or "")
    assert not result.cost_usd
    assert "payload" not in captured, "no request may be sent without a duration"


def test_estimate_prices_the_length_that_is_requested(
    tool: MusicGen, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured: dict = {}
    _stub_requests(monkeypatch, captured)

    result = tool.execute(
        {"prompt": "calm piano", "duration_seconds": 90, "output_path": str(tmp_path / "m.mp3")}
    )

    assert result.success is True
    assert captured["payload"]["music_length_ms"] == 90_000
    requested_seconds = captured["payload"]["music_length_ms"] / 1000
    assert result.cost_usd == tool.estimate_cost({"duration_seconds": requested_seconds})
    assert tool.estimate_cost({"duration_seconds": 90}) > tool.estimate_cost({"duration_seconds": 30})
