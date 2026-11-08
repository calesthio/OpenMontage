"""An explicit model must not eliminate a tool whose model field is open-ended.

``filter_explicit_route`` decides model support from declared vocabularies
(schema ``enum``, ``_MODELS``, ``_MODEL_ALIASES``, ``model_catalog``). Tools such
as ``openai_tts``, ``piper_tts`` and ``local_diffusion`` take a free-form model
string, so they declare no vocabulary — and were dropped for *every* model,
including their own schema default — even when the caller named the tool or
its provider. ``tts_selector(preferred_provider="openai", model="tts-1-hd")``
then answered "No TTS provider available." although it worked before the
routing filter was added.

An open field cannot vouch for a model, so it is honored only when the caller
targeted that tool and no other candidate declares the model; in auto mode an
unknown model must still fail cleanly rather than land on whichever free-form
tool ranks first.

The registry is iterated so a tool added later is covered automatically, and
each tool's own schema default is the independent witness of a model it accepts.
"""

from unittest import mock

import pytest

from tools.base_tool import ToolResult, ToolStatus
from tools.provider_routing import filter_explicit_route
from tools.tool_registry import registry

MODEL_FIELDS = ("model", "model_id", "model_name")
ROUTED_CAPABILITIES = ("tts", "image_generation", "video_generation")


def _default_model_cases():
    registry.discover()
    cases = []
    for name, tool in sorted(registry._tools.items()):
        if tool.capability not in ROUTED_CAPABILITIES or name.endswith("selector"):
            continue
        props = tool.input_schema.get("properties", {})
        for field in MODEL_FIELDS:
            default = props.get(field, {}).get("default")
            if isinstance(default, str) and default:
                cases.append((name, field, default))
    return cases


CASES = _default_model_cases()


def test_default_model_cases_found():
    assert len(CASES) > 10
    # The open-ended fields this test exists for must be among them.
    assert {"openai_tts", "piper_tts", "local_diffusion"} <= {c[0] for c in CASES}


@pytest.mark.parametrize(("name", "field", "default"), CASES)
def test_targeted_tool_survives_its_own_default_model(name, field, default):
    tool = registry._tools[name]
    assert filter_explicit_route({field: default, "preferred_tool": name}, [tool]) == [
        tool
    ]


def test_open_field_tool_needs_targeting():
    registry.discover()
    piper = registry._tools["piper_tts"]
    assert filter_explicit_route({"model": "tts-1-hd"}, [piper]) == []


def test_tool_without_model_field_is_still_excluded():
    registry.discover()
    azure = registry._tools["azure_tts"]
    assert not any(f in azure.input_schema.get("properties", {}) for f in MODEL_FIELDS)
    assert filter_explicit_route({"model": "tts-1-hd"}, [azure]) == []


def test_declared_vocabulary_still_rejects_unknown_model():
    registry.discover()
    eleven = registry._tools["elevenlabs_tts"]
    assert filter_explicit_route({"model_id": "not-a-model"}, [eleven]) == []


def test_tts_selector_forwards_explicit_model_to_open_field_tool(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    registry.discover()
    selector = registry._tools["tts_selector"]
    openai_tts = registry._tools["openai_tts"]
    calls = []

    def fake_execute(inputs):
        calls.append(inputs)
        return ToolResult(success=True, data={})

    with mock.patch.object(openai_tts, "execute", fake_execute), mock.patch.object(
        openai_tts, "get_status", lambda: ToolStatus.AVAILABLE
    ):
        result = selector.execute(
            {"text": "hi", "preferred_provider": "openai", "model": "tts-1-hd"}
        )

    assert result.success, result.error
    assert result.data["selected_tool"] == "openai_tts"
    assert calls[0]["model"] == "tts-1-hd"


def test_tts_selector_auto_mode_does_not_misroute_unknown_model(monkeypatch):
    registry.discover()
    selector = registry._tools["tts_selector"]
    calls = []
    for tool in selector._providers():
        monkeypatch.setattr(tool, "get_status", lambda: ToolStatus.AVAILABLE)
        monkeypatch.setattr(
            tool,
            "execute",
            lambda inputs, name=tool.name: calls.append(name)
            or ToolResult(success=True, data={}),
        )

    result = selector.execute({"text": "hi", "model": "tts-1-hd"})

    assert calls == []
    assert not result.success


def test_declared_model_beats_preferred_open_field_provider(monkeypatch):
    """preferred_provider is soft: a tool that declares the model must win."""
    registry.discover()
    selector = registry._tools["tts_selector"]
    calls = []
    for tool in selector._providers():
        monkeypatch.setattr(tool, "get_status", lambda: ToolStatus.AVAILABLE)
        monkeypatch.setattr(
            tool,
            "execute",
            lambda inputs, name=tool.name: calls.append(name)
            or ToolResult(success=True, data={}),
        )

    result = selector.execute(
        {
            "text": "hi",
            "preferred_provider": "openai",
            "model": "eleven_multilingual_v2",
        }
    )

    assert result.success, result.error
    assert calls and calls[0] != "openai_tts"
    assert calls[0] in {"elevenlabs_tts", "fal_elevenlabs_tts"}
