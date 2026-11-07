from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from lib.checkpoint import (
    CheckpointValidationError,
    _validate_prior_reference_lineage,
    write_checkpoint,
)
from lib.pipeline_loader import get_stage_sub_stages, load_pipeline
from schemas.artifacts import (
    list_schema_versions,
    load_schema,
    migrate_artifact,
    validate_artifact,
    validate_artifact_handoffs,
)
from schemas.artifacts.validation import ArtifactSemanticValidationError
from tools.analysis.video_analyzer import VideoAnalyzer


ASPECTS = ("subject", "subject_motion", "scene", "spatial_framing", "camera")


def analysis_fixture() -> dict:
    observations = [
        {
            "id": f"obs-scene-0-{aspect}",
            "scene_index": 0,
            "aspect": aspect,
            "status": "unknown",
            "value": "Not enriched yet.",
            "evidence_refs": [],
            "confidence": "low",
        }
        for aspect in ASPECTS
    ]
    return {
        "version": "1.1",
        "analysis_id": "analysis-fixture",
        "source": {
            "type": "youtube",
            "platform": "youtube",
            "surface": "shorts",
            "url": "https://example.test/watch?v=fixture",
            "duration_seconds": 10,
            "fingerprint": {
                "kind": "locator",
                "algorithm": "sha256",
                "value": "fixture-source",
            },
            "rights_status": "unknown",
            "privacy_status": "review_required",
            "retention_policy": "caller_managed",
        },
        "analysis_run": {
            "id": "run-fixture",
            "depth": "standard",
            "status": "partial",
            "steps_completed": ["metadata", "scene_detect", "keyframes"],
            "steps_failed": [],
            "tool": {"name": "video_analyzer", "version": "0.2.0"},
        },
        "evidence": [
            {
                "id": "ev-source-metadata",
                "kind": "source_metadata",
                "status": "available",
                "source_ref": "https://example.test/watch?v=fixture",
            },
            {
                "id": "ev-scene-0",
                "kind": "scene_detection",
                "status": "available",
                "source_ref": "scenes.json",
                "start_seconds": 0,
                "end_seconds": 10,
                "scene_index": 0,
            },
            {
                "id": "ev-keyframe-0",
                "kind": "keyframe",
                "status": "available",
                "source_ref": "keyframes/frame_0000.jpg",
                "start_seconds": 1,
                "end_seconds": 1,
                "scene_index": 0,
            },
        ],
        "content_analysis": {
            "summary": "A fixture reference.",
            "topics": ["testing"],
            "target_audience": "engineers",
        },
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [
                {
                    "scene_index": 0,
                    "start_time": 0,
                    "end_time": 10,
                    "description": "A fixture scene.",
                    "motion_type": "unknown",
                    "flow_variance": -1,
                    "observation_ids": [item["id"] for item in observations],
                }
            ],
            "pacing_profile": {},
        },
        "five_aspect_observations": observations,
        "assertions": [],
        "keyframes": [
            {
                "id": "keyframe-0",
                "timestamp": 1,
                "scene_index": 0,
                "path": "keyframes/frame_0000.jpg",
                "description": "Fixture frame.",
            }
        ],
        "replication_guidance": {
            "suggested_pipeline": "animation",
            "suggested_playbook": "flat-motion-graphics",
            "key_elements_to_replicate": [],
            "elements_requiring_custom_work": [],
            "estimated_complexity": "simple",
            "motion_required": False,
            "creative_differentiation_seeds": [],
            "preserve": [],
            "change": [],
            "avoid": [],
        },
    }


def proposal_fixture() -> dict:
    concept = {
        "id": "c1",
        "title": "Fixture concept",
        "hook": "A grounded fixture hook.",
        "narrative_structure": "myth_busting",
        "visual_approach": "A simple visual explanation.",
        "target_duration_seconds": 10,
        "why_this_works": "It uses an evidence-backed angle.",
        "reference_analysis_refs": ["analysis-fixture"],
        "narrative_profile_refs": ["explainer_arc@1"],
        "evidence_refs": ["ev-keyframe-0"],
        "preserve": ["The opening contrast."],
        "change": ["The subject matter."],
        "avoid": ["Copying wording or imagery."],
    }
    second = deepcopy(concept)
    second.update(
        {
            "id": "c2",
            "title": "Second fixture concept",
            "narrative_structure": "timeline",
            "narrative_profile_refs": ["but_therefore@1"],
        }
    )
    return {
        "version": "1.1",
        "reference_analysis_refs": ["analysis-fixture"],
        "narrative_profile_refs": ["explainer_arc@1", "but_therefore@1.1"],
        "reference_driven": True,
        "concept_options": [concept, second],
        "selected_concept": {
            "concept_id": "c1",
            "rationale": "Selected for the fixture.",
            "reference_analysis_refs": ["analysis-fixture"],
            "narrative_profile_refs": ["explainer_arc@1"],
        },
        "production_plan": {
            "pipeline": "animation",
            "stages": [],
            "render_runtime": "ffmpeg",
        },
        "cost_estimate": {
            "total_estimated_usd": 0,
            "line_items": [],
            "budget_verdict": "no_budget_set",
        },
        "approval": {"status": "pending"},
    }


def script_fixture() -> dict:
    return {
        "version": "1.1",
        "title": "Fixture script",
        "total_duration_seconds": 10,
        "reference_analysis_refs": ["analysis-fixture"],
        "narrative_profile_refs": ["explainer_arc@1", "but_therefore@1"],
        "sections": [
            {
                "id": "s1",
                "label": "Hook",
                "beat_role": "explainer_arc/hook",
                "text": "A grounded fixture claim.",
                "start_seconds": 0,
                "end_seconds": 10,
                "evidence_refs": ["ev-keyframe-0"],
                "source_refs": [],
                "visual_intent": {"description": "Show the core contrast."},
                "audio_intent": {"description": "Clear, measured narration."},
            }
        ],
    }


