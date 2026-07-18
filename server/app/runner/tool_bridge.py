"""Tool Bridge: exposes OpenMontage BaseTool registry to the headless agent.

The agent is given three capabilities:
  read_file         — read any file under the OpenMontage root
  write_artifact    — persist an artifact JSON to the project dir
  run_openmontage_tool — call any registered BaseTool by name

Tool schemas are returned in OpenAI function-call format so they work with
both the OpenAI SDK (pointing at MaaS) and Anthropic SDK.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add OpenMontage root to path so we can import tools/lib
OM_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(OM_ROOT))

# Artifact names are meant to be flat identifiers (e.g. "research_brief"), not
# paths — reject anything else outright rather than trying to reason about
# path-containment edge cases for a field that should never contain a
# separator at all.
_SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

# read_file's per-result truncation cap. stage_runner.py derives its own
# TOOL_RESULT_CHAR_CAP from this (READ_FILE_CHAR_CAP + headroom) — the outer
# cap MUST stay strictly larger, or a near-cap file gets truncated twice and
# the "[truncated — N total chars]" marker itself gets garbled mid-sentence.
# Keeping the relationship in code (not prose) is the whole point of this
# constant existing.
READ_FILE_CHAR_CAP = 12000


def _safe_relative_path(base: Path, relative: str) -> Path | None:
    """Resolve `relative` under `base`, returning it only if it actually stays
    within `base`. Guards against pathlib's absolute-path-override footgun
    (`base / "/etc/passwd"` silently discards `base`) and `..` traversal —
    confirmed live: read_file(path=".env") alone discloses MAAS_API_KEY since
    OM_ROOT is the repo root, and read_file(path="/etc/passwd") escapes
    entirely with no code anywhere stopping it. Returns None on any escape."""
    try:
        candidate = (base / relative).resolve()
        candidate.relative_to(base.resolve())
    except (ValueError, OSError):
        return None
    return candidate


def _anchor_output_path(supplied: str, project_dir: Path, tool: Any) -> Path:
    """Force an agent-supplied output_path to land inside the job's project_dir.

    When the agent does NOT pass output_path, the bridge auto-assigns one under
    project_dir (see execute_tool). When it DOES, the path used to be trusted
    verbatim — and confirmed live, that orphaned every generated asset: the
    agent passed relative paths (which resolve against the server's CWD, not the
    repo root) under a self-chosen project slug from its own init_project call,
    so a $7.70 batch of clips landed in server/projects/<other-slug>/assets/…
    while the manifest recorded project-relative paths the compose stage
    resolved against project_dir — and found nothing. The mismatch also broke
    the filmstrip: media_url is computed relative_to(project_dir) and threw for
    every out-of-tree file.

    Re-root the path under project_dir, preserving the first 'assets/…' or
    'renders/…' segment so the manifest's project-relative paths stay
    consistent. Idempotent for a path already correctly under project_dir.
    """
    parts = Path(supplied).parts
    for anchor in ("renders", "assets"):
        if anchor in parts:
            return project_dir / Path(*parts[parts.index(anchor):])
    # No recognizable structure — drop it under assets/<capability>/<basename>.
    cap = getattr(tool, "capability", None) or "misc"
    return project_dir / "assets" / cap / Path(supplied).name

# Authoritative budget-exceeded type shared with the runner (fall back to a
# local class if the cost_tracker module isn't importable).
try:
    from tools.cost_tracker import BudgetExceededError
except Exception:  # pragma: no cover
    class BudgetExceededError(Exception):
        """Fallback mirroring tools.cost_tracker.BudgetExceededError's shape
        (message + optional tool_name/est_cost/projected_cny) so callers don't
        have to special-case which BudgetExceededError they caught."""

        def __init__(
            self,
            message: str,
            tool_name: str | None = None,
            est_cost: float | None = None,
            projected_cny: float | None = None,
        ) -> None:
            super().__init__(message)
            self.tool_name = tool_name
            self.est_cost = est_cost
            self.projected_cny = projected_cny

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the OpenMontage filesystem. "
                "Use for skills (skills/), pipeline manifests (pipeline_defs/), "
                "schemas (schemas/), and project artifacts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to OpenMontage root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_artifact",
            "description": (
                "Write a pipeline artifact JSON to the project artifacts directory. "
                "IMPORTANT: Keep 'content' compact — each field value under 300 chars, "
                "use arrays of short strings rather than long prose. "
                "Large content causes token truncation and will fail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_name": {
                        "type": "string",
                        "description": (
                            "Use the exact name given under '## Expected Artifact Name' "
                            "in your stage instructions — it varies per pipeline/stage "
                            "(e.g. a stage named 'idea' may produce 'brief', not 'idea')."
                        )
                    },
                    "content": {
                        "type": "object",
                        "description": "Compact JSON artifact. Keep each string value under 300 chars."
                    }
                },
                "required": ["artifact_name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_openmontage_tool",
            "description": (
                "Run a tool from the OpenMontage tool registry. "
                "Available capabilities: video_generation, image_generation, tts, "
                "music_search, subtitle, enhancement, analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Registered tool name, e.g. 'maas_video', 'maas_image', 'maas_tts'"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Tool inputs per the tool's input_schema"
                    }
                },
                "required": ["tool_name", "inputs"]
            }
        }
    }
]


# Maps the job-level "which capability does this option name constrain"
# relationship: options[<key>] / options[<variants_key>] binds tool_name's
# `inputs["model"]`. Extend this if another capability gets a wizard-level
# model choice (e.g. music) — everything else about the enforcement below is
# generic over this table.
_MODEL_ENFORCED_TOOLS: dict[str, dict[str, str]] = {
    "maas_video": {"default_key": "video_model", "variants_key": "video_model_variants"},
    "maas_image": {"default_key": "image_model", "variants_key": "image_model_variants"},
    "maas_tts":   {"default_key": "tts_model",   "variants_key": "tts_model_variants"},
}


def variant_slug(model_or_variant: str) -> str:
    """Turn a model ID ("leapfast/ltx-2.3") or an already-short variant tag
    ("ltx") into a filesystem-safe slug ("ltx2-3" / "ltx"). Used to keep
    per-variant output files distinguishable (final_ltx.mp4 vs
    final_wan.mp4) instead of an opaque random suffix that tells a human
    nothing about which A/B branch produced which file."""
    tail = model_or_variant.rsplit("/", 1)[-1]
    slug = "".join(c if c.isalnum() else "-" for c in tail.lower()).strip("-")
    return slug or "default"


def _enforce_model_choice(tool_name: str, inputs: dict[str, Any], options: dict[str, Any] | None) -> str | None:
    """Fill in or validate inputs["model"] against the job's options.

    Returns None if the call may proceed (inputs mutated in place when a
    default was filled in), or an error string if the agent must be told to
    retry with a different model — before any paid API call is made.

    Without this, the wizard's model choice (or an A/B variants list) was
    purely descriptive text in the prompt (`## Options: {...}`) — the agent
    was free to call any model regardless of what the user selected. That
    made "pick a model in the UI" cosmetic: the dropdown could say
    leapfast/wan2.2 while the agent quietly kept generating with whatever it
    defaulted to.
    """
    if not options:
        return None
    cfg = _MODEL_ENFORCED_TOOLS.get(tool_name)
    if not cfg:
        return None

    variants = options.get(cfg["variants_key"])
    allowed = [m for m in variants if m] if isinstance(variants, list) and variants else None
    default = options.get(cfg["default_key"]) or None

    if not allowed and not default:
        return None  # job didn't constrain this capability at all

    requested = inputs.get("model")
    if not requested:
        if allowed and len(allowed) > 1:
            # A genuine A/B choice exists — autofilling here would silently
            # collapse every call onto allowed[0], so every "variant" in the
            # run ends up using the same model with nothing anywhere to flag
            # it. Require the agent to say which one explicitly instead.
            return (
                f"ERROR: this job declares {len(allowed)} {cfg['default_key']} variants "
                f"({allowed}) — inputs.model must be set explicitly to one of them on "
                f"every {tool_name} call. Omitting it would silently collapse every "
                "variant onto the same model."
            )
        # Fill in rather than reject — the common case (no variants) should
        # just work without the agent having to echo the option back.
        inputs["model"] = (allowed[0] if allowed else default)
        return None

    permitted = allowed or [default]
    if requested in permitted:
        return None

    return (
        f"ERROR: model {requested!r} is not permitted for this job's {cfg['default_key']} "
        f"setting. This job is constrained to: {permitted}. "
        f"Retry {tool_name} with model set to one of those — do not substitute a different "
        f"one even if you believe it fits the prompt better; the user chose this in the wizard."
    )


def _enforce_compose_variant_tag(
    tool: Any, inputs: dict[str, Any], options: dict[str, Any] | None
) -> str | None:
    """Require inputs["variant"] to be explicit on a compose call when the
    job declares more than one video_model_variants entry (an A/B run).

    Mirrors _enforce_model_choice's pattern, but for the compose stage —
    which has no `model` field of its own to validate against. The only way
    a compose call can say which A/B branch it belongs to is
    inputs["variant"] (see the output-path tagging in execute_tool below,
    which folds it into renders/final_<slug>.mp4). Without this guard, an
    agent that forgets to tag one of N compose calls in a multi-variant job
    falls back to the untagged "final.mp4" path, silently colliding with —
    and potentially overwriting — another variant's rendered output.

    Only enforced when more than one variant is declared and the call is
    actually a compose (not trim/stitch/etc.) — a single-variant (or
    non-A/B) job has nothing to collide with, so the existing permissive
    default-tag behavior is preserved there.

    Also mirrors _enforce_model_choice's MEMBERSHIP check: a truthy
    inputs["variant"] is not enough on its own — it must exactly match one
    of the declared video_model_variants. Without this, a typo'd or
    invented variant tag passed enforcement, ran an expensive render, and
    only surfaced as a problem later (stage_runner.py's `_missing_variants`
    check) after money was already spent.
    """
    if not options or tool is None:
        return None
    if getattr(tool, "capability", None) != "video_post":
        return None
    if inputs.get("operation", "compose") != "compose":
        return None

    variants = options.get("video_model_variants")
    allowed = [m for m in variants if m] if isinstance(variants, list) and variants else None
    if not allowed or len(allowed) <= 1:
        return None

    requested = inputs.get("variant")
    if requested:
        if requested in allowed:
            return None
        return (
            f"ERROR: variant {requested!r} is not one of this job's declared "
            f"video_model_variants ({allowed}). An invalid variant tag would still "
            "run an expensive render before failing later — retry with inputs.variant "
            "set to one of the exact declared strings."
        )

    return (
        f"ERROR: this job declares {len(allowed)} video_model_variants ({allowed}) — "
        "every compose call must set inputs.variant to the exact model string for the "
        "branch it is rendering. Omitting it would silently fall back to the untagged "
        "'final.mp4' output, colliding with another variant's render."
    )


_TTS_EMOTION_KEYS = ("emo_alpha", "use_emo_text", "emo_text", "interval_silence")


def _apply_tts_emotion_defaults(inputs: dict[str, Any], options: dict[str, Any] | None) -> None:
    """Fill in maas_tts's IndexTTS V3 emotion params (options["tts_emotion"])
    when the agent's call didn't set them explicitly.

    Without this, the wizard's emotion controls were purely descriptive —
    nothing read them, so picking an emotion in the UI had zero effect unless
    the agent happened to independently choose the same values. Unlike
    _enforce_model_choice, this only fills gaps rather than rejecting a
    mismatch: there's no "wrong" emotion value to block, only a default that
    should apply when the agent didn't think to set one, while still letting
    it deliberately vary emotion per line/scene if it wants to.

    emo_alpha=0.0 is a valid, meaningful value (flat delivery) — checked via
    `key in defaults`, not truthiness, so it isn't mistaken for "unset".
    """
    if not options:
        return
    defaults = options.get("tts_emotion")
    if not isinstance(defaults, dict):
        return
    for key in _TTS_EMOTION_KEYS:
        if key in defaults and key not in inputs:
            inputs[key] = defaults[key]


def _append_selector_decision(
    project_dir: Path,
    tool_name: str,
    capability: str,
    data: dict[str, Any],
) -> None:
    """Persist a selector's scored provider pick into the project's
    decision_log artifact (roadmap 1.4).

    Selectors have always computed a full rationale — selection_reason is
    ToolScore.explain(), plus provider_score and alternatives_considered —
    and returned it in result.data, where it reached only the LLM's context
    window and was never persisted. This appends a schema-valid decision
    entry so the decision rail (Backlot + web) can show auto-routed provider
    picks with their actual reasons. Consecutive identical picks for the
    same (category, subject) pair are not re-appended — a per-scene TTS loop
    would otherwise write dozens of duplicate rows.
    """
    try:
        selected = data.get("selected_tool")
        if not selected:
            return
        log_path = project_dir / "artifacts" / "decision_log.json"
        log: dict[str, Any] = {"version": "1.0", "decisions": []}
        if log_path.exists():
            try:
                loaded = json.loads(log_path.read_text())
                if isinstance(loaded, dict) and isinstance(loaded.get("decisions"), list):
                    log = loaded
            except (OSError, json.JSONDecodeError):
                pass
        category = "provider_selection"
        subject = f"{capability} provider (auto-routed via {tool_name})"
        # Latest entry for this (category, subject) pair — the board renders
        # the last entry per pair as current, so only append on change.
        latest = next(
            (d for d in reversed(log["decisions"])
             if isinstance(d, dict) and d.get("category") == category and d.get("subject") == subject),
            None,
        )
        if latest is not None and latest.get("selected") == selected:
            return
        provider = data.get("selected_provider")
        score = data.get("provider_score") or {}
        options: list[dict[str, Any]] = [{
            "option_id": selected,
            "label": f"{provider} ({selected})" if provider else selected,
            **({"score": round(float(score["weighted_score"]), 4)}
               if isinstance(score.get("weighted_score"), (int, float)) else {}),
        }]
        for alt in data.get("alternatives_considered") or []:
            options.append({"option_id": alt, "label": alt})
        entry: dict[str, Any] = {
            "category": category,
            "subject": subject,
            "selected": selected,
            "reason": data.get("selection_reason"),
            "options_considered": options,
            "user_visible": True,
            "user_approved": False,
        }
        if isinstance(score.get("weighted_score"), (int, float)):
            entry["confidence"] = max(0.0, min(1.0, float(score["weighted_score"])))
        log["decisions"].append(entry)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    except Exception:
        # Never let audit-trail bookkeeping break a successful tool call.
        logger.warning("failed to append selector decision for %s", tool_name, exc_info=True)


def execute_tool(
    name: str,
    args: dict[str, Any],
    project_dir: Path,
    emit_event: Any = None,   # callable(event_dict) for SSE
    cost_accumulator: list | None = None,  # mutable list[float] for cost accumulation
    cost_tracker: Any = None,  # optional tools.cost_tracker.CostTracker ledger
    budget_cny: float | None = None,  # per-job CNY ceiling (None = no gate)
    base_cost: float = 0.0,           # cost already spent before this run (retries)
    options: dict[str, Any] | None = None,  # job-level options (model choices, variants)
) -> str:
    """Execute a tool call and return a string result for the agent.

    Two deliberately different result shapes coexist here: cheap validation
    failures (missing/invalid params, unknown tool, path containment,
    _enforce_model_choice's rejection) return a plain "ERROR: ..." string,
    while a call that actually reached the underlying tool returns
    JSON (`{"success": true/false, ...}`) because that path carries
    structured data (result.data/artifacts/cost_usd) a bare string can't
    express. Both are read as natural-language tool output by the LLM either
    way, so this isn't a functional gap — flagged here because a repo-wide
    grep for "ERROR" pattern-matches many existing tests that assert the
    plain-string shape for the validation-error paths specifically;
    mechanically unifying the shape would mean rewriting that coverage for a
    purely cosmetic gain.
    """

    if name == "read_file":
        path = _safe_relative_path(OM_ROOT, args["path"])
        if path is None:
            return f"ERROR: path {args['path']!r} is outside the OpenMontage root — not allowed"
        # read_file exists for skills/, pipeline_defs/, schemas/, and project
        # artifacts (per its own tool description) — never dotfiles. Without
        # this, staying within OM_ROOT isn't enough: .env sits directly at
        # OM_ROOT, so a plain in-bounds read_file(path=".env") would still
        # disclose MAAS_API_KEY.
        if any(part.startswith(".") for part in path.relative_to(OM_ROOT.resolve()).parts):
            return f"ERROR: refusing to read a dotfile/dotdir path: {args['path']!r}"
        if not path.exists():
            return f"ERROR: File not found: {args['path']}"
        # path.exists() is True for directories too — confirmed live across
        # projects/, pipeline_defs/, schemas/, and skills/ in one job, each
        # raising a raw "[Errno 21] Is a directory" instead of a message the
        # agent can act on (e.g. list the directory instead).
        if not path.is_file():
            return f"ERROR: {args['path']!r} is a directory, not a file"
        content = path.read_text(encoding="utf-8")
        if len(content) > READ_FILE_CHAR_CAP:
            content = content[:READ_FILE_CHAR_CAP] + f"\n\n[truncated — {len(content)} total chars]"
        return content

    elif name == "write_artifact":
        artifact_name = args.get("artifact_name")
        content = args.get("content")
        if not artifact_name:
            return "ERROR: write_artifact requires 'artifact_name' parameter"
        if content is None:
            return "ERROR: write_artifact requires 'content' parameter"
        if not _SAFE_ARTIFACT_NAME.match(artifact_name):
            return (
                f"ERROR: invalid artifact_name {artifact_name!r} — must contain only "
                "letters, numbers, underscores, and hyphens (no path separators or '..')"
            )
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out = artifacts_dir / f"{artifact_name}.json"
        out.write_text(json.dumps(content, ensure_ascii=False, indent=2))

        # Warn-only schema check — never blocks the write. The artifact is
        # already on disk by this point; a malformed artifact is still more
        # useful to the pipeline than no artifact at all, and a hard rejection
        # here would turn a schema gap into a stage failure the agent can't
        # recover from. This exists so a malformed write shows up as a visible
        # warning right here instead of its first sign of trouble being a
        # downstream KeyError/mystery several stages later.
        schema_warning: str | None = None
        try:
            from schemas.artifacts import validate_artifact
            validate_artifact(artifact_name, content)
        except FileNotFoundError:
            # No schema registered for this artifact_name (list_schemas()
            # only covers the canonical ~20 artifact types) — nothing to
            # validate against, not a validation failure.
            pass
        except Exception as e:
            # Covers jsonschema.ValidationError (the expected case) and any
            # other unexpected error surfaced while validating — all treated
            # the same way: surface it, don't let it interrupt the write.
            schema_warning = getattr(e, "message", None) or str(e)
            if len(schema_warning) > 300:
                schema_warning = schema_warning[:300] + "…"

        if emit_event:
            emit_event({
                "type": "artifact_written",
                "artifact": artifact_name,
                "path": str(out.relative_to(OM_ROOT)),
            })
            if schema_warning:
                emit_event({
                    "type": "warning",
                    "path": str(out.relative_to(OM_ROOT)),
                    "message": f"{artifact_name} written but failed schema validation: {schema_warning}",
                })

        if schema_warning:
            return f"Written to {out} (schema warning: {schema_warning})"
        return f"Written to {out}"

    elif name == "run_openmontage_tool":
        tool_name = args["tool_name"]
        inputs = args.get("inputs", {})

        if emit_event:
            emit_event({
                "type": "tool_call",
                "tool": tool_name,
                "summary": f"调用工具 {tool_name}",
                "inputs_preview": {k: str(v)[:80] for k, v in inputs.items()},
                # Surfaced separately from inputs_preview (which truncates to 80
                # chars and isn't reliably keyed by the frontend) so the live log
                # can show which model a generation call is actually using
                # without the operator having to hunt through inputs_preview.
                "model": inputs.get("model"),
            })

        from tools.tool_registry import registry
        # ensure_discovered() only actually re-scans the package tree once
        # per process lifetime (memoized via _discovered_packages) — calling
        # discover() directly here re-walked and re-imported every tools/
        # submodule on every single tool call, including the dozens per
        # stage a busy assets run makes.
        registry.ensure_discovered()
        tool = registry.get(tool_name)
        if not tool:
            return f"ERROR: Tool '{tool_name}' not found in registry"

        # Generic required-field guardrail — confirmed exploitable live: a
        # real agent call to video_compose omitted the tool's one
        # schema-required field ("operation") twice, and nothing rejected it
        # before tool.execute(inputs) was reached. Cheap check against the
        # tool's own declared input_schema, before any paid call is made.
        # `getattr(..., None) or {}` makes this a no-op for tools/test doubles
        # that don't define input_schema at all (e.g. FakeTool in
        # test_tool_bridge.py).
        required = (getattr(tool, "input_schema", None) or {}).get("required") or []
        missing = [f for f in required if f not in inputs]
        if missing:
            return (
                f"ERROR: {tool_name} call is missing required field(s): {missing}. "
                f"Required fields per input_schema: {required}. Re-check the "
                "tool's real input_schema before retrying — do not guess field names."
            )

        enforcement_error = _enforce_model_choice(tool_name, inputs, options)
        if enforcement_error:
            return enforcement_error

        compose_variant_error = _enforce_compose_variant_tag(tool, inputs, options)
        if compose_variant_error:
            return compose_variant_error

        if tool_name == "maas_tts":
            _apply_tts_emotion_defaults(inputs, options)

        # Brand voice default (roadmap 3.2): any TTS-capability call without
        # an explicit voice narrates with the brand kit's voice_id — same
        # gap-filling semantics as _apply_tts_emotion_defaults (a deliberate
        # per-line voice choice by the agent still wins).
        if tool.capability == "tts" and (options or {}).get("brand_voice_id") and "voice" not in inputs:
            inputs["voice"] = options["brand_voice_id"]

        # A caller doing an A/B variants run (options[...variants_key] set)
        # tags which branch a call belongs to — either explicitly via
        # inputs["variant"] (the only way compose/video_post calls can say
        # this, since they have no "model" of their own) or implicitly via
        # inputs["model"] for generation calls. Popped before the tool sees
        # `inputs` — it's a routing hint, not a tool parameter.
        variant = inputs.pop("variant", None) or inputs.get("model")
        variant_tag = f"_{variant_slug(variant)}" if variant else ""

        # Per-scene reroll (roadmap 2.3): a routing hint, not a tool param —
        # when true, the content-addressed cache below is bypassed so an
        # identical prompt genuinely regenerates (fresh uuid filename)
        # instead of returning the very asset the user just rejected.
        force_regenerate = bool(inputs.pop("force_regenerate", False))

        # Set output path if not specified.
        if "output_path" not in inputs:
            ext_map = {
                "video_generation": "mp4",
                "image_generation": "png",
                "tts": "mp3",
                "music_generation": "mp3",
                "audio_processing": "mp3",
                "video_post": "mp4",
            }
            ext = ext_map.get(tool.capability, "bin")

            # The final composed video is the pipeline deliverable — it must land
            # in renders/ so the runner and /media serving can find and play it.
            # Any other video_post op (trim, stitch) stays in assets/.
            is_final_compose = (
                tool.capability == "video_post"
                and inputs.get("operation", "compose") == "compose"
            )
            if is_final_compose:
                renders_dir = project_dir / "renders"
                renders_dir.mkdir(parents=True, exist_ok=True)
                # Plain "final.mp4" for the common single-render case (kept
                # byte-for-byte compatible with every existing job/URL that
                # already assumes this name). An A/B run doing N independent
                # compose calls needs the variant folded into the filename —
                # otherwise the second call's "final.mp4" silently clobbers
                # the first's, and only one variant would ever be watchable.
                filename = f"final{variant_tag}.mp4" if variant_tag else "final.mp4"
                target = renders_dir / filename
                # Generations are never silently clobbered (roadmap 2.5): a
                # re-render of the SAME filename (revise round, reject-loop
                # round) first moves the existing file into
                # renders/history/<mtime>_<name> — recoverable, and invisible
                # to the top-level renders/*.mp4 discovery glob so the newest
                # generation alone represents the deliverable.
                if target.is_file():
                    try:
                        history_dir = renders_dir / "history"
                        history_dir.mkdir(exist_ok=True)
                        stamp = time.strftime(
                            "%Y%m%d-%H%M%S", time.localtime(target.stat().st_mtime)
                        )
                        target.replace(history_dir / f"{stamp}_{filename}")
                    except OSError:
                        logger.warning("failed to archive previous render %s", target, exc_info=True)
                inputs = {**inputs, "output_path": str(target)}
            else:
                out_dir = project_dir / "assets" / tool.capability
                out_dir.mkdir(parents=True, exist_ok=True)
                # Content-addressed output naming (roadmap 2.1): the filename
                # suffix is BaseTool.idempotency_key(inputs) — a hash of the
                # tool's declared identity fields (prompt/model/duration/…).
                # Re-running a stage with unchanged inputs therefore lands on
                # the SAME path, and the cache check below returns the
                # existing file for free instead of paying for an identical
                # generation — "重跑一次 ¥50" becomes "¥2" (only what
                # actually changed regenerates). Falls back to a random
                # suffix when the tool declares no identity fields, when
                # none of them are present in this call (an all-None hash
                # would alias DIFFERENT calls onto one file), or when the
                # caller forces a reroll.
                key_fields = getattr(tool, "idempotency_key_fields", None) or []
                cache_key = None
                if not force_regenerate and key_fields and any(f in inputs for f in key_fields):
                    try:
                        cache_key = tool.idempotency_key(inputs)
                    except Exception:
                        cache_key = None
                unique = cache_key or uuid.uuid4().hex[:8]
                inputs = {**inputs, "output_path": str(out_dir / f"{tool_name}{variant_tag}_{unique}.{ext}")}

                cached_path = Path(inputs["output_path"])
                if cache_key and cached_path.is_file() and cached_path.stat().st_size > 0:
                    # Cache hit: identical inputs already produced this asset
                    # in a previous run/round. No budget check, no ledger
                    # entry, no paid call — reuse it verbatim.
                    if emit_event:
                        cached_event = {
                            "type": "asset_ready",
                            "tool": tool_name,
                            "path": str(cached_path),
                            "kind": tool.capability,
                            "model": inputs.get("model"),
                            "cached": True,
                            "cost_cny": 0.0,
                        }
                        try:
                            rel = cached_path.resolve().relative_to(project_dir.resolve())
                            cached_event["media_url"] = f"/media/{project_dir.name}/{rel.as_posix()}"
                        except (ValueError, OSError):
                            pass
                        emit_event(cached_event)
                    return json.dumps({
                        "success": True,
                        "cached": True,
                        "data": {
                            "cached": True,
                            "note": (
                                "Reused existing asset (content-addressed: identical "
                                "inputs already produced this file). No cost incurred. "
                                "Pass force_regenerate=true to genuinely regenerate."
                            ),
                        },
                        "artifacts": [str(cached_path)],
                        "cost_usd": 0.0,
                    })
        else:
            # The agent supplied its own output_path — re-root it under this
            # job's project_dir instead of trusting it verbatim. See
            # _anchor_output_path: a trusted relative/slug-prefixed path orphans
            # the asset outside the job tree (resolved against the server CWD),
            # which is exactly how a completed run produced real clips the
            # compose stage then couldn't find.
            anchored = _anchor_output_path(inputs["output_path"], project_dir, tool)
            anchored.parent.mkdir(parents=True, exist_ok=True)
            inputs = {**inputs, "output_path": str(anchored)}

        # Hard budget ceiling — pre-call check. Bounds total spend to <= budget
        # by refusing a paid call that would cross it, instead of letting a
        # single stage (e.g. assets) generate many clips past the ceiling before
        # the between-stages gate ever fires. Raises so _run_agent_stage unwinds
        # and the runner's event loop can own the human pause.
        est_cost = float(tool.estimate_cost(inputs) or 0.0)
        if budget_cny is not None and est_cost > 0:
            projected = base_cost + (sum(cost_accumulator) if cost_accumulator else 0.0) + est_cost
            if projected > budget_cny:
                if emit_event:
                    emit_event({
                        "type": "budget_precall_block",
                        "tool": tool_name,
                        "projected_cny": round(projected, 4),
                        "budget_cny": budget_cny,
                    })
                raise BudgetExceededError(
                    f"Paid call to {tool_name} (est ¥{est_cost:.2f}) would bring spend to "
                    f"¥{projected:.2f}, over budget ¥{budget_cny:.2f}",
                    tool_name=tool_name,
                    est_cost=est_cost,
                    projected_cny=projected,
                )

        # Ledger: estimate before, reconcile after (real CostTracker usage →
        # persists an itemized cost_log.json for budget governance/audit).
        entry_id = None
        if cost_tracker is not None:
            try:
                entry_id = cost_tracker.estimate(
                    tool_name,
                    inputs.get("operation", "run"),
                    # Reuse the budget gate's est_cost above rather than
                    # re-calling estimate_cost — an estimator that isn't
                    # perfectly pure would otherwise let the gate and the
                    # ledger record two different numbers for the same call.
                    est_cost,
                )
                cost_tracker.approve_tool(tool_name)
                cost_tracker.reserve(entry_id)   # OBSERVE mode never raises
            except Exception:
                logger.warning("CostTracker.estimate/reserve failed for %s", tool_name, exc_info=True)
                entry_id = None

        result = tool.execute(inputs)

        if cost_tracker is not None and entry_id is not None:
            try:
                cost_tracker.reconcile(
                    entry_id, float(result.cost_usd or 0.0), success=result.success
                )
            except Exception:
                logger.warning("CostTracker.reconcile failed for %s (entry %s)", tool_name, entry_id, exc_info=True)
                pass

        if result.success:
            # Record every completed paid call (append even 0.0 so the tally
            # reflects call count; the sum is what drives the CNY display).
            if cost_accumulator is not None and result.cost_usd is not None:
                cost_accumulator.append(float(result.cost_usd))
            # Selector calls already compute a full scored rationale
            # (selection_reason = ToolScore.explain(), provider_score,
            # alternatives_considered) — but nothing persisted it, so the
            # decision rail showed nothing for auto-routed provider picks
            # (roadmap 1.4: "scoring.explain() 从不持久化进 decision_log").
            # Append it to the project's decision_log artifact here, at the
            # single choke point every selector-routed call passes through.
            if "selected_tool" in (result.data or {}) and "selection_reason" in (result.data or {}):
                _append_selector_decision(project_dir, tool_name, tool.capability, result.data)
            if emit_event and result.artifacts:
                last_artifact_idx = len(result.artifacts) - 1
                for idx, artifact_path in enumerate(result.artifacts):
                    event = {
                        "type": "asset_ready",
                        "tool": tool_name,
                        "path": artifact_path,
                        "kind": tool.capability,
                        # inputs["model"] reflects the FULLY RESOLVED model (after
                        # _enforce_model_choice's autofill, if any ran) — more
                        # trustworthy than the tool_call event's pre-enforcement
                        # value for "what actually generated this asset". Despite
                        # the field's name, cost_usd is already CNY for every MaaS
                        # tool (see maas_video.py's estimate_cost docstring) — no
                        # conversion needed, matching how cost_accumulator/
                        # job.cost_cny already treat it.
                        "model": inputs.get("model"),
                    }
                    # The whole call's cost is charged once, not once per
                    # artifact — the ledger (cost_accumulator/CostTracker)
                    # already accumulates it correctly exactly once above.
                    # Repeating cost_cny identically on every artifact_ready
                    # event (e.g. a TTS call returning both an audio file and
                    # a metadata file) misleadingly read as if the same money
                    # was spent once per artifact. Only the LAST artifact for
                    # this call carries cost_cny.
                    if idx == last_artifact_idx:
                        event["cost_cny"] = result.cost_usd
                    # Browser-servable URL for the live filmstrip (roadmap
                    # 1.1) — only assets inside the project workspace are
                    # reachable via the /media static mount; anything else
                    # (absolute temp paths etc.) just omits the field.
                    try:
                        rel = Path(artifact_path).resolve().relative_to(project_dir.resolve())
                        event["media_url"] = f"/media/{project_dir.name}/{rel.as_posix()}"
                    except (ValueError, OSError):
                        pass
                    emit_event(event)
            return json.dumps({
                "success": True,
                "data": result.data,
                "artifacts": result.artifacts,
                "cost_usd": result.cost_usd,
            })
        else:
            return json.dumps({"success": False, "error": result.error})

    return f"ERROR: Unknown tool: {name}"
