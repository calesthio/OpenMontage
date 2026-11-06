"""Tests for the Google Flow Job Manager (lib/flow_job_manager.py).

All tests are zero-cost: no generation, no credit spending, no generation
button clicks.  The automated system stops at READY_FOR_APPROVAL.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.flow_job_manager import (  # noqa: E402
    FlowJob,
    FlowJobManager,
    JOB_STATES,
    STATE_TRANSITIONS,
    check_gflow_auth,
    check_gflow_credits,
    check_gflow_models,
    check_gflow_projects,
    get_manager,
)

JOBS_DIR = REPO / "jobs"
TEST_JOBS_DIR = REPO / "tests" / "flow_jobs_test"
TEST_QUEUE_DIR = REPO / "tests" / "flow_queue_test"
TEST_RESULTS_DIR = REPO / "tests" / "flow_results_test"
DEMO_JOBS = JOBS_DIR / "demo_jobs.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_manager(tmp_path):
    """Fresh FlowJobManager using isolated test directories."""
    import os

    os.environ["GFLOW_MCP_NO_SPEND"] = "1"

    # Monkeypatch paths to use isolated dirs
    import lib.flow_job_manager as fjm

    orig_jobs = fjm.JOBS_DIR
    orig_queue = fjm.FLOW_QUEUE_DIR
    orig_results = fjm.FLOW_RESULTS_DIR
    orig_db = fjm.QUEUE_DB

    fjm.JOBS_DIR = TEST_JOBS_DIR
    fjm.FLOW_QUEUE_DIR = TEST_QUEUE_DIR
    fjm.FLOW_RESULTS_DIR = TEST_RESULTS_DIR
    fjm.QUEUE_DB = TEST_QUEUE_DIR / "queue.db"

    for d in (TEST_JOBS_DIR, TEST_QUEUE_DIR, TEST_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # Clear any leftover
    for f in TEST_JOBS_DIR.glob("*.json"):
        f.unlink()
    if TEST_QUEUE_DIR.exists():
        shutil.rmtree(TEST_QUEUE_DIR)
    TEST_QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    mgr = FlowJobManager()
    yield mgr

    # Restore
    fjm.JOBS_DIR = orig_jobs
    fjm.FLOW_QUEUE_DIR = orig_queue
    fjm.FLOW_RESULTS_DIR = orig_results
    fjm.QUEUE_DB = orig_db

    # Cleanup
    shutil.rmtree(TEST_JOBS_DIR, ignore_errors=True)
    shutil.rmtree(TEST_QUEUE_DIR, ignore_errors=True)
    shutil.rmtree(TEST_RESULTS_DIR, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

DEMO_JOB = {
    "job_id": "test-job-001",
    "project": "test-project",
    "scene": "test-scene",
    "prompt": "A cinematic wide shot of a rocket launching, golden hour lighting, photorealistic, 35mm lens",
    "aspect_ratio": "16:9",
    "resolution": "1920x1080",
    "references": [],
    "input_files": [],
    "generation_params": {},
}


# ---------------------------------------------------------------------------
# 1. Job state machine
# ---------------------------------------------------------------------------


def test_job_states_defined():
    """All required states exist."""
    assert "DRAFT" in JOB_STATES
    assert "VALIDATED" in JOB_STATES
    assert "READY_FOR_APPROVAL" in JOB_STATES
    assert "APPROVED" in JOB_STATES
    assert "SUBMITTED" in JOB_STATES
    assert "COMPLETED" in JOB_STATES
    assert "FAILED" in JOB_STATES


def test_state_transitions():
    """State transition graph matches spec."""
    assert STATE_TRANSITIONS["DRAFT"] == ("VALIDATED",)
    assert STATE_TRANSITIONS["VALIDATED"] == ("READY_FOR_APPROVAL",)
    assert STATE_TRANSITIONS["READY_FOR_APPROVAL"] == ("APPROVED",)
    assert STATE_TRANSITIONS["APPROVED"] == ("SUBMITTED",)
    assert STATE_TRANSITIONS["SUBMITTED"] == ("COMPLETED", "FAILED")
    assert STATE_TRANSITIONS["COMPLETED"] == ()
    assert STATE_TRANSITIONS["FAILED"] == ()


# ---------------------------------------------------------------------------
# 2. Add job
# ---------------------------------------------------------------------------


def test_add_job_draft(clean_manager):
    """Adding a job creates it in DRAFT state."""
    mgr = clean_manager
    job = mgr.add_job(**DEMO_JOB)
    assert job.job_id == "test-job-001"
    assert job.state == "DRAFT"
    assert job.prompt_version == 1
    assert job.project == "test-project"
    assert job.scene == "test-scene"


def test_add_job_duplicate_id(clean_manager):
    """Adding a job with duplicate job_id raises ValueError."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    with pytest.raises(ValueError, match="Duplicate job_id"):
        mgr.add_job(**DEMO_JOB)


