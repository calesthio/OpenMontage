"""run_pipeline_job orchestration: happy path, resume, crash guard, budget gate.

_run_agent_stage (the LLM-driven part) is stubbed; these tests exercise the
runner's control flow — the area where most of this session's fixes landed.
"""

from __future__ import annotations

import asyncio
import json
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


async def test_happy_path_completes(runner, monkeypatch, tmp_path):
    # A genuinely completed compose stage must be backed by a real render
    # file (see test_compose_fails_without_a_real_render_file below) — create
    # one so this test represents an honest success, not the fabricated-report
    # case.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: True)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "completed"
    assert set(job["completed_stages"]) == {"research", "compose"}
    assert "job_completed" in _events(runner, "j")


async def test_resume_skips_completed_stages(runner, monkeypatch, tmp_path):
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")
    ran = []
    monkeypatch.setattr(stage_runner, "_run_agent_stage",
                        lambda *a, **k: ran.append(a[1]) or True)  # a[1] = stage_name
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})
    runner.update("j", completed_stages=["research"])   # research already done

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert ran == ["compose"]                    # research skipped, only compose ran
    assert "stage_skipped" in _events(runner, "j")
    assert runner.get("j")["status"] == "completed"


async def test_compose_fails_without_a_real_render_file(runner, monkeypatch):
    # Confirmed live: an agent that hit a video_compose failure fabricated a
    # plausible-looking render_report (invented file paths under a DIFFERENT
    # project name, invented file sizes, an invented render duration) instead
    # of retrying or reporting the failure honestly — and the job showed as
    # "completed" with zero actual deliverable. Writing render_report/
    # final_review must not be enough; a real file under renders/ is required.
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: True)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    assert "compose" not in job["completed_stages"]
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "no actual render file exists" in failed[-1]["message"]


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


async def test_concurrent_run_for_same_job_id_is_a_noop(runner, monkeypatch, tmp_path):
    # Regression: two overlapping run_pipeline_job calls for the same job_id
    # (e.g. a retry racing an already-live run) used to both drive the
    # pipeline concurrently — two LLM sessions writing artifacts for the same
    # project, clobbering each other. The in-process _ACTIVE_JOB_IDS guard
    # must make the second call an immediate no-op.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")
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
        seen_budget.append(k["budget_cny"])   # keyword-only arg
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


async def test_budget_gate_pauses_then_resumes_on_approve(runner, monkeypatch, tmp_path):
    # Each stage "spends" 5 CNY against a 1 CNY budget → gate must pause.
    # TWO_STAGES has two stages (research, compose), and the gate now
    # re-arms at a raised ceiling on each approval instead of disabling
    # itself forever (see test_budget_gate_rearms_at_higher_ceiling_instead_of_disabling)
    # — so the SECOND stage's spend can legitimately blow through the newly
    # raised ceiling too and prompt again. The approver below approves every
    # prompt it sees, rather than exactly once, to match that.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")
    def spend(*a, **k):
        acc = k["cost_accumulator"]   # keyword-only arg
        if acc is not None:
            acc.append(5.0)
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 1}})

    async def approver():
        # Wait for the gate to open, then approve the overspend — every time
        # it opens, since more than one stage in this job can trigger it.
        for _ in range(500):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")
    approver_task = asyncio.create_task(approver())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": {"budget_cny": 1}})
    approver_task.cancel()
    try:
        await approver_task
    except asyncio.CancelledError:
        pass

    evs = _events(runner, "j")
    assert "budget_exceeded" in evs
    assert runner.get("j")["status"] == "completed"      # overspend(s) approved → finished


async def test_budget_gate_honors_user_chosen_ceiling(runner, monkeypatch, tmp_path):
    # Roadmap 1.3: an approve carrying new_budget_cny replaces the spent×1.2
    # ratchet with the user's own absolute cap.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")
    def spend(*a, **k):
        acc = k["cost_accumulator"]
        if acc is not None and not acc:
            acc.append(5.0)   # only the first stage spends
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    opts = {"budget_cny": 1}
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": opts})

    async def approver():
        for _ in range(500):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "", new_budget_cny=200.0)
                return
    approver_task = asyncio.create_task(approver())
    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": opts})
    await approver_task

    approved = [e for e in runner.get_events("j", after_seq=-1)
                if e["type"] == "stage_approved" and e.get("stage") == "budget"]
    assert approved and approved[0]["budget_cny"] == 200.0   # not spent×1.2 (=6.0)
    assert approved[0]["previous_budget_cny"] == 1
    assert runner.get("j")["status"] == "completed"


async def test_budget_gate_clamps_user_ceiling_below_spend(runner, monkeypatch, tmp_path):
    # A user cap BELOW what's already spent would re-open the gate instantly
    # forever — clamp to the actual spend floor.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")
    def spend(*a, **k):
        acc = k["cost_accumulator"]
        if acc is not None and not acc:
            acc.append(5.0)
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    opts = {"budget_cny": 1}
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": opts})

    async def approver():
        for _ in range(500):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "", new_budget_cny=0.5)
                return
    approver_task = asyncio.create_task(approver())
    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": opts})
    await approver_task

    approved = [e for e in runner.get_events("j", after_seq=-1)
                if e["type"] == "stage_approved" and e.get("stage") == "budget"]
    assert approved and approved[0]["budget_cny"] == 5.0   # clamped to spend
    assert runner.get("j")["status"] == "completed"


