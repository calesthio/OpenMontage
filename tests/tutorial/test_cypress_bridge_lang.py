from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.capture import cypress_bridge as bridge  # noqa: E402


def test_run_tutorial_spec_passes_lang(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, cwd=None, env=None, timeout=None):
        seen["cmd"], seen["env"] = cmd, env

    monkeypatch.setattr(bridge, "_run", fake_run)
    monkeypatch.setattr(bridge, "_find_manifest", lambda client, spec: ({"steps": []}, tmp_path / "m.json"))
    monkeypatch.setattr(bridge, "_resolve_browser", lambda: "")
    monkeypatch.delenv("CYPRESS_TUTORIAL_LANG", raising=False)
    bridge.run_tutorial_spec(str(tmp_path), "cypress/e2e-tutorials/x.tutorial.cy.js", lang="de")
    assert seen["env"]["CYPRESS_TUTORIAL_LANG"] == "de"
    env_arg = seen["cmd"][seen["cmd"].index("--env") + 1]
    assert "tutorialLang=de" in env_arg.split(",")

    bridge.run_tutorial_spec(str(tmp_path), "cypress/e2e-tutorials/x.tutorial.cy.js")
    assert "CYPRESS_TUTORIAL_LANG" not in seen["env"]
