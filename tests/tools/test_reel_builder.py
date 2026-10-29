"""Tests for reel_builder and reel_doctor.

Everything here is hermetic: no real footage, no ffmpeg encoding. The doctor is
driven with ``probe=False`` wherever a check would otherwise want to read a
media header, so the suite stays fast and runs the same on a machine with no
sample files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.base_tool import Determinism, ToolStatus
from tools.video.reel_builder import (
    STAGES,
    ReelBuilder,
    ReelDoctor,
    ReelSpec,
    _dip_expr,
    _even,
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _cutlist(cuts: list[dict[str, Any]] | None = None,
             transitions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "profile": {"w": 1080, "h": 1920, "fps": 60},
        "cuts": cuts if cuts is not None else [
            {"id": "01", "src": "A", "ext": ".MP4", "in": 0.0, "out": 2.0, "beat": "open"},
            {"id": "02", "src": "A", "ext": ".MP4", "in": 3.0, "out": 5.0, "beat": "build"},
            {"id": "03", "src": "B", "ext": ".MP4", "in": 1.0, "out": 4.0, "beat": "goal"},
        ],
        "transitions": transitions if transitions is not None else [],
    }


@pytest.fixture()
def project(tmp_path: Path):
    """A minimal project on disk: a cutlist, a timeline and one narration clip."""
    proj = tmp_path / "proj"
    (proj / "artifacts").mkdir(parents=True)
    (proj / "assets" / "audio" / "vo_v1").mkdir(parents=True)
    src = tmp_path / "footage"
    src.mkdir()

    def write(name: str, payload: Any) -> None:
        (proj / "artifacts" / name).write_text(json.dumps(payload), encoding="utf-8")

    write("cutlist.json", _cutlist())
    write("timeline.json", {"01": [0.0, 2.0], "02": [2.0, 4.0], "03": [4.0, 7.0]})
    write("vo.json", {"lines": [{"id": "w01", "at": 1.0}]})
    (proj / "assets" / "audio" / "vo_v1" / "w01.mp3").write_bytes(b"")

    spec = {
        "project_dir": str(proj),
        "source_dir": str(src),
        "total_seconds": 7.0,
        "cutlist": "artifacts/cutlist.json",
        "timeline": "artifacts/timeline.json",
        "vo_script": "artifacts/vo.json",
        "deliverables": [{"name": "out.mp4", "mix": "mix_nomusic"}],
    }
    return {"dir": proj, "src": src, "spec": spec}


def _doctor(spec: dict[str, Any]) -> dict[str, Any]:
    result = ReelDoctor().execute({"spec": spec, "probe": False})
    assert result.success, result.error
    return result.data


# --------------------------------------------------------------------------- #
# tool contracts
# --------------------------------------------------------------------------- #

def test_builder_identity():
    tool = ReelBuilder()
    assert tool.name == "reel_builder"
    assert tool.capability == "video_post"
    assert tool.provider == "ffmpeg"
    assert tool.estimate_cost({}) == 0.0


def test_builder_is_declared_stochastic():
    """The audio tail is not bit-reproducible; the contract must not claim it is."""
    assert ReelBuilder().determinism is Determinism.STOCHASTIC


def test_doctor_identity():
    tool = ReelDoctor()
    assert tool.name == "reel_doctor"
    assert tool.capability == "analysis"
    assert tool.estimate_cost({}) == 0.0


def test_tools_report_a_real_status():
    for tool in (ReelBuilder(), ReelDoctor()):
        assert tool.get_status() in (ToolStatus.AVAILABLE, ToolStatus.UNAVAILABLE)


def test_agent_skills_are_declared():
    """Layer 1 -> Layer 3 bridge. Existence is enforced by the contract suite."""
    for tool in (ReelBuilder(), ReelDoctor()):
        assert tool.agent_skills, f"{tool.name} declares no agent_skills"


# --------------------------------------------------------------------------- #
# spec
# --------------------------------------------------------------------------- #

def test_spec_applies_delivery_defaults():
    spec = ReelSpec({"project_dir": "p", "source_dir": "s"})
    assert (spec.w, spec.h, spec.fps) == (1080, 1920, 60)
    assert (spec.src_w, spec.src_h) == (2160, 3840)
    assert spec.variant == "v1"
    assert spec.total is None


def test_spec_variant_tags_every_working_directory():
    spec = ReelSpec({"project_dir": "p", "source_dir": "s", "variant": "v6"})
    assert spec.seg_dir.name == "seg_v6"
    assert spec.live_dir.name == "live_v6"
    assert spec.master.name == "picture_master_v6.mp4"
    assert spec.a("mix_music").endswith("mix_music_v6.wav")


def test_spec_path_leaves_absolute_paths_alone(tmp_path: Path):
    spec = ReelSpec({"project_dir": str(tmp_path), "source_dir": "s"})
    assert spec.path("artifacts/x.json") == tmp_path / "artifacts" / "x.json"
    absolute = tmp_path / "elsewhere" / "x.json"
    assert spec.path(str(absolute)) == absolute


def test_even_never_returns_an_odd_number():
    # libx264 rejects odd dimensions in yuv420p, so this must always be even
    for value in (1079.4, 1080.0, 1081.6, 3.1, 0.4):
        assert _even(value) % 2 == 0


def test_dip_expr_is_flat_without_dips():
    assert _dip_expr([], 0.7, 0.35) == "volume=1.0"


def test_dip_expr_mentions_every_window():
    expr = _dip_expr([[10.0, 20.0], [30.0, 40.0]], 0.7, 0.35)
    for boundary in ("10.00", "20.00", "30.00", "40.00"):
        assert boundary in expr
    assert "eval=frame" in expr


# --------------------------------------------------------------------------- #
# builder input handling
# --------------------------------------------------------------------------- #

def test_builder_rejects_an_unknown_stage(project):
    result = ReelBuilder().execute({"spec": project["spec"], "stages": ["picture", "nope"]})
    assert not result.success
    assert "nope" in result.error


def test_builder_reports_a_missing_spec_file():
    result = ReelBuilder().execute({"spec": "no/such/spec.json"})
    assert not result.success
    assert "not found" in result.error


def test_builder_names_the_missing_required_field():
    result = ReelBuilder().execute({"spec": {"source_dir": "s"}})
    assert not result.success
    assert "project_dir" in result.error


def test_every_declared_stage_has_a_runner(project):
    """A stage in STAGES with no runner would be silently skipped."""
    for stage in STAGES:
        result = ReelBuilder().execute({"spec": project["spec"], "stages": [stage]})
        assert "unknown stages" not in (result.error or "")


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #

def test_doctor_passes_a_coherent_spec(project):
    data = _doctor(project["spec"])
    assert data["ok"], data["errors"]
    assert data["checks"]["cuts"] == 3


def test_doctor_computes_length_from_the_cuts(project):
    data = _doctor(project["spec"])
    # 2.0 + 2.0 + 3.0, no transitions to subtract
    assert data["checks"]["expected_seconds"] == pytest.approx(7.0)


def test_doctor_subtracts_transition_overlap(project, tmp_path: Path):
    cutlist = _cutlist(transitions=[{"after": "01", "type": "fade", "duration": 0.5}])
    path = project["dir"] / "artifacts" / "cutlist.json"
    path.write_text(json.dumps(cutlist), encoding="utf-8")
    data = _doctor(project["spec"])
    assert data["checks"]["expected_seconds"] == pytest.approx(6.5)


def test_doctor_warns_when_cuts_do_not_add_up_to_total(project):
    spec = dict(project["spec"], total_seconds=99.0)
    data = _doctor(spec)
    assert any("total_seconds" in w for w in data["warnings"])


def test_doctor_rejects_duplicate_cut_ids(project):
    cutlist = _cutlist()
    cutlist["cuts"][1]["id"] = "01"
    (project["dir"] / "artifacts" / "cutlist.json").write_text(
        json.dumps(cutlist), encoding="utf-8")
    data = _doctor(project["spec"])
    assert not data["ok"]
    assert any("more than once" in e for e in data["errors"])


def test_doctor_rejects_a_transition_after_a_cut_that_does_not_exist(project):
    cutlist = _cutlist(transitions=[{"after": "zz", "type": "fade", "duration": 0.5}])
    (project["dir"] / "artifacts" / "cutlist.json").write_text(
        json.dumps(cutlist), encoding="utf-8")
    data = _doctor(project["spec"])
    assert not data["ok"]
    assert any("does not exist" in e for e in data["errors"])


def test_doctor_flags_a_live_cut_with_no_timeline_slot(project):
    cutlist = _cutlist()
    cutlist["cuts"][0]["live"] = 0.8
    (project["dir"] / "artifacts" / "cutlist.json").write_text(
        json.dumps(cutlist), encoding="utf-8")
    (project["dir"] / "artifacts" / "timeline.json").write_text(
        json.dumps({"02": [2.0, 4.0]}), encoding="utf-8")
    data = _doctor(project["spec"])
    assert not data["ok"]
    assert any("no timeline entry" in e for e in data["errors"])


def test_doctor_reports_a_missing_voiceover_clip(project):
    (project["dir"] / "artifacts" / "vo.json").write_text(
        json.dumps({"lines": [{"id": "w01", "at": 1.0}, {"id": "w02", "at": 2.0}]}),
        encoding="utf-8")
    data = _doctor(project["spec"])
    assert not data["ok"]
    assert any("w02.mp3" in e for e in data["errors"])


def test_doctor_counts_the_voiceover_clips_it_found(project):
    data = _doctor(project["spec"])
    assert data["checks"]["voiceover"] == "1/1 clips present"


def test_doctor_warns_about_a_stabilize_id_that_is_not_a_cut(project):
    spec = dict(project["spec"], stabilize=["01", "99"])
    data = _doctor(spec)
    assert any("99" in w for w in data["warnings"])


def test_doctor_rejects_two_deliverables_with_the_same_name(project):
    spec = dict(project["spec"], deliverables=[
        {"name": "same.mp4", "mix": "mix_nomusic"},
        {"name": "same.mp4", "mix": "mix_nomusic"},
    ])
    result = ReelDoctor().execute({"spec": spec, "probe": True})
    assert any("share a filename" in e for e in result.data["errors"])


def test_doctor_rejects_a_music_mix_with_no_music_configured(project):
    spec = dict(project["spec"], deliverables=[{"name": "m.mp4", "mix": "mix_music"}])
    result = ReelDoctor().execute({"spec": spec, "probe": True})
    assert any("no music is configured" in e for e in result.data["errors"])


def test_doctor_reports_a_missing_cutlist(project):
    spec = dict(project["spec"], cutlist="artifacts/gone.json")
    result = ReelDoctor().execute({"spec": spec, "probe": False})
    assert not result.success or not result.data["ok"]


def test_doctor_writes_nothing(project):
    before = sorted(p.name for p in (project["dir"] / "artifacts").iterdir())
    _doctor(project["spec"])
    after = sorted(p.name for p in (project["dir"] / "artifacts").iterdir())
    assert before == after