async def test_budget_gate_aborts_on_reject(runner, monkeypatch):
    def spend(*a, **k):
        acc = k["cost_accumulator"]
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


# ── mid-stage sample-preview gate: real async pause, not auto-continue ──────

async def test_sample_preview_gate_pauses_then_resumes_same_conversation(runner, monkeypatch, tmp_path):
    # A stage that stops mid-task (SamplePreviewNeeded) must genuinely pause
    # — emit awaiting_approval with gate="sample_preview", wait for a real
    # approval — and then resume with the EXACT conversation it paused with,
    # not restart from scratch.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    paused_messages = [{"role": "user", "content": "original prompt"},
                        {"role": "assistant", "content": "here's a sample, please confirm"}]
    resumed_with = []

    def flaky_research(*a, **k):
        resume_messages = k["resume_messages"]
        if resume_messages is None:
            raise stage_runner.SamplePreviewNeeded(
                messages=paused_messages, preview_text="here's a sample, please confirm",
                sample_iteration=0,
            )
        resumed_with.append(resume_messages)
        return True

    def compose_ok(*a, **k):
        return True

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else compose_ok)(*a, **k)

    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
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
    gate_event = next(e for e in evs if e["type"] == "awaiting_approval" and e.get("gate") == "sample_preview")
    assert gate_event["preview"]["text"] == "here's a sample, please confirm"
    assert gate_event["preview"]["iteration"] == 1
    approved_event = next(e for e in evs if e["type"] == "stage_approved" and e.get("gate") == "sample_preview")
    assert approved_event
    assert runner.get("j")["status"] == "completed"
    # Resumed with the paused conversation plus the approval turn appended —
    # not a freshly rebuilt prompt.
    assert resumed_with
    assert resumed_with[0][:2] == paused_messages
    assert resumed_with[0][-1]["content"] == "Approved — proceed to complete the stage."


async def test_sample_preview_gate_reject_carries_feedback_into_resume(runner, monkeypatch, tmp_path):
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    resumed_with = []

    def flaky_research(*a, **k):
        resume_messages = k["resume_messages"]
        if resume_messages is None:
            raise stage_runner.SamplePreviewNeeded(
                messages=[{"role": "user", "content": "orig"}], preview_text="sample",
                sample_iteration=0,
            )
        resumed_with.append(resume_messages)
        return True

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else (lambda *a, **k: True))(*a, **k)

    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    async def rejecter():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "reject", "wrong tone, make it warmer")
                return
    rejecter_task = asyncio.create_task(rejecter())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    await rejecter_task

    assert resumed_with
    assert "wrong tone, make it warmer" in resumed_with[0][-1]["content"]
    assert runner.get("j")["status"] == "completed"


async def test_automatic_retry_folds_last_failure_into_feedback(runner, monkeypatch, tmp_path):
    # Regression: the automatic stage-retry loop (distinct from the human
    # reject loop above) used to call _run_agent_stage again with
    # feedback="" every time — a brand-new conversation with no idea what
    # went wrong last time, so a deterministic failure reproduced identically
    # up to MAX_ROUNDS times.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    feedback_seen = []

    def flaky_research(*a, **k):
        feedback = k["feedback"]
        feedback_seen.append(feedback)
        if len(feedback_seen) == 1:
            stage_runner._emit(a[0], {"type": "error", "stage": a[1], "message": "malformed tool call: xyz"})
            return False
        return True

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else (lambda *a, **k: True))(*a, **k)

    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "completed"
    assert len(feedback_seen) == 2
    assert feedback_seen[0] == ""             # first attempt: no prior failure
    assert "malformed tool call: xyz" in feedback_seen[1]   # retry: knows what broke


# ── job_failed emits must carry an actionable diagnostic message ────────────

async def test_job_failed_after_max_rounds_includes_diagnostic_message(runner, monkeypatch):
    # Regression: the "ran out of retries" job_failed emit had no `message`
    # field at all, unlike the missing-produces failure emitted right below
    # it in the source — operators got zero actionable diagnostic for this
    # failure mode specifically.
    def always_fails(*a, **k):
        stage_runner._emit(a[0], {"type": "error", "stage": a[1], "message": "gateway timed out"})
        return False
    monkeypatch.setattr(stage_runner, "_run_agent_stage", always_fails)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed
    assert "gateway timed out" in failed[-1].get("message", "")


async def test_job_failed_after_reject_regenerate_failure_includes_diagnostic_message(runner, monkeypatch):
    # Same gap in the human-reject-then-regenerate loop: a regenerate attempt
    # that fails outright must also surface the last recorded error rather
    # than an empty message.
    calls = []

    def stub(job_id, stage_name, skill_text, project_dir, *a, **k):
        if stage_name != "research":
            return True
        calls.append(1)
        if len(calls) == 1:
            (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (project_dir / "artifacts" / "research.json").write_text("{}")
            return True
        stage_runner._emit(job_id, {"type": "error", "stage": stage_name, "message": "regen blew up"})
        return False

    monkeypatch.setattr(stage_runner, "_run_agent_stage", stub)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": True, "produces": ["research"]},
        {"name": "compose", "skill": None, "approval": False},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    async def rejecter():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "reject", "try again")
                return
    rejecter_task = asyncio.create_task(rejecter())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    await rejecter_task

    job = runner.get("j")
    assert job["status"] == "failed"
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed
    assert "regen blew up" in failed[-1].get("message", "")


