# OpenMontage — Pilot Approval Package

**Status:** PRE-PRODUCTION — awaiting owner approval  
**Date:** 2026-11-04  
**Prepared for:** Owner sign-off before first real generation run

---

## 1. Character Approval

### 1.1 Candidate sources (no new generation performed)

8 host-character candidate images were generated on Kaggle T4 via FLUX.2-klein-4B (1280×720, 4 steps, guidance_scale=1.0, seeds [1001, 2027, 777, 42, 2026, 9001, 123, 555]) and assembled into a contact sheet `contact_sheet_master.jpg` / `contact_sheet_master_v2.jpg` on Kaggle. The v2 regeneration used an updated style prompt (chibi proportions, large round eyes with highlight, wear texture on clothing only). A v2 contact sheet was produced but **neither contact sheet is present locally** — only the selected anchor reference was downloaded.

### 1.2 Locally available character reference files

| # | Path | Dimensions | Size | Description |
|---|------|------------|------|-------------|
| 1 | `tools/kaggle_bridge/jobs/pilot-render/ref/master_v3_anchor.png` | 1280×720 | 432 KB | Candidate #6 from v2 contact sheet (selected anchor, per `docs/openmontage/pilot/HOST_CHARACTER.md`) |
| 2 | `tools/kaggle_bridge/jobs/consistency-ab-test/ref_character.png` | — | 721 KB | SDXL Base 1.0 reference character (consistency A/B test baseline) |
| 3 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_01.jpg` | — | 99 KB | Contact sheet 1 of 7 (4×3 grid, numbered) |
| 4 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_02.jpg` | — | 106 KB | Contact sheet 2 of 7 |
| 5 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_03.jpg` | — | 93 KB | Contact sheet 3 of 7 |
| 6 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_04.jpg` | — | 88 KB | Contact sheet 4 of 7 |
| 7 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_05.jpg` | — | 116 KB | Contact sheet 5 of 7 |
| 8 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_06.jpg` | — | 116 KB | Contact sheet 6 of 7 |
| 9 | `tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/contact_sheet_klein_07.jpg` | — | 51 KB | Contact sheet 7 of 7 |

### 1.3 Recommended character anchor

**Candidate #6** (`master_v3_anchor.png`) is the designated anchor per `docs/openmontage/pilot/HOST_CHARACTER.md`. It was selected from the v2 contact sheet and saved as the master reference. Its anatomy (fixed description, injected verbatim into every prompt):

- **Hair:** short spiky dark gray/black buzz-cut
- **Skin:** light skin tone
- **Clothing:** gray t-shirt with light wear texture (dirt, scratches, signs of use on fabric only)
- **Style:** clean two-tone cel shading, restrained palette, no gradients, graphic-novel ink illustration
- **Proportions:** chibi (head ~1:2 body ratio), short limbs
- **Eyes:** large round expressive eyes with visible highlight, simple readable facial expression (not dots)
- **Background:** neutral light gray, without details

### 1.4 Character consistency mechanism

- **gflow `--reference-entity`** (ref_cap=10) provides native multi-reference consistency across image generations — no IP-Adapter needed.
- `lib/character_consistency_manager.py` registers anatomy (limb count, features, clothing, palette) and validates scenes against it.
- The hero character appears only where it serves the narrative (every 4th sentence by default), never in every image.
- Text description alone is NOT accepted as proof of visual consistency.

### 1.5 Owner decision required

**Pick one of the 8 candidates** from the v2 contact sheet (`contact_sheet_master_v2.jpg`) as the master reference. Candidate #6 is pre-selected as the anchor. If a different candidate is preferred, update `HOST_CHARACTER.md` and copy the new anchor to `pilot-render/ref/master_v3_anchor.png`.

---

## 2. Voice Approval

### 2.1 Available audio files

| Path | Format | Sample Rate | Channels | Size |
|------|--------|-------------|----------|------|
| `docs/openmontage/smoke/kokoro_test.wav` | RIFF WAVE, PCM 16-bit | 24000 Hz | mono | ~48 KB |
| `docs/openmontage/smoke/kokoro_normalised.wav` | RIFF WAVE, PCM 16-bit | 44100 Hz | stereo | ~128 KB |
| `docs/openmontage/slice/iss/audio/sentences/sent_00.wav` … `sent_19.wav` | RIFF WAVE | 24000 Hz | mono | varies |

