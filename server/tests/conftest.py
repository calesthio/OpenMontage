"""Shared test fixtures for the OpenMontage server suite."""

from __future__ import annotations

import pytest

from app.store import JobStore


@pytest.fixture
def store(tmp_path):
    """An isolated JobStore backed by a temp .jobstore dir (never the real one)."""
    return JobStore(persist_dir=tmp_path / "jobstore")
