"""No downstream artifact may reference an ID that does not exist.

Master Plan section 4: any fake/unknown source_id, evidence_id, scene_id or
asset_id must make the schema or the stage refuse. These tests build small
artifact pairs and assert that a fabricated reference is caught — with the
stage, artifact, field and offending value named.
"""

from __future__ import annotations

import copy

import pytest

from lib.artifact_ids import (
    DanglingReferenceError,
    assert_resolved,
    check_alignment_report,
    check_asset_manifest,
    check_evidence_ledger,
    check_fact_check_report,
    check_publish_package,
    check_script_claims,
    resolve_all,
    summarize,
)
from tests.factory.test_artifact_schemas import (
    _alignment_report,
    _asset_manifest,
    _evidence_ledger,
    _fact_check_report,
    _publish_package,
    _qa_report,
    _research_brief,
    _scene_plan,
    _script,
)


@pytest.fixture()
def chain() -> dict:
    """A fully linked, internally consistent artifact set."""

    return {
        "research_brief": _research_brief(),
        "evidence_ledger": _evidence_ledger(),
        "script": _script(),
        "fact_check_report": _fact_check_report(),
        "scene_plan": _scene_plan(),
        "asset_manifest": _asset_manifest(),
        "alignment_report": _alignment_report(),
        "qa_report": _qa_report(),
        "publish_package": _publish_package(),
    }


def test_a_clean_chain_resolves(chain: dict) -> None:
    assert resolve_all(chain) == []
    assert_resolved(chain)  # must not raise


# --- evidence ledger vs research brief -------------------------------------


def test_fabricated_source_id_is_caught(chain: dict) -> None:
    chain["evidence_ledger"]["entries"][0]["source_id"] = "SRC-does-not-exist"
    dangling = check_evidence_ledger(chain["evidence_ledger"], chain["research_brief"])
    assert len(dangling) == 1
    ref = dangling[0]
    assert ref.kind == "source_id"
    assert ref.value == "SRC-does-not-exist"
    assert ref.defined_in == "research_brief"
    assert ref.stage == "evidence"


def test_missing_source_id_is_caught(chain: dict) -> None:
    chain["evidence_ledger"]["entries"][0]["source_id"] = ""
    dangling = check_evidence_ledger(chain["evidence_ledger"], chain["research_brief"])
    assert len(dangling) == 1
    assert dangling[0].field.endswith("source_id")


# --- script vs evidence ledger ---------------------------------------------


def test_fabricated_evidence_id_in_the_script_is_caught(chain: dict) -> None:
    chain["script"]["sections"][0]["evidence_ids"].append("EV-invented-claim")
    dangling = check_script_claims(chain["script"], chain["evidence_ledger"])
    assert [d.value for d in dangling] == ["EV-invented-claim"]


def test_script_claim_without_any_evidence_is_a_defect(chain: dict) -> None:
    """An empty evidence list is not a citation; the claim is unsupported."""

    chain["script"]["sections"][0]["evidence_ids"] = []
    # An empty list resolves trivially, so the *director* must refuse. The
    # resolver's job is dangling refs; this asserts the resolver does not
    # silently invent coverage either.
    assert check_script_claims(chain["script"], chain["evidence_ledger"]) == []
    assert chain["script"]["sections"][0]["evidence_ids"] == []


def test_nested_script_claims_are_checked(chain: dict) -> None:
    chain["script"]["sections"][0]["claims"] = [
        {"text": "a claim", "evidence_ids": ["EV-10k-2024-route-density", "EV-ghost"]}
    ]
    dangling = check_script_claims(chain["script"], chain["evidence_ledger"])
    assert [d.value for d in dangling] == ["EV-ghost"]


# --- fact check vs evidence + script ---------------------------------------


def test_fact_check_citing_unknown_evidence_is_caught(chain: dict) -> None:
    chain["fact_check_report"]["claims"][0]["evidence_ids"] = ["EV-nowhere"]
    dangling = check_fact_check_report(
        chain["fact_check_report"], chain["evidence_ledger"], chain["script"]
    )
    assert [d.value for d in dangling] == ["EV-nowhere"]


def test_fact_check_pointing_at_an_unknown_script_section_is_caught(chain: dict) -> None:
    chain["fact_check_report"]["claims"][0]["script_section"] = "body-99"
    dangling = check_fact_check_report(
        chain["fact_check_report"], chain["evidence_ledger"], chain["script"]
    )
    assert [d.value for d in dangling] == ["body-99"]