# ── job-completion render check must not depend on the literal "compose" name

async def test_job_completion_refuses_without_render_file_even_if_stage_not_named_compose(
    runner, monkeypatch,
):
    # Regression: the per-stage anti-fabrication check (right after a stage
    # finishes) is keyed on the literal stage name "compose" — a manifest
    # whose render-producing stage is named something else entirely bypasses
    # it. The job-completion block itself must independently refuse to mark
    # the job "completed" without a real discovered render file, keyed off
    # the stage's declared `produces` (canonical compose output
    # "render_report" per AGENT_GUIDE.md's Stage Agents table), not its name.
    def write_report_no_video(job_id, stage_name, skill_text, project_dir, *a, **k):
        if stage_name == "final_render":
            (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (project_dir / "artifacts" / "render_report.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_report_no_video)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": False},
        {"name": "final_render", "skill": None, "approval": False, "produces": ["render_report"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "no render file was discovered" in failed[-1]["message"]


async def test_job_completion_allows_pipelines_with_no_render_producing_stage(runner, monkeypatch):
    # A pipeline that genuinely never declares a render-producing stage (e.g.
    # the framework-smoke test pipeline, which stops at "script") must NOT be
    # forced to have a render file — the completion-block fallback is a no-op
    # for it.
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: True)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": False},
        {"name": "script", "skill": None, "approval": False},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "completed"


# ── compose must not silently complete with a missing A/B variant ──────────

async def test_compose_fails_when_a_declared_variant_never_rendered(runner, monkeypatch, tmp_path):
    # 2 of 3 declared A/B variants render; the job must not silently complete
    # with the 3rd variant's failure hidden — the plain "does ANY render file
    # exist" check alone would pass here.
    renders = tmp_path / "projects" / "p" / "renders"
    renders.mkdir(parents=True)
    (renders / "final_ltx2.mp4").write_bytes(b"x")
    (renders / "final_wan2-2.mp4").write_bytes(b"y")
    # no final_kling-1.mp4 — this variant's generation failed
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: True)
    data = {
        "project_name": "p", "pipeline": "cinematic",
        "options": {"video_model_variants": ["ltx2", "wan2.2", "kling-1"]},
    }
    runner.create("j", data)

    await stage_runner.run_pipeline_job("j", data)

    job = runner.get("j")
    assert job["status"] == "failed"
    assert "compose" not in job["completed_stages"]
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "kling-1" in failed[-1]["message"]


# ── budget re-arm: approving an overspend must not waive checks forever ────

async def test_budget_gate_rearms_at_higher_ceiling_instead_of_disabling(runner, monkeypatch, tmp_path):
    # Regression: approving one overspend used to permanently disable BOTH
    # the pre-call and between-stage budget checks for every remaining stage
    # of the job (a `budget_overridden` flag passed None instead of
    # budget_cny to every subsequent _run_agent_stage call). A user approving
    # a small overage early must not unknowingly waive protection for a far
    # more expensive stage later — the ceiling must instead be re-armed
    # higher after each approval, so a later stage that blows through the
    # NEW ceiling still triggers a fresh approval.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    seen_budget = []

    def spend(*a, **k):
        seen_budget.append(k["budget_cny"])   # keyword-only arg, as of THIS stage's start
        acc = k["cost_accumulator"]           # keyword-only arg
        if acc is not None:
            acc.append(5.0)        # every stage "spends" another 5 CNY
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "research", "skill": None, "approval": False},
        {"name": "proposal", "skill": None, "approval": False},
        {"name": "compose", "skill": None, "approval": False},
    ])
    data = {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 1}}
    runner.create("j", data)

    async def approver():
        # Approve every overspend prompt that comes up (there should be one
        # after each of the 3 stages, since each re-armed ceiling is blown
        # through by the next stage's spend too).
        for _ in range(500):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")

    approver_task = asyncio.create_task(approver())
    await stage_runner.run_pipeline_job("j", data)
    approver_task.cancel()
    try:
        await approver_task
    except asyncio.CancelledError:
        pass

    evs = _events(runner, "j")
    assert evs.count("budget_exceeded") >= 2   # gated again after the ceiling was raised
    assert runner.get("j")["status"] == "completed"
    # Every stage still saw a real (non-None) ceiling — never disabled.
    assert all(b is not None for b in seen_budget)
    # Each re-arm strictly raises the ceiling (never resets back down or
    # stays flat) as spend grows.
    assert seen_budget == sorted(seen_budget)
    assert len(set(seen_budget)) > 1


