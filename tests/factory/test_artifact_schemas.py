"""Every factory artifact must validate against its schema — and reject junk.

A schema that accepts a missing field, a fabricated ID shape or an empty
evidence extract is not a gate. These tests assert both directions: a
minimal valid document passes, and each required field is actually enforced.
"""

from __future__ import annotations

import copy

import pytest

from schemas.artifacts import ARTIFACT_NAMES, validate_artifact

FACTORY_ARTIFACTS = [
    "topic_brief",
    "evidence_ledger",
    "fact_check_report",
    "narration_manifest",
    "alignment_report",
    "qa_report",
    "publish_package",
]


# ---------------------------------------------------------------------------
# Minimal valid documents — one per factory artifact
# ---------------------------------------------------------------------------

RUN_ID = "run-2026-10-15-laundry"
CREATED_AT = "2026-10-15T00:00:00Z"


def _topic_brief() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "working_title": "How Commercial Laundry Makes Its Money",
        "niche": "commercial laundry services",
        "unique_question": "How do industrial laundries turn route density and linen rental into margin?",
        "audience": {"description": "general viewers", "prior_knowledge": "none"},
        "language": "en-US",
        "target_duration_seconds": 75,
        "constraints": [
            "strict zero_cost mode: unknown cost or route is BLOCKED",
            "English (US) narration",
            "real footage with per-asset provenance and license",
            "no automatic publishing",
        ],
        "metadata": {"zero_cost_mode": True},
    }


def _research_brief() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "topic": "commercial laundry economics",
        "research_date": "2026-10-15",
        "landscape": {
            "existing_content": [
                {
                    "title": "Inside a Commercial Laundry Plant",
                    "source": "Example Channel",
                    "url": "https://example.org/video",
                    "angle": "plant tour",
                    "what_it_covers": "machines and workflow, not economics",
                },
                {
                    "title": "The Business of Hotel Linen",
                    "source": "Example Trade Press",
                    "url": "https://example.org/article",
                    "angle": "rental market growth",
                    "what_it_covers": "market size and rental share",
                },
                {
                    "title": "Why Your Sheets Smell Like That",
                    "source": "Example Blog",
                    "url": "https://example.org/blog",
                    "angle": "consumer chemistry",
                    "what_it_covers": "detergent chemistry for consumers",
                },
            ],
            "saturated_angles": ["plant tour b-roll", "market size recap"],
            "underserved_gaps": ["route density economics"],
        },
        "data_points": [
            {
                "claim": "Linen rental shifts capex to the operator",
                "source_url": "https://example.org/report",
                "source_name": "Example industry report",
                "credibility": "primary_source",
            },
            {
                "claim": "Route density drives delivery cost per pound",
                "source_url": "https://example.org/10k",
                "source_name": "Form 10-K FY2024",
                "credibility": "primary_source",
            },
            {
                "claim": "Water and discharge rules shape chemical choice",
                "source_url": "https://example.gov/epa-water",
                "source_name": "Effluent guidelines",
                "credibility": "primary_source",
            },
        ],
        "audience_insights": {
            "common_questions": ["who pays for the linen?", "how is it priced?", "why is water costly?"],
            "misconceptions": [],
            "knowledge_level": "general",
        },
        "angles_discovered": [
            {
                "name": "Route density is the margin",
                "hook": "The truck, not the wash, is the business",
                "type": "data_driven",
                "why_now": "water and energy costs moved",
            },
            {
                "name": "Linen rental is a financing business",
                "hook": "The customer rents the sheets; the operator owns the balance sheet",
                "type": "evergreen",
                "why_now": "rental share keeps rising in hospitality",
            },
            {
                "name": "Compliance sets the chemical bill",
                "hook": "The rules decide what can go in the water",
                "type": "contrarian",
                "why_now": "discharge limits tightened",
            },
        ],
        "sources": [
            {
                "source_id": "SRC-edgar-10k-2024",
                "url": "https://example.org/10k",
                "title": "Form 10-K FY2024",
                "used_for": "segment revenue and route discussion",
                "reliability": "primary",
            },
            {
                "source_id": "SRC-annual-report-2023",
                "url": "https://example.org/annual-2023",
                "title": "Annual report FY2023",
                "used_for": "prior-year baseline for revenue comparison",
                "reliability": "primary",
            },
            {
                "source_id": "SRC-epa-water-rules",
                "url": "https://example.gov/epa-water",
                "title": "Effluent guidelines for industrial laundries",
                "used_for": "water and chemical cost drivers",
                "reliability": "primary",
            },
            {
                "source_id": "SRC-trade-association-data",
                "url": "https://example.org/trade-data",
                "title": "Industry shipment and plant count data",
                "used_for": "market context",
                "reliability": "secondary",
            },
            {
                "source_id": "SRC-trade-press-analysis",
                "url": "https://example.org/press-analysis",
                "title": "Trade press analysis of route economics",
                "used_for": "cross-check of the route-density claim",
                "reliability": "secondary",
            },
        ],
        "metadata": {"gaps": []},
    }


