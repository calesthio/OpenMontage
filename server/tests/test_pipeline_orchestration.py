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
        acc = a[7]              # cost_accumulator positional arg
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
        resume_messages = a[12]
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
        resume_messages = a[12]
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
        feedback = a[6]
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
        seen_budget.append(a[9])   # budget_cny positional arg, as of THIS stage's start
        acc = a[7]                 # cost_accumulator positional arg
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
