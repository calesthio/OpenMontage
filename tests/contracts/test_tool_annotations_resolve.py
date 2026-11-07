"""Every tool's contract methods must survive type introspection.

`from __future__ import annotations` (PEP 563) makes annotations lazy strings,
so a missing `from typing import Any` costs nothing at import time and the
tool registers normally. It only detonates when something actually resolves
the hints — schema generation, doc tooling, pydantic validation over the tool
contract, or any future JSON-schema export of `input_schema`.

Regression: `tools/video/hunyuan_video.py` annotated three signatures with
`dict[str, Any]` and never imported `Any`. It sat there registering fine while
`get_type_hints(HunyuanVideo.execute)` raised NameError. `make lint` compiled
four files out of 517 and never looked.

This test resolves the hints for real, so the next one fails in CI.
"""

from typing import get_type_hints

import pytest

from tools.tool_registry import registry

CONTRACT_METHODS = ("execute", "estimate_cost", "estimate_runtime", "dry_run")


def _tool_methods() -> list[tuple[str, str]]:
    registry.discover()
    pairs: list[tuple[str, str]] = []
    for name, tool in sorted(registry._tools.items()):
        for method in CONTRACT_METHODS:
            if callable(getattr(type(tool), method, None)):
                pairs.append((name, method))
    return pairs


TOOL_METHODS = _tool_methods()


def test_registry_actually_discovered_tools() -> None:
    assert TOOL_METHODS, "registry.discover() found no tools to introspect"


@pytest.mark.parametrize(("tool", "method"), TOOL_METHODS, ids=lambda v: str(v))
def test_contract_method_annotations_resolve(tool: str, method: str) -> None:
    impl = getattr(type(registry._tools[tool]), method)
    # Unwrap the Backlot event instrumentation so we read the tool's own
    # signature rather than the wrapper's (*args, **kwargs).
    impl = getattr(impl, "__wrapped__", impl)
    try:
        get_type_hints(impl)
    except NameError as exc:
        pytest.fail(
            f"{tool}.{method} has an unresolvable annotation: {exc}. "
            f"A name used in a signature is missing from the module's imports "
            f"(PEP 563 hides this until something calls get_type_hints)."
        )
