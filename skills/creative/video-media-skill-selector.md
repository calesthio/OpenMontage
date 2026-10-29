---
name: video-media-skill-selector
description: >-
  How to choose a Video & Media skill for a content/automation job: planning,
  editing, transcription, audio processing, or delivery. Use when selecting
  which skill (or OpenMontage pipeline) to run for a render, or when scoping a
  media task — confirm container/codec/resolution/frame-rate/channel/caption
  support, editability + timestamp traceability, and upload/retention/consent/
  rights constraints before processing a full project. Reference for the Hermes
  Creative Flywheel's Render stage.
---

# Choosing a Video & Media Skill

Video and media skills may handle **planning, editing, transcription, audio
processing, or delivery**. Select around the **source media** and the **final
platform requirements**, then **test timing, codec, caption, and rights
constraints with a short representative clip** before processing a full project.

## 1. What to evaluate
- **Formats**: confirm support for the required **containers, codecs,
  resolutions, frame rates, channel layouts, and caption formats**.
- **Editability / traceability**: check whether **cuts, transcripts, loudness
  changes, and generated assets remain editable and traceable to source
  timestamps**.
- **Compliance before upload**: review **upload limits, processing location,
  retention, consent, and music or footage rights** before sending source media.

## 2. Continue your search (catalog orientation)
- **Compare video skills** — review workflows for editing, generation,
  transcription, rendering, and delivery across common video formats.
- **Work with music and audio** — explore audio-specific skills when speech
  cleanup, mixing, composition, or podcast production is the main task.
- **All Video & Media skills** — catalog is large (313 skills; ~60 surfaced at
  a time). Browse the full catalog to match a niche capability.

### Representative catalog capabilities (for orientation only)
| Capability | Example skills |
|------------|----------------|
| AI video generation | `ai-video-generation`, `runcomfy` router, `inference.sh` router |
| AI avatar / talking-head | `ai-avatar-video` (OmniHuman, Fabric, PixVerse) |
| Music / audio | `ai-music`, `ai-music-album`, `elevenlabs-music`, `audio-jingle`, `code-to-music` |
| Podcast | `ai-podcast-creation` (Kokoro/DIA/Chatterbox TTS + music + merge) |
| Social content | `ai-social-media-content`, `ai-marketing-videos` |
| Transcription | `audio-transcriber`, `azure-ai-transcription-py`, `baoyu-youtube-transcript` |
| Editing / captions | `embedded-captions`, `converting-files`, `demo-producer` |
| Motion / animation | `animation-motion-design`, `animejs`, `css-animations`, `8-bit-orbit-video-template` |
| Content intelligence | `apify-trend-analysis`, `apify-content-analytics`, `apify-audience-analysis` |

> The catalog is a capability map, not an endorsement. Pick by the source media
> + target platform, then validate with a short clip.

## 3. Flywheel Render-stage application
When the Hermes Creative Flywheel Render stage picks a base pipeline, apply this
discipline:
1. **Match source → pipeline**: explainer → `animated-explainer`; cinematic →
   `cinematic`; short-form repurpose → `clip-factory`; presenter → `talking-head`.
2. **Preflight a 5–10s representative clip**: verify codec/container/aspect,
   that cuts and loudness changes are editable and timestamped, and that
   captions (if required) render.
3. **Rights/consent check**: confirm music + footage rights and upload/retention
   policy before the full generation.
4. Only then run the full `assets → edit → compose` render.
