"""One command builds cards + EDL + render manifest for an episode."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)

import scripts.build_episode_edl as bee  # noqa: E402

SCRIPT = """# Ep
## Hook
- First sentence of the episode. [SE-01]
- Second sentence of the episode. [SE-02]

## Chapter 1 — Things
- Third sentence with more words in it. [SE-03]
- Fourth sentence. [SE-01]
"""


def _episode(tmp_path):
    ep = tmp_path / "ep"
    (ep / "artifacts").mkdir(parents=True)
    (ep / "assets" / "illustrations").mkdir(parents=True)
    (ep / "script.md").write_text(SCRIPT, encoding="utf-8")
    (ep / "artifacts" / "narration_manifest.json").write_text(
        json.dumps({"expected_duration": 40.0}), encoding="utf-8")
    # fake "labelled" illustrations: plain PNGs are enough for the EDL stage
    imgs = []
    for i in range(1, 5):
        p = ep / "assets" / "illustrations" / f"ill_{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", f"color=c=0x14455C:s=320x180:d=1", "-frames:v", "1",
                        str(p)], check=True)
        imgs.append({"file": str(p), "sha256": "b" * 64, "scene_id": "vent_grazer"})
    (ep / "assets" / "illustrations" / "illustration_manifest.json").write_text(
        json.dumps({"images": imgs, "label": "Speculative illustration",
                    "rights_basis": "ai_generated_illustration"}), encoding="utf-8")
    return ep


def test_builds_edl_and_render_manifest(tmp_path):
    ep = _episode(tmp_path)
    rc = bee.main(["--episode", "t_ep", "--episode-dir", str(ep),
                   "--resolution", "640x360", "--fps", "24"])
    assert rc == 0
    edl = json.loads((ep / "edit_decisions.json").read_text(encoding="utf-8"))
    assert edl["resolution"] == "640x360" and edl["fps"] == 24
    assert edl["cuts"][0]["role"] == "graphics_card"
    assert edl["cuts"][-1]["end"] == pytest.approx(40.0, abs=0.001)
    cards = [c for c in edl["cuts"] if c["role"] == "graphics_card"]
    ill = [c for c in edl["cuts"] if c["role"] == "illustration"]
    assert len(cards) == 2 and len(ill) == 4
    assert all((ep / "assets" / "cards").glob("card_*.png"))

    manifest = json.loads((ep / "render_manifest.json").read_text(encoding="utf-8"))
    assert manifest["resolution"] == "640x360"
    assert len(manifest["assets"]) == len(edl["cuts"])
    for cut in edl["cuts"]:
        entry = manifest["assets"][cut["asset_id"]]
        assert entry["kind"] == cut["kind"]
        assert entry["path"] == cut["source"]


def test_blocks_without_illustration_manifest(tmp_path):
    ep = _episode(tmp_path)
    (ep / "assets" / "illustrations" / "illustration_manifest.json").unlink()
    assert bee.main(["--episode", "t_ep", "--episode-dir", str(ep)]) == 2
    assert not (ep / "edit_decisions.json").exists()


def test_blocks_without_narration_duration(tmp_path):
    ep = _episode(tmp_path)
    (ep / "artifacts" / "narration_manifest.json").unlink()
    assert bee.main(["--episode", "t_ep", "--episode-dir", str(ep)]) == 2


def test_writes_rights_records_and_credits(tmp_path):
    from tools.qa.qc import rights_record_problems

    ep = _episode(tmp_path)
    assert bee.main(["--episode", "t_ep", "--episode-dir", str(ep)]) == 0
    records = json.loads(
        (ep / "artifacts" / "rights_records.json").read_text(encoding="utf-8"))["assets"]
    edl = json.loads((ep / "edit_decisions.json").read_text(encoding="utf-8"))
    assert len(records) == len(edl["cuts"]) == 6  # one record per EDL asset
    assert all(rights_record_problems(r) == [] for r in records)
    credits = (ep / "artifacts" / "credits.txt").read_text(encoding="utf-8")
    assert "Apache-2.0" in credits and "own work" in credits.lower()
