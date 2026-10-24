#!/usr/bin/env python3
"""Red/green tests for the CONFIG-locked image engine (P1).

The image model is locked in `config/image_engine.json`. Every model is one
config entry with:
  * its verified library versions (from the S7/S8 kernel manifests),
  * its prompt rules (tools/prompting is OpenCode-owned -> read only),
  * its measured seconds/image (from the same manifests).

The core promise: **changing the model is a JSON edit only**. The test swaps
the "model" field for every registered model and runs the SAME pipeline
(plan -> build job -> generator -> verify -> label+QC) against a fake
generator, without touching a line of code.

No network, no Kaggle, no paid route. Pillow only for the fake images.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.episode_batch import (  # noqa: E402
    build_job,
    label_and_qc,
    load_specs,
    plan_renders,
    verify_fetched,
)
from tools.illustration.model_registry import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    EngineConfigError,
    FakeGenerator,
    active_adapter,
    adapter_for,
    load_engine,
    owner_decision,
    project_gpu_minutes,
)

CONFIG_PATH = ROOT / "config" / "image_engine.json"
CREATURE_DIR = ROOT / "docs/openmontage/niches/speculative_evolution/creatures"
REQUIRED_LOCK_FIELDS = ("model", "scheduler", "steps", "guidance", "dtype",
                        "seed_policy", "prompt_variant", "status")
REQUIRED_MODELS = ("klein", "sdxl-lightning", "dreamshaper-xl-lightning", "sdxl")


def _specs():
    return load_specs(CREATURE_DIR)


def _write_config(tmp_path, **overrides):
    """Copy the repo config into tmp_path with the given top-level overrides."""
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    doc.update(overrides)
    p = tmp_path / "image_engine.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


# --------------------------------------------------------------- the lock
def test_config_file_exists_and_has_the_required_lock_fields():
    assert CONFIG_PATH.is_file(), "config/image_engine.json is missing"
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for field in REQUIRED_LOCK_FIELDS:
        assert field in doc, f"lock field {field!r} missing from the config"
    assert isinstance(doc["models"], dict) and doc["models"]


def test_active_model_is_the_agent_advisory_pick_while_owner_csvs_are_unfilled():
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert doc["model"] == "klein"
    assert doc["status"] == "OWNER_GATED"
    assert doc["fallback"]["model"] == "sdxl-lightning"
    assert doc["fallback"]["role"] == "FAST_FALLBACK"


def test_loader_reports_the_same_lock_as_the_file():
    engine = load_engine(CONFIG_PATH)
    assert engine.model == "klein"
    assert engine.status == "OWNER_GATED"
    assert engine.dtype == "float16"
    assert engine.steps == 4
    assert engine.guidance == 1.0
    assert engine.prompt_variant == "C"
    assert engine.fallback["model"] == "sdxl-lightning"


# ------------------------------------------------------- per-model entries
@pytest.mark.parametrize("key", REQUIRED_MODELS)
def test_every_required_model_is_a_config_entry(key):
    engine = load_engine(CONFIG_PATH)
    adapter = adapter_for(engine, key)
    assert adapter.key == key
    assert adapter.model_id
    assert adapter.pipeline_class
    assert adapter.prompt_target in {"sdxl", "klein", "zimage"}
    assert adapter.prompt_variant in {"A", "B", "C"}
    assert adapter.steps > 0
    assert adapter.dtype == "float16"
    assert adapter.versions.get("diffusers")
    assert adapter.versions.get("transformers")
    assert adapter.prompt_rules.get("source", "").startswith("tools/prompting")
    assert adapter.measured.get("steady_state_sec_per_image") > 0
    assert adapter.measured.get("source")
    assert (ROOT / adapter.measured["source"]).is_file(), \
        "the measured manifest must exist in the repo"


@pytest.mark.parametrize("key", REQUIRED_MODELS)
def test_measured_seconds_per_image_match_the_kernel_manifests(key):
    """The config may not drift from the measured manifest it cites."""
    engine = load_engine(CONFIG_PATH)
    adapter = adapter_for(engine, key)
    manifest = json.loads(
        (ROOT / adapter.measured["source"]).read_text(encoding="utf-8"))
    assert adapter.measured["steady_state_sec_per_image"] == \
        pytest.approx(manifest["steady_state_sec_per_image"])
    assert adapter.measured["load_seconds"] == pytest.approx(manifest["load_seconds"])
    assert adapter.measured["usable_images_per_minute"] == \
        pytest.approx(manifest["usable_images_per_minute"])
    assert adapter.versions["diffusers"] == manifest["versions"]["diffusers"]
    assert adapter.versions["transformers"] == manifest["versions"]["transformers"]


def test_prompt_rules_come_from_tools_prompting_not_from_a_copy():
    """The prompt text must be the builder's output for the model's target."""
    from tools.prompting.builder import PromptBuilder

    engine = load_engine(CONFIG_PATH)
    adapter = active_adapter(engine)
    spec = _specs()[0].creature
    built = PromptBuilder(seed=4000).build(
        adapter.prompt_target, adapter.prompt_variant, spec)
    assert built["prompt"] == plan_renders(
        _specs()[:1], adapter.key, per_spec=1)[0]["prompt"]


# ------------------------------------------------- the model swap promise
@pytest.mark.parametrize("key", REQUIRED_MODELS)
def test_swapping_the_model_is_a_json_edit_only(tmp_path, key):
    """Same pipeline, same code, only the JSON changed."""
    cfg_path = _write_config(tmp_path, model=key)
    engine = load_engine(cfg_path)
    adapter = active_adapter(engine)
    assert adapter.key == key

    renders = plan_renders(_specs()[:1], key, per_spec=2)
    job = build_job("t_swap", key, renders, width=320, height=180)

    # the job carries THIS model's contract
    assert job["model"] == key
    assert job["model_id"] == adapter.model_id
    assert job["pipeline_class"] == adapter.pipeline_class
    assert job["install_ladder"] == list(adapter.install_ladder)
    assert job["load_config"]["scheduler"]["class"] == \
        adapter.scheduler.get("class")
    for r in job["renders"]:
        assert r["steps"] == adapter.steps
        assert r["guidance_scale"] == adapter.guidance

    # the fake generator plays the part of the Kaggle kernel
    fetched = FakeGenerator().generate(job, adapter, out_dir=tmp_path / "fetched")
    res = verify_fetched(fetched, job)
    assert res["ok"] is True, res.get("error")

    manifest = label_and_qc(fetched, job, tmp_path / "out", speculative=True)
    assert manifest["model"] == key
    assert len(manifest["images"]) == 2
    assert manifest["generator"] == "AI"
    assert manifest["rights_basis"] == "ai_generated_illustration"


def test_the_swap_does_not_change_the_pipeline_code(tmp_path):
    """Two models, two configs, one implementation: identical call sequence."""
    plans = []
    for key in ("klein", "sdxl-lightning"):
        (tmp_path / key).mkdir(exist_ok=True)
        cfg_path = _write_config(tmp_path / key, model=key)
        engine = load_engine(cfg_path)
        renders = plan_renders(_specs()[:1], key, per_spec=1)
        job = build_job("t_swap", key, renders, width=320, height=180)
        plans.append(sorted(job.keys()))
    assert plans[0] == plans[1]


# ---------------------------------------------------------- fail-closed
def test_loader_fails_closed_on_missing_file(tmp_path):
    with pytest.raises(EngineConfigError):
        load_engine(tmp_path / "nope.json")


def test_loader_fails_closed_on_invalid_json(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(EngineConfigError):
        load_engine(p)


def test_loader_fails_closed_on_missing_lock_field(tmp_path):
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    del doc["steps"]
    p = tmp_path / "image_engine.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(EngineConfigError):
        load_engine(p)


def test_loader_fails_closed_on_unknown_active_model(tmp_path):
    p = _write_config(tmp_path, model="not-registered")
    with pytest.raises(EngineConfigError):
        load_engine(p)


def test_loader_fails_closed_when_the_active_model_is_blocked(tmp_path):
    p = _write_config(tmp_path, model="zimage")
    with pytest.raises(EngineConfigError):
        load_engine(p)


def test_loader_fails_closed_on_an_entry_without_measurements(tmp_path):
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    doc["models"]["klein"]["measured"]["steady_state_sec_per_image"] = None
    p = tmp_path / "image_engine.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(EngineConfigError):
        load_engine(p)


# ------------------------------------------------------ owner decision
def test_owner_decision_is_owner_gated_while_the_owner_csvs_are_unfilled():
    decision = owner_decision(repo_root=ROOT)
    assert decision["status"] == "OWNER_GATED"
    assert decision["model"] == "klein"
    assert decision["basis"].startswith("agent advisory")
    assert decision["owner_result"] is None


def test_owner_decision_uses_the_owner_csv_when_it_is_filled(tmp_path):
    """A filled owner CSV makes the owner's winner the locked model."""
    repo = tmp_path / "repo"
    (repo / "projects" / "s8_blind").mkdir(parents=True)
    (repo / "projects" / "s7_blind").mkdir(parents=True)
    (repo / "projects" / "s8_blind" / "mapping.json").write_text(json.dumps({
        "scenes": {
            "s01": {"A": "sdxl-lightning", "B": "klein"},
            "s02": {"A": "sdxl-lightning", "B": "klein"},
        },
    }), encoding="utf-8")
    (repo / "projects" / "s8_blind" / "results.csv").write_text(
        "scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,comment\n"
        "s01,A,B,yes,no,cleaner\n"
        "s02,A,B,yes,no,cleaner\n", encoding="utf-8")
    decision = owner_decision(repo_root=repo)
    assert decision["status"] == "OWNER_CONFIRMED"
    assert decision["model"] == "sdxl-lightning"
    assert decision["owner_result"]["wins"] == 2


