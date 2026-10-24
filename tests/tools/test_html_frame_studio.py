"""Focused tests for the HTML Scene Studio (H2F2V) tool.

No browser, no network: playwright is imported lazily inside _render, so
these tests cover the pure planning layer — step validation, manifest
building, concat timing, and the status/guardrail contract.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolRuntime, ToolStatus
from tools.tool_registry import ToolRegistry
from tools.graphics.html_frame_studio import HtmlFrameStudio


def _steps() -> list[dict]:
    return [
        {"name": "intro", "data_step": 1, "duration": 2.5},
        {"name": "scan", "data_step": 2},
        {"name": "hit", "evaluate": "document.getElementById('x').classList.add('on')", "duration": 3.0},
    ]


# ---- Contract ----

def test_contract_fields():
    tool = HtmlFrameStudio()
    assert isinstance(tool, BaseTool)
    assert tool.capability == "graphics"
    assert tool.provider == "playwright"
    assert tool.runtime is ToolRuntime.LOCAL
    assert tool.input_schema["required"] == ["html_path", "output_dir", "steps"]


def test_registry_discovery():
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("html_frame_studio") is not None
    graphics_tools = [t.name for t in registry.get_by_capability("graphics")]
    assert "html_frame_studio" in graphics_tools


# ---- Step validation ----

def test_empty_steps_rejected():
    assert HtmlFrameStudio._validate_steps([]) == ["steps must be a non-empty list"]
    assert HtmlFrameStudio._validate_steps(None) == ["steps must be a non-empty list"]


def test_step_needs_data_step_or_evaluate():
    errors = HtmlFrameStudio._validate_steps([{"name": "no-op", "duration": 1.0}])
    assert any("data_step' or 'evaluate" in e for e in errors)


def test_bad_duration_and_wait_rejected():
    steps = [{"data_step": 1, "duration": 0}, {"data_step": 2, "wait_ms": -5}]
    errors = HtmlFrameStudio._validate_steps(steps)
    assert any("duration" in e for e in errors)
    assert any("wait_ms" in e for e in errors)


def test_valid_steps_pass():
    assert HtmlFrameStudio._validate_steps(_steps()) == []


# ---- Manifest & timing ----

def test_manifest_defaults_and_ordering():
    steps = _steps()
    manifest = HtmlFrameStudio._build_manifest(
        steps,
        html_path="scene.html",
        viewport={"width": 1080, "height": 1920},
        device_scale_factor=2,
        transparent=False,
        frame_prefix="frame",
    )
    assert [f["file"] for f in manifest["frames"]] == [
        "frame_0001.png",
        "frame_0002.png",
        "frame_0003.png",
    ]
    assert manifest["frames"][0]["step"] == "intro"
    assert manifest["frames"][1]["duration"] == 2.0  # default applied
    assert manifest["frames"][2]["duration"] == 3.0
    assert manifest["total_duration"] == 7.5
    assert manifest["concat_file"] == "frames.txt"


def test_concat_lines_honor_durations_and_repeat_last():
    manifest = HtmlFrameStudio._build_manifest(
        _steps(),
        html_path="s.html",
        viewport={"width": 1920, "height": 1080},
        device_scale_factor=1,
        transparent=False,
        frame_prefix="f",
    )
    lines = HtmlFrameStudio._concat_lines(manifest).strip().splitlines()
    assert lines[0] == "file 'f_0001.png'"
    assert lines[1] == "duration 2.5"
    # last frame repeated so its duration is honored by the concat demuxer
    assert lines[-1] == "file 'f_0003.png'"
    assert lines[-2] == "duration 3.0"


def test_data_step_js_sets_body_dataset():
    assert (
        HtmlFrameStudio._data_step_js(3)
        == 'document.body.dataset.step = "3"'
    )


# ---- Guardrails ----

def test_execute_rejects_invalid_steps_before_browser():
    result = HtmlFrameStudio().execute(
        {"html_path": "x.html", "output_dir": "y", "steps": [{}]}
    )
    assert not result.success
    assert "Invalid steps" in result.error


def test_execute_reports_missing_html_without_browser(tmp_path):
    # Valid steps + missing file must fail on the file check, not on playwright
    result = HtmlFrameStudio().execute(
        {
            "html_path": str(tmp_path / "nope.html"),
            "output_dir": str(tmp_path / "out"),
            "steps": [{"data_step": 1}],
        }
    )
    assert not result.success
    assert "Scene HTML not found" in result.error


def test_status_unavailable_without_playwright(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _no_playwright(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_playwright)
    assert HtmlFrameStudio().get_status() is ToolStatus.UNAVAILABLE


def test_estimate_cost_is_zero():
    assert HtmlFrameStudio().estimate_cost({}) == 0.0
