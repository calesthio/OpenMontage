"""Tests for lib.gflow_wrapper using a fake gflow-cli binary (no spend, no network).

Covers: availability check, zero-cost gate block, READY_FOR_APPROVAL stop,
mocked single-image execution, mocked batch execution, exit-code handling,
timeout handling, duplicate-job protection, and SHA-256 recording.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from lib.flow_job_manager import FlowJobManager  # noqa: E402
from lib.gflow_wrapper import (  # noqa: E402
    EXIT_ARGS,
    EXIT_DOCTOR,
    EXIT_OK,
    EXIT_PROFILE,
    GflowWrapper,
    ZeroCostViolation,
)
from lib.zero_cost_gate import STRICT_ZERO_COST, ToolFacts, evaluate_call  # noqa: E402


# ---------------------------------------------------------------------------
# Fake gflow-cli
# ---------------------------------------------------------------------------


def _write_fake_gflow(tmp_path: Path, fail: bool = False) -> Path:
    fake = tmp_path / "gflow"
    fail_expr = "True" if fail else "False"
    script = """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if "--version" in args:
    print("gflow, version 0.92.0 (fake)")
    sys.exit(0)
if args == ["credits", "user"]:
    print(json.dumps({"profile": "flow_remote", "credits": 50}))
    sys.exit(0)
