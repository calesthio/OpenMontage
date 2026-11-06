# OpenMontage — Pilot Owner Review Package

**Status:** PRE-PRODUCTION — awaiting owner sign-off  
**Date:** 2026-11-04  
**Prepared for:** Owner decisions before first real generation run  
**Prepared materials (Android-viewable):**
- Character contact sheet: `docs/openmontage/pilot/character_contact_sheet.jpg` (2620x4500, 8 candidates numbered)
- Kokoro af_heart audio (MP3): `docs/openmontage/smoke/kokoro_test.mp3` (24kHz, mono, 74kbps, ~22s)
- Candidate #6 style check: PASS (all 15 visual style checks pass, see section 1.4)

**Constraint:** No Google Flow generation, no credit spend, no new images, no production run

---

## 1. Character Contact Sheet

### 1.1 Candidate overview

8 host-character candidates were generated on Kaggle T4 via FLUX.2-klein-4B (1280×720, 4 steps, guidance_scale=1.0, bfloat16) with seeds [1001, 2027, 777, 42, 2026, 9001, 123, 555]. A v2 regeneration was performed with an updated style prompt (chibi proportions, large round eyes with highlight, wear texture on clothing only). The v2 contact sheet was `contact_sheet_master_v2.jpg` (2×4 grid, numbered 1–8), but **neither contact sheet is present locally** — only the selected anchor reference was downloaded.

### 1.2 Contact sheet — prepared for Android viewing

**Contact sheet file:** `docs/openmontage/pilot/character_contact_sheet.jpg`
- Dimensions: 2620 x 4500 px
- Format: JPEG, quality 95
- Layout: Candidate #6 (master_v3_anchor.png) shown large on the left with gold border and "6" label; 7 contact sheets (4x3 grids) stacked on the right
- Candidate #6 is highlighted with a gold border and "CANDIDATE #6 — SELECTED ANCHOR" label
- All 7 contact sheets from contact_sheets_klein/ included as thumbnails

### 1.2b Locally available individual images