def scene_fixture() -> dict:
    return {
        "version": "1.1",
        "reference_analysis_refs": ["analysis-fixture"],
        "narrative_profile_refs": ["explainer_arc@1"],
        "scenes": [
            {
                "id": "sc1",
                "type": "diagram",
                "description": "Fixture scene treatment.",
                "start_seconds": 0,
                "end_seconds": 10,
                "script_section_ids": ["s1"],
                "evidence_refs": ["ev-keyframe-0"],
                "visual_intent": "Show the contrast clearly.",
                "subject": "A simple diagram.",
                "subject_motion": "The two states appear in sequence.",
                "scene": "Clean neutral background.",
                "spatial_framing": "Centered medium composition.",
                "camera": "Locked-off view.",
            }
        ],
    }


def bundle_fixture() -> dict:
    first = analysis_fixture()
    second = deepcopy(first)
    second["analysis_id"] = "analysis-second"
    second["source"]["url"] = "https://example.test/watch?v=second"
    second["source"]["fingerprint"]["value"] = "second-source"
    second["analysis_run"]["id"] = "run-second"
    return {"version": "1.1", "bundle_id": "bundle-fixture", "analyses": [first, second]}


def test_bundle_only_reference_activates_sample_gate():
    manifest = load_pipeline("animated-explainer")
    samples = get_stage_sub_stages(
        manifest,
        "proposal",
        context={"video_analysis_bundle_exists": True},
        include_inactive=False,
    )
    assert any(stage["name"] == "sample" for stage in samples)


def test_version_dispatch_and_legacy_schema_remain_available():
    assert list_schema_versions("video_analysis_brief") == ["1.0", "1.1"]
    assert load_schema("video_analysis_brief", "1.0")["properties"]["version"]["const"] == "1.0"
    assert load_schema("video_analysis_brief", "1.1")["properties"]["version"]["const"] == "1.1"


def test_v11_bundle_members_use_brief_schema():
    bundle = bundle_fixture()
    bundle["analyses"][0]["bogus_member_field"] = True
    with pytest.raises(ArtifactSemanticValidationError, match="video_analysis_brief@1.1 schema"):
        validate_artifact("video_analysis_bundle", bundle)


def test_v11_singular_ids_are_stable_and_resolved():
    script = script_fixture()
    script["voice_performance"] = {"sample_section_id": "bad ref#x"}
    with pytest.raises(ArtifactSemanticValidationError, match="stable section ID"):
        validate_artifact("script", script)

    script["voice_performance"]["sample_section_id"] = "missing-section"
    with pytest.raises(ArtifactSemanticValidationError, match="declared section"):
        validate_artifact("script", script)

    scene = scene_fixture()
    scene["scenes"][0]["script_section_id"] = "bad ref#x"
    with pytest.raises(ArtifactSemanticValidationError, match="stable section ID"):
        validate_artifact("scene_plan", scene)


def test_v11_stable_ids_reject_whitespace_and_separator_collision():
    analysis = analysis_fixture()
    analysis["analysis_run"]["id"] = " "
    with pytest.raises(ArtifactSemanticValidationError, match="analysis_run.id"):
        validate_artifact("video_analysis_brief", analysis)

    analysis = analysis_fixture()
    analysis["analysis_id"] = "A#B"
    with pytest.raises(ArtifactSemanticValidationError, match="cannot contain '#'"):
        validate_artifact("video_analysis_brief", analysis)

    analysis = analysis_fixture()
    analysis["evidence"][0]["id"] = "A#B"
    with pytest.raises(ArtifactSemanticValidationError, match="stable ID characters"):
        validate_artifact("video_analysis_brief", analysis)

    bundle = bundle_fixture()
    bundle["bundle_id"] = " "
    with pytest.raises(ArtifactSemanticValidationError, match="bundle_id"):
        validate_artifact("video_analysis_bundle", bundle)

    bundle = bundle_fixture()
    bundle["bundle_id"] = "bundle#1"
    with pytest.raises(ArtifactSemanticValidationError, match="cannot contain '#'"):
        validate_artifact("video_analysis_bundle", bundle)


def test_v11_stable_ids_reject_embedded_whitespace():
    analysis = analysis_fixture()
    analysis["analysis_id"] = "analysis fixture"
    with pytest.raises(ArtifactSemanticValidationError, match="analysis_id"):
        validate_artifact("video_analysis_brief", analysis)

    analysis = analysis_fixture()
    analysis["analysis_run"]["id"] = "run fixture"
    with pytest.raises(ArtifactSemanticValidationError, match="analysis_run.id"):
        validate_artifact("video_analysis_brief", analysis)

    analysis = analysis_fixture()
    analysis["evidence"][0]["id"] = "ev source"
    with pytest.raises(ArtifactSemanticValidationError, match="stable ID characters"):
        validate_artifact("video_analysis_brief", analysis)

    bundle = bundle_fixture()
    bundle["bundle_id"] = "bundle fixture"
    with pytest.raises(ArtifactSemanticValidationError, match="bundle_id"):
        validate_artifact("video_analysis_bundle", bundle)

    proposal = proposal_fixture()
    proposal["concept_options"][0]["id"] = "concept one"
    proposal["selected_concept"]["concept_id"] = "concept one"
    with pytest.raises(ArtifactSemanticValidationError, match="stable ID characters"):
        validate_artifact("proposal_packet", proposal)

    script = script_fixture()
    script["sections"][0]["id"] = "section one"
    with pytest.raises(ArtifactSemanticValidationError, match="stable ID characters"):
        validate_artifact("script", script)

    scene = scene_fixture()
    scene["scenes"][0]["id"] = "scene one"
    with pytest.raises(ArtifactSemanticValidationError, match="stable ID characters"):
        validate_artifact("scene_plan", scene)


