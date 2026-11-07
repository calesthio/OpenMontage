---
name: audio-edit
source: https://github.com/agamm/video-agent
pinned_commit: cc00d2815869cbf2d708426a5082612f0c3b4dbf
license: MIT (Agam More, 2026) — upstream LICENSE read verbatim
adaptation: Linux port — plain ffmpeg recipes; `libx264` + `aac` output (not h264_videotoolbox); loudnorm via ffmpeg `loudnorm` filter; no `uv run video-agent` CLI.
---

# Audio editing (Linux adaptation of agamm/video-agent audio-edit)

Clean up or mix a video's audio track — normalize loudness, reduce background noise/hiss, or add
background music (optionally ducked under speech). Use whenever the user wants to fix
quiet/loud/inconsistent audio, remove hiss/hum, or lay music under a talking-head/voiceover.
For removing um/uh filler words use filler-removal logic separately; for replacing audio
entirely use plain ffmpeg map.

These are plain ffmpeg one-liners — no CLI command wraps them. Every recipe stream-copies the
video (`-c:v copy`, fast + lossless) and re-encodes only the audio to `aac`.

## Normalize loudness

```
ffmpeg -y -i in.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:v copy -c:a aac out.mp4
```
-16 LUFS / -1.5 dBTP is a good general/web target. Single pass fine for most clips. For precise
targets / batch consistency, do two-pass: run once with `loudnorm=...:print_format=json`, read
the measured values, then pass them back as `measured_I`/`measured_TP`/`measured_LRA`/`measured_thresh`
on a second run (same approach validated in D1 step 5).

## Even out inconsistent levels (loud speaker vs quiet audience)

Compress to tighten dynamic range, then normalize:

```
ffmpeg -y -i in.mp4 -af \
  "acompressor=threshold=-21dB:ratio=3:attack=15:release=250:makeup=3,\
   equalizer=f=2800:t=q:w=2:g=2,\
   loudnorm=I=-14:TP=-1.5:LRA=9" \
  -c:v copy -c:a aac out.mp4
```

- `acompressor` pulls loud parts down; `makeup` lifts quiet parts up → consistent loudness.
- Gentle presence bump (~2.5–3.5 kHz) adds intelligibility.
- `loudnorm` with tight `LRA` (7–9) finishes leveling; check output isn't pumping.
- Diagnose first with `astats` (RMS level / Peak level).

## Denoise (hiss / hum)

```
ffmpeg -y -i in.mp4 -af afftdn=nr=12 -c:v copy -c:a aac out.mp4
```
`nr` = noise reduction dB (10–20 typical; start at 12). Combine with normalize:
`-af "afftdn=nr=12,loudnorm=I=-16:TP=-1.5:LRA=11"`.

## Add background music

**If the edit is an EDL, put the bed in `audio.music`** (`asset_id`, `volume`, `ducking`,
`fade_in_seconds`, `fade_out_seconds`) — mixed in the same render pass, looped to cover, ducked
under speech. No second re-encode.

Plain mix (fixed level under existing audio):
```
ffmpeg -y -i in.mp4 -i bg.mp3 -filter_complex \
  "[1:a]volume=-18dB[bg];[0:a][bg]amix=inputs=2:duration=first[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -shortest out.mp4
```

Music ducked under speech:
```
ffmpeg -y -i in.mp4 -i bg.mp3 -filter_complex \
  "[1:a]volume=-18dB[bg];\
   [bg][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[bgd];\
   [0:a][bgd]amix=inputs=2:duration=first[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -shortest out.mp4
```
Sidechain compresses music using speech as trigger: louder speech → more music attenuation.
Tune `ratio` (duck depth), `attack` (duck speed, ms), `release` (return speed, ms).

## Gotchas

- Always `-shortest` when adding music (a longer music track desyncs everything downstream).
- `amix` can lower overall level — append `,loudnorm=I=-16:TP=-1.5:LRA=11` after the amix
  output, or raise speech with `volume` before mixing.
- Re-encode audio to `aac` (`-c:a aac`); don't `-c:a copy` after a filter.
- `duration=first` ties output length to the first `amix` input — keep speech first.

## Linux adaptations vs upstream

- `h264_videotoolbox` → `libx264` (our ffmpeg build).
- No `uv run video-agent` CLI; these are ffmpeg recipes to invoke via our pipeline/tools.
- No built-in word-level "karaoke" captions; approximate via transcript `--words` grouping.

## Network / env / writes (observed from upstream SKILL.md)

- Network calls: none (plain ffmpeg).
- Env vars: none required.
- Writes: output mp4 (re-encoded audio); intermediate wav/mixes live under
  `projects/<run>/assets/audio/` per the workspace convention.
