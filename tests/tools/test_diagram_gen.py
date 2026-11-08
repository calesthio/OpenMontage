from __future__ import annotations

from tools.base_tool import ToolStatus
from tools.graphics.diagram_gen import DiagramGen
from tools.tool_registry import ToolRegistry


def test_diagram_gen_reports_operation_statuses(monkeypatch):
    tool = DiagramGen()
    monkeypatch.setattr(tool, "_has_mermaid", lambda: False)
    monkeypatch.setattr(tool, "_has_pillow", lambda: True)

    assert tool.get_status() == ToolStatus.DEGRADED
    assert tool.get_info()["operation_statuses"] == {
        "mermaid": "unavailable",
        "flowchart": "available",
        "boxes": "available",
    }


def test_mermaid_without_cli_fails_unless_text_fallback_is_explicit(monkeypatch, tmp_path):
    tool = DiagramGen()
    monkeypatch.setattr(tool, "_has_mermaid", lambda: False)

    inputs = {
        "diagram_type": "mermaid",
        "definition": "graph LR\n  A-->B",
        "output_path": str(tmp_path / "diagram.png"),
    }
    result = tool.execute(inputs)
    assert result.success is False
    assert "npm install -g @mermaid-js/mermaid-cli" in (result.error or "")

    fallback = tool.execute({**inputs, "allow_text_fallback": True})
    assert fallback.success is True
    assert fallback.data["method"] == "text_card"
    assert tool.idempotency_key(inputs) == tool.idempotency_key(
        {**inputs, "allow_text_fallback": False}
    )
    assert tool.idempotency_key(inputs) != tool.idempotency_key(
        {**inputs, "allow_text_fallback": True}
    )


def test_mermaid_cli_path_stays_available(monkeypatch, tmp_path):
    tool = DiagramGen()
    monkeypatch.setattr(tool, "_has_mermaid", lambda: True)
    monkeypatch.setattr(tool, "_has_pillow", lambda: True)
    monkeypatch.setattr(tool, "run_command", lambda *args, **kwargs: None)

    result = tool.execute({
        "diagram_type": "mermaid",
        "definition": "graph LR\n  A-->B",
        "output_path": str(tmp_path / "diagram.png"),
    })

    assert tool.get_status() == ToolStatus.AVAILABLE
    assert result.success is True
    assert result.data["method"] == "mermaid-cli"


def test_provider_menu_summary_warns_when_mermaid_is_missing(monkeypatch):
    monkeypatch.setattr(DiagramGen, "_has_mermaid", lambda self: False)
    registry = ToolRegistry()
    registry.discover()

    assert any(
        warning.startswith("diagram_gen: Mermaid CLI (mmdc) is unavailable")
        for warning in registry.provider_menu_summary()["runtime_warnings"]
    )
