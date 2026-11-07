#!/usr/bin/env python3
"""S1-1 push: build + push the Z-Image-Turbo Kaggle job (one model, one run).

Reads KAGGLE_API_TOKEN from the environment via the kaggle CLI only; never
prints, logs, or commits the token. Builds the job folder under /tmp/kilo
(nothing committed), pushes to fortr845/openmontage-runner with enable_gpu +
enable_internet (diffusers from source + HF weights need internet), then
records SUBMITTED in docs/openmontage/S1_STATE.md.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
JOB_ID = "s1-z-image-turbo-1"
KERNEL_SLUG = "forts845/openmontage-runner"
WORK = Path("/tmp/kilo/s1_jobs") / JOB_ID
RUN_PY = REPO / "tools" / "kaggle_bridge" / "s1_z_image_turbo_run.py"

# Kaggle copies only run.py -> /kaggle/src/script.py (not job.json), so embed
# the job JSON into the runner as JOB_EMBEDDED for a self-contained kernel.
def _embed_job(run_text: str, job: dict) -> str:
    marker = "JOB_EMBEDDED = None"
    injection = f"JOB_EMBEDDED = {json.dumps(job)}\n"
    if marker not in run_text:
        raise RuntimeError("JOB_EMBEDDED marker missing in runner")
    return run_text.replace(marker, injection, 1)

PROMPTS = [
    {"prompt": "single-creature silhouette: a solitary six-limbed alien grazer with a long neck, flat vector illustration, deep teal and bioluminescent lime on basalt charcoal background, silhouette only, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4000},
    {"prompt": "single-creature silhouette: a floating jellyfish-like air creature with trailing tendrils, flat vector illustration, bioluminescent lime on deep teal, silhouette only, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4001},
    {"prompt": "single-creature silhouette: a burrowing subterranean creature with spade-like forelimbs and segmented body, flat vector illustration, pale bone on basalt charcoal, silhouette only, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4002},
    {"prompt": "single-creature silhouette: a swimming filter-feeder with fin rays and a wide mouth, flat vector illustration, bioluminescent lime and deep teal, silhouette only, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4003},
    {"prompt": "habitat scene: frozen alien ocean surface with ice ridges and bioluminescent vents below the ice, flat vector illustration, deep teal, basalt charcoal, pale bone, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4004},
    {"prompt": "habitat scene: subglacial alien ocean cavern with glowing lime flora and charcoal rock, flat vector illustration, deep teal, bioluminescent lime, basalt charcoal, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4005},
    {"prompt": "habitat scene: alien tidal plain with basalt columns, pale bone mats and bioluminescent lime pools, flat vector illustration, basalt charcoal, pale bone, bioluminescent lime, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4006},
    {"prompt": "anatomy-detail crop: close-up of an alien creature limb joint showing six limbs, flat vector illustration, pale bone and basalt charcoal, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4007},
    {"prompt": "anatomy-detail crop: close-up of an alien creature head with a sensory crest, flat vector illustration, bioluminescent lime on deep teal, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4008},
    {"prompt": "food-web background plate: multiple alien creatures arranged in depth showing energy flow, flat vector illustration, deep teal, basalt charcoal, bioluminescent lime, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4009},
    {"prompt": "food-web background plate: ocean floor scene with predator and prey silhouettes, flat vector illustration, pale bone, bioluminescent lime, basalt charcoal, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4010},
    {"prompt": "planet-surface wide: frozen alien ocean horizon with ice and basalt under a pale sky, flat vector illustration, deep teal, basalt charcoal, pale bone, no text, no watermark, no letters, no numerals, not photorealistic", "seed": 4011},
]

JOB = {
    "job_id": JOB_ID,
    "model": "Tongyi-MAI/Z-Image-Turbo",
    "model_revision": "main",
    "width": 1024,
    "height": 1024,
    "steps": 9,
    "guidance_scale": 0.0,
    "prompts": PROMPTS,
    "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

bridge = KaggleBridgeTool()

# 1. build job folder
bj = bridge.execute({
    "command": "build_job_folder",
    "job_folder": str(WORK),
    "job_id": JOB_ID,
    "kernel_slug": KERNEL_SLUG,
    "job": JOB,
    "run_py": _embed_job(RUN_PY.read_text(encoding="utf-8"), JOB),
    "enable_gpu": True,
    "enable_internet": True,
    "kaggle_cmd": "kaggle",
})
if not bj.success:
    print(f"BUILD FAILED: {bj.error}"); sys.exit(1)
print(f"job folder built: {bj.data['job_folder']}")

# 2. push (push returns after code push; the run is asynchronous on Kaggle)
ps = bridge.execute({
    "command": "push",
    "job_folder": str(WORK),
    "kernel_slug": KERNEL_SLUG,
    "timeout": 3600,
    "accelerator": "gpu",
    "kaggle_cmd": "kaggle",
})
if not ps.success:
    print(f"PUSH FAILED: {ps.error}"); sys.exit(1)
print(f"PUSH OK: {ps.data['push']}")

# record submission marker locally (not committed)
(WORK / "submitted.json").write_text(
    json.dumps({"job_id": JOB_ID, "kernel_slug": KERNEL_SLUG,
                "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": "Tongyi-MAI/Z-Image-Turbo"}, indent=2),
    encoding="utf-8")
print(f"SUBMITTED job_id={JOB_ID} kernel={KERNEL_SLUG}")
