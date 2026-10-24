# Speculative Evolution Style Bible — OpenMontage Milestone S1

**Niche:** speculative_evolution / alien ecosystems (AI stills only).
**Rights basis:** ai_generated_illustration, generator: AI.
**Status:** DRAFT.

## 1. Purpose

Single source of truth for AI-generated still illustrations used in the
speculative-evolution pilot ("How could life survive beneath a frozen alien
ocean?"). This niche is 100% AI stills: every still is an AI-generated
illustration carrying the persistent "Speculative illustration" label.
No footage, no video generation, no text inside images.

## 2. Visual style — field-guide plate

- **Style:** flat-vector field-guide plate, silhouette-first, minimal detail,
  clean geometric lines, no gradients, no shading, no texture, no photographic
  depth, not photorealistic.
- **Subjects:** alien creatures, habitats, anatomy crops, food-web plates,
  planet-surface views — objects only, no people, no real events.
- **Composition:** centered or rule-of-thirds with copy space; no words, no
  letters, no numerals (text-like artifacts are auto-flagged by QC).
- **Aspect:** 1280x720 (16:9) for full-frame plates; 1024x1024 for cards.

## 3. Palette

| Token | Hex | Use |
|---|---|---|
| deep teal | #14455C | background / deep ocean |
| bioluminescent lime | #A8E06F | creature glow, vents, flora |
| basalt charcoal | #3B444B | rock, ice shadows, silhouettes |
| pale bone | #EDE7D8 | highlights, mats, distant ice |

## 4. Anatomy spec rule (mandatory per creature)

Every creature must have a written anatomy spec before it is drawn:

- **limb count:** an integer (e.g. 6 limbs for the vent grazer).
- **2–3 dominant features:** e.g. long neck + spade-like forelimbs; sensory crest + fin rays; peristaltic body + burrowing head.

Plus:
- **Canonical silhouette:** ONE fixed silhouette per creature, reused across all shots of that creature. Poses and detail crops vary, but the silhouette is fixed so the creature is recognizable shot to shot.

Creature anatomy specs (pilot):

| Creature | Limb count | Dominant features | Canonical silhouette role |
|---|---|---|---|
| Vent grazer | 6 | long neck; spade-like forelimbs | grips vent chimneys, grazes bacterial mats |
| Filter drifter | 0 (fins) | undulating fin; wide filter mouth | sieves suspended microbes, neutral buoyancy |
| Ice burrower | 0 (peristaltic) | tapered head; segmented body | peristaltic burrowing through sediment |

## 5. Prompt template

```
{subject}, flat vector illustration, field-guide plate, silhouette-first,
{creature_anatomy}, deep teal #14455C, bioluminescent lime #A8E06F,
basalt charcoal #3B444B, pale bone #EDE7D8, no text, no watermark, no
letters, no numerals, not photorealistic, no people, no logos, --{aspect}
--seed {seed}
```

- `{subject}`: creature/habitat description (no text request).
- `{creature_anatomy}`: filled from the anatomy spec (limb count + features).
- `{aspect}`: 16:9 or 1:1.
- `{seed}`: fixed seed per creature+shot, recorded in the manifest.

## 6. Editorial overlays — drawn in the editor, never by the image model

Labels, scale bars, arrows, maps, and numbers are drawn in the editor
(PIL/ffmpeg overlay), never by the image model. The image model must never
render legible text. Generated images are checked for accidental text-like
artifacts; borderline cases go to human review.

## 7. Label rule — "Speculative illustration" (AI share 100%)

Because this niche is 100% AI stills, every AI cut carries a persistent
"Speculative illustration" label:

- **At start:** the label appears from the first frame of the cut.
- **In description:** the label is carried in the cut description/metadata.
- **Gate:** every cut with generator=AI must have label="Speculative
  illustration" and a non-empty description; AI share is 1.0 (100%).
- Other AI_IMAGE_POLICY.md gates are NOT weakened: no photoreal people,
  no text in the image, no real events, no emblems/insignia, not
  photorealistic.

## 8. Motion variety (editor motion on stills)

Stills are animated in the editor with pan/zoom, detail crops, and parallax:

- Pan/zoom with differing easing (easein / easeout / easeinout).
- Detail crops to show anatomy/silhouette.
- Parallax for depth.
- **Lint:** no two identical moves in a row (motion_variety.lint_variation:
  same move + easing + direction on consecutive segments is flagged).

## 9. Prohibited content (hard rules)

- No photorealistic people, faces, or real individuals.
- No photorealistic fake events presented as real.
- No text, letters, numerals, or legible watermarks inside generated images.
- No real vehicles presented as photos; no emblems, insignia, or flags.
- Anything violating these is quarantined and not used.
