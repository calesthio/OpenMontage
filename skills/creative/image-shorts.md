# Image Shorts

Use this only when the user explicitly asks for a vertical short made from images plus a transcript: Reels, TikTok, YouTube Shorts, or “cắt thành short”.

Do not use it as a fallback when video generation, stock footage, or a locked render runtime fails. OpenMontage still forbids quietly turning a motion job into a Ken Burns teaser.

## Read next

Read `.agents/skills/create-short-videos/SKILL.md` and follow it. The builder is:

```bash
python3 .agents/skills/create-short-videos/scripts/build_shorts.py
```

Commands: `split`, `portraits`, `build`. Output goes to `docs/shorts/<slug>/` in the current project, or `./shorts/<slug>/` when there is no `docs/` directory.

## Fit with other skills

- Platform safe zones, duration, and loudness targets stay in `creative/short-form.md`.
- Ducking and mix levels stay in `creative/sound-design.md`. This builder already ducks BGM under the voice.
- Narration uses local `edge-tts` (default `vi-VN-NamMinhNeural`). If the user asks for a provider already in the registry, prefer that provider and keep this skill’s picture and edit steps.