# --- asset manifest vs scene plan ------------------------------------------


def test_asset_attached_to_an_unknown_scene_is_caught(chain: dict) -> None:
    chain["asset_manifest"]["assets"][0]["scene_id"] = "scene-99"
    dangling = check_asset_manifest(chain["asset_manifest"], chain["scene_plan"])
    assert any(d.value == "scene-99" and d.kind == "scene_id" for d in dangling)


def test_asset_without_license_or_provenance_is_caught(chain: dict) -> None:
    """Master Plan: license and provenance are mandatory per media file."""

    manifest = chain["asset_manifest"]
    manifest["assets"][0].pop("license")
    manifest["assets"][0].pop("original_url")
    manifest["assets"][0].pop("provider")
    dangling = check_asset_manifest(manifest, chain["scene_plan"])
    kinds = {d.field.split(".")[-1] for d in dangling if d.kind == "provenance"}
    assert kinds == {"license", "original_url", "provider"}


# --- alignment report vs scene plan + manifest -----------------------------


def test_alignment_verdict_for_an_unknown_scene_is_caught(chain: dict) -> None:
    chain["alignment_report"]["scenes"][0]["scene_id"] = "scene-404"
    dangling = check_alignment_report(
        chain["alignment_report"], chain["scene_plan"], chain["asset_manifest"]
    )
    assert any(d.value == "scene-404" for d in dangling)


def test_alignment_picking_an_unknown_asset_is_caught(chain: dict) -> None:
    chain["alignment_report"]["scenes"][0]["picked_asset_id"] = "asset-ghost"
    dangling = check_alignment_report(
        chain["alignment_report"], chain["scene_plan"], chain["asset_manifest"]
    )
    assert [d.value for d in dangling] == ["asset-ghost"]


# --- publish package vs manifest + qa --------------------------------------


def test_publish_crediting_an_unknown_asset_is_caught(chain: dict) -> None:
    chain["publish_package"]["sources_credits"][0]["asset_id"] = "asset-missing"
    dangling = check_publish_package(
        chain["publish_package"], chain["asset_manifest"], chain["qa_report"]
    )
    assert [d.value for d in dangling] == ["asset-missing"]


def test_publishing_after_a_failed_qa_is_caught(chain: dict) -> None:
    chain["qa_report"]["status"] = "fail"
    dangling = check_publish_package(
        chain["publish_package"], chain["asset_manifest"], chain["qa_report"]
    )
    assert any(d.kind == "qa_status_must_be_pass" for d in dangling)
    with pytest.raises(DanglingReferenceError):
        assert_resolved(chain)


def test_blocked_qa_also_blocks_publish(chain: dict) -> None:
    chain["qa_report"]["status"] = "blocked"
    dangling = check_publish_package(
        chain["publish_package"], chain["asset_manifest"], chain["qa_report"]
    )
    assert any(d.kind == "qa_status_must_be_pass" for d in dangling)


# --- reporting -------------------------------------------------------------


def test_summary_counts_by_kind_and_stage(chain: dict) -> None:
    chain["script"]["sections"][0]["evidence_ids"].append("EV-ghost")
    chain["asset_manifest"]["assets"][0]["scene_id"] = "scene-99"
    report = summarize(resolve_all(chain))
    assert report["dangling_count"] == 2
    assert report["resolved"] is False
    assert report["by_kind"] == {"evidence_id": 1, "scene_id": 1}
    assert set(report["by_stage"]) == {"script", "footage"}


def test_resolve_all_ignores_artifacts_that_are_absent(chain: dict) -> None:
    """A missing artifact is an ordering problem, not a dangling reference."""

    partial = {"research_brief": chain["research_brief"]}
    assert resolve_all(partial) == []


def test_assert_resolved_lists_every_offender(chain: dict) -> None:
    chain["script"]["sections"][1]["evidence_ids"].append("EV-ghost-2")
    with pytest.raises(DanglingReferenceError) as excinfo:
        assert_resolved(chain)
    message = str(excinfo.value)
    assert "EV-ghost-2" in message
    assert "evidence_ledger" in message


def test_a_deep_copied_chain_is_independent(chain: dict) -> None:
    """Guards against a resolver mutating the artifacts it checks."""

    before = copy.deepcopy(chain)
    resolve_all(chain)
    assert chain == before
