---
name: flow-video
description: Prompting and operating guide for the flow_video tool — Veo 3.1 and Omni generation driven through a Google Flow browser tab with Playwright, billed to a Flow subscription instead of an API key. Covers prompt shape, the model-dependent duration/resolution matrix, credit economics, and the browser-specific failure modes.
metadata:
  version: "1.0.0"
  tags: video-generation, veo, omni, google-flow, subscription, no-api-key, playwright
---

# Flow Video (Veo 3.1 / Omni via Google Flow subscription)

Layer 3 skill for `flow_video`. Read this before writing any prompt for that tool.

## What makes this provider different

Every other video provider in the registry bills an API key per clip. This one drives
the **Google Flow web UI** inside the user's own signed-in Chrome and spends
**subscription credits** instead of money. Four consequences shape how you use it:

1. **It needs a human's browser to be awake.** A Chrome started with a debugging
   port and signed in to Flow. This is not a headless server capability — never
   plan an overnight batch around it.
2. **One clip at a time.** There is a single tab and a single prompt editor, so the tool
   holds a lock. Concurrent calls fail rather than interleave.
3. **Credits are a daily allowance, not a balance you top up.** Running out means waiting
   until tomorrow, not paying more. Budget the shot list before generating. Measured on a
   PRO plan: Omni 1.1 Flash 4s ≈ 7 credits, Veo 3.1 Fast 8s ≈ 20.
4. **The UI moves under you.** Flow ships changes weekly. Selectors have fallbacks, but a
   redesign can break generation until they are updated. Treat a sudden run of failures
   as "Flow changed", not "the prompt was bad".

## Prompting

The Veo tiers are the same family `veo_video` reaches through the API, so the prompt
craft transfers; Omni responds to the same vocabulary. Veo responds to cinematography vocabulary, not tag soup:

- **Write a shot, not a subject.** "slow dolly-in on a paper boat drifting down a
  rain-slicked gutter, macro lens, shallow depth of field, overcast light" beats
  "paper boat, rain, cinematic, 8k".
- **Name the camera move explicitly.** `dolly in`, `crane up`, `orbit left`, `handheld
  follow`, `locked-off wide`. Veo honours these; vague "dynamic camera" it does not.
- **Put the audio in the prompt.** Veo 3 generates synced audio natively. Describe it:
  "ambient: rain on metal, distant traffic; no music". Say `no dialogue` when you want
  none, or Veo may invent muttering.
- **One action per clip.** At 4–8 seconds there is room for a single beat. Two actions
  produce a cut that you did not ask for and cannot control.
- **Lighting and lens carry the look.** "golden hour backlight, anamorphic flare, 35mm"
  does more work than any style adjective.
- **There is no negative prompt.** State the absence positively: "empty street, no people".
- **Disambiguate nouns that name two things.** A prompt asking for "a lone red kite
  tumbling across a winter sky" produced a red kite the *bird* — correctly, since that
  is a raptor. Say "a paper kite on a string" when you mean the toy. Veo picks a
  reading and commits to it; there is no second guess for the credits you spent.
- **Vietnamese prompts work**, but English gives noticeably tighter adherence for camera
  and lens terms. Write the prompt in English even when the project is Vietnamese.

## The matrix Flow actually offers

| Parameter | Values | Notes |
|---|---|---|
| `model_variant` | `Lite`, `Fast`, `Quality`, `Omni` | **Pick this first — it decides which other controls Flow renders.** Veo 3.1 tiers fix length and resolution (~10 credits); `Omni` exposes both (~7 credits). |
| `duration` | `4`, `6`, `8`, `10` | Optional, and **only offered by Omni**. Naming one on a Veo tier fails before any credit is spent. |
| `resolution` | `360p`, `720p` | Optional, Omni only. |
| `aspect_ratio` | `16:9`, `9:16`, `1:1`, `3:4`, `4:3` | Set in the pill, not the prompt. |
| `operation` | `text_to_video`, `image_to_video` | Image-to-video takes a local first frame via `reference_image_path`. |

For a 1080×1920 short, ask for `9:16` here rather than generating `16:9` and cropping —
Veo composes for the frame it is given.

## Operating notes

