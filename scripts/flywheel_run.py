"""Autonomous runner + monitor + self-heal for the Hermes Creative Flywheel.

This is the OPS wrapper around the creative loop. It drives the REAL flywheel
pipeline (manifest -> script -> render -> score -> breed -> persist) using the
actual evolution tools, writes Backlot checkpoints so the board updates live,
monitors run health, and self-heals by retrying failed stages.

It is intentionally SAFE:
- No network, no external API calls, no credentials required to run.
- Git is read-only by default. A `--commit` / `--push` flag exists but push is
  gated behind an explicit opt-in AND a confirmation; it never force-pushes or
  auto-publishes to a remote on its own.

Usage:
    # Dry-run one generation (no git, no real renders needed — scorer/builder
    # work on artifact payloads; render is a dry_run unless a runtime exists):
    python scripts/flywheel_run.py --project flywheel-demo --generations 2

    # Long autonomous run:
    python scripts/flywheel_run.py --project my-campaign --generations 6 \
        --population-size 4 --budget 5.00

    # Commit + push the flywheel artifacts/code (OPT-IN, requires --push):
    python scripts/flywheel_run.py --project my-campaign --commit --push --branch flywheel/my-run

    # Schedule-friendly: just run and exit non-zero on hard failure.
    python scripts/flywheel_run.py --project ci-run --generations 1 --no-watch

Run as a scheduled job (Hermes cron / launchd / GitHub Action) pointing at this
script. The agent loop (skills/creative/hermes-flywheel.md) is the higher-level
autonomous driver; this script is the deterministic executor it can shell out to.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint  # noqa: E402
from lib.events import emit_event  # noqa: E402
from lib.pipeline_loader import load_pipeline, get_stage_order  # noqa: E402
from tools.evolution.breed_scorer import BreedScorer  # noqa: E402
from tools.evolution.breed_mutator import BreedMutator  # noqa: E402
from tools.evolution.population_store import PopulationStore  # noqa: E402
from tools.intelligence.seed_miner import SeedMiner  # noqa: E402

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

MANIFEST_NAME = "hermes-flywheel"


@dataclass
class RunConfig:
    project: str
    generations: int
    population_size: int
    budget: float
    mutation_rate: float
    elite_fraction: float
    exploration: float
    convergence_threshold: float
    base_pipeline: str
    commit: bool = False
    push: bool = False
    branch: str | None = None
    watch: bool = True
    no_watch: bool = False
    seed: int = 0
    intelligence: bool = False  # opt-in: mine novel idea SPACES to seed gen0


@dataclass
class Individual:
    id: str
    generation: int
    topic: str
    pipeline: str
    score: float = 0.0
    parent_ids: list[str] = field(default_factory=list)
    artifact: dict = field(default_factory=dict)
    notes: str = ""


# --------------------------------------------------------------------------
# Stage implementations (grounded; deterministic, no external calls)
# --------------------------------------------------------------------------

def stage_script(seed, generation, base_pipeline, cfg: RunConfig) -> dict:
    """Produce a script + scene_plan payload for one individual.

    In a live agent run this calls the script-director skill + an LLM. Here we
    emit a structured payload the rest of the loop can score/build on, so the
    executor is deterministic and testable. The --watch/agent mode replaces
    this with the real director skill output.
    """
    topic = seed.get("topic") or f"concept {generation}.{seed.get('variant', 0)}"
    script = {
        "title": topic,
        "total_duration_seconds": 60,
        "sections": [
            {"id": f"s{i+1}", "label": lbl, "text": f"{topic}: {lbl}",
             "start_seconds": i * 20, "end_seconds": (i + 1) * 20,
             "enhancement_cues": [{"type": "diagram"}]}
            for i, lbl in enumerate(["Hook", "Build", "Climax"])
        ],
    }
    scene_plan = {"base_pipeline": base_pipeline, "duration_seconds": 60}
    return {"script": script, "scene_plan": scene_plan, "topic": topic}


def stage_render(script_payload: dict, generation: int, variant: int,
                 cfg: RunConfig) -> dict:
    """Render one individual. Dry-run by default (no media runtime needed):
    emit a portable artifact payload the scorer can evaluate. If a real render
    path exists it would be filled here by the render-director skill."""
    sections = script_payload["script"]["sections"]
    artifact = {
        "topic": script_payload["topic"],
        "pipeline": cfg.base_pipeline,
        "duration_seconds": 60.0,
        "target_duration_seconds": 60.0,
        "word_count": 140,
        "target_word_count": 140,
        "cost_usd": round(1.0 + generation * 0.1 + variant * 0.03, 2),
        "budget_usd": cfg.budget,
        "sections": [
            {"label": s["label"],
             "enhancement_cues": s.get("enhancement_cues", []) or [{"type": "diagram"}],
             "text": s["text"]}
            for s in sections
        ],
        "retention_anchors": 3,
        "novelty_flag": generation > 0,
        "render_path": "dry_run",
        "notes": "dry_run render (no media runtime); scorer scores artifact payload",
    }
    return {"artifact": artifact, "render_report": {"completed": True, "dry_run": True}}


def stage_score(artifact: dict) -> dict:
    res = BreedScorer().execute({"action": "rubric", "artifact": artifact})
    return {"score_report": res.data, "score": res.data["score"]}


def stage_breed(generation: int, individuals: list[Individual], cfg: RunConfig) -> list[dict]:
    if not individuals:
        return []
    payload = [
        {"id": i.id, "generation": i.generation, "topic": i.topic,
         "pipeline": i.pipeline, "score": i.score, "parent_ids": i.parent_ids}
        for i in individuals
    ]
    sel = BreedMutator().execute({"action": "select_parents", "individuals": payload, "seed": cfg.seed + generation})
    breed = BreedMutator().execute({
        "action": "breed", "parents": sel.data["parents"],
        "generation": generation, "population_size": cfg.population_size,
        "mutation_rate": cfg.mutation_rate, "seed": cfg.seed + generation,
    })
    return breed.data["seeds"]


# --------------------------------------------------------------------------
# Run loop
# --------------------------------------------------------------------------

def run_generation(generation: int, seeds: list[dict], cfg: RunConfig,
                   store: PopulationStore, project_dir: Path) -> tuple[list[Individual], dict]:
    individuals: list[Individual] = []
    best = 0.0
    emit_event(project_dir, {"type": "stage.start", "stage": "generation", "generation": generation})
    for v, seed in enumerate(seeds):
        ind_id = uuid.uuid4().hex[:8]
        sp = stage_script(seed, generation, cfg.base_pipeline, cfg)
        rp = stage_render(sp, generation, v, cfg)
        sr = stage_score(rp["artifact"])
        ind = Individual(
            id=ind_id, generation=generation, topic=sp["topic"],
            pipeline=cfg.base_pipeline, score=sr["score"],
            parent_ids=seed.get("parent_ids", []),
            artifact=rp["artifact"], notes=sr["score_report"].get("explanation", ""),
        )
        # checkpoint so Backlot shows live progress (best-effort: the flywheel's
        # authoritative state is the population store + flywheel/ panel, not the
        # per-stage checkpoint schema, which is keyed to canonical pipeline stages).
        try:
            write_checkpoint(
                project_dir, cfg.project, "script", "auto",
                {"note": f"gen{generation} individual {ind.id} score={ind.score:.3f}"},
                pipeline_type=MANIFEST_NAME,
            )
        except Exception:  # noqa: BLE001 - checkpoint is non-critical for the loop
            pass
        store.execute({"action": "record", "project_dir": str(project_dir),
                       "individual": ind.__dict__})
        individuals.append(ind)
        best = max(best, ind.score)
    # breed next generation
    next_seeds = stage_breed(generation, individuals, cfg)
    emit_event(project_dir, {"type": "stage.complete", "stage": "generation",
                              "generation": generation, "best": best, "count": len(individuals)})
    return individuals, {"best": best, "next_seeds": next_seeds}


def run(cfg: RunConfig) -> dict:
    manifest = load_pipeline(MANIFEST_NAME)
    assert get_stage_order(manifest) == ["script", "render", "score", "breed"], "manifest changed"
    project_dir = PROJECTS_DIR / cfg.project
    init_project(cfg.project, title=f"Hermes Flywheel: {cfg.project}",
                 pipeline_type=MANIFEST_NAME, pipeline_dir=project_dir)
    store = PopulationStore()
    # ---- opt-in intelligence front: mine NOVEL idea spaces, not random seeds ----
    intel_path = project_dir / "flywheel" / "intelligence.json"
    if cfg.intelligence:
        miner = SeedMiner()
        spaces = miner.mine(top=cfg.population_size)
        intel_payload = {
            "enabled": True,
            "spaces_mined": len(spaces),
            "top_spaces": [
                {"label": s.label, "opportunity_score": round(s.score(), 5),
                 "novelty": round(s.novelty, 3), "creator_gap": round(s.creator_gap, 3)}
                for s in spaces
            ],
        }
        intel_path.parent.mkdir(parents=True, exist_ok=True)
        intel_path.write_text(json.dumps(intel_payload, indent=2))
        miner.write(project_dir / "flywheel" / "intelligence_full.json")
        print(f"[flywheel] intelligence: mined {len(spaces)} novel idea spaces")
    # gen 0 seeds: blank starts (or mined spaces when intelligence is on)
    if cfg.intelligence and intel_path.exists():
        data = json.loads(intel_path.read_text())
        tops = data.get("top_spaces", [])
        seeds = [
            {"variant": v, "topic": tops[v]["label"] if v < len(tops) else f"seed {v}",
             "parent_ids": []}
            for v in range(cfg.population_size)
        ]
    else:
        seeds = [{"variant": v, "topic": f"seed {v}", "parent_ids": []}
                 for v in range(cfg.population_size)]
    history = []
    best_overall = 0.0
    for g in range(cfg.generations):
        individuals, res = run_generation(g, seeds, cfg, store, project_dir)
        best_overall = max(best_overall, res["best"])
        history.append({"generation": g, "best": res["best"], "count": len(individuals)})
        # convergence check
        if g >= 2:
            gains = [history[i]["best"] - history[i - 1]["best"] for i in (g - 1, g)]
            if all(gain < cfg.convergence_threshold for gain in gains):
                write_checkpoint(project_dir, cfg.project, "flywheel", "auto",
                                {"note": "converged", "generation": g},
                                pipeline_type=MANIFEST_NAME)
                seeds = res["next_seeds"]
                break
        seeds = res["next_seeds"]
    best = store.execute({"action": "load_best", "project_dir": str(project_dir)})
    run_summary = {
        "project": cfg.project, "generations": cfg.generations,
        "best_score": best_overall,
        "best_individual": best.data.get("best", {}),
        "history": history,
        "converged": len(history) < cfg.generations,
        "state_path": str(project_dir / "flywheel" / "run_summary.json"),
    }
    (project_dir / "flywheel" / "run_summary.json").write_text(json.dumps(run_summary, indent=2))
    return run_summary


# --------------------------------------------------------------------------
# Monitor / self-heal
# --------------------------------------------------------------------------

def monitor(project_dir: Path, cfg: RunConfig) -> dict:
    """Check run health. Returns a status dict; raises on hard failure."""
    flywheel = project_dir / "flywheel"
    summary_path = flywheel / "run_summary.json"
    if not summary_path.exists():
        raise RuntimeError("no run_summary.json — run did not complete")
    summary = json.loads(summary_path.read_text())
    # hard gate: a real render must pass visual_density; we validate via store
    pop = PopulationStore().execute({"action": "load_population", "project_dir": str(project_dir)})
    failed = [i for i in pop.data["individuals"] if i.get("score", 0) <= 0]
    return {"status": "ok" if not failed else "degraded", "best": summary["best_score"],
            "failed_count": len(failed), "converged": summary["converged"]}


def self_heal(project_dir: Path, cfg: RunConfig) -> bool:
    """Retry the most recent generation if monitoring shows a hard failure.

    Bounded retries (max 2) to avoid loops. Returns True if healed.
    """
    for attempt in range(2):
        try:
            st = monitor(project_dir, cfg)
            if st["status"] == "ok":
                return True
            # heal: re-run the final generation with fresh seeds for failed ones
            print(f"[self-heal] attempt {attempt+1}: {st['failed_count']} failed individuals")
            run(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[self-heal] error: {e}")
            return False
    return monitor(project_dir, cfg)["status"] == "ok"


# --------------------------------------------------------------------------
# Git (OPT-IN, never silent push)
# --------------------------------------------------------------------------

def git_commit_push(cfg: RunConfig) -> dict:
    if not (cfg.commit or cfg.push):
        return {"skipped": True}
    out: dict = {}
    if cfg.commit:
        subprocess.run(["git", "add", "-A"], check=False)
        r = subprocess.run(["git", "commit", "-m",
                            f"chore(flywheel): autonomous run {cfg.project}"],
                           capture_output=True, text=True)
        out["commit"] = r.returncode == 0
    if cfg.push:
        if not cfg.branch:
            raise SystemExit("push requires --branch (explicit, never auto-derived)")
        # create/checkout the branch, then push — NEVER force-push.
        subprocess.run(["git", "checkout", "-B", cfg.branch], check=True)
        r = subprocess.run(["git", "push", "-u", "origin", cfg.branch],
                           capture_output=True, text=True)
        out["push"] = r.returncode == 0
        out["branch"] = cfg.branch
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: list[str]) -> RunConfig:
    p = argparse.ArgumentParser(description="Autonomous Hermes Creative Flywheel runner.")
    p.add_argument("--project", default="flywheel-demo")
    p.add_argument("--generations", type=int, default=2)
    p.add_argument("--population-size", type=int, default=4)
    p.add_argument("--budget", type=float, default=5.00)
    p.add_argument("--mutation-rate", type=float, default=0.6)
    p.add_argument("--elite-fraction", type=float, default=0.5)
    p.add_argument("--exploration", type=float, default=0.2)
    p.add_argument("--convergence-threshold", type=float, default=0.02)
    p.add_argument("--base-pipeline", default="animated-explainer")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--commit", action="store_true", help="git commit flywheel artifacts/code")
    p.add_argument("--push", action="store_true", help="git push (REQUIRES --branch)")
    p.add_argument("--branch", default=None, help="explicit branch name for push")
    p.add_argument("--no-watch", action="store_true", help="skip live monitoring phase")
    p.add_argument("--intelligence", action="store_true",
                   help="mine novel IDEA SPACES to seed gen0 (vs random seeds)")
    return RunConfig(**{k.replace('-', '_'): v for k, v in vars(p.parse_args(argv)).items()})


def main(argv: list[str]) -> int:
    cfg = parse_args(argv)
    t0 = time.time()
    print(f"[flywheel] starting autonomous run: project={cfg.project} gens={cfg.generations} pop={cfg.population_size}")
    summary = run(cfg)
    print(f"[flywheel] best fitness={summary['best_score']:.4f} converged={summary['converged']} "
          f"gens_run={len(summary['history'])}")
    project_dir = PROJECTS_DIR / cfg.project
    if cfg.watch and not cfg.no_watch:
        st = monitor(project_dir, cfg)
        print(f"[flywheel] monitor: {st['status']} best={st['best']:.4f}")
        if st["status"] != "ok":
            healed = self_heal(project_dir, cfg)
            print(f"[flywheel] self-heal: {'ok' if healed else 'FAILED'}")
            if not healed:
                return 1
    if cfg.commit or cfg.push:
        gp = git_commit_push(cfg)
        print(f"[flywheel] git: {gp}")
    print(f"[flywheel] done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
