"""Tests for scripts/s7_checks.py (S7-6).

Contract: objective flags only --
  * resolution mismatch is flagged;
  * a black image is flagged (and a duplicate pair is detected);
  * saturation/contrast outliers are flagged relative to the model's own median;
  * nothing here judges anatomy or beauty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from scripts.s7_checks import run  # noqa: E402


def _write_model(root: Path, model: str, images):
    d = root / f"s7_bakeoff_{model}"
    (d / "images").mkdir(parents=True)
    entries = []
    for name, arr in images:
        arr = np.asarray(arr, dtype=np.uint8)
        Image.fromarray(arr).save(d / "images" / name)
        entries.append({"render_id": name.replace(".png", ""), "scene_id": "s01",
                        "file": name, "sha256": "x", "bytes": 1})
    (d / "manifest.json").write_text(json.dumps({
        "model": model, "job_id": f"s7-{model}-1", "images": entries,
        "black_count": 0, "nan_count": 0, "oom_count": 0,
        "steady_state_sec_per_image": 1.5, "peak_vram_mb": 100, "load_seconds": 10,
    }), encoding="utf-8")


def _noise(seed: int, size: int = 1024) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (size, size, 3), dtype=np.uint8)


def test_flags_resolution_black_duplicate_and_outliers(tmp_path):
    root = tmp_path / "out"
    grey = _noise(1)
    _write_model(root, "sdxl", [
        ("r0001.png", grey),
        ("r0002.png", grey.copy()),                      # exact duplicate
        ("r0003.png", np.zeros((512, 512, 3), dtype=np.uint8)),  # black + wrong size
        ("r0004.png", np.full((1024, 1024, 3), 255, dtype=np.uint8)),  # blown out
    ])
    report = run(root, tmp_path / "checks.json")

    rows = {r["file"]: r for r in report["images"]}
    assert rows["r0003.png"]["resolution_ok"] is False
    assert rows["r0003.png"]["laplacian_var"] < 15.0
    assert rows["r0001.png"]["resolution_ok"] is True
    dupes = report["duplicates"]
    assert any(d["a"].endswith(":r0001") and d["b"].endswith(":r0002")
               for d in dupes), "the duplicated pair must be reported"
    assert report["per_model"]["sdxl"]["images"] == 4
    # every image carries the saturation / contrast outlier verdicts
    for r in report["images"]:
        assert isinstance(r["saturation_outlier"], bool)
        assert isinstance(r["contrast_outlier"], bool)


def test_saturation_and_contrast_outliers_are_robust_relative_to_the_model(tmp_path):
    root = tmp_path / "out"
    images = [(f"r{i:04d}.png", _noise(i)) for i in range(1, 9)]
    images.append(("r0099.png", np.full((1024, 1024, 3), 255, dtype=np.uint8)))
    _write_model(root, "zimage", images)
    report = run(root, tmp_path / "checks.json")
    rows = {r["file"]: r for r in report["images"]}
    assert rows["r0099.png"]["contrast_outlier"] is True
    assert rows["r0099.png"]["saturation_outlier"] is True
    assert sum(1 for r in report["images"] if r["contrast_outlier"]) == 1


def test_report_is_written_with_thresholds(tmp_path):
    root = tmp_path / "out"
    _write_model(root, "klein", [("r0001.png", _noise(7))])
    out = tmp_path / "checks.json"
    report = run(root, out)
    assert out.is_file()
    assert report["thresholds"]["dup_hamming_same_scene"] == 6
    assert report["note"].startswith("objective flags only")
