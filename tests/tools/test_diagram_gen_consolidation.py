"""The merged cache contract retains layout inputs and explicit fallback policy."""

import subprocess

import pytest

from tools.graphics.diagram_gen import DiagramGen, _mmdc_major_version, _mmdc_width_args


@pytest.mark.parametrize("change", [
    {"connections": [{"from": 0, "to": 1}]}, {"title": "Other"},
    {"theme": "light"}, {"width": 640}, {"height": 480},
    {"allow_text_fallback": True},
])
def test_render_controls_remain_part_of_cache_identity(change):
    inputs = {"diagram_type": "mermaid", "definition": "graph TD; A-->B"}
    tool = DiagramGen()
    assert tool.idempotency_key(inputs) != tool.idempotency_key({**inputs, **change})
    assert tool.cache_key(inputs) != tool.cache_key({**inputs, **change})


def test_omitted_false_fallback_normalization_survives_cache_field_union():
    inputs = {"diagram_type": "mermaid", "definition": "graph TD; A-->B"}
    tool = DiagramGen()
    assert tool.idempotency_key(inputs) == tool.idempotency_key(
        {**inputs, "allow_text_fallback": False}
    )
    assert tool.cache_key(inputs) == tool.cache_key({**inputs, "allow_text_fallback": False})


@pytest.mark.parametrize("version,flag", [("11.12.0", "-w"), ("12.0.0", "--size")])
def test_mermaid_cli_width_compatibility_is_preserved(monkeypatch, version, flag):
    _mmdc_major_version.cache_clear()
    monkeypatch.setattr("tools.graphics.diagram_gen.shutil.which", lambda _: "mock-mmdc")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, version, "")

    monkeypatch.setattr("tools.graphics.diagram_gen.subprocess.run", fake_run)
    try:
        assert _mmdc_width_args(640) == [flag, "640"]
        assert _mmdc_width_args(800) == [flag, "800"]
        assert calls == [["mock-mmdc", "--version"]]
    finally:
        _mmdc_major_version.cache_clear()
