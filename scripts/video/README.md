# scripts/video — montage_lib

Recipe library for the Thiền Đạo video pipeline, **Stage 6–7** (Edit & Mix + Compose).
Full pipeline SOP: [`docs/video-production-pipeline.md`](../../docs/video-production-pipeline.md).

These are the proven FFmpeg recipes extracted from `projects/bon-mua-cua-hoi-tho/build_meditation_video.py`,
generalized into pure functions. **Each video keeps its own thin driver** that imports the lib and
describes its bespoke timeline — there is intentionally no monolithic config schema (formats differ
too much; see plan `260630-0044`).

## Surface (≤6 recipes + 1 helper)

| Function | Stage | Purpose |
|---|---|---|
| `slow_loop_scene(scene, dur, out)` | 7 | stream-loop + slow a clip to cover a duration |
| `make_card(bg, text_big, dur, out, text_small=...)` | 7 | intro/outro/title card, drawtext `textfile=` (UTF-8) |
| `concat_segments(paths, out, reencode=True)` | 7 | join segments (re-encode-safe by default) |
| `narration_offsets_from_durations(cues)` | 6 | **helper** — compute absolute offsets from clip durations + silence gaps |
| `build_narration_track(cues, total, out)` | 6 | delay+sum narration cues (batched amix, scales to 100s of cues) |
| `duck_mux(video_silent, narration, music, out)` | 6 | mux + sidechain-duck music + loudnorm I=-16 |
| `remux_audio(video_silent, audio, out)` | 7 | swap audio without re-encoding video (guards against double-music) |

## Guarantees

- **Pure functions** — no globals, no env reads. Return the output path, raise on failure.
- **No shell injection** — subprocess arg lists only; all on-screen text via drawtext `textfile=`.
- **Idempotent** — every renderer skips when its output already exists (crash-resumable).
- **Fail-fast** — missing assets raise; narration overflow warns; `remux_audio` refuses a non-silent master.

## Minimal thin driver

```python
# projects/<slug>/build.py
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "video"))
import montage_lib as m

ROOT = "projects/my-video"
A = f"{ROOT}/assets"; R = f"{ROOT}/renders"; os.makedirs(R, exist_ok=True)

# 1. Stage 7 — build visual segments
intro = m.make_card(f"{A}/video/scene.mp4", "TIÊU ĐỀ VIDEO", 5.0, f"{R}/seg_intro.mp4",
                    text_small="Phụ đề mở đầu")
main  = m.slow_loop_scene(f"{A}/video/scene.mp4", 120.0, f"{R}/seg_main.mp4")
outro = m.make_card(f"{A}/video/scene.mp4", "CẢM ƠN QUÝ VỊ ĐÃ XEM", 6.0, f"{R}/seg_outro.mp4",
                    text_small="Đăng ký kênh & bấm Thích để ủng hộ")
silent = m.concat_segments([intro, main, outro], f"{R}/final-clean.mp4")  # silent master

# 2. Stage 6 — narration + ducked music
total = m.probe_duration(silent)
cues  = m.narration_offsets_from_durations([
    {"path": f"{A}/audio/intro.mp3", "gap": "paragraph", "offset": 1.5},
    {"path": f"{A}/audio/s1.mp3", "gap": "sentence"},
    {"path": f"{A}/audio/s2.mp3", "gap": "line"},
])
narr = m.build_narration_track(cues, total, f"{A}/audio/narration.m4a", reverb=True)
final = m.duck_mux(silent, narr, f"{A}/music/bed.mp3", f"{R}/final.mp4", total=total)
print("DONE ->", final)

# Later: swap copyright-claimed music without re-rendering video
# m.remux_audio(f"{R}/final-clean.mp4", f"{A}/music/new_bed_mix.m4a", f"{R}/final-v2.mp4")
```

## Notes

- `size` defaults to `1920x1080`; pass `size="1080x1920"` for Shorts/Reels.
- Vietnamese diacritics: text always via `textfile=`; set `PYTHONUTF8=1` when running on Windows.
- Font defaults to Windows `arialbd.ttf`; pass `font=...` on other machines (`make_card` checks it exists).
- TTS is the driver's job (ElevenLabs re-fetch voice_id, or google_tts, or pre-rendered files) — the lib only builds/mixes.

## Validation

Recipe correctness is exercised on real assets (no asset-gen / TTS) by:
- `_validate_bonmua.py` — reduced bon-mua rebuild through every recipe + remux guard proof.
- `_validate_longform.py` — sleep-format build path: 240-cue batch-amix scale proof + long concat/duck path.
- `_qa.py` — Stage-8 QA gates: ffprobe (codec/res/duration), silencedetect (voice timeline), and a **hard copyright gate** (`format_tags` must carry no Content-ID/CC-BY markers).

Run with `PYTHONUTF8=1 python scripts/video/_validate_bonmua.py [OUT_DIR]` (outputs go to a temp dir, never `projects/.../renders/`).
