"""Shipped manifests must agree with what the engine enforces and offers.

Three drifts this guards against:

- ``checkpoint_required: false`` on a stage that has a successor. The
  checkpoint writer refuses to advance a later stage until every earlier one
  has a completed checkpoint, so an agent that honoured the flag hit a
  PREREQUISITE VIOLATION one stage later.
- a tool listed under ``required_tools``/``optional_tools`` that the stage does
  not list under ``tools_available``.
- a tool name no registered tool answers to.
"""

from __future__ import annotations

import pytest

from lib.pipeline_loader import list_pipelines, load_pipeline
from tools.tool_registry import registry

PIPELINES = sorted(list_pipelines())

# Capabilities the agent brings itself; they are not registry tools.
AGENT_NATIVE_TOOLS = {"web_search"}

TOOL_FIELDS = (
    "required_tools",
    "optional_tools",
    "preferred_tools",
    "fallback_tools",
    "tools_available",
)


@pytest.fixture(scope="module")
def registered_tools() -> set[str]:
    registry.ensure_discovered()
    return set(registry.list_all())


@pytest.mark.parametrize("name", PIPELINES)
def test_only_the_last_stage_may_skip_its_checkpoint(name: str) -> None:
    stages = load_pipeline(name)["stages"]

    skipped = [
        stage["name"]
        for stage in stages[:-1]
        if stage.get("checkpoint_required", True) is False
    ]

    assert not skipped, (
        f"{name}: {skipped} declare checkpoint_required: false but have a "
        f"successor; prerequisite enforcement needs their completed checkpoint"
    )


@pytest.mark.parametrize("name", PIPELINES)
def test_declared_tools_are_available_to_their_stage(name: str) -> None:
    missing = []
    for stage in load_pipeline(name)["stages"]:
        available = set(stage.get("tools_available", []))
        for field in ("required_tools", "optional_tools"):
            for tool in stage.get(field, []):
                if tool not in available:
                    missing.append(f"{stage['name']}.{field}: {tool}")

    assert not missing, f"{name}: not in tools_available -> {missing}"


@pytest.mark.parametrize("name", PIPELINES)
def test_manifest_tools_are_registered(name: str, registered_tools: set[str]) -> None:
    manifest = load_pipeline(name)
    named: set[str] = set(
        (manifest.get("reference_input") or {}).get("analysis_tools", [])
    )
    for stage in manifest["stages"]:
        for scope in (stage, *stage.get("sub_stages", [])):
            for field in TOOL_FIELDS:
                named.update(scope.get(field, []))

    unknown = sorted(named - registered_tools - AGENT_NATIVE_TOOLS)

    assert not unknown, f"{name}: no registered tool named {unknown}"
