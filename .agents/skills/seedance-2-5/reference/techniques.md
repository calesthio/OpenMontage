# Seedance 2.5 — the ten official prompt categories

Higgsfield published a prompt library of ten categories in August 2026, each tested across
multiple generations to see which structures hold up on a second run. This file records the
settings each category used, why that combination works, and **which technique it
introduces**.

Use it to pick the closest archetype before writing from scratch.

The full prompts are at <https://higgsfield.ai/blog/seedance-2-5-prompting-guide> with a
copy button. They are not reproduced here — what follows is the extractable method.

---

## 1. Dramatic exterior · human subject, available light

**Settings:** Genre drama · Golden hour, single motivated source · Emotional control: grief
held beneath composure · Anamorphic large format, mixed wide and close coverage.

**Why it works:** drama holds shots longer than most genres, so a two-hander has room to
play out. Golden hour keeps the light identical across every segment without describing the
sun's position in each one.

**Introduces:**
- **Event track.** The sea declared "an event track, not a texture", with every wave and
  gust given its timestamp and its spray height as a percentage of frame. Irregular
  intervals, no two identical.
- **STILLNESS LOCK.** The list of what does not happen: nobody stands, nobody hugs, no hand
  leaves the blanket. Exactly one tear falls, hers, at 13.2s.
- **Blocking in percentages.** Her at x 42%, head at y 44%. Him at x 58%, y 42%.
- **Reverse-angle note.** When the camera crosses to the seaward side she reads screen-right
  and he reads screen-left. They never swap sides.
- **LENS LOCK per segment** in degrees: 47° for the wides, 29° for the close-ups.
- **Invented face.** "A wholly original, invented face", so no real likeness is cloned.

## 2. Action sequence · multi-shot choreography

**Settings:** Genre action · Physics realistic, high impact, real paper mass and inertia ·
Anamorphic, hybrid handheld and gyro rig · Hard cold key with a single warm accent.

**Why it works:** action tightens pacing and keeps the camera close to the movement, so a
nine-shot fight reads as one continuous sequence rather than stitched takes.

**Introduces:**
- **Physics per material, named and marked critical.** An entire block devoted to the
  banknotes being individual paper — visible fibre, worn creased edges, each bill tumbling
  on its own air current — so hundreds of notes do not read as one rigid mass.
- **Marking sections "(critical)".** Flagging the block that must not be ignored.
- **Palette in percentages.** 60% cold steel, 30% matte black, 10% warm focal pop. "She and
  the cash are the only warm things in a cold world."
- **Author references "in spirit, fully original execution".** Naming directors and
  cinematographers without copying a specific work.
- **Explicit anti-plastic block** enumerating real optical imperfection: film grain, gate
  weave, halation, chromatic aberration, lens breathing on focus pulls.
- **Cuts land on the hits**, never on a still pose.

## 3. Commercial product · multi-reference scene

**Settings:** Genre general · True handheld with light shake · Physics: real magic on honest
rules.

**Why it works:** locking three references (person, location, product) keeps all three
stable while the gimmick happens around them.

**Introduces:** the effect defined as a **mechanic with rules**, not as an adjective. Color
waves radiate from each footfall at constant radial speed, repaint what they cross, and
stay. One mechanic the model repeats identically instead of improvising it shot to shot. If
your piece has a visual trick, write it this way.

## 4. Epic landscape · environment as protagonist

**Settings:** Genre epic · Slow steady push-in across all three shots · Bright diffused
daylight, cold grade.

**The shortest of the ten.** Three shots, three sentences, `Hard cut` between them, and a
closing consistent-look block with the exclusions (no people, no animals, no birds, no
shake).

**Lesson:** with no people on screen, almost no locks are needed. Prompt complexity should
track what can actually drift, not ambition.

## 5. Noir · shadow and atmosphere

**Settings:** Drama with a noir base · Hard key, high contrast, monochrome · Anamorphic with
the lens locked per segment.

**Introduces:**
- **LOCATION MAP.** The space written out: the camera works from the south sidewalk facing
  north for the entire sequence, with background, midground, and foreground specified.
- **SCREEN DIRECTION LOCK.** The sedan always arrives from screen-right, the woman always
  travels right-to-left, the camera never crosses to the far side of the street.
- **Lens ladder per segment:** 84° wide, 29° medium, 47° normal, 18° telephoto for the
  two-shot, 84° again for the low finish, with "no lens drift mid-segment".
- **State monotonicity** applied to wetness: it only accumulates, never resets.
- **Controlled legible text:** the only readable text anywhere is the neon sign's word.

## 6. Multi-character · consistent faces across frames

**Settings:** Action, performance piece · Average shot under 1.5 s · Dual-quality system.

**The hardest category:** four named characters across twenty-four fast cuts, with no time
to re-establish who is who between them.

