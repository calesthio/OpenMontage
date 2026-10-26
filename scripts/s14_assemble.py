#!/usr/bin/env python3
"""S14: assemble the smoke-test results from the 3 Kaggle kernel outputs into
a combined report under docs/ and gitignored projects/.

Reads only local artefacts (no network, no model judgment beyond what the
kernels recorded).

Outputs:
  docs/openmontage/image_gen/s14_smoke_results.csv   (per-image rows)
  docs/openmontage/image_gen/s14_smoke_report.json   (per-model + aggregate)
  docs/openmontage/image_gen/s14_smoke_report.md     (human-readable report)
  (same three files mirrored under projects/s14/, gitignored)
"""
from __future__ import annotations

import csv, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = "/workspaces/OpenMontage"
FETCH = Path("/tmp/kilo/s14_out")
DOCS = Path(ROOT) / "docs/openmontage/image_gen"
PROJ = Path(ROOT) / "projects/s14"
for d in (DOCS, PROJ):
    d.mkdir(parents=True, exist_ok=True)

MODELS = ["minit2i-b-16", "minit2i-l-16", "zimage-base"]


def read_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def assemble():
    rows = []
    per_model = {}
    total = {"images": 0, "ok": 0, "black": 0, "nan": 0, "errors": 0,
             "hardware_fail": 0}

    for model in MODELS:
        base = FETCH / model / f"s14_smoke_{model}"
        man = read_json(base / "manifest.json") if base.is_dir() else None
        done = read_json(base / "DONE.json") if base.is_dir() else None
        status = (base / "status.txt").read_text(encoding="utf-8").strip() if (base / "status.txt").is_file() else "FETCH_FAILED"
        license_txt = (base / "license.txt").read_text(encoding="utf-8").strip() if (base / "license.txt").is_file() else "unknown"
        revision_txt = (base / "revision.txt").read_text(encoding="utf-8").strip() if (base / "revision.txt").is_file() else "unknown"
        gpu = read_json(base / "gpu_precheck.json") if base.is_dir() else None
        versions = read_json(base / "versions.json") if base.is_dir() else None
        install = read_json(base / "install_log.json") if base.is_dir() else None

        model_record = {
            "model": model,
            "model_id": man.get("model_id") if man else None,
            "status": status,
            "license": license_txt,
            "revision": revision_txt,
            "gpu_name": gpu.get("info", {}).get("gpu_name") if gpu else None,
            "compute_capability": gpu.get("info", {}).get("compute_capability") if gpu else None,
            "fp16_supported": gpu.get("info", {}).get("fp16_supported") if gpu else None,
            "bf16_supported": gpu.get("info", {}).get("bf16_supported") if gpu else None,
            "bitsandbytes": gpu.get("info", {}).get("bitsandbytes") if gpu else None,
            "torch": versions.get("torch") if versions else None,
            "diffusers": versions.get("diffusers") if versions else None,
            "transformers": versions.get("transformers") if versions else None,
            "pipeline_class": man.get("pipeline_class") if man else None,
            "steps": man.get("steps") if man else None,
            "guidance_scale": man.get("guidance_scale") if man else None,
            "load_seconds": man.get("load_seconds") if man else None,
            "warm_sec_per_image": man.get("warm_sec_per_image") if man else None,
            "peak_vram_allocated_mb": man.get("peak_vram_allocated_mb") if man else None,
            "peak_vram_reserved_mb": man.get("peak_vram_reserved_mb") if man else None,
            "requested": man.get("requested") if man else 0,
            "generated": man.get("generated") if man else 0,
            "n_ok": man.get("n_ok") if man else 0,
            "black_count": man.get("black_count") if man else 0,
            "nan_count": man.get("nan_count") if man else 0,
            "errors": man.get("errors") if man else [],
            "images": [],
        }
        # hardware-fail detection: status text or DONE errors mention it
        is_hw_fail = ("HARDWARE FAIL" in status) or any(
            "HARDWARE FAIL" in str(e) for e in (man.get("errors") or []))
        model_record["hardware_fail"] = is_hw_fail

        if man and man.get("images"):
            for im in man["images"]:
                row = {
                    "model": model,
                    "model_id": man.get("model_id"),
                    "license": license_txt,
                    "revision": revision_txt,
                    "seed": im.get("seed"),
                    "output_file": im.get("output_file"),
                    "seconds": im.get("seconds"),
                    "warm_sec_per_image": im.get("warm_sec_per_image"),
                    "black_or_nan": im.get("black_or_nan"),
                    "error": im.get("error"),
                    "sha256": im.get("sha256"),
                    "bytes": im.get("bytes"),
                }
                rows.append(row)
                model_record["images"].append(row)
                total["images"] += 1
                if im.get("error"):
                    total["errors"] += 1
                elif im.get("black_or_nan"):
                    total["black"] += 1
                else:
                    total["ok"] += 1
        else:
            # no images: model failed before/during generation
            total["hardware_fail"] += 1

        per_model[model] = model_record

    total["black"] = sum(m["black_count"] for m in per_model.values())
    total["nan"] = sum(m["nan_count"] for m in per_model.values())
    total["models_run"] = len(MODELS)

    # CSV
    csv_path = DOCS / "s14_smoke_results.csv"
    fields = ["model", "model_id", "license", "revision", "seed", "output_file",
              "seconds", "warm_sec_per_image", "black_or_nan", "error", "sha256", "bytes"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "milestone": "S14",
        "rule": {
            "gpu_required": "T4, compute capability 7.5",
            "dtype": "fp16 only",
            "no_bitsandbytes": True,
            "no_cpu_fallback": True,
            "size": "512x512",
            "seeds": [101, 202, 303],
            "prompt": ("flat vector illustration of an alien deep-sea creature, "
                       "exactly six separate tendrils, two pairs of fins, plain "
                       "light background, empty lower fifth, no text"),
        },
        "total": total,
        "per_model": per_model,
        "per_image": rows,
    }
    json_path = DOCS / "s14_smoke_report.json"
    json.dump(report, open(json_path, "w"), indent=2)

    # Markdown
    lines = ["# S14 — smoke test, 3 new models (free Kaggle T4)",
             "", f"Generated: {report['ts']}", "",
             "## Precheck (per kernel, enforced before any generation)",
             f"- GPU: T4, compute capability 7.5; fp16 only; bf16 NOT supported; "
             f"bitsandbytes absent.",
             "- One model per kernel (never stacked dependency sets).",
             "- fp16 only; no pipe.to('cuda') before offload; enable_model_cpu_offload().",
             "", "## Per-model outcome"]
    for model in MODELS:
        m = per_model[model]
        hw = "HARDWARE FAIL" if m["hardware_fail"] else ""
        lines.append(
            f"- {model} ({m['model_id']}): {m['status']} {hw}; "
            f"license={m['license']}; revision={m['revision']}; "
            f"pipeline={m['pipeline_class']}; steps={m['steps']}; "
            f"guidance={m['guidance_scale']}; "
            f"load={m['load_seconds']}s; warm={m['warm_sec_per_image']}s/img; "
            f"peak VRAM alloc={m['peak_vram_allocated_mb']}MB "
            f"reserved={m['peak_vram_reserved_mb']}MB; "
            f"generated={m['generated']}/{m['requested']} ok={m['n_ok']} "
            f"black={m['black_count']} nan={m['nan_count']}"
        )
    lines.append("")
    lines.append("## Per-image detail")
    lines.append("| model | seed | output_file | seconds | warm_s | black_or_nan | error |")
    lines.append("|---|---:|---|---:|---:|---|---|")
    for r in rows:
        lines.append(f"| {r['model']} | {r['seed']} | {r['output_file']} | "
                     f"{r['seconds']} | {r['warm_sec_per_image']} | "
                     f"{r['black_or_nan']} | {r['error'] or ''} |")
    lines.append("")
    lines.append("## Aggregate")
    lines.append(f"- models run: {total['models_run']}")
    lines.append(f"- total images: {total['images']} | ok: {total['ok']} | "
                 f"black: {total['black']} | nan: {total['nan']} | errors: {total['errors']}")
    lines.append(f"- hardware-fail models: {total['hardware_fail']}")
    lines.append("")
    lines.append("## Notes")
    lines.append("- MiniT2I B/16 and MiniT2I L/16 repos are not public on "
                 "HuggingFace (404) -> HARDWARE FAIL, recorded with exact error; "
                 "no retry beyond one attempt per model.")
    lines.append("- Z-Image Base loads (ZImagePipeline, revision 04cc4abb..., "
                 "Apache-2.0 per model card README) but produces black frames "
                 "for all 3 seeds -> black/NaN flag set, n_ok=0.")
    lines.append("- No 1024 bake-offs run; no Kromoss/MOSS-Image-SFT/Iris/"
                 "HiDream/FLUX.3 Klein downloaded (only model-card licence "
                 "reporting required for those).")
    lines.append("- License for MiniT2I models could not be fetched (repo not "
                 "found); recorded as unknown.")

    md_path = DOCS / "s14_smoke_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # mirror to projects/s14 (gitignored)
    for p in (csv_path, json_path, md_path):
        dest = PROJ / p.name
        dest.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"wrote {csv_path} ({len(rows)} image rows)")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"mirrored to {PROJ}")
    print(json.dumps(total, indent=2))
    return report


if __name__ == "__main__":
    assemble()
