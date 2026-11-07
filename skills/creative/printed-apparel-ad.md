# Printed Apparel Ad — ads for AOP / POD garments

Extends [`shopee-product-ad.md`](shopee-product-ad.md). That skill takes a product
link to a finished vertical ad; this one overrides its Step 2 and Step 4 for a
product class that breaks them: **garments whose selling point is a printed
design**. All-over-print sweatshirts, novelty tees, POD hoodies, anything from
BurgerPrints / Printify / Wrappiness / a Shopee AOP listing.

Everything below was measured on Google Flow (Omni) in Sep 2026 across two such
products. The failures are recorded because each one looked reasonable while it
was being made.

## When to use

The product **is** a printed image on fabric, and the ad fails if the print is
wrong. Use `shopee-product-ad.md` unchanged for anything else.

## The hard gate: never describe the print

A generative model cannot be talked into an exact printed design. Four prose
attempts on one product, four different failures:

| What was tried | What came back |
|---|---|
| Character stills as refs in video "Thành phần" mode | Portraits of the cast printed onto the garment |
| Full garment description, text only | A closed red vest with a belt — a different product |
| Full description + the flat product photo as a reference | A knitted novelty-jumper texture instead of a flat print |
| Same, plus the surface pinned as "a flat print" | Flat cartoon vector art, and a content-filter refusal |

What works is the opposite of effort: attach an **approved still of the garment
being worn** and say nothing about what the design depicts. The wording that
landed it, verbatim:

> …wears exactly the sweatshirt from the reference photo, with the printed design
> identical in every detail — same artwork, same colours, same size, same position
> on the body. It is a photographic all-over print on smooth sweatshirt fleece,
> not knitted, not embroidered and not a cartoon drawing. Nothing from a reference
> photo is reprinted onto the garment as a portrait.

Three clauses, each earned: *identical in every detail* pins it; *not knitted, not
embroidered, not a cartoon* kills the three texture drifts; *nothing reprinted as
a portrait* stops the model treating your reference photo as artwork to print.

**Enforce it in code, not in intent.** The generation script asserts that no
prompt contains a word describing the design:

```python
for banned in ("suspender", "belly", "torso", "hairy", "navel", "snowman print"):
    assert banned not in text, f"{label}: {banned!r} describes the print — let the reference carry it"
assert "identical in every detail" in text
assert "not knitted, not embroidered and not a cartoon drawing" in text
```

## The pipeline: settle everything while it is free

Flow images cost 0 credits; an 8s clip costs 12. So every argument that can be
had over a still is had over a still, and the video stage only ever animates
frames already approved.

```
product photos (flat lay + one worn mockup)
        ↓  0 credits — regenerate until the print matches, review it yourself
  hero still: the new model wearing it, whole print visible collar to hem
        ↓  0 credits — every beat still is generated FROM the hero
  one still per beat
        ↓  12 credits each — image_to_video, one still in, no end frame
  one clip per beat
        ↓  ffmpeg
  the cut
```

The hero still is the single pin for the whole ad. Generate beat stills from it,
never from the product photos again, or the model's face drifts between beats.

Review with `visual_qa` (`operation: "review"`) and read the frames. Not the
browser — the project has the tool.

## The filter rule: no undressing beat, by construction

Flow refuses to animate a garment coming off when the print depicts skin. Both
of these were refused, on a product whose print showed a bikini and a midriff:

- "…pull their coats open and off their shoulders, revealing both printed sweaters"
- "…take their coats off together and hold them down at their sides"

A control run proved the images are fine: **the same two stills generated
normally under a neutral prompt** ("the camera holds steady, nobody moves"). It
is the described act of removal that trips it.

Three consequences, in priority order:

1. **Design the ad without an undressing beat.** Showcase-Reaction (below) has
   none. This is the only legitimate fix — the format simply does not need it.
2. **If a reveal is essential, put it in the cut.** Generate one clip holding on
   the covered state and one holding on the revealed state, each from its own
   still, each prompt carrying "dressed exactly as in the first frame for the
   whole clip; no clothing is put on, taken off or changed". The hard cut between
   them is the reveal. The measured reference ad does it this way anyway.
3. **Start+end frames are only safe when both frames wear the same clothes.**
   A start frame in a coat and an end frame without one is the refused
   configuration, expressed in pictures instead of words.

