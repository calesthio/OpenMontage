#!/usr/bin/env python3
"""Red/green tests for the episode-scale image pipeline (P3).

Covers the hard parts with a fake bridge (no Kaggle, no GPU, no network):

  * the image brief: one prompt per visual beat, tagged KNOWN/INFERENCE/SPECULATION,
  * unknown beat / unknown claim -> fail closed,
  * the per-episode budget (images per minute of video),
  * batches of 40-100 prompts, one kernel per batch,
  * partial failure -> only the failed prompts are retried,
  * resume -> images already verified by sha256 are not regenerated,
  * hash mismatch -> the image is re-queued, never trusted,
  * the owner-approved cache -> approved images are never regenerated,
  * hard fail when images < prompts,
  * the per-image seed log and the manifest (versions / params / model).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.episode_run import (  # noqa: E402
    BudgetError,
    EpisodeImages,
    FakeBridge,
    RunError,
)
from tools.illustration.image_brief import (  # noqa: E402
    ImageBriefError,
    build_brief,
    parse_ledger,
    parse_script,
)
from tools.illustration.model_registry import (  # noqa: E402
    active_adapter,
    load_engine,
)
from tools.illustration.style_kit import load_style  # noqa: E402

EPISODE = ROOT / "projects" / "se_pilot"
SCRIPT = EPISODE / "script.md"
LEDGER = EPISODE / "claim_ledger.md"
SPEC_DIR = ROOT / "docs/openmontage/niches/speculative_evolution/creatures"


def _adapter():
    return active_adapter(load_engine())


def _style():
    return load_style("speculative_evolution")


def _run(tmp_path, bridge=None, **kwargs):
    """An episode run rooted in a temp dir (the real episode dir is untouched)."""
    episode = tmp_path / "ep"
    (episode / "assets" / "illustrations").mkdir(parents=True, exist_ok=True)
    return EpisodeImages(episode, _adapter(), _style(), bridge=bridge,
                         spec_dir=SPEC_DIR, script_path=SCRIPT,
                         ledger_path=LEDGER, **kwargs)


# ------------------------------------------------------------------ brief
def test_script_and_ledger_parse():
    beats = parse_script(SCRIPT.read_text(encoding="utf-8"))
    assert len(beats) >= 40
    assert all(b.claim_ids for b in beats)
    claims = parse_ledger(LEDGER.read_text(encoding="utf-8"))
    assert "SE-01" in claims and "SE-09" in claims
    assert claims["SE-01"]["source_type"] == "TWO"
    assert claims["SE-09"]["source_type"] == "SPECULATION"


def test_brief_has_one_prompt_per_visual_beat_with_a_tag():
    brief = build_brief(SCRIPT, LEDGER, SPEC_DIR, _style(), _adapter())
    assert brief["entries"]
    for entry in brief["entries"]:
        assert entry["prompt"]
        assert entry["tag"] in {"KNOWN", "INFERENCE", "SPECULATION"}
        assert entry["seed"]
        assert entry["prompt_sha256"]
        assert entry["subject"]
    ids = [e["beat_id"] for e in brief["entries"]]
    assert len(ids) == len(set(ids))


def test_brief_tags_cover_the_three_evidence_classes():
    brief = build_brief(SCRIPT, LEDGER, SPEC_DIR, _style(), _adapter())
    tags = brief["tags"]
    assert tags["KNOWN"] > 0
    assert tags["INFERENCE"] > 0
    assert tags["SPECULATION"] > 0


def test_creature_prompts_always_carry_the_anatomy_counts():
    brief = build_brief(SCRIPT, LEDGER, SPEC_DIR, _style(), _adapter())
    creatures = [e for e in brief["entries"] if e["subject_type"] == "species"]
    assert creatures
    for entry in creatures:
        assert "limbs," in entry["prompt"]
        assert "eyes," in entry["prompt"]
        assert "horns" in entry["prompt"]


def test_unknown_beat_fails_closed():
    with pytest.raises(ImageBriefError):
        build_brief(SCRIPT, LEDGER, SPEC_DIR, _style(), _adapter(),
                    required_beats=["b999"])


def test_unknown_claim_fails_closed(tmp_path):
    script = tmp_path / "script.md"
    script.write_text("## Chapter 1\n\n- A beat about a thing. [SE-99]\n",
                      encoding="utf-8")
    with pytest.raises(ImageBriefError):
        build_brief(script, LEDGER, SPEC_DIR, _style(), _adapter())


def test_brief_is_deterministic():
    a = build_brief(SCRIPT, LEDGER, SPEC_DIR, _style(), _adapter())
    b = build_brief(SCRIPT, LEDGER, SPEC_DIR, _style(), _adapter())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ------------------------------------------------------------------ budget
def test_budget_limits_the_number_of_images(tmp_path):
    run = _run(tmp_path, narration_minutes=2.0, images_per_minute=7)
    brief = run.build_brief()
    plan = run.plan(brief)
    assert plan["budget"]["max_images"] == 14
    assert len(plan["renders"]) <= 14
    assert plan["truncated"] is True
    assert plan["dropped_beats"]


def test_budget_refuses_an_out_of_range_rate(tmp_path):
    with pytest.raises(BudgetError):
        _run(tmp_path, narration_minutes=2.0, images_per_minute=50)


# ------------------------------------------------------------------ batches
def test_batches_hold_between_40_and_100_prompts(tmp_path):
    run = _run(tmp_path, narration_minutes=20.0, images_per_minute=7)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    assert plan["renders"]
    for batch in plan["batches"]:
        assert 40 <= len(batch["render_ids"]) <= 100
    total = sum(len(b["render_ids"]) for b in plan["batches"])
    assert total == len(plan["renders"])


def test_one_kernel_per_batch(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    submitted = []
    for batch in plan["batches"]:
        result = run.submit(batch)
        submitted.append(result["job_id"])
    assert len(submitted) == len(set(submitted))
    assert bridge.submissions == len(plan["batches"])


# ------------------------------------------------------- partial failure
def test_partial_failure_retries_only_the_failed_prompts(tmp_path):
    bridge = FakeBridge(fail=("r0002",))
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    result = run.fetch(batch)
    assert result["failed"]
    assert result["failed"] == ["r0002"]
    assert len(result["verified"]) == len(batch["render_ids"]) - 1

    # the next submission contains ONLY the failed render
    pending = run.pending()
    assert [r["render_id"] for r in pending] == ["r0002"]


def test_a_retry_changes_the_seed_concretely(tmp_path):
    """A retry must not repeat the same image: the seed is re-drawn."""
    bridge = FakeBridge(fail=("r0002",))
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    original = {r["render_id"]: r["seed"] for r in plan["renders"]}
    run.submit(batch)
    run.fetch(batch)

    pending = run.pending()
    assert len(pending) == 1
    assert pending[0]["seed"] != original["r0002"]
    retries = [l for l in run.seed_log_lines() if l.get("status") == "retry"]
    assert retries and retries[0]["seed"] == pending[0]["seed"]
    # the seed stays inside the reserved range and is unique in the batch
    low, high = _style().seed_policy["range"]
    assert low <= pending[0]["seed"] <= high
    seeds = [r["seed"] for r in run.pending()] + \
        [r["seed"] for r in plan["renders"] if r["render_id"] != "r0002"]
    assert len(seeds) == len(set(seeds))


def test_resume_does_not_regenerate_verified_images(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    run.fetch(batch)

    run2 = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    pending = run2.pending()
    assert pending == [], "verified images must never be regenerated"


def test_a_hash_mismatch_is_detected_and_re_queued(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    run.fetch(batch)
    assert not run.pending()

    # corrupt one cached image: the sha256 no longer matches the state
    cache = run.cache_dir
    victim = sorted(cache.glob("*.png"))[0]
    victim.write_bytes(b"not the image we verified")
    run2 = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    pending = run2.pending()
    assert len(pending) == 1
    assert pending[0]["render_id"] == victim.stem.split("_")[-1]


# -------------------------------------------------------- approved cache
def test_owner_approved_images_are_never_regenerated(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    run.fetch(batch)

    approved_id = batch["render_ids"][0]
    run.approve(approved_id, approved_by="owner")

    run2 = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    pending_ids = [r["render_id"] for r in run2.pending()]
    assert approved_id not in pending_ids
    assert run2.approved_count() == 1


# --------------------------------------------------------------- hard fail
def test_finalize_hard_fails_when_images_are_fewer_than_prompts(tmp_path):
    bridge = FakeBridge(fail=("r0001", "r0002"))
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    run.fetch(batch)
    with pytest.raises(RunError):
        run.finalize()


def test_finalize_writes_the_manifest_with_versions_params_and_model(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    run.fetch(batch)
    manifest = run.finalize()
    assert manifest["model"] == "klein"
    assert manifest["model_id"] == "black-forest-labs/FLUX.2-klein-4B"
    assert manifest["params"]["steps"] == 4
    assert manifest["params"]["guidance"] == 1.0
    assert manifest["params"]["dtype"] == "float16"
    assert manifest["versions"]["diffusers"]
    assert manifest["versions"]["transformers"]
    assert manifest["images"]
    for image in manifest["images"]:
        assert image["sha256"]
        assert image["seed"]
        assert image["tag"] in {"KNOWN", "INFERENCE", "SPECULATION"}
        assert image["prompt_sha256"]


# -------------------------------------------------------------- seed log
def test_every_image_gets_a_seed_log_line(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    lines = run.seed_log_lines()
    assert len(lines) == len(plan["renders"])
    for line in lines:
        assert line["seed"]
        assert line["render_id"]
        assert line["prompt_sha256"]
    seeds = [line["seed"] for line in lines]
    assert len(seeds) == len(set(seeds)), "a seed must not be reused"


def test_seed_log_is_append_only_across_runs(tmp_path):
    bridge = FakeBridge()
    run = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    first = len(run.seed_log_lines())
    run2 = _run(tmp_path, bridge=bridge, narration_minutes=20.0)
    run2.build_brief()
    run2.plan(run2.build_brief(), batch_size=60)
    assert len(run2.seed_log_lines()) == first
