#!/usr/bin/env python3
"""Red/green tests for scripts/run_illustrations.py (G3 driver).

The Kaggle bridge is monkeypatched: these tests never shell out and never
touch the network.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_illustrations as ri  # noqa: E402


# ---------------------------------------------------------------- helpers
def _run(argv):
    sys.argv = ["run_illustrations.py", *argv]
    return ri.main()


def _noise_image(path: Path, size=(320, 180), seed=3):
    img = Image.new("RGB", size, (16, 60, 88))
    d = ImageDraw.Draw(img)
    for i in range(0, size[0], 3):
        s = (seed * 41 + i * 17) % 255
        d.line([(i, 0), (i, size[1])], fill=(s, (s * 5) % 255, (s * 11) % 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


class FakeBridge:
    """Stand-in for KaggleBridgeTool: no subprocess, no network."""

    fetch_source: Path | None = None

    def execute(self, inputs):
        cmd = inputs["command"]
        if cmd == "build_job_folder":
            folder = Path(inputs["job_folder"])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "run.py").write_text(inputs["run_py"], encoding="utf-8")
            return SimpleNamespace(success=True, error=None,
                                   data={"job_folder": str(folder)})
        if cmd == "push":
            return SimpleNamespace(success=True, error=None, data={})
        if cmd == "fetch_output":
            dest = Path(inputs["dest"])
            dest.mkdir(parents=True, exist_ok=True)
            if FakeBridge.fetch_source:
                shutil.copytree(FakeBridge.fetch_source, dest, dirs_exist_ok=True)
            return SimpleNamespace(success=True, error=None, data={})
        raise AssertionError(f"unexpected command {cmd}")


@pytest.fixture()
def fake_bridge(monkeypatch):
    from tools.kaggle_bridge import kaggle_bridge

    FakeBridge.fetch_source = None
    monkeypatch.setattr(kaggle_bridge, "KaggleBridgeTool", FakeBridge)
    return FakeBridge


# -------------------------------------------------------------------- plan
def test_plan_writes_one_job_for_the_model(tmp_path):
    out = tmp_path / "job.json"
    rc = _run(["plan", "--episode", "t_ep", "--per-spec", "2",
               "--job-json", str(out), "--cache", str(tmp_path / "cache")])
    assert rc == 0
    job = json.loads(out.read_text())
    assert job["job_id"] == "ill-t_ep-klein-1"
    assert job["episode_id"] == "t_ep"
    assert len(job["renders"]) == 12          # 6 specs x 2
    assert job["plan"]["specs"] == 6
    assert job["plan"]["to_generate"] == 12


def test_plan_is_deterministic(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for p in (a, b):
        assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                     "--job-json", str(p), "--cache", str(tmp_path / "c")]) == 0
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    assert [r["prompt"] for r in ja["renders"]] == [r["prompt"] for r in jb["renders"]]


def test_plan_rejects_over_budget(tmp_path):
    rc = _run(["plan", "--episode", "t_ep", "--per-spec", "21",
               "--job-json", str(tmp_path / "j.json"), "--cap", "120",
               "--cache", str(tmp_path / "c")])
    assert rc == 2


def test_plan_reuses_cached_images(tmp_path):
    first = tmp_path / "j1.json"
    cache = tmp_path / "cache"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(first), "--cache", str(cache)]) == 0
    job = json.loads(first.read_text())
    # Seed the cache with the first render's prompt hash.
    _noise_image(cache / "cached.png")
    (cache / "illustration_manifest.json").write_text(json.dumps({"images": [
        {"prompt_sha256": job["renders"][0]["prompt_sha256"], "file": "cached.png"},
    ]}), encoding="utf-8")
    second = tmp_path / "j2.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(second), "--cache", str(cache)]) == 0
    j2 = json.loads(second.read_text())
    assert j2["plan"]["reused"] == 1
    assert len(j2["renders"]) == 5


# ------------------------------------------------------------------ submit
def test_submit_dry_run_embeds_job(tmp_path, fake_bridge):
    job_json = tmp_path / "job.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(job_json),
                 "--cache", str(tmp_path / "c")]) == 0
    rc = _run(["submit", "--job-json", str(job_json), "--no-push"])
    assert rc == 0
    work = ROOT / "projects" / "t_ep" / "jobs" / "ill-t_ep-klein-1"
    run_py = (work / "run.py").read_text()
    assert "JOB_EMBEDDED = json.loads(" in run_py
    assert "ill-t_ep-klein-1" in run_py
    # clean up the project folder created by the dry run
    shutil.rmtree(ROOT / "projects" / "t_ep", ignore_errors=True)


def test_submit_attempt_two_skips_tried_ladder_rung(tmp_path, fake_bridge):
    job_json = tmp_path / "job.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(job_json),
                 "--cache", str(tmp_path / "c")]) == 0
    first = json.loads(job_json.read_text())
    assert _run(["submit", "--job-json", str(job_json), "--no-push",
                 "--attempt", "2"]) == 0
    sub = json.loads((ROOT / "projects" / "t_ep" / "jobs" /
                      "ill-t_ep-klein-2" / "job.json").read_text())
    assert sub["job_id"] != first["job_id"]
    assert sub["install_ladder"][0] != first["install_ladder"][0]
    shutil.rmtree(ROOT / "projects" / "t_ep", ignore_errors=True)


def test_submit_limit_and_job_id_override_keep_ladder(tmp_path, fake_bridge):
    """A smoke retry must shrink the batch, keep the proven install rung and
    get a fresh job id (so the failed attempt's folder is not overwritten)."""
    job_json = tmp_path / "job.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "2",
                 "--job-json", str(job_json),
                 "--cache", str(tmp_path / "c")]) == 0
    full = json.loads(job_json.read_text())
    assert len(full["renders"]) > 3
    assert _run(["submit", "--job-json", str(job_json), "--no-push",
                 "--attempt", "2", "--limit", "3",
                 "--job-id", "ill-t_ep-klein-2-smoke",
                 "--keep-ladder"]) == 0
    work = ROOT / "projects" / "t_ep" / "jobs" / "ill-t_ep-klein-2-smoke"
    sub = json.loads((work / "job.json").read_text())
    assert sub["job_id"] == "ill-t_ep-klein-2-smoke"
    assert len(sub["renders"]) == 3
    assert [r["render_id"] for r in sub["renders"]] == \
        [r["render_id"] for r in full["renders"][:3]]
    assert sub["install_ladder"] == full["install_ladder"]
    assert "smoke" in sub["changed_from_previous"]
    assert "ill-t_ep-klein-2-smoke" in (work / "run.py").read_text()
    shutil.rmtree(ROOT / "projects" / "t_ep", ignore_errors=True)