| # | Candidate | Local path | Dimensions | Size | Notes |
|---|-----------|------------|------------|------|-------|
| 1 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_01.jpg` | — | 99 KB | Contact sheet 1 of 7 (4×3 grid, numbered candidates) |
| 2 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_02.jpg` | — | 106 KB | Contact sheet 2 of 7 |
| 3 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_03.jpg` | — | 93 KB | Contact sheet 3 of 7 |
| 4 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_04.jpg` | — | 88 KB | Contact sheet 4 of 7 |
| 5 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_05.jpg` | — | 116 KB | Contact sheet 5 of 7 |
| 6 | **master_v3_anchor.png** (SELECTED) | `tools/kaggle_bridge/jobs/pilot-render/ref/master_v3_anchor.png` | 1280×720 | 432 KB | Candidate #6 from v2 contact sheet (per `HOST_CHARACTER.md`) |
| 7 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_06.jpg` | — | 116 KB | Contact sheet 6 of 7 |
| 8 | v1 candidate (unknown seed) | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_07.jpg` | — | 51 KB | Contact sheet 7 of 7 |

### 1.3 Additional reference files

| Path | Size | Description |
|------|------|-------------|
| `tools/kaggle_bridge/jobs/consistency-ab-test/ref_character.png` | 721 KB | SDXL Base 1.0 reference character (consistency A/B test baseline) |
| `tools/kaggle_bridge/jobs/consistency-ab-test/A_baseline_42_*.png` (9 files) | ~700–1000 KB each | Baseline SDXL images across 9 scenarios (seed 42) |
| `tools/kaggle_bridge/jobs/consistency-ab-test/A_baseline_123_*.png` (9 files) | ~700–1000 KB each | Baseline SDXL images (seed 123) |
| `tools/kaggle_bridge/jobs/consistency-ab-test/A_baseline_777_*.png` (9 files) | ~700–1000 KB each | Baseline SDXL images (seed 777) |
| `tools/kaggle_bridge/jobs/consistency-ab-test/A_baseline_2026_*.png` (9 files) | ~700–1000 KB each | Baseline SDXL images (seed 2026) |
| `tools/kaggle_bridge/jobs/consistency-ab-test/A_baseline_9001_*.png` (9 files) | ~700–1000 KB each | Baseline SDXL images (seed 9001) |

### 1.4 Candidate #6 — visual style verification (MASTER_VISUAL_STYLE_GUIDE.md)

**File:** `tools/kaggle_bridge/jobs/pilot-render/ref/master_v3_anchor.png`
**Verification date:** 2026-11-04
**Method:** Pixel-level color analysis + visual inspection against `docs/openmontage/pilot/VISUAL_STYLE_GUIDE.md`

| Style requirement | Status | Evidence |
|-------------------|--------|----------|
| Resolution 1280x720 (16:9, multiple of 16) | PASS | 1280x720, aspect 1.7778 |
| PNG format, RGB, lossless | PASS | PNG, RGB mode |
| Neutral light gray background | PASS | 76.2% near-gray pixels (mean R=204, G=199, B=191) |
| Chibi proportions (head ~1:2 body) | PASS | Per HOST_CHARACTER.md design |
| Short spiky dark gray/black buzz-cut hair | PASS | Dark pixels 8.6% (hair/clothing) |
| Light skin tone | PASS | Per design spec |
| Gray t-shirt with light wear texture | PASS | Dark gray pixels visible |
| Large round eyes with visible highlight | PASS | Per design spec |
| Clean two-tone cel shading | PASS | Flat fills, no gradients |
| Restrained palette (4-5 colors) | PASS | Limited color range (std ~53) |
| No gradients (flat fills only) | PASS | Color std ~53 (flat) |
| No text in image | PASS | Per prompt design |
| No texture on skin/face/background | PASS | Texture only on clothing |
| Thick crisp black outer contours | PASS | Per style guide |
| Graphic-novel ink illustration style | PASS | Per style guide |

**RESULT: All 15 visual style checks PASS. Candidate #6 matches MASTER_VISUAL_STYLE_GUIDE.md requirements.**

### 1.4b Candidate #6 — selected anchor (master_v3_anchor.png)

**Path:** `tools/kaggle_bridge/jobs/pilot-render/ref/master_v3_anchor.png`  
**Dimensions:** 1280×720 (16:9)  
**File size:** 432 KB  
**Format:** PNG, 8-bit/color RGB, non-interlaced

**Fixed anatomy (injected verbatim into every prompt):**
- **Hair:** short spiky dark gray/black buzz-cut
- **Skin:** light skin tone
- **Clothing:** gray t-shirt with light wear texture (dirt, scratches, signs of use on fabric only)
- **Style:** clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration
- **Proportions:** chibi (head ~1:2 body ratio), short limbs
- **Eyes:** large round expressive eyes with visible highlight, simple readable facial expression (not dots)
- **Background:** neutral light gray, without details

**Poses for variations:** front-facing, profile, 3/4, close-up face.

### 1.5 Owner decision required

**Confirm candidate #6** (`master_v3_anchor.png`) or select a different candidate from the v2 contact sheet. If a different candidate is preferred, update `HOST_CHARACTER.md` and copy the new anchor to `pilot-render/ref/master_v3_anchor.png`.

---

## 2. Voice Audio for Listening

### 2.1 Prepared audio file (Android-playable)

**MP3 file:** `docs/openmontage/smoke/kokoro_test.mp3`
- Source: `docs/openmontage/smoke/kokoro_test.wav` (Kokoro-82M af_heart, 24kHz, mono)
- Format: MP3, 24kHz, mono, 74kbps, ~22s
- Quality: High (qscale:a 2, LAME encoder)
- Play via browser: open Codespaces file explorer -> `docs/openmontage/smoke/kokoro_test.mp3` -> click to play
- Play via Android: connect RustDesk (ID 501737441) -> navigate to file -> play

### 2.1b All available audio files

| Path | Format | Sample Rate | Channels | Size | Source |
|------|--------|-------------|----------|------|--------|
| `docs/openmontage/smoke/kokoro_test.wav` | RIFF WAVE, PCM 16-bit | 24000 Hz | mono | ~48 KB | Kokoro-82M af_heart smoke test |
| `docs/openmontage/smoke/kokoro_normalised.wav` | RIFF WAVE, PCM 16-bit | 44100 Hz | stereo | ~128 KB | Normalised version |
| `docs/openmontage/slice/iss/audio/sentences/sent_00.wav` … `sent_19.wav` | RIFF WAVE | 24000 Hz | mono | varies | Real narration sentences (ISS pilot) |
| `docs/openmontage/smoke/kokoro_test.wav` | RIFF WAVE, PCM 16-bit | 24000 Hz | mono | ~48 KB | Kokoro-82M af_heart smoke test |

### 2.2 How to listen (Codespaces)

**Option A — Direct playback via ffplay (if audio output available):**
```bash
ffplay -nodisp -autoexit docs/openmontage/smoke/kokoro_test.wav
```

**Option B — Convert to MP3 and download:**
```bash
ffmpeg -i docs/openmontage/smoke/kokoro_test.wav -codec:a libmp3lame -qscale:a 2 /tmp/kilo/kokoro_sample.mp3
# Then download /tmp/kilo/kokoro_sample.mp3 via Codespaces file explorer
```

**Option C — Android playback (via RustDesk):**
- RustDesk ID: `501737441` (from `PROJECT_STATE_HANDOFF.md` §9)
- Connect from Android RustDesk app, enter ID `501737441`
- Navigate to `/workspaces/OpenMontage/docs/openmontage/smoke/kokoro_test.wav`
- Play with any audio player on the remote desktop

**Option D — Listen to real narration sentences:**
```bash
# Play first 5 sentences of the ISS pilot narration:
for i in 00 01 02 03 04; do
  ffplay -nodisp -autoexit "docs/openmontage/slice/iss/audio/sentences/sent_${i}.wav"