- **Runs are serialized** through a lock at `~/.openmontage/flow_video.lock`. A parallel
  call returns an error rather than fighting over the prompt editor. Plan the asset stage
  sequentially.
- **Download quality.** The driver asks Flow for the upscaled 1080p render first and
  falls back to the native resolution. A body under 100 KB means Flow had not finished
  rendering, and is refused rather than written out as a truncated mp4.
- **Cost reporting.** `estimate_cost()` returns `0.0` because no money moves. That is not
  the same as free — always state the credit cost alongside the $0.00 in the proposal.
- **The user can watch it work.** The Flow tab visibly types and clicks. Tell the
  user not to type in that tab, and not to attach another debugger to it (DevTools,
  another automation tool), while a job runs — Chrome allows only one.

## Failure modes and what they mean

| Symptom | Cause | Action |
|---|---|---|
| `Playwright is not installed` | missing dependency | `pip install playwright` |
| `No Chrome is listening for automation on …` | Chrome has no debugging port | start it with `--remote-debugging-port=9222` **and** a dedicated `--user-data-dir` — the port is ignored on the default profile since Chrome 136 |
| `connect: this Chrome profile is not signed in` | fresh profile | sign in to Flow once in that window; the profile keeps the session |
| `settings: … does not offer a duration choice` | a Veo tier fixes its own length | omit `duration`, or use `model_variant: Omni` |
| `settings: "X" is not one of Flow's models` | model renamed or unavailable on this plan | the error lists what Flow actually offers; pick from that |
| `attach_frame: … is not in the picker` | upload landed but the picker did not refresh | the driver reloads the page for exactly this reason; if it persists, Flow changed the picker |
| `attach_frame: the start-frame slot is still empty` | the reference did not attach | **do not use the clip** — Flow would have generated from the prompt alone |
| `type_prompt: Flow still reports an empty prompt` | the editor did not accept the text | usually a stale page; reload the Flow tab |
| `Another Flow generation is in progress` | a previous run crashed holding the lock | delete the lock file named in the error |
| `Flow returned a Ns clip but Ms was requested` | the download picked up a different clip | **do not use the file**; rerun |
| Clicks silently do nothing | another debugger is attached to the tab | close DevTools and any other browser-automation tool — Chrome allows one per tab |
| Generation fails repeatedly with selector errors | Flow shipped a UI change | `lib/flow_driver.py` selectors need updating — expected maintenance |
| Out of credits | daily allowance spent | wait for reset, or fall back to `veo_video` / `seedance_video` if a key exists |

## Continuity pass — do this before delivering

AI shots are generated independently, so they break continuity in ways no single
clip reveals. Watching each clip on its own tells you nothing; putting the last
frame of shot N beside the first frame of shot N+1 tells you everything.

```bash
python scripts/flow_continuity_check.py <clip-dir>
```

It writes `seam_N_to_M.jpg` (last frame | first frame across every cut) and
`shot_N.jpg` (first | middle | last within each shot) into a `continuity/`
folder. **Review the seam sheets before stitching.** This is a judgement step,
not an automated one — the script only makes the judgement cheap.

What to look for, in the order it bites:

| Break | Example seen in production |
|---|---|
| **The action moves place between shots** | She dug a small hole in the dry lawn in shot 4, then shots 5-8 showed the planting inside a brick-edged bed of tilled soil. Different ground, different place. This one survived a first continuity pass because the review was hunting objects and colour; **check where the action happens and at what scale, not just what is in frame** |
| **The subject stands on or walks through what they just made** | Shot 7 put her standing *inside* the bed she had just seeded and watered, treading on it. Generated in isolation the shot is fine; after shot 6 it destroys the beat. An image prompt that names a place must also say where the person's feet are — "both feet on the grass, she does not step on the soil" |
| **An object undoes an earlier action** | A seed buried and covered in shot 5 lay uncovered on the soil in shot 8 — the viewer sees it climb back out of the ground |
| **Colour temperature jump** | Shot 8 rendered in warm golden-hour while shots 1-7 were pale morning |
| **Wardrobe drift** | Long sleeves in one shot, short sleeves in the next — caught in the photoreal cut |
| **Set drift** | Brick edging, buildings or planting beds appearing, moving or vanishing |
| **Light direction flip** | Sun raking from the left, then from the right |

