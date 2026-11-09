"""Contract tests for the Hermes Creative Flywheel evolution tools.

These are contract-style tests (no network, no API keys): they verify the
tools conform to the BaseTool contract, score/breed/persist correctly, and
that the manifest validates against the schema.

Run:
  pytest tests/contracts/test_flywheel_evolution.py -q
  (or: python -m pytest tests/contracts/test_flywheel_evolution.py)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Make repo root importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.evolution.breed_scorer import BreedScorer  # noqa: E402
from tools.evolution.breed_mutator import BreedMutator  # noqa: E402
from tools.evolution.population_store import PopulationStore  # noqa: E402
from tools.base_tool import ToolResult  # noqa: E402
from tools.tool_registry import ToolRegistry  # noqa: E402
from lib.pipeline_loader import load_pipeline, list_pipelines  # noqa: E402

_PROJECT = "_flywheel_test_project"


def _sample_artifact(score_visual: bool = True) -> dict:
    return {
        "topic": "vector search",
        "duration_seconds": 60.0,
        "target_duration_seconds": 60.0,
        "word_count": 140,
        "target_word_count": 140,
        "cost_usd": 1.33,
        "budget_usd": 5.0,
        "sections": [
            {"label": "Hook", "enhancement_cues": [{"type": "diagram"}], "text": "What if search didn't scan every row?"},
            {"label": "Build", "enhancement_cues": [{"type": "animation"}, {"type": "stat_card"}], "text": "Embeddings cluster by meaning."},
            {"label": "Climax", "enhancement_cues": [{"type": "overlay"}], "text": "Now it's a math problem."},
        ],
        "retention_anchors": 3,
        "novelty_flag": False,
        "notes": "sample",
    }


# --- BaseTool contract ----------------------------------------------------

def test_tools_registered_in_registry():
    reg = ToolRegistry()
    reg.discover("tools")
    for name in ("breed_scorer", "breed_mutator", "population_store"):
        assert reg.get(name) is not None, f"{name} not discovered"


def test_tools_available_status():
    for cls in (BreedScorer, BreedMutator, PopulationStore):
        assert cls().get_status().value == "available"


def test_execute_returns_toolresult():
    res = BreedScorer().execute({"action": "rubric", "artifact": _sample_artifact()})
    assert isinstance(res, ToolResult)
    assert res.success is True


# --- Scorer ---------------------------------------------------------------

def test_scorer_rubric_returns_explainable():
    res = BreedScorer().execute({"action": "rubric", "artifact": _sample_artifact()})
    assert res.success
    assert 0.0 <= res.data["score"] <= 1.0
    assert "components" in res.data and "explanation" in res.data
    assert set(res.data["components"].keys())


def test_scorer_hard_gate_low_visual_density():
    art = _sample_artifact()
    # strip enhancement cues -> visual_density floor fails
    for s in art["sections"]:
        s["enhancement_cues"] = []
    res = BreedScorer().execute({"action": "rubric", "artifact": art})
    assert res.data["passed_hard_gate"] is False


def test_scorer_compare_delta():
    good = _sample_artifact()
    good["llm_score"] = 0.9
    bad = _sample_artifact()
    bad["llm_score"] = 0.3
    res = BreedScorer().execute({"action": "compare", "artifact": good, "baseline": bad})
    assert res.success
    assert res.data["improved"] is True
    assert res.data["delta"] > 0


# --- Breeder --------------------------------------------------------------

def test_breed_select_and_breed():
    mut = BreedMutator()
    individuals = [
        {"id": "a", "score": 0.8, "topic": "t", "generation": 0},
        {"id": "b", "score": 0.5, "topic": "t", "generation": 0},
        {"id": "c", "score": 0.2, "topic": "t", "generation": 0},
    ]
    sel = mut.execute({"action": "select_parents", "individuals": individuals, "seed": 1})
    assert sel.success
    assert sel.data["parents"][0]["id"] == "a"  # best is elite
    breed = mut.execute(
        {"action": "breed", "parents": sel.data["parents"], "generation": 0,
         "population_size": 4, "seed": 1}
    )
    assert breed.success
    seeds = breed.data["seeds"]
    assert len(seeds) == 4
    assert all("generation" in s and s["generation"] == 1 for s in seeds)
    # determinism: same seed -> same variant count and ids lineage
    assert all("parent_ids" in s for s in seeds)


def test_breed_deterministic_with_seed():
    mut = BreedMutator()
    parents = [{"id": "a", "score": 0.8, "topic": "t"}, {"id": "b", "score": 0.5, "topic": "t"}]
    r1 = mut.execute({"action": "breed", "parents": parents, "generation": 0, "population_size": 4, "seed": 42})
    r2 = mut.execute({"action": "breed", "parents": parents, "generation": 0, "population_size": 4, "seed": 42})
    assert json.dumps(r1.data["seeds"], sort_keys=True) == json.dumps(r2.data["seeds"], sort_keys=True)


# --- Population store -----------------------------------------------------

def test_population_record_and_load(tmp_path):
    store = PopulationStore()
    proj = str(tmp_path / _PROJECT)
    rec = store.execute({
        "action": "record",
        "project_dir": proj,
        "individual": {"generation": 0, "topic": "t", "score": 0.7, "pipeline": "x"},
    })
    assert rec.success
    assert rec.data["state"]["count"] == 1
    assert rec.data["state"]["best_score"] == 0.7
    loaded = store.execute({"action": "load_population", "project_dir": proj})
    assert loaded.success
    assert loaded.data["individuals"][0]["score"] == 0.7
    state = store.execute({"action": "state", "project_dir": proj})
    assert state.data["state"]["generation"] == 0


# --- Manifest validation -------------------------------------------------

def test_flywheel_manifest_validates():
    manifest = load_pipeline("hermes-flywheel")
    assert manifest["name"] == "hermes-flywheel"
    stage_names = [s["name"] for s in manifest["stages"]]
    assert stage_names == ["script", "render", "score", "breed"]
    # required_skills reference the flywheel director skills
    assert any("hermes-flywheel" in s for s in manifest["required_skills"])


def test_flywheel_in_pipeline_list():
    assert "hermes-flywheel" in list_pipelines()