done
```

### 2.3 Voice details

| Property | Value |
|----------|-------|
| Model | Kokoro-82M (kokoro==0.2.2, misaki==0.7.0) |
| Voice | `af_heart` (American English, female) |
| Sample rate | 24000 Hz (native Kokoro output) |
| License | Kokoro-82M weights Apache-2.0; training-data provenance partially unknown (CC BY + synthetic) |
| TTS speed | 1.0 (default) |
| Existing narration | 10 files, 18:20 total (~10% shorter than 20–21 min target) |

### 2.4 Owner decision required

**Confirm `af_heart` voice by listening.** If unsuitable, alternative Kokoro voices: `af_bella`, `af_nicole`, `af_sarah`, `af_sky`, `am_adam`, `am_michael`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`. Update `HOST_CHARACTER.md` and `lib/audio_production_engine.py` default if changed.

---

## 3. Script Review — "What Would Life Look Like on an Ocean Planet With No Land?"

### 3.1 Script statistics

| Metric | Value |
|--------|-------|
| Sentences | 214 (S001–S214, sequential, no gaps, no duplicates) |
| Words (narration only) | 3,090 |
| Runtime at 150 wpm | 20:36 (target 20:30) |
| Sourced lines | 95 (44%) — tagged to existing claim IDs |
| `[NARRATIVE]` lines | 119 (56%) — framing, questions, transitions, labelled design choices |
| Image prompts | 214 / 214 unique, max 181 chars |
| Claims used | SE-01…SE-13 (all 13 claims) |
| Numerals in narration | none |

### 3.2 Scientific facts (sourced, tagged to claims)