def test_v11_available_provenance_rejects_reserved_locators():
    analysis = analysis_fixture()
    analysis["source"]["url"] = "  UnAvAiLaBlE://invented"
    with pytest.raises(ArtifactSemanticValidationError, match="usable locator"):
        validate_artifact("video_analysis_brief", analysis)

    analysis = analysis_fixture()
    analysis["evidence"][1]["source_ref"] = "  MiGrAtIoN://invented"
    with pytest.raises(ArtifactSemanticValidationError, match="available locator"):
        validate_artifact("video_analysis_brief", analysis)


def test_v11_analysis_requires_explicit_aspect_coverage_and_evidence():
    analysis = analysis_fixture()
    validate_artifact("video_analysis_brief", analysis)

    complete = deepcopy(analysis)
    complete["analysis_run"]["status"] = "complete"
    complete["analysis_run"]["steps_completed"].append("visual_enrichment")
    for item in complete["five_aspect_observations"]:
        item["status"] = "observed"
        item["value"] = "Observed in the fixture frame."
        item["evidence_refs"] = ["ev-keyframe-0"]
    validate_artifact("video_analysis_brief", complete)

    completion_cases = [
        ("source locator", lambda item: item["source"].update(url=" "), "usable locator"),
        ("positive duration", lambda item: item["source"].update(duration_seconds=0), "positive duration"),
        ("fingerprint", lambda item: item["source"]["fingerprint"].update(value=" "), "source.fingerprint"),
        ("summary", lambda item: item["content_analysis"].update(summary=" "), "content metadata"),
        ("topics", lambda item: item["content_analysis"].update(topics=[" "]), "content metadata"),
        ("audience", lambda item: item["content_analysis"].update(target_audience=" "), "content metadata"),
        ("scene evidence", lambda item: item.update(evidence=[item["evidence"][0]]), "scene/keyframe evidence"),
        (
            "keyframe evidence",
            lambda item: item.update(
                evidence=[evidence for evidence in item["evidence"] if evidence["kind"] != "keyframe"]
            ),
            "scene/keyframe evidence",
        ),
        (
            "evidence locator",
            lambda item: next(
                evidence.update(source_ref=" ")
                for evidence in item["evidence"]
                if evidence["kind"] == "keyframe"
            ),
            "scene/keyframe evidence",
        ),
        (
            "reserved evidence locator",
            lambda item: [
                evidence.update(source_ref="  migration://invented")
                for evidence in item["evidence"]
                if evidence["kind"] in {"scene_detection", "keyframe"}
            ],
            "scene/keyframe evidence",
        ),
        (
            "evidence scene anchor",
            lambda item: [
                evidence.update(scene_index=999)
                for evidence in item["evidence"]
                if evidence["kind"] in {"scene_detection", "keyframe"}
            ],
            "unknown scene",
        ),
        (
            "evidence ID",
            lambda item: next(
                evidence.update(id=" ")
                for evidence in item["evidence"]
                if evidence["kind"] == "keyframe"
            ),
            "evidence IDs",
        ),
        (
            "scene evidence range",
            lambda item: next(
                evidence.update(start_seconds=2, end_seconds=3)
                for evidence in item["evidence"]
                if evidence["kind"] == "scene_detection"
            ),
            "scene ranges",
        ),
        (
            "keyframe evidence time",
            lambda item: next(
                evidence.update(start_seconds=2, end_seconds=2)
                for evidence in item["evidence"]
                if evidence["kind"] == "keyframe"
            ),
            "keyframe evidence",
        ),
        (
            "sentinel content",
            lambda item: item["content_analysis"].update(summary="Unknown."),
            "content metadata",
        ),
        (
            "punctuation-only content",
            lambda item: item["content_analysis"].update(
                summary="...", topics=["___"], target_audience="!!!"
            ),
            "content metadata",
        ),
        (
            "scheme-only source",
            lambda item: item["source"].update(url="https://"),
            "usable locator",
        ),
        (
            "scheme-only fingerprint",
            lambda item: item["source"]["fingerprint"].update(value="sha256:"),
            "source.fingerprint",
        ),
        (
            "retention policy",
            lambda item: item["source"].update(retention_policy=" "),
            "retention_policy",
        ),
        (
            "observed sentinel",
            lambda item: item["five_aspect_observations"][0].update(value="Unknown."),
            "must be meaningful",
        ),
        (
            "keyframe asset drift",
            lambda item: item["keyframes"][0].update(path="other.jpg"),
            "keyframe evidence",
        ),
        (
            "uppercase reserved locator",
            lambda item: [
                evidence.update(source_ref="  MIGRATION://invented")
                for evidence in item["evidence"]
                if evidence["kind"] in {"scene_detection", "keyframe"}
            ],
            "scene/keyframe evidence",
        ),
        (
            "uppercase reserved source",
            lambda item: item["source"].update(url="MIGRATION://invented"),
            "usable locator",
        ),
    ]
    for _, mutate, message in completion_cases:
        hollow = deepcopy(complete)
        mutate(hollow)
        with pytest.raises(ArtifactSemanticValidationError, match=message):
            validate_artifact("video_analysis_brief", hollow)


    empty_transcript = deepcopy(analysis)
    empty_transcript["analysis_run"]["depth"] = "transcript_only"
    empty_transcript["analysis_run"]["status"] = "complete"
    empty_transcript["analysis_run"]["steps_completed"] = ["metadata", "transcript_whisper"]
    empty_transcript["narration_transcript"] = {"full_text": "", "segments": []}
    with pytest.raises(ArtifactSemanticValidationError, match="non-empty transcript"):
        validate_artifact("video_analysis_brief", empty_transcript)

    metadata_only = deepcopy(analysis)
    metadata_only["analysis_run"]["status"] = "complete"
    metadata_only["analysis_run"]["steps_completed"] = ["metadata"]
    with pytest.raises(ArtifactSemanticValidationError, match="standard/deep"):
        validate_artifact("video_analysis_brief", metadata_only)


    non_finite_evidence = deepcopy(analysis)
    non_finite_evidence["evidence"][1]["start_seconds"] = float("nan")
    with pytest.raises(ArtifactSemanticValidationError, match="finite"):
        validate_artifact("video_analysis_brief", non_finite_evidence)

    dangling_scene_claim = deepcopy(analysis)
    dangling_scene_claim["assertions"] = [{
        "id": "claim-scene",
        "kind": "inferred",
        "statement": "Dangling scene claim.",
        "evidence_refs": ["ev-keyframe-0"],
        "confidence": "low",
        "scene_index": 999,
    }]
    with pytest.raises(ArtifactSemanticValidationError, match="unknown scene"):
        validate_artifact("video_analysis_brief", dangling_scene_claim)

    unavailable = deepcopy(analysis)
    unavailable["five_aspect_observations"][0]["status"] = "observed"
    unavailable["five_aspect_observations"][0]["value"] = "Observed in the fixture frame."
    unavailable["five_aspect_observations"][0]["evidence_refs"] = ["ev-keyframe-0"]
    unavailable["evidence"][2]["status"] = "unavailable"
    with pytest.raises(ArtifactSemanticValidationError, match="unavailable evidence"):
        validate_artifact("video_analysis_brief", unavailable)

    missing_rights = deepcopy(analysis)
    del missing_rights["source"]["rights_status"]
    with pytest.raises(Exception, match="rights_status"):
        validate_artifact("video_analysis_brief", missing_rights)

    incomplete = deepcopy(analysis)
    incomplete["analysis_run"]["status"] = "complete"
    with pytest.raises(Exception, match="visual_enrichment"):
        validate_artifact("video_analysis_brief", incomplete)

    unresolved_complete = deepcopy(incomplete)
    unresolved_complete["analysis_run"]["steps_completed"].append("visual_enrichment")
    with pytest.raises(ArtifactSemanticValidationError, match="unresolved observations"):
        validate_artifact("video_analysis_brief", unresolved_complete)

    missing = deepcopy(analysis)
    missing["five_aspect_observations"] = missing["five_aspect_observations"][:-1]
    with pytest.raises(ArtifactSemanticValidationError, match="missing five-aspect"):
        validate_artifact("video_analysis_brief", missing)

    observed_without_evidence = deepcopy(analysis)
    observed_without_evidence["five_aspect_observations"][0]["status"] = "observed"
    with pytest.raises(Exception, match="evidence_refs"):
        validate_artifact("video_analysis_brief", observed_without_evidence)

    dangling = deepcopy(analysis)
    dangling["assertions"] = [
        {
            "id": "claim-1",
            "kind": "inferred",
            "statement": "Unsupported fixture claim.",
            "evidence_refs": ["ev-missing"],
            "confidence": "low",
        }
    ]
    with pytest.raises(ArtifactSemanticValidationError, match="unknown evidence"):
        validate_artifact("video_analysis_brief", dangling)


