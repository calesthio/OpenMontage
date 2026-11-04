---
name: seedance-2-5
description: |
  Generate 4-30 second cinematic video with ByteDance Seedance 2.5 through fal.ai, Volcengine Ark, Runway, or ComfyUI Partner Nodes. Use for long single generations, synchronized audio, and large multimodal reference sets (up to 30 images, 10 videos, and 10 audio clips). Also covers the 2.5 prompt contract: section order, multi-shot "Hard cut" breakdown, named locks for continuity across cuts, the asset and character-sheet method, voice conditioning, and iteration discipline.
---

# Seedance 2.5

Seedance 2.5 extends the Seedance 2 family to 4–30 second 480p/720p clips and
larger multimodal reference sets. It is hosted; there are no local model
weights in OpenMontage.

## Choose a supported route

| Route | Tool call | Notes |
|-------|-----------|-------|
| fal.ai | `seedance_video`, `model_version: "2.5"` | T2V, I2V, and reference-to-video |
| Volcengine Ark | `seedance_ark`, `model: "2.5"` | First-party model ID `doubao-seedance-2-5-260628`; custom token price required for cost estimates |
| Runway | `runway_video`, `model: "seedance2_5"` | T2V, I2V, V2V; 480p/720p |
| ComfyUI Partner Node | `comfyui_video`, `model_family: "seedance_2.5"` | Hosted and paid despite running in a ComfyUI graph |

Do not invent a Replicate, HeyGen, or Higgsfield identifier when their current
public API schema does not list Seedance 2.5.

> **Resolution note.** The supported routes above expose 480p and 720p. The model
> generates 1080p natively on the vendor's own web platform, which is not an
> OpenMontage route. If a vendor blog cites 1080p or 4K, check which surface it means
> before promising it in a pipeline.

## Reference limits

- Up to 30 reference images.
- Up to 10 reference videos.
- Up to 10 reference audio clips.
- Keep combined reference video/audio duration within the provider's documented
  ceiling; Runway caps it at 30 seconds.
- For Runway video-to-video, the source video consumes one video slot.

Reference inputs are provider-specific. fal.ai uses `image_urls`, `video_urls`,
and `audio_urls` internally. Runway uses `references`, `referenceVideos`, and
`referenceAudio`. Ark uses typed content entries with roles. Always call the
OpenMontage tool instead of constructing a provider payload manually.

**50 assets is a ceiling to use deliberately, not to max out.** A cluttered reference
set with competing faces, props, and locations produces a *less* coherent result than a
smaller, chosen one. Rule: one reference per element that must stay consistent — a face,
a product, a location, a style.

---

## Prompting

Lead with the shot structure, then subject, action, camera, lighting, and audio.
For multi-shot work, give each beat an explicit time range and use quoted text
for dialogue. Reference each supplied asset by a stable role in the prompt.
Thirty seconds is a ceiling, not a target: use a shorter generation when the
scene has only one meaningful action.

### Section order

One continuous block of text, broken into labeled sections. Skipping a section does not
degrade the output generally — it breaks it in a specific, predictable way.

```
GLOBAL STYLE
  Genre, color grade, film stock or digital look, aspect ratio, shutter behavior,
  and anything that must not appear. Everything below must match this.

SCENE
  A one-line logline: what happens, where, in what mood.

CHARACTERS
  Face, hair, build, wardrobe. If a reference covers this, just name which
  reference is which character.

LOCATION
  The space and its props, separate from the people in it. A vague location is
  the single most common reason a multi-shot sequence drifts between cuts.

FIRST FRAME AND BLOCKING
  Exact starting positions: who is where, facing which direction, as the clip
  opens. Something fixed before any motion starts.

Shot 1: [shot type] [action in one or two sentences]. Hard cut.
Shot 2: [...]. Hard cut.
Shot 3: [...].
  Pacing is built here. State camera distance and framing per shot: vague
  transitions are the most common cause of a sequence collapsing.

OPTICS / CAMERA
  Focal length, camera height, handheld or dolly or crane, per shot.

PHYSICS
  Fabric, smoke, hair, liquid. Anything that would look wrong moving like a solid.

LIGHTING
  Where the light is motivated from, its direction, how it falls on faces.

AUDIO
  Ambience, specific effects, and what must not be heard. Default:
  "No music, no discernible dialogue", unless the scene needs otherwise.
```

The shape working prompts share: **one visual rule at the top, one sound rule at the
bottom, everything in between broken into shots.** CHARACTERS can be short when a
reference does that work; keep GLOBAL STYLE, the shot breakdown, and AUDIO regardless.

### Genre, era, and lighting carry more than prose

On vendor web platforms these are UI selectors, and changing genre alone shifts pacing,
contrast, and camera behavior with the scene description held identical. **The API routes
above expose no such selectors**, so on OpenMontage tool calls that intent has to be
written into `GLOBAL STYLE` and `LIGHTING` explicitly — genre, decade, grain and color
response, light source and its angle, and the emotional register. Leaving them implicit is
the difference between a shot that reads as noir and one that is merely dark.

---

## Locks: continuity across cuts

Constraints do not belong in a trailing negative prompt. They go in **named blocks**,
usually phrased positively, stating what holds.

| Lock | What it solves |
|---|---|
| `FIRST FRAME AND SPATIAL BLOCKING` | Positions as x/y percentages of frame, plus the reverse-angle note: when the camera crosses, who ends up on which side, so they never swap |
| `SCREEN DIRECTION` | The axis. "Sea always screen-right, dune line always screen-left, never reverses" |
| `LENS LOCK` | One focal per segment in degrees of diagonal field of view: 84° wide, 47° normal, 29° portrait, 18° telephoto. Plus "no lens drift mid-segment" |
| `SINGLE-LENS LOCK` | One focal for the whole piece; framing changes because the operator walks. This is what reads as documentary |
| `COUNT LOCK` | "Exactly four, never five, no background double, no mirror or reflection showing an extra copy" |
| `STILLNESS LOCK` | The list of what does not happen: nobody stands, nobody hugs, no hand leaves the blanket |
| `POSITIVE LOCKS` | Closing block restating in positive terms what holds across cuts |
| `IDENTITY / NO-IP LOCK` | "A wholly original, invented face." No logos, no readable text, no recognizable melody |

