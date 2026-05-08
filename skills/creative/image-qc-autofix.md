---
name: image-qc-autofix
layer: 2
status: optional-postprocess
added: 2026-05-08
ported_from: VRSEN/OpenSwarm image_generation_agent (commit 28e5fe38)
related: image-provider-usage.md, image-gen-usage.md
---

# Image QC Auto-Fix Loop

> **What this is:** A standardized post-generation quality-control pattern. Run after any image-generation tool call — `gemini_image`, `flux_image`, `openai_image`, `recraft_image`, `grok_image`, `local_diffusion`, `google_imagen`. Catches common defects (composition drift, missing elements, broken text, scale issues, lighting artifacts, hallucinated content) and triggers exactly **one** corrective regeneration before final delivery.

> **Why it exists:** OpenMontage already has Layer-1 EP gating + checkpoint protocol for full pipelines. But for **single-shot image generation calls** outside a pipeline (one-off product shots, blog hero, slide image, asset for an existing video), there's no automated quality gate. This skill fills that gap with a 60-second QC ritual.

> **When to use:** Any image generation that will be **delivered to a client** or **used as a reference for downstream video generation**. Skip for throw-away tests or agent-internal scratch images.

---

## The Loop

```
┌─────────────────────────────────────────────────────────┐
│ 1. GENERATE        gemini_image / flux_image / etc.     │
│ 2. QC PASS         5-bullet checklist (see below)       │
│ 3. PASS?           Yes → deliver. No → fix once.        │
│ 4. FIX             Same prompt, smarter model           │
│ 5. QC PASS #2      Repeat checklist                     │
│ 6. STILL FAILING?  Stop. Report failures + 1 next move. │
└─────────────────────────────────────────────────────────┘
```

**Hard rule:** Maximum **two** generations per QC loop (initial + 1 fix). Do not loop forever — that's how budgets explode.

---

## Step 1: Generate

Pick a provider per `image-provider-usage.md`. For new work, default to `gemini_image` with `gemini-2.5-flash-image` (cheap + fast for the first take).

## Step 2: QC Pass — 5-Bullet Checklist

Look at the rendered image as if a client just sent it back asking "What's wrong with this?"

Tick each bullet **PASS / FAIL** with one-line evidence:

1. **Composition match** — does the framing, subject placement, and aspect ratio match the prompt? (PASS / FAIL: "subject is centered but prompt asked for rule-of-thirds left")
2. **Required elements present** — every named entity in the prompt visible? (PASS / FAIL: "missing the second figure described in the prompt")
3. **Text fidelity** — if any text/labels were specified, are they spelled correctly and readable? (PASS / FAIL: "the word 'PREMIUM' came out as 'PREMUM'")
4. **Lighting + color** — does the lighting/palette/mood match the prompt? Any hot spots, banding, or color shifts? (PASS / FAIL: "shadows are too harsh, prompt asked for soft diffused light")
5. **Artifacts + anatomy** — extra fingers, distorted faces, illegible patterns, weird edges? (PASS / FAIL: "hand has 6 fingers")

**Decision rule:** All 5 PASS → deliver. **Any FAIL** → go to Step 3.

## Step 3: One Auto-Fix Pass

The fix should be **smarter, not just retried**. Strategy:

| Failure type | Fix strategy |
|--------------|--------------|
| Composition / scale | Same provider, augment prompt with explicit framing ("centered, rule-of-thirds left, 3/4 view"). Re-run. |
| Missing element | Same provider, prepend element with "MUST INCLUDE: ..." phrasing. Re-run. |
| Text fidelity broken | **Upgrade to `gemini-3-pro-image-preview` or `openai_image` (GPT Image 1)** — both have superior text rendering. |
| Multi-constraint adherence | **Upgrade to `gemini-3-pro-image-preview`** — best instruction following. |
| Anatomy / artifact | Same provider with negative prompt ("avoid extra fingers, distorted hands") OR upgrade to `flux_image` for photorealism. |
| Style mismatch | Same provider, encode style explicitly in prompt text (don't rely on enum). |
| All-around poor | Upgrade tier (Flash → 3 Pro) OR switch family (Gemini → OpenAI / Flux). |

**Cost note:** A single upgrade from `gemini-2.5-flash-image` (~$0.04) to `gemini-3-pro-image-preview` (~$0.10) is the cheapest precision step in the lineup. Only upgrade once per loop.

## Step 4: QC Pass #2

Same 5-bullet checklist. Document what changed between attempt 1 and attempt 2.

## Step 5: Final Decision

- **All 5 PASS:** Deliver with the file path + 1-line summary.
- **Some FAIL still:** Stop. Output:
  - File path (the better of the two attempts)
  - List of remaining failures
  - **One** specific next move ("retry with `recraft_image` for SVG-grade text" / "use `text_card` from Remotion for the badge text" / "manual edit in Photoshop").

Never deliver a "best-effort" image without surfacing what's still wrong.

---

## Output Format

After every QC loop, the orchestrator should produce:

```
Image generation: <prompt summary>
- Provider: <tool>:<model>
- Output: <absolute path>
- QC status: PASS|PARTIAL|FAIL
- Checklist:
  ✓ Composition match — <evidence>
  ✓ Required elements present — <evidence>
  ✗ Text fidelity — "PREMUM" should be "PREMIUM" → upgraded to gemini-3-pro-image-preview, fixed
  ✓ Lighting + color — <evidence>
  ✓ Artifacts + anatomy — <evidence>
- Auto-fix used: yes (Flash → 3 Pro for text fidelity)
- Cost: $0.14 (2 generations)
- Next step (if PARTIAL/FAIL): <one concrete suggestion>
```

---

## Integration with EP Gating

This skill is **complementary** to the existing EP (Executive Producer) protocol used in cinematic / animation / video-clone pipelines. EP gating handles **multi-stage** quality control across an entire pipeline (proposal → script → scene → asset → edit → compose → publish). QC auto-fix handles **single-shot** images that bypass full EP.

If you're already inside an EP-gated pipeline, the EP's existing review covers this. Don't double-run the QC loop.

---

## Anti-Patterns

1. **Retry forever** — hard cap is 2 generations. If a Flash-then-3-Pro-then-Flux-then-Recraft loop still fails, the prompt itself is broken. Report and stop.
2. **Skip QC because "it looked fine"** — every delivered image gets the 5-bullet check. Two bullets take 30 seconds; one missed broken word costs a re-render.
3. **Auto-fix without changing strategy** — re-running the same model with the same prompt produces the same defect. Always change something (model tier, prompt augmentation, family switch).
4. **Hallucinated PASS** — never tick PASS without evidence. "Looks good" is not evidence.
5. **Deliver before final QC** — even after auto-fix, run the checklist again. The fix may have introduced new issues.

---

## When to skip this skill

- Inside an EP-gated full pipeline (cinematic / animation / character-animation) — the EP already reviews.
- Throw-away test images for prompt iteration.
- Bulk variant generation (`num_variants > 1`) where the user explicitly wants raw outputs to pick from.
- Non-deliverable internal-only assets.

---

## Relationship to OpenSwarm

This pattern is ported from `VRSEN/OpenSwarm`'s `image_generation_agent/instructions.md` (commit 28e5fe38, 2026-05-08). OpenMontage adopts the **discipline** without the dependency — same QC ritual, applied to OpenMontage's broader 8-provider image lineup.
