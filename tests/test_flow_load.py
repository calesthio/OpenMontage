"""Load testing for Flow Job Manager — 100 jobs, duplicates, malformed JSON,
restart recovery, parallel addition. Zero-cost: no generation, no credits."""

from __future__ import annotations

import json
import shutil
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.flow_job_manager import FlowJobManager  # noqa: E402

TEST_ROOT = Path("/tmp/flow_load_test")


def fresh_manager():
    """Create a manager with isolated test directories."""
    import lib.flow_job_manager as fjm

    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir(parents=True, exist_ok=True)

    jobs_dir = TEST_ROOT / "jobs"
    queue_dir = TEST_ROOT / "flow_queue"
    results_dir = TEST_ROOT / "flow_results"
    for d in (jobs_dir, queue_dir, results_dir):
        d.mkdir(parents=True, exist_ok=True)

    fjm.JOBS_DIR = jobs_dir
    fjm.FLOW_QUEUE_DIR = queue_dir
    fjm.FLOW_RESULTS_DIR = results_dir
    fjm.QUEUE_DB = queue_dir / "queue.db"

    return FlowJobManager()


def make_job(i: int, project: str = "load-test") -> dict:
    return {
        "job_id": f"load-{i:04d}",
        "project": project,
        "scene": f"scene-{i % 5}",
        "prompt": f"Load test prompt number {i} for validation purposes",
        "aspect_ratio": "16:9",
        "resolution": "1920x1080",
        "references": [],
        "input_files": [],
        "generation_params": {},
    }


def test_100_jobs():
    """Add 100 jobs — all should succeed in DRAFT state."""
    mgr = fresh_manager()
    for i in range(100):
        mgr.add_job(**make_job(i))
    summary = mgr.queue_summary()
    assert summary["total"] == 100, f"Expected 100, got {summary['total']}"
    assert summary["draft"] == 100
    print("  PASS: 100 jobs added")


def test_many_identical_prompts():
    """Many jobs with identical prompt but different IDs — content hash
    should NOT block them (different job_id + same prompt is fine if
    scene/project differ; same everything is blocked)."""
    mgr = fresh_manager()
    # Same prompt, same project, same scene, different job_id — should be
    # blocked as duplicate content (hash is based on content, not job_id)
    mgr.add_job(job_id="dup-1", project="P", scene="S", prompt="Identical prompt here")
    try:
        mgr.add_job(job_id="dup-2", project="P", scene="S", prompt="Identical prompt here")
        print("  FAIL: duplicate content not blocked")
        return False
    except ValueError:
        pass
    # Same prompt, different scene — should be allowed
    mgr.add_job(job_id="dup-3", project="P", scene="S2", prompt="Identical prompt here")
    summary = mgr.queue_summary()
    assert summary["total"] == 2, f"Expected 2, got {summary['total']}"
    print("  PASS: identical prompts handled correctly")
    return True


def test_restart_recovery():
    """Manager restart reloads all jobs from disk."""
    mgr = fresh_manager()
    for i in range(10):
        mgr.add_job(**make_job(i, project="restart-test"))
    mgr.validate_job("load-0000")
    mgr.validate_job("load-0001")
    mgr.ready_for_approval("load-0001")

    # Simulate restart: new manager instance
    mgr2 = FlowJobManager()
    jobs = mgr2.list_jobs()
    assert len(jobs) == 10, f"Expected 10 after restart, got {len(jobs)}"
    states = {j.job_id: j.state for j in jobs}
    assert states["load-0000"] == "VALIDATED"
    assert states["load-0001"] == "READY_FOR_APPROVAL"
    print("  PASS: restart recovery works")


def test_parallel_addition():
    """Parallel job addition from multiple threads — no duplicates, no corruption."""
    mgr = fresh_manager()
    errors = []

    def add_batch(start: int, count: int):
        try:
            for i in range(start, start + count):
                mgr.add_job(**make_job(i, project="parallel-test"))
        except Exception as exc:
            errors.append(exc)

    threads = []
    for t in range(10):
        th = threading.Thread(target=add_batch, args=(t * 10, 10))
        threads.append(th)
        th.start()
    for th in threads:
        th.join()

    assert len(errors) == 0, f"Errors during parallel add: {errors}"
    summary = mgr.queue_summary()
    assert summary["total"] == 100, f"Expected 100, got {summary['total']}"
    print("  PASS: parallel addition works")


def test_duplicate_requests():
    """Duplicate job_id and duplicate content are both rejected."""
    mgr = fresh_manager()
    mgr.add_job(**make_job(0, project="dup-test"))

    # Duplicate job_id (same content, same ID)
    try:
        mgr.add_job(**make_job(0, project="dup-test"))
        print("  FAIL: duplicate job_id not blocked")
        return False
    except ValueError:
        pass

    # Duplicate content, different ID (same project, scene, prompt)
    try:
        dup = dict(make_job(0, project="dup-test"))
        dup["job_id"] = "different-id"
        mgr.add_job(**dup)
        print("  FAIL: duplicate content not blocked")
        return False
    except ValueError:
        pass

    print("  PASS: duplicate protection works")
    return True


def test_malformed_json(tmp_path):
    """Malformed job JSON files are skipped on load, not crashing."""
    import lib.flow_job_manager as fjm

    jobs_dir = tmp_path / "jobs"
    queue_dir = tmp_path / "flow_queue"
    results_dir = tmp_path / "flow_results"
    for d in (jobs_dir, queue_dir, results_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Write a valid job
    (jobs_dir / "valid-001.json").write_text(
        json.dumps({
            "job_id": "valid-001", "project": "P", "scene": "S",
            "prompt": "A valid prompt for testing purposes here",
        })
    )
    # Write a malformed JSON
    (jobs_dir / "broken.json").write_text("{not valid json{{{")
    # Write a JSON with missing fields
    (jobs_dir / "incomplete.json").write_text(
        json.dumps({"job_id": "incomplete-001"})
    )

    fjm.JOBS_DIR = jobs_dir
    fjm.FLOW_QUEUE_DIR = queue_dir
    fjm.FLOW_RESULTS_DIR = results_dir
    fjm.QUEUE_DB = queue_dir / "queue.db"

    mgr = FlowJobManager()
    # Should have loaded valid job, skipped broken one
    assert mgr.get_job("valid-001") is not None
    # incomplete job might load but with defaults — check it doesn't crash
    print("  PASS: malformed JSON handled gracefully")


def main():
    print("=== Flow Job Manager Load Testing ===\n")
    test_100_jobs()
    assert test_many_identical_prompts(), "identical prompts test failed"
    test_restart_recovery()
    test_parallel_addition()
    assert test_duplicate_requests(), "duplicate requests test failed"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_malformed_json(Path(td))
    print("\n=== All load tests passed ===")


if __name__ == "__main__":
    main()