def test_v11_downstream_artifacts_are_framework_composable_and_traceable():
    analysis = analysis_fixture()
    proposal = proposal_fixture()
    script = script_fixture()
    scene = scene_fixture()
    validate_artifact_handoffs({
        "video_analysis_brief": analysis,
        "proposal_packet": proposal,
        "script": script,
        "scene_plan": scene,
    })
    validate_artifact("proposal_packet", proposal)
    validate_artifact("script", script)
    validate_artifact("scene_plan", scene)

    missing_scene_aspects = deepcopy(scene)
    for field in ("subject", "subject_motion", "scene", "spatial_framing", "camera"):
        del missing_scene_aspects["scenes"][0][field]
    with pytest.raises(Exception, match="required"):
        validate_artifact("scene_plan", missing_scene_aspects)


    missing_evidence_field = deepcopy(script)
    del missing_evidence_field["sections"][0]["evidence_refs"]
    with pytest.raises(ArtifactSemanticValidationError, match="must declare evidence_refs"):
        validate_artifact("script", missing_evidence_field)

    bad_evidence = deepcopy(script)
    bad_evidence["sections"][0]["evidence_refs"] = ["ev-missing"]
    with pytest.raises(ArtifactSemanticValidationError, match="unresolved evidence"):
        validate_artifact_handoffs({
            "video_analysis_brief": analysis,
            "script": bad_evidence,
        })

    bad_scene = deepcopy(scene)
    bad_scene["scenes"][0]["script_section_ids"] = ["missing-section"]
    with pytest.raises(ArtifactSemanticValidationError, match="dangling"):
        validate_artifact_handoffs({
            "video_analysis_brief": analysis,
            "script": script,
            "scene_plan": bad_scene,
        })


