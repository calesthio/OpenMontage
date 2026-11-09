"""Regression tests for Makefile RUN_PYTHON quoting.

A checkout path may contain spaces (a Windows "Program Files"-style directory,
an external volume, or any user folder with a space in the name). RUN_PYTHON
expands to that path, so every command-position use has to be quoted. Unquoted,
sh word-splits it and ensure-venv fails while blaming the interpreter:

    /bin/sh: /Volumes/Some Drive/repo/.venv/bin/python: not found
    ERROR: OpenMontage requires Python 3.10+.
    Current interpreter is unavailable: /Volumes/Some Drive/repo/.venv/bin/python

The interpreter is fine. Every make target fails, and the reported cause is
wrong, which sends people off to reinstall a Python they do not need.
"""

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MAKEFILE = PROJECT_ROOT / "Makefile"

# Command position: the start of a recipe line (optionally after @), after a
# shell operator, inside a command substitution, or in the PIP recipe variable.
# Display-only uses inside echo strings do not need quoting.
COMMAND_POSITION = re.compile(r"(?:^\t@?|\|\| |&& |\$\$\(|^PIP = )\$\(RUN_PYTHON\)", re.M)


def test_run_python_is_quoted_in_every_command_position():
    text = MAKEFILE.read_text()
    offenders = []
    for match in COMMAND_POSITION.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        offenders.append(f"  Makefile:{line_no}: {text.splitlines()[line_no - 1].strip()[:90]}")

    assert not offenders, (
        "Unquoted $(RUN_PYTHON) in command position. The interpreter path can "
        "contain spaces, so these word-split in sh:\n" + "\n".join(offenders)
    )


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
def test_ensure_venv_succeeds_when_the_venv_path_contains_spaces(tmp_path):
    """End-to-end: run a real make target from a path with a space in it."""
    workdir = tmp_path / "dir with spaces"
    bindir = workdir / ".venv" / "bin"
    bindir.mkdir(parents=True)
    shutil.copy(MAKEFILE, workdir / "Makefile")

    # A wrapper rather than a symlink, so `python -m pip` still resolves
    # against the real environment instead of this empty directory.
    fake_python = bindir / "python"
    fake_python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    env = {**os.environ, "VIRTUAL_ENV": str(workdir / ".venv"), "CONDA_PREFIX": ""}
    proc = subprocess.run(
        ["make", "ensure-venv"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, (
        f"make ensure-venv failed from a path containing spaces.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "No such file or directory" not in proc.stderr
    assert "requires Python" not in proc.stdout