**Introduces:**
- **COUNT LOCK.** Exactly four, never five, no background double, no cloned member, and no
  mirror, glass, or reflection showing an extra copy.
- **DUAL-QUALITY SYSTEM.** Every beat tagged `[FILM]` or `[REPORTER CAM]`, the degradation
  described in full, and an explicit rule that it **never leaks** from one into the other.
- **Match-cut motif.** Round shapes and eyes that rhyme between scenes: CRT screen,
  porthole, dental lamp, planet disc, pupil.
- **Wardrobe by act**, declared in the locks block.
- "Exactly five fingers per hand."

## 7. Fantasy action · character and creature at scale

**Settings:** Epic, action · Hyperbolic physics, no blood anywhere · Emotional control:
calm, focused, not afraid.

**Introduces:**
- **One grammar per action.** She only cuts, never stabs, with the four phases of the cut
  written out, plus a **closed list** of the five sword actions in the piece and their
  timestamps.
- **Slow-motion allow-list.** Two moments only, with exact timestamps, nowhere else.
- **Substitute rather than only forbid.** No blood: the demons are cooled lava with fire
  inside, the cut edge glows orange, sparks blow out, the body crumbles to ash.
- **Numeric heights.** Ledge floor is zero, the horde is 2.5 m, the archdemon 5 m with eyes
  at 4.5 m; she levels at 4 m and drops to 3 m so he is looking down at her.
- **A geometric weak point** with measurements and the condition that exposes it.
- **Progressive dirt** that never cleans up.

## 8. UGC-style ad · natural movement, no production feel

**Settings:** Genre general, no genre-specific visual logic imposed · Handheld selfie framing
fixed for the whole video · Soft even cabin light · Emotional control: understated, no
performing.

**Introduces:**
- **Performance by imperfection.** Natural blink rate, reactions arriving half a beat late,
  smiles that start small and grow, the glance away from the lens and back mid-sentence, the
  lowered voice of someone self-conscious about filming on a plane.
- **Live background people, not NPCs.** Each with an independent activity; nobody looks at
  the camera and nobody reacts in sync.
- **Fixed seating geometry** across all eight shots.
- **State monotonicity** applied to the cookie: whole, bitten, two halves, finished, never
  regrowing.
- **Turbulence that exists in two shots only and never returns.**
- **Dialogue per shot in complete sentences**, with all speech ending by 25s.

## 9. Horror · wrong light, wrong angle

**Settings:** Genre horror · Deep one-point perspective, 4:3 · Real weight and inertia ·
Emotional control: tired, welling tears, held tension without release.

**Introduces:** the negative space past the shoulder declared first empty, then filled —
dread built from absence rather than a reveal.

And the most elegant rule of the ten: the antagonist is **never in sharp focus** until the
final second. Always a blur, a silhouette, a fragment behind shelves. "The autofocus refuses
to lock on her." Focus directed as a narrative device.

## 10. Documentary · observational camera

**Settings:** General, third-person observational · A single 47° lens for the entire
sequence · Five distinct natural light states across one continuous span of time.

**Introduces:**
- **SINGLE-LENS LOCK.** One focal length for thirty seconds; every framing change is
  achieved by the operator physically walking, with camera-to-subject distance declared per
  segment: 5 m, 2 m, 3 m, 2.5 m, 7 m.
- **Crowd size as the clock.** Forty people at the start, sixty, a hundred at the peak,
  fifteen or twenty deep in the night, five or six by dawn — so it reads as one continuous
  night rather than five separate scenes.
- **FRAMING RESPECT LOCK.** The camera treats her as a person at a party, not a body: no
  slow pans up or down a figure, no isolated shots of torso or legs, no low angles.
- **BEAUTY WITHOUT RETOUCHING LOCK.** Visible pores, developing sunburn, salt drying to a
  faint bloom, sand along the forearms, tired eyes by dawn.
- **CLEAN-AIR LOCK.** Nobody smokes; the only smoke comes from the fires and always travels
  out to sea.
- **Wardrobe layered progressively** as the temperature drops.

---

## The six findings from their testing

1. **References hold identity across cuts more reliably than a text description.** Once a
   face or product is locked as a reference it survives hard cuts, lighting changes, and
   camera moves that would otherwise cause drift.
2. **Genre and lighting settings do more work than most of the prompt text.**
3. **Multi-character scenes are the hardest category to keep consistent.** The more faces in
   one shot, the more reference material each needs.
4. **The shot-by-shot breakdown outperforms a single continuous scene description** for
   anything with more than one camera angle. Vague transitions are the most common cause of
   a sequence falling apart.
5. **50 references is a ceiling worth using deliberately, not maxing out by default.** A
   cluttered set produces a less coherent result than a smaller, carefully chosen one.
6. **GLOBAL STYLE and AUDIO function as guardrails more than instructions.** Explicitly
   excluding what should not appear prevents more failures than adding positive description.