def test_multi_reference_bundle_requires_qualified_ambiguous_evidence():
    bundle = bundle_fixture()
    proposal = proposal_fixture()
    proposal["reference_analysis_refs"] = ["analysis-fixture", "analysis-second"]
    for concept in proposal["concept_options"]:
        concept["reference_analysis_refs"] = ["analysis-fixture", "analysis-second"]
        concept["evidence_refs"] = [
            "analysis-fixture#ev-keyframe-0",
            "analysis-second#ev-keyframe-0",
        ]
    proposal["selected_concept"]["reference_analysis_refs"] = [
        "analysis-fixture",
        "analysis-second",
    ]
    validate_artifact("video_analysis_bundle", bundle)
    validate_artifact("proposal_packet", proposal)
    validate_artifact_handoffs({"video_analysis_bundle": bundle, "proposal_packet": proposal})

    selected_subset = deepcopy(proposal)
    selected_subset["selected_concept"]["reference_analysis_refs"] = ["analysis-fixture"]
    validate_artifact("proposal_packet", selected_subset)
    validate_artifact_handoffs({"video_analysis_bundle": bundle, "proposal_packet": selected_subset})

    cross_wired = deepcopy(proposal)
    cross_wired["concept_options"][0]["reference_analysis_refs"] = ["analysis-fixture"]
    cross_wired["concept_options"][0]["evidence_refs"] = ["analysis-second#ev-keyframe-0"]
    with pytest.raises(ArtifactSemanticValidationError, match="unresolved evidence"):
        validate_artifact_handoffs({"video_analysis_bundle": bundle, "proposal_packet": cross_wired})

    selected_subset = deepcopy(proposal)
    selected_subset["concept_options"][0]["reference_analysis_refs"] = ["analysis-fixture"]
    selected_subset["concept_options"][0]["evidence_refs"] = ["ev-keyframe-0"]
    with pytest.raises(ArtifactSemanticValidationError, match="unresolved evidence"):
        validate_artifact_handoffs({"video_analysis_bundle": bundle, "proposal_packet": selected_subset})

    ambiguous = deepcopy(proposal)
    ambiguous["concept_options"][0]["evidence_refs"] = ["ev-keyframe-0"]
    with pytest.raises(ArtifactSemanticValidationError, match="unresolved evidence"):
        validate_artifact_handoffs({"video_analysis_bundle": bundle, "proposal_packet": ambiguous})


def test_optional_analysis_context_does_not_force_reference_lineage():
    brief = migrate_artifact(
        "brief",
        {
            "version": "1.0",
            "title": "Original brief",
            "hook": "An original hook",
            "key_points": ["An original point"],
            "tone": "clear",
            "style": "clean",
            "target_platform": "youtube",
            "target_duration_seconds": 10,
        },
    )
    brief.pop("reference_driven", None)
    brief.pop("reference_analysis_refs", None)
    validate_artifact("brief", brief)
    validate_artifact_handoffs({"video_analysis_brief": analysis_fixture(), "brief": brief})


def test_v11_handoff_rejects_unresolved_analysis_reference():
    proposal = proposal_fixture()
    with pytest.raises(ArtifactSemanticValidationError, match="without a v1.1"):
        validate_artifact_handoffs({"proposal_packet": proposal})

    analysis = analysis_fixture()
    bad = proposal_fixture()
    bad["reference_analysis_refs"] = ["analysis-other"]
    with pytest.raises(ArtifactSemanticValidationError, match="unresolved IDs"):
        validate_artifact_handoffs({"video_analysis_brief": analysis, "proposal_packet": bad})


def test_v11_migration_is_deterministic_and_does_not_mutate_v10():
    legacy = {
        "version": "1.0",
        "source": {
            "type": "youtube",
            "url": "https://example.test/watch?v=legacy",
            "duration_seconds": 10,
        },
        "content_analysis": {
            "summary": "Legacy fixture.",
            "topics": ["migration"],
            "target_audience": "general",
        },
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 0, "end_time": 10, "description": "Legacy scene."}],
            "pacing_profile": {},
        },
    }
    original = deepcopy(legacy)
    migrated = migrate_artifact("video_analysis_brief", legacy)
    assert legacy == original
    assert migrated["version"] == "1.1"
    assert migrated["analysis_id"].startswith("analysis-")
    assert len(migrated["five_aspect_observations"]) == 5
    validate_artifact("video_analysis_brief", migrated)
    assert migrate_artifact("video_analysis_brief", legacy) == migrated




@pytest.mark.parametrize(
    ("name", "legacy"),
    [
        (
            "brief",
            {
                "version": "1.0",
                "title": "Legacy brief",
                "hook": "A hook",
                "key_points": ["A point"],
                "tone": "clear",
                "style": "clean",
                "target_platform": "youtube",
                "target_duration_seconds": 10,
                "reference_material": ["legacy://reference"],
            },
        ),
        (
            "proposal_packet",
            {
                "version": "1.0",
                "concept_options": [
                    {
                        "id": f"c{i}",
                        "title": f"Concept {i}",
                        "hook": "A hook",
                        "narrative_structure": "story",
                        "visual_approach": "A visual approach",
                        "target_duration_seconds": 10,
                        "why_this_works": "A reason",
                    }
                    for i in range(1, 4)
                ],
                "selected_concept": {"concept_id": "c1", "rationale": "Legacy choice"},
                "production_plan": {"pipeline": "animation", "stages": [], "render_runtime": "ffmpeg"},
                "cost_estimate": {"total_estimated_usd": 0, "line_items": [], "budget_verdict": "no_budget_set"},
                "approval": {"status": "pending"},
            },
        ),
        (
            "script",
            {
                "version": "1.0",
                "title": "Legacy script",
                "total_duration_seconds": 10,
                "sections": [{"id": "s1", "label": "Hook", "text": "A line", "start_seconds": 0, "end_seconds": 10}],
            },
        ),
        (
            "scene_plan",
            {
                "version": "1.0",
                "scenes": [{"id": "sc1", "type": "diagram", "description": "A scene", "start_seconds": 0, "end_seconds": 10, "script_section_id": "s1"}],
            },
        ),
    ],
)
def test_all_v11_migrations_validate_without_mutating(name: str, legacy: dict):
    original = deepcopy(legacy)
    migrated = migrate_artifact(name, legacy)
    assert legacy == original
    assert migrated["version"] == "1.1"
    validate_artifact(name, migrated)


def test_v11_bundle_migration_preserves_independent_sources():
    legacy_analysis = {
        "version": "1.0",
        "source": {"type": "youtube", "url": "https://example.test/legacy", "duration_seconds": 4},
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 0, "end_time": 4, "description": "Scene"}],
            "pacing_profile": {},
        },
    }
    legacy = {"version": "1.0", "analyses": [legacy_analysis, deepcopy(legacy_analysis)]}
    legacy["analyses"][1]["source"]["url"] = "https://example.test/legacy-two"
    migrated = migrate_artifact("video_analysis_bundle", legacy)
    assert migrated["bundle_id"].startswith("bundle-")
    assert [item["analysis_id"] for item in migrated["analyses"]]
    assert len({item["analysis_id"] for item in migrated["analyses"]}) == 2
    validate_artifact("video_analysis_bundle", migrated)


