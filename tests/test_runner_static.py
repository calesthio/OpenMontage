#!/usr/bin/env python3
"""Static checks for the Kaggle kernel runner (P2).

The runner runs on Kaggle, far away from the test suite: a NameError only
shows up after the kernel has installed diffusers and loaded the model. These
checks catch that class of bug locally:

  * every name a module-level function uses is defined in the module (or is a
    builtin) - no unbound names,
  * the runner still exposes the markers the bridge needs,
  * the generation call builder keeps its contract.

No network, no Kaggle, no GPU.
"""

from __future__ import annotations

import builtins
import symtable
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "tools/kaggle_bridge/s7_bakeoff_run.py"


def _module_symbols(source: str):
    table = symtable.symtable(source, str(RUNNER), "exec")
    module = table.get_name() if table.get_type() == "module" else None
    return table


def test_no_unbound_names_in_the_runner():
    """A name that a function uses but nobody defines is an unbound name.

    In a module-level function such a name is an *implicit global*: it is not
    local, not a parameter and not defined in the module - at runtime that is
    a NameError. This is the bug class that broke the first smoke job
    (`guidance` was only defined inside the call-builder).
    """
    source = RUNNER.read_text(encoding="utf-8")
    table = _module_symbols(source)
    module_symbols = {s.get_name(): s for s in table.get_symbols()}
    unbound: list[str] = []
    for child in table.get_children():
        if child.get_type() != "function":
            continue
        for sym in child.get_symbols():
            name = sym.get_name()
            if not sym.is_global():
                continue
            if name in dir(builtins):
                continue
            module_sym = module_symbols.get(name)
            if module_sym is not None and (module_sym.is_assigned()
                                           or module_sym.is_imported()
                                           or module_sym.is_namespace()):
                continue
            unbound.append(f"{child.get_name()}: {name}")
    assert not unbound, f"unbound names in the kernel runner: {unbound}"


def test_the_runner_keeps_its_bridge_markers():
    source = RUNNER.read_text(encoding="utf-8")
    assert "JOB_EMBEDDED = None" in source
    assert "def main() -> None:" in source
    assert "def resolve_model_plan(" in source
    assert "def build_generation_call(" in source


def test_the_runner_reports_a_missing_reference_image_instead_of_guessing():
    source = RUNNER.read_text(encoding="utf-8")
    assert "missing_reference_image" in source