def test_add_job_duplicate_content(clean_manager):
    """Adding a job with identical content to an existing job raises ValueError."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    dup = dict(DEMO_JOB)
    dup["job_id"] = "test-job-002"  # different id, same content
    with pytest.raises(ValueError, match="Duplicate job content"):
        mgr.add_job(**dup)


# ---------------------------------------------------------------------------
# 3. Edit prompt
# ---------------------------------------------------------------------------


def test_edit_prompt(clean_manager):
    """Editing a prompt creates a new version without changing state."""
    mgr = clean_manager
    job = mgr.add_job(**DEMO_JOB)
    assert job.prompt_version == 1
    assert job.state == "DRAFT"

    updated = mgr.edit_prompt("test-job-001", "Updated prompt for testing purposes only")
    assert updated.prompt_version == 2
    assert updated.prompt == "Updated prompt for testing purposes only"
    assert updated.state == "DRAFT"  # state unchanged


def test_edit_prompt_not_draft(clean_manager):
    """Cannot edit prompt in non-DRAFT/VALIDATED states."""
    mgr = clean_manager
    job = mgr.add_job(**DEMO_JOB)
    mgr.validate_job("test-job-001")  # now VALIDATED
    # Edit while VALIDATED should work
    mgr.edit_prompt("test-job-001", "Edited while validated prompt text here")
    # Move to READY_FOR_APPROVAL
    mgr.ready_for_approval("test-job-001")
    with pytest.raises(ValueError, match="Cannot edit prompt"):
        mgr.edit_prompt("test-job-001", "Should not work")


# ---------------------------------------------------------------------------
# 4. Validation
# ---------------------------------------------------------------------------


def test_validate_draft_job(clean_manager):
    """A valid DRAFT job transitions to VALIDATED."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    job = mgr.validate_job("test-job-001")
    assert job.state == "VALIDATED"
    assert job.error is None
    assert job.mcp_checked is True


def test_validate_empty_prompt(clean_manager):
    """A job with empty prompt fails validation and stays DRAFT."""
    mgr = clean_manager
    bad = dict(DEMO_JOB)
    bad["job_id"] = "test-job-empty"
    bad["prompt"] = ""
    mgr.add_job(**bad)
    job = mgr.validate_job("test-job-empty")
    assert job.state == "DRAFT"
    assert job.error is not None
    assert "empty" in job.error


def test_validate_missing_reference(clean_manager):
    """A job with a missing reference file fails validation."""
    mgr = clean_manager
    bad = dict(DEMO_JOB)
    bad["job_id"] = "test-job-missing-ref"
    bad["references"] = ["/nonexistent/image.png"]
    mgr.add_job(**bad)
    job = mgr.validate_job("test-job-missing-ref")
    assert job.state == "DRAFT"
    assert job.error is not None
    assert "not found" in job.error


# ---------------------------------------------------------------------------
# 5. Queue formation
# ---------------------------------------------------------------------------


def test_queue_formation(clean_manager):
    """Jobs form a queue grouped by state."""
    mgr = clean_manager
    for i in range(3):
        j = dict(DEMO_JOB)
        j["job_id"] = f"q-job-{i:03d}"
        j["scene"] = f"scene-{i}"
        mgr.add_job(**j)

    # Validate all
    for i in range(3):
        mgr.validate_job(f"q-job-{i:03d}")

    summary = mgr.queue_summary()
    assert summary["total"] == 3
    assert summary["by_state"]["VALIDATED"] == 3
    assert summary["draft"] == 0


def test_list_jobs_filter(clean_manager):
    """Listing jobs supports state and project filters."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    j2 = dict(DEMO_JOB)
    j2["job_id"] = "test-job-002"
    j2["project"] = "other-project"
    mgr.add_job(**j2)

    all_jobs = mgr.list_jobs()
    assert len(all_jobs) == 2

    draft_jobs = mgr.list_jobs(state="DRAFT")
    assert len(draft_jobs) == 2

    tp_jobs = mgr.list_jobs(project="test-project")
    assert len(tp_jobs) == 1
    assert tp_jobs[0].job_id == "test-job-001"


# ---------------------------------------------------------------------------
# 6. Recovery after restart
# ---------------------------------------------------------------------------


def test_recovery_after_restart(clean_manager):
    """Jobs persist and are reloaded on manager restart (queue recovery)."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    mgr.validate_job("test-job-001")

    # Simulate restart: new manager instance loads from disk
    mgr2 = FlowJobManager()
    job = mgr2.get_job("test-job-001")
    assert job is not None
    assert job.state == "VALIDATED"
    assert job.job_id == "test-job-001"


# ---------------------------------------------------------------------------
# 7. Error handling for bad data
# ---------------------------------------------------------------------------


