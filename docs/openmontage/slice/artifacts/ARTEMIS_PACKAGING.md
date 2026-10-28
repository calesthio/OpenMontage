# Artemis I — Packaging (Milestone Z7)

**Episode:** Artemis I — SLS / Orion Mission Draft (3:05, 1920x1080p30, h264/aac)  
**Status:** DRAFT — NOT_PUBLISHABLE (see Z2 credits.txt)  
**Video:** projects/slice_artemis_v0/renders/final_artemis_draft.mp4 (gitignored media)

---

## 1. Three truthful titles

| # | Title | Rationale |
|---|---|---|
| 1 | Artemis I — SLS and Orion Mission Overview (NASA Footage Draft) | Describes subject (SLS/Orion), source (NASA footage), and draft status; no exaggeration |
| 2 | Artemis I Launch and Mission: SLS, Orion, and the Path to the Moon | Covers launch + mission content; no superlatives ("first", "best", "only") not supported by script |
| 3 | NASA Artemis I: SLS Rocket, Orion Spacecraft, and the 25.5-Day Mission | Specific mission duration from script; attributes NASA; no unverifiable claims |

**Truthfulness check:** No titles promise "Moon landing" (Artemis I was uncrewed, no landing), no "first woman/person of color" (that's Artemis II/III, not this video), no "Mars" content. All titles match the 20-sentence script (Z2).

---

## 2. Thumbnail text options

| # | Thumbnail file | Text on thumbnail | Source of visual |
|---|---|---|---|
| 1 | projects/slice_artemis_v0/thumbnails/thumb_01_title_card.png | "Artemis I — SLS / Orion Mission" | Own graphics card (card_title.png), downscaled to 1280x720 |
| 2 | projects/slice_artemis_v0/thumbnails/thumb_02_launch_frame.png | "Artemis I Launch" | NASA/MSFC Causeway slo-mo frame (50s), darkened for legibility |
| 3 | projects/slice_artemis_v0/thumbnails/thumb_03_apollo_test.png | "Artemis I — Moon Mission Draft" | Own graphics card (card_b1.png), downscaled to 1280x720 |

**Thumbnail rules verified:**
- 1280x720 PNG ✓
- From own graphics or NASA stills ✓
- No NASA emblem/logo ✓ (frame checked; card graphics contain no NASA insignia)
- No people ✓ (launch hardware only; no identifiable persons)
- No emblem ✓

---

## 3. Description (with chapters and credits block)

```
Artemis I — SLS and Orion Mission Overview (NASA Footage Draft)

An uncrewed flight test of NASA's Space Launch System rocket and Orion spacecraft,
the Artemis I mission launched November 16, 2022 from Kennedy Space Center's
Launch Pad 39B. This draft covers the SLS/Orion backbone, the launch, the
25.5-day lunar transit, two flybys within 80 miles of the surface, the farthest
distance (~270,000 miles from Earth), Pacific splashdown, and the path toward
Artemis II.

All footage is NASA public domain (source_policy_us_gov) or OpenMontage original
graphics. Narration is synthetic (Kokoro-82M, af_heart voice, local CPU).
This is a draft — not approved for public release.

CHAPTERS
0:00 — Title
0:08 — B1: Preparation — SLS / Orion backbone
0:22 — Launch B-roll (NASA Causeway slo-mo)
0:38 — B2: Launch — Pad 39B, Nov 16 2022
0:54 — Launch B-roll continued
1:10 — B3: Transit — 25.5-day lunar mission
1:24 — B4: Moon — flybys, farthest distance
1:42 — Launch B-roll continued
1:58 — Launch B-roll continued
2:14 — B5: Return — Pacific splashdown
2:36 — B6: Legacy — Artemis II, deep-space backbone
2:58 — Credits

CREDITS
Title: Artemis I — SLS / Orion Mission Draft
Director: OpenMontage Factory Pipeline
Production: OpenMontage (YouTube Factory)

Footage:
- Artemis I Launch (Causeway Slo Mo), GX010506, NASA Image and Video Library (images-api.nasa.gov), NASA/MSFC, 2022-11-16 — source_policy_us_gov — archive inserts, 4x 16s segments, 1920x1080 used unscaled

Graphics (OpenMontage originals):
- card_title.png — Title
- card_b1.png — B1 Preparation
- card_b2.png — B2 Launch
- card_b3.png — B3 Transit
- card_b4.png — B4 Moon flybys
- card_b5.png — B5 Return
- card_b6.png — B6 Legacy
- card_credits.png — Credits

Narration: Kokoro-82M (af_heart), Apache-2.0 weights, synthetic voice, local CPU synthesis. 20 sentences, 185.45s.
Subtitles: sentence SRT from measured Kokoro timings; word-level timestamps from stable-ts (whisper-tiny) forced alignment.

No third-party credit. Identifiable persons / NASA logo flags unreviewed from metadata (NEEDS_REVIEW).
NOT_PUBLISHABLE: voice-license residual risk • no clip frame-level review • NASA insignia clearance pending • synthetic-voice disclosure pending • 4 single-source claims flagged.
```

---

## 4. Synthetic-voice disclosure checklist

**Official YouTube help page (verified):** https://support.google.com/youtube/answer/14328491  
**"Disclosing use of GenAI content — Computer — YouTube Help"**

| # | Checklist item | YouTube help page guidance (paraphrased) | Status |
|---|---|---|---|
| 1 | Disclose synthetic voice narration | YouTube requires creators to disclose AI-generated or meaningfully AI-altered content that seems realistic. Synthetically generating a person's voice to narrate a video is listed as content that needs disclosure. | PENDING — owner must set "AI use" = Yes in YouTube Studio during upload |
| 2 | Use YouTube Studio "AI use" setting | Disclosure is made during upload in YouTube Studio: Attributes section → "AI use" → select Yes if content meets disclosure requirements. | NOT_DONE — upload not performed (no publishing in this milestone) |
| 3 | Label appears to viewers | If "Yes" is selected, YouTube adds a label to the video (on the video player for photorealistic AI content, or in the expanded description for non-photorealistic/animated content). | NOT_DONE — depends on upload |
| 4 | Disclosure doesn't limit reach/monetization | Per the help page: "Disclosing AI content won't limit a video's audience or impact its eligibility to earn money." | N/A — informational |
| 5 | Realistic voice = disclosure required | Kokoro-82M af_heart is a realistic synthetic voice. Narration is the primary audio of the video. Disclosure is required. | PENDING — owner action |
| 6 | Script generation with AI = no disclosure needed | YouTube does not require disclosure for generative AI used for productivity (scripts, content ideas, automatic captions). Script was written by the pipeline; only the voice needs disclosure. | OK — no action needed for script |
| 7 | Paraphrased disclosure wording for description | "This video uses a synthetic (AI-generated) voice for narration. Disclosed per YouTube's AI content policy." | READY — see below |

**Paraphrased disclosure text (for video description or metadata):**

> Synthetic-voice disclosure: This video uses an AI-generated voice (Kokoro-82M, "af_heart") for narration. Disclosed in accordance with YouTube's altered/synthetic content policy: https://support.google.com/youtube/answer/14328491

**Owner action required:** Before any upload, set "AI use" = Yes in YouTube Studio Attributes section. Do not publish without this disclosure — the Kokoro-82M voice is realistic synthetic audio and YouTube's policy requires it.

**NOT_PUBLISHABLE reasons (carried from Z2):** voice-license residual risk (Kokoro-82M synthetic-data training provenance unresolved) • no clip frame-level review • NASA insignia clearance pending • synthetic-voice disclosure pending (see above) • 4 single-source claims flagged (APOLLO-style flags not applicable to Artemis; Artemis SINGLE_SOURCE claims are ARTEMIS-02, ARTEMIS-04, ARTEMIS-12).