def test_locatorless_legacy_bundle_members_are_disambiguated():
    legacy_analysis = {
        "version": "1.0",
        "source": {"type": "youtube", "duration_seconds": 4},
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 0, "end_time": 4, "description": "Scene"}],
            "pacing_profile": {},
        },
    }
    migrated = migrate_artifact(
        "video_analysis_bundle",
        {"version": "1.0", "analyses": [legacy_analysis, deepcopy(legacy_analysis)]},
    )
    assert len({item["analysis_id"] for item in migrated["analyses"]}) == 2
    assert all(item["source"]["identity_status"] == "unavailable" for item in migrated["analyses"])
    validate_artifact("video_analysis_bundle", migrated)


@pytest.mark.parametrize("locator", [" MIGRATION://legacy ", "UNAVAILABLE://legacy", "..."])
def test_reserved_legacy_locator_becomes_unavailable_provenance(locator: str):
    legacy = {
        "version": "1.0",
        "source": {"type": "youtube", "url": locator, "duration_seconds": 4},
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 0, "end_time": 4, "description": "Scene"}],
            "pacing_profile": {},
        },
    }
    migrated = migrate_artifact("video_analysis_brief", legacy)
    assert "url" not in migrated["source"]
    assert migrated["evidence"][0]["status"] == "unavailable"
    assert migrated["evidence"][0]["source_ref"].startswith("migration://")
    validate_artifact("video_analysis_brief", migrated)


def test_migration_repairs_legacy_fingerprint_and_keyframe_placeholders():
    legacy = {
        "version": "1.0",
        "source": {
            "type": "youtube",
            "url": "https://example.test/legacy",
            "duration_seconds": 4,
            "fingerprint": {
                "kind": "content",
                "algorithm": "sha256",
                "value": "definitely-not-a-sha256-digest",
            },
        },
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 0, "end_time": 4, "description": "Scene"}],
            "pacing_profile": {},
        },
        "keyframes": [{"id": "legacy-frame", "timestamp": 1, "scene_index": 0, "path": "..."}],
    }
    migrated = migrate_artifact("video_analysis_brief", legacy)
    assert migrated["source"]["fingerprint"]["kind"] == "legacy_locator"
    assert migrated["source"]["fingerprint"]["algorithm"] == "sha256"
    assert migrated["keyframes"][0]["path"].startswith("unavailable://")
    assert migrated["evidence"][-1]["status"] == "unavailable"
    validate_artifact("video_analysis_brief", migrated)


def test_migration_normalizes_legacy_scene_section_refs():
    legacy = {
        "version": "1.0",
        "scenes": [{
            "id": "scene one#",
            "type": "animation",
            "description": "Scene",
            "start_seconds": 0,
            "end_seconds": 4,
            "script_section_id": "section one#",
        }],
    }
    migrated = migrate_artifact("scene_plan", legacy)
    scene = migrated["scenes"][0]
    assert scene["id"] == "scene-one"
    assert scene["script_section_id"] == "section-one"
    assert scene["script_section_ids"] == ["section-one"]
    validate_artifact("scene_plan", migrated)


def test_whitespace_legacy_locator_becomes_unavailable_provenance():
    legacy = {
        "version": "1.0",
        "source": {"type": "youtube", "url": "   ", "duration_seconds": 4},
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 0, "end_time": 4, "description": "Scene"}],
            "pacing_profile": {},
        },
    }
    migrated = migrate_artifact("video_analysis_brief", legacy)
    assert "url" not in migrated["source"]
    assert migrated["evidence"][0]["status"] == "unavailable"
    assert migrated["evidence"][0]["source_ref"].startswith("migration://")
    validate_artifact("video_analysis_brief", migrated)


def test_migration_rejects_unsafe_legacy_time_ranges():
    legacy = {
        "version": "1.0",
        "source": {"type": "local_file", "duration_seconds": 4},
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 1,
            "scenes": [{"scene_index": 0, "start_time": 3, "end_time": 5, "description": "Invalid"}],
            "pacing_profile": {},
        },
    }
    with pytest.raises(ValueError, match="exceeds duration"):
        migrate_artifact("video_analysis_brief", legacy)


    non_finite_keyframe = deepcopy(legacy)
    non_finite_keyframe["source"]["duration_seconds"] = 4
    non_finite_keyframe["structure_analysis"]["scenes"] = [{
        "scene_index": 0, "start_time": 0, "end_time": 4, "description": "Scene"
    }]
    non_finite_keyframe["keyframes"] = [{"timestamp": float("nan"), "scene_index": 0}]
    with pytest.raises(ValueError, match="non-finite"):
        migrate_artifact("video_analysis_brief", non_finite_keyframe)

    negative_duration = deepcopy(legacy)
    negative_duration["source"]["duration_seconds"] = -1
    with pytest.raises(ValueError, match="invalid duration"):
        migrate_artifact("video_analysis_brief", negative_duration)