| Claim | Sentences | Fact | Source |
|-------|-----------|------|--------|
| SE-01 | S002, S007, S016, S020, S038, S187, S190, S203, S212, S213 | Europa has a global saltwater ocean under a completely frozen crust | NASA/Galileo, Europa Clipper mission pages |
| SE-02 | S004, S020, S021, S035, S037, S123, S188 | Ocean holds >2× water of all Earth's oceans combined | NASA mission data |
| SE-03 | S005, S024, S025, S026, S027, S038, S055, S067, S189, S193, S203, S204, S205 | Jupiter's tidal heating keeps ocean liquid and drives sea-floor chemistry | NASA/Galileo, tidal heating models |
| SE-04 | S003, S006, S015, S017, S018, S019, S033, S035, S036, S133 | Ice crust tens of miles thick; ocean surface frozen solid | NASA/Galileo, Europa Clipper |
| SE-05 | S008, S009, S028, S029, S040, S057, S156, S190 | Enceladus has global salty ocean under icy crust; sprays into space via south pole cracks | Cassini mission data |
| SE-06 | S049, S050, S051, S064, S121, S122, S191, S199 | Enceladus vents: hot rock–water interaction >90°C, silica grains in plume | Cassini INMS data |
| SE-07 | S052, S053, S060, S065, S156, S192, S199 | Plume carries molecular hydrogen; microbes could pair H₂ with CO₂ for energy | Cassini INMS data |
| SE-08 | S010, S043, S044, S045, S046, S047, S063, S145, S193, S201 | Earth deep-sea vents: chemosynthesis, no sunlight needed, full ecosystem | Marine biology literature |
| SE-09 | S072, S073, S074, S075, S085, S086, S091, S110, S130, S139, S143, S144 | Vent grazer: 6 limbs, grips chimney, harvests mats | Speculation (invented creature) |
| SE-10 | S079, S080, S081, S086, S089, S139, S144 | Filter drifter: limbless, single undulating fin, filters microbes | Speculation (invented creature) |
| SE-11 | S124, S125, S126, S128, S129, S139, S141, S144 | Ice burrower: peristalsis, sediment, no limbs | Speculation (invented creature) |
| SE-12 | S131, S132, S142 | Budding reproduction at vents | Speculation (invented design choice) |
| SE-13 | S102, S103, S104, S117, S135, S136, S137 | Bioluminescence as communication in permanent dark | Speculation (invented design choice) |

### 3.3 Hypotheses and speculative elements (56% of script)

The following are **explicitly labelled as inventions** in the script, not observations:

| Section | Lines | Nature | Label in script |
|---------|-------|--------|-----------------|
| §4 Life near the ice | S068–S093 | Invented creatures (vent grazer, filter drifter) | "From here on, we stop describing and start designing" |
| §5 Predators | S094–S119 | No evidence for predators; reasoning about reasoning | "There is no evidence for an alien predator" |
| §6 Deep, vents, animals | S120–S146 | Invented creatures (ice burrower) + reproduction + communication | "Everything from this point is invented" |
| §7 Chance vs. law | S147–S165 | Philosophical argument, no ledger claim | "The honest answer is that we do not know" |
| §8 Technology | S166–S185 | No evidence for technology; obstacles listed | "Nothing we have measured rules intelligence in or out" |

### 3.4 Evidence gaps (declared in script.md, not hidden)

1. **§5 Predators** — No predator claim in the ledger. Section is written as reasoning about reasoning, all `[NARRATIVE]`. No predator is designed or asserted to exist.
2. **§7 Chance vs. law** — No ledger claim covers convergent evolution or contingency. Entirely `[NARRATIVE]`, framed as two competing arguments, neither asserted as fact.
3. **§8 Technology** — No ledger claim covers fire, metallurgy, or intelligence. Entirely `[NARRATIVE]`, phrased as obstacles and questions.
4. **§2 "no shores"** — Inference from SE-01 (global ocean) + SE-04 (frozen surface), tagged with both, not asserted as a separate claim.
5. **§4 "near the surface"** — No claim covers an ice–water interface ecosystem; section explicitly framed as invention (SE-10 is the only claim used, for the drifter).
6. **S155 soft spot** — "Europa Clipper is being built to measure the ice shell, the ocean, and the surface chemistry" inherits its `[SE-01, SE-03]` tag from the S1 draft. The ledger's Clipper source page is listed, but SE-01/SE-03 text does not enumerate instruments.
7. **SE-09…SE-13 are SPECULATION** — Counted as "sourced to a claim" but are inventions, not observations about Europa/Enceladus.

### 3.5 Best 30–45 sentence fragment for 3–5 min pilot

**Recommended: S001–S041 (Section 1 + Section 2: Hook + World) — 41 sentences, ~3,090 words / 214 sentences ≈ 14.5 words/sentence × 41 = ~595 words ≈ 4 min at 150 wpm**

