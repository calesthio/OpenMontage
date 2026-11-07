# OpenMontage — Host Character Design (draft, owner review needed)

Status: DRAFT. Nothing like this existed yet — STICK4's `ref_face.png` was a
placeholder (seed 1111, no actual design). This fills that gap so whichever
consistency path wins (IP-Adapter Plus or 1Prompt1Story) has a real
character to anchor on, not a blank seed.

## Why this design, given everything found today

- Education & Science positioning (RPM research) rewards a calm, credible
  documentary tone — not a cartoon mascot. Keeps "Made for Kids" risk low
  per the FTC factors already checked (child-directed activities/incentives/
  toys are the real trigger, not illustration style itself).
- Works for both the speculative-biology content and general
  science-explainer content without re-dressing the character.
- Kept deliberately simple: diffusion-based consistency (IP-Adapter Plus,
  1Prompt1Story) holds onto a FEW bold, describable features far better
  than an intricate costume — the Calliope Labs reference sheet's own
  notes made the same point ("high eyebrow and cheek scar are constant").
- No real person, no specific ethnicity/gender signalled beyond what's
  described below — avoids resting the design on a stereotype.

## The character: a field researcher, not a mascot

A practical, calm field-scientist figure — the kind of person who'd
actually be out cataloguing a reef or a fossil bed, not a cartoon
professor. Narrates like a documentary field correspondent: curious,
precise, never cutesy.

## Constant features (the anchor — reuse this exact block everywhere)

```
a field researcher character: short practical dark hair, a brass loupe
(magnifying lens) worn on a cord around the neck, a weathered
field jacket with rolled-up sleeves, calm steady expression
```

These three details — loupe-on-a-cord, rolled sleeves, short practical
hair — are the recognizability anchor. Everything else about the scene
(pose, background, lighting direction) can and should vary freely;
these three should not.

## Model-sheet generation prompt (for the reference image)

Use the locked prefix/suffix from `prompt_recipe_comic_ink.json` around
the constant-features block above, in a turnaround layout:

```
bold ink illustration, graphic novel style, clean linework, hand-inked outlines,
character reference sheet, a field researcher character: short practical dark
hair, a brass loupe (magnifying lens) worn on a cord around the neck, a
weathered field jacket with rolled-up sleeves, calm steady expression, three
views front and three-quarter and side on one sheet, plus one close-up head
study, muted limited color palette, dramatic directional lighting, consistent
ink style, high detail linework, flat neutral background, no text, no labels
```

Negative prompt: reuse the one already locked in `prompt_recipe_comic_ink.json`
unchanged.

## For 1Prompt1Story specifically (if it becomes the chosen path)

1Prompt1Story wants one concatenated prompt starting with an identity
sentence, then per-frame continuations. The identity sentence should be
exactly the constant-features block above, unmodified:

```
a field researcher character: short practical dark hair, a brass loupe
(magnifying lens) worn on a cord around the neck, a weathered field jacket
with rolled-up sleeves, calm steady expression, [then: frame 1 action],
[frame 2 action], [frame 3 action]...
```

## What's still a decision for the owner, not assumed here

- Name for the character (or channel-brand mascot name) — left blank.
- Voice: whether Kokoro's `af_heart` (already decided for narration) is
  also this character's "voice", or the character is silent/on-screen
  only while a separate narrator voice plays — not decided.
- Age/presentation beyond "calm, practical, short dark hair" — kept
  deliberately open rather than guessed.
