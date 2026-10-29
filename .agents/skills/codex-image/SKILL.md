---
name: codex-image
description: Prompting and operating guide for the codex_image tool — gpt-image-2 generation billed to a local Codex ChatGPT subscription instead of an API key. Covers prompt shape, the three usable aspect ratios, quota economics, and failure modes.
metadata:
  version: "1.0.0"
  tags: image-generation, codex, gpt-image-2, subscription, no-api-key
---

# Codex Image (gpt-image-2 via ChatGPT subscription)

Layer 3 skill for `codex_image`. Read this before writing any prompt for that tool.

## What makes this provider different

Every other image provider in the registry bills an API key per image. This one drives
the locally-installed `codex` CLI, which already holds the user's ChatGPT OAuth session,
and spends **subscription quota** instead of money. Two consequences shape how you use it:

1. **Each image costs 30–60 seconds**, because a full agent turn runs underneath.
   Never queue a 20-image batch the way you would with FLUX.
2. **Quota is shared with the user's coding**. Image turns drain the rolling 5-hour and
   weekly ChatGPT limits roughly 3–5× faster than a normal turn. Burning the budget on
   b-roll can leave the user unable to use Codex for work. Say so before a batch.

## Prompting

The model behind it is **gpt-image-2** — the same model as `openai_image`. So the
prompting knowledge that applies is instruction-following, not tag-soup:

- **Write a sentence, not keywords.** "a single red paper lantern glowing on a black
  background, studio lighting, shallow depth of field" beats "lantern, red, black bg, 8k".
- **It renders text well.** Put the exact string in quotes: `a poster reading "HẾT HÀNG"
  in bold condensed type`. This is the main reason to pick it over a diffusion model.
- **It follows multi-element layout instructions.** "three objects left to right: a key,
  a lock, an open door" is respected far more reliably than by SDXL-class models.
- **Name what you do NOT want as a positive.** There is no negative prompt parameter.
  Write "empty background, no people" rather than expecting a `negative_prompt`.
- **Diacritics survive.** Vietnamese text in prompts and in rendered image text both work.

## Reference images (style / character lock)

`codex exec -i <file>` attaches images to the prompt; the tool exposes this as
`reference_images: [path, ...]`. The agent hands them to gpt-image-2 as input images,
so palette, lighting, materials and character design carry over instead of drifting.

```python
CodexImage().execute({
    "prompt": "The same lion mascot as in the reference image, but younger: ...",
    "reference_images": ["assets/su-tu-poster.webp"],
    "size": "1536x1024",
})
```

- Write the prompt as a **delta**: "same X as the reference, only change Y". Listing the
  whole scene again invites the model to re-invent it.
- One or two refs is enough. More refs = more tokens per turn on the same quota.
- Verified 2026-09: without a ref the same prompt shifted the palette to warm orange
  sunset; with the poster as ref it kept the beige-gray sky and muted gold of the original.

## Aspect ratios — only three

| `size` | Use for |
|---|---|
| `1024x1024` | square social, thumbnails, icons |
| `1024x1536` | vertical / 9:16-ish shorts |
| `1536x1024` | landscape / 16:9-ish |

There is no arbitrary-dimension mode. For a 1080×1920 short, generate `1024x1536` and
crop or pad with the existing ffmpeg tooling (`auto_reframe`, `video_compose`) —
do not ask the model for a size outside the enum.

## Operating notes

- **Runs are serialized.** Codex keeps global state on disk, so the tool takes a lock in
  `$CODEX_HOME`. A parallel call returns an error rather than corrupting state. Plan
  asset generation sequentially.
- **`n` above 1 is still one turn** but multiplies wall time. Prefer separate calls with
  distinct prompts over `n=4` variations of one prompt, unless you genuinely want variants.
- **Cost reporting.** `estimate_cost()` returns `0.0` because no money moves. That is not
  the same as free — always mention the quota cost in the proposal alongside the $0.00.

## Failure modes and what they mean

| Symptom | Cause | Action |
|---|---|---|
| `Codex CLI not available or not signed in` | binary missing from PATH, or `auth.json` unreadable | `codex login` |
| Status `DEGRADED` | signed in with an API key, not a ChatGPT plan | generation will bill API credit — tell the user before proceeding |
| `Codex produced no image files` | quota exhausted, or the account has no image generation | `codex features list` → `image_generation` must be `true`; free tier has none |
| `Another Codex image run is in progress` | a previous run crashed holding the lock | delete the lock file named in the error |
| Timeout | a turn genuinely stalled | raise `timeout_seconds`; default is 900 |

## When to pick something else

Reach for `flux_image` / `openai_image` / `recraft_image` instead when the user has a key
and the job is a **batch** — those return in seconds and do not touch the subscription.
`codex_image` is the right pick when there is no key at all, or when a small number of
high-instruction-fidelity images (text in image, precise composition) matter more than
throughput.

## Transparent sprites (measured 2026-09-06)

gpt-image-2 honours "PNG with a fully transparent background" only partially: a 3x3 sprite sheet
came back RGBA with 2–60 % of pixels at alpha 0 depending on the subject, sometimes with a drawn
checkerboard or baked shadow instead of real transparency. Ask for it anyway (it saves most of the
cut-out work), then **flatten onto white and run `bg_remove`** for any sheet whose alpha-0 fraction
is below ~30 %. Never `convert("RGB")` a returned PNG directly — transparent pixels turn black and
the cut-out inherits fringes. Sprite-sheet phrasing that works: "3x3 sprite sheet … nine consecutive
animation frames of the SAME <subject> … identical character, size, lighting and camera in every
panel … no text, no numbers".
