---
name: create-short-videos
description: Splits collage or slide images, writes punchy VO from a transcript, generates 9:16 Ken Burns shorts, neural TTS, and motivational BGM mix. Use only when the user explicitly asks to create short videos, Reels, TikTok, YouTube Shorts, or sends images plus a transcript/script for video. Not a fallback when video generation or motion footage is unavailable.
---

# Create short videos

User supplies **images + transcript** and explicitly asks for a short. Produce 9:16 shorts (1080×1920) with voice and motivate BGM.

In OpenMontage this is an opt-in path. Do not use it to replace a failed video-generation or footage job with a Ken Burns slideshow. If the user did not ask for an image short, stay on the pipeline they chose.

## Inputs

| Input | Accept |
|-------|--------|
| Images | One collage/grid, several slide PNGs, or already-9:16 frames |
| Transcript | Numbered lines, JSON, or one block to split per slide |
| Optional | Voice (`male`/`female`/edge-tts name), language, slug, output dir, skip GenerateImage |

Defaults: Vietnamese male `vi-VN-NamMinhNeural`, Mixkit *Driving Ambition* BGM, duck under VO.

## Output layout

```
docs/shorts/<slug>/          # or ./shorts/<slug> if no docs/
  slides/                    # cropped tiles (faithful split)
  portraits-9x16/            # 9:16 frames used for video
  voice/                     # .txt .mp3 scripts.json + bgm/
  videos/                    # 01-…N.mp4 + full-short.mp4
```

## Workflow

Copy and track:

```
- [ ] 1. Collect images, transcript, slug
- [ ] 2. Split / normalize slides
- [ ] 3. Make 9:16 portraits (GenerateImage if tiles are small)
- [ ] 4. Write voice/scripts.json (punchy, ~6–9s per clip)
- [ ] 5. Run scripts/build_shorts.py tts encode mux
- [ ] 6. Verify audio (volumedetect) and tell user to reload files
```

### 1. Collect

- Slug: kebab-case from title / first headline.
- Output: `docs/shorts/<slug>/` in the current repo, else `./shorts/<slug>/`.
- Transcript → one spoken line per slide. If one block, split by slide meaning. If missing, write VO from visible slide text.

**VO rules:** 1–2 sentences, ~12–18 words, spoken language matching the user. Keep a condensed `full` script (~20–28s) for the montage.

`voice/scripts.json`:

```json
{
  "clips": [["01-slug", "Spoken sentence."], ["02-slug", "…"]],
  "full": "Condensed narration for the montage."
}
```

### 2. Split

Run from the OpenMontage repo root (skill dir = `.agents/skills/create-short-videos/`):

```bash
python3 .agents/skills/create-short-videos/scripts/build_shorts.py split \
  --out <out> --images <img1> [img2…]
```

- One image that is a grid → detect bright gutters, crop N tiles into `slides/`.
- Already N images → copy into `slides/` as `01-…`.
- User-stated grid (`3x4`) overrides auto-detect.

### 3. 9:16 portraits

If **any** slide width **< 600px** (typical collage crop):

1. `GenerateImage` aspect `9:16` with `reference_image_paths` = that slide.
2. Prompt: same layout, typography, and scene; sharp 4K text; no watermark; match language on the slide.
3. Copy results into `<out>/portraits-9x16/01-….png`.

Else:

```bash
python3 .agents/skills/create-short-videos/scripts/build_shorts.py portraits --out <out>
```

### 4–5. TTS + Ken Burns + mux

```bash
python3 .agents/skills/create-short-videos/scripts/build_shorts.py build \
  --out <out> \
  --voice vi-VN-NamMinhNeural
```

`build` does: TTS (retry on `NoAudioReceived`) → Ken Burns clips → mix VO + BGM (sidechain duck, fade).

| Flag | Default |
|------|---------|
| `--voice` | `vi-VN-NamMinhNeural` (female: `vi-VN-HoaiMyNeural`; English: `en-US-AndrewNeural`) |
| `--bgm` | downloads Mixkit *Driving Ambition* into `voice/bgm/` if missing |
| `--no-bgm` | VO only |

Ensure `ffmpeg` and `edge-tts` (`pip3 install --user edge-tts`). Pillow for split/portraits.

### 6. Verify

- Each `videos/0N-*.mp4`: 1080×1920, AAC audio, duration ≈ VO + 0.7s.
- `videos/full-short.mp4`: all slides, condensed VO + BGM, ~25–40s.
- `ffmpeg -i file -af volumedetect -f null -` → max_volume greater than about −8 dB (not silent).

Tell the user the folder path and to **reload** open videos.

## Voice / BGM notes

- Never burn female+male; rebuild audio from `portraits-9x16` + new mp3 (script maps **video only** from existing mp4 if re-muxing).
- BGM stays under VO (`volume≈0.15`, duck when speaking).
- Mixkit License: keep `voice/bgm/SOURCE.txt`.

- For input/output examples, see [examples.md](examples.md).

## Do not

- Do not invent extra slides.
- Do not skip confirm-style punchy VO in favor of reading the whole poster.
- Do not commit large MP4s unless the user asks (often 7–10MB each).
