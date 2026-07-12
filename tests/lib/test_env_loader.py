"""Regression test for require_env's exception type.

require_env used to raise EnvironmentError, which is an alias for OSError in
Python 3 — a broad ``except OSError`` elsewhere in the codebase could
silently swallow a missing-required-variable error. It now raises a
dedicated MissingEnvironmentVariable so that can't happen.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from lib.env_loader import MissingEnvironmentVariable, require_env  # noqa: E402


def test_require_env_raises_dedicated_exception(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_TEST_MISSING_VAR", raising=False)
    with pytest.raises(MissingEnvironmentVariable):
        require_env("OPENMONTAGE_TEST_MISSING_VAR")


def test_require_env_error_is_not_an_oserror(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_TEST_MISSING_VAR", raising=False)
    try:
        require_env("OPENMONTAGE_TEST_MISSING_VAR")
    except OSError:
        pytest.fail("require_env's exception must not be catchable as OSError")
    except MissingEnvironmentVariable:
        pass


def test_require_env_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_TEST_MISSING_VAR", "hello")
    assert require_env("OPENMONTAGE_TEST_MISSING_VAR") == "hello"
