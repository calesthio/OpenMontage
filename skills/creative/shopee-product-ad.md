# Shopee Product Ad — from a product link to a finished vertical ad

## When to Use

When the user hands over **a product link (Shopee/TikTok Shop/Lazada) or a product
description** and wants a short vertical ad made for it — "làm video cho sản phẩm
này", "clone kiểu video này cho sản phẩm X", a pasted Shopee URL with no other
instruction.

Do **not** use this for:
- Brand/story films or explainers → `skills/creative/short-form.md` + the normal pipeline
- A reference video the user wants analysed first → `skills/meta/video-reference-analyst.md`
  (run that first, then come back here with its findings)
- Editing footage the user already shot → the footage-led pipelines

## Prerequisites

| Resource | Why |
|---|---|
| `skills/creative/short-form.md` | Safe zones, LUFS, caption rules for 9:16 delivery |
| `skills/creative/video-gen-prompting.md` | The 5-aspect prompt vocabulary used in Step 4 |
| `.agents/skills/flow-video/references/shot-sequence-prompts.md` | STYLE/CAST/STAGE discipline when shots must share a person or place |
| `video_analyzer` tool | Measuring any reference video the user supplies |
| `video_selector` / a video-gen provider | Producing the clips |
| `video_stitch` / `video_compose` | Assembling the cut |
| `registry.provider_menu()` | Provider + cost + watermark check before spending |

---

## The measured DNA (reference: `@the.fattypack`, FB/TikTok, analysed 2026-09-13)

Do not treat this as folklore. These numbers came off the file itself via
`video_analyzer` + `scripts/clip_motion.py`, and they are the spine of the format:

| Property | Measured | What it means for you |
|---|---|---|
| Duration | **10.0s** | Well under the 15–30s "standard" — a single gag does not need 30s |
| Shots | **4** | 4.23s → 2.13s → 2.17s → 1.52s |
| Cut rhythm | **accelerating** | Shot 1 is ~2× every later shot. Set up slowly, pay off fast |
| Speech | **none** (empty transcript) | No VO, no dialogue. Music + visual gag + reactions carry it |
| Frame | 720×1280, 30fps | Vertical, phone-grade — not cinema-grade |
| Motion mean | 13.0 (cut-driven) | Reads as punchy because of the cuts, not camera moves |
| On-screen text | one line, persistent, top-centre | Never changes across all 4 shots |
| Watermark | brand IG handle, small | This **is** the CTA — there is no end card |

**The structural insight worth stealing:** it is *one* demo repeated in **four
different public places**, not four different features. Repetition in changing
settings is what sells "this works anywhere" and gives four payoffs in ten
seconds. Most people copying this format wrongly show four *features* — that is
a spec sheet, not an ad.

**The second insight:** the proof is a *bystander reaction* inside the frame
(cashier laughing, barista laughing, people turning). No testimonial, no
star rating graphic. The reaction shot is the social proof.

---

## Process

### Step 1: Intake the product — get facts, not adjectives

Shopee blocks most scrapers. In practice, in this order:

1. Ask the user to paste the product title, price, and 2–3 listing photos, **or**
2. Open the link with the browser tools (`mcp__claude-in-chrome__*`) and read the
   page, **or**
3. Work from the user's description alone.

Whatever the route, you need these five fields before going further. Write them
down explicitly — guessing any of them produces a generic ad:

```
PRODUCT:      [exact name]
WHAT IT DOES: [the one mechanical function, in plain words]
THE MOMENT:   [when in real life someone needs it]
THE VISIBLE CHANGE: [what an onlooker could SEE change — this is everything]
PRICE / TIER: [cheap impulse buy vs considered purchase]
```

**`THE VISIBLE CHANGE` is the gate.** If nothing visibly changes when the product
works, this format cannot sell it, and you must say so rather than produce a
pretty video that converts nothing. See Step 2.

### Step 2: Pick the archetype — not every product fits the gag format

| If the product… | Archetype | Shape |
|---|---|---|
| Produces a **surprising visible reveal** (hidden storage, transformation, before/after in <2s) | **Repeat-Reveal** (the reference) | Same reveal, 3–4 different public settings, accelerating cuts, bystander reactions |
| Solves a **visible daily annoyance** (tangles, spills, mess, pain) | **Problem-Snap** | 1 shot of the annoyance happening, 1 shot of product fixing it, 1 shot of the calm after |
| Is **satisfying to operate** (click, slide, snap, peel) | **ASMR Demo** | Macro hands, 3–4 close shots of the mechanism, no wide shots at all |
| Is a **printed garment** (AOP/POD sweatshirt, novelty tee) where the print is the product | **Showcase-Reaction** → [`printed-apparel-ad.md`](printed-apparel-ad.md) | Double-take, a silent beat on the print alone, someone touching it, the group laughing. Read that skill first: describing the print in a prompt fails every time |
| Has **no visible change** (supplements, software, scent, comfort) | **Do not use this skill** | Say so. Recommend a talking-head/testimonial route instead |

Tell the user which archetype you picked **and why**, in one sentence, before
building shots. If the product falls in row 4, say that plainly — an honest "this
format won't sell this product" is worth more than a video that looks fine and
converts nothing.

### Step 3: Build the beat sheet

Copy the reference's *rhythm*, not its content. For Repeat-Reveal:

```
Shot 1  ~4s   SETUP + FIRST REVEAL.  Product visible by 1.0s. Ordinary setting.
              One bystander in frame who can react.
Shot 2  ~2s   SAME REVEAL, NEW PLACE. Different setting, different bystander.
Shot 3  ~2s   SAME REVEAL, NEW PLACE. Escalate: busier place or bigger reaction.
Shot 4  ~1.5s SAME REVEAL, BIGGEST REACTION. Cut out on the reaction, not after it.
```