**Never search for wording that slips past the filter.** Two refusals is the stop
signal: report it and offer the routes below. Rewording until something passes is
evading a safety control, whatever the content turns out to be.

When it fires on content that is plainly benign, the honest options are: Flow's
own "gửi ý kiến phản hồi" link on the refusal (report the false positive), a
different provider for that one shot (`kling_video`, `runway_video`,
`seedance_video`), or real photography.

Assert it too:

```python
for banned in ("take off", "takes off", "pull open", "revealing", "reveal", "undress"):
    assert banned not in text, f"{name}: {banned!r} is the refused wording — the ad has no undressing beat"
```

## Archetype: Showcase-Reaction

Added to `shopee-product-ad.md` Step 2's table for this product class. Use when
the brief asks for **design showcase** plus **UGC reaction**, or whenever the
product is a print that people react to rather than a gadget that does something.

Keeps the measured rhythm of the reference ad in
`projects/_analysis/fb_dropship_ref/` — 10.0s, four beats, accelerating, at most
one word spoken, no on-screen text — and replaces its mechanic:

| Beat | Share | What happens | Job |
|---|---|---|---|
| 1 | ~42% (4.2s) | The wearer walks past a group. Someone glances, looks away, **snaps their head back** and stares | Hook — the double-take is the whole thesis |
| 2 | ~21% (2.1s) | Camera pushes in on the print alone, filling frame, chin just in shot | **The showcase.** The design gets its own beat and no human competes with it |
| 3 | ~22% (2.2s) | A friend **reaches out and touches** a detail of the print, then cracks up | Proves the print is real and worth touching |
| 4 | ~15% (1.5s) | The group crowds in laughing, one of them points at it | Social proof, out on the laugh |

Rules that make it work:
- Beats 1, 3 and 4 each **end on a reaction**. Assert at least three do.
- Beat 2 has **no reaction at all** — it is the only quiet beat, and cutting it
  short is what makes the design register.
- The print faces camera and is never covered by an arm in any beat.
- One continuous location. Unlike Repeat-Reveal, changing rooms costs you the
  UGC feel; consistency reads as one real evening.

## Casting

If the client's mockups use one body type, cast **against** it. A printed dad
belly on a slim young woman reads instantly as a print — which makes it both a
clearer product showcase and a better joke than the same print on the man it was
photographed on. Say in one line which reading of "a different model" you took;
"different person" and "different garment variant" are both plausible and one
sentence saves a whole regeneration.

## Cost, measured

| Stage | Unit | Flow (Omni) |
|---|---|---|
| Product/hero/beat stills | per image | **0 credits** |
| Clip, 4s | per clip | 7 credits |
| Clip, 8s | per clip | **12 credits** |

8s is worth it over Flow's 4s floor: it gives the reaction room to land and
leaves headroom to cut the best seconds out. A four-beat ad is ~48 credits.

## Common pitfalls

- **Describing the print because the reference "isn't quite right".** It never
  gets better. Regenerate the still — it is free — and leave the prompt alone.
- **Generating beat stills from the product photo.** The face drifts every time.
  Generate them from the hero still.
- **Counting reference chips with a selector that matches two nodes per chip.**
  `REF_CHIP` double-counts; count `button.chip-container`.
- **Assuming a refusal charged you.** Flow states it on the refusal line — read
  it before reporting spend.
- **Letting the showcase beat run long.** It is the shortest beat that carries
  the most; at 2.1s it registers, at 4s it stalls.
- **Forgetting that the *other* people are wearing clothes too.** A no-text
  clause that only bans captions and overlays still lets the crowd turn up in
  slogan jumpers, and the model renders those slogans as broken half-words. Add:
  "nobody else in shot wears clothing with any writing, slogan or lettering on
  it". Bites hardest on the group beat, where the crowd is the point.

## Sources

- `projects/wrappiness-ad/FINDINGS.md` — the five findings, with the control run
  that separated the image from the wording
- `projects/_analysis/fb_dropship_ref/` — the measured reference ad (10.05s,
  4 scenes, [4.23, 2.13, 2.17, 1.52], one spoken word)
- `scripts/_gen_wrappiness_ad.py` — a working implementation; its `check()` is
  the enforcement described above
- `lib/flow_driver.py:attach_reference_images` — one asset per picker session,
  uploads cached in `~/.openmontage/flow_uploads.json`