Fixing one is cheap and worth doing: regenerate that shot's opening frame with
the contradiction named *explicitly and negatively* ("the soil is bare, there is
NO seed lying on it"), regenerate the one clip, re-stitch. One shot costs a
handful of credits; shipping a video where a seed climbs out of the ground costs
the viewer's belief in the whole piece.

The prompt-side counterpart — how to write a shot sequence so these breaks
do not happen in the first place — is in
[`references/shot-sequence-prompts.md`](references/shot-sequence-prompts.md).

Some differences are not breaks. A prop that changes hands or is set down
between shots reads as elapsed time; viewers accept it. Only chase things that
contradict a previous shot or physical sense.

Run the pass as four separate sweeps, because a single sweep finds only the
category it happens to be thinking about:

1. **Place** — is every shot in the same spot, on the same ground, and is the
   subject standing where the previous shot leaves them able to stand?
2. **Objects** — does anything appear, vanish, or undo a previous action?
3. **Continuity of person** — wardrobe, hair, what is in which hand.
4. **Light** — colour temperature and the direction the sun comes from.

Sweep 1 is the one that gets skipped, and it hides the largest errors: a whole
change of location reads as normal inside any single frame.

Expect to run the sweeps **more than once**. Fixing the shot that sweep 1 caught
re-renders its neighbours' seams, and the next-worst place error only becomes
visible once the worst one is gone — in this production, correcting shot 4
revealed shot 6, and correcting shot 6 revealed shot 7. Re-run all four sweeps
over all shots after every fix, not just the seams either side of it.

## Flow's internal API

Flow's own endpoints are mapped in
[`references/flow-api.md`](references/flow-api.md) — captured by instrumenting a
live session, credentials never recorded. Read it before changing how the driver
talks to Flow.

The short version: **the two credit-spending calls are the two behind bot
detection.** Starting a generation and upscaling to 1080p each carry a
reCAPTCHA Enterprise token; upload, status polling, credits and media download
do not. So generation runs through the real UI, where that token is a by-product
of actually using the app, and everything else uses the API directly.

The status endpoint is the honest place to read back what Flow *actually* did:
`videoGenerationMode` says `IMAGE_TO_VIDEO` or `TEXT_TO_VIDEO`, which is the
only reliable way to catch a reference image that was silently ignored.

## Scope and risk

Automating Flow plausibly violates Google's terms of service and carries a risk of
account suspension. This tool drives the user's **own** account in the user's **own**
browser. It has no multi-account rotation, no proxy support, and no detection-evasion
layer, and none will be added — those belong to account farming, not to a person
automating a subscription they pay for. Say this once when a user first reaches for the
provider; do not repeat it every run.

## When to pick something else

Reach for `veo_video`, `seedance_video`, or `kling_video` when the user has a key and the
job is a **batch**, or when generation must run unattended. `flow_video` is the right pick
when there is no video API key at all, when the user explicitly wants zero spend, or when
a handful of hero shots matter more than throughput.

## Images: `flow_image` (Nano Banana via the same tab)

Same driver, same Chrome, same lock. Switches the settings popover to **"Hình ảnh"**, picks a
Nano Banana model, an aspect (`1:1`, `16:9`, `9:16`, `4:3`, `3:4`) and `x1..x4`, then downloads
each tile at **"1K Kích thước gốc"** (~1024 px JPEG). Measured 2026-09-05: **0 credits per image**
on every Nano Banana model, so images do not touch the daily video allowance.

- `model_variant`: `2` (default, Nano Banana 2 — fast, excellent), `Pro`, `2 Lite`.
- `n` up to 4 gives variations of one prompt, not a sequence. For **animation frames that stay
  consistent**, ask for one image that is a `2x2 sprite sheet` of the same subject ("identical
  character, lighting and camera in every panel, thin white gaps") and split it afterwards —
  see `projects/hsg-van/gen_assets_flow.py`. Cut-outs: run `bg_remove` on each panel.
- Flow's **agent mode** ("Tác nhân" chip) hides the settings pill. The driver switches it off for
  the run and restores it. Do **not** use the Flow tab while a run is in progress: a click that
  opens a tile editor empties the grid the driver is watching, and the wait times out.
- No reference images yet (`supports.reference_image: false`); the add-media menu exists in
  image mode and is the upgrade path.
