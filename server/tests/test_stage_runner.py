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


def test_discover_falls_back_to_assets_mp4(tmp_path):
    proj = tmp_path / "p"
    (proj / "renders").mkdir(parents=True)
    (proj / "assets" / "video").mkdir(parents=True)
    (proj / "assets" / "video" / "clip.mp4").write_bytes(b"x")
    assert _discover_render_url(proj, "p") == "/media/p/assets/video/clip.mp4"


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
