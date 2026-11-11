from pathlib import Path

import pytest

from lib.pipeline_loader import load_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_music_plans_discover_all_music_capabilities() -> None:
    instruction_files = [
        "AGENT_GUIDE.md",
        "skills/pipelines/cinematic/proposal-director.md",
        "skills/pipelines/documentary-montage/idea-director.md",
        "skills/pipelines/explainer/proposal-director.md",
    ]

    for relative_path in instruction_files:
        text = _read(relative_path)
        for capability in ("music_library", "music_search", "music_generation"):
            assert f'get_by_capability("{capability}")' in text, (
                f"{relative_path} omits the {capability!r} music source"
            )


def test_explainer_directors_do_not_reference_fictitious_submit_functions() -> None:
    for stage in ("proposal", "script", "scene"):
        text = _read(f"skills/pipelines/explainer/{stage}-director.md")
        assert "handle_explainer_" not in text


# Manifests that start at research -> proposal. Their old idea-director.md is
# a stub that must only point onward, so no agent can follow a retired process.
SUPERSEDED_IDEA_DIRECTORS = {
    "animated-explainer": "explainer",
    "animation": "animation",
    "cinematic": "cinematic",
}


@pytest.mark.parametrize(("pipeline", "skill_dir"), sorted(SUPERSEDED_IDEA_DIRECTORS.items()))
def test_superseded_idea_directors_are_pointer_stubs(pipeline: str, skill_dir: str) -> None:
    manifest = load_pipeline(pipeline)
    stage_names = [stage["name"] for stage in manifest["stages"]]
    assert "idea" not in stage_names, f"{pipeline} has an idea stage again; revive its director"
    assert stage_names[:2] == ["research", "proposal"], stage_names

    idea_skill = f"pipelines/{skill_dir}/idea-director"
    for stage in manifest["stages"]:
        assert stage.get("skill") != idea_skill, f"{pipeline}:{stage['name']} runs the stub"

    relative_path = f"skills/{idea_skill}.md"
    text = _read(relative_path)
    assert "superseded" in text.lower(), f"{relative_path} does not say it is superseded"
    assert "Do not use this file" in text
    assert f"skills/pipelines/{skill_dir}/proposal-director.md" in text
    assert (REPO_ROOT / f"skills/pipelines/{skill_dir}/proposal-director.md").is_file()
    for retired in ("## Process", "## When to Use", "## When To Use", "Gate Reminder"):
        assert retired not in text, f"{relative_path} still carries a process section {retired!r}"
    assert len(text) < 1200, f"{relative_path} has grown back into a director skill"
