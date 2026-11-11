"""A style_playbook chosen at a checkpoint must reach the project marker.

The Backlot board reads `style_playbook` from `project.json`. On the
2026-11-11 end-to-end audit run the proposal and scene_plan checkpoints carried
`style_playbook`, but `project.json` never did (init_project ran before the
playbook was chosen), so the board showed none.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.checkpoint import init_project, write_checkpoint
from styles.playbook_loader import list_playbooks

PLAYBOOKS = sorted(list_playbooks())


def _marker(base: Path, project_id: str) -> dict:
    return json.loads((base / project_id / "project.json").read_text(encoding="utf-8"))


def _write_research(base: Path, project_id: str, style_playbook: str | None) -> None:
    write_checkpoint(
        base,
        project_id,
        "research",
        "in_progress",
        {},
        pipeline_type="animated-explainer",
        style_playbook=style_playbook,
    )


def test_checkpoint_playbook_is_recorded_on_the_marker(tmp_path: Path) -> None:
    init_project("p", title="P", pipeline_type="animated-explainer", pipeline_dir=tmp_path)
    assert "style_playbook" not in _marker(tmp_path, "p")

    _write_research(tmp_path, "p", PLAYBOOKS[0])

    assert _marker(tmp_path, "p")["style_playbook"] == PLAYBOOKS[0]


def test_a_changed_playbook_replaces_the_marker_value(tmp_path: Path) -> None:
    init_project(
        "p", title="P", pipeline_type="animated-explainer",
        style_playbook=PLAYBOOKS[0], pipeline_dir=tmp_path,
    )
    _write_research(tmp_path, "p", PLAYBOOKS[1])

    marker = _marker(tmp_path, "p")
    assert marker["style_playbook"] == PLAYBOOKS[1]
    assert marker["title"] == "P"
    assert marker["pipeline_type"] == "animated-explainer"


def test_no_playbook_leaves_the_marker_alone(tmp_path: Path) -> None:
    init_project("p", title="P", pipeline_type="animated-explainer", pipeline_dir=tmp_path)
    before = (tmp_path / "p" / "project.json").read_text(encoding="utf-8")

    _write_research(tmp_path, "p", None)

    assert (tmp_path / "p" / "project.json").read_text(encoding="utf-8") == before
