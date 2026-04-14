#!/usr/bin/env python3
"""Google Flow full batch: all image aspect ratios + 2 video models."""

import sys
import time
from pathlib import Path

BASE = Path("projects/google-flow-batch-test")
PROMPT = "A futuristic city skyline at golden hour with vibrant neon lights reflecting on wet streets"
ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3"]

results = []


def run(label: str, tool_name: str, inputs: dict) -> dict:
    import importlib
    mod = importlib.import_module(f"tools.video.{tool_name}")
    cls_name = "GoogleFlowImage" if tool_name == "google_flow_image" else "GoogleFlowVideo"
    tool = getattr(mod, cls_name)()
    print(f"\n→ {label}")
    t0 = time.time()
    result = tool.execute_safe(inputs)
    elapsed = round(time.time() - t0, 1)
    status = "✅" if result.success else "❌"
    out = result.data.get("output_path", "") if result.success else ""
    size = ""
    if out and Path(out).exists():
        size_kb = Path(out).stat().st_size // 1024
        size = f"{size_kb}KB"
    print(f"  {status} {elapsed}s  {out}  {size}")
    if not result.success:
        print(f"  ERROR: {result.error}")
    return {"label": label, "success": result.success, "path": out, "size": size, "elapsed": elapsed}


# ── Nano Banana Pro (all 4 aspect ratios) ──────────────────────────────────
for ar in ASPECT_RATIOS:
    slug = ar.replace(":", "x")
    results.append(run(
        f"nano_banana_pro {ar}",
        "google_flow_image",
        {
            "prompt": PROMPT,
            "model": "nano_banana_pro",
            "aspect_ratio": ar,
            "output_path": str(BASE / f"images/nbpro_{slug}.png"),
        },
    ))

# ── Nano Banana 2 (all 4 aspect ratios) ───────────────────────────────────
for ar in ASPECT_RATIOS:
    slug = ar.replace(":", "x")
    results.append(run(
        f"nano_banana {ar}",
        "google_flow_image",
        {
            "prompt": PROMPT,
            "model": "nano_banana",
            "aspect_ratio": ar,
            "output_path": str(BASE / f"images/nb2_{slug}.png"),
        },
    ))

# ── Veo Fast (video) ───────────────────────────────────────────────────────
results.append(run(
    "veo_fast 16:9",
    "google_flow_video",
    {
        "prompt": PROMPT,
        "model": "veo_fast",
        "aspect_ratio": "16:9",
        "output_path": str(BASE / "videos/veo_fast.mp4"),
    },
))

# ── Veo Lite (video) ───────────────────────────────────────────────────────
results.append(run(
    "veo_lite 16:9",
    "google_flow_video",
    {
        "prompt": PROMPT,
        "model": "veo_lite",
        "aspect_ratio": "16:9",
        "output_path": str(BASE / "videos/veo_lite.mp4"),
    },
))

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BATCH RESULTS")
print("=" * 60)
passed = sum(1 for r in results if r["success"])
for r in results:
    icon = "✅" if r["success"] else "❌"
    print(f"{icon}  {r['label']:<30}  {r['size']:<10}  {r['path']}")

print(f"\nTotal: {passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
