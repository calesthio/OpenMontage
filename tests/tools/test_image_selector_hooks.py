"""Optional per-request hooks honoured by ImageSelector and provider_routing.

A provider may define two duck-typed hooks:

- ``accepts_image_input(inputs) -> bool``: whether *this request* can use a
  reference image (e.g. the selected template/workflow takes an input image).
- ``get_status_for(inputs) -> ToolStatus``: readiness for *this request*.

Tools without the hooks keep the static behaviour (schema keys /
``supports["image_edit"]`` and ``get_status()``).

These tests use stub providers injected through ``_providers`` so the global
tool registry is never touched.
"""

from __future__ import annotations

from typing import Any

import pytest

from tools.base_tool import ToolResult, ToolStatus
from tools.graphics.image_selector import ImageSelector
from tools.provider_routing import filter_explicit_route


class _PlainTool:
    """Image provider without hooks: static schema and global status."""

    capability = "image_generation"

    def __init__(
        self,
        name: str,
        *,
        schema_keys: tuple[str, ...] = ("prompt",),
        status: ToolStatus = ToolStatus.AVAILABLE,
    ) -> None:
        self.name = name
        self.provider = name
        self.supports: dict[str, Any] = {}
        self.input_schema = {"properties": {k: {} for k in schema_keys}}
        self._status = status
        self.last_inputs: dict[str, Any] | None = None

    def get_status(self) -> ToolStatus:
        return self._status

    def get_info(self) -> dict[str, Any]:
        return {"name": self.name, "provider": self.provider, "agent_skills": []}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        self.last_inputs = dict(inputs)
        return ToolResult(success=True, data={})


class _TemplateTool(_PlainTool):
    """Provider that runs one of several templates, chosen by ``workflow``.

    Only the ``edit`` template takes an input image, and only the ``edit``
    template's model is installed; the default template is text-only.
    """

    def __init__(self, name: str = "template_tool", **kwargs: Any) -> None:
        kwargs.setdefault("status", ToolStatus.DEGRADED)
        super().__init__(name, **kwargs)

    def accepts_image_input(self, inputs: dict[str, Any]) -> bool:
        return inputs.get("workflow") == "edit"

    def get_status_for(self, inputs: dict[str, Any]) -> ToolStatus:
        if inputs.get("workflow") == "edit":
            return ToolStatus.AVAILABLE
        return ToolStatus.DEGRADED


class _Score:
    def __init__(self, tool: _PlainTool) -> None:
        self.provider = tool.provider
        self.tool_name = tool.name

    def explain(self) -> str:
        return self.tool_name

    def to_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "tool_name": self.tool_name}


@pytest.fixture
def selector(monkeypatch: pytest.MonkeyPatch):
    def _make(*tools: _PlainTool) -> ImageSelector:
        sel = ImageSelector()
        monkeypatch.setattr(sel, "_providers", lambda: list(tools))
        monkeypatch.setattr(
            "lib.scoring.rank_providers",
            lambda candidates, ctx: [_Score(t) for t in candidates],
        )
        return sel

    return _make


EDIT = {"prompt": "x", "image_path": "ref.png"}


# --- _filter_candidates ------------------------------------------------------


def test_edit_request_keeps_hook_tool_only_when_it_accepts_images(selector):
    tool = _TemplateTool()
    sel = selector(tool)
    assert sel._filter_candidates({**EDIT, "workflow": "edit"}, [tool]) == [tool]
    assert sel._filter_candidates({**EDIT, "workflow": "t2i"}, [tool]) == []


def test_hook_overrides_static_schema(selector):
    # Declares image_path in its schema, but the hook says this request can't.
    tool = _TemplateTool(schema_keys=("prompt", "image_path"))
    sel = selector(tool)
    assert sel._filter_candidates({**EDIT, "workflow": "t2i"}, [tool]) == []


def test_tools_without_hooks_keep_static_edit_filter(selector):
    text_only = _PlainTool("text_only")
    editor = _PlainTool("editor", schema_keys=("prompt", "image_path"))
    sel = selector(text_only, editor)
    assert sel._filter_candidates(EDIT, [text_only, editor]) == [editor]
    # Non-edit requests are unaffected.
    assert sel._filter_candidates({"prompt": "x"}, [text_only, editor]) == [
        text_only,
        editor,
    ]


# --- provider_routing.filter_explicit_route ---------------------------------


def test_explicit_route_honours_hook_with_preferred_tool():
    tool = _TemplateTool()
    inputs = {**EDIT, "preferred_tool": tool.name}
    assert filter_explicit_route({**inputs, "workflow": "edit"}, [tool]) == [tool]
    assert filter_explicit_route({**inputs, "workflow": "t2i"}, [tool]) == []


def test_explicit_route_without_hook_unchanged():
    text_only = _PlainTool("text_only")
    editor = _PlainTool("editor", schema_keys=("prompt", "image_path"))
    assert filter_explicit_route({**EDIT, "preferred_tool": "text_only"}, [text_only]) == []
    assert filter_explicit_route({**EDIT, "preferred_tool": "editor"}, [editor]) == [editor]


# --- _tool_selectable --------------------------------------------------------


def test_selectability_follows_get_status_for(selector):
    tool = _TemplateTool()  # get_status() is DEGRADED
    sel = selector(tool)
    assert sel._tool_selectable(tool, {"prompt": "x", "workflow": "edit"}) is True
    assert sel._tool_selectable(tool, {"prompt": "x", "workflow": "t2i"}) is False


def test_selectability_without_hook_uses_get_status(selector):
    ok = _PlainTool("ok")
    degraded = _PlainTool("degraded", status=ToolStatus.DEGRADED)
    sel = selector(ok, degraded)
    assert sel._tool_selectable(ok, {"prompt": "x"}) is True
    assert sel._tool_selectable(degraded, {"prompt": "x"}) is False


# --- execute (end to end through the selector) ------------------------------


def test_execute_routes_edit_request_to_hook_tool_and_forwards_image_path(selector):
    tool = _TemplateTool()
    sel = selector(tool)
    result = sel.execute({**EDIT, "workflow": "edit", "preferred_tool": tool.name})
    assert result.success, result.error
    assert result.data["selected_tool"] == tool.name
    assert tool.last_inputs["image_path"] == "ref.png"


def test_hook_only_covers_image_path():
    # Documented limit: the hook only stands in for ``image_path``. List/URL
    # reference keys (``image_paths``, ``image_url``, ``image_urls``) still need
    # to be declared in the tool's schema, as before.
    tool = _TemplateTool()
    inputs = {**EDIT, "workflow": "edit", "image_urls": ["https://example.com/a.png"]}
    assert filter_explicit_route(inputs, [tool]) == []


def test_execute_without_hooks_strips_image_path_for_text_only_tool(selector):
    text_only = _PlainTool("text_only")
    sel = selector(text_only)
    # Not an edit request, but image keys a tool doesn't declare are stripped.
    result = sel.execute({"prompt": "x"})
    assert result.success
    assert text_only.last_inputs == {"prompt": "x"}
    # Edit request with no image-capable provider: nothing is selected.
    assert sel.execute(EDIT).success is False
