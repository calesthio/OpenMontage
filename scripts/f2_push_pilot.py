#!/usr/bin/env python3
"""F2: push the 214-sentence pilot to ONE Kaggle T4 kernel (locked S15 recipe).

Input:  docs/openmontage/pilot/script.md  (S001..S214, each with one PROMPT line)
Output: /tmp/f2/jobs/<job_id>/ (run.py + kernel-metadata.json + prompts.json)

Recipe (frozen in docs/openmontage/image_gen/recipe_dreamshaper_xl_1_0.json):
  Lykon/dreamshaper-xl-1-0 @ 41e6644752a8c9aa63930e6043c4fd83c7708420,
  StableDiffusionXLPipeline, fp16, DEISMultistepScheduler, 25 steps, CFG 5.5,
  1024x1024, stock VAE, cuda, no offload, no bf16, no bitsandbytes.

Prompt = <S15 graphic-novel-ink style verbatim> + <scene text from script.md>
         + <anatomy sentence, creature scenes only> + <S15 tail verbatim>.

Usage:
  python scripts/f2_push_pilot.py --dry-run     # validate, no push
  python scripts/f2_push_pilot.py              # push the kernel
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

KERNEL_SLUG = "forts845/of-bridge-runner"
JOBS_DIR = Path("/tmp/f2/jobs")
SCRIPT = REPO / "docs/openmontage/pilot/script.md"

MODEL_ID = "Lykon/dreamshaper-xl-1-0"
REVISION = "41e6644752a8c9aa63930e6043c4fd83c7708420"
MODEL_KEY = "dreamshaper-xl-1-0"
OUTPUT_DIR = "f2_pilot_dreamshaper-xl-1-0"
STEPS = 25
CFG = 5.5
SEED = 1001
WIDTH = HEIGHT = 1024
MAX_WALL = 7200  # 2 h hard cap inside the kernel (waiting rule: safety stop only)

STYLE = ("bold graphic-novel ink illustration, thick outer contour, sparse "
         "hatching, large flat shadow masses, limited halftone, night ink, "
         "deep sea, electric teal, pale bone, one coral accent")
TAIL = ("stylized, non-photorealistic, empty low-detail lower fifth for "
        "captions, no text")
NEGATIVE = ("photorealistic, photo, glossy 3D render, mirror reflections, "
            "text, letters, watermark, signature, logo, extra limbs, fused "
            "anatomy, duplicated creature, cluttered bottom edge")
ANATOMY_GRAZER = "exactly six separate tendrils, two pairs of fins"
ANATOMY_DRIFTER = "no legs, no arms, one continuous undulating fin, wide filter mouth"

SENT_RE = re.compile(r"^S(\d{3})\s+\[([^\]]+)\]\s+(.*\S)\s*$")


def parse_script(path: Path) -> List[Dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: List[Dict[str, str]] = []
    i = 0
    while i < len(lines):
        m = SENT_RE.match(lines[i])
        if m:
            prompt = ""
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("PROMPT:"):
                prompt = lines[i + 1].split("PROMPT:", 1)[1].strip()
            if not prompt:
                raise SystemExit(f"BLOCKED: S{m.group(1)} has no PROMPT line")
            rows.append({"sentence_id": f"S{m.group(1)}", "claim": m.group(2),
                         "text": m.group(3), "scene": prompt})
            i += 2
            continue
        i += 1
    if not rows:
        raise SystemExit("BLOCKED: no sentences parsed from the script")
    ids = [r["sentence_id"] for r in rows]
    if ids != [f"S{n:03d}" for n in range(1, len(rows) + 1)]:
        raise SystemExit("BLOCKED: sentence ids are not sequential")
    return rows


def build_prompt(scene: str) -> str:
    """Style + scene + anatomy (if the scene depicts a creature) + tail."""
    parts = [STYLE + "."]
    parts.append(scene.rstrip(".") + ".")
    low = scene.lower()
    if "grazer" in low and ANATOMY_GRAZER not in low:
        parts.append(f"The vent grazer has {ANATOMY_GRAZER}.")
    if "drifter" in low and "limbless" not in low and ANATOMY_DRIFTER not in low:
        parts.append(f"The filter drifter is limbless: {ANATOMY_DRIFTER}.")
    parts.append(TAIL + ".")
    return " ".join(parts)


def build_job(rows: List[Dict[str, str]], attempt: int, seed: int = SEED) -> Dict[str, Any]:
    renders = []
    for r in rows:
        renders.append({
            "render_id": f"f2_{r['sentence_id']}",
            "scene_id": r["sentence_id"],
            "style": "graphic-novel-ink",
            "prompt": build_prompt(r["scene"]),
            "negative_prompt": NEGATIVE,
            "steps": STEPS,
            "guidance_scale": CFG,
            "seed": seed,
            "width": WIDTH,
            "height": HEIGHT,
        })
    return {
        "job_id": f"f2-pilot-{attempt}",
        "attempt": attempt,
        "kind": "pilot_f2",
        "model": MODEL_KEY,
        "model_id": MODEL_ID,
        "revision": REVISION,
        "output_dir": OUTPUT_DIR,
        "width": WIDTH,
        "height": HEIGHT,
        "dtype": "float16",
        "bf16": False,
        "bitsandbytes": False,
        "cpu_offload": False,
        "steps": STEPS,
        "guidance": CFG,
        "scheduler": {"class": "DEISMultistepScheduler", "kwargs": {}},
        "max_wall_seconds": MAX_WALL,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "renders": renders,
        "wide_scenes": [],
        "model_config": {
            "pipeline_candidates": ["StableDiffusionXLPipeline",
                                    "AutoPipelineForText2Image"],
            "load_config": {
                "offload": False,
                "low_cpu_mem_usage": None,
                "extra_kwargs": {},
                "guidance_override": CFG,
                "scheduler": {"class": "DEISMultistepScheduler", "kwargs": {}},
            },
            "install_ladder": ["released_037_x4", "released_037_x5",
                               "released_041_x5_ao", "git_main_x4"],
        },
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--seed", type=int, default=SEED,
                    help="override the seed (retries use 2027)")
    ap.add_argument("--only", default="",
                    help="comma-separated sentence ids to re-render (e.g. S012,S045)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=int, default=10800)
    args = ap.parse_args(argv)

    rows = parse_script(SCRIPT)
    if args.only:
        want = {s.strip().upper() for s in args.only.split(",") if s.strip()}
        rows = [r for r in rows if r["sentence_id"] in want]
        missing = want - {r["sentence_id"] for r in rows}
        if missing:
            raise SystemExit(f"BLOCKED: unknown sentence ids {sorted(missing)}")
    job = build_job(rows, args.attempt, args.seed)

    lens = [len(r["prompt"]) for r in job["renders"]]
    print(f"sentences: {len(rows)} | prompts: {len(lens)} | "
          f"chars min/median/max: {min(lens)}/{sorted(lens)[len(lens)//2]}/{max(lens)}")
    for r in job["renders"]:
        if not r["prompt"].endswith(TAIL + "."):
            raise SystemExit(f"BLOCKED: {r['render_id']} prompt lacks the locked tail")
        if len(r["prompt"]) > 1200:
            raise SystemExit(f"BLOCKED: {r['render_id']} prompt over 1200 chars")

    work = JOBS_DIR / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)
    audit = {
        "job_id": job["job_id"], "created_utc": job["created_utc"],
        "model_id": MODEL_ID, "revision": REVISION, "steps": STEPS,
        "guidance_scale": CFG, "seed": args.seed, "width": WIDTH, "height": HEIGHT,
        "style": STYLE, "tail": TAIL, "negative_prompt": NEGATIVE,
        "anatomy_grazer": ANATOMY_GRAZER, "anatomy_drifter": ANATOMY_DRIFTER,
        "note": ("SDXL CLIP truncates at 77 tokens per encoder; the verbatim S15 "
                 "style string and tail are kept so this batch matches the "
                 "measured S15 baseline rather than silently shortening it."),
        "renders": [{"render_id": r["render_id"], "sentence_id": r["scene_id"],
                     "prompt": r["prompt"]} for r in job["renders"]],
    }
    (work / "prompts.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"prompts audit: {work / 'prompts.json'}")

    if args.dry_run:
        print("dry run: not pushing")
        return 0

    engine = (REPO / "tools/kaggle_bridge/s15_style_lock_run.py").read_text(encoding="utf-8")
    marker = "JOB_EMBEDDED = None"
    if marker not in engine:
        raise SystemExit("BLOCKED: JOB_EMBEDDED marker missing in the runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    run_text = engine.replace(marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)
    if run_text.count('if __name__ == "__main__":') != 1:
        raise SystemExit("BLOCKED: composed runner must keep exactly one __main__ guard")
    (work / "run.py").write_text(run_text, encoding="utf-8")

    bridge = KaggleBridgeTool()
    bj = bridge.execute({
        "command": "build_job_folder", "job_folder": str(work),
        "job_id": job["job_id"], "kernel_slug": KERNEL_SLUG, "job": job,
        "run_py": run_text, "enable_gpu": True, "enable_internet": True,
    })
    if not bj.success:
        print(bj.error, file=sys.stderr)
        return 1
    print(f"job folder: {work}")

    push = bridge.execute({
        "command": "push", "job_folder": str(work), "kernel_slug": KERNEL_SLUG,
        "timeout": args.timeout, "accelerator": "gpu", "max_retries": 3,
    })
    if not push.success:
        print(push.error, file=sys.stderr)
        return 1
    print(f"PUSHED {KERNEL_SLUG} job_id={job['job_id']} timeout={args.timeout}s")
    print(f"status: kaggle kernels status {KERNEL_SLUG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
