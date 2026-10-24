# Art History Style Bible — FINAL (P2)

**Niche:** art_history — public-domain museum collections.
**Machine-readable style:** `docs/openmontage/niches/art_history/style.json`
**Locked model:** `config/image_engine.json` → `klein` (prompt target `klein`,
variant C, 4 steps, guidance 1.0, fp16), status `OWNER_GATED`.
**Status: FINAL**

## 1. Purpose and media policy

The niche's visuals are **real artworks** from CC0 / public-domain museum
records (Met, Smithsonian, Rijksmuseum, NGA, Wikimedia), each with its own
rights record. AI illustrations are **inserts only**, at most **15% of the
runtime** (`ai_illustration_max_share: 0.15`).

Hard rule for this niche: an AI plate must **never** imitate or reproduce a
specific real artwork. It may show a generic motif study or a diagram of a
composition — an invented subject of its own. Real artworks are never
presented as AI, and AI plates are never presented as real artworks.

## 2. Visual style — museum plate line drawing

- Fine ink contour lines, hatching for volume, monochrome with two muted
  accent washes, catalogue-plate framing with wide margins.
- No photographic texture, no impasto simulation, no chiaroscuro.
- Motifs: generic composition studies, technique diagrams, material and
  process diagrams — not reproductions.

## 3. Palette

| Token | Hex | Use |
|---|---|---|
| plaster_white | #F2EFE9 | paper / background |
| graphite | #3A3A3A | contour lines, hatching |
| ochre | #C08A3E | accent wash 1 |
| verdigris | #4E8073 | accent wash 2 |

## 4. Camera vocabulary

| View | Plate description |
|---|---|
| `front` | flat front view of the motif, centered, catalogue-plate margins |
| `side` | profile view of the motif, centered, catalogue-plate margins |
| `three_quarter` | three-quarter view of the motif, near and far planes readable |
| `detail_crop` | close crop on one detail of the motif |
| `wide_context` | wide plate of the motif in a generic setting, small in frame |

## 5. Constraints — positive wording (the locked model has no negative prompt)

| id | positive form (used) | negative form (sdxl-family only) |
|---|---|---|
| no_text | clean image without text, text-free, no letters, no numerals, no watermark, no signature | text, watermark, letters, numerals, signature, inscription |
| not_photoreal | drawn line work, not a photograph, not a photorealistic painting | photorealism, photograph, oil painting texture, photorealistic |
| no_people | no human figures, no faces, no portrait likeness | people, person, portrait, face, likeness, figure |
| no_logos | no emblems, no insignia, no flags, no logos, no watermarks | emblem, insignia, flag, logo, watermark, signature |
| no_fake_artwork | generic original motif study, an invented subject | copy of a known painting, famous artwork, reproduction of a specific artwork |
| plate_margins | wide plain margins around the motif | full bleed, cropped edges, busy frame |

`no_text`, `not_photoreal`, `no_people` and `no_logos` are applied by the
read-only prompt builder; the style kit injects the rest. A model that accepts
a negative prompt (SDXL family) gets the negative forms instead.

## 6. Anatomy rule

Not applicable: no creatures in this niche. The motif and its parts are named
in the prompt. (The read-only builder still emits the counts line "0 limbs,
0 eyes, 0 horns" — a known artefact of the builder contract, harmless for
plates, and left unchanged because the builder is read only.)

## 7. Editorial overlays

Labels, callouts, arrows, measurement lines and numbers are drawn in the editor,
never by the image model. Museum object labels always name the real object,
its date and its collection — and come from the museum record, not from the
image model.

## 8. Label rule

Every AI cut carries the label **"Illustration"** at the start of the cut and in
the cut description; the AI share stays within the niche limit (≤ 15% of
runtime). An AI plate is never presented as a real artwork.

## 9. Seed policy

Range **3000-3999** reserved for illustrations; one fixed seed per plate and
view, recorded in the manifest; never reuse a seed for two subjects inside one
batch.

## 10. Sources

- Profile: `docs/openmontage/niches/art_history.yaml`
- Model card: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
  (accessed 2026-10-22)
- Seeds: `docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md` §3
