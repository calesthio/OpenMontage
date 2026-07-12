"""Evolution seams: storage, queue (strong ref), auth, and the live registry."""

from __future__ import annotations

import asyncio

import app.interfaces as interfaces
from app.interfaces import (
    get_storage, get_job_queue, get_auth_provider, active_backends,
)
from app.interfaces.storage import LocalStorage
from app.interfaces.queue import AsyncioJobQueue
from app.interfaces.auth import PassphraseAuth


def test_defaults():
    assert get_storage().name == "local"
    assert get_job_queue().name == "asyncio"
    assert get_auth_provider().name == "passphrase"


def test_unknown_storage_backend_falls_back_and_logs(monkeypatch, caplog):
    # Regression: an unrecognized OM_STORAGE_BACKEND used to silently
    # substitute the default adapter with no trace of the misconfiguration.
    interfaces.get_storage.cache_clear()
    monkeypatch.setenv("OM_STORAGE_BACKEND", "s3")
    try:
        with caplog.at_level("WARNING"):
            backend = interfaces.get_storage()
        assert backend.name == "local"
        assert any("OM_STORAGE_BACKEND" in r.getMessage() for r in caplog.records)
    finally:
        interfaces.get_storage.cache_clear()


def test_unknown_job_queue_falls_back_and_logs(monkeypatch, caplog):
    interfaces.get_job_queue.cache_clear()
    monkeypatch.setenv("OM_JOB_QUEUE", "redis")
    try:
        with caplog.at_level("WARNING"):
            queue = interfaces.get_job_queue()
        assert queue.name == "asyncio"
        assert any("OM_JOB_QUEUE" in r.getMessage() for r in caplog.records)
    finally:
        interfaces.get_job_queue.cache_clear()


def test_unknown_auth_provider_falls_back_and_logs(monkeypatch, caplog):
    interfaces.get_auth_provider.cache_clear()
    monkeypatch.setenv("OM_AUTH_PROVIDER", "oauth")
    try:
        with caplog.at_level("WARNING"):
            auth = interfaces.get_auth_provider()
        assert auth.name == "passphrase"
        assert any("OM_AUTH_PROVIDER" in r.getMessage() for r in caplog.records)
    finally:
        interfaces.get_auth_provider.cache_clear()


def test_active_backends_shape():
    b = active_backends()
    for seam in ("storage", "queue", "auth"):
        assert b[seam]["active"]
        assert isinstance(b[seam]["available"], list)
        assert isinstance(b[seam]["planned"], list)


def test_local_storage_url_and_paths(tmp_path):
    s = LocalStorage(root=tmp_path)
    assert s.url_for("proj", "renders/final.mp4") == "/media/proj/renders/final.mp4"
    # backslashes / leading slashes normalized
    assert s.url_for("proj", "\\renders\\a.mp4") == "/media/proj/renders/a.mp4"
    assert s.project_dir("proj") == tmp_path / "proj"
    assert s.exists("proj", "x.mp4") is False
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "x.mp4").write_text("data")
    assert s.exists("proj", "x.mp4") is True


def test_passphrase_auth(monkeypatch):
    auth = PassphraseAuth(passphrase="secret")
    assert auth.login({"passphrase": "secret"}) == "authenticated"
    assert auth.login({"passphrase": "wrong"}) is None
    assert auth.login({}) is None
    assert auth.verify("authenticated") is True
    assert auth.verify("nope") is False

    # empty configured passphrase must never authenticate
    empty = PassphraseAuth(passphrase="")
    assert empty.login({"passphrase": ""}) is None


async def test_queue_retains_reference_and_runs():
    q = AsyncioJobQueue()
    done = []

    async def job(x):
        await asyncio.sleep(0.02)
        done.append(x)

    q.enqueue(job, 7)
    assert len(q._tasks) == 1          # strong reference held during run
    await asyncio.sleep(0.05)
    assert done == [7]                 # job ran to completion
    assert len(q._tasks) == 0          # discarded via done-callback


async def test_queue_logs_exception_from_a_failed_job(caplog):
    # AsyncioJobQueue used to have no exception-handling contract of its own —
    # a coroutine that raised was only ever safe because its one current
    # caller (run_pipeline_job) happens to catch everything internally. A
    # future second caller wouldn't get that same protection for free.
    q = AsyncioJobQueue()

    async def boom():
        raise ValueError("kaboom")

    with caplog.at_level("ERROR"):
        q.enqueue(boom)
        await asyncio.sleep(0.05)

    assert len(q._tasks) == 0
    assert any(r.exc_info and "kaboom" in str(r.exc_info[1]) for r in caplog.records)