def _evidence_ledger() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "entries": [
            {
                "evidence_id": "EV-10k-2024-route-density",
                "claim_text": "Segment revenue rose from $1.2B in 2019 to $2.0B in 2024",
                "source_id": "SRC-edgar-10k-2024",
                "url": "https://example.org/10k",
                "extract": "Route revenue increased to $2.0 billion in fiscal 2024 from $1.2 billion in fiscal 2019.",
                "publisher": "Example Linen Co.",
                "published_date": "2025-02-14",
                "accessed_date": "2026-10-15",
                "source_type": "primary",
                "source_class": "corporate_filing",
                "claim_label": "fact",
                "quality": "high",
                "metrics": [
                    {"value": "2.0", "unit": "USD billion", "as_of_date": "2024-12-31", "geography": "US"}
                ],
                "caveats": ["company-reported figure"],
            }
        ],
        "metadata": {"source_gaps": [], "unverified_claim_count": 0},
    }


def _script() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "title": "How Commercial Laundry Makes Its Money",
        "total_duration_seconds": 75.0,
        "sections": [
            {
                "id": "hook",
                "text": "Every hotel towel you have ever used was washed in a plant that runs on a schedule tighter than a bus route.",
                "start_seconds": 0.0,
                "end_seconds": 12.0,
                "evidence_ids": ["EV-10k-2024-route-density"],
            },
            {
                "id": "close",
                "text": "The wash is cheap. The route is the business.",
                "start_seconds": 63.0,
                "end_seconds": 75.0,
                "evidence_ids": ["EV-10k-2024-route-density"],
            },
        ],
    }


def _fact_check_report() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "status": "pass",
        "claims": [
            {
                "claim_id": "CLM-route-revenue",
                "claim_text": "Segment revenue rose from $1.2B in 2019 to $2.0B in 2024",
                "script_section": "hook",
                "verdict": "confirmed",
                "evidence_ids": ["EV-10k-2024-route-density"],
                "confidence": 0.95,
                "legally_sensitive": False,
                "action": "keep",
            }
        ],
        "summary": {
            "total_claims": 1,
            "confirmed": 1,
            "partially_confirmed": 0,
            "disputed": 0,
            "refuted": 0,
            "unverified": 0,
            "central_thesis_status": "supported",
        },
    }


def _scene_plan() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "scenes": [
            {
                "id": "scene-1",
                "type": "broll",
                "description": "Industrial laundry sorting line with linen on conveyor",
                "start_seconds": 0.0,
                "end_seconds": 12.0,
                "script_section_id": "hook",
                "search_queries": [
                    "industrial laundry facility sorting linen conveyor",
                    "commercial laundry plant sheets folder machine",
                ],
                "narration_excerpt": "Every hotel towel you have ever used...",
                "visual_class": "illustrative",
                "illustrative_allowed": True,
            },
            {
                "id": "scene-2",
                "type": "diagram",
                "description": "Margin stack: water, chemicals, labour, route",
                "start_seconds": 12.0,
                "end_seconds": 30.0,
                "script_section_id": "body-1",
                "visual_class": "diagram",
                "diagram_spec": {
                    "needed": True,
                    "diagram_type": "mermaid",
                    "definition": "flowchart TD; A[Route revenue] --> B[Water]; A --> C[Chemicals]; A --> D[Labour]",
                    "title": "Where a laundry dollar goes",
                    "units": "USD",
                    "data_source": "EV-10k-2024-route-density",
                    "hold_seconds": 8.0,
                },
            },
        ],
    }


def _narration_manifest() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "provider": "piper",
        "model": "en_US-lessac-medium",
        "voice_id": "en_US-lessac-medium",
        "voice_license": "MIT (piper voices: CC-BY for the recording where noted)",
        "language": "en-US",
        "input_text_sha256": "a" * 64,
        "total_duration_seconds": 75.4,
        "sample_rate_hz": 22050,
        "segments": [
            {
                "segment_id": "seg-hook",
                "script_section": "hook",
                "text": "Every hotel towel you have ever used was washed in a plant that runs on a schedule tighter than a bus route.",
                "audio_path": "projects/run/artifacts/audio/seg-hook.wav",
                "start_seconds": 0.0,
                "end_seconds": 12.1,
                "duration_seconds": 12.1,
                "word_timestamps": [
                    {"word": "Every", "start_seconds": 0.0, "end_seconds": 0.4}
                ],
            }
        ],
        "verification": {
            "method": "provider_timestamps",
            "word_accuracy": None,
            "threshold": 0.95,
            "passed": None,
        },
    }


