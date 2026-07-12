"""Stage runner: render discovery, artifact loading, and the finish=stop fix."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.runner import stage_runner
from app.runner.stage_runner import (
    _discover_render_url, _discover_render_urls, _load_artifacts, _load_brand_kit,
    _brand_reference_image_data_uri, _MAX_REFERENCE_DATA_URI_CHARS,
)


# ── _discover_render_url ──────────────────────────────────────────────────────

def test_discover_prefers_renders(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == "/media/p/renders/final.mp4"


def test_discover_falls_back_to_assets_video_post_mp4(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_post").mkdir(parents=True)
    (proj / "assets" / "video_post" / "clip.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == "/media/p/assets/video_post/clip.mp4"


def test_discover_ignores_raw_generation_clips(tmp_path):
    # Regression: the fallback used to glob assets/**/*.mp4 — broad enough to
    # match assets/video_generation/*.mp4, the RAW per-scene clips from
    # maas_video. Confirmed live: a compose stage that never actually
    # composed anything (all generation blocked, render_report honestly
    # documented the failure) still left a raw scene clip sitting in
    # assets/video_generation/ from an earlier stage — the broad glob picked
    # it and presented a random few-second clip as if it were the finished
    # film. Only assets/video_post/ (the compose-family tools' own capability
    # folder) is a legitimate fallback location.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_generation").mkdir(parents=True)
    (proj / "assets" / "video_generation" / "maas_video_abc123.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") is None


def test_discover_misnamed_compose_bin(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video_post").mkdir(parents=True)
    (proj / "assets" / "video_post" / "video_compose_output.bin").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == \
        "/media/p/assets/video_post/video_compose_output.bin"


def test_discover_none_when_empty(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    assert _discover_render_url(proj, "p") is None


# ── _discover_render_urls (A/B variant-aware) ────────────────────────────────

def test_discover_render_urls_none_for_single_render(tmp_path):
    # A normal (non-variant) job — only the plain final.mp4 exists. Callers
    # must fall back to the singular render_url in this case, so this needs
    # to return None, not a one-entry dict.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final.mp4").write_bytes(b"x")
    assert _discover_render_urls(proj, "p") is None


def test_discover_render_urls_none_when_empty(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    assert _discover_render_urls(proj, "p") is None


def test_discover_render_urls_maps_each_variant(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final_ltx-2-3.mp4").write_bytes(b"x")
    (proj / "renders" / "final_wan2-2.mp4").write_bytes(b"y")
    urls = _discover_render_urls(proj, "p")
    assert urls == {
        "ltx-2-3": "/media/p/renders/final_ltx-2-3.mp4",
        "wan2-2": "/media/p/renders/final_wan2-2.mp4",
    }


def test_discover_render_urls_bare_final_gets_default_slug_alongside_variant(tmp_path):
    # Edge case: a bare final.mp4 sitting next to a variant-tagged one (e.g.
    # a job that only tagged the SECOND compose call). Both must surface.
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "renders" / "final.mp4").write_bytes(b"x")
    (proj / "renders" / "final_wan2-2.mp4").write_bytes(b"y")
    urls = _discover_render_urls(proj, "p")
    assert urls == {
        "default": "/media/p/renders/final.mp4",
        "wan2-2": "/media/p/renders/final_wan2-2.mp4",
    }


# ── _brand_reference_image_data_uri ──────────────────────────────────────────

def test_brand_reference_image_data_uri_absent_without_path(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    assert _brand_reference_image_data_uri("some-kit", {}) is None
    assert _brand_reference_image_data_uri(None, {"reference_image_path": "reference.png"}) is None


def test_brand_reference_image_data_uri_reads_and_encodes(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    kit_dir = tmp_path / "brand_kits" / "acme-123"
    kit_dir.mkdir(parents=True)
    (kit_dir / "reference.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-but-nonempty")
    uri = _brand_reference_image_data_uri("acme-123", {"reference_image_path": "reference.png"})
    assert uri is not None
    assert uri.startswith("data:image/png;base64,")


def test_brand_reference_image_data_uri_skips_oversized_file_instead_of_truncating(tmp_path, monkeypatch):
    # A truncated data URI isn't a smaller image, it's corrupt — must be
    # skipped entirely (None) rather than handed to the agent half-cut.
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    kit_dir = tmp_path / "brand_kits" / "acme-123"
    kit_dir.mkdir(parents=True)
    # base64 expands ~4/3x — this comfortably exceeds the char cap.
    (kit_dir / "reference.png").write_bytes(b"x" * (_MAX_REFERENCE_DATA_URI_CHARS))
    uri = _brand_reference_image_data_uri("acme-123", {"reference_image_path": "reference.png"})
    assert uri is None


def test_brand_reference_image_data_uri_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)
    assert _brand_reference_image_data_uri("acme-123", {"reference_image_path": "reference.png"}) is None


# ── artifact / brand-kit loading ─────────────────────────────────────────────

def test_load_artifacts_skips_invalid(tmp_path):
    a = tmp_path / "artifacts"
    a.mkdir()
    (a / "research.json").write_text('{"k": 1}')
    (a / "bad.json").write_text("{ not valid json")
    arts = _load_artifacts(tmp_path)
    assert arts["research"] == {"k": 1}
    assert "bad" not in arts


def test_load_brand_kit_absent():
    assert _load_brand_kit(None) == {}
    assert _load_brand_kit("definitely-not-a-real-kit-xyz") == {}


# ── O-1 regression: finish_reason=="stop" must NOT drop tool_calls ───────────

def _msg(content, tool_calls):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _resp(content, tool_calls, finish):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=_msg(content, tool_calls), finish_reason=finish)]
    )


def _tool_call(cid, name, arguments):
    return SimpleNamespace(id=cid, function=SimpleNamespace(name=name, arguments=arguments))


def test_finish_stop_with_tool_calls_still_executes(tmp_path, monkeypatch):
    # Turn 1: gateway returns finish_reason="stop" WHILE carrying a tool_call
    # (the exact shape the aiapbot shim can produce). Turn 2: no tool_calls → end.
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact",
                    '{"artifact_name": "research", "content": {"summary": "ok"}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create",
        lambda **kw: next(responses),
    )

    ok = stage_runner._run_agent_stage(
        "job-x", "research", "skill", tmp_path, {}, {},
    )
    assert ok is True
    # The artifact was written → the tool_call was executed, not dropped.
    written = tmp_path / "artifacts" / "research.json"
    assert written.exists()
    assert '"summary": "ok"' in written.read_text()


def test_no_tool_calls_ends_stage(tmp_path, monkeypatch):
    resp = _resp("nothing to do", None, "stop")
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create",
        lambda **kw: resp,
    )
    ok = stage_runner._run_agent_stage("job-y", "research", "skill", tmp_path, {}, {})
    assert ok is True
    assert not (tmp_path / "artifacts").exists()  # no tool ran


# ── mid-stage stall nudging (agent stops to ask, artifact not written) ──────

def test_sample_preview_pauses_instead_of_auto_continuing(tmp_path, monkeypatch):
    # Regression: confirmed live — asset-director.md's own "Sample Preview"
    # step tells the agent to generate one sample of each asset type and
    # confirm with the user before batch-generating the rest. This used to
    # be silently overridden with a "no human is available, proceed
    # autonomously" nudge, which defeated the skill's own wasted-spend
    # safeguard. It must now pause for a REAL approval instead.
    turn1 = _resp(
        "Here are samples of each asset — please confirm before I continue.",
        None, "stop",
    )
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", lambda **kw: turn1)

    with pytest.raises(stage_runner.SamplePreviewNeeded) as exc_info:
        stage_runner._run_agent_stage(
            "job-nudge1", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
        )
    spn = exc_info.value
    assert spn.sample_iteration == 0
    assert "please confirm" in spn.preview_text.lower()
    # The paused conversation carries the agent's own message so a resume
    # doesn't have to re-explain itself.
    assert spn.messages[-1]["role"] == "assistant"
    assert not (tmp_path / "artifacts" / "asset_manifest.json").exists()


def test_sample_preview_resume_continues_the_same_conversation(tmp_path, monkeypatch):
    # After approval, _run_agent_stage must pick up with the resumed
    # conversation (not rebuild the initial prompt from scratch) and be able
    # to complete normally from there.
    resume = [
        {"role": "user", "content": "## Director Skill\noriginal prompt"},
        {"role": "assistant", "content": "Here's a sample — please confirm."},
        {"role": "user", "content": "Approved — proceed to complete the stage."},
    ]
    turn = _resp(
        "writing",
        [_tool_call("c1", "write_artifact",
                    '{"artifact_name": "asset_manifest", "content": {"ok": true}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn, turn2])
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    ok = stage_runner._run_agent_stage(
        "job-resume1", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
        resume_messages=resume, sample_iteration=1,
    )
    assert ok is True
    assert (tmp_path / "artifacts" / "asset_manifest.json").exists()
    # The original prompt was NOT rebuilt — the resumed history is exactly
    # what was passed in, with the new turn's messages appended after it.
    assert captured["messages"][:3] == resume


def test_no_nudge_when_artifact_already_written(tmp_path, monkeypatch):
    # A text-only turn AFTER the artifact already exists is genuine
    # completion (the prompt itself asks for a brief confirmation once
    # done) — must return immediately, not waste a nudge.
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "asset_manifest.json").write_text('{"ok": true}')
    resp = _resp("All done, produced the asset manifest above.", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    ok = stage_runner._run_agent_stage(
        "job-nudge2", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
    )
    assert ok is True
    # Only the original prompt — no nudge appended.
    user_msgs = [m for m in captured["messages"] if m.get("role") == "user"]
    assert len(user_msgs) == 1


def test_sample_preview_iteration_budget_exhausted_ends_stage(tmp_path, monkeypatch):
    # A genuinely stuck agent (still hasn't written the artifact after
    # exhausting its pause/resume budget) must stop rather than pause again —
    # the caller's own _missing_produces check catches the still-missing
    # artifact and fails the stage from there.
    stall = _resp("Still need confirmation before I continue.", None, "stop")
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", lambda **kw: stall)

    ok = stage_runner._run_agent_stage(
        "job-nudge3", "assets", "skill", tmp_path, {}, {}, produces=["asset_manifest"],
        sample_iteration=stage_runner.MAX_SAMPLE_ITERATIONS,
    )
    assert ok is True
    assert not (tmp_path / "artifacts").exists()


# ── truncated tool-call arguments: finish_reason-aware diagnosis ────────────

def test_truncated_args_length_limit_gives_shorten_hint(tmp_path, monkeypatch):
    # finish_reason="length" means the shared narration+JSON budget really was
    # exhausted — the agent should be told to write less next time.
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact", '{"artifact_name": "scene_pla')],  # cut off mid-string
        "length",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-len", "scene_plan", "skill", tmp_path, {}, {})

    tool_msgs = [m["content"] for m in captured["messages"] if m.get("role") == "tool"]
    assert tool_msgs
    assert "finish_reason=length" in tool_msgs[0]
    assert "more concise" in tool_msgs[0]


def test_truncated_args_non_length_gives_malformed_hint(tmp_path, monkeypatch):
    # A non-"length" finish_reason with unparsable JSON is a different failure
    # (a genuinely malformed call) — telling the agent to "write less" would
    # be misleading advice when the visible content wasn't actually large.
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact", '{"artifact_name": "scene_pla')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-malformed", "scene_plan", "skill", tmp_path, {}, {})

    tool_msgs = [m["content"] for m in captured["messages"] if m.get("role") == "tool"]
    assert tool_msgs
    assert "finish_reason=stop" in tool_msgs[0]
    assert "wasn't a length limit" in tool_msgs[0]
    assert "more concise" not in tool_msgs[0]


def test_llm_call_uses_generous_max_tokens(tmp_path, monkeypatch):
    # Regression: 8192 shared between narration and a large write_artifact
    # payload (e.g. a multi-clip scene_plan) could exhaust the budget before
    # the JSON finished, truncating arguments to just a few characters.
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured.update(kw)
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-budget", "scene_plan", "skill", tmp_path, {}, {})
    assert captured["max_tokens"] >= 16384


def test_tool_keyerror_reports_missing_parameter_not_bare_repr(tmp_path, monkeypatch):
    # Regression: a tool indexing inputs["some_field"] with no fallback raises
    # a bare KeyError, which str()s to just "'some_field'" — cryptic enough
    # that the agent can't tell what to fix and repeats the same broken call
    # until the stage burns through MAX_TURNS (this exact pattern hit
    # video_compose's "operation" key live). The message fed back to the
    # agent must name the parameter explicitly so it can self-correct.
    turn1 = _resp(
        "composing",
        [_tool_call("c1", "run_openmontage_tool",
                    '{"tool_name": "video_compose", "inputs": {}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner, "execute_tool",
        lambda *a, **k: (_ for _ in ()).throw(KeyError("operation")),
    )

    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return next(responses)
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-w", "compose", "skill", tmp_path, {}, {})

    tool_result_msgs = [m["content"] for m in captured["messages"] if m.get("role") == "tool"]
    assert tool_result_msgs, "expected a tool-role message with the error"
    assert "missing required parameter" in tool_result_msgs[0].lower()
    assert "operation" in tool_result_msgs[0]
    # The bare, uninterpretable KeyError repr must NOT be the whole message.
    assert tool_result_msgs[0] != "ERROR: Tool execution failed: 'operation'"


# ── tool_call event summary (progress-log clarity) ───────────────────────────

def test_tool_call_summary_shows_path_not_param_names(tmp_path, monkeypatch):
    # Regression: the summary used to be f"{tool_name}({list(tool_args.keys())})"
    # — literally the parameter NAMES, so every read_file call rendered the
    # identical "read_file(['path'])" in the progress log regardless of which
    # file was actually read.
    turn1 = _resp(
        "reading",
        [_tool_call("c1", "read_file", '{"path": "skills/meta/foo.md"}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create", lambda **kw: next(responses),
    )
    (tmp_path / "skills" / "meta").mkdir(parents=True)
    (tmp_path / "skills" / "meta" / "foo.md").write_text("hi")
    monkeypatch.setattr(stage_runner, "OM_ROOT", tmp_path)

    events = []
    monkeypatch.setattr(stage_runner, "_emit", lambda job_id, ev: events.append(ev))

    stage_runner._run_agent_stage("job-t1", "idea", "skill", tmp_path, {}, {})

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["summary"] == "read_file(skills/meta/foo.md)"


def test_tool_call_summary_shows_artifact_name(tmp_path, monkeypatch):
    turn1 = _resp(
        "writing",
        [_tool_call("c1", "write_artifact",
                    '{"artifact_name": "brief", "content": {"a": 1}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create", lambda **kw: next(responses),
    )

    events = []
    monkeypatch.setattr(stage_runner, "_emit", lambda job_id, ev: events.append(ev))

    stage_runner._run_agent_stage("job-t2", "idea", "skill", tmp_path, {}, {})

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["summary"] == "write_artifact(brief)"


def test_tool_call_summary_shows_target_tool_name(tmp_path, monkeypatch):
    turn1 = _resp(
        "generating",
        [_tool_call("c1", "run_openmontage_tool",
                    '{"tool_name": "maas_video", "inputs": {"prompt": "x"}}')],
        "stop",
    )
    turn2 = _resp("done", None, "stop")
    responses = iter([turn1, turn2])
    monkeypatch.setattr(
        stage_runner.llm.chat.completions, "create", lambda **kw: next(responses),
    )
    monkeypatch.setattr(stage_runner, "execute_tool", lambda *a, **k: '{"success": true}')

    events = []
    monkeypatch.setattr(stage_runner, "_emit", lambda job_id, ev: events.append(ev))

    stage_runner._run_agent_stage("job-t3", "assets", "skill", tmp_path, {}, {})

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["summary"] == "run_openmontage_tool(maas_video)"


def test_prompt_tells_agent_the_produces_name(tmp_path, monkeypatch):
    # Regression: stages whose name differs from what they produce (e.g. stage
    # "idea" produces "brief") used to leave the agent guessing artifact_name
    # from the stage name alone. The prompt must state the real name(s)
    # explicitly when the manifest provides a `produces` list.
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    # A text-only turn with neither artifact written now pauses for a real
    # sample-preview approval (see SamplePreviewNeeded) rather than
    # returning — this test only cares about the prompt content, which is
    # captured before that pause fires.
    with pytest.raises(stage_runner.SamplePreviewNeeded):
        stage_runner._run_agent_stage(
            "job-z", "idea", "skill", tmp_path, {}, {},
            produces=["brief", "decision_log"],
        )
    user_msg = captured["messages"][0]["content"]
    assert "Expected Artifact Name" in user_msg
    assert 'artifact_name="brief"' in user_msg
    assert "decision_log" in user_msg   # secondary artifact mentioned too


def test_prompt_falls_back_to_stage_name_without_produces(tmp_path, monkeypatch):
    resp = _resp("done", None, "stop")
    captured = {}
    def fake_create(**kw):
        captured["messages"] = kw["messages"]
        return resp
    monkeypatch.setattr(stage_runner.llm.chat.completions, "create", fake_create)

    stage_runner._run_agent_stage("job-z2", "custom_stage", "skill", tmp_path, {}, {})
    user_msg = captured["messages"][0]["content"]
    assert 'artifact_name="custom_stage"' in user_msg or '"custom_stage"' in user_msg