### 2.2 Voice details

- **Model:** Kokoro-82M (kokoro==0.2.2, misaki==0.7.0)
- **Voice:** `af_heart` (American English, female)
- **Sample rate:** 24000 Hz (native Kokoro output)
- **License:** Kokoro-82M weights Apache-2.0; training-data provenance partially unknown (CC BY + synthetic, UNKNOWN origin) → owner sign-off required
- **Status:** 10 narration files generated (18:20 total), ~10% shorter than 20–21 min target (TTS pace vs. 150 wpm human pace)

### 2.3 Listen to the sample

```bash
# Play the real Kokoro af_heart sample (mono, 24 kHz):
ffplay -nodisp -autoexit docs/openmontage/smoke/kokoro_test.wav

# Or convert to MP3 for easier listening:
ffmpeg -i docs/openmontage/smoke/kokoro_test.wav -codec:a libmp3lame -qscale:a 2 /tmp/kilo/kokoro_sample.mp3
```

### 2.4 Owner decision required

**Confirm `af_heart` voice by listening.** If the voice is unsuitable, alternative Kokoro voices available locally: `af_bella`, `af_nicole`, `af_sarah`, `af_sky`, `am_adam`, `am_michael`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`. If a different voice is chosen, update `HOST_CHARACTER.md` and `lib/audio_production_engine.py` default.

---

## 3. Nano Banana Cost Test Plan

### 3.1 gflow-cli status (verified, read-only)

| Item | Value |
|------|-------|
| Version | gflow 0.92.0 |
| Profile | `flow_remote` (vvv86357482@gmail.com) |
| Credits | 50 (read-only verified via `gflow credits user`) |
| CLI path | `/home/vscode/.local/bin/gflow` |
| Headless | `GFLOW_CLI_HEADLESS=true` required in Codespace |
| Spend guard | `--no-spend`, `GFLOW_MCP_NO_SPEND=1`, MCP Security Proxy (default-deny) |
| Auth status | Valid session (verified via `gflow auth status`) |

### 3.2 Nano Banana 2.1 (NARWHAL) parameters

| Parameter | Value |
|-----------|-------|
| Model alias | `nano2` (default), `nano2.1`, `nano-2.1` |
| ref_cap | 10 (native multi-reference character consistency) |
| Aspect ratios | `9:16`, `16:9`, `1:1`, `4:3`, `3:4` |
| `-n/--count` | 1–4 images per prompt |
| `--reference-entity` | CHARACTER entity ID (repeatable, shared ref-budget with `--ref`) |
| Output | PNG, flat write to `--out` directory |

### 3.3 Command to generate one image

```bash
GFLOW_CLI_HEADLESS=true gflow image t2i \
  "A bioluminescent deep-sea alien creature glows in the dark ocean, thick crisp black outer contours, clean two-tone cel shading, night ink and deep sea teal palette" \
  --aspect 16:9 --model nano2 -n 1 \
  --out /tmp/kilo/nano_test \
  --reference-entity CHAR-HERO-1 \
  --json
