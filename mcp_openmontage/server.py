"""Hermes MCP server for OpenMontage — agentic integration surface.

Exposes the OpenMontage tool registry + the Hermes Creative Flywheel evolution
tools to any MCP-capable client (the Hermes agent, Claude, Cursor, etc.) so the
flywheel can be driven autonomously from outside the repo.

Tools exposed:
  om_list_pipelines        -> list pipeline manifests
  om_load_pipeline         -> load + validate a manifest (returns stages/skills)
  om_run_stage             -> execute one pipeline stage's tool(s) (generic pass-through)
  om_score_artifact        -> breed_scorer.rubric / .compare
  om_breed                 -> breed_mutator.select_parents / .breed
  om_population            -> population_store record/load/state
  om_backlot_state         -> read a project's Backlot events + flywheel state

Resources:
  openmontage://pipelines/<name>   -> the raw manifest YAML
  openmontage://registry            -> full tool support envelope

Run:
  python -m mcp_openmontage.server
  (or: mcp dev mcp_openmontage/server.py)

Requires: `pip install "mcp>=1.0"` and the OpenMontage requirements.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

try:
    from mcp.server import FastMCP
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "MCP SDK not installed. Run: pip install 'mcp>=1.0' "
        "(OpenMontage needs Python >=3.10). Original error: %r" % (exc,)
    )

# Make the repo root importable so tools/* and lib/* resolve.
_REPO_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.tool_registry import ToolRegistry  # noqa: E402
from tools.evolution.breed_scorer import BreedScorer  # noqa: E402
from tools.evolution.breed_mutator import BreedMutator  # noqa: E402
from tools.evolution.population_store import PopulationStore  # noqa: E402
from lib.pipeline_loader import (  # noqa: E402
    load_pipeline,
    list_pipelines,
    get_stage_order,
    get_stage_skill,
)
from lib.events import read_events  # noqa: E402

mcp = FastMCP("openmontage-hermes-flywheel")

# Shared registry instance (lazy-discovered on first use).
_REGISTRY: Optional[ToolRegistry] = None


def _registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
        _REGISTRY.discover("tools")
    return _REGISTRY


def _tool_instance(cls) -> Any:
    """Instantiate one of our evolution tools (they take no init args)."""
    return cls()


# ---------------------------------------------------------------------------
# Resource: pipeline manifests + registry envelope
# ---------------------------------------------------------------------------

@mcp.resource("openmontage://pipelines/{name}")
def pipeline_manifest_resource(name: str) -> str:
    """Raw pipeline manifest YAML for `name`."""
    manifest_path = _REPO_ROOT / "pipeline_defs" / f"{name}.yaml"
    if not manifest_path.exists():
        return f"# pipeline not found: {name}"
    return manifest_path.read_text(encoding="utf-8")


@mcp.resource("openmontage://registry")
def registry_resource() -> str:
    """Full tool support envelope as JSON."""
    return json.dumps(_registry().support_envelope(), indent=2, default=str)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def om_list_pipelines() -> str:
    """List all available OpenMontage pipeline manifests by name."""
    return json.dumps({"pipelines": list_pipelines()}, default=str)


@mcp.tool()
def om_load_pipeline(name: str) -> str:
    """Load and validate a pipeline manifest; return stages, skills, order.

    Args:
        name: pipeline name (e.g. 'hermes-flywheel', 'animated-explainer').
    """
    try:
        manifest = load_pipeline(name)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, default=str)
    return json.dumps(
        {
            "name": manifest.get("name"),
            "description": manifest.get("description"),
            "stages": get_stage_order(manifest),
            "stage_skills": {
                s["name"]: get_stage_skill(manifest, s["name"])
                for s in manifest.get("stages", [])
            },
            "orchestration": manifest.get("orchestration"),
            "metadata": manifest.get("metadata"),
        },
        default=str,
    )


@mcp.tool()
def om_run_stage(pipeline: str, stage: str, project_dir: str, inputs: str = "{}") -> str:
    """Execute one pipeline stage's required tools against a project.

    This is a generic pass-through: it loads the manifest, finds the stage's
    required/optional tools, and runs each available tool's execute() with the
    provided inputs. The driving agent is expected to have run the stage
    director skill first (the intelligence is in the skills, not here).

    Args:
        pipeline: pipeline name.
        stage: stage name (e.g. 'script', 'render', 'score', 'breed').
        project_dir: Backlot project directory (projects/<name>).
        inputs: JSON string of tool inputs.
    """
    try:
        manifest = load_pipeline(pipeline)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, default=str)
    stage_def = next((s for s in manifest.get("stages", []) if s["name"] == stage), None)
    if stage_def is None:
        return json.dumps({"error": f"stage {stage!r} not in {pipeline}"}, default=str)
    tool_names = list(
        stage_def.get("required_tools", [])
        + stage_def.get("optional_tools", [])
        + stage_def.get("tools_available", [])
    )
    try:
        parsed = json.loads(inputs) if inputs else {}
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"bad inputs JSON: {exc}"}, default=str)

    reg = _registry()
    results = {}
    for tname in dict.fromkeys(tool_names):  # dedupe, preserve order
        tool = reg.get(tname)
        if tool is None:
            results[tname] = {"status": "not_registered"}
            continue
        try:
            res = tool.execute(parsed)
            results[tname] = {
                "success": getattr(res, "success", None),
                "data": getattr(res, "data", None),
                "error": getattr(res, "error", None),
                "cost_usd": getattr(res, "cost_usd", None),
            }
        except Exception as exc:
            results[tname] = {"status": "error", "error": str(exc)}
    return json.dumps(
        {"stage": stage, "tools_run": list(results.keys()), "results": results},
        default=str,
    )


@mcp.tool()
def om_score_artifact(artifact: str, action: str = "rubric", baseline: str = "null") -> str:
    """Score a rendered individual with the breed_scorer fitness function.

    Args:
        artifact: JSON string of the artifact (see breed_scorer docstring).
        action: 'rubric' (score one) or 'compare' (score vs baseline).
        baseline: JSON string of baseline artifact (for action='compare').
    """
    try:
        art = json.loads(artifact)
        base = json.loads(baseline) if baseline and baseline != "null" else None
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"bad JSON: {exc}"}, default=str)
    scorer = _tool_instance(BreedScorer)
    res = scorer.execute({"action": action, "artifact": art, "baseline": base})
    return json.dumps(
        {"success": res.success, "data": res.data, "error": res.error}, default=str
    )


@mcp.tool()
def om_breed(
    action: str,
    individuals: str = "null",
    generation: int = 0,
    population_size: int = 4,
    seed: int = 0,
    parents: str = "null",
) -> str:
    """Select parents / breed next-generation seeds with breed_mutator.

    Args:
        action: 'select_parents' or 'breed'.
        individuals: JSON string of scored individuals (for select_parents).
        generation: generation number these came from.
        population_size: variants to emit (breed).
        seed: RNG seed for reproducibility.
        parents: JSON string of pre-selected parents (breed, optional).
    """
    try:
        inds = json.loads(individuals) if individuals and individuals != "null" else None
        pars = json.loads(parents) if parents and parents != "null" else None
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"bad JSON: {exc}"}, default=str)
    mutator = _tool_instance(BreedMutator)
    res = mutator.execute(
        {
            "action": action,
            "individuals": inds,
            "generation": generation,
            "population_size": population_size,
            "seed": seed,
            "parents": pars,
        }
    )
    return json.dumps(
        {"success": res.success, "data": res.data, "error": res.error}, default=str
    )


@mcp.tool()
def om_population(project_dir: str, action: str, individual: str = "null",
                  generation: int = 0, top_k: int = 0) -> str:
    """Persist / load the evolutionary population via population_store.

    Args:
        project_dir: Backlot project directory.
        action: record | load_generation | load_population | load_best | state.
        individual: JSON string individual (record).
        generation: generation number (load_generation).
        top_k: return top-K (load_population / load_best; 0 = all).
    """
    try:
        ind = json.loads(individual) if individual and individual != "null" else None
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"bad JSON: {exc}"}, default=str)
    store = _tool_instance(PopulationStore)
    res = store.execute(
        {
            "action": action,
            "project_dir": project_dir,
            "individual": ind,
            "generation": generation,
            "top_k": top_k or None,
        }
    )
    return json.dumps(
        {"success": res.success, "data": res.data, "error": res.error}, default=str
    )


@mcp.tool()
def om_backlot_state(project_dir: str, limit: int = 50) -> str:
    """Read a project's Backlot activity events + flywheel state.

    Args:
        project_dir: Backlot project directory.
        limit: max events to return (most recent).
    """
    events = read_events(project_dir, limit=limit)
    flywheel_dir = Path(project_dir) / "flywheel"
    state_path = flywheel_dir / "flywheel_state.json"
    state = None
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = None
    return json.dumps(
        {"events": events, "flywheel_state": state}, default=str
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
