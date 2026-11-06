# PILOT CREATIVE REVIEW — OpenMontage First Pilot

**Video:** `projects/pilot/first_video/final.mp4`
**Review date:** 2026-11-05
**Reviewer:** Kilo (Reflection Beam 1.0) — automated + technical review (visual assessment via contact sheets and metrics; direct vision unavailable, contact sheets saved to `/tmp/review/` for human review).

## 1. Automated measurements

- Duration: 174.37 s
- Resolution: 1920×1080 @ 30 fps
- Codec: H.264 + AAC
- Scene changes (threshold 0.3): 40 (out of 41 scenes) — good visual variety
- Freeze segments (freezedetect n=0.003, d=0.5): 12 segments, longest 5.33 s
- Black frames: 0
- Silence ratio: 0.092 (16.12 s / 174.37 s), 41 silent segments, longest 0.55 s
- Loudness: -15.1 LUFS (target -14 ±2) — PASS
- True peak: -3.68 dBTP

## 2. First 30 seconds (separate review)

Contact sheet: `/tmp/review/first30_sheet.jpg` (1 frame/s, 30 frames).

- 0:00–0:04.7: freeze (static establishing shot with no motion). Hook visual is present but static.
- S001 (question) → S002 (Europa) → S003 (ice crust) → S004 (water volume) → S005 (tidal heating) → S006 (Enceladus) within first ~10 s. Pacing is fast; hook lands within first 5–10 s.
- No logo/title card; cold open works.
- Audio: narration starts immediately, intelligible.

Weakness: first 4.7 s are frozen; meaningful motion rule (2.5 s) violated at the very start.

## 3. Visual variety and composition

- 40 distinct scene changes across 41 scenes — strong variety, no slideshow monotony at scene level.
- Composition types present: extreme wide establishing, cross-section, macro, organism, infographic (implied by prompts).
- Motion types: static (15), detail_crop (13), pan_zoom (10), parallax (3). 15 static scenes is a significant weakness — these are frozen frames for their entire duration.
- Zoom range is modest (1.0–1.13), making motion barely perceptible; freezedetect flags many segments.
- Images are 1376×768 upscaled to 1920×1080 via cover (no distortion, but some softness expected).

## 4. Stickman Rig-1 presence

**The Stickman Rig-1 is NOT present in the rendered MP4.** Rig fields (pose, expression, view, motion events) are carried as metadata in edit decisions and timeline, but the FFmpeg render path only renders background images + camera motion. The programmatic SVG rig was never composited. This is the single largest gap vs. the master plan and the intended visual identity. The stickman must be composited via Remotion/HyperFrames in a follow-up pass.

## 5. Audio

- Voice: Kokoro-82M `af_heart`, natural, intelligible.
- Loudness: -15.1 LUFS (within ±2 of -14 target).
- Silence ratio: 0.092 (acceptable after trimming).
- No clipping, no truncated words.
- Sync: audio duration matches video (174.37 s) within 0.01 s.
- Weakness: no music or SFX bed — narration only. The master plan calls for music supporting emotional arc and point SFX. This reduces emotional impact.

## 6. Scientific quality

- Source ledger exists (`docs/openmontage/evidence/S1_SPECULATIVE_CLAIM_LEDGER.md`), claims tagged SE-XX.
- Facts (Europa global ocean, ice thickness, water volume, tidal heating, Enceladus) separated from narrative speculation.
- Narrative-only sections (predators, chance vs law, technology) are explicitly tagged `[NARRATIVE]` with no fabricated facts.
- Speculative evolution (grazers, drifters) framed as invention, not discovery.
- Weakness: this pilot slice ends mid-arc (S041 open question) with no resolution; full 20-min film has resolution but pilot doesn't. Acceptable for a 3-min slice but should be noted.

## 7. Storytelling and hook

- Cold open: question + establishing shot, no logo card. Good.
- Hook lands within first 5–10 s.
- Arc: question → rules of the world → Europa/Enceladus → (slice ends). Coherent but incomplete by design.
- Pacing: ~4.2 s/sentence average, natural.
- Weakness: ending is an open question with no payoff; the slice was cut for length.

## 8. Assessment vs. large educational channels

- The visual style (Nano Banana 2.1 + consistent ink/teal/pale-bone palette) is distinctive but not yet at Kurzgesagt/TED-Ed polish level: no character animation in final render, no music, no SFX, no infographic overlays.
- The technical pipeline (unique image per sentence, alignment, QC) is production-grade.
- The emotional arc is present in script but not fully realized in render due to missing audio bed and character layer.

## 9. Scores

| Criterion | Score | Notes |
|---|---|---|
| Hook | 7/10 | Strong question + cold open; weakened by 4.7 s frozen start |
| Storytelling | 7/10 | Coherent slice, clear arc; ends without resolution (by design) |
| Visual Quality | 7/10 | 40 scene changes, consistent palette; upscaled 1376→1080, no character layer |
| Animation | 4/10 | 15 static scenes, subtle zoom, no stickman composited; meaningful-motion rule violated |
| Audio | 8/10 | Natural voice, good sync, normalized loudness; no music/SFX bed |
| Scientific Quality | 8/10 | Source ledger, fact/speculation separation, tagged claims |
| Overall Experience | 6/10 | Technically solid pipeline; creative impact limited by animation and missing character/audio bed |

## 10. Prioritized improvements

### P1 — Critical (must fix before next pilot)

1. **Composite Stickman Rig-1** into the render. Build a Remotion pass that overlays the SVG rig (poses, expressions, gestures) on the background images per edit decision. Without this, the core visual identity is absent.
2. **Replace 15 static scenes** with meaningful motion: use detail_crop, pan_zoom, or parallax with larger amplitude (zoom 1.0→1.25+, pan across the image). Eliminate freezedetect-flagged segments.
3. **Add music bed** (royalty-free, ducked under narration) and point SFX (transitions, reveals). Use existing AudioMixing with a cleared music track.

### P2 — High

4. **Regenerate or enhance S001 establishing shot** — it freezes for 4.7 s; add a slow push-in.
5. **Add infographic overlays** (arrows, labels, scale bars) as vector layers on cutaway/infographic scenes.
6. **Improve image resolution** — request 1920×1080 from gflow if the model supports it, or upscale with a better method (currently 1376×768 cover-upscale).

### P3 — Medium

7. **Complete the narrative arc** — render a longer slice (S001–S060 or full) so the pilot has a resolution.
8. **Add title card / end card** (non-intrusive, after climax).
9. **Contact sheet + owner review** — generate a full-frame contact sheet for human visual QA.
10. **Tune silence threshold** or reduce inter-sentence pauses to lower silence ratio further (currently 0.092, just under 0.1).

### P4 — Low

11. **Add thumbnail concept and title variants** (no publication).
12. **Measure and record** per-scene render time and cost per minute for the economics report.

## 11. Conclusion

The pilot demonstrates a production-grade pipeline: unique image per sentence, precise audio alignment, QC PASS, and a coherent 3-min slice. However, the creative impact is significantly limited by the absence of the stickman character in the rendered frames, 15 static scenes, and no music/SFX bed. The next iteration must composite the rig and add meaningful motion and audio design before this can be considered a showcase piece.

**Recommendation:** Do not publish. Proceed with P1 improvements (stickman compositing, motion, audio bed) in the next iteration.
EOF
echo done