if args[0] == "image" and args[1] == "t2i":
    out = "/tmp/kilo/fake_out.png"
    try:
        from pathlib import Path
        Path("/tmp/kilo/fake_out.png").write_bytes(b"FAKE-IMAGE-BYTES")
    except Exception:
        pass
    print(json.dumps({
        "media_id": "media-t2i",
        "output_path": out,
        "width": 1920,
        "height": 1080,
        "sha256": "deadbeef",
        "bytes": 17,
    }))
    if __FAIL__:
        print("simulated generation error", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
if args[0] == "run" and "--config" in args:
    print(json.dumps({"jobs": len(args), "status": "ok", "output_dir": "/tmp/kilo/batch"}))
    sys.exit(0)
print("unknown gflow command: " + " ".join(args), file=sys.stderr)
sys.exit(2)
"""
    script = script.replace("__FAIL__", fail_expr)
    fake.write_text(script)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return fake


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_flow_state():
    """Isolate each test from persisted FlowJobManager artifacts.

    The manager writes jobs/ and flow_queue/queue.db under the repo root
    (gitignored runtime artifacts).  Clearing them before every test keeps
    duplicate-job / duplicate-content checks deterministic.
    """
    jobs_dir = Path("/workspaces/OpenMontage/jobs")
    queue_db = Path("/workspaces/OpenMontage/flow_queue/queue.db")
    if jobs_dir.exists():
        for f in jobs_dir.glob("*.json"):
            f.unlink(missing_ok=True)
    for ext in ("", "-wal", "-shm"):
        Path(str(queue_db) + ext).unlink(missing_ok=True)
    yield


@pytest.fixture
def fake_gflow(tmp_path):
    return _write_fake_gflow(tmp_path)


@pytest.fixture
def wrapper(fake_gflow):
    return GflowWrapper(gflow_bin=str(fake_gflow), timeout_seconds=30.0)


def _tag():
    return uuid.uuid4().hex[:8]


def _unique_sentence():
    return f"S{int(time.time() * 1000) % 100000:05d}-{_tag()}"


# ---------------------------------------------------------------------------
# Availability / version (read-only)
# ---------------------------------------------------------------------------


def test_version(wrapper):
    assert wrapper.version() == "gflow, version 0.92.0 (fake)"


def test_check_available(wrapper):
    assert wrapper.check_available() is True


def test_check_available_when_missing(tmp_path):
    missing = tmp_path / "no_gflow"
    w = GflowWrapper(gflow_bin=str(missing))
    assert w.check_available() is False


# ---------------------------------------------------------------------------
# Zero-cost gate blocks generation without approval / known cost
# ---------------------------------------------------------------------------


def test_execute_image_blocked_without_approval(wrapper):
    job = wrapper.plan_image_job(
        sentence_id=_unique_sentence(), project="proj",
        prompt=f"A deep sea alien glows. [{_tag()}]",
        output_path="/tmp/kilo/s001.png", reference_entity="CHAR-1",
    )
    assert job.state == "READY_FOR_APPROVAL"

    # Unknown cost + no approval -> ZeroCostViolation, no subprocess call.
    with pytest.raises(ZeroCostViolation):
        wrapper.execute_image(job_id=job.job_id, user_approved=False, cost_usd=None)

    # Known zero cost but job not yet APPROVED -> error result, no gflow call.
    result = wrapper.execute_image(job_id=job.job_id, user_approved=False, cost_usd=0.0)
    assert result.success is False
    assert "not APPROVED" in result.error


def test_gate_blocks_unknown_cost_directly():
    facts = ToolFacts(
        tool="gflow_image_t2i", operation="execute", provider="google_flow",
        runtime="api", route="gflow image t2i model=nano2 aspect=16:9",
        cost_usd=None, status="available",
    )
    dec = evaluate_call(facts, mode=STRICT_ZERO_COST, user_approved=False)
    assert dec.blocked
    assert "cost_usd is null" in dec.reason


# ---------------------------------------------------------------------------
# Mocked single-image execution (approved, zero cost)
# ---------------------------------------------------------------------------


def test_execute_image_approved_records_result(wrapper):
    job = wrapper.plan_image_job(
        sentence_id=_unique_sentence(), project="proj",
        prompt=f"A bioluminescent alien creature glows in the dark ocean. [{_tag()}]",
        output_path="/tmp/kilo/s001.png", reference_entity="CHAR-1",
    )
    assert job.state == "READY_FOR_APPROVAL"
    # Simulate explicit owner approval (manual gate) before generation.
    wrapper.manager.approve(job.job_id)
    assert wrapper.manager.get_job(job.job_id).state == "APPROVED"

    result = wrapper.execute_image(
        job_id=job.job_id, user_approved=True, cost_usd=0.0,
    )
    assert result.success is True
    assert result.exit_code == EXIT_OK
    assert result.media_id is not None
    assert result.output_path is not None
    assert result.width == 1920
    assert result.height == 1080
    assert result.sha256 is not None
    assert result.duration_seconds is not None
    assert result.error is None


def test_execute_image_handles_failure(wrapper, tmp_path):
    fail_bin = _write_fake_gflow(tmp_path, fail=True)
    w = GflowWrapper(gflow_bin=str(fail_bin), timeout_seconds=30.0)
    job = w.plan_image_job(
        sentence_id=_unique_sentence(), project="proj", prompt=f"A test. [{_tag()}]",
        output_path="/tmp/kilo/s001.png",
    )
    # Simulate explicit owner approval before credit-bearing generation.
    w.manager.approve(job.job_id)
    result = w.execute_image(job_id=job.job_id, user_approved=True, cost_usd=0.0)
    assert result.success is False
    assert result.exit_code == 1
    assert result.error is not None


# ---------------------------------------------------------------------------
# Batch execution (mocked)
# ---------------------------------------------------------------------------


def test_execute_batch_approved(wrapper, tmp_path):
    config = tmp_path / "batch.json"
    config.write_text(
        json.dumps({"profile": "flow_remote", "prompts": [
            {"text": "prompt one", "aspect_ratio": "16:9", "count": 1},
            {"text": "prompt two", "aspect_ratio": "16:9", "count": 1},
        ]})
    )
    result = wrapper.execute_batch(
        config_path=str(config), output_dir=str(tmp_path / "out"),
        user_approved=True, cost_usd=0.0,
    )
    assert result.success is True
    assert result.exit_code == EXIT_OK
    assert result.duration_seconds is not None


# ---------------------------------------------------------------------------
# Exit codes mapped correctly
# ---------------------------------------------------------------------------


def test_exit_code_constants():
    assert EXIT_OK == 0
    assert EXIT_ARGS == 2
    assert EXIT_PROFILE == 11
    assert EXIT_DOCTOR == 33


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------


def test_timeout_handled(wrapper, tmp_path):
    slow = tmp_path / "slow_gflow"
    slow.write_text("#!/usr/bin/env python3\nimport time, sys; time.sleep(60)\n")
    slow.chmod(slow.stat().st_mode | stat.S_IXUSR)
    w = GflowWrapper(gflow_bin=str(slow), timeout_seconds=2.0)
    job = w.plan_image_job(
        sentence_id=_unique_sentence(), project="proj", prompt=f"A test. [{_tag()}]",
        output_path="/tmp/kilo/s001.png",
    )
    # Simulate explicit owner approval before credit-bearing generation.
    w.manager.approve(job.job_id)
    result = w.execute_image(job_id=job.job_id, user_approved=True, cost_usd=0.0)
    assert result.success is False
    assert "timeout" in result.error.lower()


# ---------------------------------------------------------------------------
# Duplicate job protection (FlowJobManager raises on duplicate job_id)
# ---------------------------------------------------------------------------


def test_duplicate_job_id_rejected():
    m = FlowJobManager()
    jid = f"dup-{_tag()}"
    m.add_job(job_id=jid, project="p", scene="S001", prompt="alpha")
    with pytest.raises(ValueError, match="Duplicate job_id"):
        m.add_job(job_id=jid, project="p", scene="S001", prompt="alpha")


# ---------------------------------------------------------------------------
# READY_FOR_APPROVAL: no APPROVED/SUBMITTED transition by wrapper
# ---------------------------------------------------------------------------


def test_automated_system_stops_at_ready_for_approval(wrapper):
    job = wrapper.plan_image_job(
        sentence_id=_unique_sentence(), project="proj", prompt=f"A test scene. [{_tag()}]",
        output_path="/tmp/kilo/s001.png",
    )
    assert job.state == "READY_FOR_APPROVAL"
    # The wrapper never calls approve/submit; those require manual approval.
    assert wrapper.manager.get_job(job.job_id).state == "READY_FOR_APPROVAL"
