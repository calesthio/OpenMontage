#!/usr/bin/env python3
"""Tests for the S8 bake-off tooling (test set, push job, runner additions)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


push = _load("s8_push", REPO / "scripts/s8_push_bakeoff.py")
build_set = _load("s8_build", REPO / "scripts/s8_build_testset.py")


def test_test_set_has_ten_scenes_and_thirty_renders():
    doc = json.loads((REPO / "docs/openmontage/image_gen/S8_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    assert len(doc["scenes"]) == 10
    assert len(doc["renders"]) == 30
    for model in ("sdxl-lightning", "dreamshaper-xl", "sana-sprint-1.6b"):
        rows = [r for r in doc["renders"] if r["model"] == model]
        assert len(rows) == 10, model
        assert len({r["scene_id"] for r in rows}) == 10
        assert all(r["steps"] and r["guidance_scale"] is not None for r in rows)


def test_sana_has_no_negative_prompt_and_card_steps():
    """SanaSprintPipeline.__call__ has no negative_prompt argument."""
    doc = json.loads((REPO / "docs/openmontage/image_gen/S8_TEST_SET.json")
                     .read_text(encoding="utf-8"))
    sana = [r for r in doc["renders"] if r["model"] == "sana-sprint-1.6b"]
    assert all(r["negative_prompt"] is None for r in sana)
    assert all(r["steps"] == 2 for r in sana)
    lightning = [r for r in doc["renders"] if r["model"] == "sdxl-lightning"]
    assert all(r["steps"] == 8 and r["guidance_scale"] == 0.0
               for r in lightning)
    assert all(r["negative_prompt"] for r in lightning)
    dream = [r for r in doc["renders"] if r["model"] == "dreamshaper-xl"]
    assert all(r["steps"] == 4 and r["guidance_scale"] == 2.0 for r in dream)


def test_seeds_match_the_s7_test_set():
    """The same scene must use the same seed in S8 as in S7."""
    s7 = json.loads((REPO / "docs/openmontage/image_gen/S7_TEST_SET.json")
                    .read_text(encoding="utf-8"))
    s8 = json.loads((REPO / "docs/openmontage/image_gen/S8_TEST_SET.json")
                    .read_text(encoding="utf-8"))
    s7_seeds = {r["scene_id"]: r["seed"] for r in s7["renders"]}
    for r in s8["renders"]:
        assert r["seed"] == s7_seeds[r["scene_id"]], r["scene_id"]


def test_reused_s7_frames_are_sha256_verified():
    reuse = json.loads((REPO / "docs/openmontage/image_gen/S8_REUSE.json")
                       .read_text(encoding="utf-8"))
    assert len(reuse["images"]) == 20
    models = {i["model"] for i in reuse["images"]}
    assert models == {"sdxl", "klein"}
    for item in reuse["images"]:
        assert len(item["sha256"]) == 64
        assert (REPO / item["cached"]).is_file()


def test_job_carries_the_model_card_settings():
    job = push.build_job("sdxl-lightning", 1, 1024, 1024, "first attempt")
    assert job["job_id"] == "s8-sdxl-lightning-1"
    assert job["output_dir"] == "s8_bakeoff_sdxl-lightning"
    assert job["unet_checkpoint"]["repo"] == "ByteDance/SDXL-Lightning"
    assert job["vae_model_id"] == "madebyollin/sdxl-vae-fp16-fix"
    assert len(job["renders"]) == 10
    assert job["install_ladder"] == ["released_037_x4", "released_037_x5",
                                      "released_036_x4"]


def test_attempt_two_skips_the_rung_that_was_tried():
    job = push.build_job("dreamshaper-xl", 2, 1024, 1024, "retry")
    assert job["install_ladder"] == ["released_037_x5", "released_036_x4"]
    assert job["job_id"] == "s8-dreamshaper-xl-2"


def test_runner_is_self_contained_and_embeds_the_job():
    job = push.build_job("sana-sprint-1.6b", 1, 1024, 1024, "first attempt")
    text = push.build_runner(job)
    assert "JOB_EMBEDDED = None" not in text
    assert "json.loads(" in text
    assert "s8-sana-sprint-1.6b-1" in text
    # the engine's own guard is removed so the S8 additions register first
    assert text.count('if __name__ == "__main__":') == 1
    assert text.index("S8 additions") > text.index("def install_and_probe")
    compile(text, "run.py", "exec")  # must be syntactically valid Python


def test_strip_main_guard_removes_the_engine_guard():
    engine = (REPO / "tools/kaggle_bridge/s7_bakeoff_run.py").read_text(
        encoding="utf-8")
    stripped = push.strip_main_guard(engine)
    assert 'if __name__ == "__main__":' not in stripped
    assert "def install_and_probe" in stripped


def test_s8_additions_register_released_only_ladders():
    mod = _load("s8_runner", REPO / "tools/kaggle_bridge/s8_bakeoff_run.py")
    assert mod.S8_LADDER == ["released_037_x4", "released_037_x5",
                             "released_036_x4"]
    for rung in mod.S8_LADDER:
        assert "git+" not in rung
    engine = mod._ENGINE  # the engine module the additions registered into
    for model in ("sdxl-lightning", "dreamshaper-xl", "sana-sprint-1.6b"):
        assert engine.DEFAULT_LADDERS[model] == mod.S8_LADDER
        assert engine.PIPELINE_CANDIDATES[model]
        assert engine.LOAD_CONFIG[model]["guidance_override"] is not None


def test_composed_runner_registers_the_s8_models_without_the_engine_file():
    """The concatenated run.py must not try to import the engine module."""
    job = push.build_job("sdxl-lightning", 1, 1024, 1024, "first attempt")
    text = push.build_runner(job)
    import types
    mod = types.ModuleType("s8_composed")
    mod.__file__ = "/kaggle/working/run.py"
    sys.modules["s8_composed"] = mod
    exec(compile(text, "run.py", "exec"), mod.__dict__)  # noqa: S102
    ns = mod.__dict__
    assert ns["PIPELINE_CANDIDATES"]["sdxl-lightning"] == [
        "StableDiffusionXLPipeline"]
    assert ns["PIPELINE_CANDIDATES"]["sana-sprint-1.6b"][0] == \
        "SanaSprintPipeline"
    assert ns["DEFAULT_LADDERS"]["dreamshaper-xl"] == [
        "released_037_x4", "released_037_x5", "released_036_x4"]
    assert ns["LOAD_CONFIG"]["sdxl-lightning"]["scheduler"]["kwargs"] == {
        "timestep_spacing": "trailing"}
    assert ns["JOB_EMBEDDED"]["model"] == "sdxl-lightning"


def test_s8_additions_capture_the_engine_main_before_defining_their_own():
    """RecursionError in S8 attempt 1: `def main` shadowed the engine's main."""
    src = (REPO / "tools/kaggle_bridge/s8_bakeoff_run.py").read_text(
        encoding="utf-8")
    assert src.index("_ENGINE_MAIN = _ENGINE.main") < src.index("def main() -> int:")
    assert "return _ENGINE.main()" not in src
    assert "return _ENGINE_MAIN()" in src


def test_s8_additions_support_an_fp32_text_encoder():
    """SANA-Sprint in fp16 produced NaN embeddings -> black frames."""
    src = (REPO / "tools/kaggle_bridge/s8_bakeoff_run.py").read_text(
        encoding="utf-8")
    assert "text_encoder_fp32" in src
    assert 'te.to(dtype=torch.float32)' in src


def test_steps_and_guidance_overrides_reach_the_renders():
    job = push.build_job("sana-sprint-1.6b", 4, 1024, 1024, "4-step retry",
                          steps=4, guidance_scale=4.5)
    assert all(r["steps"] == 4 for r in job["renders"])
    assert all(r["guidance_scale"] == 4.5 for r in job["renders"])