def test_migration_normalizes_schema_valid_duplicate_ids():
    legacy_analysis = {
        "version": "1.0",
        "source": {"type": "local_file", "duration_seconds": 4},
        "content_analysis": {"summary": "Legacy", "topics": [], "target_audience": "general"},
        "structure_analysis": {
            "total_scenes": 2,
            "scenes": [
                {"scene_index": 0, "start_time": 0, "end_time": 2, "description": "One"},
                {"scene_index": 0, "start_time": 2, "end_time": 4, "description": "Two"},
            ],
            "pacing_profile": {},
        },
        "narration_transcript": {
            "segments": [
                {"id": "duplicate", "start": 0, "end": 1, "text": "one"},
                {"id": "duplicate", "start": 1, "end": 2, "text": "two"},
            ]
        },
        "keyframes": [
            {"id": "duplicate", "timestamp": 1, "scene_index": 99},
            {"id": "duplicate", "timestamp": 3, "scene_index": 1, "path": "frame.jpg"},
        ],
    }
    validate_artifact("video_analysis_brief", legacy_analysis)
    migrated_analysis = migrate_artifact("video_analysis_brief", legacy_analysis)
    validate_artifact("video_analysis_brief", migrated_analysis)
    assert [item["id"] for item in migrated_analysis["narration_transcript"]["segments"]] == [
        "segment-0000", "segment-0001"
    ]
    assert [item["id"] for item in migrated_analysis["keyframes"]] == [
        "keyframe-0000", "keyframe-0001"
    ]
    assert migrated_analysis["keyframes"][0]["path"].startswith("unavailable://")

    legacy_proposal = {
        "version": "1.0",
        "concept_options": [
            {"id": "c1", "title": "One", "hook": "Hook", "narrative_structure": "story", "visual_approach": "Visual", "target_duration_seconds": 4, "why_this_works": "Reason"},
            {"id": "c1", "title": "Two", "hook": "Hook", "narrative_structure": "story", "visual_approach": "Visual", "target_duration_seconds": 4, "why_this_works": "Reason"},
            {"id": "c3", "title": "Three", "hook": "Hook", "narrative_structure": "story", "visual_approach": "Visual", "target_duration_seconds": 4, "why_this_works": "Reason"},
        ],
        "selected_concept": {"concept_id": "c1", "rationale": "Legacy"},
        "production_plan": {"pipeline": "animation", "stages": [], "render_runtime": "ffmpeg"},
        "cost_estimate": {"total_estimated_usd": 0, "line_items": [], "budget_verdict": "no_budget_set"},
        "approval": {"status": "pending"},
    }
    validate_artifact("proposal_packet", legacy_proposal)
    migrated_proposal = migrate_artifact("proposal_packet", legacy_proposal)
    validate_artifact("proposal_packet", migrated_proposal)
    assert [item["id"] for item in migrated_proposal["concept_options"]] == ["c1", "c1-2", "c3"]
    assert migrated_proposal["selected_concept"]["concept_id"] == "c1"

    legacy_script = {"version": "1.0", "title": "Legacy", "total_duration_seconds": 4, "sections": [
        {"id": "s1", "text": "one", "start_seconds": 0, "end_seconds": 2},
        {"id": "s1", "text": "two", "start_seconds": 2, "end_seconds": 4},
    ]}
    validate_artifact("script", legacy_script)
    migrated_script = migrate_artifact("script", legacy_script)
    validate_artifact("script", migrated_script)
    assert [item["id"] for item in migrated_script["sections"]] == ["s1", "s1-2"]

    legacy_scene = {"version": "1.0", "scenes": [
        {"id": "scene", "type": "animation", "description": "one", "start_seconds": 0, "end_seconds": 2, "script_section_id": "s1"},
        {"id": "scene", "type": "animation", "description": "two", "start_seconds": 2, "end_seconds": 4, "script_section_id": "s1"},
    ]}
    validate_artifact("scene_plan", legacy_scene)
    migrated_scene = migrate_artifact("scene_plan", legacy_scene)
    validate_artifact("scene_plan", migrated_scene)
    assert [item["id"] for item in migrated_scene["scenes"]] == ["scene", "scene-2"]


def test_v11_transcript_segments_bind_to_evidence():
    analysis = analysis_fixture()
    analysis["narration_transcript"] = {
        "full_text": "A spoken line.",
        "segments": [{"id": "segment-1", "start": 0, "end": 1, "text": "A spoken line."}],
    }
    analysis["evidence"].append({
        "id": "ev-transcript-segment-1",
        "kind": "transcript_segment",
        "status": "available",
        "source_ref": analysis["source"]["url"],
        "start_seconds": 0,
        "end_seconds": 1,
        "excerpt": "A spoken line.",
    })
    validate_artifact("video_analysis_brief", analysis)

    missing = deepcopy(analysis)
    missing["evidence"] = [item for item in missing["evidence"] if item["kind"] != "transcript_segment"]
    with pytest.raises(ArtifactSemanticValidationError, match="transcript segments"):
        validate_artifact("video_analysis_brief", missing)

    mismatched = deepcopy(analysis)
    mismatched["evidence"][-1]["excerpt"] = "A different line."
    with pytest.raises(ArtifactSemanticValidationError, match="transcript segments"):
        validate_artifact("video_analysis_brief", mismatched)


def test_analyzer_normalizes_segments_and_builds_unknown_aspect_scaffold(tmp_path: Path):
    analyzer = VideoAnalyzer()
    assert analyzer.get_info()["artifact_schema"] == {"artifact": "video_analysis_brief", "version": "1.1"}
    assert analyzer._analysis_status(["metadata"], [], "standard", False, False, False) == "partial"
    assert analyzer._analysis_status(["metadata"], [], "transcript_only", False, False, False) == "partial"
    assert analyzer._analysis_status(["metadata", "audio_extract", "transcript_whisper"], [], "transcript_only", True, False, False) == "complete"
    assert not analyzer._has_transcript_content({"narration_transcript": {"full_text": " ", "segments": [{"text": "  "}]}})
    segments = analyzer._normalise_transcript_segments([
        {"start": 0, "duration": 1.25, "text": " first "},
        {"start": 1.25, "end": 2.0, "text": "second"},
    ])
    assert [segment["id"] for segment in segments] == ["segment-0000", "segment-0001"]
    assert segments[0]["end"] == 1.25
    assert segments[1]["end"] == 2.0

    brief = {"structure_analysis": {"scenes": [{"scene_index": 0}]}}
    observations = analyzer._build_five_aspect_observations(brief)
    assert {item["aspect"] for item in observations} == set(ASPECTS)
    assert brief["structure_analysis"]["scenes"][0]["observation_ids"]
    assert analyzer._source_fingerprint(str(tmp_path / "missing.mp4"))["kind"] == "locator"