async def test_budget_gate_rearm_uses_projected_cost_not_just_spent(runner, monkeypatch, tmp_path):
    # Regression: on the pre-call-block path, `spent` (base_cost +
    # cost_accumulator) does NOT include the cost of the call that is
    # actually blocked — that call never ran. budget_cny=10, first paid call
    # est_cost=50 (nothing spent yet, cost_accumulator=[]) → the OLD formula
    # re-armed to round(0 * 1.2, 4) == 0, LOWER than the original ceiling, so
    # the identical call would be blocked again forever. The re-arm must
    # instead use max(old_ceiling, projected_cny) so it's always enough to
    # admit the blocking call.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    budget_exc = stage_runner.BudgetExceededError(
        "over budget", tool_name="maas_video", est_cost=50.0, projected_cny=50.0,
    )
    seen_budget = []

    def flaky_research(*a, **k):
        seen_budget.append(k["budget_cny"])   # keyword-only arg
        resume_messages = k["resume_messages"]
        if resume_messages is None:
            raise stage_runner.BudgetGateNeeded(
                messages=[{"role": "user", "content": "orig"}],
                preview_text="blocked", budget_exc=budget_exc,
            )
        return True

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else (lambda *a, **k: True))(*a, **k)

    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
    data = {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 10}}
    runner.create("j", data)

    async def approver():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")
                return
    approver_task = asyncio.create_task(approver())

    await stage_runner.run_pipeline_job("j", data)
    await approver_task

    assert runner.get("j")["status"] == "completed"
    # First call saw the original ceiling (10); the retry after approval saw
    # a re-armed ceiling that's enough to admit the ¥50 call — NOT 0 (which
    # round(spent * 1.2, 4) alone would have produced) and not below 10.
    assert seen_budget[0] == 10
    assert seen_budget[1] >= 50
    assert seen_budget[1] > seen_budget[0]


async def test_budget_gate_awaiting_approval_names_the_blocked_call(runner, monkeypatch, tmp_path):
    # Regression: force=True firing purely from a pre-call block (spent may
    # still be <= budget_cny) made over_by_cny come out negative — the UI
    # showed "under budget" while asking approval for an apparent overspend,
    # with no visibility into what triggered it. The blocked tool_name/
    # est_cost must be surfaced explicitly.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    budget_exc = stage_runner.BudgetExceededError(
        "over budget", tool_name="maas_video", est_cost=50.0, projected_cny=50.0,
    )

    def flaky_research(*a, **k):
        resume_messages = k["resume_messages"]
        if resume_messages is None:
            raise stage_runner.BudgetGateNeeded(
                messages=[{"role": "user", "content": "orig"}],
                preview_text="blocked", budget_exc=budget_exc,
            )
        return True

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else (lambda *a, **k: True))(*a, **k)

    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
    data = {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 10}}
    runner.create("j", data)

    async def approver():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")
                return
    approver_task = asyncio.create_task(approver())

    await stage_runner.run_pipeline_job("j", data)
    await approver_task

    evs = runner.get_events("j", after_seq=-1)
    gate_event = next(e for e in evs if e["type"] == "awaiting_approval" and e.get("gate") == "budget")
    assert gate_event["preview"]["blocked_tool_name"] == "maas_video"
    assert gate_event["preview"]["blocked_est_cost_cny"] == 50.0
    budget_exceeded_event = next(e for e in evs if e["type"] == "budget_exceeded" and "blocked_tool_name" in e)
    assert budget_exceeded_event["blocked_tool_name"] == "maas_video"


# ── BudgetGateNeeded: resume the SAME conversation, not a fresh one ─────────

async def test_budget_gate_needed_pauses_then_resumes_same_conversation(runner, monkeypatch, tmp_path):
    # Regression: a pre-call budget block used to unwind the whole stage as a
    # bare BudgetExceededError with no `messages` — approval then restarted
    # the stage conversation from scratch, orphaning any assets already
    # generated earlier in that SAME stage's conversation. It must now pause
    # for a real approval and resume with the SAME conversation, and the
    # resumed message list must be valid enough for a real OpenAI-shaped API
    # to accept: every tool_call_id in the paused assistant turn (including
    # ones never reached because a sibling call blocked first) must have a
    # matching tool-role response.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    paused_messages = [
        {"role": "user", "content": "original prompt"},
        {"role": "assistant", "content": "generating", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "run_openmontage_tool", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {"name": "run_openmontage_tool", "arguments": "{}"}},
            {"id": "c3", "type": "function", "function": {"name": "run_openmontage_tool", "arguments": "{}"}},
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"success": true}'},   # already ran
        {"role": "tool", "tool_call_id": "c2", "content": "BLOCKED: awaiting budget approval"},
        {"role": "tool", "tool_call_id": "c3", "content": "SKIPPED: stage paused for budget approval"},
    ]
    budget_exc = stage_runner.BudgetExceededError(
        "over budget", tool_name="maas_video", est_cost=50.0, projected_cny=60.0,
    )
    resumed_with = []

    def flaky_research(*a, **k):
        resume_messages = k["resume_messages"]
        if resume_messages is None:
            raise stage_runner.BudgetGateNeeded(
                messages=paused_messages, preview_text="blocked", budget_exc=budget_exc,
            )
        resumed_with.append(resume_messages)
        return True

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else (lambda *a, **k: True))(*a, **k)

    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
    data = {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 1}}
    runner.create("j", data)

    async def approver():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.set_approval("j", "approve", "")
                return
    approver_task = asyncio.create_task(approver())

    await stage_runner.run_pipeline_job("j", data)
    await approver_task

    assert runner.get("j")["status"] == "completed"
    assert resumed_with
    resumed = resumed_with[0]
    # Prior turns intact — not restarted from scratch.
    assert resumed[:5] == paused_messages
    assert resumed[-1]["role"] == "user"
    assert "approved" in resumed[-1]["content"].lower()

    # Every tool_call in the assistant turn has a matching tool-role response
    # — a real OpenAI-shaped API would reject the request otherwise.
    assistant_turn = next(m for m in resumed if m.get("role") == "assistant" and m.get("tool_calls"))
    tool_call_ids = {tc["id"] for tc in assistant_turn["tool_calls"]}
    tool_response_ids = {m["tool_call_id"] for m in resumed if m.get("role") == "tool"}
    assert tool_call_ids <= tool_response_ids


