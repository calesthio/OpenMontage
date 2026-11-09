"""Regression tests for Makefile RUN_ENV_PATH.

`make preflight` picks the right interpreter (RUN_PYTHON) but, without the
environment's bin dir on PATH, tool discovery (`shutil.which`) cannot find CLI
dependencies installed in that environment, such as `piper`, unless the venv
was activated by hand. They are then reported unavailable although installed.

RUN_ENV_PATH prepends the interpreter's directory to PATH for the targets that
run discovery. It is resolved in sh because make's $(dir)/$(abspath) split on
whitespace, and the checkout path may contain spaces (see
test_makefile_run_python_quoting.py).
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


def _recipe(text: str, target: str) -> str:
    match = re.search(rf"^{re.escape(target)}:.*?\n((?:\t.*\n?)+)", text, re.M)
    assert match, f"target {target!r} not found in Makefile"
    return match.group(1)


@pytest.mark.parametrize("target", ["preflight", "demo"])
def test_discovery_targets_put_the_env_bin_dir_on_path(target):
    assert "$(RUN_ENV_PATH)" in _recipe(MAKEFILE.read_text(), target), (
        f"`make {target}` must run with $(RUN_ENV_PATH) so CLI deps installed "
        "in the selected environment are discoverable without activating it"
    )


def test_run_env_path_does_not_use_whitespace_splitting_make_functions():
    line = next(
        (l for l in MAKEFILE.read_text().splitlines() if l.startswith("RUN_ENV_PATH")),
        "",
    )
    assert line, "RUN_ENV_PATH is not defined"
    # A make function call is `$(name ` (single `$`, then whitespace); the sh
    # command substitution `$$(dirname ...)` is fine and must not match.
    assert not re.search(r"(?<!\$)\$\((dir|abspath|realpath|notdir)\s", line), (
        "$(dir)/$(abspath) split on spaces and break for checkouts in paths "
        "containing whitespace; resolve the directory in sh instead"
    )


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell wrapper")
def test_env_bin_cli_is_discoverable_when_the_venv_path_contains_spaces(tmp_path):
    workdir = tmp_path / "dir with spaces"
    bindir = workdir / ".venv" / "bin"
    bindir.mkdir(parents=True)

    def make_executable(path: Path, body: str) -> None:
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    make_executable(bindir / "python", f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    make_executable(bindir / "fake-env-cli", "#!/bin/sh\nexit 0\n")

    # Reuse the real macro; add a probe target that runs discovery the way
    # `preflight` does.
    (workdir / "Makefile").write_text(
        MAKEFILE.read_text()
        + '\nprobe:\n\t$(RUN_ENV_PATH) "$(RUN_PYTHON)" -c '
        '"import shutil; print(\'FOUND=\' + str(shutil.which(\'fake-env-cli\')))"\n'
    )

    # The venv bin dir is deliberately NOT on PATH.
    env = {**os.environ, "VIRTUAL_ENV": str(workdir / ".venv"), "CONDA_PREFIX": ""}

    proc = subprocess.run(
        ["make", "probe"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert f"FOUND={bindir / 'fake-env-cli'}" in proc.stdout, proc.stdout
