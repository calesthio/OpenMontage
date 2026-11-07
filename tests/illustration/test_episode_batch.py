#!/usr/bin/env python3
"""Red/green tests for tools/illustration/episode_batch.py (G3, L4).

Covers: niche-spec adaptation, deterministic per-model planning, per-episode
budget, single-job-per-model build, cache reuse, fail-closed fetch
verification, and label+QC manifest.

No network. Pillow only for the real-image cases (320x180 keeps QC fast).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.episode_batch import (  # noqa: E402
    BudgetError,
    IMAGE_LABEL,
    SPECULATIVE_LABEL,
    build_job,
    check_budget,
    estimate_wall_seconds,
    images_for_minutes,
    label_and_qc,
    load_specs,
    plan_renders,
    split_cached,
    verify_fetched,
)

CREATURE_DIR = ROOT / "docs/openmontage/niches/speculative_evolution/creatures"


# ---------------------------------------------------------------- fixtures
def _specs():
    return load_specs(CREATURE_DIR)


def _job(n=2, model="klein", episode="t_ep"):
    renders = plan_renders(_specs()[:1], model, per_spec=n)
    return build_job(episode, model, renders, width=320, height=180)


def _noise_image(path: Path, size=(320, 180), seed=1):
    """Sharp, non-flat image so blur variance clears the QC floor."""
    img = Image.new("RGB", size, (20, 69, 92))
    d = ImageDraw.Draw(img)
    for i in range(0, size[0], 4):
        shade = (seed * 37 + i * 13) % 255
        d.line([(i, 0), (i, size[1])], fill=(shade, (shade * 3) % 255, (shade * 7) % 255))
    img.save(path)
    return path


def _fetched_tree(tmp_path, job, *, black=None, drop=None, job_id=None, mutate_sha=False):
    """Write a kernel-shaped fetched tree: manifest.json + images/."""
    root = tmp_path / "fetched"
    (root / "images").mkdir(parents=True, exist_ok=True)
    images = []
    for r in job["renders"]:
        if drop and r["render_id"] in drop:
            continue
        name = f"{r['render_id']}.png"
        p = _noise_image(root / "images" / name, (job["width"], job["height"]),
                         seed=r["seed"] % 200 + 1)
        data = p.read_bytes()
        images.append({
            "render_id": r["render_id"],
            "file": name,
            "sha256": hashlib.sha256(data if not mutate_sha else data[:-10]).hexdigest(),
            "bytes": len(data),
            "black": bool(black and r["render_id"] in black),
        })
    manifest = {
        "job_id": job_id or job["job_id"],
        "generated": len(images),
        "images": images,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


# ------------------------------------------------------------ spec loading
def test_load_specs_reads_niche_creature_yaml():
    specs = _specs()
    assert len(specs) == 6
    names = [s.name for s in specs]
    assert "filter_drifter" in names
    for s in specs:
        assert s.creature.subject.strip(), s.name
        assert s.creature.style.strip(), s.name
        assert s.creature.palette, s.name


def test_load_specs_rejects_empty_dir(tmp_path):
    with pytest.raises(ValueError):
        load_specs(tmp_path)


def test_plan_prompts_build_for_all_models():
    for model in ("klein", "sdxl", "zimage"):
        renders = plan_renders(_specs()[:1], model, per_spec=2)
        assert len(renders) == 2
        for r in renders:
            assert len(r["prompt"]) >= 10
            assert r["prompt_sha256"] == hashlib.sha256(
                f"{model}|{r['prompt']}|{r['seed']}".encode("utf-8")
            ).hexdigest()
        if model == "sdxl":
            assert renders[0]["negative_prompt"]
        else:
            assert renders[0]["negative_prompt"] is None


def test_plan_is_deterministic_and_ids_are_unique():
    a = plan_renders(_specs(), "klein", per_spec=3)
    b = plan_renders(_specs(), "klein", per_spec=3)
    assert a == b
    assert len({r["render_id"] for r in a}) == len(a)
    assert len({r["seed"] for r in a}) == len(a)
    assert len({r["prompt_sha256"] for r in a}) == len(a)


def test_plan_rejects_unknown_model_and_empty_variants():
    specs = _specs()[:1]
    with pytest.raises(ValueError):
        plan_renders(specs, "not-a-model")
    with pytest.raises(ValueError):
        plan_renders(specs, "klein", variants=())


# ------------------------------------------------------------------ budget
def test_images_for_minutes():
    assert images_for_minutes(10.5, per_minute=8) == 84
    with pytest.raises(ValueError):
        images_for_minutes(0)


def test_budget_rejects_empty_and_over_cap():
    with pytest.raises(BudgetError):
        check_budget(0)
    with pytest.raises(BudgetError):
        check_budget(121, cap=120)
    check_budget(84, cap=120)


def test_estimate_wall_seconds_unmeasured_is_none():
    assert estimate_wall_seconds("klein", 84) == pytest.approx(24.691 * 84 + 150, abs=0.1)
    assert estimate_wall_seconds("zimage", 84) is None


# ------------------------------------------------------- job + cache reuse
def test_build_job_is_one_job_per_model():
    job = _job(n=3)
    assert job["job_id"] == "ill-t_ep-klein-1"
    assert job["output_dir"] == "illustrations_t_ep_klein"
    assert job["episode_id"] == "t_ep"
    assert job["install_ladder"][0] == "released_037_x4"
    assert len(job["renders"]) == 3
    assert job["width"] == 320 and job["height"] == 180


def test_build_job_attempt_two_changes_something():
    a = _job(n=1)
    b = build_job("t_ep", "klein", a["renders"], attempt=2)
    assert a["job_id"] != b["job_id"]
    assert a["changed_from_previous"] != b["changed_from_previous"]


def test_split_cached_reuses_matching_prompt_sha(tmp_path):
    job = _job(n=2)
    cache = tmp_path / "cache"
    cache.mkdir()
    _noise_image(cache / "a.png")
    cache.joinpath("illustration_manifest.json").write_text(json.dumps({"images": [
        {"prompt_sha256": job["renders"][0]["prompt_sha256"], "file": "a.png"},
    ]}), encoding="utf-8")
    todo, reused = split_cached(job["renders"], cache)
    assert [r["render_id"] for r in todo] == [job["renders"][1]["render_id"]]
    assert [r["render_id"] for r in reused] == [job["renders"][0]["render_id"]]
    assert reused[0]["cached_path"].endswith("a.png")


# ------------------------------------------------------ fetch verification
def test_verify_fetched_accepts_good_tree(tmp_path):
    job = _job(n=2)
    res = verify_fetched(_fetched_tree(tmp_path, job), job)
    assert res["ok"] is True, res.get("error")


def test_verify_fetched_rejects_missing_manifest(tmp_path):
    job = _job(n=2)
    empty = tmp_path / "empty"
    empty.mkdir()
    res = verify_fetched(empty, job)
    assert res["ok"] is False
    assert "manifest" in res["error"]


def test_verify_fetched_rejects_job_id_mismatch(tmp_path):
    job = _job(n=1)
    res = verify_fetched(_fetched_tree(tmp_path, job, job_id="ill-other-klein-1"), job)
    assert res["ok"] is False and "job_id" in res["error"]


def test_verify_fetched_rejects_missing_render(tmp_path):
    job = _job(n=2)
    res = verify_fetched(_fetched_tree(tmp_path, job, drop={job["renders"][0]["render_id"]}), job)
    assert res["ok"] is False and "missing image" in res["error"]


def test_verify_fetched_rejects_sha_mismatch(tmp_path):
    job = _job(n=1)
    res = verify_fetched(_fetched_tree(tmp_path, job, mutate_sha=True), job)
    assert res["ok"] is False and "sha256" in res["error"]


def test_verify_fetched_rejects_black_frame(tmp_path):
    job = _job(n=2)
    res = verify_fetched(_fetched_tree(tmp_path, job, black={job["renders"][1]["render_id"]}), job)
    assert res["ok"] is False and "black" in res["error"]


# ------------------------------------------------------ label + QC manifest
def test_label_and_qc_burns_label_and_writes_manifest(tmp_path):
    job = _job(n=2)
    fetched = _fetched_tree(tmp_path, job)
    out = tmp_path / "out"
    manifest = label_and_qc(fetched, job, out, speculative=True)
    assert manifest["label"] == SPECULATIVE_LABEL
    assert manifest["generator"] == "AI"
    assert manifest["rights_basis"] == "ai_generated_illustration"
    assert manifest["job_id"] == job["job_id"]
    assert len(manifest["images"]) == 2
    for ent in manifest["images"]:
        p = out / ent["file"]
        assert p.is_file()
        assert ent["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        assert ent["label"] == SPECULATIVE_LABEL
        assert ent["qc"]["aspect_ok"] is True
    assert (out / "illustration_manifest.json").is_file()
    assert manifest["qc"]["total"] == 2


def test_label_and_qc_non_speculative_uses_plain_label(tmp_path):
    job = _job(n=1)
    manifest = label_and_qc(_fetched_tree(tmp_path, job), job, tmp_path / "out2")
    assert manifest["images"][0]["label"] == IMAGE_LABEL


def test_label_and_qc_fails_closed_without_manifest(tmp_path):
    job = _job(n=1)
    empty = tmp_path / "nomanifest"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        label_and_qc(empty, job, tmp_path / "out3")