# ── approval ladder: remind → expire, never auto-decide (roadmap 0.2) ───────

async def _answer_gates(store, jid, actions):
    """Wait for successive awaiting_approval flips and answer each with the
    scripted (action, feedback) tuples. Returns when the script is spent."""
    for action, feedback in actions:
        for _ in range(500):
            await asyncio.sleep(0.005)
            if (store.get(jid) or {}).get("status") == "awaiting_approval":
                break
        assert store.get(jid)["status"] == "awaiting_approval", (
            f"gate never opened for scripted answer {action!r}"
        )
        assert store.set_approval(jid, action, feedback)
        # Let the runner consume the decision before watching for the next flip.
        for _ in range(500):
            await asyncio.sleep(0.005)
            if (store.get(jid) or {}).get("status") != "awaiting_approval":
                break


async def test_approval_reminder_events_then_decision_honored(runner, monkeypatch):
    monkeypatch.setattr(stage_runner, "APPROVAL_REMINDER_SECONDS", 0.02)
    monkeypatch.setattr(stage_runner, "APPROVAL_EXPIRY_SECONDS", 30.0)

    def writes_artifact(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts" / "brief.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", writes_artifact)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "idea", "skill": None, "approval": True, "produces": ["brief"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    task = asyncio.create_task(
        stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    )
    # Let several reminder slices elapse before answering.
    await asyncio.sleep(0.1)
    assert runner.get("j")["status"] == "awaiting_approval"
    assert runner.set_approval("j", "approve", "")
    await task

    assert runner.get("j")["status"] == "completed"
    events = runner.get_events("j", after_seq=-1)
    reminders = [e for e in events if e["type"] == "approval_reminder"]
    assert reminders, "reminder ladder never fired"
    assert all(e["stage"] == "idea" and e["expires_at"] > 0 for e in reminders)
    # The awaiting_approval event itself must carry the countdown fields.
    awaiting = [e for e in events if e["type"] == "awaiting_approval"]
    assert awaiting and awaiting[0]["expires_at"] > time.time()


async def test_approval_expiry_fails_loudly_never_auto_decides(runner, monkeypatch):
    monkeypatch.setattr(stage_runner, "APPROVAL_REMINDER_SECONDS", 0.02)
    monkeypatch.setattr(stage_runner, "APPROVAL_EXPIRY_SECONDS", 0.06)

    calls = []

    def writes_artifact(job_id, stage_name, skill_text, project_dir, *a, **k):
        calls.append(stage_name)
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts" / "brief.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", writes_artifact)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "idea", "skill": None, "approval": True, "produces": ["brief"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    # The stage was NOT auto-approved (not in completed_stages) and NOT
    # auto-rejected (no regenerate ran — exactly one agent call).
    assert "idea" not in job.get("completed_stages", [])
    assert calls == ["idea"]
    events = _events(runner, "j")
    assert "stage_approved" not in events
    assert "stage_rejected" not in events
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert "approval window" in failed[-1]["message"]


# ── max_revisions_per_stage enforcement (roadmap 0.4) ────────────────────────

def _revision_pipeline(monkeypatch, run_counter):
    def regenerating_agent(job_id, stage_name, skill_text, project_dir, *a, **k):
        run_counter.append(stage_name)
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        p = project_dir / "artifacts" / "brief.json"
        p.write_text(json.dumps({"round": len(run_counter)}))
        # Force a strictly newer mtime so the regenerate-actually-rewrote
        # check (_artifact_mtimes) sees a genuine rewrite each round.
        import os as _os
        st = p.stat()
        _os.utime(p, (st.st_atime, st.st_mtime + len(run_counter)))
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", regenerating_agent)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "idea", "skill": None, "approval": True, "produces": ["brief"]},
    ])