def test_prior_stage_lineage_rejects_reference_switches_and_dangling_scenes(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    proposal_path = project_dir / "checkpoint_proposal.json"
    proposal_path.write_text(
        '{"status":"completed","artifacts":{"proposal_packet":'
        '{"version":"1.1","reference_analysis_refs":["analysis-fixture"]}}}',
        encoding="utf-8",
    )
    switched_script = script_fixture()
    switched_script["reference_analysis_refs"] = ["analysis-other"]
    with pytest.raises(CheckpointValidationError, match="introduced analysis refs"):
        _validate_prior_reference_lineage(
            tmp_path,
            "project",
            "animated-explainer",
            "script",
            {"script": switched_script},
        )

    proposal_path.write_text(
        json.dumps({
            "status": "completed",
            "artifacts": {
                "proposal_packet": {
                    "version": "1.1",
                    "reference_analysis_refs": ["analysis-fixture", "analysis-second"],
                }
            },
        }),
        encoding="utf-8",
    )
    dropped_script = script_fixture()
    dropped_script["reference_analysis_refs"] = ["analysis-fixture"]
    with pytest.raises(CheckpointValidationError, match="dropped prior analysis refs"):
        _validate_prior_reference_lineage(
            tmp_path,
            "project",
            "animated-explainer",
            "script",
            {"script": dropped_script},
        )

    proposal_path.write_text(
        json.dumps({
            "status": "completed",
            "artifacts": {
                "video_analysis_brief": analysis_fixture(),
                "proposal_packet": proposal_fixture(),
            },
        }),
        encoding="utf-8",
    )
    changed_analysis = analysis_fixture()
    changed_analysis["source"]["fingerprint"]["value"] = "different-source"
    with pytest.raises(CheckpointValidationError, match="source fingerprint"):
        _validate_prior_reference_lineage(
            tmp_path,
            "project",
            "animated-explainer",
            "script",
            {"video_analysis_brief": changed_analysis, "script": script_fixture()},
        )

    script_path = project_dir / "checkpoint_script.json"
    script_path.write_text(
        '{"status":"completed","artifacts":{"script":'
        + json.dumps(script_fixture())
        + "}}",
        encoding="utf-8",
    )
    bad_scene = scene_fixture()
    bad_scene["scenes"][0]["script_section_ids"] = ["missing-section"]
    with pytest.raises(CheckpointValidationError, match="outside the prior script"):
        _validate_prior_reference_lineage(
            tmp_path,
            "project",
            "animated-explainer",
            "scene_plan",
            {"scene_plan": bad_scene},
        )


def test_prior_stage_lineage_uses_selected_proposal_refs(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "checkpoint_proposal.json").write_text(
        json.dumps({
            "status": "completed",
            "artifacts": {
                "proposal_packet": {
                    "version": "1.1",
                    "reference_analysis_refs": ["analysis-fixture", "analysis-second"],
                    "selected_concept": {
                        "reference_analysis_refs": ["analysis-fixture"],
                    },
                }
            },
        }),
        encoding="utf-8",
    )
    selected_script = script_fixture()
    selected_script["reference_analysis_refs"] = ["analysis-fixture"]
    _validate_prior_reference_lineage(
        tmp_path,
        "project",
        "animated-explainer",
        "script",
        {"script": selected_script},
    )


def test_v11_reference_lineage_survives_stage_checkpoints(tmp_path: Path):
    analysis = analysis_fixture()
    proposal = proposal_fixture()
    script = script_fixture()
    scene = scene_fixture()
    write_checkpoint(
        tmp_path,
        "lineage",
        "proposal",
        "completed",
        {"video_analysis_brief": analysis, "proposal_packet": proposal},
    )
    write_checkpoint(
        tmp_path,
        "lineage",
        "script",
        "completed",
        {"video_analysis_brief": analysis, "script": script},
    )
    scene_path = write_checkpoint(
        tmp_path,
        "lineage",
        "scene_plan",
        "completed",
        {"video_analysis_brief": analysis, "script": script, "scene_plan": scene},
    )
    assert scene_path.exists()


def test_partial_analyzer_output_is_explicit_and_validated(tmp_path: Path):
    analyzer = VideoAnalyzer()
    brief = analysis_fixture()
    analyzer._finalize_v11_brief(
        brief,
        tmp_path,
        "https://example.test/watch?v=fixture",
        ["metadata"],
        ["scene_detect: unavailable"],
        "2026-01-01T00:00:00+00:00",
        "standard",
        False,
    )
    assert brief["analysis_run"]["status"] == "partial"
    assert brief["source"]["rights_status"] == "unknown"
    assert brief["source"]["privacy_status"] == "review_required"
    analyzer._save_brief(brief, tmp_path)
    assert (tmp_path / "video_analysis_brief.json").exists()
    validate_artifact("video_analysis_brief", brief)


def test_checkpoint_enforces_v11_handoff_lineage(tmp_path: Path):
    with pytest.raises(CheckpointValidationError, match="without a v1.1"):
        write_checkpoint(
            tmp_path,
            "fixture",
            "proposal",
            "completed",
            {"proposal_packet": proposal_fixture()},
        )

    path = write_checkpoint(
        tmp_path,
        "fixture",
        "proposal",
        "completed",
        {
            "proposal_packet": proposal_fixture(),
            "video_analysis_brief": analysis_fixture(),
        },
    )
    assert path.exists()
