# Pilot Audio Results — Kokoro TTS (af_heart)

**Voice:** af_heart (fixed, per task requirement)  
**Sample rate:** 24000 Hz  
**Engine:** Kokoro 0.2.2, venv `/tmp/kilo/z1_venv`  
**Generated:** 2026-10-27

## Results: 10/10 sections

| Section | File | Title | Words | Duration (s) | Expected (s) | Diff (s) | Status |
|---------|------|-------|-------|-------------|-------------|----------|--------|
| §1 | `audio/section_01.wav` | Hook and the question | 229 | 83.0 | 91 | −8.0 | OK |
| §2 | `audio/section_02.wav` | The world: an ocean with no shores | 384 | 129.4 | 153 | −23.6 | OK |
| §3 | `audio/section_03.wav` | Energy: no sunlight, two answers | 377 | 148.6 | 150 | −1.4 | OK |
| §4 | `audio/section_04.wav` | Life near the ice: mats and filter-feeders | 381 | 135.5 | 155 | −19.5 | OK |
| §5 | `audio/section_05.wav` | Predators, and the logic of an arms race | 383 | 132.9 | 149 | −16.1 | OK |
| §6 | `audio/section_06.wav` | The deep, the vents, and the animals that stay | 390 | 137.8 | 152 | −14.2 | OK |
| §7 | `audio/section_07.wav` | Chance and law: would this world repeat? | 302 | 99.9 | 118 | −18.1 | OK |
| §8 | `audio/section_08.wav` | What blocks technology without land or fire | 332 | 101.4 | 120 | −18.6 | OK |
| §9 | `audio/section_09.wav` | What is science, and what is a guess | 268 | 83.6 | 87 | −3.4 | OK |
| §10 | `audio/section_10.wav` | Closing and a question for you | 208 | 47.8 | 57 | −9.2 | OK |

**Total actual:** 1099.9s (18:20)  
**Total expected:** 1232s (20:32)  
**Overall diff:** −132.1s (−10.7%)

## Duration divergence notes

All sections are shorter than the expected runtime from `script.md` stats (which are at 150 wpm spoken pace). Kokoro TTS at speed=1 reads faster than a human narrator, and the TTS output doesn't include natural pauses between sentences that a human speaker would have. This is expected for TTS and can be adjusted in post-production (adding silence between sections, or reducing playback speed).

## Generation notes

- Sections 3–10 were generated sentence-by-sentence in separate Kokoro processes (to avoid memory accumulation that caused termination when generating all sentences in one process).
- Section 1–2 were generated in a single process.
- No text preprocessing was applied beyond sentence splitting on `.!?` boundaries.

## Local paths

All audio: `tools/kaggle_bridge/jobs/pilot-render/audio/section_01.wav` … `section_10.wav`  
Raw results JSON: generated inline (not saved separately)
