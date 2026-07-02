"""run_pipeline_job orchestration: happy path, resume, crash guard, budget gate.

_run_agent_stage (the LLM-driven part) is stubbed; these tests exercise the
runner's control flow — the area where most of this session's fixes landed.
"""

from __future__ import annotations

import asyncio

import pytest

from app.runner import stage_runner
from app.store import JobStore

TWO_STAGES = [
    {"name": "research", "skill": "skills/none.md", "approval": False},
    {"name": "compose", "skill": "skills/none.md", "approval": False},
]


@pytest.fixture
def runner(tmp_path, monkeypatch):
    ts = JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(stage_runner, "job_store", ts)
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", TWO_STAGES)
    return ts


def _events(store, jid):
    return [e["type"] for e in store.get_events(jid, after_seq=-1)]


async def test_skill_less_stage_does_not_crash(runner, monkeypatch):
    # Regression: a manifest stage with no `skill` key must resolve to
    # skill=None and fall through to the placeholder text, not crash trying to
    # read_text() on OM_ROOT (Path(OM_ROOT) / "" == OM_ROOT, a real directory).
    seen_skill_text = []
    def capture(job_id, stage_name, skill_text, *a, **k):
        seen_skill_text.append(skill_text)
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", capture)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic",
                        [{"name": "research", "skill": None, "approval": False}])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "completed"
    assert "director" in seen_skill_text[0]   # placeholder fallback text used


async def test_happy_path_completes(runner, monkeypatch):
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: True)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "completed"
    assert set(job["completed_stages"]) == {"research", "compose"}
    assert "job_completed" in _events(runner, "j")


async def test_resume_skips_completed_stages(runner, monkeypatch):
    ran = []
    monkeypatch.setattr(stage_runner, "_run_agent_stage",
                        lambda *a, **k: ran.append(a[1]) or True)  # a[1] = stage_name
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})
    runner.update("j", completed_stages=["research"])   # research already done

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert ran == ["compose"]                    # research skipped, only compose ran
    assert "stage_skipped" in _events(runner, "j")
    assert runner.get("j")["status"] == "completed"


async def test_unhandled_error_marks_failed(runner, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(stage_runner, "_run_agent_stage", boom)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    evs = runner.get_events("j", after_seq=-1)
    failed = [e for e in evs if e["type"] == "job_failed"]
    assert failed and "Unhandled pipeline error" in failed[0].get("message", "")


async def test_budget_gate_pauses_then_resumes_on_approve(runner, monkeypatch):
    # Each stage "spends" 5 CNY against a 1 CNY budget → gate must pause.
    def spend(*a, **k):
        acc = a[7]              # cost_accumulator positional arg
        if acc is not None:
            acc.append(5.0)
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 1}})

    async def approver():
        # Wait for the gate to open, then approve the overspend once.
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")
                return
    approver_task = asyncio.create_task(approver())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": {"budget_cny": 1}})
    await approver_task

    evs = _events(runner, "j")
    assert "budget_exceeded" in evs
    assert runner.get("j")["status"] == "completed"      # overspend approved → finished


async def test_budget_gate_aborts_on_reject(runner, monkeypatch):
    def spend(*a, **k):
        acc = a[7]
        if acc is not None:
            acc.append(5.0)
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 1}})

    async def rejecter():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "reject", "too pricey")
                return
    rejecter_task = asyncio.create_task(rejecter())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": {"budget_cny": 1}})
    await rejecter_task

    assert runner.get("j")["status"] == "failed"