async def test_reject_loop_is_bounded_and_exhaustion_can_accept_as_is(runner, monkeypatch):
    runs: list[str] = []
    _revision_pipeline(monkeypatch, runs)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    task = asyncio.create_task(
        stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    )
    # 4 rejects: rounds 1-3 regenerate; the 4th must hit the exhaustion gate
    # instead of paying for another round. Approving there accepts as-is.
    answers = [("reject", f"no {i}") for i in range(4)] + [("approve", "")]
    await _answer_gates(runner, "j", answers)
    await task

    job = runner.get("j")
    assert job["status"] == "completed"
    # initial run + exactly 3 regenerates — never a 5th agent call.
    assert len(runs) == 4
    gates = [e.get("gate") for e in runner.get_events("j", after_seq=-1)
             if e["type"] == "awaiting_approval"]
    assert gates.count("revisions_exhausted") == 1


async def test_reject_at_exhaustion_gate_stops_the_job(runner, monkeypatch):
    runs: list[str] = []
    _revision_pipeline(monkeypatch, runs)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    task = asyncio.create_task(
        stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    )
    answers = [("reject", f"no {i}") for i in range(4)] + [("reject", "stop")]
    await _answer_gates(runner, "j", answers)
    await task

    job = runner.get("j")
    assert job["status"] == "failed"
    assert len(runs) == 4   # the final reject bought no additional round
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert "revision" in failed[-1]["message"]


# ── inline artifact edit must survive into the next stage ───────────────────

