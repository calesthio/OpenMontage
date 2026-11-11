"""One broken tool module must not take the registry down.

`ToolRegistry.discover()` imported every module under `tools/` in one loop with
no isolation: a syntax error or an import-time crash in any one of ~165 tool
modules raised out of discovery, and with it preflight for every pipeline.
"""

import sys
import textwrap

import pytest

from tools.tool_registry import ToolRegistry, registry

GOOD = """
from tools.base_tool import BaseTool, ToolResult

class Good(BaseTool):
    name = "{name}"
    capability = "probe"
    def execute(self, inputs):
        return ToolResult(success=True)
"""


@pytest.fixture
def package(tmp_path, monkeypatch):
    """A throwaway tool package with one good, one unimportable, one crashing module."""
    root = tmp_path / "probe_tools"
    (root / "sub").mkdir(parents=True)
    (root / "badpkg").mkdir()
    (root / "__init__.py").write_text("")
    (root / "sub" / "__init__.py").write_text("")
    (root / "good.py").write_text(GOOD.format(name="good_probe"))
    (root / "sub" / "nested.py").write_text(GOOD.format(name="nested_probe"))
    (root / "syntax_error.py").write_text("def broken(:\n    pass\n")
    (root / "import_error.py").write_text("import a_module_that_does_not_exist_anywhere\n")
    (root / "ctor_error.py").write_text(textwrap.dedent("""
        from tools.base_tool import BaseTool, ToolResult

        class Explodes(BaseTool):
            name = "explodes"
            def __init__(self):
                raise RuntimeError("constructor failed")
            def execute(self, inputs):
                return ToolResult(success=True)
    """))
    (root / "badpkg" / "__init__.py").write_text("raise RuntimeError('package init failed')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "probe_tools"
    for name in [m for m in sys.modules if m == "probe_tools" or m.startswith("probe_tools.")]:
        del sys.modules[name]


def test_good_tools_register_and_failures_are_recorded(package):
    reg = ToolRegistry()
    discovered = reg.discover(package)

    assert sorted(discovered) == ["good_probe", "nested_probe"]
    assert set(reg.discovery_errors) == {
        "probe_tools.syntax_error",
        "probe_tools.import_error",
        "probe_tools.ctor_error",
        "probe_tools.badpkg",
    }
    assert "SyntaxError" in reg.discovery_errors["probe_tools.syntax_error"]
    assert "a_module_that_does_not_exist_anywhere" in reg.discovery_errors["probe_tools.import_error"]
    assert "constructor failed" in reg.discovery_errors["probe_tools.ctor_error"]
    assert "package init failed" in reg.discovery_errors["probe_tools.badpkg"]


def test_failures_are_surfaced_at_preflight(package):
    reg = ToolRegistry()
    reg.discover(package)
    reg._discovered_packages.add("tools")       # keep the summary on the probe package
    for compact in (False, True):
        warnings = reg.provider_menu_summary(compact=compact)["runtime_warnings"]
        joined = "\n".join(warnings)
        assert "probe_tools.syntax_error failed to load" in joined
        assert "missing from this menu" in joined


def test_a_module_that_is_fixed_stops_being_reported(package, tmp_path):
    reg = ToolRegistry()
    reg.discover(package)
    (tmp_path / "probe_tools" / "import_error.py").write_text(GOOD.format(name="repaired_probe"))
    sys.modules.pop("probe_tools.import_error", None)
    import importlib

    importlib.invalidate_caches()
    assert "repaired_probe" in reg.discover(package)
    assert "probe_tools.import_error" not in reg.discovery_errors
    reg.clear()
    assert reg.discovery_errors == {}


def test_the_repo_itself_has_no_discovery_errors():
    """The guard that makes isolation safe: a tool module in THIS repo that
    stops importing fails here, loudly, instead of quietly shrinking the menu."""
    registry.discover()
    assert registry.discovery_errors == {}, registry.discovery_errors
    assert len(registry.list_all()) >= 160
