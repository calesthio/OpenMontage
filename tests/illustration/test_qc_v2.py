#!/usr/bin/env python3
"""Red/green tests for the extended illustration QC (P4).

Covers the new objective checks:

  * the size check (exact frame) and the aspect check,
  * the palette drift check against the niche style file,
  * near-duplicate detection across an episode (two hashes),
  * the REVIEW queue builder: objective flags only, sorted for the owner,
  * the owner approved/rejected ledger (CSV) and the P3 cache reading it.

No network, no Kaggle, no GPU. The fixtures are generated at test time.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from make_qc_fixtures import build  # noqa: E402

from tools.illustration.episode_run import EpisodeImages  # noqa: E402
from tools.illustration.illustration_qc import (  # noqa: E402
    check_aspect_size,
    duplicate_report,
    palette_drift,
    qc_batch,
    qc_image,
)
from tools.illustration.model_registry import (  # noqa: E402
    active_adapter,
    load_engine,
)
from tools.illustration.owner_review import (  # noqa: E402
    LEDGER_COLUMNS,
    read_ledger,
    write_decision,
)
from tools.illustration.review_queue import build_review_queue  # noqa: E402
from tools.illustration.style_kit import load_style  # noqa: E402

STYLE = load_style("speculative_evolution")
PALETTE = STYLE.palette


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    out = tmp_path_factory.mktemp("qc")
    manifest = build(out)
    return manifest, out


# ------------------------------------------------------------ size/aspect
def test_the_size_check_is_exact(fixtures):
    manifest, out = fixtures
    assert check_aspect_size(out / "text_dark_on_light.png", 1024, 576) is True
    assert check_aspect_size(out / "text_dark_on_light.png", 1344, 768) is False


def test_qc_image_reports_size_and_aspect(fixtures):
    manifest, out = fixtures
    result = qc_image(out / "text_dark_on_light.png", 1024, 576)
    assert result["size_ok"] is True
    assert result["aspect_ok"] is True
    assert result["dimensions"] == [1024, 576]


def test_a_wrong_size_fails_the_check(fixtures, tmp_path):
    from PIL import Image
    manifest, out = fixtures
    other = tmp_path / "wrong.png"
    Image.new("RGB", (800, 450), (10, 20, 30)).save(other)
    result = qc_image(other, 1024, 576)
    assert result["size_ok"] is False
    assert result["aspect_ok"] is False
    assert result["passed"] is False


# ------------------------------------------------------------ palette drift
def test_palette_drift_is_measured_against_the_style(fixtures):
    manifest, out = fixtures
    drift = palette_drift(out / "text_dark_on_light.png", PALETTE)
    assert drift["checked"] is True
    assert 0.0 <= drift["coverage"] <= 1.0
    assert set(drift["per_token"]) == set(PALETTE)


def test_an_image_in_the_style_palette_does_not_drift(fixtures):
    manifest, out = fixtures
    # the flat_two_tone fixture is drawn with the style palette colours
    drift = palette_drift(out / "flat_two_tone.png", PALETTE)
    assert drift["coverage"] > 0.2
    assert drift["drift"] is False


def test_an_off_palette_image_drifts(fixtures, tmp_path):
    from PIL import Image
    manifest, out = fixtures
    other = tmp_path / "magenta.png"
    Image.new("RGB", (1024, 576), (255, 0, 255)).save(other)
    drift = palette_drift(other, PALETTE)
    assert drift["coverage"] < 0.05
    assert drift["drift"] is True


# -------------------------------------------------------------- duplicates
def test_near_duplicates_are_found_across_an_episode(fixtures, tmp_path):
    from PIL import Image
    manifest, out = fixtures
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGB", (1024, 576), (12, 90, 120)).save(a)
    Image.new("RGB", (1024, 576), (12, 90, 120)).save(b)
    c = tmp_path / "c.png"
    Image.new("RGB", (1024, 576), (240, 30, 30)).save(c)
    report = duplicate_report([str(a), str(b), str(c)])
    assert len(report["duplicates"]) == 1
    pair = report["duplicates"][0]
    assert {pair["file_i"], pair["file_j"]} == {str(a), str(b)}
    assert pair["average_hash_distance"] == 0
    assert pair["difference_hash_distance"] == 0


def test_qc_batch_reports_duplicates(fixtures, tmp_path):
    from PIL import Image
    manifest, out = fixtures
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGB", (1024, 576), (12, 90, 120)).save(a)
    Image.new("RGB", (1024, 576), (12, 90, 120)).save(b)
    report = qc_batch([str(a), str(b)], 1024, 576)
    assert report["duplicates"]
    assert report["batch_ok"] is False


# ------------------------------------------------------------ review queue
def test_the_review_queue_sorts_by_objective_flags(fixtures, tmp_path):
    manifest, out = fixtures
    files = [str(out / f["file"]) for f in manifest["fixtures"]]
    queue = build_review_queue(files, 1024, 576, PALETTE)
    assert queue["total"] == len(files)
    assert queue["items"]
    # every item carries objective flags and a priority
    for item in queue["items"]:
        assert "priority" in item
        assert isinstance(item["flags"], list)
        assert item["flags"]
    # the priorities are descending
    priorities = [item["priority"] for item in queue["items"]]
    assert priorities == sorted(priorities, reverse=True)
    # a text image must be queued with the text flag
    text_items = [i for i in queue["items"]
                  if "text_like" in i["flags"]]
    assert text_items


def test_the_review_queue_never_judges_anatomy(fixtures):
    manifest, out = fixtures
    files = [str(out / f["file"]) for f in manifest["fixtures"]]
    queue = build_review_queue(files, 1024, 576, PALETTE)
    for item in queue["items"]:
        assert "anatomy" not in item
        assert "anatomy" not in item.get("flags", [])
        assert "beauty" not in item
    assert "anatomy" not in queue


def test_the_review_queue_writes_a_csv_and_json(fixtures, tmp_path):
    manifest, out = fixtures
    files = [str(out / f["file"]) for f in manifest["fixtures"]]
    queue = build_review_queue(files, 1024, 576, PALETTE, out_dir=tmp_path)
    assert (tmp_path / "review_queue.csv").is_file()
    assert (tmp_path / "review_queue.json").is_file()
    rows = list(csv.DictReader((tmp_path / "review_queue.csv").open()))
    assert len(rows) == len(queue["items"])


# ------------------------------------------------------- owner review ledger
def test_the_owner_ledger_round_trip(tmp_path):
    path = tmp_path / "owner_review.csv"
    write_decision(path, "r0027", "approved", sha256="a" * 64,
                   prompt_sha256="b" * 64, reviewer="owner", note="looks right")
    write_decision(path, "r0030", "rejected", sha256="c" * 64,
                   prompt_sha256="d" * 64, reviewer="owner", note="flat")
    rows = read_ledger(path)
    assert len(rows) == 2
    assert rows[0]["decision"] == "approved"
    assert rows[1]["decision"] == "rejected"
    assert set(LEDGER_COLUMNS) <= set(rows[0].keys())


def test_a_second_decision_replaces_the_first(tmp_path):
    path = tmp_path / "owner_review.csv"
    write_decision(path, "r0027", "rejected", sha256="a" * 64, reviewer="owner")
    write_decision(path, "r0027", "approved", sha256="a" * 64, reviewer="owner")
    rows = read_ledger(path)
    assert len(rows) == 1
    assert rows[0]["decision"] == "approved"


def test_the_p3_cache_reads_the_owner_ledger(tmp_path):
    """An approved image is never regenerated; a rejected one is re-queued."""
    from tools.illustration.episode_run import FakeBridge

    episode = tmp_path / "ep"
    (episode / "assets" / "illustrations").mkdir(parents=True, exist_ok=True)
    adapter = active_adapter(load_engine())
    bridge = FakeBridge()
    run = EpisodeImages(episode, adapter, STYLE, bridge=bridge,
                        narration_minutes=20.0,
                        script_path=ROOT / "projects/se_pilot/script.md",
                        ledger_path=ROOT / "projects/se_pilot/claim_ledger.md",
                        spec_dir=ROOT / "docs/openmontage/niches/"
                                 "speculative_evolution/creatures")
    brief = run.build_brief()
    plan = run.plan(brief, batch_size=60)
    batch = plan["batches"][0]
    run.submit(batch)
    run.fetch(batch)
    assert not run.pending()

    # the owner approves one image and rejects another
    ledger = episode / "assets" / "illustrations" / "owner_review.csv"
    approved_id = batch["render_ids"][0]
    rejected_id = batch["render_ids"][1]
    write_decision(ledger, approved_id, "approved",
                   sha256=run.load_state()["renders"][approved_id]["sha256"],
                   reviewer="owner")
    write_decision(ledger, rejected_id, "rejected",
                   sha256=run.load_state()["renders"][rejected_id]["sha256"],
                   reviewer="owner")

    run2 = EpisodeImages(episode, adapter, STYLE, bridge=bridge,
                         narration_minutes=20.0,
                         script_path=ROOT / "projects/se_pilot/script.md",
                         ledger_path=ROOT / "projects/se_pilot/claim_ledger.md",
                         spec_dir=ROOT / "docs/openmontage/niches/"
                                  "speculative_evolution/creatures")
    run2.build_brief()
    run2.plan(run2.build_brief(), batch_size=60)
    pending_ids = [r["render_id"] for r in run2.pending()]
    assert approved_id not in pending_ids, "an approved image must never be regenerated"
    assert rejected_id in pending_ids, "a rejected image must be re-queued"
