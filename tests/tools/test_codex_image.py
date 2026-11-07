"""codex_image drives an external CLI, so every test here mocks the subprocess.

The session network guard only blocks sockets inside the test process — a real
`codex exec` would escape it, spend the developer's ChatGPT quota, and take a
minute per run. Nothing below is allowed to actually launch codex.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.base_tool import ToolStatus
from tools.graphics.codex_image import CodexImage


@pytest.fixture
def codex_home(tmp_path, monkeypatch):
    """A fake $CODEX_HOME signed in with a ChatGPT subscription."""
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "auth.json").write_text(
        json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "not-a-real-token"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setattr("tools.graphics.codex_image.shutil.which", lambda _: "/usr/bin/codex")
    return home


class TestStatus:

    def test_available_when_signed_in_with_chatgpt(self, codex_home):
        assert CodexImage().get_status() is ToolStatus.AVAILABLE

    def test_degraded_when_signed_in_with_api_key(self, codex_home):
        (codex_home / "auth.json").write_text(
            json.dumps({"auth_mode": "apikey"}), encoding="utf-8"
        )
        # Still usable, but it bills API credit — callers must be able to tell
        # that apart from the subscription path this tool advertises.
        assert CodexImage().get_status() is ToolStatus.DEGRADED

    def test_unavailable_without_the_binary(self, codex_home, monkeypatch):
        monkeypatch.setattr("tools.graphics.codex_image.shutil.which", lambda _: None)
        assert CodexImage().get_status() is ToolStatus.UNAVAILABLE

    def test_unavailable_when_auth_file_is_missing(self, codex_home):
        (codex_home / "auth.json").unlink()
        assert CodexImage().get_status() is ToolStatus.UNAVAILABLE

    def test_unavailable_when_auth_file_is_corrupt(self, codex_home):
        (codex_home / "auth.json").write_text("{not json", encoding="utf-8")
        assert CodexImage().get_status() is ToolStatus.UNAVAILABLE


class TestOutputPaths:

    def test_single_image_keeps_the_requested_name(self):
        assert CodexImage._output_paths("out/hero.png", 1, "png") == [Path("out/hero.png")]

    def test_multiple_images_do_not_overwrite_each_other(self):
        paths = CodexImage._output_paths("out/hero.png", 3, "png")
        assert paths == [
            Path("out/hero_1.png"),
            Path("out/hero_2.png"),
            Path("out/hero_3.png"),
        ]
        assert len(set(paths)) == 3


class TestCollectImages:

    def test_reads_the_structured_response_first(self, tmp_path):
        img = tmp_path / "made.png"
        img.write_bytes(b"png")
        last = tmp_path / "last.json"
        last.write_text(json.dumps({"images": [str(img)]}), encoding="utf-8")

        assert CodexImage._collect_images(last, started_at=0.0) == [img]

    def test_falls_back_to_the_codex_session_dir(self, codex_home, tmp_path):
        """The agent may answer off-contract; Codex still wrote the files."""
        session = codex_home / "generated_images" / "01a0-session"
        session.mkdir(parents=True)
        for name in ("exec-b.png", "exec-a.png"):
            (session / name).write_bytes(b"png")

        found = CodexImage._collect_images(tmp_path / "missing.json", started_at=0.0)
        assert [p.name for p in found] == ["exec-a.png", "exec-b.png"]

    def test_ignores_session_dirs_from_earlier_runs(self, codex_home, tmp_path):
        stale = codex_home / "generated_images" / "old-session"
        stale.mkdir(parents=True)
        (stale / "exec-old.png").write_bytes(b"png")

        # started_at far in the future — nothing from this run exists yet.
        assert CodexImage._collect_images(tmp_path / "missing.json", started_at=2**40) == []

    def test_ignores_paths_the_agent_claimed_but_did_not_write(self, tmp_path):
        last = tmp_path / "last.json"
        last.write_text(json.dumps({"images": ["/nope/ghost.png"]}), encoding="utf-8")

        assert CodexImage._collect_images(last, started_at=2**40) == []


class TestExecute:

    def _fake_run(self, images: list[Path]):
        """Stand in for run_command: write last.json the way codex exec would."""
        def run_command(cmd, *, timeout=None, cwd=None, env=None, input=None):
            assert "codex" in cmd[0]
            # The prompt must arrive on stdin — codex exec blocks on an unclosed
            # stdin, and argv quoting breaks on multi-line prompts.
            assert input and "image generation tool" in input
            # An inherited OPENAI_API_KEY would flip Codex onto API billing.
            assert env is not None and "OPENAI_API_KEY" not in env
            last = Path(cmd[cmd.index("-o") + 1])
            last.write_text(json.dumps({"images": [str(p) for p in images]}), encoding="utf-8")

            class Proc:
                stdout = ""
                stderr = ""
            return Proc()
        return run_command

    def test_writes_the_image_and_reports_subscription_billing(
        self, codex_home, tmp_path, monkeypatch
    ):
        session = codex_home / "generated_images" / "01a0-session"
        session.mkdir(parents=True)
        src = session / "exec-1.png"
        src.write_bytes(b"fake-png-bytes")

        monkeypatch.setenv("OPENAI_API_KEY", "would-flip-billing-to-the-api")
        tool = CodexImage()
        monkeypatch.setattr(tool, "run_command", self._fake_run([src]))

        dest = tmp_path / "out" / "hero.png"
        result = tool.execute({"prompt": "a red lantern", "output_path": str(dest)})

        assert result.success is True
        assert dest.read_bytes() == b"fake-png-bytes"
        assert result.artifacts == [str(dest)]
        assert result.data["billing"] == "chatgpt_subscription"
        assert result.data["session_id"] == "01a0-session"
        # No money moves, so the cost tracker must not be told otherwise.
        assert result.cost_usd == 0.0

    def test_reference_images_are_attached_with_dash_i(self, codex_home, tmp_path, monkeypatch):
        session = codex_home / "generated_images" / "01a0-session"
        session.mkdir(parents=True)
        src = session / "exec-1.png"
        src.write_bytes(b"png")
        ref = tmp_path / "ref.webp"
        ref.write_bytes(b"ref")
        seen = {}
        inner = self._fake_run([src])

        def run_command(cmd, **kw):
            seen["cmd"], seen["input"] = cmd, kw["input"]
            return inner(cmd, **kw)

        tool = CodexImage()
        monkeypatch.setattr(tool, "run_command", run_command)
        result = tool.execute({
            "prompt": "same lion, younger",
            "reference_images": [str(ref)],
            "output_path": str(tmp_path / "out.png"),
        })

        assert result.success is True
        assert seen["cmd"][seen["cmd"].index("-i") + 1] == str(ref.resolve())
        assert "STYLE AND CHARACTER REFERENCES" in seen["input"]

    def test_missing_reference_image_fails_before_spending_quota(self, codex_home, tmp_path, monkeypatch):
        tool = CodexImage()
        monkeypatch.setattr(tool, "run_command", lambda *a, **k: pytest.fail("must not run codex"))
        result = tool.execute({"prompt": "x", "reference_images": [str(tmp_path / "nope.png")]})
        assert result.success is False
        assert "reference_images not found" in result.error

    def test_refuses_to_run_when_codex_is_missing(self, codex_home, monkeypatch):
        monkeypatch.setattr("tools.graphics.codex_image.shutil.which", lambda _: None)
        result = CodexImage().execute({"prompt": "a red lantern"})

        assert result.success is False
        assert "codex login" in result.error

    def test_reports_a_turn_that_produced_nothing(self, codex_home, tmp_path, monkeypatch):
        tool = CodexImage()
        monkeypatch.setattr(tool, "run_command", self._fake_run([]))

        result = tool.execute({"prompt": "a red lantern", "output_path": str(tmp_path / "x.png")})

        assert result.success is False
        assert "image_generation" in result.error

    def test_second_concurrent_run_is_refused_not_serialized_badly(
        self, codex_home, tmp_path, monkeypatch
    ):
        """Codex keeps global state on disk; two turns at once corrupt it."""
        tool = CodexImage()
        lock = tool._lock_path()
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.touch()

        try:
            result = tool.execute({"prompt": "a red lantern"})
        finally:
            lock.unlink(missing_ok=True)

        assert result.success is False
        assert "in progress" in result.error

    def test_the_lock_is_released_after_a_failed_run(self, codex_home, tmp_path, monkeypatch):
        tool = CodexImage()

        def blow_up(*args, **kwargs):
            raise RuntimeError("codex exploded")

        monkeypatch.setattr(tool, "run_command", blow_up)
        assert tool.execute({"prompt": "a red lantern"}).success is False
        assert not tool._lock_path().exists()


def test_cost_is_zero_dollars_regardless_of_count(codex_home):
    assert CodexImage().estimate_cost({"prompt": "x", "n": 4}) == 0.0
