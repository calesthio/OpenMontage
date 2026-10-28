"""OpenMontage K3 — FLUX.2-klein-4B pilot frame generation (Kaggle T4).

One kernel per section-group (weights downloaded once per kernel).
Shots are embedded inline (SHOTS) — no repo path dependency.

Per shot:
  - prompt = bit's scene description + VISUAL_STYLE_GUIDE technique
  - 1280x720, 4 steps, guidance_scale=1.0 (CFG off), bfloat16 -> float16 fallback
  - NaN/black frame detection via min/max pixels
  - log time, peak VRAM, selected dtype per shot

Outputs: /kaggle/working/k3-klein-frames/
         frames/B001.png ... B078.png
         results.json
         kernel.log
"""

from __future__ import annotations

import importlib.metadata as md
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import torch
from PIL import Image

# --- Пин версий (diffusers 0.37.0 уже содержит Flux2KleinPipeline) ---
PINNED_VERSIONS = ["diffusers==0.37.0", "transformers==4.57.6", "huggingface_hub==0.36.2"]


def _ensure_pinned_versions():
    for pkg in PINNED_VERSIONS:
        name = pkg.split("==")[0]
        try:
            if md.version(name) == pkg.split("==")[1]:
                continue
        except Exception:
            pass
        print(f"Installing {pkg} ...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", pkg],
            check=True,
        )


_ensure_pinned_versions()

import inspect  # noqa: E402
from diffusers import Flux2KleinPipeline  # noqa: E402

