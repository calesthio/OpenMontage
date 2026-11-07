# OpenMontage AI Illustration Style Bible

**Purpose:** Single source of truth for AI-generated illustration assets used as
backdrops/cards in OpenMontage Factory videos. All assets carry
`rights_basis=ai_generated_illustration` and the on-screen label "Illustration".
AI backdrops are limited to <= 10-15% of runtime (qc.py `ai_label_max_share`,
default 0.15).

**Provenance:** generated via Kaggle bridge batch jobs (tools/illustration/
illustration_batch.py) -> gitignored projects/image_gen/illustrations/ -> manifest
sha256+bytes verified (kaggle_bridge verify) -> auto QC
(tools/illustration/illustration_qc.py) -> approved set.

**Hard prohibitions (never):** photorealistic people/faces, celebrity likenesses,
text-legible logos or emblems (incl. NASA insignia per 14 CFR 1221), NSFW,
copyrighted characters. If any generated image violates these, quarantine it and
do not use.

---

## 1. Visual style (niche-agnostic baseline)

- **Line style:** flat vector illustration, clean geometric lines, minimal
  detail, no gradients, no shading, no texture, no photorealism.
- **Palette (hex):** deep-space navy #0B1021, star-field slate #1B263B,
  orbit cyan #4FC3F7, earth teal #2A9D8F, solar amber #E9C46A, station grey
  #8D99AE, paper white #F4F1DE, ink black #22223B, accent magenta #C23B22.
- **Background:** solid or two-tone flat gradient; no photographic depth.
- **Subjects:** diagrams, schematics, silhouettes, abstract orbits, window
  frames, solar panels, rockets, telescopes — objects only, no people.
- **Composition:** centered or rule-of-thirds with copy space; no words, no
  letters, no numerals (text-like artifacts are auto-flagged by QC).
- **Aspect:** 16:9 (1280x720) for full-frame backdrops; 1:1 (1024x1024) for
  cards; 9:16 (720x1280) for Shorts variants.

---

## 2. Prompt templates (fill {subject}, {seed}, {aspect})

**Backdrop template (full-frame):**
```
{subject}, flat vector illustration, clean geometric lines, deep space,
{minimal}, {palette_accent}, white background variant, no text, no letters,
no numerals, no people, no faces, no logos, no emblems, no photographic
detail, no gradients, no shading, --{aspect} --seed {seed}
```

**Card template (isolated object):**
```
{subject}, ink line art, flat vector, {palette_main}, isolated on white,
no text, no letters, no numerals, no people, no faces, no logos, --{aspect}
--seed {seed}
```

**Palette substitutions:**
- `{palette_main}`: one of deep-space navy / star-field slate / orbit cyan /
  earth teal / solar amber / station grey.
- `{palette_accent}`: one of solar amber / accent magenta / earth teal.
- `{minimal}`: "minimal" | "minimal illustration" (cycle per seed).

---

## 3. Seed policy

- Fixed seeds per niche+subject, recorded in manifest; never reuse a seed for
  two different subjects within one batch.
- Seed range: 3000-3999 reserved for illustrations (G1/G2 used 1000-1099 and
  2000-2009).
- Deterministic: same seed + same prompt + same model = same image (within a
  model version). Record model + revision in manifest.

---

## 4. Model policy (zero-cost, no paid routes)

- Preferred: SDXL-Lightning (4-step baseline, OpenRAIL++, commercial OK) via
  Kaggle T4 GPU when available.
- Fallback: Z-Image-Turbo (apache-2.0) or FLUX.2-klein-4B (apache-2.0) only
  if the official model card clearly allows commercial use; fp16 or quantized
  fallback; record peak VRAM.
- Never pay for a generation route. Record seconds/image, VRAM, GPU minutes.

---

## 5. Acceptance (auto QC, tools/illustration/illustration_qc.py)

- Blur: Laplacian variance >= 100 (not blurry).
- Duplicates: perceptual hash (average-hash, 8x8) Hamming distance > 8 between
  any pair in a batch (near-duplicates rejected).
- Aspect/size: exact target aspect (1280x720 or 1024x1024 or 720x1280), within
  1%.
- Text-like artifacts: OCR-free heuristic — reject images with > 3% near-white
  high-contrast thin rectangular clusters in expected text zones (top/bottom
  thirds); human review for borderline.
- Rights: rights_basis=ai_generated_illustration; label="Illustration".

---

## 6. Label

- Every AI-illustration cut in edit_decisions.json: generator=AI, label="Illustration",
  rights_basis=ai_generated_illustration.
- On-screen: burn a small "Illustration" chip (bottom-right, semi-transparent)
  on AI backdrop cards via PIL/ffmpeg; qc.py ai_illustration_label enforces
  presence + <= 0.15 share.
