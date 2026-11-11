"""Every registered tool's declared contract must be internally consistent.

The agent learns what a tool accepts from `input_schema` in the registry, and
three pieces of runtime code read the same declarations:

- `registry.find_fallback()` looks each `fallback` / `fallback_tools` entry up
  by tool name, so an entry that is not a registered name can never be found.
- `BaseTool.cache_key()` hashes `idempotency_key_fields`. A field listed there
  but missing from the schema is an input the tool reads and never documents.
- The capability selectors route on the property names a provider declares.

The registry is iterated rather than named so a newly added tool is covered
the moment it is discovered.
"""

from __future__ import annotations

import jsonschema
import pytest

from tools.base_tool import BaseTool
from tools.tool_registry import registry

# idempotency_key_fields entries that are deliberately not schema properties.
UNDECLARED_IDEMPOTENCY_FIELDS: dict[str, set[str]] = {
    # pika_video accepts image_url / image_path as first-frame aliases and keys
    # its cache on them, but must not declare them: video_selector uploads a
    # local reference image to fal for any provider whose schema lists
    # image_url. The aliases are documented on reference_image_url/_path.
    "pika_video": {"image_url", "image_path"},
}


def _discovered_tools() -> list[tuple[str, BaseTool]]:
    registry.discover()
    return sorted(registry._tools.items())


TOOLS = dict(_discovered_tools())
TOOL_NAMES = set(TOOLS)


def _properties(tool: BaseTool) -> dict:
    return (tool.input_schema or {}).get("properties") or {}


def _fallback_targets(tool: BaseTool) -> list[str]:
    targets = list(tool.fallback_tools or [])
    if tool.fallback and tool.fallback not in targets:
        targets.append(tool.fallback)
    return targets


FALLBACKS = [
    (name, target) for name, tool in TOOLS.items() for target in _fallback_targets(tool)
]
WITH_PROPERTIES = [name for name, tool in TOOLS.items() if _properties(tool)]
WITH_SCHEMA = [name for name, tool in TOOLS.items() if tool.input_schema]


def test_checks_are_not_vacuous() -> None:
    """Guard against the parametrized tests below silently covering nothing."""
    assert TOOLS, "registry.discover() found no tools"
    assert FALLBACKS
    assert any(TOOLS[name].idempotency_key_fields for name in WITH_PROPERTIES)
    assert any(TOOLS[name].input_schema.get("required") for name in WITH_SCHEMA)


@pytest.mark.parametrize(("tool", "target"), FALLBACKS, ids=lambda v: str(v))
def test_fallback_target_is_a_registered_tool(tool: str, target: str) -> None:
    """Regression: screen_capture_selector listed the provider keys `cap` and
    `ffmpeg` instead of the tool names `cap_recorder` and `screen_recorder`."""
    assert target in TOOL_NAMES, (
        f"{tool} lists fallback {target!r}, which is not a registered tool name"
    )
    assert target != tool, f"{tool} lists itself as its own fallback"


@pytest.mark.parametrize("name", WITH_PROPERTIES)
def test_idempotency_fields_are_declared_properties(name: str) -> None:
    """Regression: video_compose keyed its cache on 13 inputs (playbook,
    scene_plan, public_dir, ...) that its schema never mentioned."""
    tool = TOOLS[name]
    allowed = UNDECLARED_IDEMPOTENCY_FIELDS.get(name, set())
    undeclared = set(tool.idempotency_key_fields or []) - set(_properties(tool))
    assert undeclared - allowed == set(), (
        f"{name} hashes inputs its input_schema does not declare: "
        f"{sorted(undeclared - allowed)}"
    )
    assert allowed - undeclared == set(), (
        f"{name} no longer needs these UNDECLARED_IDEMPOTENCY_FIELDS entries: "
        f"{sorted(allowed - undeclared)}"
    )


def test_allowlist_names_only_registered_tools() -> None:
    assert set(UNDECLARED_IDEMPOTENCY_FIELDS) <= TOOL_NAMES


@pytest.mark.parametrize("name", WITH_SCHEMA)
def test_required_inputs_are_declared_properties(name: str) -> None:
    tool = TOOLS[name]
    missing = set(tool.input_schema.get("required") or []) - set(_properties(tool))
    assert missing == set(), (
        f"{name} requires inputs its input_schema does not declare: {sorted(missing)}"
    )


@pytest.mark.parametrize("name", WITH_SCHEMA)
def test_input_schema_is_valid_json_schema(name: str) -> None:
    jsonschema.Draft202012Validator.check_schema(TOOLS[name].input_schema)