# --- LOAD SHOTS ---
SHOTS = [{"bit_id": "B001", "section": 8, "sentence_ids": ["S166", "S167", "S168"], "start": 0.0, "end": 14.19, "duration": 14.19, "text": "There is one more question, and it is the strangest one in the episode. If this ocean had life, could it ever build something? Not a civilisation, something simpler: a tool, a structure, a signal that carries further than a body can.", "words": 42, "prompt": "wide plate, empty black field with a single pale-bone vertical seam of light, no subject | wide plate, pale-bone stack of flat blocks in deep teal water, no hands, no subject | minimal plate, small pale-bone shape extended by a coral accent line, flat fills, no text", "host_in_frame": False, "prompt_klein": "wide plate, empty black field with a single pale-bone vertical seam of light, no subject | wide plate, pale-bone stack of flat blocks in deep teal water, no hands, no subject | minimal plate, small pale-bone shape extended by a coral accent line, flat fills, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B002", "section": 8, "sentence_ids": ["S169", "S170", "S171"], "start": 14.19, "end": 26.19, "duration": 12, "text": "Start with the obvious obstacle: there is no dry land to stand on. Everything happens in water, and water is a medium that pushes back. The second obstacle is heat you can hold.", "words": 33, "prompt": "wide plate, unbroken dark teal water surface meeting pale-bone ice, no shore anywhere | detail crop, pale-bone object with electric teal drag lines curving around it, sparse hatching | minimal plate, single coral accent glow held inside a pale-bone ring, night ink background", "host_in_frame": False, "prompt_klein": "wide plate, unbroken dark teal water surface meeting pale-bone ice, no shore anywhere | detail crop, pale-bone object with electric teal drag lines curving around it, sparse hatching | minimal plate, single coral accent glow held inside a pale-bone ring, night ink background. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B003", "section": 8, "sentence_ids": ["S172", "S173"], "start": 26.19, "end": 39.71, "duration": 13.52, "text": "A vent gives heat, but it gives it at the bottom of an ocean, in a place you cannot carry it away from. The third obstacle is material: our own technology leans on solids that can be shaped and kept.", "words": 40, "prompt": "wide context, basalt floor with coral heat glow, dark teal water mass above, no subject | wide plate, three pale-bone flat blocks stacked in dark water, hard edges, no tools, no text", "host_in_frame": False, "prompt_klein": "wide context, basalt floor with coral heat glow, dark teal water mass above, no subject | wide plate, three pale-bone flat blocks stacked in dark water, hard edges, no tools, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B004", "section": 8, "sentence_ids": ["S174", "S175"], "start": 39.71, "end": 51.71, "duration": 12, "text": "Rock and ice exist here, but whether they can be worked is a different question. And if a vent field shifts or cools, anything built on it has to move with it.", "words": 32, "prompt": "detail crop, cracked basalt charcoal surface beside a pale-bone ice facet, flat fills | wide plate, chimney cluster tilted, pale-bone structure outline abandoned beside it, dark water", "host_in_frame": False, "prompt_klein": "detail crop, cracked basalt charcoal surface beside a pale-bone ice facet, flat fills | wide plate, chimney cluster tilted, pale-bone structure outline abandoned beside it, dark water. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B005", "section": 8, "sentence_ids": ["S176", "S177", "S178"], "start": 51.71, "end": 69.62, "duration": 17.91, "text": "So a technological species here would need a body that works in water, hands or their equivalent, and a reason to build at all. That is a long list of conditions, and each one is a place where the story could stop. It is also the reason this section is short on conclusions.", "words": 53, "prompt": "wide plate, three pale-bone conditions as three separate marks in a row, coral accent under the third, no text | wide plate, a pale-bone line crossing three gaps, each gap marked by a coral accent break | minimal plate, empty pale-bone frame on night ink, nothing inside, flat fills", "host_in_frame": False, "prompt_klein": "wide plate, three pale-bone conditions as three separate marks in a row, coral accent under the third, no text | wide plate, a pale-bone line crossing three gaps, each gap marked by a coral accent break | minimal plate, empty pale-bone frame on night ink, nothing inside, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B006", "section": 8, "sentence_ids": ["S179", "S180", "S181"], "start": 69.62, "end": 83.47, "duration": 13.85, "text": "We could invent a tool-maker, but inventing one would tell you nothing about this ocean. Nothing we have measured rules intelligence in or out. That is an honest place to leave it: an open question with no evidence on either side.", "words": 41, "prompt": "extreme wide, faint silhouette of a limb-like shape holding a pale-bone block, distant, unreadable, no detail | wide plate, black water with a single pale-bone dot, one coral accent ring, extreme minimal | wide plate, two empty pale-bone panels facing each other across a dark gap, flat fills", "host_in_frame": False, "prompt_klein": "extreme wide, faint silhouette of a limb-like shape holding a pale-bone block, distant, unreadable, no detail | wide plate, black water with a single pale-bone dot, one coral accent ring, extreme minimal | wide plate, two empty pale-bone panels facing each other across a dark gap, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B007", "section": 8, "sentence_ids": ["S182", "S183", "S184"], "start": 83.47, "end": 97.67, "duration": 14.19, "text": "And it is worth saying plainly that the absence of evidence is not a verdict. And what happens to a tool left in salt water for a century? Every obstacle here is a place where a different world would have an advantage.", "words": 42, "prompt": "minimal plate, pale-bone outline of a closed shape with one side left open, night ink field | detail crop, pale-bone block half-eroded in electric teal fluid, sparse hatching, no subject | wide plate, three pale-bone barriers in a dark field, each with a coral accent gap", "host_in_frame": False, "prompt_klein": "minimal plate, pale-bone outline of a closed shape with one side left open, night ink field | detail crop, pale-bone block half-eroded in electric teal fluid, sparse hatching, no subject | wide plate, three pale-bone barriers in a dark field, each with a coral accent gap. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B008", "section": 8, "sentence_ids": ["S185"], "start": 97.67, "end": 109.67, "duration": 12, "text": "Which is why the honest answer to the technology question is not no, but not yet measurable.", "words": 17, "prompt": "minimal plate, pale-bone open frame on night ink, one coral accent dot outside it", "host_in_frame": False, "prompt_klein": "minimal plate, pale-bone open frame on night ink, one coral accent dot outside it. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What blocks technology without land or fire — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B001", "section": 9, "sentence_ids": ["S186", "S187", "S188"], "start": 0.0, "end": 13.36, "duration": 13.36, "text": "So let us separate the two piles, starting with what is measured. Europa has a global saltwater ocean under a completely frozen crust. That ocean holds more than twice the water of all Earth's oceans.", "words": 35, "prompt": "wide plate, pale-bone field divided into two flat blocks, one textured, one empty, hard seam | front view schematic, small sphere with deep teal band beneath a pale-bone cracked shell, flat fills, no labels | wide plate, large dark teal mass dwarfing a small pale-bone sphere, flat fills, no text", "host_in_frame": False, "prompt_klein": "wide plate, pale-bone field divided into two flat blocks, one textured, one empty, hard seam | front view schematic, small sphere with deep teal band beneath a pale-bone cracked shell, flat fills, no labels | wide plate, large dark teal mass dwarfing a small pale-bone sphere, flat fills, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What is science, and what is a guess — target 1:30. 1280x720, flat graphic style."}, {"bit_id": "B002", "section": 9, "sentence_ids": ["S189", "S190", "S191"], "start": 13.36, "end": 27.1, "duration": 13.74, "text": "Jupiter's tidal heating keeps it liquid and drives chemistry at the sea floor. Enceladus has a global salty ocean under ice. Its vents put hot rock in contact with water, and the plume carries the evidence.", "words": 36, "prompt": "wide context, moon silhouette with stress arcs and a faint coral glow at its base, distant | front view schematic, small fractured pale-bone sphere with a deep teal band, flat fills | side cross-section, basalt core, coral accent seam, pale-bone plume rising through the ocean", "host_in_frame": False, "prompt_klein": "wide context, moon silhouette with stress arcs and a faint coral glow at its base, distant | front view schematic, small fractured pale-bone sphere with a deep teal band, flat fills | side cross-section, basalt core, coral accent seam, pale-bone plume rising through the ocean. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What is science, and what is a guess — target 1:30. 1280x720, flat graphic style."}, {"bit_id": "B003", "section": 9, "sentence_ids": ["S192", "S193", "S194"], "start": 27.1, "end": 41.22, "duration": 14.12, "text": "Its plume also carries hydrogen, a chemical energy source microbes could use. And on Earth, vent life runs on chemosynthesis, without sunlight. Everything else is ours: the grazer, the drifter, the burrower, the budding, and the glow.", "words": 37, "prompt": "abstract detail plate, pale-bone bubbles rising in electric teal, no symbols, no text | wide establishing plate, black chimney cluster with lime-teal mat glow, night ink water | wide plate, five faint pale-bone outlines in a row, all distant, all dissolving into hatching at the edges", "host_in_frame": False, "prompt_klein": "abstract detail plate, pale-bone bubbles rising in electric teal, no symbols, no text | wide establishing plate, black chimney cluster with lime-teal mat glow, night ink water | wide plate, five faint pale-bone outlines in a row, all distant, all dissolving into hatching at the edges. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What is science, and what is a guess — target 1:30. 1280x720, flat graphic style."}, {"bit_id": "B004", "section": 9, "sentence_ids": ["S195", "S196", "S197"], "start": 41.22, "end": 54.19, "duration": 12.98, "text": "Five inventions, each with a stated constraint, none with an observation. That is the whole list, and it is short on purpose. A longer list would have meant weaker sourcing, not a better episode.", "words": 34, "prompt": "minimal plate, five pale-bone marks with coral accent ticks beneath each, deep teal field, no text | wide plate, small pale-bone block in a large empty night ink field, extreme minimal | minimal plate, long pale-bone line fading to nothing, one coral accent dot at its origin", "host_in_frame": False, "prompt_klein": "minimal plate, five pale-bone marks with coral accent ticks beneath each, deep teal field, no text | wide plate, small pale-bone block in a large empty night ink field, extreme minimal | minimal plate, long pale-bone line fading to nothing, one coral accent dot at its origin. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What is science, and what is a guess — target 1:30. 1280x720, flat graphic style."}, {"bit_id": "B005", "section": 9, "sentence_ids": ["S198", "S199"], "start": 54.19, "end": 67.17, "duration": 12.98, "text": "If you remember one thing, make it this: the ocean is real, and the animals are not. Enceladus supplies the strongest chemical case, because its ocean is sampled for us, by its own plumes.", "words": 34, "prompt": "split plate, left a solid pale-bone ice-and-water mass, right five faint dotted outlines, hard vertical seam | wide context, small moon venting a pale-bone plume, faint electric teal streaks, distant", "host_in_frame": False, "prompt_klein": "split plate, left a solid pale-bone ice-and-water mass, right five faint dotted outlines, hard vertical seam | wide context, small moon venting a pale-bone plume, faint electric teal streaks, distant. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What is science, and what is a guess — target 1:30. 1280x720, flat graphic style."}, {"bit_id": "B006", "section": 9, "sentence_ids": ["S200", "S201", "S202"], "start": 67.17, "end": 83.57, "duration": 16.41, "text": "Notice the asymmetry: eight claims about the world, and five about animals we made up. The Earth analogue is the reason any of this is worth arguing about. If the vents had no life, this episode would be science fiction with better footnotes.", "words": 43, "prompt": "wide plate, eight pale-bone marks on the left, five fainter dotted marks on the right, hard seam | wide establishing plate, black chimney cluster with lime mat glow, empty dark water | wide plate, empty black chimney field with no glow, night ink water, extreme minimal", "host_in_frame": False, "prompt_klein": "wide plate, eight pale-bone marks on the left, five fainter dotted marks on the right, hard seam | wide establishing plate, black chimney cluster with lime mat glow, empty dark water | wide plate, empty black chimney field with no glow, night ink water, extreme minimal. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: What is science, and what is a guess — target 1:30. 1280x720, flat graphic style."}, {"bit_id": "B001", "section": 10, "sentence_ids": ["S203", "S204", "S205", "S206"], "start": 0.0, "end": 17.38, "duration": 17.38, "text": "A frozen alien ocean may be the best place in the solar system to look for life. Not because we have found it, but because the physics allows it. Water, chemistry, energy: the ingredients are there. The rest is a question for the next mission, and for the people who fly it.", "words": 52, "prompt": "wide context, pale-bone ice-covered moon lit from one edge, black space, distant and schematic | wide plate, faint coral heat glow at a sea floor under a vast dark teal ocean, no subject | wide plate, three flat bands of deep teal, lime teal and coral accent with pale-bone separators, no text | wide context, small probe silhouette above a moon disc, distant, no detail, night ink space", "host_in_frame": False, "prompt_klein": "wide context, pale-bone ice-covered moon lit from one edge, black space, distant and schematic | wide plate, faint coral heat glow at a sea floor under a vast dark teal ocean, no subject | wide plate, three flat bands of deep teal, lime teal and coral accent with pale-bone separators, no text | wide context, small probe silhouette above a moon disc, distant, no detail, night ink space. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Closing and a question for you — target 1:00. 1280x720, flat graphic style."}, {"bit_id": "B002", "section": 10, "sentence_ids": ["S207", "S208", "S209", "S210", "S211"], "start": 17.38, "end": 34.76, "duration": 17.38, "text": "So here is our question for you. If you had one instrument to send under that ice, what would you measure first? The chemistry, the temperature, or the sound of something moving? Tell us in the comments, and tell us why. Because that is how a guess becomes a question worth funding.", "words": 52, "prompt": "minimal plate, single pale-bone dot at centre of deep teal field, coral accent ring, no text | wide plate, small pale-bone instrument shape lowered on a thin line into black water, distant | wide plate, three separate pale-bone marks in a row: grains, a heat glow, a ripple line, no text | minimal plate, two pale-bone speech-like blank blocks facing each other, no letters, flat fills | wide plate, pale-bone outline of a shape being lifted by a thin coral accent line, night ink field", "host_in_frame": False, "prompt_klein": "minimal plate, single pale-bone dot at centre of deep teal field, coral accent ring, no text | wide plate, small pale-bone instrument shape lowered on a thin line into black water, distant | wide plate, three separate pale-bone marks in a row: grains, a heat glow, a ripple line, no text | minimal plate, two pale-bone speech-like blank blocks facing each other, no letters, flat fills | wide plate, pale-bone outline of a shape being lifted by a thin coral accent line, night ink field. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Closing and a question for you — target 1:00. 1280x720, flat graphic style."}, {"bit_id": "B003", "section": 10, "sentence_ids": ["S212", "S213", "S214"], "start": 34.76, "end": 47.8, "duration": 13.04, "text": "It is a moon of Jupiter, and it has been there the whole time. The ocean is waiting under the ice, and it is not going anywhere. Until then, keep asking the question, and keep asking for the evidence.", "words": 39, "prompt": "wide context, small pale-bone moon disc beside a large dark planet mass, night ink space, distant | wide context, small probe silhouette above an ice-covered moon, distant, no detail | minimal plate, single pale-bone dot with a coral accent ring, deep teal field, no text", "host_in_frame": False, "prompt_klein": "wide context, small pale-bone moon disc beside a large dark planet mass, night ink space, distant | wide context, small probe silhouette above an ice-covered moon, distant, no detail | minimal plate, single pale-bone dot with a coral accent ring, deep teal field, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Closing and a question for you — target 1:00. 1280x720, flat graphic style."}]
# --- END LOAD SHOTS ---

