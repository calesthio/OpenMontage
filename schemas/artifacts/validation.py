"""Semantic validation for versioned OpenMontage artifacts.

JSON Schema validates shape. This module validates relationships that require
context across fields or artifacts: time ranges, unique identities, evidence
references, and handoff lineage.
"""

from __future__ import annotations

import jsonschema
import math
from numbers import Real
import re
from typing import Any


class ArtifactSemanticValidationError(ValueError):
    """Raised when a schema-valid artifact violates semantic invariants."""


_PROFILE_REF = re.compile(
    r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@[0-9]+(?:\.[0-9]+)*$"
)
_ASPECTS = {
    "subject",
    "subject_motion",
    "scene",
    "spatial_framing",
    "camera",
}


def _fail(name: str, message: str) -> None:
    raise ArtifactSemanticValidationError(f"{name}: {message}")


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _check_finite_values(name: str, value: Any, path: str = "$") -> None:
    """Reject NaN and infinity anywhere in a v1.1 JSON-compatible value."""
    if isinstance(value, float) and not math.isfinite(value):
        _fail(name, f"{path} must be finite")
    if isinstance(value, dict):
        for key, child in value.items():
            _check_finite_values(name, child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_finite_values(name, child, f"{path}[{index}]")


_SENTINEL_TEXT = frozenset({
    "unknown",
    "unavailable",
    "not available",
    "not analyzed",
    "not yet analyzed",
    "pending",
    "tbd",
    "todo",
    "placeholder",
    "not provided",
    "not specified",
    "redacted",
    "not known",
    "no data",
    "n/a",
    "n a",
    "na",
    "none",
})


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _meaningful_text(value: Any) -> bool:
    if not _non_blank(value):
        return False
    normalized = re.sub(r"[\W_]+", " ", value.strip().casefold()).strip()
    return bool(normalized) and normalized not in _SENTINEL_TEXT


_SCHEME_ONLY = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:/*$")


def _usable_locator(value: Any) -> bool:
    if not _meaningful_text(value):
        return False
    normalized = value.strip().casefold()
    return not normalized.startswith(("unavailable://", "migration://")) and not _SCHEME_ONLY.fullmatch(normalized)


_STABLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _stable_id(value: Any) -> bool:
    return isinstance(value, str) and _meaningful_text(value) and bool(_STABLE_ID_PATTERN.fullmatch(value))


def _has_available_evidence(evidence: Any, kind: str) -> bool:
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if (
            item.get("kind") == kind
            and item.get("status") == "available"
            and _usable_locator(item.get("source_ref"))
        ):
            return True
    return False


def _check_range(
    name: str,
    start: Any,
    end: Any,
    label: str,
    upper: float | None = None,
    *,
    allow_point: bool = True,
) -> None:
    if not _is_number(start) or not _is_number(end):
        _fail(name, f"{label} must have numeric start and end")
    if start < 0 or end < 0:
        _fail(name, f"{label} cannot be negative")
    if end < start or (not allow_point and end == start):
        operator = "<=" if allow_point else "<"
        _fail(name, f"{label} requires start {operator} end")
    if upper is not None and end > upper + 0.001:
        _fail(name, f"{label} ends at {end}, beyond duration {upper}")


def _unique(name: str, values: list[Any], label: str) -> set[Any]:
    blank_values = [value for value in values if isinstance(value, str) and not value.strip()]
    if blank_values:
        _fail(name, f"{label} must contain non-empty values")
    invalid_values = [
        value for value in values
        if isinstance(value, str) and not _STABLE_ID_PATTERN.fullmatch(value)
    ]
    if invalid_values:
        _fail(name, f"{label} must use stable ID characters: {invalid_values}")
    if len(values) != len(set(values)):
        duplicates = sorted({value for value in values if values.count(value) > 1}, key=str)
        _fail(name, f"duplicate {label}: {duplicates}")
    return set(values)


def _refs(name: str, refs: Any, label: str = "evidence_refs") -> list[str]:
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        _fail(name, f"{label} must be a list of non-empty strings")
    if len(refs) != len(set(refs)):
        _fail(name, f"duplicate values in {label}")
    return refs


def _analysis_refs(name: str, refs: Any, label: str) -> list[str]:
    values = _refs(name, refs, label)
    invalid = [value for value in values if not _stable_id(value)]
    if invalid:
        _fail(name, f"{label} must contain stable IDs: {invalid}")
    return values


def _evidence_refs(name: str, refs: Any, label: str = "evidence_refs") -> list[str]:
    values = _refs(name, refs, label)
    invalid = []
    for value in values:
        parts = value.split("#")
        if len(parts) not in {1, 2} or any(not _stable_id(part) for part in parts):
            invalid.append(value)
    if invalid:
        _fail(name, f"{label} must contain stable or qualified evidence IDs: {invalid}")
    return values


def _profile_refs(name: str, data: dict[str, Any], field: str = "narrative_profile_refs") -> None:
    refs = data.get(field, [])
    if not isinstance(refs, list):
        _fail(name, f"{field} must be a list")
    if len(refs) != len(set(refs)):
        _fail(name, f"duplicate values in {field}")
    for ref in refs:
        if not isinstance(ref, str) or not _PROFILE_REF.fullmatch(ref):
            _fail(name, f"invalid {field} value {ref!r}; expected name@version")


def _validate_video_analysis(data: dict[str, Any]) -> None:
    name = "video_analysis_brief@1.1"
    analysis_id = data.get("analysis_id")
    if not _stable_id(analysis_id):
        _fail(name, "analysis_id must be non-empty and cannot contain '#'")

    source = data["source"]
    duration = source.get("duration_seconds")
    if not _is_number(duration) or duration < 0:
        _fail(name, "source.duration_seconds must be a non-negative number")
    fingerprint = source.get("fingerprint", {})
    if not isinstance(fingerprint, dict) or not _usable_locator(fingerprint.get("value")):
        _fail(name, "source.fingerprint.value is required")
    for field in ("url", "local_path"):
        if field in source and not _usable_locator(source[field]):
            _fail(name, f"source.{field} must be a usable locator")
    if not _meaningful_text(source.get("retention_policy")):
        _fail(name, "source.retention_policy must be non-empty")

    run = data["analysis_run"]
    if not _stable_id(run.get("id")):
        _fail(name, "analysis_run.id must be non-empty and cannot contain '#'")
    completed = run.get("steps_completed", [])
    failed = run.get("steps_failed", [])
    status = run.get("status")
    transcript_for_status = data.get("narration_transcript", {})
    transcript_segments_for_status = transcript_for_status.get("segments", [])
    transcript_has_content = bool(
        str(transcript_for_status.get("full_text", "")).strip()
        or any(
            isinstance(segment, dict) and str(segment.get("text", "")).strip()
            for segment in transcript_segments_for_status
        )
    )
    if status == "complete" and failed:
        _fail(name, "analysis_run.status=complete cannot contain failed steps")
    if status == "complete" and run.get("depth") == "transcript_only":
        if not any(step.startswith("transcript_") for step in completed) or not transcript_has_content:
            _fail(name, "complete transcript_only analysis requires a non-empty transcript step")
    if status == "complete" and run.get("depth") in {"standard", "deep"}:
        keyframe_steps = {"keyframes", "keyframes_uniform"}
        scenes_for_status = data.get("structure_analysis", {}).get("scenes", [])
        keyframes_for_status = data.get("keyframes", [])
        content = data.get("content_analysis", {})
        topics = content.get("topics", []) if isinstance(content, dict) else []
        locator_field = "local_path" if source.get("type") == "local_file" else "url"
        if (
            "metadata" not in completed
            or "scene_detect" not in completed
            or not keyframe_steps.intersection(completed)
            or not scenes_for_status
            or not keyframes_for_status
            or duration <= 0
            or not _usable_locator(source.get(locator_field))
            or not _usable_locator(fingerprint.get("value"))
            or not isinstance(content, dict)
            or not _meaningful_text(content.get("summary"))
            or not any(_meaningful_text(topic) for topic in topics)
            or not _meaningful_text(content.get("target_audience"))
            or not _has_available_evidence(data.get("evidence"), "scene_detection")
            or not _has_available_evidence(data.get("evidence"), "keyframe")
        ):
            _fail(
                name,
                "complete standard/deep analysis requires a source locator, positive duration, "
                "non-empty fingerprint, content metadata, and available scene/keyframe evidence",
            )
        blank_scene_fields = [
            index for index, scene in enumerate(scenes_for_status)
            if not _meaningful_text(scene.get("description", ""))
        ]
        blank_keyframe_fields = [
            index for index, frame in enumerate(keyframes_for_status)
            if (
                not _usable_locator(frame.get("path"))
                or not _meaningful_text(frame.get("description", ""))
            )
        ]
        if blank_scene_fields or blank_keyframe_fields:
            _fail(
                name,
                f"complete analysis requires described scenes and keyframes; "
                f"blank scenes={blank_scene_fields}, blank keyframes={blank_keyframe_fields}",
            )
    if status == "complete" and data.get("structure_analysis", {}).get("scenes"):
        if "visual_enrichment" not in completed:
            _fail(name, "analysis_run.status=complete requires visual_enrichment when scenes exist")
    if status == "failed" and completed:
        _fail(name, "analysis_run.status=failed cannot contain completed steps")

    evidence = data["evidence"]
    evidence_ids = _unique(name, [item["id"] for item in evidence], "evidence IDs")
    evidence_by_id = {item["id"]: item for item in evidence}
    for index, item in enumerate(evidence):
        source_ref = item["source_ref"]
        if not _meaningful_text(source_ref):
            _fail(name, f"evidence[{index}].source_ref cannot be blank")
        if item["status"] == "available" and not _usable_locator(source_ref):
            _fail(name, f"evidence[{index}].source_ref is not a usable available locator")
        has_start = "start_seconds" in item
        has_end = "end_seconds" in item
        if has_start != has_end:
            _fail(name, f"evidence[{index}] must include both start_seconds and end_seconds")
        if has_start:
            _check_range(
                name,
                item["start_seconds"],
                item["end_seconds"],
                f"evidence[{index}] time range",
                float(duration) if duration > 0 else None,
            )

    structure = data["structure_analysis"]
    scenes = structure["scenes"]
    if structure["total_scenes"] != len(scenes):
        _fail(name, "structure_analysis.total_scenes must equal scenes length")
    scene_indices = _unique(name, [scene["scene_index"] for scene in scenes], "scene indices")
    for index, item in enumerate(evidence):
        scene_index = item.get("scene_index")
        if scene_index is not None and scene_index not in scene_indices:
            _fail(name, f"evidence[{index}] refers to unknown scene {scene_index}")
    for index, scene in enumerate(scenes):
        _check_range(
            name,
            scene["start_time"],
            scene["end_time"],
            f"scene[{index}] time range",
            float(duration) if duration > 0 else None,
            allow_point=False,
        )
        observation_ids = scene.get("observation_ids", [])
        _analysis_refs(name, observation_ids, "observation_ids")

    observations = data["five_aspect_observations"]
    observation_ids = _unique(name, [item["id"] for item in observations], "observation IDs")
    coverage: set[tuple[int, str]] = set()
    for index, item in enumerate(observations):
        scene_index = item["scene_index"]
        aspect = item["aspect"]
        if scene_indices and scene_index not in scene_indices:
            _fail(name, f"observation[{index}] refers to unknown scene {scene_index}")
        if aspect not in _ASPECTS:
            _fail(name, f"observation[{index}] has unknown aspect {aspect!r}")
        if not _non_blank(item["value"]):
            _fail(name, f"observation[{index}] value cannot be blank")
        if item["status"] in {"observed", "inferred"} and not _meaningful_text(item["value"]):
            _fail(name, f"observation[{index}] {item['status']} value must be meaningful")
        key = (scene_index, aspect)
        if key in coverage:
            _fail(name, f"duplicate five-aspect observation for scene {scene_index}, {aspect}")
        coverage.add(key)
        refs = _evidence_refs(name, item["evidence_refs"])
        missing_refs = set(refs) - evidence_ids
        if missing_refs:
            _fail(name, f"observation[{index}] has unknown evidence refs {sorted(missing_refs)}")
        unavailable_refs = [
            ref for ref in refs if evidence_by_id[ref]["status"] != "available"
        ]
        if item["status"] in {"observed", "inferred"} and unavailable_refs:
            _fail(name, f"observation[{index}] cites unavailable evidence {unavailable_refs}")
        if item["status"] in {"observed", "inferred"} and not refs:
            _fail(name, f"observation[{index}] status {item['status']!r} requires evidence_refs")
        if item.get("status") in {"unknown", "not_applicable"} and refs:
            # References are allowed for unknown values only when they explain
            # why the aspect could not be established; keep them valid.
            pass

    expected = {(scene_index, aspect) for scene_index in scene_indices for aspect in _ASPECTS}
    missing = expected - coverage
    if missing:
        _fail(name, f"missing five-aspect observations: {sorted(missing)}")
    if status == "complete" and scene_indices:
        unresolved = [
            item["id"]
            for item in observations
            if item["status"] not in {"observed", "inferred", "not_applicable"}
        ]
        if unresolved:
            _fail(name, f"complete analysis has unresolved observations {unresolved}")
    if observation_ids:
        for scene in scenes:
            declared = set(scene.get("observation_ids", []))
            expected_ids = {
                item["id"] for item in observations if item["scene_index"] == scene["scene_index"]
            }
            if declared and declared != expected_ids:
                _fail(name, f"scene {scene['scene_index']} observation_ids do not match observations")

    assertions = data["assertions"]
    _unique(name, [item["id"] for item in assertions], "assertion IDs")
    for index, item in enumerate(assertions):
        refs = _evidence_refs(name, item["evidence_refs"])
        if item.get("scene_index") is not None and item["scene_index"] not in scene_indices:
            _fail(name, f"assertion[{index}] refers to unknown scene {item['scene_index']}")
        missing_refs = set(refs) - evidence_ids
        if missing_refs:
            _fail(name, f"assertion[{index}] has unknown evidence refs {sorted(missing_refs)}")
        unavailable_refs = [
            ref for ref in refs if evidence_by_id[ref]["status"] != "available"
        ]
        if unavailable_refs:
            _fail(name, f"assertion[{index}] cites unavailable evidence {unavailable_refs}")
        if not refs:
            _fail(name, f"assertion[{index}] must cite evidence")
        time_range = item.get("time_range")
        if time_range is not None:
            _check_range(
                name,
                time_range["start_seconds"],
                time_range["end_seconds"],
                f"assertion[{index}] time range",
                float(duration) if duration > 0 else None,
            )

    transcript = data.get("narration_transcript", {})
    segments = transcript.get("segments", [])
    _unique(name, [segment["id"] for segment in segments], "transcript segment IDs")
    for index, segment in enumerate(segments):
        _check_range(
            name,
            segment["start"],
            segment["end"],
            f"transcript segment[{index}] time range",
            float(duration) if duration > 0 else None,
            allow_point=False,
        )

    transcript_evidence = [
        item for item in evidence if item.get("kind") == "transcript_segment"
    ]
    if segments:
        def matches_transcript(item: dict[str, Any], segment: dict[str, Any]) -> bool:
            start = item.get("start_seconds")
            end = item.get("end_seconds")
            return (
                item.get("id") == f"ev-transcript-{segment['id']}"
                and _is_number(start)
                and _is_number(end)
                and abs(float(start) - float(segment["start"])) <= 0.001
                and abs(float(end) - float(segment["end"])) <= 0.001
                and str(item.get("excerpt", "")).strip() == str(segment["text"]).strip()
            )

        unbound_segments = [
            index
            for index, segment in enumerate(segments)
            if not any(matches_transcript(item, segment) for item in transcript_evidence)
        ]
        unbound_evidence = [
            index
            for index, item in enumerate(transcript_evidence)
            if not any(matches_transcript(item, segment) for segment in segments)
        ]
        if unbound_segments or unbound_evidence:
            _fail(
                name,
                "transcript segments require matching transcript_segment evidence; "
                f"unbound_segments={unbound_segments}, unbound_evidence={unbound_evidence}",
            )
    elif transcript_evidence:
        _fail(name, "transcript_segment evidence requires transcript segments")

    keyframes = data.get("keyframes", [])
    _unique(name, [frame["id"] for frame in keyframes], "keyframe IDs")
    for index, frame in enumerate(keyframes):
        timestamp = frame["timestamp"]
        if not _is_number(timestamp) or timestamp < 0:
            _fail(name, f"keyframe[{index}] timestamp must be non-negative")
        if duration > 0 and timestamp > duration + 0.001:
            _fail(name, f"keyframe[{index}] timestamp exceeds source duration")
        if scene_indices and frame["scene_index"] not in scene_indices:
            _fail(name, f"keyframe[{index}] refers to unknown scene {frame['scene_index']}")

    if status == "complete" and run.get("depth") in {"standard", "deep"}:
        available_scene_evidence = [
            item
            for item in evidence
            if item.get("kind") == "scene_detection"
            and item.get("status") == "available"
            and _usable_locator(item.get("source_ref"))
        ]
        scene_evidence_indices = {item.get("scene_index") for item in available_scene_evidence}
        if scene_evidence_indices != scene_indices:
            _fail(
                name,
                "complete analysis scene evidence must resolve every declared scene; "
                f"missing={sorted(scene_indices - scene_evidence_indices, key=str)}",
            )

        def matches_scene(item: dict[str, Any], scene: dict[str, Any]) -> bool:
            start = item.get("start_seconds")
            end = item.get("end_seconds")
            return (
                item.get("scene_index") == scene["scene_index"]
                and _is_number(start)
                and _is_number(end)
                and abs(float(start) - float(scene["start_time"])) <= 0.001
                and abs(float(end) - float(scene["end_time"])) <= 0.001
            )

        unbound_scenes = [
            index
            for index, scene in enumerate(scenes)
            if not any(matches_scene(item, scene) for item in available_scene_evidence)
        ]
        unbound_scene_evidence = [
            index
            for index, item in enumerate(available_scene_evidence)
            if not any(matches_scene(item, scene) for scene in scenes)
        ]
        if unbound_scenes or unbound_scene_evidence:
            _fail(
                name,
                "complete analysis scene evidence must match declared scene ranges; "
                f"unbound_scenes={unbound_scenes}, unbound_evidence={unbound_scene_evidence}",
            )

        available_keyframe_evidence = [
            item
            for item in evidence
            if item.get("kind") == "keyframe"
            and item.get("status") == "available"
            and _usable_locator(item.get("source_ref"))
        ]

        def matches_keyframe(item: dict[str, Any], frame: dict[str, Any]) -> bool:
            start = item.get("start_seconds")
            end = item.get("end_seconds")
            return (
                item.get("scene_index") == frame["scene_index"]
                and _is_number(start)
                and _is_number(end)
                and abs(float(start) - float(frame["timestamp"])) <= 0.001
                and abs(float(end) - float(frame["timestamp"])) <= 0.001
                and item.get("source_ref", "").strip() == str(frame.get("path", "")).strip()
            )

        unbound_keyframes = [
            index
            for index, frame in enumerate(keyframes)
            if not any(matches_keyframe(item, frame) for item in available_keyframe_evidence)
        ]
        unbound_evidence = [
            index
            for index, item in enumerate(available_keyframe_evidence)
            if not any(matches_keyframe(item, frame) for frame in keyframes)
        ]
        if unbound_keyframes or unbound_evidence:
            _fail(
                name,
                "complete analysis keyframe evidence must resolve declared keyframes; "
                f"unbound_keyframes={unbound_keyframes}, unbound_evidence={unbound_evidence}",
            )

    all_transfer_ids: list[str] = []
    guidance = data["replication_guidance"]
    for field in (
        "key_elements_to_replicate",
        "elements_requiring_custom_work",
        "creative_differentiation_seeds",
        "preserve",
        "change",
        "avoid",
    ):
        for index, item in enumerate(guidance.get(field, [])):
            all_transfer_ids.append(item["id"])
            refs = _evidence_refs(name, item["evidence_refs"])
            if not refs and item.get("provenance_status") != "unavailable":
                _fail(name, f"{field}[{index}] must cite evidence or declare unavailable provenance")
            if item.get("provenance_status") == "unavailable" and refs:
                _fail(name, f"{field}[{index}] cannot mix unavailable provenance with evidence refs")
            missing_refs = set(refs) - evidence_ids
            if missing_refs:
                _fail(name, f"{field}[{index}] has unknown evidence refs {sorted(missing_refs)}")
            unavailable_refs = [
                ref for ref in refs if evidence_by_id[ref]["status"] != "available"
            ]
            if unavailable_refs:
                _fail(name, f"{field}[{index}] cites unavailable evidence {unavailable_refs}")
    _unique(name, all_transfer_ids, "transfer guidance IDs")


def _validate_v11_bundle(data: dict[str, Any]) -> None:
    name = "video_analysis_bundle@1.1"
    if not _stable_id(data.get("bundle_id")):
        _fail(name, "bundle_id must be non-empty and cannot contain '#'")
    analyses = data["analyses"]
    _unique(name, [analysis.get("analysis_id") for analysis in analyses], "analysis IDs")
    if any(not isinstance(analysis, dict) or analysis.get("version") != "1.1" for analysis in analyses):
        _fail(name, "every bundle member must be a video_analysis_brief@1.1")

    from schemas.artifacts import load_schema

    member_schema = load_schema("video_analysis_brief", "1.1")
    for index, analysis in enumerate(analyses):
        try:
            jsonschema.validate(instance=analysis, schema=member_schema)
        except jsonschema.ValidationError as exc:
            _fail(
                name,
                f"analyses[{index}] must match video_analysis_brief@1.1 schema: {exc.message}",
            )
        _validate_video_analysis(analysis)


def _validate_v11_brief(data: dict[str, Any]) -> None:
    name = "brief@1.1"
    if data["target_duration_seconds"] <= 0:
        _fail(name, "target_duration_seconds must be positive")
    _profile_refs(name, data)
    refs = _analysis_refs(name, data.get("reference_analysis_refs", []), "reference_analysis_refs")
    if data.get("reference_driven") and not refs:
        _fail(name, "reference_driven briefs require reference_analysis_refs")


def _validate_v11_proposal(data: dict[str, Any]) -> None:
    name = "proposal_packet@1.1"
    _profile_refs(name, data)
    refs = _analysis_refs(name, data.get("reference_analysis_refs", []), "reference_analysis_refs")
    if data.get("reference_driven") and not refs:
        _fail(name, "reference_driven proposals require reference_analysis_refs")
    concepts = data["concept_options"]
    for index, concept in enumerate(concepts):
        if concept["target_duration_seconds"] <= 0:
            _fail(name, f"concept_options[{index}] target_duration_seconds must be positive")
    concept_ids = _unique(name, [concept["id"] for concept in concepts], "concept IDs")
    selected_id = data["selected_concept"]["concept_id"]
    if selected_id not in concept_ids:
        _fail(name, f"selected_concept.concept_id {selected_id!r} is not a concept option")
    reference_driven = bool(data.get("reference_analysis_refs"))
    for index, concept in enumerate(concepts):
        _profile_refs(name, concept)
        for field in ("reference_analysis_refs", "evidence_refs"):
            ref_validator = _analysis_refs if field == "reference_analysis_refs" else _evidence_refs
            ref_validator(name, concept.get(field, []), f"concept_options[{index}].{field}")
        if reference_driven:
            if not concept.get("reference_analysis_refs"):
                _fail(name, f"concept_options[{index}] must attribute its reference analysis")
            if not concept.get("evidence_refs"):
                _fail(name, f"reference-driven concept_options[{index}] must cite evidence")
            for field in ("preserve", "change", "avoid"):
                if field not in concept or not isinstance(concept[field], list):
                    _fail(name, f"reference-driven concept_options[{index}] must declare {field}")
    if reference_driven:
        selected = data["selected_concept"]
        if not selected.get("reference_analysis_refs"):
            _fail(name, "selected_concept must retain reference analysis attribution")
        selected_option = next(
            concept for concept in concepts if concept["id"] == selected["concept_id"]
        )
        selected_refs = set(
            _analysis_refs(
                name,
                selected.get("reference_analysis_refs", []),
                "selected_concept.reference_analysis_refs",
            )
        )
        option_refs = set(
            _analysis_refs(
                name,
                selected_option.get("reference_analysis_refs", []),
                "selected concept option.reference_analysis_refs",
            )
        )
        if not selected_refs.issubset(option_refs):
            _fail(name, "selected_concept references analyses outside its selected concept")


def _validate_v11_script(data: dict[str, Any]) -> None:
    name = "script@1.1"
    _profile_refs(name, data)
    refs = _analysis_refs(name, data.get("reference_analysis_refs", []), "reference_analysis_refs")
    duration = float(data["total_duration_seconds"])
    if duration <= 0:
        _fail(name, "total_duration_seconds must be positive")
    sections = data["sections"]
    ids = _unique(name, [section["id"] for section in sections], "section IDs")
    voice_performance = data.get("voice_performance", {})
    sample_section_id = (
        voice_performance.get("sample_section_id")
        if isinstance(voice_performance, dict)
        else None
    )
    if sample_section_id is not None:
        if not _stable_id(sample_section_id):
            _fail(name, "sample_section_id must be a stable section ID")
        if sample_section_id not in ids:
            _fail(name, f"sample_section_id {sample_section_id!r} is not a declared section")
    ordered = sorted(sections, key=lambda section: section["start_seconds"])
    previous_end = 0.0
    for index, section in enumerate(ordered):
        _check_range(
            name,
            section["start_seconds"],
            section["end_seconds"],
            f"section[{index}] time range",
            duration,
            allow_point=False,
        )
        if section["start_seconds"] < previous_end - 0.001:
            _fail(name, f"section[{index}] overlaps the previous section")
        previous_end = section["end_seconds"]
        if refs and "evidence_refs" not in section:
            _fail(name, f"reference-driven section[{index}] must declare evidence_refs")
        _evidence_refs(name, section.get("evidence_refs", []))
        _refs(name, section.get("source_refs", []), "source_refs")
    if not ids:
        _fail(name, "at least one section is required")


def _validate_v11_scene_plan(data: dict[str, Any]) -> None:
    name = "scene_plan@1.1"
    _profile_refs(name, data)
    refs = _analysis_refs(name, data.get("reference_analysis_refs", []), "reference_analysis_refs")
    scenes = data["scenes"]
    ids = _unique(name, [scene["id"] for scene in scenes], "scene IDs")
    duration = max((scene["end_seconds"] for scene in scenes), default=0.0)
    ordered = sorted(scenes, key=lambda scene: scene["start_seconds"])
    previous_end = 0.0
    for index, scene in enumerate(ordered):
        _check_range(
            name,
            scene["start_seconds"],
            scene["end_seconds"],
            f"scene[{index}] time range",
            duration,
            allow_point=False,
        )
        if scene["start_seconds"] < previous_end - 0.001:
            _fail(name, f"scene[{index}] overlaps the previous scene")
        previous_end = scene["end_seconds"]
        _analysis_refs(name, scene.get("script_section_ids", []), "script_section_ids")
        singular_script_ref = scene.get("script_section_id")
        if singular_script_ref is not None and not _stable_id(singular_script_ref):
            _fail(name, f"scene[{index}] script_section_id must be a stable section ID")
        if refs:
            for field in ("subject", "subject_motion", "scene", "spatial_framing", "camera"):
                if not str(scene.get(field, "")).strip():
                    _fail(name, f"reference-driven scene[{index}] field {field} cannot be blank")
        if refs and "evidence_refs" not in scene:
            _fail(name, f"reference-driven scene[{index}] must declare evidence_refs")
        _evidence_refs(name, scene.get("evidence_refs", []))
    if not ids:
        _fail(name, "at least one scene is required")


def validate_artifact_semantics(name: str, data: dict[str, Any]) -> None:
    """Validate cross-field invariants for the v1.1 artifact contracts."""
    if data.get("version") != "1.1":
        return
    _check_finite_values(name, data)
    validators = {
        "video_analysis_brief": _validate_video_analysis,
        "video_analysis_bundle": _validate_v11_bundle,
        "brief": _validate_v11_brief,
        "proposal_packet": _validate_v11_proposal,
        "script": _validate_v11_script,
        "scene_plan": _validate_v11_scene_plan,
    }
    validator = validators.get(name)
    if validator is not None:
        validator(data)


def _attached_analyses(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    """Return independently validated v1.1 analyses attached to a checkpoint."""
    analyses: list[dict[str, Any]] = []
    single = artifacts.get("video_analysis_brief")
    if isinstance(single, dict) and single.get("version") == "1.1":
        analyses.append(single)
    bundle = artifacts.get("video_analysis_bundle")
    if isinstance(bundle, dict) and bundle.get("version") == "1.1":
        members = bundle.get("analyses", [])
        if isinstance(members, list):
            analyses.extend(member for member in members if isinstance(member, dict))
    return analyses


def _handoff_evidence_ids(
    analyses: list[dict[str, Any]],
    *,
    all_analyses: list[dict[str, Any]] | None = None,
) -> set[str]:
    """Return locally unique IDs plus qualified IDs for selected sources.

    Local uniqueness is calculated across every attached analysis, not only
    the selected subset, so an unqualified ref cannot hide a duplicate in an
    unselected bundle member.
    """
    all_analyses = analyses if all_analyses is None else all_analyses
    global_counts: dict[str, int] = {}
    for analysis in all_analyses:
        for item in analysis.get("evidence", []):
            evidence_id = item["id"]
            global_counts[evidence_id] = global_counts.get(evidence_id, 0) + 1

    local: set[str] = set()
    qualified: set[str] = set()
    for analysis in analyses:
        analysis_id = analysis["analysis_id"]
        for item in analysis.get("evidence", []):
            evidence_id = item["id"]
            if global_counts[evidence_id] == 1:
                local.add(evidence_id)
            qualified.add(f"{analysis_id}#{evidence_id}")
    return local | qualified


def validate_artifact_handoffs(artifacts: dict[str, Any]) -> None:
    """Validate v1.1 references between artifacts in one checkpoint.

    A reference-driven v1.1 downstream artifact must carry the referenced
    analysis artifact or bundle in the same checkpoint. When a bundle contains
    repeated local evidence IDs, downstream refs must use ``analysis_id#id``.
    """
    analyses = _attached_analyses(artifacts)
    analysis_ids = {analysis["analysis_id"] for analysis in analyses}
    if len(analysis_ids) != len(analyses):
        _fail("handoff", "attached v1.1 analysis IDs must be unique")
    analysis_by_id = {analysis["analysis_id"]: analysis for analysis in analyses}

    def evidence_for(refs: set[str]) -> set[str]:
        selected = [analysis_by_id[ref] for ref in refs if ref in analysis_by_id]
        return _handoff_evidence_ids(selected, all_analyses=analyses)

    def check_evidence(name: str, label: str, refs: Any, selected_ids: set[str]) -> None:
        values = set(refs or [])
        unresolved = values - evidence_for(selected_ids)
        if unresolved:
            _fail(name, f"{label} has unresolved evidence_refs {sorted(unresolved)}")

    downstream_names = ("brief", "proposal_packet", "script", "scene_plan")
    for name in downstream_names:
        data = artifacts.get(name)
        if not isinstance(data, dict) or data.get("version") != "1.1":
            continue
        refs = data.get("reference_analysis_refs", [])
        reference_driven = bool(data.get("reference_driven")) or bool(refs)
        if refs and not analysis_ids:
            _fail(name, "reference_analysis_refs cannot resolve without a v1.1 analysis artifact")
        if analysis_ids and reference_driven:
            if not refs:
                _fail(name, "reference-driven v1.1 artifact must declare reference_analysis_refs")
            unresolved = set(refs) - analysis_ids
            if unresolved:
                _fail(name, f"reference_analysis_refs has unresolved IDs {sorted(unresolved)}")

    proposal = artifacts.get("proposal_packet")
    if isinstance(proposal, dict) and proposal.get("version") == "1.1" and analysis_ids:
        top_refs = set(proposal.get("reference_analysis_refs", []))
        for index, concept in enumerate(proposal.get("concept_options", [])):
            refs = set(concept.get("reference_analysis_refs", []))
            if not refs.issubset(top_refs):
                _fail("proposal_packet", f"concept_options[{index}] references analyses outside the proposal")
            check_evidence("proposal_packet", f"concept_options[{index}]", concept.get("evidence_refs", []), refs)
        selected_refs = set(proposal["selected_concept"].get("reference_analysis_refs", []))
        if not selected_refs.issubset(top_refs):
            _fail("proposal_packet", "selected_concept references analyses outside the proposal")

    script = artifacts.get("script")
    if isinstance(script, dict) and script.get("version") == "1.1" and analysis_ids:
        script_refs = set(script.get("reference_analysis_refs", []))
        for index, section in enumerate(script.get("sections", [])):
            check_evidence("script", f"sections[{index}]", section.get("evidence_refs", []), script_refs)

    scene_plan = artifacts.get("scene_plan")
    if isinstance(scene_plan, dict) and scene_plan.get("version") == "1.1" and analysis_ids:
        scene_refs = set(scene_plan.get("reference_analysis_refs", []))
        for index, scene in enumerate(scene_plan.get("scenes", [])):
            check_evidence("scene_plan", f"scenes[{index}]", scene.get("evidence_refs", []), scene_refs)

    if (
        isinstance(script, dict)
        and script.get("version") == "1.1"
        and isinstance(scene_plan, dict)
        and scene_plan.get("version") == "1.1"
    ):
        section_ids = {section["id"] for section in script.get("sections", [])}
        for index, scene in enumerate(scene_plan.get("scenes", [])):
            refs = list(scene.get("script_section_ids", []))
            if scene.get("script_section_id"):
                refs.append(scene["script_section_id"])
            if not refs:
                _fail("scene_plan", f"scene[{index}] must map to at least one script section")
            if not set(refs).issubset(section_ids):
                _fail("scene_plan", f"scene[{index}] has dangling script section refs")