```

### 3.4 Cost determination

**No per-image price is published in the gflow-cli documentation.** The cost must be determined empirically:

1. **Dry-run first:** `gflow image t2i "PROMPT" --aspect 16:9 -n 1 --dry-run --out /tmp/kilo/nano_test --json` — shows the plan without spending credits.
2. **Credit check before/after:** `gflow credits user` before and after one real generation to measure per-image cost.
3. **Batch test:** Generate 5–10 images via `gflow run --config batch.json --output-dir DIR --continue-on-error --resume` to measure total cost.

### 3.5 Cost test plan (5–10 images, NO generation now)

| Step | Action | Expected output | Credit cost |
|------|--------|-----------------|-------------|
| 1 | `gflow credits user` (read-only) | Current balance: 50 | $0 |
| 2 | `gflow image t2i "PROMPT" --aspect 16:9 -n 1 --dry-run --json` | Plan without spend | $0 |
| 3 | Owner reviews dry-run output | Confirm parameters | $0 |
| 4 | `gflow credits user` again | Balance unchanged | $0 |
| 5 | One real `gflow image t2i ...` (owner-approved) | One 16:9 image | Measured |
| 6 | `gflow credits user` | New balance → per-image cost | $0 (read-only) |
| 7 | If cost acceptable: batch 5–10 via `gflow run --config` | Images + cost data | Measured |

**Owner gate:** Steps 5–7 require explicit owner approval before any credits are spent. The zero-cost gate (`lib/zero_cost_gate.py`) blocks unknown-cost calls.

### 3.6 Constraints verified

- `--no-spend` flag is present on all gflow mcp commands
- `GFLOW_MCP_NO_SPEND=1` is set in kilo.jsonc
- MCP Security Proxy (default-deny) hides `gflow_generate_image` and `gflow_generate_video`
- Automated system stops at `READY_FOR_APPROVAL` — never auto-submits

---

## 4. Pilot Script — 3 Topic Recommendations

### Topic 1: "What Would Life Look Like on an Ocean Planet With No Land?" (RECOMMENDED)

**Status:** Existing draft script at `docs/openmontage/pilot/script.md` — 214 sentences, 3,090 words, 20:36 at 150 wpm, 10 sections.

| Criterion | Assessment |
|-----------|------------|
| Scientific interest | High — Europa/Enceladus subsurface oceans, extremophiles, hydrothermal vents, chemosynthesis |
| 20-min narrative potential | Excellent — 10 sections (hook, no-shore ocean, energy without sun, life at ice, predators, deep sources, chance vs law, technology, science vs guesses, conclusion) |
| Visual potential | Very high — deep-sea creatures, ice ceilings, hydrothermal chimneys, alien biomes |
| Scene count | ~214 (one image per sentence) |
| Fact-checking difficulty | Medium-High — requires primary sources (NASA NTRS, Europa Clipper, Enceladus Cassini data); evidence gaps declared in script.md |
| Existing assets | Script drafted, image recipe locked, character defined, narration available |

**Evidence gaps declared:** No predator claim (section 5 is narrative-only), no convergent evolution claim (section 7), no technology/fire claim (section 8), "no shores" is inference from SE-01+SE-04, "near surface" is explicitly framed as invention.

### Topic 2: Aviation & Spaceflight Test History

**Status:** Niche decision at `docs/openmontage/NICHE_DECISION.md` — configured niche, test video CID (1984 NASA/FAA Controlled Impact Demonstration).

| Criterion | Assessment |
|-----------|------------|
| Scientific interest | High — aviation safety, crash testing, NTSB/FAA investigations |
| 20-min narrative potential | Good — crash test history, safety evolution, human factors |
| Visual potential | Medium — archive footage (320×240, below HD bar), diagrams, NTSB reports |
| Scene count | ~160–200 estimated |
| Fact-checking difficulty | Medium — NTSB/FAA primary documents available, NASA NTRS |
| Existing assets | Archive adapters exist (nasa, nara, archive_org, wikimedia, loc, pond5_pd); primary documents as class |

**Note:** Demand signal present for CID topic (100k–138k views in 365d), but all licensable CID clips are 320×240 (below 720p HD bar). Would need HD footage verification for the space/astronomy niche.

### Topic 3: "Could Life Exist on Enceladus?" — Saturn's Ocean Moon

**Status:** Proposed new topic (not yet scripted).

| Criterion | Assessment |
|-----------|------------|
| Scientific interest | Very high — Enceladus has confirmed hydrothermal activity, organic molecules, global salty ocean |
| 20-min narrative potential | Excellent — Cassini mission, plume sampling, ocean chemistry, astrobiology implications |
| Visual potential | Very high — Enceladus plumes, cryovolcanism, ice shell, hydrothermal chimneys |
| Scene count | ~180–220 estimated |
| Fact-checking difficulty | High — Cassini INMS data, plume composition, energy budget calculations |
| Existing assets | None yet (would need full script, character, image generation) |

### Recommendation

**Topic 1: "What Would Life Look Like on an Ocean Planet With No Land?"** is recommended for the first pilot because:

1. **Script already exists** — 214 sentences, 10 sections, evidence gaps declared up front
2. **Image recipe locked** — style, model parameters, anatomy rules, negative prompts all defined
3. **Character defined** — host character anatomy + master reference anchor selected
4. **Narration available** — 10 audio files (18:20) generated with Kokoro `af_heart`
5. **Visual style guide** — complete palette, technique, and composition rules
6. **Publish package drafted** — title options, description, chapters, thumbnail prompt

Topics 2 and 3 are viable for subsequent episodes but require more preparation (Topic 2 needs HD footage verification; Topic 3 needs full scripting).

---

## 5. Production Plan — First Pilot (3–5 min stage)

### 5.1 Scope

**First stage:** 3–5 minutes (approximately 30–45 sentences) of the full 20:36 pilot script, rendered end-to-end through the factory pipeline to prove the complete workflow on a manageable subset before scaling to the full 20+ minutes.

### 5.2 Pipeline stages

| Stage | Module | Output | Status |
|-------|--------|--------|--------|
| 1. Research | `script_analyzer.py` | Meaning blocks, scientific claims | Existing |
| 2. Fact-check | `artifact_ids.py` + evidence ledger | Claim IDs, sources | Existing (gaps declared) |
| 3. Script | `sentence_segmenter.py` | S001…S045 with text, duration | Existing |
| 4. Voice | `audio_production_engine.py` (Kokoro `af_heart`) | Per-sentence WAV | Existing |
| 5. Sentence segmentation | `sentence_segmenter.py` | Sentence IDs + timing estimates | Existing |
| 6. Storyboard | `scene_planner.py` + `visual_director.py` | Scene plans, shot variety | Existing |
| 7. Prompt engineering | `prompt_engineer.py` | Unique visual prompt per sentence | Existing |
| 8. Image generation | `image_generation_engine.py` + `gflow_wrapper.py` | One 16:9 image per sentence (Nano Banana 2.1) | Mock-tested |
| 9. Quality control | `quality_control.py` + `image_uniqueness.py` | Per-scene QC (9 criteria) + aHash duplicates | Existing |
| 10. Audio sync | `audio_alignment.py` | start_ms/end_ms/duration_ms per sentence | Mock-tested |
| 11. Motion design | `motion_engine.py` + `edit_decision_engine.py` | MotionSpec + EditDecision per sentence | Tested |
| 12. Editing | `production_timeline.py` | Unified timeline + validation | Tested |
| 13. Rendering | `render_engine.py` (FFmpeg) | MP4 1920×1080 30fps H.264/AAC | Tested |
| 14. Final QC | `final_qc.py` + `release_gate.py` | QCReport + PASS/WARNING/FAIL | Tested |

### 5.3 Asset structure

```
projects/ocean-planet-pilot/
├── manifest.json              # all assets + status
├── prompts.json               # sentence_id → source prompt + prompt_id
├── generation_jobs.json       # job_id → generation job record
├── assets/                    # S001.png … S045.png (one per sentence)
├── qc_reports/                # S001.json … S045.json
├── generation_logs/
├── audio/
│   ├── narration/             # narration.wav (concatenated)
│   ├── sentence_alignment/    # S001.wav … S045.wav
│   ├── music/                 # (empty — owner sources track)
│   ├── sfx/                   # (empty)
│   └── qc_reports/
└── renders/
    └── final.mp4              # target output