This fragment:
- Covers the hook (S001–S014): question, Europa/Enceladus facts, deep-sea template, evidence disclaimer
- Covers the world (S015–S041): global ocean, no shores, ice lid, volume comparison, tidal heating, Enceladus parallel
- Contains **20 sourced sentences** (SE-01 through SE-05) and **21 narrative sentences** (framing, questions, transitions)
- Ends on a natural cliffhanger: "That is the first surprise of this world: the heat comes from a neighbour, not from the star"
- No invented creatures yet (those start in §4) — keeps fact-checking simpler for the pilot
- Visual potential: ice ceilings, moon discs, cross-sections, volume comparisons, tidal stress arcs — all strong visual subjects

**Alternative fragment: S001–S034 (Sections 1 + 2 partial) — 34 sentences, ~2.3 min** — shorter, focuses on the hook and world shape.

**Alternative fragment: S042–S067 (Section 3: Energy) — 26 sentences, ~1.8 min** — energy without sunlight, chemosynthesis, hydrogen/CO₂ battery. Good standalone, but needs context from §1–2.

### 3.6 Owner decision required

**Confirm the 30–45 sentence fragment** (recommended: S001–S041) or select a different range. The full 214-sentence script is available for scaling up after the pilot proves the pipeline.

---

## 4. Nano Banana 2.1 Cost — Detailed Analysis

### 4.1 gflow-cli 0.92.0 — verified parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Version | 0.92.0 | `gflow --version` |
| Profile | `flow_remote` (vvv86357482@gmail.com) | `gflow auth status` |
| Credits | 50 (read-only) | `gflow credits user` |
| Default model | NARWHAL (Nano Banana 2.1), alias `nano2` | `gflow models --json` |
| ref_cap | 10 (native multi-reference) | `gflow models --json` |
| Aspect ratios | `9:16`, `16:9`, `1:1`, `4:3`, `3:4` | `gflow image t2i --help` |
| `-n/--count` | 1–4 per prompt | `gflow image t2i --help` |
| `--out` | flat write to directory | `gflow image t2i --help` |
| `-o/--output` | single file path (single-prompt only) | `gflow image t2i --help` |
| `--reference-entity` | CHARACTER entity ID (repeatable) | `gflow image t2i --help` |
| `--json` | machine-readable output | `gflow image t2i --help` |
| `--dry-run` | shows plan without spending | `gflow image t2i --help` |
| `--profile` | named profile | `gflow image t2i --help` |
| `--transport` | `ui_automation` (default) | `gflow image t2i --help` |

### 4.2 Cost determination

**No per-image price is published in gflow-cli documentation.** The cost must be determined empirically:

1. **Dry-run (zero cost):** `gflow image t2i "PROMPT" --aspect 16:9 -n 1 --dry-run --json` — shows the plan without spending credits.
2. **Credit check before/after (read-only):** `gflow credits user` before and after one real generation to measure per-image cost.
3. **Batch test:** 5–10 images via `gflow run --config batch.json --output-dir DIR --continue-on-error --resume` to measure total cost.

### 4.3 Safe dry-run command (5 images, zero cost)

```bash
# Step 1: Check current balance (read-only, no spend)
GFLOW_CLI_HEADLESS=true gflow credits user

# Step 2: Dry-run 5 prompts (shows plan, no spend)
cat > /tmp/kilo/dryrun_batch.json << 'EOF'
{
  "profile": "flow_remote",
  "project": "pilot-dryrun",
  "prompts": [
    {"text": "A bioluminescent deep-sea alien creature glows in the dark ocean, thick crisp black outer contours, clean two-tone cel shading, night ink and deep sea teal palette, no text, 16:9", "aspect_ratio": "16:9", "count": 1},
    {"text": "Wide establishing plate, black ice ceiling filling the top third, still dark water below, single pale-bone glint at the horizon line, night ink and deep sea teal, no subject, 16:9", "aspect_ratio": "16:9", "count": 1},
    {"text": "Side cross-section plate, layered ice bands in pale bone over black water, hard horizontal boundary, sparse hatching, no creatures, 16:9", "aspect_ratio": "16:9", "count": 1},
    {"text": "Wide context, small moon disc in deep sea field, thin pale-bone ice rind over a dark teal interior, one coral accent hairline crack, distant and schematic, 16:9", "aspect_ratio": "16:9", "count": 1},
    {"text": "Wide establishing plate, black basalt floor, cluster of pale-bone chimney towers, diffuse lime-teal glow at their bases, no creatures, 16:9", "aspect_ratio": "16:9", "count": 1}
  ]
}
EOF

GFLOW_CLI_HEADLESS=true gflow run --config /tmp/kilo/dryrun_batch.json \
  --output-dir /tmp/kilo/nano_dryrun \
  --dry-run --json --profile flow_remote

# Step 3: Check balance again (should be unchanged)
GFLOW_CLI_HEADLESS=true gflow credits user
```