def _asset_manifest() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "assets": [
            {
                "id": "asset-laundry-1",
                "type": "video",
                "path": "assets/video/laundry_conveyor.mp4",
                "source_tool": "direct_clip_search",
                "scene_id": "scene-1",
                "provider": "wikimedia",
                "license": "CC-BY-4.0",
                "original_url": "https://commons.wikimedia.org/wiki/File:laundry.mp4",
                "author": "Example Contributor",
                "attribution": "Example Contributor, CC-BY-4.0, via Wikimedia Commons",
                "duration_seconds": 24.0,
                "sha256": "b" * 64,
                "search_query": "industrial laundry facility sorting linen conveyor",
                "selection_reason": "only candidate showing a real sorting line",
                "qa_verdict": "pass",
            }
        ],
        "total_cost_usd": 0.0,
    }


def _alignment_report() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "scenes": [
            {
                "scene_id": "scene-1",
                "script_section": "hook",
                "picked_asset_id": "asset-laundry-1",
                "visual_class": "illustrative",
                "verdict": "accepted",
                "frames_inspected": 3,
                "observed_objects": ["conveyor", "linen bundles"],
                "observed_actions": ["sorting"],
                "semantic_match": 0.71,
                "factual_specificity_risk": 0.2,
                "visual_quality": 0.8,
                "reuse_penalty": 0.0,
                "reasons": ["frames show a real sorting line, classed illustrative"],
            },
            {
                "scene_id": "scene-2",
                "picked_asset_id": None,
                "visual_class": "diagram",
                "verdict": "accepted",
                "reasons": ["original diagram rendered from ledger data"],
            },
        ],
        "summary": {
            "total_scenes": 2,
            "accepted": 2,
            "rejected": 0,
            "blocked": 0,
            "max_reuse_count": 1,
            "illustrative_scene_count": 1,
        },
    }


def _render_report() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "outputs": [
            {
                "path": "renders/final.mp4",
                "format": "mp4",
                "resolution": "1920x1080",
                "duration_seconds": 75.4,
                "fps": 30,
                "codec": "h264",
                "audio_codec": "aac",
            }
        ],
        "metadata": {"render_runtime": "ffmpeg"},
    }


def _qa_report() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "status": "pass",
        "output_path": "renders/final.mp4",
        "checks": [
            {
                "check_id": "schema-all-artifacts",
                "category": "schema",
                "name": "all stage artifacts validate",
                "deterministic": True,
                "measured": True,
                "threshold": True,
                "status": "pass",
                "evidence": "schemas.artifacts.validate_artifact",
            },
            {
                "check_id": "reference-id-resolution",
                "category": "reference",
                "name": "evidence/scene/asset IDs resolve",
                "deterministic": True,
                "measured": 0,
                "threshold": 0,
                "status": "pass",
                "evidence": "lib.artifact_ids.resolve_all",
            },
        ],
        "summary": {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "skipped": 0,
            "deterministic_failed": 0,
            "semantic_score": 0.82,
            "semantic_threshold": 0.75,
        },
        "blocking_failures": [],
    }


def _publish_package() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "video": {
            "path": "renders/final.mp4",
            "duration_seconds": 75.4,
            "resolution": "1920x1080",
            "fps": 30,
            "sha256": "c" * 64,
            "container": "mp4",
            "video_codec": "h264",
            "audio_codec": "aac",
        },
        "title": "How Commercial Laundry Makes Its Money",
        "description": "Route density, linen rental and where the margin actually sits.",
        "chapters": [{"start_seconds": 0.0, "label": "The towel"}],
        "sources_credits": [
            {
                "asset_id": "asset-laundry-1",
                "scene_id": "scene-1",
                "provider": "wikimedia",
                "original_url": "https://commons.wikimedia.org/wiki/File:laundry.mp4",
                "author": "Example Contributor",
                "license": "CC-BY-4.0",
                "attribution": "Example Contributor, CC-BY-4.0, via Wikimedia Commons",
                "commercial_use_allowed": True,
            }
        ],
        "manual_approval": {"status": "pending", "upload_target": None},
        "qa_ref": {"status": "pass", "report_path": "artifacts/qa_report.json"},
    }


def _publish_log() -> dict:
    return {
        "version": "1.0",
        "run_id": RUN_ID,
        "created_at": CREATED_AT,
        "entries": [
            {
                "platform": "youtube",
                "status": "pending_review",
                "timestamp": CREATED_AT,
                "export_path": "publish/package",
                "metadata_used": {
                    "title": "How Commercial Laundry Makes Its Money",
                    "description": "Route density, linen rental and where the margin actually sits.",
                },
            }
        ],
        "metadata": {"note": "package created for human review; no upload attempted"},
    }