def test_submit_limit_rejects_more_than_planned(tmp_path, fake_bridge):
    job_json = tmp_path / "job.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(job_json),
                 "--cache", str(tmp_path / "c")]) == 0
    n = len(json.loads(job_json.read_text())["renders"])
    assert _run(["submit", "--job-json", str(job_json), "--no-push",
                 "--limit", str(n + 5)]) != 0
    assert not (ROOT / "projects" / "t_ep" / "jobs" / "ill-t_ep-klein-1").exists()
    shutil.rmtree(ROOT / "projects" / "t_ep", ignore_errors=True)


# ------------------------------------------------------------------- fetch
def test_fetch_verifies_labels_and_reports_qc(tmp_path, fake_bridge):
    job_json = tmp_path / "job.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(job_json), "--width", "320", "--height", "180",
                 "--cache", str(tmp_path / "c")]) == 0
    job = json.loads(job_json.read_text())

    src = tmp_path / "kernel_out" / job["output_dir"]
    images = []
    for r in job["renders"]:
        p = _noise_image(src / "images" / f"{r['render_id']}.png",
                         (320, 180), seed=len(images) + 1)
        data = p.read_bytes()
        images.append({"render_id": r["render_id"], "file": p.name,
                       "sha256": hashlib.sha256(data).hexdigest(),
                       "bytes": len(data), "black": False})
    (src / "manifest.json").write_text(json.dumps({
        "job_id": job["job_id"], "generated": len(images), "images": images}),
        encoding="utf-8")
    FakeBridge.fetch_source = tmp_path / "kernel_out"

    out = tmp_path / "out"
    rc = _run(["fetch", "--job-json", str(job_json),
               "--dest", str(tmp_path / "fetched"), "--out", str(out)])
    assert rc in (0, 1)
    manifest = json.loads((out / "illustration_manifest.json").read_text())
    assert manifest["label"] == "Speculative illustration"
    assert len(manifest["images"]) == len(job["renders"])
    assert all((out / e["file"]).is_file() for e in manifest["images"])


def test_fetch_rejects_bad_manifest_and_writes_nothing(tmp_path, fake_bridge):
    job_json = tmp_path / "job.json"
    assert _run(["plan", "--episode", "t_ep", "--per-spec", "1",
                 "--job-json", str(job_json), "--width", "320", "--height", "180",
                 "--cache", str(tmp_path / "c")]) == 0
    src = tmp_path / "kernel_out" / "illustrations_t_ep_klein"
    src.mkdir(parents=True)
    (src / "manifest.json").write_text(json.dumps({
        "job_id": "wrong-id", "generated": 0, "images": []}), encoding="utf-8")
    FakeBridge.fetch_source = tmp_path / "kernel_out"
    out = tmp_path / "out"
    rc = _run(["fetch", "--job-json", str(job_json),
               "--dest", str(tmp_path / "fetched"), "--out", str(out)])
    assert rc == 2
    assert not (out / "illustration_manifest.json").exists()
    verdict = json.loads((tmp_path / "fetched" / "verification.json").read_text())
    assert verdict["ok"] is False