async def test_inline_edit_survives_into_next_stage(runner, monkeypatch, tmp_path):
    # Regression (silent inline-edit discard): the /artifact endpoint used to
    # write artifacts/<stage>.json even when the stage's produces name
    # differed (stage "idea" produces "brief") — an orphan file. The next
    # stage's required_artifacts_in loaded the ORIGINAL brief.json; the
    # user's edit was silently ignored while the UI said "saved". This test
    # drives the REAL router handler against the REAL runner: the edit made
    # at the approval gate must be exactly what the next stage consumes.
    from app.routers import jobs as jobs_router
    from app.routers.jobs import SaveArtifactRequest, save_artifact

    monkeypatch.setattr(jobs_router, "job_store", runner)
    monkeypatch.setattr(jobs_router, "OM_ROOT", tmp_path)

    seen_by_script_stage = {}

    def fake_agent(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "idea":
            (project_dir / "artifacts" / "brief.json").write_text(
                json.dumps({"hook": "original"})
            )
        if stage_name == "script":
            seen_by_script_stage.update(
                json.loads((project_dir / "artifacts" / "brief.json").read_text())
            )
            (project_dir / "artifacts" / "script.json").write_text("{}")
        return True

    monkeypatch.setattr(stage_runner, "_run_agent_stage", fake_agent)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "idea", "skill": None, "approval": True, "produces": ["brief"]},
        {"name": "script", "skill": None, "approval": False, "produces": ["script"],
         "required_artifacts_in": ["brief"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    task = asyncio.create_task(
        stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    )
    for _ in range(200):
        await asyncio.sleep(0.01)
        if (runner.get("j") or {}).get("status") == "awaiting_approval":
            break
    assert runner.get("j")["status"] == "awaiting_approval"

    # The UI's inline edit: sent with the STAGE name (what approval-panel.tsx
    # sends today) — must resolve to the produces name "brief".
    resp = await save_artifact("j", SaveArtifactRequest(stage="idea", content={"hook": "edited"}))
    assert resp["saved"] == "brief"

    assert runner.set_approval("j", "approve", "")
    await task

    assert runner.get("j")["status"] == "completed"
    assert seen_by_script_stage == {"hook": "edited"}


# ── publish anti-fabrication (generalized render/export-file check) ─────────

def _publish_log_with_export(export_path: str) -> dict:
    return {
        "version": "1.0",
        "entries": [{
            "platform": "youtube",
            "status": "exported",
            "export_path": export_path,
            "timestamp": "2026-01-01T00:00:00Z",
        }],
    }


async def test_publish_stage_fails_on_fabricated_publish_log(runner, monkeypatch, tmp_path):
    # Confirmed live: a publish_log artifact claimed 5 real export files
    # (teaser cut, platform-specific crops, poster frame) that were never
    # generated — no exports/ directory ever created, zero video-processing
    # tool calls in that stage's trace. Claiming status="exported" with an
    # export_path must not be enough — a real file must back it up.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    def write_fabricated_publish_log(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "compose":
            (project_dir / "artifacts" / "render_report.json").write_text("{}")
        if stage_name == "publish":
            (project_dir / "artifacts" / "publish_log.json").write_text(
                json.dumps(_publish_log_with_export("exports/teaser.mp4"))
            )
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_fabricated_publish_log)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "compose", "skill": None, "approval": False, "produces": ["render_report"]},
        {"name": "publish", "skill": None, "approval": False, "produces": ["publish_log"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    assert "publish" not in job["completed_stages"]
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "exports/teaser.mp4" in failed[-1]["message"]


async def test_publish_stage_accepts_real_export_bundle_output(runner, monkeypatch, tmp_path):
    # Cross-module regression: the canonical publish tool
    # (tools/publishers/export_bundle.py) writes the bundle's ROOT DIRECTORY
    # as export_path — not a file. The validator's original is_file()-only
    # check therefore hard-failed every genuine export_bundle run: the
    # publish happy path was structurally dead. Run the REAL tool and feed
    # its actual publish_log through the pipeline's validation.
    from tools.publishers.export_bundle import ExportBundle

    renders = tmp_path / "projects" / "p" / "renders"
    renders.mkdir(parents=True)
    (renders / "final.mp4").write_bytes(b"real render bytes")

    def publish_via_real_export_bundle(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "compose":
            (project_dir / "artifacts" / "render_report.json").write_text("{}")
        if stage_name == "publish":
            result = ExportBundle().execute({
                "video_path": str(project_dir / "renders" / "final.mp4"),
                "title": "Cross-module regression",
            })
            assert result.success, result.error
            (project_dir / "artifacts" / "publish_log.json").write_text(
                json.dumps(result.data["publish_log"])
            )
        return True

    monkeypatch.setattr(stage_runner, "_run_agent_stage", publish_via_real_export_bundle)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "compose", "skill": None, "approval": False, "produces": ["render_report"]},
        {"name": "publish", "skill": None, "approval": False, "produces": ["publish_log"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "completed", [
        e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"
    ]
    assert "publish" in job["completed_stages"]


async def test_publish_stage_fails_on_fabricated_export_directory(runner, monkeypatch, tmp_path):
    # Accepting directories must not reopen the fabrication hole: an
    # export_path naming an EMPTY directory (mkdir'd but never populated)
    # still proves nothing was exported and must fail.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    def write_empty_dir_publish_log(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "compose":
            (project_dir / "artifacts" / "render_report.json").write_text("{}")
        if stage_name == "publish":
            (project_dir / "exports").mkdir(parents=True, exist_ok=True)
            (project_dir / "artifacts" / "publish_log.json").write_text(
                json.dumps(_publish_log_with_export("exports"))
            )
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_empty_dir_publish_log)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "compose", "skill": None, "approval": False, "produces": ["render_report"]},
        {"name": "publish", "skill": None, "approval": False, "produces": ["publish_log"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "failed"


async def test_publish_stage_passes_with_genuine_exports(runner, monkeypatch, tmp_path):
    # The mirror-image case: real files on disk at the claimed export_path
    # must NOT be flagged.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    def write_genuine_publish_log(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "compose":
            (project_dir / "artifacts" / "render_report.json").write_text("{}")
        if stage_name == "publish":
            (project_dir / "exports").mkdir(parents=True, exist_ok=True)
            (project_dir / "exports" / "teaser.mp4").write_bytes(b"real bytes")
            (project_dir / "artifacts" / "publish_log.json").write_text(
                json.dumps(_publish_log_with_export("exports/teaser.mp4"))
            )
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_genuine_publish_log)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "compose", "skill": None, "approval": False, "produces": ["render_report"]},
        {"name": "publish", "skill": None, "approval": False, "produces": ["publish_log"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "completed"


# ── edit-stage render_runtime consistency (Fix 8) ───────────────────────────

async def test_edit_stage_fails_on_silent_render_runtime_divergence(runner, monkeypatch, tmp_path):
    # Confirmed live: proposal locked a render_runtime with an explicit
    # decision_log entry demanding no silent fallback to FFmpeg, yet
    # edit_decisions silently switched render_runtime to 'ffmpeg' with no new
    # decision_log entry and no escalation — the edit stage has no human
    # approval gate to catch this on its own.
    def write_diverging_edit_decisions(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "proposal":
            (project_dir / "artifacts" / "proposal_packet.json").write_text(json.dumps(
                {"production_plan": {"render_runtime": "remotion"}}
            ))
        if stage_name == "edit":
            (project_dir / "artifacts" / "edit_decisions.json").write_text(json.dumps(
                {"render_runtime": "ffmpeg"}
            ))
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_diverging_edit_decisions)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "proposal", "skill": None, "approval": False, "produces": ["proposal_packet"]},
        {"name": "edit", "skill": None, "approval": False, "produces": ["edit_decisions"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    job = runner.get("j")
    assert job["status"] == "failed"
    assert "edit" not in job["completed_stages"]
    failed = [e for e in runner.get_events("j", after_seq=-1) if e["type"] == "job_failed"]
    assert failed and "remotion" in failed[-1]["message"] and "ffmpeg" in failed[-1]["message"]


async def test_edit_stage_passes_when_divergence_is_justified_by_decision_log(runner, monkeypatch, tmp_path):
    def write_justified_edit_decisions(job_id, stage_name, skill_text, project_dir, *a, **k):
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        if stage_name == "proposal":
            (project_dir / "artifacts" / "proposal_packet.json").write_text(json.dumps(
                {"production_plan": {"render_runtime": "remotion"}}
            ))
        if stage_name == "edit":
            (project_dir / "artifacts" / "edit_decisions.json").write_text(json.dumps(
                {"render_runtime": "ffmpeg"}
            ))
            (project_dir / "artifacts" / "decision_log.json").write_text(json.dumps({
                "decisions": [{
                    "decision_id": "d-002", "stage": "edit", "category": "render_runtime_selection",
                    "subject": "runtime override", "options_considered": [
                        {"option_id": "o1", "label": "ffmpeg", "score": 1, "reason": "remotion unavailable"},
                    ],
                    "selected": "o1", "reason": "remotion render failed at edit time",
                }],
            }))
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", write_justified_edit_decisions)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic", [
        {"name": "proposal", "skill": None, "approval": False, "produces": ["proposal_packet"]},
        {"name": "edit", "skill": None, "approval": False, "produces": ["edit_decisions"]},
    ])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "completed"


# ── cancellation: cancel_requested must win over every gate's own reject
# semantics (abort/try-again/regenerate all mean something different — a
# cancel must short-circuit all of them, not get reinterpreted as one) ──────

async def test_cancel_requested_before_any_stage_never_runs_one(runner, monkeypatch):
    # The "queued" case: cancelled before the job was even dequeued. The
    # per-stage loop's cancel check must fire on the very first iteration,
    # before any stage — including a non-approval-gated one — actually runs.
    ran = []
    monkeypatch.setattr(stage_runner, "_run_agent_stage", lambda *a, **k: ran.append(1) or True)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})
    runner.update("j", cancel_requested=True)

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})

    assert runner.get("j")["status"] == "cancelled"
    assert ran == []
    assert any(e["type"] == "job_cancelled" for e in runner.get_events("j", after_seq=-1))