```

### 5.4 Character consistency

- **Master reference:** `master_v3_anchor.png` (candidate #6 from v2)
- **Mechanism:** gflow `--reference-entity` (ref_cap=10) — native multi-reference, no IP-Adapter
- **Appearance:** chibi proportions, short spiky dark gray/black hair, gray t-shirt with wear texture, large round eyes with highlight
- **Placement:** Hero character appears every 4th sentence (not in every image)
- **Anatomy:** registered in `character_consistency_manager.py` (limb count, features, clothing, palette)

### 5.5 Visual style (from VISUAL_STYLE_GUIDE.md)

- **Technique:** thick crisp black outer contours, controlled interior linework, large flat matte color fills, clean two-tone cel shading, restrained palette (4–5 colors), no gradients
- **Palette:** night ink (dark blue-black), deep sea teal, pale bone, electric teal, coral accent
- **Resolution:** 1280×720 source (upscaled to 1920×1080 in render)
- **Model:** Nano Banana 2.1 via gflow-cli (nano2, ref_cap=10, 16:9)
- **Negative prompt:** photorealistic, photo, glossy 3D render, mirror reflections, text, letters, watermark, signature, logo, extra limbs, fused anatomy, duplicated creature, cluttered bottom edge

### 5.6 Audio

- **Voice:** Kokoro-82M `af_heart` (24000 Hz, mono, Apache-2.0 weights)
- **Normalization:** abbreviations, decimals, scientific terms expanded
- **Alignment:** sentence-level via ffmpeg silencedetect on concatenated narration
- **QC:** file existence, decodable, 24000 Hz mono, duration, clipping, silence ratio, loudness
- **Mixing:** narration priority, optional music (ducked), SFX, loudnorm (−14 LUFS, −1 dBTP)

### 5.7 Motion & rendering

- **Motion types:** pan_zoom, detail_crop, parallax (only with depth), static, chapter_card
- **Variety enforced:** no identical consecutive moves (`motion_variety.lint_variation`)
- **Transitions:** cut, dissolve, fade, wipe (default 0.5s)
- **Render:** FFmpeg per-scene clips → concat demuxer → AAC mux, 1920×1080 30fps H.264/AAC
- **Preview:** short fragments (first N sentences) with 8-check QC

### 5.8 Quality gate (Release Gate)

- PASS: all blocking checks pass, no warnings → can_publish=True
- WARNING: all blocking pass, warnings present → can_publish=True (flagged for review)
- FAIL: any blocking check fails → can_publish=False (publish blocked)

### 5.9 Owner decisions required before proceeding

1. **Character reference:** Confirm candidate #6 (`master_v3_anchor.png`) or select from v2 contact sheet
2. **Voice:** Confirm `af_heart` by listening to `docs/openmontage/smoke/kokoro_test.wav`
3. **Nano Banana cost:** Approve cost test (5–10 images) after dry-run review
4. **Music bed:** Source from YouTube Audio Library or approve silence
5. **Fact-checking:** Retrieve primary sources for the ocean planet topic (NASA NTRS, Europa Clipper data)
6. **Pilot scope:** Confirm 3–5 min first stage vs. full 20 min

### 5.10 What happens next (after owner approval)

1. Owner approves character + voice + cost test
2. Run Nano Banana cost test (5–10 images, measure credits)
3. If cost acceptable: generate all images for the pilot subset (30–45 sentences)
4. Synthesize narration (Kokoro `af_heart`)
5. Align audio → timeline
6. Render MP4 (FFmpeg)
7. Run Final QC + Release Gate
8. Owner reviews final MP4 → approve or request changes

---

## 6. Constraints (unchanged)

- No Google Flow generation (no credits spent)
- No auth/browser profile changes
- `--no-spend` and MCP Security Proxy intact
- No production run until owner approves
- No P6 implementation until owner approves

---

## 7. Summary

The OpenMontage factory pipeline (P0–P5) is fully built and tested:

- **P0:** Environment stabilized (ffmpeg, pytest, Kokoro, gflow-cli)
- **P1:** Integration layer (gflow wrapper, sentence segmenter, image uniqueness)
- **P2:** Image generation engine (mock-tested, 19 tests, 10/160/250 sentences)
- **P3:** Audio production (Kokoro TTS, alignment, QC, timeline, 17 tests)
- **P4:** Motion design & rendering (FFmpeg render, audio mixing, timeline, preview, 13 tests)
- **P5:** Final QC (16 checks, release gate, 8 tests)

All 194 tests pass (3 skipped for infrastructure). Real MP4s rendered and verified at 10/50/250 sentences (1920×1080, 30fps, H.264/AAC, full decode clean).

The factory is ready for its first pilot production run pending the 6 owner decisions listed in §5.9.
