# Speculative Science Style Bible — FINAL (P2)

**Niche:** speculative_science — hypotheses and thought experiments.
**Machine-readable style:** `docs/openmontage/niches/speculative_science/style.json`
**Locked model:** `config/image_engine.json` → `klein` (prompt target `klein`,
variant C, 4 steps, guidance 1.0, fp16), status `OWNER_GATED`.
**Status: FINAL**

## 1. Purpose and media policy

Real NASA / archive footage and peer-reviewed sources carry the evidence; AI
illustrations are **inserts only**, at most **15% of the runtime**
(`ai_illustration_max_share: 0.15`).

Two hard rules:

- **Speculation must be labelled as speculation** (`speculation_label_required:
  true` in the profile). Every AI cut carries the label "Speculative
  illustration" at the start of the cut and in the cut description.
- A plate must never be presented as a real event or a real observation.

## 2. Visual style — hypothesis schematic plate

- Schematic science plate: clean vector diagram, thin uniform strokes, flat
  fills, diagram layout, no photographic background.
- Diagrammatic, not scenic: the mechanism, the setup or the system is drawn,
  not photographed.
- Own diagrams (drawn in the editor) are the primary visual; AI plates are
  supporting art.

## 3. Palette

| Token | Hex | Use |
|---|---|---|
| slate_blue | #33506B | structure, primary shapes |
| hypothesis_amber | #D99A2B | the speculative element, accent |
| counter_teal | #2F7F79 | counter-hypothesis / secondary element |
| paper_grey | #E6E3DC | background / grid |

## 4. Camera vocabulary

| View | Plate description |
|---|---|
| `front` | flat orthographic view of the mechanism, centered |
| `side` | cutaway side view of the mechanism, centered |
| `three_quarter` | three-quarter cutaway view, near and far planes readable |
| `detail_crop` | close crop on one component of the mechanism |
| `wide_context` | wide schematic of the whole system, small in frame |

## 5. Constraints — positive wording (the locked model has no negative prompt)

| id | positive form (used) | negative form (sdxl-family only) |
|---|---|---|
| no_text | clean image without text, text-free, no letters, no numerals, no watermark | text, watermark, letters, numerals, axis labels |
| not_photoreal | schematic diagram, not a photograph, not a photorealistic scene | photorealism, photograph, photorealistic, cinematic lighting |
| no_people | no human figures | people, person, human figure, portrait |
| no_logos | no emblems, no insignia, no flags, no logos | emblem, insignia, flag, logo |
| no_real_event | generic illustrative mechanism, an invented diagram subject | real event, real incident, news photograph, specific dated event |
| copy_space | wide empty background space | cluttered background, busy composition |

`no_text`, `not_photoreal`, `no_people` and `no_logos` are applied by the
read-only prompt builder; the style kit injects the rest. A model that accepts
a negative prompt (SDXL family) gets the negative forms instead.

## 6. Anatomy rule

Not applicable: no creatures in this niche. The mechanism and its parts are
named in the prompt. (The read-only builder still emits the counts line "0
limbs, 0 eyes, 0 horns" — a known artefact of the builder contract, harmless
for diagrams, and left unchanged because the builder is read only.)

## 7. Editorial overlays

Labels, callouts, arrows, axis lines and numbers are drawn in the editor, never
by the image model. Diagrams that carry numbers (e.g. a launch probability) get
their numbers from the cited source, not from the model.

## 8. Label rule

Every AI cut carries the label **"Speculative illustration"** at the start of the
cut and in the cut description; the niche gate requires the speculation label.
The AI share stays within the niche limit (≤ 15% of runtime).

## 9. Seed policy

Range **3000-3999** reserved for illustrations; one fixed seed per plate and
view, recorded in the manifest; never reuse a seed for two subjects inside one
batch.

## 10. Sources

- Profile: `docs/openmontage/niches/speculative_science.yaml`
- Model card: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
  (accessed 2026-10-22)
- Seeds: `docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md` §3
