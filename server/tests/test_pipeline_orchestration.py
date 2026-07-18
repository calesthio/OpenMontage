"""run_pipeline_job orchestration: happy path, resume, crash guard, budget gate.

_run_agent_stage (the LLM-driven part) is stubbed; these tests exercise the
runner's control flow — the area where most of this session's fixes landed.
"""

from __future__ import annotations

import asyncio
import time

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


async def test_required_artifact_missing_fails_fast(runner, monkeypatch):
    # A stage requiring an upstream artifact that was never produced must fail
    # immediately with a clear diagnostic, not silently launch the LLM call.
    called = []
    monkeypatch.setattr(stage_runner, "_run_agent_stage",
                        lambda *a, **k: called.append(a[1]) or True)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": False, "produces": ["research_brief"]},
        {"name": "script", "skill": None, "approval": False,
         "required_artifacts_in": ["research_brief"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    # research's stub never actually wrote research_brief.json, so script's
    # preflight must catch the gap and fail before ever calling _run_agent_stage
    # for "script".
    assert called == ["research"]
    job = runner.get("j")
    assert job["status"] == "failed"
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "research_brief" in failed[0]["message"]


async def test_required_artifact_present_proceeds(runner, monkeypatch, tmp_path):
    def write_then_succeed(job_id, stage_name, skill_text, project_dir, *a, **k):
        if stage_name == "research":
            (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (project_dir / "artifacts" / "research_brief.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_then_succeed)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": False, "produces": ["research_brief"]},
        {"name": "script", "skill": None, "approval": False,
         "required_artifacts_in": ["research_brief"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "completed"


async def test_concurrent_run_for_same_job_id_is_a_noop(runner, monkeypatch):
    # Regression: two overlapping run_pipeline_job calls for the same job_id
    # (e.g. a retry racing an already-live run) used to both drive the
    # pipeline concurrently — two LLM sessions writing artifacts for the same
    # project, clobbering each other. The in-process _ACTIVE_JOB_IDS guard
    # must make the second call an immediate no-op.
    calls = []
    def slow_stage(*a, **k):
        calls.append(1)
        time.sleep(0.05)   # runs inside asyncio.to_thread — a real sleep is fine here
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", slow_stage)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    first = asyncio.create_task(
        stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    )
    await asyncio.sleep(0.01)   # let the first call register itself as active
    # Second call for the SAME job_id while the first is still in flight.
    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    await first

    events = runner.get_events("j", after_seq=-1)
    dup_ignored = [e for e in events if "duplicate run_pipeline_job" in e.get("message", "")]
    assert len(dup_ignored) == 1
    assert runner.get("j")["status"] == "completed"
    assert "j" not in stage_runner._ACTIVE_JOB_IDS   # cleaned up after completion


async def test_stage_stopping_without_producing_artifact_fails_not_completes(runner, monkeypatch):
    # Regression: _run_agent_stage returning True only means the agent's LLM
    # loop ended with no further tool calls — e.g. it stopped to ask a human
    # instead of silently substituting a fallback provider (the correct
    # behavior when a generation tool fails, per the provider skill contract).
    # That was being treated as unconditional stage success: the stage got
    # added to completed_stages and PERMANENTLY skipped on every future
    # retry — retry could never re-run the one stage that actually needed it,
    # a dead end. The job must instead fail at the stage that stalled, and
    # NOT record it as completed, so a retry actually re-attempts it.
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: True)  # never writes anything
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "scene_plan", "skill": None, "approval": False, "produces": ["scene_plan"]},
        {"name": "assets", "skill": None, "approval": False, "produces": ["asset_manifest"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    assert job["current_stage"] == "scene_plan"        # fails at the FIRST stage that stalls
    assert "scene_plan" not in job["completed_stages"]  # NOT recorded — retry can re-attempt it
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "scene_plan" in failed[0]["message"]


async def test_compose_preview_ready_before_job_completes(runner, monkeypatch, tmp_path):
    # The compose stage's render is the actual deliverable, but publish
    # (packaging/distribution metadata) still has to run before the job is
    # "completed" — several more turns the user would otherwise wait through
    # with no way to see the render they're actually waiting on. A
    # preview_ready event (carrying the same render it'll serve as the final
    # one) must fire as soon as compose finishes, well before job_completed.
    def write_stage_output(job_id, stage_name, skill_text, project_dir, *a, **k):
        if stage_name == "compose":
            (project_dir / "renders").mkdir(parents=True, exist_ok=True)
            (project_dir / "renders" / "final.mp4").write_bytes(b"x")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_stage_output)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": False},
        {"name": "compose", "skill": None, "approval": False},
        {"name": "publish", "skill": None, "approval": False},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    evs = runner.get_events("j", after_seq=-1)
    types = [e["type"] for e in evs]
    preview_idx = types.index("preview_ready")
    completed_idx = types.index("job_completed")
    assert preview_idx < completed_idx   # surfaced well before the job finished
    assert evs[preview_idx]["render_url"] == "/media/p/renders/final.mp4"
    # Persisted on the job record too — so a page load/refresh mid-publish
    # (before job_completed) can still show it via the initial REST fetch.
    assert runner.get("j")["preview_render_url"] == "/media/p/renders/final.mp4"


async def test_partial_produces_fails_not_just_any_of_them(runner, monkeypatch, tmp_path):
    # Found live: compose declares produces=[render_report, final_review] and
    # publish's required_artifacts_in names final_review specifically. An agent
    # run that writes render_report but stops before writing final_review must
    # fail AT compose (with a message naming final_review) — not be treated as
    # "done enough" because at least one produces name exists, which would
    # cascade the failure one stage further downstream to publish with a more
    # confusing message and a wasted round-trip.
    def write_only_render_report(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts" / "render_report.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_only_render_report)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "compose", "skill": None, "approval": False,
         "produces": ["render_report", "final_review"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    assert "compose" not in job["completed_stages"]
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "final_review" in failed[0]["message"]
    # the artifact that WAS written must not appear in the missing list
    assert "'render_report'" not in failed[0]["message"]


async def test_approval_preview_uses_produces_name_not_stage_name(runner, monkeypatch):
    # Regression: many pipelines name a stage differently from what it
    # produces (e.g. stage "idea" → artifact "brief"). The old preview lookup
    # only checked stage_name (plus a single "proposal"→"proposal_packet"
    # alias), so it showed a null preview for every other mismatched stage
    # even though the agent's artifact wrote successfully.
    def write_brief(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts" / "brief.json").write_text('{"hook": "real content"}')
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_brief)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic",
                        [{"name": "idea", "skill": None, "approval": True, "produces": ["brief"]}])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    async def approver():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")
                return
    approver_task = asyncio.create_task(approver())
    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    await approver_task

    evs = runner.get_events("j", after_seq=-1)
    awaiting = next(e for e in evs if e["type"] == "awaiting_approval")
    assert awaiting["preview"] == {"hook": "real content"}


async def test_reject_retry_still_receives_budget_ceiling(runner, monkeypatch):
    # Regression: the reject-regenerate call to _run_agent_stage used to omit
    # budget_cny/base_cost entirely, so a reject-loop could keep spending past
    # the configured ceiling with no pre-call check at all. Assert the
    # reject-path call receives the same non-None ceiling as the initial run.
    seen_budget = []
    def stub(*a, **k):
        seen_budget.append(a[9])   # budget_cny positional arg
        # Simulate a real stage: write the declared produces artifact so the
        # post-success "did this stage actually produce anything" check passes.
        project_dir = a[3]
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts" / "script.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", stub)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic",
                        [{"name": "script", "skill": None, "approval": True, "produces": ["script"]}])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 50}})

    async def driver():
        rejected = False
        for _ in range(300):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] != "awaiting_approval":
                continue
            action = "reject" if not rejected else "approve"
            runner.set_approval("j", action, "try again" if action == "reject" else "")
            if action == "reject":
                rejected = True
            else:
                return
    driver_task = asyncio.create_task(driver())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": {"budget_cny": 50}})
    await driver_task

    assert seen_budget == [50, 50]     # initial run + reject-retry both saw the real ceiling
    assert runner.get("j")["status"] == "completed"


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
