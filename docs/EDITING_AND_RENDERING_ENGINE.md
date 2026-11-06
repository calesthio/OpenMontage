# OpenMontage — Editing & Rendering Engine (P4)

**Components:** `lib/render_engine.py`, `lib/audio_mixing.py`, `lib/production_timeline.py`, `lib/preview_system.py`  
**Status:** P4 complete — designed, implemented, and tested  
**Date:** 2026-11-03  
**Render path:** FFmpeg 7.1.5 (confirmed working at `/usr/bin/ffmpeg`)  
**Cost:** $0 (FFmpeg only, no generation, no credits)

---

## 1. Render Engine (`lib/render_engine.py`)

### Render pipeline

Each scene is rendered as an individual clip, then clips are concatenated via the FFmpeg concat demuxer, and the master audio track is muxed in:

```
scene image → per-scene clip (loop + scale/crop motion) → concat demuxer → + audio → final MP4
```

**Why per-scene clips:** A single giant `filter_complex` with 50+ inputs (each using `scale:eval=frame`) hangs on this FFmpeg build. Per-scene clips + concat demuxer is robust and scales to 250+ sentences.

### Motion implementation (FFmpeg filter)

`zoompan` returns "Invalid argument" in this FFmpeg 7.1.5 build regardless of expression. Motion is implemented with:

```
loop=loop=-1:size=1:start=0, framerate=fps=30, trim=duration=X,
scale=w='iw*(Z)':h='ih*(Z)':eval=frame,
crop=w=1920:h=1080:x='(iw-1920)/2':y='(ih-1080)/2'
```

Where `Z` is a time-varying zoom expression `start_scale + (end_scale-start_scale)*min(t/duration,1)`. This:
- Preserves aspect ratio (scale then center-crop — **never stretches**)
- Produces smooth zoom in/out
- Works reliably in this FFmpeg build

### Output format (target profile)

| Attribute | Value |
|---|---|
| Container | MP4 |
| Resolution | 1920×1080 (16:9) |
| Frame rate | 30 FPS |
| Video codec | H.264 (libx264, CRF 23) |
| Audio codec | AAC (192 kbps, 48 kHz, stereo) |
| Pixel format | yuv420p |
| Fast start | Enabled (`-movflags +faststart`) |

### Quality checks (automatic)

| Check | Tool | Fail condition |
|---|---|---|
| File exists / non-empty | filesystem | Empty → FAILED |
| ffprobe full decode | ffprobe | Error → FAILED |
| Video codec | ffprobe | ≠ h264 → warning |
| Audio codec | ffprobe | ≠ aac → warning |
| Resolution | ffprobe | ≠ 1920×1080 → warning |
| Black frames | ffmpeg blackdetect | >0 → warning |
| Frozen segments | ffmpeg freezedetect | >0 → warning |

---

## 2. Audio Mixing (`lib/audio_mixing.py`)

Mix narration + optional music + SFX into a master AAC track:

| Layer | Treatment |
|---|---|
| Narration | Priority, unity volume, always present |
| Background music | Volume-ducked under narration via `sidechaincompress` |
| SFX | Mixed at configured volume, no ducking |

Master pass: `afade` in/out + `loudnorm` to hit YouTube-safe loudness (−14 LUFS integrated, −1 dBTP true peak).

**Rights:** Music/SFX are optional and only used when the caller supplies an asset with confirmed commercial rights. Missing files are silently skipped — narration always renders alone. Narration is never modified (new master file written).

---

## 3. Production Timeline (`lib/production_timeline.py`)

Unified timeline merging P3 audio timings with P4 edit decisions:

| Entry field | Source |
|---|---|
| `sentence_id` | P3 / P2 |
| `start_ms` / `end_ms` / `duration_ms` | P3 audio alignment (authoritative) |
| `image_asset_id` / `image_path` | P4 edit decision |
| `audio_asset_id` / `audio_path` | P3 audio |
| `motion_type` / `camera_parameters` | P4 motion engine |
| `transition` / `visual_effects` | P4 edit decision |
| `pause_after` | Explicit inter-sentence pause element |

**Validation:**
- Every `sentence_id` present exactly once
- Unique `image_asset_id` and `audio_asset_id` (one image = one sentence = one audio)
- Chronological, gap-free, non-overlapping
- Inter-sentence gaps become explicit `TimelinePause` elements (not accidental gaps)

`ready_for_p4()` returns True when all entries have audio QC-passed.

---

## 4. Preview System (`lib/preview_system.py`)

Builds short preview fragments (first N sentences or selected IDs) before full render, then QC:

| Check | Criterion |
|---|---|
| Render success | Exit code 0 |
| Composition | 1920×1080, 16:9 |
| Motion speed | Scale within [0.8, 2.0] |
| Transitions | Valid type (cut/dissolve/fade/wipe) |
| Sync | Render duration ≈ expected (±1s) |
| Readability | ≥720p height (scientific diagrams legible) |
| Visual variety | Not all identical motion type |
| No black/frozen | ffmpeg blackdetect/freezedetect clean |

Previews are capped at `max_preview_seconds` (default 30s) for fast iteration.

---

## 5. Remotion

`remotion-composer/` exists (Node v26, `@remotion/cli ^4.0.484`, `Explainer.tsx` etc.) and is available as an alternative composition engine. **Not wired** because `Explainer.tsx` is a specific animated explainer, not a generic edit-decision renderer. Authoring that bridge is out of scope for P4. FFmpeg is the verified render path.

Per `AGENT_GUIDE.md` hard rule: when both Remotion and HyperFrames are available, both are presented before locking `render_runtime`. FFmpeg was selected as the default for the stills-led documentary pipeline.

---

## 6. Files created (P4 editing/rendering)

| File | Purpose |
|---|---|
| `lib/render_engine.py` | FFmpeg render engine (per-scene clips + concat demuxer + audio mux + QC) |
| `lib/audio_mixing.py` | Narration/music/SFX mixing with ducking + loudnorm |
| `lib/production_timeline.py` | Unified timeline + validation |
| `lib/preview_system.py` | Short preview fragments + QC |
| `tests/lib/test_p4_engine.py` | Edit decision + timeline tests |
| `tests/lib/test_p4_render.py` | Real MP4 render tests (10/50/250 sentences) |

**No existing modules were rewritten.**

---

## 7. Test results

| Test | Sentences | Status | Result |
|---|---|---|---|
| test_render_10_sentences_mp4 | 10 | PASS | Real MP4, h264/aac, 1920×1080, 30fps, sync ±1s |
| test_render_50_sentences_mp4 | 50 | PASS | Real MP4, full QC |
| test_render_250_sentences_mp4 | 250 | PASS | Real MP4, full QC (~200s render) |
| test_render_various_durations | 20 | PASS | Mixed durations 150–1200ms |
| test_render_fast_and_slow_motion | 8 | PASS | Motion variety ≥2 types |
| test_render_long_pauses | 6 | PASS | Explicit pause elements |
| test_render_missing_images | 4 | PASS | Graceful failure on missing image |
| test_render_missing_narration | 5 | PASS | Silent-audio fallback renders |
| test_preview_system_short_fragment | 10→3 | PASS | Preview QC passes |
| test_sentence_timeline_integration | 7 | PASS | P3→P4 timeline merge + render |

All edit decision / timeline tests pass (uniqueness, chronology, gaps/overlaps, artifact shape).