Hard rules, each traceable to the measurement above:
- **Total 10–12s.** Adding shots to reach 30s kills this format.
- **Each shot shorter than the last.** Never let a later shot run longer.
- **The product is on screen in the first second of shot 1.** Not at 0:03.
- **Every shot contains a person who reacts.** A product alone on a table is a
  catalogue photo, not this format.
- **Cut on the reaction.** The laugh/turn/double-take is the last frame, not the
  middle of the shot.

### Step 4: Write the shot prompts

Use the 5-aspect vocabulary from `skills/creative/video-gen-prompting.md`
(Subject / Subject Motion / Scene / Spatial Framing / Camera). Because the same
person and the same product must survive four independently-generated shots,
also apply the pinning discipline from
`.agents/skills/flow-video/references/shot-sequence-prompts.md`:

- One **`SUBJECT`** block, pasted verbatim into every shot — measurable attributes
  only (build, age, hair, exact clothing). Same person, four places.
- One **`PRODUCT`** block, pasted verbatim into every shot — shape, colour,
  material, size relative to a hand.
- **`SETTING`** changes per shot; everything else does not.
- State absences positively: there is no negative prompt. "no text, no caption,
  no watermark, no logo, no graphics of any kind anywhere in the frame."

### Step 4b: Honour the no-text / no-watermark constraint

The reference leans on a burned-in text hook and a brand watermark. If the user
asks for **neither** (the default ask for this skill), two things change:

1. **The hook must be fully visual.** The product's visible change has to land in
   the first ~1s of shot 1 — there is no text to explain it. If the reveal needs
   a sentence to make sense, the archetype is wrong; go back to Step 2.
2. **There is no CTA in the frame.** The CTA lives in the caption and the
   profile. Say this to the user so they do not expect one.

**Provider check — do this before generating, not after.** Some providers stamp
an unavoidable visible watermark; Google Flow applies one automatically for
accounts in India, South Korea and Vietnam, and it cannot be switched off from
the tool. If the deliverable must be watermark-free, run
`registry.provider_menu()` and pick a provider that does not impose one, and
tell the user what that choice costs. Do not promise a clean frame from a
provider that will stamp it.

### Step 5: Generate, stitch, verify

1. Generate each shot with the selected provider. **Sample shot 1 first** and show
   it before producing the rest — this format lives or dies on whether the reveal
   reads in one second.
2. Stitch with hard cuts only (`video_stitch`). No dissolves — the reference has
   none, and a dissolve kills the snap.
3. Verify before delivering:
   - `python scripts/clip_motion.py <dir> --cuts` — catches a provider inserting
     its own cut inside a shot.
   - Watch shot 1 muted. If you cannot tell what the product does with the sound
     off, it fails; regenerate.
   - Confirm zero burned-in text/watermark if that was the ask.

### Step 6: Self-evaluate

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| Hook speed | Product appears after 3s | Appears ~2s | Visible and doing its thing by 1s |
| Rhythm | Shots equal or getting longer | Roughly even | Strictly accelerating, ends ≤12s |
| Repetition logic | 4 different features shown | 2 settings | Same reveal, 3–4 distinct settings |
| Reaction/proof | No people | A person present but passive | Every shot ends on a visible reaction |
| Mute test | Unintelligible without sound | Mostly clear | Fully clear with sound off |
| Frame cleanliness | Stray text/watermark/logo | Minor artefacts | Completely clean as specified |
| Subject consistency | Person/product changes between shots | Minor drift | Identical across all four |

Score ≤3 on **Hook speed**, **Mute test**, or **Subject consistency** → fix before
delivering. Those three are the ones the format cannot survive.

---

## Common Pitfalls

- **Stretching to 30 seconds.** The measured reference is 10s. Length is not value
  here; it is decay.
- **Showing four features instead of one repeated reveal.** This is the single most
  common failure when copying this format. Four features is a spec sheet.
- **Product arriving late.** If the first second is a person walking toward camera
  with the product still in a bag, the ad is already over.
- **Empty frames.** A product alone on a clean table has no reaction, and the
  reaction *is* the proof.
- **Letting the person or product drift between shots.** Four independently
  generated clips will produce four different people unless `SUBJECT` and
  `PRODUCT` are pasted verbatim into every prompt.
- **Promising a watermark-free deliverable without checking the provider.** Check
  first (Step 4b); a watermark discovered at delivery means regenerating everything.
- **Using this skill for a product with no visible change.** Say so at Step 2 and
  recommend a different format. Producing it anyway wastes the user's money.

## Sources

Format research, September 2026:
- [UGC Script Templates: 10 Proven Structures & 20 Hook Formulas — Reloop](https://reloop.so/blog/article/ugc-script-templates/) — hook→problem→solution→CTA timing bands
- [UGC Hooks: 50+ Examples & Proven Formula — Vidlo](https://vidlo.video/blog/ugc-hooks) — 1.7s average scroll decision
- [Scroll-stopping hooks for ads: 7 frameworks — Zeely](https://zeely.ai/blog/7-scroll-stopping-hooks/) — visual-only hook techniques for muted viewing
- [How to Make Video Ads for Dropshipping That Convert — Spocket](https://www.spocket.co/blogs/how-to-make-video-ads-for-dropshipping) — 15–30s cold-audience band
- Primary measurement: `projects/_analysis/fb_dropship_ref/` (video_analyzer brief, scenes.json, clip_motion output)
