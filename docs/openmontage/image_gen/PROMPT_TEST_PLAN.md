# Prompt Test Plan — Speculative Evolution / Alien Ecosystems (AI stills only)
**Milestone S3-2 (OpenCode)** | Niche: speculative_evolution | Pilot: "life beneath a frozen alien ocean"
**Status:** DRAFT (owner approves before Kilo's bridge job runs)

## 1. Purpose
Blind, seed-controlled comparison of three image models (sdxl, zimage, klein)
on the same 12 fixed scenes, each rendered in 3 prompt variants (A tags, B
prose, C prose with anatomy first). Outputs feed the S3-3 rubric scorer to
pick a winning model x variant for the pilot's AI stills.

## 2. Run matrix (what Kilo's bridge job reads)
**File:** `docs/openmontage/image_gen/prompt_test_matrix.json` (schema below).
**Blind mapping:** `docs/openmontage/image_gen/prompt_test_mapping.json`
(neutral `render_id` → human-readable scene/model/variant/seed). Kilo's bridge
reads only the matrix; outputs are named by neutral `render_id` so reviewers
are blinded. The mapping file is kept separate and used only to unblind after
scoring. **Do not edit Kilo's bridge code** — the matrix is a read-only input.

### Schema (`prompt_test_matrix.json`)
| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | string | "1.0" |
| `niche` | string | "speculative_evolution" |
| `pilot` | string | pilot title |
| `total_scenes` | int | 12 |
| `models` | string[] | ["sdxl","zimage","klein"] |
| `variants` | string[] | ["A","B","C"] |
| `combos_per_scene` | int | 9 |
| `total_renders` | int | 108 |
| `seed_mode` | string | "same seed per scene across all model/variant combos" |
| `seeds` | int[] | [4000..4011] |
| `aspect` | string | "16:9" |
| `resolution` | int[] | [1280,720] |
| `style` | string | "flat-vector field-guide plate" |
| `palette` | object | deep_teal #14455C, bioluminescent_lime #A8E06F, basalt_charcoal #3B444B, pale_bone #EDE7D8 |
| `constraints` | object | no_text, no_people, no_logos, not_photorealistic, silhouette_first |
| `jobs[]` | array | one render job per scene×model×variant |

Each job:
| Field | Type | Meaning |
|-------|------|---------|
| `render_id` | string | neutral ID "r0001".."r0108" (blind output name) |
| `scene_id` | string | "s01".."s12" |
| `model` | string | sdxl \| zimage \| klein |
| `variant` | string | A \| B \| C |
| `seed` | int | scene seed (4000-4011), same across all 9 combos of a scene |
| `spec` | object | creature/scene spec: subject, anatomy {limb_count, eye_count, horn_count, dominant_features}, environment, light, style, palette, camera, constraints |

Prompt rendering per job is done by `tools/prompting.PromptBuilder` (S3-1):
- **sdxl:** structured phrases + separate negative prompt
  ("extra limbs, fused legs, duplicate subject, text, watermark, photorealism"),
  guidance 7.5, 50 steps.
- **zimage:** descriptive prose, style FIRST, 3–5 key visual concepts, NO
  negative prompt, constraints phrased positively; guidance 0, 9 steps.
- **klein:** narrative prose, subject + anatomy in the FIRST sentence, NO
  negative prompt, constraints phrased positively; 4 steps.
- Variants A/B/C: tags / prose / prose-with-anatomy-first. Negation vs
  positive switch controls the "no text" phrasing.

## 3. The 12 fixed scenes
Breakdown mirrors S1-1: 4 single-creature silhouettes, 3 habitat scenes, 2
anatomy-detail crops, 2 food-web background plates, 1 planet-surface wide.

| Scene | Seed | Label |
|-------|------|-------|
| s01 | 4000 | Vent grazer single silhouette on vent chimney |
| s02 | 4001 | Vent grazer full-body silhouette |
| s03 | 4002 | Filter drifter in open water |
| s04 | 4003 | Ice burrower in sediment |
| s05 | 4004 | Vent chimney field habitat |
| s06 | 4005 | Under-ice cavern habitat |
| s07 | 4006 | Abyssal plain habitat |
| s08 | 4007 | Vent grazer forelimb anatomy crop |
| s09 | 4008 | Filter drifter filter-mouth anatomy crop |
| s10 | 4009 | Food-web plate: bacteria, vent grazer, filter drifter |
| s11 | 4010 | Food-web plate: ice burrower, bacteria, detritus |
| s12 | 4011 | Planet-surface wide with vent plumes |

Creature anatomy (from the style bible / S3-4 creature specs):
- Vent grazer: 6 limbs, 2 eyes, 0 horns; long neck + spade-like forelimbs.
- Filter drifter: 0 limbs (fins), 0 eyes, 0 horns; undulating fin + wide filter mouth.
- Ice burrower: 0 limbs (peristaltic), 0 eyes, 0 horns; tapered head + segmented body.

Full per-scene specs live in `prompt_test_matrix.json` (the `spec` object).

## 4. Blind naming scheme
- Outputs are named by neutral `render_id` (r0001..r0108) — no model, variant,
  or creature name in the filename.
- `prompt_test_mapping.json` maps `render_id` → {scene_id, scene_label, model,
  variant, seed}. It is **not** given to blind reviewers; the owner uses it to
  unblind after scoring.
- Same seed per scene across all 9 combos ⇒ any difference between models/
  variants is attributable to the model/prompt, not the seed.

## 5. How results are consumed
Kilo's bridge job renders the 108 jobs and writes images + a per-job manifest.
The S3-3 rubric scorer (`scripts/score_rubric.py`) ingests owner/reviewer
scores (CSV) and outputs per model × variant: severe-artifact rate, repair
burden, usable share, and a winner table (≥24 images per cell required, else
"INSUFFICIENT"). 108 renders ÷ 9 cells = 12 images per cell, which is BELOW
the 24-image minimum, so the owner should either (a) double the scenes or
(b) accept that the winner call will be INSUFFICIENT and treat results as
directional. Flag this to the owner before running.

## 6. Rights / policy
- All images: AI-generated illustrations only, `rights_basis: ai_generated_illustration`,
  `generator: AI`, `ai_share: 1.0`. Persistent "Speculative illustration" label
  (S1 style bible). No photoreal people, no text in image, no logos/emblems,
  not photorealistic (AI_IMAGE_POLICY.md).
- No YouTube search calls used in this plan (quota exhausted per S2_STATE.md).

## 7. Files
- `docs/openmontage/image_gen/PROMPT_TEST_PLAN.md` (this document)
- `docs/openmontage/image_gen/prompt_test_matrix.json` (run matrix for Kilo's bridge)
- `docs/openmontage/image_gen/prompt_test_mapping.json` (blind unblinding map; keep separate)

## 8. Owner decision needed
Approve the matrix (108 renders) and confirm acceptance of the
<24-images-per-cell "INSUFFICIENT" winner rule, or approve expanding scenes
to reach ≥24 per cell before Kilo's bridge job runs.