**State monotonicity.** The cheapest continuity trick available: states only advance,
never reset. Wetness only accumulates. The cookie only shrinks — whole, bitten, two
halves, finished — and never regrows. Writing the progression shot by shot stops the model
from cleaning up your character on the next cut.

**One grammar per action.** When an action repeats, define one way to perform it and
forbid the rest, then close the list: exactly five sword actions in the piece, each with
its timestamp. Same for slow motion — allow-list it to named moments and nowhere else.

**Event tracks.** Write ambient elements as a timestamped event list rather than as
texture: each wave with its second and its spray height as a percentage of frame, at
irregular intervals. Works for sea, wind, rain, traffic, and crowds.

**Substitute, don't only forbid.** If you forbid something, supply the concrete
replacement. "No blood" is weak; "the cut edge glows orange, sparks blow out, the body
crumbles to ash" is enforceable.

---

## Assets

The piece is won or lost here, before any video generates.

**Character sheet: three plates, face on only one.** Full body front with the face
removed, full body back, and a 3/4 close-up carrying the face in two versions, smiling and
neutral. The face is stripped from the full-body plates because in a wide shot it is small
and blurry and the model copies that blur; if the only face in the set is a sharp
close-up, that is the one it uses. Without the smiling version the model invents teeth.

**One asset per state.** Variations are split into separate assets rather than noted in
the prompt: clean jacket, soaked, and bloodied. Splitting is cheaper than arguing.

**The rule of 10.** Before accepting an asset, generate it ten times across different poses
and lighting. It must stay recognizable all ten.

**Locations.** Do not generate a head-on still. Generate a video of the empty space with
the camera moving slowly, then derive the other sides of the room from that footage. A
still gives you a wall; a slow travelling gives you geometry.

---

## Voice

Voice is a **conditioning sentence, not an asset**. Write it once with accent, tempo, and
manner, then paste it verbatim — without changing a word — every time that character
speaks. Rewording widens the sampling range and destabilizes the voice.

Write accent phonetically, describing what the mouth does rather than where the speaker is
from: `th going to f and v, dropped h, glottal t, -ing to -in'`.

Keep audio tracks separate. Never voice and music in the same reference clip.

---

## What the model cannot do

| Failure | Workaround |
|---|---|
| **Singing** | Pre-record the track, cut it into 12-second files, and label each `THE TRACK THEY ARE PERFORMING`. The label states the audio's role in the scene; `audio guide, for sync only` is technically accurate and produces nothing usable |
| **Sustained physical contact** | Fights and two bodies in constant contact. Shoot the reference on a phone and pass it as a motion reference; cheaper than twenty iterations |
| **Multi-character scenes** | The hardest category. The more faces in one shot, the more reference material each needs to avoid drifting into a generic face by the third or fourth cut |

---

## Chaining and correction

Past 30 seconds, extend the previous clip or pass it as a video reference plus a
description of what comes next — the second route also lets you introduce new characters
or objects at the seam. Avoid vendor "long video" options that stitch several generations
from one short prompt: there is not enough detail available for the runtime.

For a single wrong element, edit rather than regenerate, stating what changes and what
holds:

```
Around the 2-second mark, change only [X] from [before] to [after].
Keep the characters, movement, camera, lighting, composition and timing unchanged.
```

A repaired frame can also be passed as a start image for a short replacement segment.
Note the tension: a published 110-minute Seedance production banned starting frames
throughout, so continuity was carried by the assets rather than by the previous take's
last frame, which drags its own drift. Treat the start-image repair as a point fix, not as
a continuity method.

---

## Cost and verification

All supported routes are paid. Confirm the exact provider/model before calling
and review the result for identity continuity, cuts, lip sync, audio artifacts,
and prompt adherence. ComfyUI Partner Nodes use prepaid Comfy credits and are
not an offline fallback.

Iteration discipline that keeps that cost bounded:

- **Lock the assets before generating anything.** The model has no memory: re-describe
  everything, every time.
- **Change one thing per iteration**, or you will not know which change fixed it.
- **At 10 to 15 failed iterations, simplify or split the scene, not the wording.**
- Explore at the lowest resolution the route offers and only re-run what works.
- Keep a log of version, what changed, and verdict.
- **Judge the whole clip, never a single frame.** A good still can come from a generation
  that falls apart at second 9.
- Land cuts on movement, never on a still pose.

---

## Reference

[`reference/techniques.md`](reference/techniques.md) — ten prompt archetypes, the settings
each used, why the combination works, and which technique each one introduces. Use it to
pick the closest archetype before writing from scratch.

## Provenance

The prompting method, lock patterns, and asset rules above are distilled from material the
Higgsfield team published in August 2026 — an official Seedance 2.5 prompting guide of ten
categories each tested across multiple generations, and the open-sourced production method
of a 110-minute Seedance feature. No prompt from either source is reproduced verbatim; the
technique is restated with original templates. Credit for the underlying work is theirs.

- <https://higgsfield.ai/blog/seedance-2-5-prompting-guide>
- <https://higgsfield.ai/original-series/cully-hill-boys/full-film>

The route table, provider field names, and cost guidance in this file are OpenMontage's own
and take precedence over anything a vendor blog implies about API availability.
