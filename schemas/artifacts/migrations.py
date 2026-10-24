"""Deterministic migrations for OpenMontage artifact contracts."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
import re
from typing import Any


ASPECTS = (
    "subject",
    "subject_motion",
    "scene",
    "spatial_framing",
    "camera",
)


def _hash(value: str) -> str:
    """Return a full digest for persisted fingerprints."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _short_hash(value: str) -> str:
    """Return a compact digest for generated IDs only."""
    return _hash(value)[:24]


def _validate_legacy_time_ranges(data: dict[str, Any]) -> None:
    """Reject v1.0 ranges that cannot be migrated without inventing meaning."""
    source = data.get("source", {})
    try:
        duration = float(source.get("duration_seconds", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Cannot migrate source: non-numeric duration") from exc
    if not math.isfinite(duration) or duration < 0:
        raise ValueError(f"Cannot migrate source: invalid duration {duration}")

    def check(start: Any, end: Any, label: str) -> None:
        try:
            start_value = float(start)
            end_value = float(end)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Cannot migrate {label}: non-numeric time range") from exc
        if not math.isfinite(start_value) or not math.isfinite(end_value):
            raise ValueError(f"Cannot migrate {label}: non-finite time range")
        if start_value < 0 or end_value <= start_value:
            raise ValueError(f"Cannot migrate {label}: invalid time range {start_value}, {end_value}")
        if duration > 0 and end_value > duration + 0.001:
            raise ValueError(f"Cannot migrate {label}: range exceeds duration {duration}")

    structure = data.get("structure_analysis", {})
    for index, scene in enumerate(structure.get("scenes", [])):
        check(scene.get("start_time", 0), scene.get("end_time", 0), f"scene[{index}]")
    transcript = data.get("narration_transcript", {})
    for index, segment in enumerate(transcript.get("segments", [])):
        start = segment.get("start", 0)
        end = segment.get("end")
        if end is None:
            end = float(start) + float(segment.get("duration", 0) or 0)
        check(start, end, f"transcript segment[{index}]")
    for index, frame in enumerate(data.get("keyframes", [])):
        timestamp = float(frame.get("timestamp", 0))
        if not math.isfinite(timestamp):
            raise ValueError(f"Cannot migrate keyframe[{index}]: non-finite timestamp")
        if timestamp < 0 or (duration > 0 and timestamp > duration + 0.001):
            raise ValueError(f"Cannot migrate keyframe[{index}]: timestamp outside source")


def _validate_legacy_finite_values(value: Any, path: str = "$") -> None:
    """Reject non-finite numeric values before a legacy migration."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Cannot migrate {path}: non-finite number")
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_legacy_finite_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_legacy_finite_values(child, f"{path}[{index}]")


_LEGACY_SENTINEL_TEXT = frozenset({
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
_LEGACY_SCHEME_ONLY = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:/*$")
_SHA256_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


def _usable_legacy_locator(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    normalized = re.sub(r"[\W_]+", " ", text.casefold()).strip()
    lowered = text.casefold()
    return (
        bool(normalized)
        and normalized not in _LEGACY_SENTINEL_TEXT
        and not lowered.startswith(("unavailable://", "migration://"))
        and not _LEGACY_SCHEME_ONLY.fullmatch(lowered)
    )


def _source_locator(source: dict[str, Any]) -> str | None:
    for field in ("url", "local_path"):
        value = source.get(field)
        if _usable_legacy_locator(value):
            return value.strip()
    return None


def _source_ref(source: dict[str, Any]) -> str:
    return _source_locator(source) or "migration://video_analysis_brief/1.0/source"


def _normalise_id(value: Any, fallback: str) -> str:
    if not _usable_legacy_locator(value):
        return fallback
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return text or fallback


def _unique_id(value: Any, fallback: str, used: set[str]) -> str:
    """Keep legacy IDs readable while making duplicates deterministic."""
    base = _normalise_id(value, fallback)
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _normalise_transcript_segment(segment: dict[str, Any], index: int) -> dict[str, Any]:
    start = float(segment.get("start", 0))
    if "end" in segment:
        end = float(segment.get("end", start))
    else:
        end = start + float(segment.get("duration", 0))
    if end <= start:
        end = start + 0.001
    result: dict[str, Any] = {
        "id": f"segment-{index:04d}",
        "start": round(start, 3),
        "end": round(end, 3),
        "text": str(segment.get("text", "")),
    }
    for field in ("speaker", "duration", "words"):
        if field in segment:
            result[field] = segment[field]
    return result


def _transfer_items(values: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    items: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        if isinstance(value, dict):
            description = str(value.get("description") or "Legacy guidance without a description.")
            item_id = _normalise_id(value.get("id"), f"{field}-{index + 1}")
            refs = value.get("evidence_refs", [])
        else:
            description = str(value) or "Legacy guidance without a description."
            item_id = f"{field}-{index + 1}"
            refs = []
        grounded = isinstance(refs, list) and bool(refs)
        items.append({
            "id": item_id,
            "description": description,
            "evidence_refs": [str(ref) for ref in refs] if grounded else [],
            "assertion_type": "recommended",
            "provenance_status": "grounded" if grounded else "unavailable",
        })
    return items


def _migrate_video_analysis(data: dict[str, Any]) -> dict[str, Any]:
    _validate_legacy_time_ranges(data)
    result = deepcopy(data)
    source = deepcopy(result.get("source", {}))
    for field in ("url", "local_path"):
        if field in source and not _usable_legacy_locator(source[field]):
            source.pop(field)
    source_locator = _source_locator(source)
    source_ref = source_locator or _source_ref(source)
    fingerprint = source.get("fingerprint")
    if (
        not isinstance(fingerprint, dict)
        or set(fingerprint) - {"kind", "algorithm", "value"}
        or fingerprint.get("kind") not in {"content", "locator", "legacy_locator"}
        or fingerprint.get("algorithm") != "sha256"
        or not isinstance(fingerprint.get("value"), str)
        or not _SHA256_HEX.fullmatch(fingerprint["value"].strip())
    ):
        fingerprint = {
            "kind": "legacy_locator",
            "algorithm": "sha256",
            "value": _hash(source_ref),
        }
    else:
        fingerprint = {**fingerprint, "value": fingerprint["value"].strip().lower()}
    source["fingerprint"] = fingerprint
    if source_locator is None:
        source["identity_status"] = "unavailable"
    source.setdefault("rights_status", "unknown")
    source.setdefault("privacy_status", "review_required")
    source.setdefault("retention_policy", "caller_managed")
    source.setdefault("platform", "youtube" if source.get("type") == "shorts" else source.get("type", "unknown"))
    source.setdefault("surface", source.get("type", "unknown"))

    analysis_id = _normalise_id(
        result.get("analysis_id"), f"analysis-{_short_hash(source_ref)}"
    )
    legacy_meta = result.pop("_analysis_meta", {})
    if not isinstance(legacy_meta, dict):
        legacy_meta = {}
    completed = [str(step) for step in legacy_meta.get("steps_completed", [])]
    failed = [str(step) for step in legacy_meta.get("steps_failed", [])]
    depth = str(legacy_meta.get("depth", "standard"))
    legacy_transcript = result.get("narration_transcript", {})
    has_transcript = bool(
        isinstance(legacy_transcript, dict)
        and (
            str(legacy_transcript.get("full_text", "")).strip()
            or any(
                isinstance(segment, dict) and str(segment.get("text", "")).strip()
                for segment in legacy_transcript.get("segments", [])
            )
        )
    )
    status = (
        "complete"
        if depth == "transcript_only"
        and any(step.startswith("transcript_") for step in completed)
        and has_transcript
        and not failed
        else "partial"
    )
    if not completed and failed:
        status = "failed"

    evidence: list[dict[str, Any]] = [{
        "id": "ev-source-metadata",
        "kind": "source_metadata",
        "status": "available" if source_locator is not None else "unavailable",
        "source_ref": source_ref,
        "description": "Source locator and legacy metadata; content revision was not captured in v1.0.",
    }]
    structure = deepcopy(result.get("structure_analysis", {}))
    scenes = []
    observations = []
    for raw_scene in structure.get("scenes", []):
        scene = deepcopy(raw_scene)
        legacy_scene_index = scene.get("scene_index")
        scene_index = len(scenes)
        scene["scene_index"] = scene_index
        if legacy_scene_index is not None and legacy_scene_index != scene_index:
            scene["legacy_scene_index"] = int(legacy_scene_index)
        scene.setdefault("motion_type", "unknown")
        scene.setdefault("flow_variance", -1)
        scene_evidence_id = f"ev-scene-{scene_index}"
        evidence.append({
            "id": scene_evidence_id,
            "kind": "scene_detection",
            "status": "unavailable",
            "source_ref": "migration://video_analysis_brief/1.0/structure_analysis",
            "start_seconds": float(scene.get("start_time", 0)),
            "end_seconds": float(scene.get("end_time", 0)),
            "scene_index": scene_index,
        })
        observation_ids = []
        for aspect in ASPECTS:
            observation_id = f"obs-scene-{scene_index}-{aspect}"
            observation_ids.append(observation_id)
            observations.append({
                "id": observation_id,
                "scene_index": scene_index,
                "aspect": aspect,
                "status": "unknown",
                "value": "Not captured in the v1.0 artifact; requires reference inspection.",
                "evidence_refs": [],
                "confidence": "low",
            })
        scene["observation_ids"] = observation_ids
        scenes.append(scene)
    structure["scenes"] = scenes
    structure["total_scenes"] = len(scenes)

    transcript = deepcopy(result.get("narration_transcript", {}))
    if isinstance(transcript, dict):
        raw_segments = transcript.get("segments", [])
        transcript["segments"] = [
            _normalise_transcript_segment(segment, index)
            for index, segment in enumerate(raw_segments)
            if isinstance(segment, dict)
        ]
        for segment in transcript["segments"]:
            evidence.append({
                "id": f"ev-transcript-{segment['id']}",
                "kind": "transcript_segment",
                "status": "available" if source_locator is not None else "unavailable",
                "source_ref": source_ref,
                "start_seconds": segment["start"],
                "end_seconds": segment["end"],
                "excerpt": segment["text"],
            })

    keyframes = []
    normalized_scene_indices = {scene["scene_index"] for scene in scenes}
    for index, raw_frame in enumerate(result.get("keyframes", [])):
        if not isinstance(raw_frame, dict):
            continue
        frame = deepcopy(raw_frame)
        frame["id"] = f"keyframe-{index:04d}"
        if raw_frame.get("id") is not None:
            frame["legacy_id"] = str(raw_frame["id"])
        frame["timestamp"] = float(frame.get("timestamp", 0))
        raw_scene_index = int(frame.get("scene_index", 0))
        frame["scene_index"] = (
            raw_scene_index
            if not normalized_scene_indices or raw_scene_index in normalized_scene_indices
            else 0
        )
        if raw_scene_index != frame["scene_index"]:
            frame["legacy_scene_index"] = raw_scene_index
        frame["description"] = str(frame.get("description") or "Legacy keyframe without description.")
        raw_path = frame.get("path")
        has_path = _usable_legacy_locator(raw_path)
        frame["path"] = raw_path.strip() if has_path else f"unavailable://legacy-keyframe/{index:04d}"
        keyframes.append(frame)
        evidence.append({
            "id": f"ev-keyframe-{frame['id']}",
            "kind": "keyframe",
            "status": "available" if has_path else "unavailable",
            "source_ref": frame["path"],
            "start_seconds": frame["timestamp"],
            "end_seconds": frame["timestamp"],
            "scene_index": frame["scene_index"],
        })

    guidance = deepcopy(result.get("replication_guidance", {}))
    if not isinstance(guidance, dict):
        guidance = {}
    for field in (
        "key_elements_to_replicate",
        "elements_requiring_custom_work",
        "creative_differentiation_seeds",
        "preserve",
        "change",
        "avoid",
    ):
        guidance[field] = _transfer_items(guidance.get(field, []), field)

    result.update({
        "version": "1.1",
        "analysis_id": analysis_id,
        "source": source,
        "analysis_run": {
            "id": f"run-{_short_hash(analysis_id + ':' + str(legacy_meta.get('depth', 'standard')))}",
            "depth": depth,
            "status": status,
            "steps_completed": completed,
            "steps_failed": failed,
            "tool": {"name": "video_analyzer", "version": "legacy-v1.0"},
            "config": {},
        },
        "evidence": evidence,
        "five_aspect_observations": observations,
        "assertions": [],
        "structure_analysis": structure,
        "narration_transcript": transcript,
        "keyframes": keyframes,
        "replication_guidance": guidance,
        "metadata": {
            "migrated_from": "video_analysis_brief@1.0",
            "legacy_analysis_meta": legacy_meta,
        },
    })
    result.setdefault("style_profile", {})
    result.setdefault("content_analysis", {"summary": "", "topics": [], "target_audience": "unknown"})
    return result


def _migrate_bundle(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    migrated = []
    for analysis in result.get("analyses", []):
        if isinstance(analysis, dict) and analysis.get("version") == "1.0":
            migrated.append(_migrate_video_analysis(analysis))
        else:
            migrated.append(deepcopy(analysis))
    reserved_ids = {
        str(item.get("analysis_id"))
        for item in migrated
        if isinstance(item, dict) and item.get("analysis_id")
    }
    seen_ids: set[str] = set()
    for index, item in enumerate(migrated):
        if not isinstance(item, dict):
            continue
        base_id = str(item.get("analysis_id", f"analysis-member-{index:04d}"))
        if base_id in seen_ids:
            candidate = f"{base_id}-member-{index:04d}"
            suffix = 2
            while candidate in reserved_ids or candidate in seen_ids:
                candidate = f"{base_id}-member-{index:04d}-{suffix}"
                suffix += 1
            item["analysis_id"] = candidate
            run = item.get("analysis_run")
            if isinstance(run, dict) and run.get("id"):
                run["id"] = f"{run['id']}-member-{index:04d}"
            item.setdefault("metadata", {})["identity_disambiguation"] = {
                "reason": "duplicate legacy source identity",
                "bundle_member_index": index,
            }
        seen_ids.add(str(item["analysis_id"]))
    ids = [str(item.get("analysis_id", index)) for index, item in enumerate(migrated) if isinstance(item, dict)]
    result["version"] = "1.1"
    result["bundle_id"] = _normalise_id(
        result.get("bundle_id"), f"bundle-{_short_hash('|'.join(ids))}"
    )
    result["analyses"] = migrated
    result.setdefault("metadata", {})
    result["metadata"]["migrated_from"] = "video_analysis_bundle@1.0"
    return result


def _migrate_brief(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    result["version"] = "1.1"
    result.setdefault("reference_analysis_refs", [])
    result.setdefault("narrative_profile_refs", [])
    result.setdefault("reference_driven", bool(result.get("reference_material")))
    result.setdefault("adaptation", {"preserve": [], "change": [], "avoid": []})
    result.setdefault("metadata", {})
    if result.get("reference_material"):
        result["metadata"]["legacy_reference_material_unresolved"] = list(result["reference_material"])
        result["reference_driven"] = False
    return result


def _migrate_proposal(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    result["version"] = "1.1"
    result.setdefault("reference_analysis_refs", [])
    result.setdefault("narrative_profile_refs", [])
    used_ids: set[str] = set()
    id_map: dict[str, str] = {}
    for index, concept in enumerate(result.get("concept_options", [])):
        original_id = concept.get("id")
        concept["id"] = _unique_id(original_id, f"concept-{index + 1}", used_ids)
        if isinstance(original_id, str) and original_id not in id_map:
            id_map[original_id] = concept["id"]
        concept.setdefault("reference_analysis_refs", [])
        concept.setdefault("narrative_profile_refs", [])
        concept.setdefault("evidence_refs", [])
        concept.setdefault("preserve", [])
        concept.setdefault("change", [])
        concept.setdefault("avoid", [])
    selected = result.setdefault("selected_concept", {})
    if selected.get("concept_id") in id_map:
        selected["concept_id"] = id_map[selected["concept_id"]]
    selected.setdefault("reference_analysis_refs", [])
    selected.setdefault("narrative_profile_refs", [])
    return result


def _migrate_script(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    result["version"] = "1.1"
    result.setdefault("reference_analysis_refs", [])
    result.setdefault("narrative_profile_refs", [])
    used_ids: set[str] = set()
    id_map: dict[str, str] = {}
    for index, section in enumerate(result.get("sections", [])):
        original_id = section.get("id")
        section["id"] = _unique_id(original_id, f"section-{index + 1}", used_ids)
        if isinstance(original_id, str) and original_id not in id_map:
            id_map[original_id] = section["id"]
        section.setdefault("evidence_refs", [])
        section.setdefault("source_refs", [])
        if section.get("source_ref") and section["source_ref"] not in section["source_refs"]:
            section["source_refs"].append(section["source_ref"])
        section.setdefault("beat_role", section.get("label", "section"))
    voice_performance = result.get("voice_performance")
    if isinstance(voice_performance, dict) and "sample_section_id" in voice_performance:
        sample_id = voice_performance.get("sample_section_id")
        normalized_sample_id = id_map.get(sample_id) if isinstance(sample_id, str) else None
        if normalized_sample_id in used_ids:
            voice_performance["sample_section_id"] = normalized_sample_id
        else:
            voice_performance.pop("sample_section_id", None)
    if "sample_section_id" in result:
        sample_id = result.get("sample_section_id")
        normalized_sample_id = id_map.get(sample_id) if isinstance(sample_id, str) else None
        if normalized_sample_id in used_ids:
            result["sample_section_id"] = normalized_sample_id
        else:
            result.pop("sample_section_id", None)
    return result


def _migrate_scene_plan(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    result["version"] = "1.1"
    result.setdefault("reference_analysis_refs", [])
    result.setdefault("narrative_profile_refs", [])
    used_ids: set[str] = set()
    for index, scene in enumerate(result.get("scenes", [])):
        scene["id"] = _unique_id(scene.get("id"), f"scene-{index + 1}", used_ids)
        raw_refs = scene.get("script_section_ids", [])
        if not isinstance(raw_refs, list):
            raw_refs = []
        refs = []
        for ref_index, ref in enumerate(raw_refs):
            normalized_ref = _normalise_id(ref, f"section-{index + 1}-{ref_index + 1}")
            if normalized_ref not in refs:
                refs.append(normalized_ref)
        if "script_section_id" in scene:
            normalized_singular = _normalise_id(
                scene.get("script_section_id"), f"section-{index + 1}-1"
            )
            scene["script_section_id"] = normalized_singular
            if normalized_singular not in refs:
                refs.append(normalized_singular)
        scene["script_section_ids"] = refs
        scene.setdefault("evidence_refs", [])
        scene.setdefault("visual_intent", scene.get("shot_intent", scene.get("description", "")))
    return result


def migrate_artifact(
    name: str,
    data: dict[str, Any],
    *,
    target_version: str = "1.1",
) -> dict[str, Any]:
    """Return a new artifact migrated to target_version without mutating input."""
    if target_version != "1.1":
        raise ValueError(f"Unsupported migration target {target_version!r}")
    current = data.get("version")
    if current == target_version:
        return deepcopy(data)
    if current != "1.0":
        raise ValueError(f"Unsupported {name} source version {current!r}")
    _validate_legacy_finite_values(data)
    migrators = {
        "video_analysis_brief": _migrate_video_analysis,
        "video_analysis_bundle": _migrate_bundle,
        "brief": _migrate_brief,
        "proposal_packet": _migrate_proposal,
        "script": _migrate_script,
        "scene_plan": _migrate_scene_plan,
    }
    try:
        migrator = migrators[name]
    except KeyError as exc:
        raise ValueError(f"No migration registered for {name!r}") from exc
    return migrator(data)