def test_owner_decision_refuses_to_guess_on_a_tie(tmp_path):
    repo = tmp_path / "repo"
    (repo / "projects" / "s8_blind").mkdir(parents=True)
    (repo / "projects" / "s8_blind" / "mapping.json").write_text(json.dumps({
        "scenes": {
            "s01": {"A": "sdxl-lightning", "B": "klein"},
            "s02": {"A": "sdxl-lightning", "B": "klein"},
        },
    }), encoding="utf-8")
    (repo / "projects" / "s8_blind" / "results.csv").write_text(
        "scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,comment\n"
        "s01,A,B,yes,no,x\n"
        "s02,B,A,no,yes,y\n", encoding="utf-8")
    decision = owner_decision(repo_root=repo)
    assert decision["status"] == "OWNER_GATED"
    assert decision["owner_result"]["winner"] is None
    assert "TIE" in decision["basis"] or "tie" in decision["basis"]


# ------------------------------------------------------------- projections
def test_projection_for_100_images_uses_the_measured_speed():
    engine = load_engine(CONFIG_PATH)
    rows = {}
    for key in REQUIRED_MODELS:
        adapter = adapter_for(engine, key)
        proj = project_gpu_minutes(adapter, 100)
        rows[key] = proj
        expected = adapter.measured["steady_state_sec_per_image"] * 100 / 60.0
        assert proj["render_minutes"] == pytest.approx(expected, abs=0.01)
        assert proj["total_minutes"] > proj["render_minutes"]
        assert proj["images"] == 100


def test_projection_refuses_a_model_without_usable_measurements():
    engine = load_engine(CONFIG_PATH)
    adapter = adapter_for(engine, "zimage")
    with pytest.raises(EngineConfigError):
        project_gpu_minutes(adapter, 100)
