"""Contract: edit_decisions accepts what Explainer renders and still rejects typos.

video_compose hands the artifact to Remotion unchanged, so the props of a scene
component travel on the cut. These tests go through the validator the project
really uses (validate_artifact, and write_checkpoint for the edit stage).
"""

import json
import re
from pathlib import Path

import jsonschema
import pytest

from lib.checkpoint import CheckpointValidationError, write_checkpoint
from schemas.artifacts import load_schema, validate_artifact

ROOT = Path(__file__).resolve().parent.parent.parent
EXPLAINER = (ROOT / "remotion-composer" / "src" / "Explainer.tsx").read_text(encoding="utf-8")
DEMO_PROPS = sorted((ROOT / "remotion-composer" / "public" / "demo-props").glob("*.json"))


def _interface_keys(name: str) -> list[str]:
    body = re.search(rf"^interface {name} \{{(.*?)^\}}", EXPLAINER, re.S | re.M)
    assert body, f"interface {name} not found in Explainer.tsx"
    return re.findall(r"^  (\w+)\??:", body.group(1), re.M)


def _artifact(**fields) -> dict:
    artifact = {
        "version": "1.0",
        "render_runtime": "remotion",
        "cuts": [{"id": "c1", "source": "a.mp4", "in_seconds": 0, "out_seconds": 1}],
    }
    artifact.update(fields)
    return artifact


def _cut(**props) -> dict:
    return _artifact(cuts=[{"id": "c1", "source": "", "in_seconds": 0, "out_seconds": 1, **props}])


def _overlay(**props) -> dict:
    return _artifact(overlays=[props])


COMPONENT_OVERLAY = {"type": "section_title", "in_seconds": 12, "out_seconds": 18}
ASSET_OVERLAY = {"asset_id": "a", "start_seconds": 0, "end_seconds": 1, "position": {"x": 0, "y": 0}}


def test_every_cut_prop_explainer_declares_is_accepted():
    # Fails on an upgrade when upstream adds a prop to Cut: add it to the schema.
    validator = jsonschema.Draft202012Validator(load_schema("edit_decisions"))
    unknown = [
        key
        for key in _interface_keys("Cut")
        if any("unexpected" in error.message for error in validator.iter_errors(_cut(**{key: None})))
    ]
    assert unknown == []


def test_every_overlay_prop_explainer_declares_is_accepted():
    full = {
        **COMPONENT_OVERLAY,
        "text": "",
        "subtitle": "x",
        "accentColor": "#fff",
        "position": "top-left",
        "providers": ["a"],
        "cycleSeconds": 2,
        "label": "x",
    }
    assert set(_interface_keys("Overlay")) <= set(full)
    validate_artifact("edit_decisions", _overlay(**full))


@pytest.mark.parametrize(
    "artifact",
    [
        _cut(type="text_card", text="Hello", backgroundImage="a.png", animation="zoom-in"),
        _cut(type="callout", text="x", callout_type="tip", titleFontSize=40),
        _cut(type="bar_chart", chartData=[{"label": "a", "value": 1}], showValues=True),
        _cut(source="a.mp4", source_in_seconds=2),
        _cut(type="title", text="Chapter one"),
        _cut(source="a.mp4", shot_language={"shot_size": "wide"}, shot_intent="x", narrative_role="evidence", information_role="x", hero_moment=True),
        _overlay(**COMPONENT_OVERLAY, text="", subtitle="Source: Eurostat", accentColor="#8C90A3", position="bottom-left"),
        _overlay(type="provider_chip", in_seconds=0, out_seconds=1, providers=["a"], cycleSeconds=2, label="x"),
        _overlay(**ASSET_OVERLAY),
    ],
    ids=["text_card", "titleFontSize", "bar_chart", "video_seek", "cinematic_title", "shot_metadata", "section_title", "provider_chip", "asset_overlay"],
)
def test_valid_artifacts_pass(artifact):
    validate_artifact("edit_decisions", artifact)


@pytest.mark.parametrize(
    "artifact",
    [
        _cut(type="text_card", text="x", backgroudImage="a.png"),
        _cut(type="text-card", text="x"),
        _cut(type="chart", chartData=[]),
        _cut(type="progress", progress=50),
        _overlay(type="sectoin_title", in_seconds=0, out_seconds=1),
        _overlay(type="section_title", text="x"),
        _overlay(**COMPONENT_OVERLAY, subtitel="x"),
        _overlay(**COMPONENT_OVERLAY, **ASSET_OVERLAY),
        _artifact(foo=1),
    ],
    ids=["cut_key_typo", "cut_type_typo", "undrawn_chart_type", "undrawn_progress_type", "overlay_type_typo", "overlay_no_times", "overlay_key_typo", "mixed_overlay", "root_key"],
)
def test_invalid_artifacts_are_rejected(artifact):
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact("edit_decisions", artifact)


def test_every_scene_type_explainer_dispatches_is_accepted():
    # Fails on an upgrade when upstream adds a scene component: add it to the enum.
    dispatched = set(re.findall(r'cut\.type === "(\w+)"', EXPLAINER))
    accepted = set(load_schema("edit_decisions")["properties"]["cuts"]["items"]["properties"]["type"]["enum"])
    assert dispatched and dispatched <= accepted


def test_cut_typo_error_names_the_key():
    with pytest.raises(jsonschema.ValidationError, match="backgroudImage"):
        validate_artifact("edit_decisions", _cut(type="text_card", backgroudImage="a.png"))


@pytest.mark.parametrize("path", DEMO_PROPS, ids=lambda p: p.stem)
def test_shipped_demo_cuts_and_overlays_validate(path):
    # The demos are render props: they carry captions/theme at the root and no
    # version, which the edit artifact does not hold. Their cuts and overlays must pass.
    demo = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(
        "edit_decisions",
        _artifact(**{key: demo[key] for key in ("cuts", "overlays", "audio") if key in demo}),
    )


def test_demo_props_are_present():
    assert DEMO_PROPS


def test_edit_checkpoint_accepts_scene_props_and_overlays(tmp_path):
    artifact = _cut(type="text_card", text="Hello", titleFontSize=40)
    artifact["overlays"] = [dict(COMPONENT_OVERLAY, subtitle="Source: Eurostat")]
    write_checkpoint(tmp_path, "p", "edit", "completed", {"edit_decisions": artifact})


def test_edit_checkpoint_rejects_a_typo(tmp_path):
    with pytest.raises(CheckpointValidationError, match="backgroudImage"):
        write_checkpoint(tmp_path, "p", "edit", "completed", {"edit_decisions": _cut(type="text_card", backgroudImage="a.png")})
