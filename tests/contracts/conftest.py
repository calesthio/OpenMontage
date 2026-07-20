"""Shared fixtures for contract tests."""

from __future__ import annotations

import pytest

from tools.tool_registry import ToolRegistry


@pytest.fixture()
def isolated_tool_registry(monkeypatch) -> ToolRegistry:
    """Provide a registry singleton replacement scoped to one test."""
    test_registry = ToolRegistry()
    monkeypatch.setattr("tools.tool_registry.registry", test_registry)
    return test_registry