async def test_cancel_overrides_budget_gate_reject_semantics(runner, monkeypatch):
    # Budget-gate reject already means "abort" — but it must abort as
    # "cancelled", not "failed", when the rejection was actually a cancel
    # (the cancel endpoint sets cancel_requested=True and calls
    # set_approval(..., "reject", ...) verbatim, since a plain reject is the
    # only way to unblock wait_for_approval from outside the runner).
    def spend(*a, **k):
        acc = k["cost_accumulator"]
        if acc is not None:
            acc.append(5.0)
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", spend)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic", "options": {"budget_cny": 1}})

    async def canceller():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.update("j", cancel_requested=True)
                runner.set_approval("j", "reject", "Cancelled by user")
                return
    canceller_task = asyncio.create_task(canceller())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic",
                                              "options": {"budget_cny": 1}})
    await canceller_task

    assert runner.get("j")["status"] == "cancelled"
    assert any(e["type"] == "job_cancelled" for e in runner.get_events("j", after_seq=-1))


async def test_cancel_overrides_sample_preview_gate_reject_semantics(runner, monkeypatch, tmp_path):
    # The sample-preview gate's OWN reject semantics mean "try a different
    # approach and keep going" (see _sample_preview_gate) — the exact
    # opposite of stopping. Without checking cancel_requested first, routing
    # a cancel through set_approval(..., "reject", ...) here would just make
    # the agent try again instead of actually cancelling the job.
    (tmp_path / "projects" / "p" / "renders").mkdir(parents=True)
    (tmp_path / "projects" / "p" / "renders" / "final.mp4").write_bytes(b"x")

    def flaky_research(*a, **k):
        resume_messages = k["resume_messages"]
        if resume_messages is None:
            raise stage_runner.SamplePreviewNeeded(
                messages=[{"role": "user", "content": "orig"}], preview_text="sample",
                sample_iteration=0,
            )
        return True   # would only be reached if the reject were misinterpreted as "resume"

    def dispatch(*a, **k):
        stage_name = a[1]
        return (flaky_research if stage_name == "research" else (lambda *a, **k: True))(*a, **k)
    monkeypatch.setattr(stage_runner, "_run_agent_stage", dispatch)
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    async def canceller():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.update("j", cancel_requested=True)
                runner.set_approval("j", "reject", "Cancelled by user")
                return
    canceller_task = asyncio.create_task(canceller())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    await canceller_task

    assert runner.get("j")["status"] == "cancelled"
    assert any(e["type"] == "job_cancelled" for e in runner.get_events("j", after_seq=-1))


async def test_cancel_overrides_stage_boundary_gate_reject_semantics(runner, monkeypatch):
    # The ordinary stage-boundary approval gate's OWN reject semantics mean
    # "regenerate with feedback, keep looping until approved" — also the
    # opposite of stopping. A cancel routed through the same reject action
    # must not fall into that regenerate loop.
    regenerate_calls = []
    def stub(*a, **k):
        regenerate_calls.append(1)
        project_dir = a[3]
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts" / "script.json").write_text("{}")
        return True
    monkeypatch.setattr(stage_runner, "_run_agent_stage", stub)
    monkeypatch.setitem(stage_runner.PIPELINE_MAP, "cinematic",
                        [{"name": "script", "skill": None, "approval": True, "produces": ["script"]}])
    runner.create("j", {"project_name": "p", "pipeline": "cinematic"})

    async def canceller():
        for _ in range(200):
            await asyncio.sleep(0.01)
            if runner.get("j")["status"] == "awaiting_approval":
                runner.update("j", cancel_requested=True)
                runner.set_approval("j", "reject", "Cancelled by user")
                return
    canceller_task = asyncio.create_task(canceller())

    await stage_runner.run_pipeline_job("j", {"project_name": "p", "pipeline": "cinematic"})
    await canceller_task

    assert runner.get("j")["status"] == "cancelled"
    assert regenerate_calls == [1]   # only the initial run — no regenerate round was triggered
    assert any(e["type"] == "job_cancelled" for e in runner.get_events("j", after_seq=-1))