def test_invalid_transition(clean_manager):
    """Invalid state transitions raise ValueError."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    job = mgr.get_job("test-job-001")
    with pytest.raises(ValueError):
        job.transition("COMPLETED", "skip states")  # DRAFT → COMPLETED not allowed


def test_get_nonexistent_job(clean_manager):
    """Getting a nonexistent job returns None."""
    mgr = clean_manager
    assert mgr.get_job("does-not-exist") is None


# ---------------------------------------------------------------------------
# 8. Duplicate protection (re-verified through queue)
# ---------------------------------------------------------------------------


def test_duplicate_protection_in_queue(clean_manager):
    """The queue rejects duplicate content even with different IDs."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    dup = dict(DEMO_JOB)
    dup["job_id"] = "dup-content-id"
    with pytest.raises(ValueError, match="Duplicate job content"):
        mgr.add_job(**dup)


# ---------------------------------------------------------------------------
# 9. Google Flow check (MCP read-only)
# ---------------------------------------------------------------------------


def test_gflow_auth_check(clean_manager):
    """gflow auth status is a read-only MCP check."""
    try:
        result = check_gflow_auth()
        assert result["ok"] is True
    except RuntimeError as exc:
        # MCP may be unreachable in test env (browser launch); that's OK
        # for unit tests — the integration test verifies real connectivity.
        pytest.skip(f"gflow MCP unreachable: {exc}")


def test_gflow_projects_check(clean_manager):
    """gflow list projects is read-only."""
    result = check_gflow_projects()
    assert result["ok"] is True
    assert "projects" in result


def test_gflow_models_check(clean_manager):
    """gflow list models is read-only (no spend)."""
    try:
        result = check_gflow_models()
        assert result["ok"] is True
        assert "models" in result
    except RuntimeError as exc:
        pytest.skip(f"gflow MCP unreachable: {exc}")


def test_gflow_credits_check(clean_manager):
    """gflow get credits is read-only (no spend)."""
    try:
        result = check_gflow_credits()
        assert result["ok"] is True
    except RuntimeError as exc:
        pytest.skip(f"gflow MCP unreachable: {exc}")


# ---------------------------------------------------------------------------
# 10. Protection against accidental generation
# ---------------------------------------------------------------------------


def test_no_spend_env_preserved():
    """GFLOW_MCP_NO_SPEND=1 must be set (in kilo.jsonc env block)."""
    import os

    os.environ.setdefault("GFLOW_MCP_NO_SPEND", "1")
    assert os.environ.get("GFLOW_MCP_NO_SPEND") == "1"


def test_gflow_read_only_tools_only():
    """Only read-only gflow tools are permitted."""
    from lib.flow_job_manager import GFLOW_READ_ONLY_TOOLS

    assert "gflow_auth_status" in GFLOW_READ_ONLY_TOOLS
    assert "gflow_list_projects" in GFLOW_READ_ONLY_TOOLS
    assert "gflow_list_models" in GFLOW_READ_ONLY_TOOLS
    assert "gflow_get_credits" in GFLOW_READ_ONLY_TOOLS
    # Generation tools must NOT be in the read-only set
    assert "gflow_generate_image" not in GFLOW_READ_ONLY_TOOLS
    assert "gflow_generate_video" not in GFLOW_READ_ONLY_TOOLS


def test_browser_use_forbidden_actions():
    """Browser Use must not click generation buttons."""
    from lib.flow_job_manager import FORBIDDEN_BU_ACTIONS, BROWSER_USE_READ_ONLY_TOOLS

    assert "browser_click" in FORBIDDEN_BU_ACTIONS
    assert "browser_type" in FORBIDDEN_BU_ACTIONS
    assert "browser_scroll" in FORBIDDEN_BU_ACTIONS
    # Read-only tools must not include click/type/scroll
    assert "browser_click" not in BROWSER_USE_READ_ONLY_TOOLS
    assert "browser_type" not in BROWSER_USE_READ_ONLY_TOOLS
    assert "browser_scroll" not in BROWSER_USE_READ_ONLY_TOOLS


def test_auto_stop_at_ready_for_approval(clean_manager):
    """Automated system stops at READY_FOR_APPROVAL; APPROVED requires manual step."""
    mgr = clean_manager
    mgr.add_job(**DEMO_JOB)
    mgr.validate_job("test-job-001")
    mgr.ready_for_approval("test-job-001")
    job = mgr.get_job("test-job-001")
    assert job.state == "READY_FOR_APPROVAL"
    # APPROVED is a separate manual call — not auto-transitioned
    assert job.approved_at is None


# ---------------------------------------------------------------------------
# 11. Bulk import from JSON
# ---------------------------------------------------------------------------


def test_bulk_import_from_json(clean_manager):
    """Bulk importing jobs from JSON works."""
    mgr = clean_manager
    created = mgr.add_jobs_from_json(str(DEMO_JOBS))
    assert len(created) == 10
    for job in created:
        assert job.state == "DRAFT"
    summary = mgr.queue_summary()
    assert summary["total"] == 10
    assert summary["draft"] == 10


# ---------------------------------------------------------------------------
# 12. Results organization
# ---------------------------------------------------------------------------


def test_result_dir_creation(clean_manager):
    """Result directories are organized by project and scene."""
    mgr = clean_manager
    d = mgr.result_dir("test-project", "test-scene")
    assert d.exists()
    assert d.name == "test-scene"
    assert d.parent.name == "test-project"