OUT = Path("/kaggle/working/k3-klein-frames")
FRAME_DIR = OUT / "frames"
FRAME_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1280, 720
STEPS = 4
GUIDANCE = 1.0


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reset_peak():
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def peak_mb():
    if torch.cuda.is_available():
        return round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1)
    return 0


def is_black_or_nan(image: Image.Image) -> bool:
    import numpy as np
    arr = np.asarray(image)
    if arr.dtype.kind == "f":
        if np.isnan(arr).any():
            return True
    gray = arr.mean(axis=2) if arr.ndim == 3 else arr
    return float(gray.max()) < 5.0  # essentially black


def env_info():
    info = {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "diffusers": md.version("diffusers"),
        "transformers": md.version("transformers"),
        "huggingface_hub": md.version("huggingface_hub"),
    }
    if torch.cuda.is_available():
        info["device"] = torch.cuda.get_device_name(0)
        info["total_vram_gb"] = round(
            torch.cuda.get_device_properties(0).total_memory / 1024**3, 2
        )
    return info


def main():
    print(f"SHOTS TO RENDER: {len(SHOTS)}")
    print("ENV:", json.dumps(env_info(), ensure_ascii=False))
    print("SIGNATURE:", str(inspect.signature(Flux2KleinPipeline.__call__)))

    results = {
        "started_utc": now(),
        "model": "black-forest-labs/FLUX.2-klein-4B",
        "resolution": f"{W}x{H}",
        "steps": STEPS,
        "guidance_scale": GUIDANCE,
        "environment": env_info(),
        "signature": str(inspect.signature(Flux2KleinPipeline.__call__)),
        "shots": [],
        "selected_dtype": None,
    }
    print("ENV:", json.dumps(results["environment"], ensure_ascii=False))

    # --- Load model, try bf16 first, fall back to float16 ---
    reset_peak()
    t_load0 = time.time()
    pipe = None
    selected_dtype = None
    load_error = None
    for dtype_name, dtype in [("bfloat16", torch.bfloat16), ("float16", torch.float16)]:
        try:
            print(f"Attempting load with {dtype_name} ...")
            pipe = Flux2KleinPipeline.from_pretrained(
                "black-forest-labs/FLUX.2-klein-4B",
                torch_dtype=dtype,
            )
            pipe.enable_model_cpu_offload()
            selected_dtype = dtype_name
            print(f"Model loaded with {dtype_name}")
            break
        except Exception as exc:
            load_error = str(exc)
            print(f"Load failed with {dtype_name}: {load_error}")
            pipe = None

    if pipe is None:
        results["status"] = "failed"
        results["stage"] = "load"
        results["load_error"] = load_error
        (OUT / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )
        return

    load_s = round(time.time() - t_load0, 2)
    results["load_seconds"] = load_s
    results["peak_vram_mb_after_load"] = peak_mb()
    results["selected_dtype"] = selected_dtype
    print(f"Loaded in {load_s}s, peak VRAM after load: {peak_mb()} MB, dtype={selected_dtype}")

    # --- Generate shots ---
    for idx, shot in enumerate(SHOTS, start=1):
        bid = shot["bit_id"]
        print(f"[{idx}/{len(SHOTS)}] {bid} section={shot['section']} "
              f"t={shot['start']}-{shot['end']}s ...")
        t0 = time.time()
        dtype = torch.bfloat16 if selected_dtype == "bfloat16" else torch.float16
        image = None
        gen_s = 0
        status = "ok"
        try:
            out = pipe(
                prompt=shot["prompt_klein"],
                width=W,
                height=H,
                num_inference_steps=STEPS,
                guidance_scale=GUIDANCE,
                generator=torch.manual_seed(hash(bid) % (2**32)),
                output_type="pil",
            )
            image = out.images[0]
            gen_s = round(time.time() - t0, 2)
            bad = is_black_or_nan(image)
            if bad:
                status = "bad_frame"
                # fallback to float16 if bf16 bad
                if selected_dtype == "bfloat16":
                    print(f"  {bid} bf16 bad frame, retry float16 ...")
                    out = pipe(
                        prompt=shot["prompt_klein"],
                        width=W,
                        height=H,
                        num_inference_steps=STEPS,
                        guidance_scale=GUIDANCE,
                        generator=torch.manual_seed(hash(bid) % (2**32)),
                        output_type="pil",
                    )
                    image = out.images[0]
                    gen_s = round(time.time() - t0, 2)
                    bad = is_black_or_nan(image)
                    status = "ok" if not bad else "bad_frame"
                    if not bad:
                        print(f"  {bid} float16 OK")
        except Exception as exc:
            gen_s = round(time.time() - t0, 2)
            status = f"exception: {exc}"
            image = None
            print(f"  {bid} EXCEPTION: {exc}")

        if image is not None and status == "ok":
            fpath = FRAME_DIR / f"s{shot['section']:02d}_{bid}.png"
            image.save(fpath)
            print(f"  {bid} OK -> {fpath.name} ({gen_s}s)")
            results["shots"].append({
                "bit_id": bid,
                "section": shot["section"],
                "start": shot["start"],
                "end": shot["end"],
                "text": shot["text"],
                "prompt_klein": shot["prompt_klein"],
                "host_in_frame": shot.get("host_in_frame", False),
                "file": str(fpath),
                "status": "ok",
                "gen_seconds": gen_s,
                "seed": hash(bid) % (2**32),
            })
        else:
            print(f"  {bid} FAILED: {status}")
            results["shots"].append({
                "bit_id": bid,
                "section": shot["section"],
                "start": shot["start"],
                "end": shot["end"],
                "text": shot["text"],
                "prompt_klein": shot["prompt_klein"],
                "host_in_frame": shot.get("host_in_frame", False),
                "file": None,
                "status": "failed",
                "reason": status,
                "gen_seconds": gen_s if image is None else None,
            })

    peak_gen = peak_mb()
    results["peak_vram_mb_overall"] = max(results["peak_vram_mb_after_load"], peak_gen)
    results["peak_vram_gb_overall"] = round(
        results["peak_vram_mb_overall"] / 1024, 2
    )
    results["total_vram_gb"] = env_info().get("total_vram_gb", 0)
    results["finished_utc"] = now()
    ok_count = sum(1 for s in results["shots"] if s["status"] == "ok")
    results["status"] = "completed"
    results["shots_ok"] = ok_count
    results["shots_total"] = len(results["shots"])
    print(f"RESULT: {ok_count}/{len(results['shots'])} OK, "
          f"peak VRAM {results['peak_vram_gb_overall']} GB, dtype={selected_dtype}")
    (OUT / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False)
    )
    print(f"All outputs in {OUT}")


if __name__ == "__main__":
    main()
