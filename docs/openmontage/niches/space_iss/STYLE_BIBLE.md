# Space (ISS) Style Bible — FINAL (P2)

**Niche:** space_iss — ISS Earth view & cupola.
**Machine-readable style:** `docs/openmontage/niches/space_iss/style.json`
**Locked model:** `config/image_engine.json` → `klein` (prompt target `klein`,
variant C, 4 steps, guidance 1.0, fp16), status `OWNER_GATED`.
**Status: FINAL**

## 1. Purpose and media policy

Real NASA / archive footage is the primary visual of this niche. AI
illustrations are **inserts only**: at most **15% of the runtime**
(`ai_illustration_max_share: 0.15`). Everything in this bible applies to those
inserts — own diagrams and AI plates alike.

Excluded: identifiable private persons without clearance, NASA insignia or
emblems (14 CFR 1221 — cropped out where present), third-party credit
required, legible text inside images.

## 2. Visual style — orbital technical plate

- Technical schematic illustration: thin uniform strokes, flat fills,
  orthographic diagram look.
- No photographic background, no reflections, no lens flare, no gradients.
- Objects: station modules, cupola, robotic arm, orbit paths, Earth-observation
  phenomena — drawn as diagrams, never as fake photographs.

## 3. Palette

| Token | Hex | Use |
|---|---|---|
| orbital_black | #0B1622 | background / space |
| earth_blue | #2E6FA8 | Earth limb, atmosphere |
| vacuum_grey | #5A6672 | structure, station body |
| signal_orange | #E08A3C | the single accent (markings, highlights) |

## 4. Camera vocabulary

| View | Plate description |
|---|---|
| `front` | orthographic front elevation, full object centered |
| `side` | orthographic side elevation, full object centered |
| `three_quarter` | orthographic three-quarter elevation, near and far faces readable |
| `detail_crop` | close orthographic crop on one component |
| `wide_context` | wide schematic view of the assembly, small in frame |

## 5. Constraints — positive wording (the locked model has no negative prompt)

| id | positive form (used) | negative form (sdxl-family only) |
|---|---|---|
| no_text | clean image without text, text-free, no letters, no numerals, no watermark | text, watermark, letters, numerals, label text |
| not_photoreal | schematic line drawing, not a photograph, not a photorealistic render | photorealism, photograph, photorealistic render, cinematic lighting |
| no_people | uncrewed structure, no human figures | people, astronaut, person, human figure |
| no_logos | no emblems, no insignia, no flags, no logos, no agency marks | emblem, insignia, flag, logo, NASA insignia, agency mark |
| no_starfield | plain flat dark field, empty background | starfield, milky way, nebula, dense stars |
| copy_space | wide empty background space | cluttered background, busy composition |

`no_text`, `not_photoreal`, `no_people` and `no_logos` are applied by the
read-only prompt builder; the style kit injects the rest. A model that accepts
a negative prompt (SDXL family) gets the negative forms instead.

## 6. Anatomy rule

Not applicable: this niche has no creatures. Structural parts are named in the
prompt instead of anatomy counts. (The read-only builder still emits the
counts line "0 limbs, 0 eyes, 0 horns" — a known artefact of the builder
contract, harmless for diagrams, and left unchanged because the builder is
read only.)

## 7. Editorial overlays

Labels, callouts, arrows, dimension lines and numbers are drawn in the editor,
never by the image model.

## 8. Label rule

Every AI cut carries the label **"Illustration"** at the start of the cut and in
the cut description. The AI share must stay within the niche limit (≤ 15% of
runtime); the gate checks both.

## 9. Seed policy

Range **3000-3999** reserved for illustrations; one fixed seed per plate and
view, recorded in the manifest; never reuse a seed for two subjects inside one
batch.

## 10. Sources

- Profile: `docs/openmontage/niches/space_iss.yaml`
- Model card: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
  (accessed 2026-10-22)
- Seeds: `docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md` §3
