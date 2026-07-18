"""Stage runner: render discovery, artifact loading, and the finish=stop fix."""

from __future__ import annotations

from types import SimpleNamespace

from app.runner import stage_runner
from app.runner.stage_runner import (
    _discover_render_url, _load_artifacts, _load_brand_kit,
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