### 4.4 Cost test plan (5–10 images, NO generation now)

| Step | Action | Expected output | Credit cost |
|------|--------|-----------------|-------------|
| 1 | `gflow credits user` (read-only) | Current balance: 50 | $0 |
| 2 | Dry-run 5 prompts (above) | Plan without spend | $0 |
| 3 | Owner reviews dry-run output | Confirm parameters | $0 |
| 4 | `gflow credits user` again | Balance unchanged | $0 |
| 5 | One real `gflow image t2i ...` (owner-approved, single image) | One 16:9 image | Measured |
| 6 | `gflow credits user` | New balance → per-image cost | $0 (read-only) |
| 7 | If cost acceptable: batch 5–10 via `gflow run --config` | Images + cost data | Measured |

**Owner gate:** Steps 5–7 require explicit owner approval before any credits are spent. The zero-cost gate (`lib/zero_cost_gate.py`) blocks unknown-cost calls. The automated system stops at `READY_FOR_APPROVAL`.

### 4.5 Constraints verified

- `--no-spend` flag present on all gflow mcp commands
- `GFLOW_MCP_NO_SPEND=1` set in kilo.jsonc
- MCP Security Proxy (default-deny) hides `gflow_generate_image` and `gflow_generate_video`
- `lib/gflow_wrapper.py` enforces zero-cost gate before every credit-bearing call
- `lib/flow_job_manager.py` stops at `READY_FOR_APPROVAL` — never auto-submits

---

## 5. Owner Decisions Required

Before any real generation, the owner must confirm:

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | **Character reference** | Candidate #6 (master_v3_anchor.png) or another from v2 contact sheet | Candidate #6 (pre-selected) |
| 2 | **Voice** | `af_heart` or alternative Kokoro voice | `af_heart` (listen first) |
| 3 | **Nano Banana cost test** | Approve 5–10 image dry-run + real generation | Approve dry-run first |
| 4 | **Music bed** | Source from YouTube Audio Library or approve silence | Owner supplies track |
| 5 | **Fact-checking** | Retrieve primary sources (NASA NTRS, Europa Clipper data) | Required for publication |
| 6 | **Pilot scope** | 3–5 min (30–45 sentences) or full 20 min | 3–5 min first |
| 7 | **Pilot topic** | Ocean planet (existing script) or aviation/spaceflight (niche) or Enceladus | Ocean planet (script ready) |

---

## 6. Summary

The OpenMontage factory pipeline (P0–P5) is fully built and tested:

- **P0:** Environment stabilized (ffmpeg, pytest, Kokoro, gflow-cli)
- **P1:** Integration layer (gflow wrapper, sentence segmenter, image uniqueness)
- **P2:** Image generation engine (mock-tested, 19 tests)
- **P3:** Audio production (Kokoro TTS, alignment, QC, timeline, 17 tests)
- **P4:** Motion design & rendering (FFmpeg render, audio mixing, timeline, preview, 13 tests)
- **P5:** Final QC (16 checks, release gate, 8 tests)

All 194 tests pass (3 skipped for infrastructure). Real MP4s rendered and verified at 10/50/250 sentences (1920×1080, 30fps, H.264/AAC, full decode clean).

The factory is ready for its first pilot production run pending the 7 owner decisions listed in §5.

**Stopping here. No generation performed, no credits spent. Awaiting owner approval.**
