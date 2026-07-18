"""Render discovery and produces-vs-reality validators for the stage runner.

Split out of stage_runner.py: everything here is a stateless leaf function
(project_dir / an artifact dict / options in, a Path/str/ProducesValidation
out) with no orchestration dependencies — no job_store, no LLM client, no
nonlocal closures over pipeline state. `_check_render_runtime_consistency`
(the edit-vs-proposal render_runtime check) deliberately stayed behind in
stage_runner.py — it's a different check family (consistency between two
artifacts, not an artifact's claims vs. what's actually on disk) and isn't
one of the _PRODUCES_EXPORT_VALIDATORS entries this module owns.

Re-imported back into stage_runner.py's own namespace (see its import block)
so every existing call site in that file, and every direct
`from app.runner.stage_runner import _discover_render_url, ...` in the test
suite, keeps working unchanged — this is pure code motion, not a behavior
change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.runner.tool_bridge import variant_slug

logger = logging.getLogger(__name__)


# Tool names (registry `name`, from tools/tool_registry.py) capable of
# producing the FINAL composed video — the whole-film render, not a per-clip
# editing op. tool_bridge.py names every non-final-compose video_post output
# "{tool_name}{variant_tag}_{unique}.mp4" and writes it under assets/video_post/
# (only a call whose `operation` resolves to "compose" is treated as final and
# routed to renders/ instead — see tool_bridge.py's is_final_compose). A call
# using one of these SAME tool names but a different operation (e.g.
# operation="render"/"remotion_render", which still legitimately produces the
# whole film via Remotion/HyperFrames) also lands in assets/video_post/, so
# this is deliberately a whitelist of compose-capable tool names, not a check
# on the operation string itself.
_COMPOSE_FAMILY_TOOL_PREFIXES = ("video_compose_", "hyperframes_compose_")


def _discover_render_path(project_dir: Path) -> Path | None:
    """Find the final rendered video file on disk, or None if none exists.

    Extracted out of _discover_render_url so a caller that needs the actual
    Path (not just a servable URL) — e.g. cross-validating render_report's
    own claimed output path against reality — doesn't have to re-derive it.
    """
    def _newest(paths: list[Path]) -> Path | None:
        existing = [p for p in paths if p.is_file()]
        if not existing:
            return None
        return max(existing, key=lambda p: p.stat().st_mtime)

    candidate = _newest(list((project_dir / "renders").glob("*.mp4")))
    if candidate is None:
        # Fallback: a compose-family tool (video_compose/hyperframes_compose,
        # capability="video_post") wrote its output under assets/ instead of
        # renders/ — e.g. operation="render"/"remotion_render" is a legitimate
        # final render but isn't routed to renders/ by tool_bridge.py (only
        # operation="compose" is). Scoped to those two tool names specifically
        # — NOT every assets/video_post/*.mp4 — because trim/stitch/etc. calls
        # (video_trimmer, video_stitch, ...) write their INTERMEDIATE,
        # non-final clips to this same folder using the same naming scheme.
        # Without this scoping, a trim/stitch call that ran earlier in this
        # stage's conversation, followed by a final compose call that then
        # FAILED, would leave that intermediate clip sitting here as the
        # newest assets/video_post/*.mp4 — and the old unscoped glob picked
        # exactly that up and presented it as the finished render (the same
        # bug class already fixed once below for assets/video_generation/*.mp4
        # raw scene clips).
        candidate = _newest([
            p for p in project_dir.glob("assets/video_post/*.mp4")
            if p.name.startswith(_COMPOSE_FAMILY_TOOL_PREFIXES)
        ])
    if candidate is None:
        # Last resort: a misnamed compose output (.bin) that is really an mp4
        candidate = _newest(list(project_dir.glob("assets/video_post/*compose*output*")))

    return candidate


def _discover_render_url(project_dir: Path, project_name: str) -> str | None:
    """Find the final rendered video and return a browser-servable /media URL."""
    candidate = _discover_render_path(project_dir)
    if candidate is None:
        return None
    return _url_for_render(project_dir, project_name, candidate)


def _render_report_path_diverges(
    project_dir: Path, render_report: dict, discovered: Path | None
) -> str | None:
    """Return render_report's own claimed output path if it differs from the
    actually-discovered render file, else None.

    Confirmed live: even in a run that passed the render-file-existence
    check (a real mp4 existed), render_report claimed a DIFFERENT output
    filename than the one actually discovered. A wrong internal path claim
    while a real file DOES exist is lower-severity than no file at all
    (already hard-failed separately) — this only informs, it never fails
    the stage.
    """
    if discovered is None:
        return None
    outputs = (render_report or {}).get("outputs") or []
    if not outputs:
        return None
    claimed = outputs[0].get("path")
    if not claimed:
        return None
    try:
        claimed_resolved = (project_dir / claimed).resolve()
    except OSError:
        return claimed
    if claimed_resolved != discovered.resolve():
        return claimed
    return None


def _validate_publish_log_exports(project_dir: Path, publish_log: dict) -> list[str]:
    """Return the publish_log-claimed export_paths that have NO real file on
    disk, for every entry whose status implies a file was actually produced.

    Confirmed live: a publish_log artifact claimed 5 real export files
    (teaser cut, platform-specific crops, poster frame) that were never
    generated — no exports/ directory ever created, zero video-processing
    tool calls in that stage's trace. Per schemas/artifacts/publish_log.
    schema.json, "exported" and "draft" are the statuses that imply a real
    file was written (as opposed to "published"/a remote upload with no
    local file, "failed", or "pending_review").
    """
    missing: list[str] = []
    for entry in (publish_log or {}).get("entries", []):
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        export_path = entry.get("export_path")
        if status in ("exported", "draft") and export_path:
            # export_path may name a single file OR a bundle directory —
            # tools/publishers/export_bundle.py (the canonical publish tool)
            # writes the bundle's ROOT DIRECTORY as export_path, so an
            # is_file()-only check hard-failed every genuine export_bundle
            # run. A directory counts as real only when it contains at
            # least one file — an empty dir proves nothing was exported.
            p = project_dir / export_path
            if not (p.is_file() or (p.is_dir() and any(f.is_file() for f in p.rglob("*")))):
                missing.append(export_path)
    return missing


@dataclass
class ProducesValidation:
    """Uniform result shape for every _PRODUCES_EXPORT_VALIDATORS entry.

    Replaces the single "failure-message-or-None" return each validator used
    to have — adding a second entry (render_report, folding in the former
    compose-only render-file/path-divergence/variant checks — see
    _validate_render_report_produces) needed a way to express a hard failure
    and a separate, non-fatal warning from ONE validator call, without
    inventing a third ad hoc return shape per entry. `hard_failures` MUST
    fail the stage (a fabricated/missing artifact-vs-reality claim);
    `warnings` are surfaced via a "warning" event but let the stage proceed
    (e.g. render_report's internal path claim being wrong while a real
    render file still exists — lower severity than no file at all).
    """
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _validate_publish_log_produces(
    project_dir: Path, publish_log: dict, options: dict
) -> ProducesValidation:
    """_PRODUCES_EXPORT_VALIDATORS adapter for _validate_publish_log_exports.

    `options` is accepted-but-unused purely so every table entry shares the
    same call signature (render_report's entry needs it for the A/B variant
    list) — the call site can then invoke any entry identically.
    """
    missing = _validate_publish_log_exports(project_dir, publish_log)
    result = ProducesValidation()
    if missing:
        result.hard_failures.append(
            f"wrote publish_log claiming export(s) {missing}, but no file "
            f"exists at that path under {project_dir} — the artifact's "
            "claimed output isn't backed by a real file. Retry will re-run "
            "this stage."
        )
    return result


def _validate_render_report_produces(
    project_dir: Path, render_report: dict, options: dict
) -> ProducesValidation:
    """_PRODUCES_EXPORT_VALIDATORS entry folding in the three compose-specific
    "did this really render?" checks that used to run independently, back to
    back, right after the compose stage finished (see _run_pipeline_impl's
    call site for the "confirmed live" incident behind each):
      1. _discover_render_path: a real file under renders/ must exist —
         render_report/final_review existing is not proof a render happened.
      2. _render_report_path_diverges: render_report's own claimed output
         path must match what was actually discovered (a warning, not a
         failure — a real file DOES exist here, lower severity than #1).
      3. _missing_variants: for an A/B job, EVERY declared variant must have
         its own rendered file, not just any one of them.
    """
    result = ProducesValidation()
    discovered = _discover_render_path(project_dir)
    if discovered is None:
        result.hard_failures.append(
            "wrote render_report/final_review but no actual render file "
            f"exists under {project_dir / 'renders'} — the report's claimed "
            "output isn't backed by a real file. Retry will re-run this "
            "stage."
        )
        return result  # nothing else to check without a real file

    diverges = _render_report_path_diverges(project_dir, render_report, discovered)
    if diverges:
        result.warnings.append(
            f"render_report claims output path '{diverges}' but the actual "
            "discovered render file is "
            f"'{discovered.relative_to(project_dir)}' — the report's "
            "internal path claim doesn't match reality (a real file does "
            "exist, so the stage still proceeds)."
        )

    missing_variants = _missing_variants(project_dir, options)
    if missing_variants:
        total_variants = len(options.get("video_model_variants") or [])
        result.hard_failures.append(
            f"is an A/B variants job ({total_variants} declared), but "
            f"{len(missing_variants)} variant(s) never produced a render "
            f"file: {missing_variants}. Refusing to mark a multi-variant "
            "compose stage complete with partial output. Retry will re-run "
            "this stage."
        )
    return result


# Stage-produces artifact name -> validator (project_dir, artifact_value,
# options) -> ProducesValidation, checking the artifact's file-backed claims
# against reality. ONE table drives every per-stage artifact-vs-reality
# check — see _run_pipeline_impl's call site comment for the four separate
# mechanisms this replaced (a literal `stage_name == "compose"` render-file
# check, a separate _missing_variants() call, a separate
# _render_report_path_diverges() warning check, and this same produces-keyed
# loop, previously carrying only the publish_log case).
_PRODUCES_EXPORT_VALIDATORS = {
    "publish_log": _validate_publish_log_produces,
    "render_report": _validate_render_report_produces,
}


def _missing_variants(project_dir: Path, options: dict) -> list[str] | None:
    """For a multi-variant compose job, return the declared A/B model strings
    that have NO corresponding rendered file — or None if this isn't a
    multi-variant job, or every declared variant rendered.

    The compose anti-fabrication check (in _run_pipeline_impl, right after
    _discover_render_url) only requires ANY render file to exist. In a
    3-variant job where 2 variants render and the 3rd fails, that check alone
    still passes (a render DID happen) and the stage proceeds as genuinely
    complete with no signal that a whole variant never rendered. Each
    variant is expected to land at renders/final_<variant_slug(model)>.mp4 per
    tool_bridge.py's per-call output-path tagging — the "A/B Variants" prompt
    section in _run_agent_stage instructs the agent to pass `inputs.variant`
    as the exact declared model string on every compose call.
    """
    variants = [m for m in (options.get("video_model_variants") or []) if m]
    if len(variants) <= 1:
        return None
    renders_dir = project_dir / "renders"
    missing = [m for m in variants if not (renders_dir / f"final_{variant_slug(m)}.mp4").is_file()]
    return missing or None


def _url_for_render(project_dir: Path, project_name: str, candidate: Path) -> str:
    rel = candidate.relative_to(project_dir).as_posix()
    # Route through the storage seam so swapping to object storage later yields
    # signed URLs without touching this call site.
    try:
        from app.interfaces import get_storage
    except ImportError:
        # The storage seam module itself isn't importable in this process —
        # genuinely "no real storage backend available" (e.g. a stripped
        # module path), not a bug in a configured backend.
        return f"/media/{project_name}/{rel}"
    try:
        return get_storage().url_for(project_name, rel)
    except Exception as exc:
        # A genuinely configured (non-local) storage backend raising here is a
        # real bug (bad credentials, unreachable bucket, ...) that silently
        # falling back to the local /media/ path would mask — the returned
        # URL would just 404 with no diagnostic anywhere. Log it so it's
        # visible, but still fall back so render discovery doesn't hard-fail
        # the whole job over a URL-formatting problem.
        logger.warning(
            "get_storage().url_for(%r, %r) raised %r; falling back to local media path",
            project_name, rel, exc,
        )
        return f"/media/{project_name}/{rel}"


def _discover_render_urls(project_dir: Path, project_name: str) -> dict[str, str] | None:
    """Variant-aware sibling of _discover_render_url.

    An A/B job's compose stage produces renders/final_<slug>.mp4 per variant
    (tool_bridge.py's `variant` output-path tagging) instead of a single
    renders/final.mp4. Returns {variant_slug: url} for every renders/final*.mp4
    found, or None for a normal (non-variant) job where only final.mp4 exists —
    callers should keep using the singular render_url/preview_render_url in
    that case, so a non-variant job's behavior is untouched.
    """
    renders = sorted((project_dir / "renders").glob("final*.mp4"))
    if len(renders) <= 1:
        return None  # 0 or 1 file: not a multi-variant job, nothing plural to report
    urls: dict[str, str] = {}
    for path in renders:
        stem = path.stem  # "final_ltx2-3" -> "ltx2-3"; bare "final" -> ""
        slug = stem[len("final"):].lstrip("_") or "default"
        urls[slug] = _url_for_render(project_dir, project_name, path)
    return urls
