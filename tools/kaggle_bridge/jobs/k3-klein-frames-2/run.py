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
SHOTS = [{"bit_id": "B001", "section": 5, "sentence_ids": ["S094", "S095", "S096"], "start": 0.0, "end": 17.1, "duration": 17.1, "text": "Here we have to be honest: there is no evidence for an alien predator, because nobody has seen one. What we can do is reason: if a mat feeds a grazer, the same energy is available to something that eats grazers. That is not evidence, it is bookkeeping.", "words": 48, "prompt": "wide plate, empty night ink field with a single pale-bone question-shaped gap of light, no subject, flat fills | wide plate, lime-teal mat at base, pale-bone dot above it, coral accent arrowless line rising further, no text | minimal plate, two flat columns of pale-bone marks on deep teal, one slightly taller, no numerals", "host_in_frame": False, "prompt_klein": "wide plate, empty night ink field with a single pale-bone question-shaped gap of light, no subject, flat fills | wide plate, lime-teal mat at base, pale-bone dot above it, coral accent arrowless line rising further, no text | minimal plate, two flat columns of pale-bone marks on deep teal, one slightly taller, no numerals. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B002", "section": 5, "sentence_ids": ["S097", "S098", "S099"], "start": 17.1, "end": 29.92, "duration": 12.82, "text": "Energy that collects in one body becomes a target for another. So a plausible ocean would not stop at grazers. A hunter here would face the same constraints as everything else: pressure, cold, and permanent dark.", "words": 36, "prompt": "detail crop, single pale-bone sphere with a coral accent ring closing around it, night ink background | wide context, chain of three distant silhouettes in a dark field, the last one larger and less readable | extreme wide, large unreadable silhouette low in frame under an ice roof, all black, no detail", "host_in_frame": False, "prompt_klein": "detail crop, single pale-bone sphere with a coral accent ring closing around it, night ink background | wide context, chain of three distant silhouettes in a dark field, the last one larger and less readable | extreme wide, large unreadable silhouette low in frame under an ice roof, all black, no detail. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B003", "section": 5, "sentence_ids": ["S100", "S101", "S102", "S103"], "start": 29.92, "end": 47.74, "duration": 17.81, "text": "We did not design one, because a predator is where invention starts to outrun constraint. Instead, ask what an arms race would even look like without light. One answer is already in our design set: light. The vent grazer signals with bioluminescence, in an ocean that never sees the sun.", "words": 50, "prompt": "wide plate, pale-bone outline that stops halfway across the frame and dissolves into hatching, coral accent at the break | wide plate, two pale-bone silhouettes facing each other across an empty deep teal gap, both distant, no detail | single coral accent glow point in black water, pale-bone halo, extreme minimal | extreme wide, distant grazer silhouette on a chimney with a small lime glow at its head, everything else night ink", "host_in_frame": False, "prompt_klein": "wide plate, pale-bone outline that stops halfway across the frame and dissolves into hatching, coral accent at the break | wide plate, two pale-bone silhouettes facing each other across an empty deep teal gap, both distant, no detail | single coral accent glow point in black water, pale-bone halo, extreme minimal | extreme wide, distant grazer silhouette on a chimney with a small lime glow at its head, everything else night ink. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B004", "section": 5, "sentence_ids": ["S104", "S105", "S106"], "start": 47.74, "end": 60.92, "duration": 13.18, "text": "In permanent darkness, light is the only language that travels. But a signal that travels is also a signal that can be intercepted. That is the whole logic of an arms race: every advantage becomes a vulnerability.", "words": 37, "prompt": "wide plate, three small lime-teal glow points in a black field, spaced apart, flat fills, no text | wide plate, one lime glow at left, a faint pale-bone eye-less shape at right, dark gap between them | minimal plate, pale-bone shield shape with a coral accent crack, night ink field", "host_in_frame": False, "prompt_klein": "wide plate, three small lime-teal glow points in a black field, spaced apart, flat fills, no text | wide plate, one lime glow at left, a faint pale-bone eye-less shape at right, dark gap between them | minimal plate, pale-bone shield shape with a coral accent crack, night ink field. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B005", "section": 5, "sentence_ids": ["S107", "S108", "S109"], "start": 60.92, "end": 78.02, "duration": 17.1, "text": "Camouflage against a glow, speed against a slow grazer, a harder shell against a jaw. Each of those is a guess about a guess, and we are not going to dress them up as findings. What we can say is that competition would not require sunlight, only scarcity.", "words": 48, "prompt": "wide plate, three flat panels: dark matte texture, motion streak, pale-bone ridged shell, separated by hard seams | wide plate, pale-bone outline of a shape drawn three times, each fainter, dissolving into night ink | wide plate, one lime-teal patch at frame edge, vast empty dark teal elsewhere, flat fills", "host_in_frame": False, "prompt_klein": "wide plate, three flat panels: dark matte texture, motion streak, pale-bone ridged shell, separated by hard seams | wide plate, pale-bone outline of a shape drawn three times, each fainter, dissolving into night ink | wide plate, one lime-teal patch at frame edge, vast empty dark teal elsewhere, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B006", "section": 5, "sentence_ids": ["S110", "S111", "S112"], "start": 78.02, "end": 94.05, "duration": 16.03, "text": "Bacterial mats coat the chimneys, which makes the food patchy by construction. Patchy food makes territory, and territory makes conflict. None of this is observed: all of it is the reasoning a field biologist would use on Earth, pointed at a place we cannot visit.", "words": 45, "prompt": "wide context, three separated chimney towers, lime mat only at their bases, empty water between | wide plate, two pale-bone boundary lines drawn around separate lime patches, coral accent where they meet | wide plate, pale-bone survey grid laid over an empty dark teal field, one coral accent marker, no text", "host_in_frame": False, "prompt_klein": "wide context, three separated chimney towers, lime mat only at their bases, empty water between | wide plate, two pale-bone boundary lines drawn around separate lime patches, coral accent where they meet | wide plate, pale-bone survey grid laid over an empty dark teal field, one coral accent marker, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B007", "section": 5, "sentence_ids": ["S113", "S114", "S115"], "start": 94.05, "end": 111.86, "duration": 17.81, "text": "And that is the limit of this section: the shape of an argument, with no animal attached to it. So we leave the predators unbuilt, and say so out loud. A predator is not a monster in this story, it is a bookkeeping entry that has not been filled in.", "words": 50, "prompt": "wide plate, pale-bone outline of a large shape with an empty interior, night ink field, no subject | minimal plate, empty coral accent frame with nothing inside, deep teal field | wide plate, empty coral accent frame in a black field, nothing inside, flat fills", "host_in_frame": False, "prompt_klein": "wide plate, pale-bone outline of a large shape with an empty interior, night ink field, no subject | minimal plate, empty coral accent frame with nothing inside, deep teal field | wide plate, empty coral accent frame in a black field, nothing inside, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B008", "section": 5, "sentence_ids": ["S116", "S117", "S118"], "start": 111.86, "end": 126.46, "duration": 14.61, "text": "And an unfilled entry is more honest than a creature invented to fill it. Our grazer already carries a light, which means it already carries a risk. Every signal in the dark is a decision about who gets to find you.", "words": 41, "prompt": "minimal plate, pale-bone blank rectangle on night ink, one coral accent edge, no text | extreme wide, distant grazer silhouette with a small lime glow at its head, black water around | wide plate, one lime-teal glow point with a faint pale-bone shape approaching from the far edge", "host_in_frame": False, "prompt_klein": "minimal plate, pale-bone blank rectangle on night ink, one coral accent edge, no text | extreme wide, distant grazer silhouette with a small lime glow at its head, black water around | wide plate, one lime-teal glow point with a faint pale-bone shape approaching from the far edge. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B009", "section": 5, "sentence_ids": ["S119"], "start": 126.46, "end": 138.46, "duration": 12, "text": "That is the arms race in one sentence, and we can leave it there without inventing a winner.", "words": 18, "prompt": "wide plate, two distant silhouettes facing each other, empty dark gap, no detail", "host_in_frame": False, "prompt_klein": "wide plate, two distant silhouettes facing each other, empty dark gap, no detail. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Predators, and the logic of an arms race — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B001", "section": 6, "sentence_ids": ["S120", "S121", "S122"], "start": 0.0, "end": 15.95, "duration": 15.95, "text": "Now go down, past the mats, to the floor of the world. At Enceladus, that floor is where the ocean meets rock, and where the vents are. The silica grains in the plume are the receipt: water and hot rock, interacting above ninety degrees.", "words": 44, "prompt": "wide context, descending water column from pale-bone ice to basalt floor, faint gradient, no subject | side cross-section, deep teal ocean layer meeting basalt charcoal core, coral accent at the seam, no subject | detail crop, pale-bone angular grains clustered beside dark rock, faint warm coral glow, flat fills", "host_in_frame": False, "prompt_klein": "wide context, descending water column from pale-bone ice to basalt floor, faint gradient, no subject | side cross-section, deep teal ocean layer meeting basalt charcoal core, coral accent at the seam, no subject | detail crop, pale-bone angular grains clustered beside dark rock, faint warm coral glow, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B002", "section": 6, "sentence_ids": ["S123", "S124", "S125"], "start": 15.95, "end": 29.73, "duration": 13.78, "text": "At Europa, the same meeting point would be the sea floor, under an ocean twice the size of ours. The ice burrower lives in the sediment at that boundary. It moves by peristalsis, pushing through sediment under load.", "words": 38, "prompt": "wide establishing plate, basalt floor with mineral wisps, huge dark teal water mass above, pale-bone ice far overhead | extreme wide, small segmented silhouette half-buried in pale-bone sediment, distant, no detail | detail crop, pale-bone sediment with a single smooth tunnel line and faint compression rings, no animal", "host_in_frame": False, "prompt_klein": "wide establishing plate, basalt floor with mineral wisps, huge dark teal water mass above, pale-bone ice far overhead | extreme wide, small segmented silhouette half-buried in pale-bone sediment, distant, no detail | detail crop, pale-bone sediment with a single smooth tunnel line and faint compression rings, no animal. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B003", "section": 6, "sentence_ids": ["S126", "S127", "S128"], "start": 29.73, "end": 44.23, "duration": 14.5, "text": "Near-freezing water and high pressure are the two constraints its body answers. We gave it no limbs, because limbs do not help in mud. It does not swim and it does not graze: it simply moves through the ground, slowly.", "words": 40, "prompt": "wide plate, pale-bone sediment band under dark teal water, sparse hatching, cold flat fills | minimal plate, pale-bone cylinder silhouette with no appendages, flat fills, deep teal field | extreme wide, faint tunnel traces through sediment, tiny silhouette at the far end, distant and unreadable", "host_in_frame": False, "prompt_klein": "wide plate, pale-bone sediment band under dark teal water, sparse hatching, cold flat fills | minimal plate, pale-bone cylinder silhouette with no appendages, flat fills, deep teal field | extreme wide, faint tunnel traces through sediment, tiny silhouette at the far end, distant and unreadable. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B004", "section": 6, "sentence_ids": ["S129", "S130", "S131"], "start": 44.23, "end": 58.0, "duration": 13.78, "text": "Everything down here ultimately traces back to chemosynthesis, the same chemistry as Earth's vents. The grazer stays near the chimneys, where the mats are. And it reproduces by budding, at the vents, where chemical energy is most abundant.", "words": 38, "prompt": "wide plate, lime-teal mat at the base of a black chimney, faint electric teal wisps rising, no creatures | extreme wide, grazer silhouette on a chimney at frame right, empty dark water at left | extreme wide, two small silhouettes attached at the base of one chimney, distant, all dark", "host_in_frame": False, "prompt_klein": "wide plate, lime-teal mat at the base of a black chimney, faint electric teal wisps rising, no creatures | extreme wide, grazer silhouette on a chimney at frame right, empty dark water at left | extreme wide, two small silhouettes attached at the base of one chimney, distant, all dark. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B005", "section": 6, "sentence_ids": ["S132", "S133", "S134"], "start": 58.0, "end": 73.59, "duration": 15.59, "text": "Budding is a design choice: no mate required, no season required, just energy and time. In a world sealed under ice, there is no daylight to synchronise with. So reproduction would have to be tied to something else: chemistry, temperature, or each other.", "words": 43, "prompt": "minimal plate, one pale-bone circle splitting into two smaller circles, coral accent at the join | wide plate, unbroken pale-bone ice lid across the top, black water below, no light shafts | wide plate, three flat pale-bone markers along a dark teal line, one coral accent, no text", "host_in_frame": False, "prompt_klein": "minimal plate, one pale-bone circle splitting into two smaller circles, coral accent at the join | wide plate, unbroken pale-bone ice lid across the top, black water below, no light shafts | wide plate, three flat pale-bone markers along a dark teal line, one coral accent, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B006", "section": 6, "sentence_ids": ["S135", "S136", "S137"], "start": 73.59, "end": 88.09, "duration": 14.5, "text": "Communication, in that world, would have to travel without any light from above. Bioluminescence is our answer: the creature makes its own light. It is also the least certain thing in this episode, and we are flagging it as such.", "words": 40, "prompt": "wide plate, black water column, one small lime glow at the centre, everything else night ink | extreme wide, distant silhouette with a small lime-teal halo at its head, subject tiny in a black field | minimal plate, single lime glow half-covered by a pale-bone bar, flat fills, no text", "host_in_frame": False, "prompt_klein": "wide plate, black water column, one small lime glow at the centre, everything else night ink | extreme wide, distant silhouette with a small lime-teal halo at its head, subject tiny in a black field | minimal plate, single lime glow half-covered by a pale-bone bar, flat fills, no text. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B007", "section": 6, "sentence_ids": ["S138", "S139", "S140"], "start": 88.09, "end": 101.86, "duration": 13.78, "text": "Three invented animals, one shared constraint: everything must work in the dark, under pressure, at near-freezing temperature. The grazer grips, the drifter filters, the burrower pushes. None of them has been seen, and all of them are possible.", "words": 38, "prompt": "wide plate, three small distant silhouettes in a row under an ice roof, all dark, no detail | wide plate, three abstract pale-bone marks: a six-spoke shape, a wavy line, a segmented bar, flat fills, no text | wide plate, three pale-bone outlines fading into night ink at the frame edges, one coral accent dot", "host_in_frame": False, "prompt_klein": "wide plate, three small distant silhouettes in a row under an ice roof, all dark, no detail | wide plate, three abstract pale-bone marks: a six-spoke shape, a wavy line, a segmented bar, flat fills, no text | wide plate, three pale-bone outlines fading into night ink at the frame edges, one coral accent dot. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B008", "section": 6, "sentence_ids": ["S141", "S142", "S143"], "start": 101.86, "end": 119.63, "duration": 17.76, "text": "Sediment is the quietest habitat in this world, and the burrower is built for quiet. Budding means the young are not scattered, they start where the energy already is. The chimney is a tower of chemistry, and the grazer is the animal that learned to hold on to it.", "words": 49, "prompt": "wide plate, pale-bone sediment plain under dark teal water, faint tunnel traces, no subject | extreme wide, two small silhouettes at the base of one chimney, lime glow beneath, distant | wide context, tall black chimney with lime mat at its base, tiny silhouette attached, distant", "host_in_frame": False, "prompt_klein": "wide plate, pale-bone sediment plain under dark teal water, faint tunnel traces, no subject | extreme wide, two small silhouettes at the base of one chimney, lime glow beneath, distant | wide context, tall black chimney with lime mat at its base, tiny silhouette attached, distant. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B009", "section": 6, "sentence_ids": ["S144", "S145"], "start": 119.63, "end": 131.62, "duration": 12, "text": "Three animals, three answers to the same exam question: how do you make a living where nothing grows from light? On Earth, that exam has already been passed, in water just as dark.", "words": 33, "prompt": "wide plate, three distant silhouettes in a row under an ice roof, all dark, unreadable | wide establishing plate, black vent chimney with lime-teal mat glow, no creatures, flat fills", "host_in_frame": False, "prompt_klein": "wide plate, three distant silhouettes in a row under an ice roof, all dark, unreadable | wide establishing plate, black vent chimney with lime-teal mat glow, no creatures, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B010", "section": 6, "sentence_ids": ["S146"], "start": 131.62, "end": 143.62, "duration": 12, "text": "And that is why the deep is the closest thing we have to a rehearsal for Europa.", "words": 17, "prompt": "wide context, basalt floor with mineral wisps under a vast dark teal water mass, pale-bone ice far above", "host_in_frame": False, "prompt_klein": "wide context, basalt floor with mineral wisps under a vast dark teal water mass, pale-bone ice far above. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: The deep, the vents, and the animals that stay — target 2:30. 1280x720, flat graphic style."}, {"bit_id": "B001", "section": 7, "sentence_ids": ["S147", "S148"], "start": 0.0, "end": 13.83, "duration": 13.83, "text": "Suppose life did appear under that ice: would it look like our designs, or like nothing we could guess? This is the part of the episode where the honest answer is that we do not know, and neither does anyone else.", "words": 41, "prompt": "wide plate, pale-bone outline shape at left, empty black space at right, hard flat seam between | wide plate, empty deep teal field with a single faint pale-bone horizon line, no subject", "host_in_frame": False, "prompt_klein": "wide plate, pale-bone outline shape at left, empty black space at right, hard flat seam between | wide plate, empty deep teal field with a single faint pale-bone horizon line, no subject. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B002", "section": 7, "sentence_ids": ["S149", "S150"], "start": 13.83, "end": 28.34, "duration": 14.51, "text": "There are two ways to think about it, and they point in opposite directions. The first says that physics narrows the options: if you need to grip rock in a current, six points of contact is one of a small number of answers.", "words": 43, "prompt": "minimal plate, two pale-bone arrows suggested by tapered bars pointing away from each other, no text | detail crop, pale-bone rock surface with six identical grip points arranged in a ring, sparse hatching", "host_in_frame": False, "prompt_klein": "minimal plate, two pale-bone arrows suggested by tapered bars pointing away from each other, no text | detail crop, pale-bone rock surface with six identical grip points arranged in a ring, sparse hatching. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B003", "section": 7, "sentence_ids": ["S151", "S152", "S153"], "start": 28.34, "end": 43.86, "duration": 15.52, "text": "The second says that history matters more than physics: what survives depends on what happened to arrive first. Under that view, our grazer is not a prediction, it is a coincidence waiting to be disproved. Both views are respectable, and neither is testable from a desk.", "words": 46, "prompt": "wide plate, scattered pale-bone marks drifting in deep teal, one coral accent mark ahead of the rest | extreme wide, tiny grazer silhouette at the centre of a vast empty field, subject almost lost | wide plate, two pale-bone rectangles side by side on night ink, both empty, flat fills", "host_in_frame": False, "prompt_klein": "wide plate, scattered pale-bone marks drifting in deep teal, one coral accent mark ahead of the rest | extreme wide, tiny grazer silhouette at the centre of a vast empty field, subject almost lost | wide plate, two pale-bone rectangles side by side on night ink, both empty, flat fills. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B004", "section": 7, "sentence_ids": ["S154", "S155", "S156", "S157"], "start": 43.86, "end": 61.41, "duration": 17.55, "text": "That is why the mission matters more than the argument. Europa Clipper is being built to measure the ice shell, the ocean, and the surface chemistry. Future missions could sample Enceladus' plumes directly, looking for the chemistry of life. Until then, every creature in this episode is a hypothesis with a shape.", "words": 52, "prompt": "wide context, small pale-bone probe silhouette above a moon disc, distant, no detail | wide context, small spacecraft silhouette in black space beside a pale-bone ice-covered moon, distant and schematic | wide context, small probe silhouette crossing a pale-bone plume venting from a moon at frame edge, distant | wide plate, pale-bone outline of an unreadable animal form, flat fills, deep teal field", "host_in_frame": False, "prompt_klein": "wide context, small pale-bone probe silhouette above a moon disc, distant, no detail | wide context, small spacecraft silhouette in black space beside a pale-bone ice-covered moon, distant and schematic | wide context, small probe silhouette crossing a pale-bone plume venting from a moon at frame edge, distant | wide plate, pale-bone outline of an unreadable animal form, flat fills, deep teal field. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B005", "section": 7, "sentence_ids": ["S158", "S159", "S160"], "start": 61.41, "end": 75.58, "duration": 14.17, "text": "And a hypothesis with a shape is easier to argue with than a vague hope. That is the point of designing them at all: to make our assumptions visible. If the ocean is empty, our designs are wrong in an interesting way.", "words": 42, "prompt": "minimal plate, pale-bone geometric outline beside a soft pale-bone blur, coral accent on the outline | wide plate, pale-bone survey lines revealing a faint silhouette inside a dark field, no text | wide plate, empty dark teal water column, one pale-bone outline erased to a dotted trace", "host_in_frame": False, "prompt_klein": "minimal plate, pale-bone geometric outline beside a soft pale-bone blur, coral accent on the outline | wide plate, pale-bone survey lines revealing a faint silhouette inside a dark field, no text | wide plate, empty dark teal water column, one pale-bone outline erased to a dotted trace. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B006", "section": 7, "sentence_ids": ["S161", "S162", "S163"], "start": 75.58, "end": 89.42, "duration": 13.83, "text": "And if it is not empty, they are probably wrong in a more interesting way. Either outcome teaches us something, and that is the best a guess can do. So would this world repeat? We will not know until someone looks.", "words": 41, "prompt": "wide plate, dense pale-bone fragments in dark water, one coral accent among them, no readable shapes | minimal plate, two pale-bone dots connected by a single coral accent line, night ink field | wide plate, pale-bone ice lid, black water, one tiny unreadable silhouette, extreme distance", "host_in_frame": False, "prompt_klein": "wide plate, dense pale-bone fragments in dark water, one coral accent among them, no readable shapes | minimal plate, two pale-bone dots connected by a single coral accent line, night ink field | wide plate, pale-bone ice lid, black water, one tiny unreadable silhouette, extreme distance. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}, {"bit_id": "B007", "section": 7, "sentence_ids": ["S164", "S165"], "start": 89.42, "end": 101.42, "duration": 12, "text": "The two views do not cancel each other, they set the size of the bet. Either way, the ocean is the thing to look at, and the ice is the door.", "words": 31, "prompt": "minimal plate, two pale-bone blocks of different sizes on night ink, one coral accent line between | wide context, pale-bone ice lid with a faint seam, dark teal water below, one coral accent at the seam", "host_in_frame": False, "prompt_klein": "minimal plate, two pale-bone blocks of different sizes on night ink, one coral accent line between | wide context, pale-bone ice lid with a faint seam, dark teal water below, one coral accent at the seam. thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration. Section: Chance and law: would this world repeat? — target 2:00. 1280x720, flat graphic style."}]
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
