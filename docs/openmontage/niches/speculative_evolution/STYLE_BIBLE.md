# Speculative Evolution Style Bible — FINAL (P2)

**Niche:** speculative_evolution / alien ecosystems (AI stills only).
**Rights basis:** ai_generated_illustration · generator: AI · AI share: 100%.
**Machine-readable style:** `docs/openmontage/niches/speculative_evolution/style.json`
(the kit reads this file; this document is its human-readable twin).
**Locked model:** `config/image_engine.json` → `klein` (FLUX.2-klein-4B, prompt target
`klein`, variant C, 4 steps, guidance 1.0, fp16). Status `OWNER_GATED` until the
owner blind-scores the models.
**Status: FINAL** (owner-gated on the model choice, not on this style).

## 1. Purpose

Single source of truth for every AI-generated still of the alien-ecosystem
pilot ("How could life survive beneath a frozen alien ocean?"). 100% AI stills,
no footage, no video generation, no legible text inside images.

## 2. Visual style — field-guide plate

- Flat-vector field-guide plate, silhouette-first, minimal detail, clean
  geometric lines, flat fills.
- One flat fill per surface, no gradients, no shading, no photographic depth.
- Outline weight constant across a plate; the silhouette must read at
  thumbnail size.
- Objects only: alien creatures, habitats, anatomy crops, food-web plates.
  No people, no real events.

## 3. Palette

| Token | Hex | Use |
|---|---|---|
| deep_teal | #14455C | background / deep ocean |
| bioluminescent_lime | #A8E06F | creature glow, vents, flora |
| basalt_charcoal | #3B444B | rock, ice shadows, silhouettes |
| pale_bone | #EDE7D8 | highlights, mats, distant ice |

## 4. Camera vocabulary

| View | Plate description |
|---|---|
| `front` | full body straight from the front, symmetric, both flanks visible |
| `side` | full body in profile, silhouette readable edge to edge |
| `three_quarter` | full body at a three-quarter angle, near and far side readable |
| `detail_crop` | close crop on one anatomy detail |
| `wide_context` | wide establishing view of the habitat, subject small in frame |

Every canonical creature sheet contains `front`, `side` and `three_quarter`.

## 5. Anatomy spec rule (mandatory per creature)

Every creature carries a written anatomy spec before it is drawn
(OpenCode's YAML, read only):

- **limb count, eye count, horn count** — integers;
- **2–3 dominant features**;
- **one canonical silhouette**, reused across every shot of that creature.

The counts are written into **every** prompt ("6 limbs, 2 eyes, 0 horns"); a
prompt without the counts is invalid and the kit refuses to build it. The
canonical silhouette goes into the prompt as its first clause (the full text
stays in the YAML spec) so the prompt stays inside the builder's 1200-character
limit.

## 6. Constraints — positive wording (the locked model has no negative prompt)

The locked model (klein) takes **no negative prompt**, so every constraint is
written **positively** into the prompt. The read-only prompt builder
(`tools/prompting/builder.py`) already applies `no_text`, `not_photoreal`,
`no_people`, `no_logos`; the style kit injects the rest:

| id | positive form (used) | negative form (sdxl-family only) |
|---|---|---|
| no_text | clean image without text, text-free, no letters, no numerals, no watermark | text, watermark, letters, numerals, signature |
| not_photoreal | flat vector rendering, not photorealistic, no photographic depth | photorealism, photograph, photorealistic, 3d render |
| no_people | uninhabited scene, no human figures | people, person, human figure |
| no_logos | no emblems, no insignia, no flags, no logos | emblem, insignia, flag, logo, watermark |
| even_light | uniform flat shading | gradients, bloom, volumetric light |
| copy_space | wide empty copy space above | cluttered background, busy composition |

For a model that accepts a negative prompt (the SDXL family: `sdxl`,
`sdxl-lightning`, `dreamshaper-xl-lightning`) the negative forms are used
instead — and only then.

## 7. Editorial overlays — drawn in the editor, never by the image model

Labels, scale bars, arrows, maps and numbers are drawn in the editor
(PIL/ffmpeg overlay). The image model never renders legible text; text-like
artifacts are auto-flagged by the image QC and borderline cases go to the owner.

## 8. Label rule — "Speculative illustration"

AI share is 100%, so every AI cut carries the label **from the first frame**
and in the cut description/metadata. The gate requires
`label = "Speculative illustration"` and a non-empty description on every AI
cut. Other AI_IMAGE_POLICY gates are not weakened (no photoreal people, no
text in the image, no real events, no emblems/insignia).

## 9. Motion variety (editor motion on stills)

Pan/zoom with differing easing (easein / easeout / easeinout), detail crops,
parallax; no two identical moves in a row (`motion_variety.lint_variation`).

## 10. Seed policy

- Range **3000-3999** reserved for illustrations (G1/G2 used 1000-1099 and
  2000-2009). The S7 bake-off used 4000-4022 and the episode planner 7000+ —
  those are outside the reserved range; new work uses the reserved range.
- One fixed seed per creature **and** view, recorded in the manifest.
- Never reuse a seed for two subjects inside one batch.

## 11. Prohibited content (hard rules)

No photorealistic people, faces or real individuals · no photorealistic fake
events presented as real · no text, letters, numerals or legible watermarks in
the image · no real vehicles presented as photos · no emblems, insignia or
flags. Anything violating these is quarantined and not used.

## 12. Sources

- Profile: `docs/openmontage/niches/speculative_evolution/speculative_evolution.yaml`
- Creature specs: `docs/openmontage/niches/speculative_evolution/creatures/*.yaml`
  (OpenCode-owned, **read only** — the kit never writes them)
- Prompt builder: `tools/prompting/builder.py` (OpenCode-owned, **read only**)
- Model card: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
  (accessed 2026-10-22) — prompt style sensitivity, multi-reference editing
- Style seeds: `docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md` §3
