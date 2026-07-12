"""Dynamic pipeline resolution + the /pipelines catalogue endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.runner.stage_runner import _resolve_stages, CINEMATIC_STAGES, PIPELINE_MAP


client = TestClient(main.app)


def test_override_wins_over_manifest():
    # cinematic/marketing_film are explicit overrides → the hardcoded stages
    names = [s["name"] for s in _resolve_stages("cinematic")]
    assert names == [s["name"] for s in CINEMATIC_STAGES]
    assert _resolve_stages("marketing_film") is PIPELINE_MAP["marketing_film"]


def test_dynamic_manifest_load():
    stages = _resolve_stages("animated-explainer")
    names = [s["name"] for s in stages]
    assert "research" in names and "compose" in names
    # skill paths are normalized to skills/....md
    assert all(s["skill"].startswith("skills/") and s["skill"].endswith(".md")
               for s in stages if s["skill"])
    # manifest-declared approval gates survive
    assert any(s["approval"] for s in stages)


def test_unknown_pipeline_falls_back_to_cinematic():
    names = [s["name"] for s in _resolve_stages("no-such-pipeline-xyz")]
    assert names == [s["name"] for s in CINEMATIC_STAGES]


def test_pipelines_list_endpoint():
    r = client.get("/pipelines")
    assert r.status_code == 200
    pipes = r.json()["pipelines"]
    assert len(pipes) >= 5
    names = {p["name"] for p in pipes}
    assert "cinematic" in names and "animated-explainer" in names
    sample = next(p for p in pipes if p["name"] == "cinematic")
    for key in ("description", "category", "stability", "stages", "approval_stages"):
        assert key in sample
    assert isinstance(sample["stages"], list) and sample["stages"]


def test_all_manifests_listed_even_with_schema_drift():
    # screen-demo / documentary-montage fail strict schema validation; the
    # lenient loader must still surface them (previously silently dropped, and
    # selecting them fell back to cinematic).
    from app.pipeline_catalog import list_manifest_names
    listed = {p["name"] for p in client.get("/pipelines").json()["pipelines"]}
    assert listed == set(list_manifest_names())
    assert {"screen-demo", "documentary-montage"} <= listed


def test_broken_manifest_is_logged_not_silently_dropped(monkeypatch, caplog):
    # Regression: list_pipelines_endpoint's `except Exception: continue`
    # dropped a broken manifest with zero trace — a genuinely bad manifest
    # (not just schema drift, which the lenient loader already handles) would
    # vanish from /pipelines with nothing in the logs to explain why.
    import app.pipeline_catalog as pc
    real_load_manifest = pc.load_manifest

    def flaky(name):
        if name == "cinematic":
            raise ValueError("boom")
        return real_load_manifest(name)

    monkeypatch.setattr(pc, "load_manifest", flaky)
    with caplog.at_level("WARNING"):
        r = client.get("/pipelines")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()["pipelines"]}
    assert "cinematic" not in names
    assert "animated-explainer" in names   # everything else still listed
    assert any("cinematic" in rec.getMessage() for rec in caplog.records)


def test_drifted_pipeline_resolves_own_stages():
    sd = [s["name"] for s in _resolve_stages("screen-demo")]
    assert sd and sd != [s["name"] for s in CINEMATIC_STAGES]


def test_pipeline_detail_endpoint_and_404():
    ok = client.get("/pipelines/cinematic")
    assert ok.status_code == 200
    body = ok.json()
    assert body["name"] == "cinematic"
    assert all("name" in s and "approval" in s for s in body["stages"])
    # a schema-drifted manifest still returns detail (not 400)
    assert client.get("/pipelines/screen-demo").status_code == 200
    assert client.get("/pipelines/definitely-not-real").status_code == 404


# ── security/robustness regressions found by the follow-up audit ────────────

def test_skill_less_stage_resolves_none_not_directory():
    # framework-smoke's research/script stages declare no `skill` key. Before
    # the fix this resolved to "" and Path(OM_ROOT) / "" == OM_ROOT (a real,
    # existing directory), defeating the missing-skill fallback and crashing
    # read_text() with IsADirectoryError on the very first stage.
    stages = _resolve_stages("framework-smoke")
    assert stages, "framework-smoke should resolve real stages, not fall back"
    skill_less = [s for s in stages if s["skill"] is None]
    assert skill_less, "expected at least one skill-less stage in framework-smoke"


def test_pipeline_name_traversal_is_blocked():
    from app.pipeline_catalog import load_manifest
    import pytest
    for bad in ("../config", "../../etc/passwd", "../../../../etc/passwd", "not-a-real-pipeline"):
        with pytest.raises(FileNotFoundError):
            load_manifest(bad)


def test_traversal_via_detail_endpoint_returns_404():
    # Not a route-level slash — "../config" has no literal "/", so FastAPI's
    # plain {name} path param matches it; only load_manifest's allowlist stops it.
    assert client.get("/pipelines/../config").status_code in (404, 307, 308)


def test_cinematic_hardcoded_approval_matches_manifest():
    # Regression: CINEMATIC_STAGES is a hand-maintained copy of
    # pipeline_defs/cinematic.yaml's stage list — it drifted false for
    # scene_plan/assets/publish while the manifest (and each stage's own
    # "Gate Reminder (Binding)" skill text) required a checkpoint, silently
    # skipping the asset-generation cost gate for every job run through the
    # web platform's hardcoded-override path. Every stage's `approval` flag
    # here must match the manifest's human_approval_default exactly.
    from app.pipeline_catalog import load_manifest
    from lib.pipeline_loader import get_stage_human_approval_default
    manifest = load_manifest("cinematic")
    for stage in CINEMATIC_STAGES:
        expected = get_stage_human_approval_default(manifest, stage["name"])
        assert stage["approval"] == expected, (
            f"CINEMATIC_STAGES['{stage['name']}'].approval={stage['approval']} "
            f"but pipeline_defs/cinematic.yaml declares human_approval_default={expected}"
        )


def test_cinematic_hardcoded_stage_shape_matches_manifest():
    # Companion to test_cinematic_hardcoded_approval_matches_manifest above,
    # which only guards the `approval` flag. CINEMATIC_STAGES is still a
    # hand-maintained copy of pipeline_defs/cinematic.yaml's stage list, so
    # names/order, `produces`, and `required_artifacts_in` can drift the same
    # way the approval flags did. Assert those stay in sync too.
    from app.pipeline_catalog import load_manifest
    manifest = load_manifest("cinematic")
    manifest_stages = {s["name"]: s for s in manifest["stages"]}

    assert [s["name"] for s in CINEMATIC_STAGES] == list(manifest_stages), (
        "CINEMATIC_STAGES stage names/order drifted from pipeline_defs/cinematic.yaml"
    )
    for stage in CINEMATIC_STAGES:
        manifest_stage = manifest_stages[stage["name"]]
        assert stage["produces"] == (manifest_stage.get("produces") or []), (
            f"CINEMATIC_STAGES['{stage['name']}'].produces={stage['produces']} "
            f"but pipeline_defs/cinematic.yaml declares produces={manifest_stage.get('produces')}"
        )
        assert stage["required_artifacts_in"] == (manifest_stage.get("required_artifacts_in") or []), (
            f"CINEMATIC_STAGES['{stage['name']}'].required_artifacts_in={stage['required_artifacts_in']} "
            f"but pipeline_defs/cinematic.yaml declares "
            f"required_artifacts_in={manifest_stage.get('required_artifacts_in')}"
        )


def test_load_manifest_never_returns_none(tmp_path, monkeypatch):
    import app.pipeline_catalog as pc
    import lib.pipeline_loader as pl

    (tmp_path / "empty.yaml").write_text("")
    monkeypatch.setattr(pc, "PIPELINE_DEFS_DIR", tmp_path)
    # Simulate strict validation failing (schema drift) so the lenient
    # yaml.safe_load fallback runs — on an empty file that returns None.
    monkeypatch.setattr(pl, "load_pipeline",
                        lambda name, defs_dir=None: (_ for _ in ()).throw(ValueError("drift")))
    result = pc.load_manifest("empty")
    assert result == {}
