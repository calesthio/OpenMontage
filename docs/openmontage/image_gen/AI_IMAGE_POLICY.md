# AI Image Policy — OpenMontage (Milestone G1)

**Applies to:** AI-generated still images used as illustrations in OpenMontage productions.  
**Effective:** 2026-10-20  
**Rights basis:** `ai_generated_illustration`

## 1. Permitted use

AI-generated images may be used **only as illustrations** (backdrops, schematics, stylized sketches, abstract textures), never as a substitute for real footage.

Allowed subjects (non-photoreal, illustrative style only):
- abstract orbit-diagram backdrops
- stylized cupola-window / station sketches
- starfield / nebula gradients
- blueprint-style schematics
- flat-vector planet/earth curves

## 2. Prohibited use (hard rules)

- **Never presented as real footage.** AI images are illustrations; they must not be passed off as captured camera footage.
- **No real people.** No photorealistic or stylized likenesses of real individuals.
- **No real events.** No depictions presented as documentation of real occurrences.
- **No emblems / insignia.** No NASA emblem, agency logos, flags, or official seals.
- **No real vehicles presented as photos.** Vehicles may appear only in stylized/schematic form.
- **No text in the image.** Prompts must request no legible text; generated images must be checked for accidental text.
- **Not photoreal.** Output must remain in an illustrative style (flat vector, line art, blueprint, sketch).

## 3. On-screen label rule — "Illustration"

Every AI-generated image shown on screen must carry a visible **"Illustration"** label.

- **Maximum share of runtime:** AI-illustration content must not exceed **10–15% of total runtime** (policy ceiling 15%; target ≤10%).
- The label must be legible and present for the full duration the AI image is on screen.
- The QC gate fails any clip with `generator=AI` that lacks the `"Illustration"` label or exceeds the configured runtime share (see `tools/qa/qc.py` check `ai_illustration_label`).

## 4. Synthetic-content disclosure (YouTube)

Per YouTube's altered/synthetic content disclosure, content that is AI-generated or significantly altered and could be mistaken for real must be disclosed.

- **Official YouTube help page:** https://support.google.com/youtube/answer/13347880 ("Add labels to altered or synthetic content")
- **Checklist (cite and paraphrase the official page):**
  - [ ] Is the content AI-generated or altered in a way that could be mistaken for a real person, event, or place?
  - [ ] If yes, apply the required disclosure/label before publishing.
  - [ ] Do not present AI illustrations as real footage, real people, or real events.
  - [ ] Keep the disclosure consistent with YouTube's current requirements; review the official page at each release.

## 5. Records

Each generated image is recorded in `projects/image_gen/manifest.json` with:
- `sha256`, `bytes`, `prompt`, `seed`, `steps`, `guidance_scale`, `width`, `height`, `seconds`
- `model`, `model_revision`, `base_model`, `base_revision`
- `rights_basis: ai_generated_illustration`
- `generator: AI`

Images and manifest are downloaded via the Kaggle bridge and hashes are verified before use.

## 6. Verdict discipline

Observed quality problems (blur, artifacts, text, anatomy) are recorded in `G1_REPORT.md` as **observed**, not assumed. A channel-use verdict (USEFUL | MARGINAL | NOT_USEFUL) is stated there.
