#!/usr/bin/env python3
"""QA Test 02: MLX image generation — t2i matrix + adversarial VLM scoring.

Generates a small deterministic matrix of images via the local MLX provider
(``mlx_image`` — shells out to the sibling mlx-movie-director ``run.py``;
$0, Apple-Silicon-native), then scores each with ``run.py caption --style score``
(Qwen3-VL via LM Studio). Produces, under ``tests/qa/output/``:

  - the raw PNGs (for human inspection per the QA_PLAN protocol), and
  - ``qa_image_gen_receipt.json`` — per-image scores + flags + gen metadata.

This fills the ``test_02_image_gen.py`` slot in ``QA_PLAN.md`` AND serves as a
regression gate for the ``mlx_image`` provider: a score collapse or generation
failure here catches a provider/env regression before it reaches a user.

NOT a CI pytest — it needs ``MLX_MOVIE_DIRECTOR_DIR`` + the mlx venv + staged
models + Apple Silicon + LM Studio on localhost:1234. Run manually:

    MLX_MOVIE_DIRECTOR_DIR=/path/to/video_generation \\
        .venv/bin/python tests/qa/test_02_image_gen.py

Exit code is non-zero only on a generation or scoring FAILURE (provider broke,
caption broke). Low scores are flagged ⚠ in the table but do not fail the run —
QA is human-inspected, and the adversarial scorer is deliberately harsh.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.env_loader import load_env  # noqa: E402

load_env()

from tools._mlx.env import resolve_mlx_env  # noqa: E402
from tools.graphics.mlx_image import MLXImage  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT, exist_ok=True)
RECEIPT = os.path.join(OUT, "qa_image_gen_receipt.json")

# Adversarial-scorer advisory thresholds. The `score` style is deliberately
# strict (it is told to FIND flaws, not praise), so these are soft flags, not
# pass/fail gates. A consistent drop below these across the matrix is the real
# regression signal — a single low image may just be a hard prompt.
SOFT_OVERALL = 6
SOFT_ARTIFACTS = 7

# A small, deterministic matrix. Fixed seeds → reproducible regression baseline.
# Each row stresses a different known weak spot (skin/hands/composition) so a
# regression localizes instead of looking like a uniform dip.
MATRIX = [
    {
        "tag": "portrait",
        "prompt": (
            "portrait of a young woman with freckles and loose hair, soft window "
            "light from the left, shallow depth of field, neutral background, "
            "photorealistic"
        ),
        "width": 1024,
        "height": 1024,
        "seed": 100,
    },
    {
        "tag": "still_life",
        "prompt": (
            "a ceramic bowl of citrus fruit on a weathered wooden table, warm "
            "morning sunlight, visible skin of the fruit, detailed texture, "
            "photorealistic still life"
        ),
        "width": 1024,
        "height": 1024,
        "seed": 200,
    },
    {
        "tag": "hands",
        "prompt": (
            "a barista's hands holding a ceramic latte cup with leaf latte art, "
            "close-up, natural kitchen light, detailed fingers, photorealistic"
        ),
        "width": 1024,
        "height": 1024,
        "seed": 300,
    },
]


def run_caption(run_py: str, venv_python: str, image: str) -> tuple[dict | None, float | None, str | None]:
    """Score one image with `run.py caption --style score --samples 3`.

    ``--samples 3`` runs 3 independent VLM passes and writes the per-dimension
    MEDIAN — necessary because the local Gemma-4 VLM is image-dependent and can
    return an empty response on a single pass. ``caption`` writes the canonical
    structured result to ``<image>.caption.json`` (its stdout only echoes a
    preview); we read that file and pull the score dict out of
    ``styles["score"]["caption"]`` (a JSON-encoded string). Returns
    ``(score_dict, elapsed_sec, error)``.
    """
    try:
        proc = subprocess.run(
            [venv_python, run_py, "caption", image, "--style", "score", "--samples", "3"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, None, "caption timed out (>180s)"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        return None, None, f"caption rc={proc.returncode}:\n" + "\n".join(tail)

    cap_json = Path(image).with_suffix(".caption.json")
    if not cap_json.is_file():
        return None, None, f"caption produced no {cap_json.name}"
    try:
        data = json.loads(cap_json.read_text())
    except json.JSONDecodeError as exc:
        return None, None, f"{cap_json.name} parse failed: {exc}"

    style_block = (data.get("styles") or {}).get("score") or {}
    raw = style_block.get("caption") or data.get("caption")
    if not raw:
        return None, None, f"{cap_json.name} has no score caption field"
    try:
        score = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        return None, None, f"score caption JSON parse failed: {exc}"
    return score, style_block.get("elapsed_sec"), None


def main() -> int:
    print("=" * 72)
    print("QA Test 02: MLX image generation — t2i matrix + VLM scoring")
    print("=" * 72)

    # Resolve the MLX env once, requiring both generation (models + arm64) and
    # caption (LM Studio). Fail fast with the provider's own reason if missing.
    env = resolve_mlx_env(need_models=True, need_lm_studio=True)
    if not env["ok"]:
        print(f"\n✗ MLX env not ready: {env['reason']}")
        print("  Set MLX_MOVIE_DIRECTOR_DIR, stage models, and start LM Studio (localhost:1234).")
        return 1
    run_py = env["run_py"]
    venv_python = env["venv_python"]
    print(f"  mlx_dir:     {env['mlx_dir']}")
    print(f"  run.py:      {run_py}")
    print(f"  venv python: {venv_python}")
    print(f"  arm64:       {env['arm64']}")

    tool = MLXImage()
    print(f"  provider status: {tool.get_status().name}")

    results = []
    failures = []
    for row in MATRIX:
        tag = row["tag"]
        out_png = os.path.join(OUT, f"t2i_{tag}_s{row['seed']}.png")
        print(f"\n--- [{tag}] {row['prompt'][:60]}... ---")

        inputs = {
            "prompt": row["prompt"],
            "width": row["width"],
            "height": row["height"],
            "seed": row["seed"],
            "output_path": out_png,
        }
        t0 = time.time()
        result = tool.execute(inputs)
        gen_elapsed = round(time.time() - t0, 2)

        if not result.success:
            msg = result.error or "(unknown error)"
            print(f"  ✗ GENERATION FAILED ({gen_elapsed}s): {msg[:160]}")
            failures.append({"tag": tag, "stage": "generate", "error": msg})
            results.append({"tag": tag, "ok": False, "stage": "generate", "error": msg})
            continue

        image_path = result.data.get("output") or (result.artifacts or [None])[0]
        model = result.data.get("model")
        print(f"  ✓ generated ({gen_elapsed}s, {model}) → {os.path.basename(image_path)}")

        score, score_elapsed, err = run_caption(run_py, venv_python, image_path)
        if err:
            print(f"  ✗ SCORING FAILED: {err[:160]}")
            failures.append({"tag": tag, "stage": "score", "error": err})
            results.append(
                {
                    "tag": tag,
                    "ok": False,
                    "stage": "score",
                    "image": image_path,
                    "model": model,
                    "gen_seconds": gen_elapsed,
                    "error": err,
                }
            )
            continue

        overall = score.get("overall")
        artifacts = score.get("artifacts")
        flag = ""
        if isinstance(overall, int) and overall < SOFT_OVERALL:
            flag += f" ⚠overall<{SOFT_OVERALL}"
        if isinstance(artifacts, int) and artifacts < SOFT_ARTIFACTS:
            flag += f" ⚠artifacts<{SOFT_ARTIFACTS}"
        sec = f" ({round(score_elapsed, 2)}s)" if isinstance(score_elapsed, (int, float)) else ""
        print(
            f"  scored{sec}: overall={overall} detail={score.get('detail')} "
            f"sharpness={score.get('sharpness')} composition={score.get('composition')} "
            f"prompt={score.get('prompt_adherence')} artifacts={artifacts}{flag}"
        )
        issues = score.get("issues") or []
        if issues:
            print(f"    issues: {issues}")
        print(f"    summary: {score.get('summary')}")

        results.append(
            {
                "tag": tag,
                "ok": True,
                "image": image_path,
                "model": model,
                "gen_seconds": gen_elapsed,
                "prompt": row["prompt"],
                "seed": row["seed"],
                "size": [row["width"], row["height"]],
                "scores": {
                    "overall": overall,
                    "detail": score.get("detail"),
                    "sharpness": score.get("sharpness"),
                    "composition": score.get("composition"),
                    "prompt_adherence": score.get("prompt_adherence"),
                    "artifacts": artifacts,
                },
                "issues": issues,
                "strengths": score.get("strengths") or [],
                "summary": score.get("summary"),
                "flagged": bool(flag),
            }
        )

    # Persist receipt.
    receipt = {
        "matrix_size": len(MATRIX),
        "failures": failures,
        "soft_thresholds": {"overall": SOFT_OVERALL, "artifacts": SOFT_ARTIFACTS},
        "results": results,
    }
    with open(RECEIPT, "w") as fh:
        json.dump(receipt, fh, indent=2, ensure_ascii=False)
    print(f"\n→ receipt: {RECEIPT}")
    print(f"→ images:  {OUT}")

    # Summary line.
    ok = [r for r in results if r.get("ok")]
    flagged = [r for r in ok if r.get("flagged")]
    print("\n" + "=" * 72)
    print(
        f"{len(ok)}/{len(MATRIX)} generated+scored"
        + (f", {len(failures)} FAILURE(S)" if failures else "")
        + (f", {len(flagged)} flagged below soft threshold" if flagged else "")
    )
    print("=" * 72)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
