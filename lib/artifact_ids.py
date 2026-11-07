"""Cross-artifact ID resolution for the business-documentary pipeline.

Master Plan section 4 ("Контракты артефактов"):

    Каждая ссылка из следующего этапа должна разрешаться к существующему
    артефакту. Любой фальшивый/неизвестный source_id, evidence_id,
    scene_id или asset_id должен вызывать отказ схемы/этапа.

JSON Schema cannot express "this ID exists in another artifact", so the
check lives here. Every reference a downstream artifact makes is resolved
against the artifact that defines it, and anything that does not resolve
is reported with the stage, artifact, field and offending value.

Nothing here inspects networks or costs — it is pure data validation, so
it is safe to run at any checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

EVIDENCE_PATTERN_PREFIX = "EV-"
SOURCE_PATTERN_PREFIX = "SRC-"
SCENE_PREFIX = "SCN-"
ASSET_PREFIX = "AST-"
CLAIM_PREFIX = "CLM-"


class DanglingReferenceError(ValueError):
    """Raised when a downstream artifact references an ID that does not exist."""


@dataclass(frozen=True)
class DanglingReference:
    """One unresolved reference, described precisely enough to fix it."""

    stage: str
    artifact: str
    field: str
    value: str
    kind: str
    defined_in: str

    def as_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "artifact": self.artifact,
            "field": self.field,
            "value": self.value,
            "kind": self.kind,
            "defined_in": self.defined_in,
        }

    def __str__(self) -> str:  # pragma: no cover - presentation only
        return (
            f"{self.stage}: {self.artifact}.{self.field} references unknown "
            f"{self.kind} {self.value!r} (defined in {self.defined_in})"
        )


def _as_sequence(value: Any) -> list[str]:
    """Normalize a field that may be a list, a tuple, or a single string."""

    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v]
    return [str(value)]


def _entries(artifact: Optional[Mapping[str, Any]], key: str) -> list[Mapping[str, Any]]:
    if not isinstance(artifact, Mapping):
        return []
    raw = artifact.get(key)
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [entry for entry in raw if isinstance(entry, Mapping)]
    return []


# ---------------------------------------------------------------------------
# ID collectors — read the defining artifact, return the set of live IDs
# ---------------------------------------------------------------------------


def evidence_ids(evidence_ledger: Mapping[str, Any]) -> set[str]:
    """IDs defined by the evidence ledger (stage 3)."""

    return {
        str(entry["evidence_id"])
        for entry in _entries(evidence_ledger, "entries")
        if entry.get("evidence_id")
    }


def source_ids(research_brief: Mapping[str, Any]) -> set[str]:
    """Source IDs defined by the research brief (stage 2).

    Looks in the usual places: ``metadata.sources[]`` and a top-level
    ``sources[]``. Both are produced by existing research skills.
    """

    found: set[str] = set()
    for container in (research_brief, _metadata(research_brief)):
        for entry in _entries(container, "sources"):
            source_id = entry.get("source_id") or entry.get("id")
            if source_id:
                found.add(str(source_id))
    return found


def claim_ids(fact_check_report: Mapping[str, Any]) -> set[str]:
    """Claim IDs defined by the fact-check report (stage 5)."""

    return {
        str(entry["claim_id"])
        for entry in _entries(fact_check_report, "claims")
        if entry.get("claim_id")
    }


def scene_ids(scene_plan: Mapping[str, Any]) -> set[str]:
    """Scene IDs defined by the scene plan (stage 6)."""

    found: set[str] = set()
    for container in (scene_plan, _metadata(scene_plan)):
        for entry in _entries(container, "scenes"):
            scene_id = entry.get("scene_id") or entry.get("id")
            if scene_id:
                found.add(str(scene_id))
    return found


def asset_ids(asset_manifest: Mapping[str, Any]) -> set[str]:
    """Asset IDs defined by the asset manifest (stage 8)."""

    return {
        str(entry["id"] or entry["asset_id"])
        for entry in _entries(asset_manifest, "assets")
        if entry.get("id") or entry.get("asset_id")
    }


def _metadata(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(artifact, Mapping):
        return {}
    meta = artifact.get("metadata")
    return meta if isinstance(meta, Mapping) else {}


# ---------------------------------------------------------------------------
# Reference checks — resolve a downstream artifact against its definitions
# ---------------------------------------------------------------------------


def check_evidence_ledger(
    evidence_ledger: Mapping[str, Any],
    research_brief: Mapping[str, Any],
    *,
    stage: str = "evidence",
) -> list[DanglingReference]:
    """Every ledger entry must cite a source the research brief defines."""

    known_sources = source_ids(research_brief)
    dangling: list[DanglingReference] = []

    for index, entry in enumerate(_entries(evidence_ledger, "entries")):
        field_name = f"entries[{index}].source_id"
        source_id = entry.get("source_id")
        if not source_id:
            dangling.append(
                DanglingReference(
                    stage, "evidence_ledger", field_name, "", "source_id", "research_brief"
                )
            )
            continue
        if known_sources and str(source_id) not in known_sources:
            dangling.append(
                DanglingReference(
                    stage,
                    "evidence_ledger",
                    field_name,
                    str(source_id),
                    "source_id",
                    "research_brief",
                )
            )
    return dangling


def check_script_claims(
    script: Mapping[str, Any],
    evidence_ledger: Mapping[str, Any],
    *,
    stage: str = "script",
) -> list[DanglingReference]:
    """Every evidence ID the script cites must exist in the ledger.

    Evidence IDs are accepted at the section level (``evidence_ids``) and
    inside per-line claims (``claims[].evidence_ids``), because the
    script schema already allows both shapes.
    """

    known = evidence_ids(evidence_ledger)
    dangling: list[DanglingReference] = []

    for index, section in enumerate(_entries(script, "sections")):
        refs = _as_sequence(section.get("evidence_ids"))
        for ref in refs:
            if ref not in known:
                dangling.append(
                    DanglingReference(
                        stage,
                        "script",
                        f"sections[{index}].evidence_ids",
                        ref,
                        "evidence_id",
                        "evidence_ledger",
                    )
                )
        for claim_index, claim in enumerate(_entries(section, "claims")):
            for ref in _as_sequence(claim.get("evidence_ids")):
                if ref not in known:
                    dangling.append(
                        DanglingReference(
                            stage,
                            "script",
                            f"sections[{index}].claims[{claim_index}].evidence_ids",
                            ref,
                            "evidence_id",
                            "evidence_ledger",
                        )
                    )
    return dangling


def check_fact_check_report(
    fact_check_report: Mapping[str, Any],
    evidence_ledger: Mapping[str, Any],
    script: Mapping[str, Any],
    *,
    stage: str = "fact_check",
) -> list[DanglingReference]:
    """Fact-check evidence IDs must resolve, and every script section must
    be covered by a verdict."""

    known_evidence = evidence_ids(evidence_ledger)
    script_sections = {
        str(section.get("section_id") or section.get("id") or section.get("title"))
        for section in _entries(script, "sections")
        if section.get("section_id") or section.get("id") or section.get("title")
    }
    dangling: list[DanglingReference] = []

    for index, claim in enumerate(_entries(fact_check_report, "claims")):
        for ref in _as_sequence(claim.get("evidence_ids")):
            if ref not in known_evidence:
                dangling.append(
                    DanglingReference(
                        stage,
                        "fact_check_report",
                        f"claims[{index}].evidence_ids",
                        ref,
                        "evidence_id",
                        "evidence_ledger",
                    )
                )
        section = claim.get("script_section")
        if section and script_sections and str(section) not in script_sections:
            dangling.append(
                DanglingReference(
                    stage,
                    "fact_check_report",
                    f"claims[{index}].script_section",
                    str(section),
                    "script_section",
                    "script",
                )
            )
    return dangling


def check_asset_manifest(
    asset_manifest: Mapping[str, Any],
    scene_plan: Mapping[str, Any],
    *,
    stage: str = "footage",
) -> list[DanglingReference]:
    """Every asset must be attached to a scene the scene plan defines,
    and must carry the provenance the license rules require."""

    known_scenes = scene_ids(scene_plan)
    dangling: list[DanglingReference] = []

    for index, asset in enumerate(_entries(asset_manifest, "assets")):
        scene_id = asset.get("scene_id")
        if not scene_id:
            dangling.append(
                DanglingReference(
                    stage, "asset_manifest", f"assets[{index}].scene_id", "", "scene_id", "scene_plan"
                )
            )
        elif known_scenes and str(scene_id) not in known_scenes:
            dangling.append(
                DanglingReference(
                    stage,
                    "asset_manifest",
                    f"assets[{index}].scene_id",
                    str(scene_id),
                    "scene_id",
                    "scene_plan",
                )
            )
        for field in ("provider", "original_url", "license"):
            if not asset.get(field):
                dangling.append(
                    DanglingReference(
                        stage,
                        "asset_manifest",
                        f"assets[{index}].{field}",
                        "",
                        "provenance",
                        "asset_manifest",
                    )
                )
    return dangling


def check_alignment_report(
    alignment_report: Mapping[str, Any],
    scene_plan: Mapping[str, Any],
    asset_manifest: Mapping[str, Any],
    *,
    stage: str = "editorial",
) -> list[DanglingReference]:
    """Alignment verdicts must point at real scenes and real assets."""

    known_scenes = scene_ids(scene_plan)
    known_assets = asset_ids(asset_manifest)
    dangling: list[DanglingReference] = []

    for index, scene in enumerate(_entries(alignment_report, "scenes")):
        scene_id = scene.get("scene_id")
        if not scene_id or (known_scenes and str(scene_id) not in known_scenes):
            dangling.append(
                DanglingReference(
                    stage,
                    "alignment_report",
                    f"scenes[{index}].scene_id",
                    str(scene_id or ""),
                    "scene_id",
                    "scene_plan",
                )
            )
        asset_id = scene.get("picked_asset_id")
        if asset_id and str(asset_id) not in known_assets:
            dangling.append(
                DanglingReference(
                    stage,
                    "alignment_report",
                    f"scenes[{index}].picked_asset_id",
                    str(asset_id),
                    "asset_id",
                    "asset_manifest",
                )
            )
    return dangling


def check_publish_package(
    publish_package: Mapping[str, Any],
    asset_manifest: Mapping[str, Any],
    qa_report: Mapping[str, Any],
    *,
    stage: str = "publish",
) -> list[DanglingReference]:
    """Credits must match the manifest, and a failed QA cannot publish."""

    known_assets = asset_ids(asset_manifest)
    dangling: list[DanglingReference] = []

    for index, credit in enumerate(_entries(publish_package, "sources_credits")):
        asset_id = credit.get("asset_id")
        if asset_id and str(asset_id) not in known_assets:
            dangling.append(
                DanglingReference(
                    stage,
                    "publish_package",
                    f"sources_credits[{index}].asset_id",
                    str(asset_id),
                    "asset_id",
                    "asset_manifest",
                )
            )

    qa_status = (_metadata(qa_report).get("status") or qa_report.get("status") or "").lower()
    if qa_status in {"fail", "blocked"}:
        dangling.append(
            DanglingReference(
                stage,
                "publish_package",
                "qa_ref.status",
                qa_status,
                "qa_status_must_be_pass",
                "qa_report",
            )
        )
    return dangling


def resolve_all(artifacts: Mapping[str, Mapping[str, Any]]) -> list[DanglingReference]:
    """Run every cross-artifact check that the available artifacts allow.

    Missing artifacts are skipped rather than guessed at: an absent ledger
    is a pipeline-order problem for the orchestrator, not a dangling
    reference.
    """

    research_brief = artifacts.get("research_brief", {})
    evidence_ledger = artifacts.get("evidence_ledger", {})
    script = artifacts.get("script", {})
    fact_check = artifacts.get("fact_check_report", {})
    scene_plan = artifacts.get("scene_plan", {})
    asset_manifest = artifacts.get("asset_manifest", {})
    alignment = artifacts.get("alignment_report", {})
    publish = artifacts.get("publish_package", {})
    qa = artifacts.get("qa_report", {})

    dangling: list[DanglingReference] = []

    if evidence_ledger and research_brief:
        dangling += check_evidence_ledger(evidence_ledger, research_brief)
    if script and evidence_ledger:
        dangling += check_script_claims(script, evidence_ledger)
    if fact_check and evidence_ledger and script:
        dangling += check_fact_check_report(fact_check, evidence_ledger, script)
    if asset_manifest and scene_plan:
        dangling += check_asset_manifest(asset_manifest, scene_plan)
    if alignment and scene_plan and asset_manifest:
        dangling += check_alignment_report(alignment, scene_plan, asset_manifest)
    if publish and asset_manifest:
        dangling += check_publish_package(publish, asset_manifest, qa)
    return dangling


def assert_resolved(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    """Raise :class:`DanglingReferenceError` listing every unresolved ID."""

    dangling = resolve_all(artifacts)
    if dangling:
        listed = "; ".join(str(ref) for ref in dangling)
        raise DanglingReferenceError(
            f"{len(dangling)} unresolved reference(s): {listed}"
        )


def summarize(dangling: Iterable[DanglingReference]) -> dict[str, Any]:
    """Aggregate view for a checkpoint or QA artifact."""

    refs = list(dangling)
    return {
        "dangling_count": len(refs),
        "resolved": not refs,
        "by_kind": _count_by(refs, "kind"),
        "by_stage": _count_by(refs, "stage"),
        "references": [ref.as_dict() for ref in refs],
    }


def _count_by(refs: list[DanglingReference], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ref in refs:
        key = getattr(ref, attribute)
        counts[key] = counts.get(key, 0) + 1
    return counts
