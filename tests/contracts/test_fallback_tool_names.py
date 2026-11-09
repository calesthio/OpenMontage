"""Every declared fallback must name a tool the registry can resolve.

`registry.find_fallback()` looks each name up with `registry.get()`, which is
keyed by tool *name*. `screen_capture_selector` built its list from
`_providers()`, a dict keyed by `tool.provider`, so it advertised `["cap",
"ffmpeg"]` — neither of which is a tool name. `find_fallback()` returned None
even with both `cap_recorder` and `screen_recorder` AVAILABLE, and preflight
("Check `fallback_tools` for unavailable tools", AGENT_GUIDE.md) had nothing
to look up.

`get_info()` republishes the list into the support envelope, described in
tool_registry as "the primary report the orchestrator uses", so an
unresolvable name propagates to every consumer of that report.

The registry is iterated rather than named so a newly added tool is covered
the moment it is discovered.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import ToolStatus  # noqa: E402
from tools.tool_registry import registry  # noqa: E402


def _declared_fallbacks() -> list[tuple[str, str]]:
    registry.discover()
    pairs: list[tuple[str, str]] = []
    for name, tool in sorted(registry._tools.items()):
        declared = list(tool.fallback_tools or [])
        if tool.fallback and tool.fallback not in declared:
            declared.append(tool.fallback)
        pairs.extend((name, fb) for fb in declared)
    return pairs


FALLBACKS = _declared_fallbacks()


def test_some_tools_declare_a_fallback() -> None:
    """Guard against the parametrized test below silently covering nothing."""
    assert FALLBACKS


@pytest.mark.parametrize(("tool", "fallback"), FALLBACKS, ids=lambda v: str(v))
def test_declared_fallback_names_a_registered_tool(tool: str, fallback: str) -> None:
    registry.discover()
    assert registry.get(fallback) is not None, (
        f"{tool} declares fallback {fallback!r}, which is not a registered "
        f"tool name — registry.find_fallback({tool!r}) cannot resolve it"
    )


def test_selector_falls_back_while_a_provider_is_available() -> None:
    """The end the defect was actually visible from.

    Availability is derived from the capability, not from `fallback_tools` —
    reading the list under test to decide whether to assert on it is how this
    defect stays invisible: unresolvable names look like "no providers".
    """
    registry.discover()

    for selector, capability in (
        ("screen_capture_selector", "screen_capture"),
        ("tts_selector", "tts"),
        ("image_selector", "image_generation"),
        ("video_selector", "video_generation"),
    ):
        if registry.get(selector) is None:
            continue
        providers = [
            t for t in registry.get_by_capability(capability)
            if t.name != selector and t.get_status() == ToolStatus.AVAILABLE
        ]
        if not providers:
            continue

        assert registry.find_fallback(selector) is not None, (
            f"{selector} has available providers "
            f"{[t.name for t in providers]} but find_fallback returned None"
        )