FIXTURES = {
    "topic_brief": _topic_brief,
    "research_brief": _research_brief,
    "evidence_ledger": _evidence_ledger,
    "script": _script,
    "fact_check_report": _fact_check_report,
    "scene_plan": _scene_plan,
    "narration_manifest": _narration_manifest,
    "asset_manifest": _asset_manifest,
    "alignment_report": _alignment_report,
    "render_report": _render_report,
    "qa_report": _qa_report,
    "publish_package": _publish_package,
    "publish_log": _publish_log,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_factory_artifacts_are_registered() -> None:
    for name in FACTORY_ARTIFACTS:
        assert name in ARTIFACT_NAMES, f"{name} is not registered for validation"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_minimal_valid_artifact_passes(name: str) -> None:
    validate_artifact(name, FIXTURES[name]())


@pytest.mark.parametrize("name", sorted(FACTORY_ARTIFACTS))
def test_empty_document_is_rejected(name: str) -> None:
    with pytest.raises(Exception):
        validate_artifact(name, {})


@pytest.mark.parametrize(
    "artifact,field",
    [
        ("topic_brief", "unique_question"),
        ("topic_brief", "constraints"),
        ("evidence_ledger", "entries"),
        ("fact_check_report", "status"),
        ("narration_manifest", "input_text_sha256"),
        ("alignment_report", "scenes"),
        ("qa_report", "checks"),
        ("publish_package", "video"),
    ],
)
def test_required_field_is_enforced(artifact: str, field: str) -> None:
    doc = FIXTURES[artifact]()
    doc.pop(field, None)
    with pytest.raises(Exception):
        validate_artifact(artifact, doc)


def test_evidence_ledger_rejects_a_fabricated_id_shape() -> None:
    doc = _evidence_ledger()
    doc["entries"][0]["evidence_id"] = "made-up-id"
    with pytest.raises(Exception):
        validate_artifact("evidence_ledger", doc)


def test_evidence_ledger_rejects_a_paraphrase_label_as_opinion_is_not_enough() -> None:
    """claim_label separates fact from interpretation — the enum is enforced."""

    doc = _evidence_ledger()
    doc["entries"][0]["claim_label"] = "truthy"
    with pytest.raises(Exception):
        validate_artifact("evidence_ledger", doc)


def test_evidence_ledger_requires_a_verbatim_extract() -> None:
    doc = _evidence_ledger()
    doc["entries"][0]["extract"] = ""
    with pytest.raises(Exception):
        validate_artifact("evidence_ledger", doc)


def test_fact_check_report_rejects_unknown_verdict() -> None:
    doc = _fact_check_report()
    doc["claims"][0]["verdict"] = "probably_fine"
    with pytest.raises(Exception):
        validate_artifact("fact_check_report", doc)


def test_fact_check_status_enum_is_closed() -> None:
    doc = _fact_check_report()
    doc["status"] = "shipped_anyway"
    with pytest.raises(Exception):
        validate_artifact("fact_check_report", doc)


def test_alignment_report_rejects_unknown_visual_class() -> None:
    doc = _alignment_report()
    doc["scenes"][0]["visual_class"] = "vibes"
    with pytest.raises(Exception):
        validate_artifact("alignment_report", doc)


def test_qa_report_rejects_unknown_check_status() -> None:
    doc = _qa_report()
    doc["checks"][0]["status"] = "trust_me"
    with pytest.raises(Exception):
        validate_artifact("qa_report", doc)


def test_publish_package_requires_explicit_manual_approval() -> None:
    doc = _publish_package()
    doc["manual_approval"].pop("status")
    with pytest.raises(Exception):
        validate_artifact("publish_package", doc)


def test_publish_package_requires_provenance_on_every_credit() -> None:
    doc = _publish_package()
    doc["sources_credits"][0].pop("license")
    with pytest.raises(Exception):
        validate_artifact("publish_package", doc)


def test_script_sections_accept_evidence_ids() -> None:
    """The canonical script schema had no evidence slot; the factory added it."""

    doc = copy.deepcopy(FIXTURES["script"]())
    validate_artifact("script", doc)
    assert doc["sections"][0]["evidence_ids"]


def test_scene_plan_accepts_factory_search_and_diagram_slots() -> None:
    doc = copy.deepcopy(FIXTURES["scene_plan"]())
    validate_artifact("scene_plan", doc)
    assert doc["scenes"][0]["search_queries"]
    assert doc["scenes"][1]["diagram_spec"]["needed"] is True


def test_asset_manifest_accepts_factory_provenance_fields() -> None:
    doc = copy.deepcopy(FIXTURES["asset_manifest"]())
    validate_asset = validate_artifact
    validate_asset("asset_manifest", doc)
    assert doc["assets"][0]["attribution"]
