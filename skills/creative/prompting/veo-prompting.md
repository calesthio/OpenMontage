# VEO 3.1 / VEO 3 — Prompting Guide

> Source: [Vertex AI Video Gen Prompt Guide](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide)
> For universal vocabulary, see: `skills/creative/video-gen-prompting.md`

**Word count:** VEO 3.1 sweet spot is 100–250 words; longer prompts stop helping.

## VEO-Specific 14-Component Structure

VEO responds to the most comprehensive prompt structure of any model:

1. **Subject** — who/what the action revolves around
2. **Action** — movements, interactions, expressions
3. **Scene / Context** — location, time, weather, period
4. **Camera Angles** — shot type and perspective
5. **Camera Movements** — dynamic motion
6. **Lens / Optical Effects** — how the camera "sees"
7. **Lighting** — source, direction, quality
8. **Tone / Mood** — emotional register
9. **Artistic Style** — photorealistic, cinematic, animation, art movement
10. **Ambiance** — color palettes, atmospheric effects, textures
11. **Temporal Elements** — pacing, time flow, rhythm
12. **Audio** — sound effects, ambient, dialogue (VEO 3 generates dialogue)
13. **Cinematic Terms** — editing techniques (match cut, montage, split diopter)
14. **Negative Prompt** — what to exclude

## VEO-Specific Strengths

- **Dialogue generation**: VEO 3 natively generates character speech. Write dialogue naturally.
- **Audio integration**: Ambient sound, music, and voice are generated together with video.
- **Negative prompts**: Explicitly supported — "no text overlays, no watermarks, no lens flare"
- **Editing vocabulary**: Understands "match cut", "jump cut", "montage", "split diopter" as prompt terms.

### Camera vocabulary VEO honors literally

VEO 3.1 distinguishes the three camera-motion families and treats their tokens as separate primitives. Mixing them up (e.g. asking for a "zoom" when you mean a "dolly") will produce the wrong move.

- **Translation (rig physically moves):** `dolly` (in/out along the lens axis), `truck` (left/right laterally), `pedestal` (up/down vertically)
- **Rotation (rig stays put, camera rotates):** `pan` (yaw, left/right), `tilt` (pitch, up/down), `roll` (Dutch / Z-axis)
- **Lens-only (rig and body don't move):** `zoom` (focal length change), `rack focus` / `pull focus` / `focus tracking` (focal-plane change)

dolly ≠ zoom; pan ≠ truck. VEO follows whichever token leads.

## VEO Lens Effects (Unique)

VEO specifically responds to optical effects most models ignore:

| Effect | Prompt Language |
|--------|----------------|
| **Rack focus** | "rack focus from foreground flower to background figure" (snap shift) |
| **Pull focus** | "slow pull focus from the candle in the foreground to the doorway behind" (gradual, slower than rack) |
| **Focus tracking** | "focus tracks the runner as she crosses frame; background stays soft" (focus follows a moving subject) |
| **Dolly zoom (vertigo)** | "vertigo effect as character realizes the truth" |
| **Fisheye** | "fisheye lens distortion, skatepark POV" |
| **Anamorphic lens flare** | "anamorphic lens flare streaking horizontally from setting sun" |

These three focus modes (rack, pull, tracking) are different — VEO 3.1 honors the distinction per the paper.

## VEO Art Movement References

VEO responds well to specific art movements as style anchors:
- "Van Gogh-inspired swirling sky"
- "Surrealist Dalí-esque melting landscape"
- "Art Deco geometric patterns in the architecture"
- "Bauhaus clean lines and primary colors"
- "Gritty graphic novel illustration style"
- "Chinese ink wash painting animation"

## Subtitle Prevention

VEO may add subtitles by default for dialogue. To prevent:
- Add to negative prompt: "no subtitles, no captions, no text overlays"

## Example

```
Subject: A lone astronaut in a weathered white spacesuit
Action: Slowly turns to face the camera, visor reflecting a dying star
Scene: Surface of a barren moon, cracked grey terrain, massive ringed
       planet filling the horizon
Camera: Low-angle medium shot, slow arc around subject
Lens: Wide-angle, deep focus keeping both astronaut and planet sharp
Lighting: Harsh rim light from the star behind, cool blue fill from
          planet reflection, no atmosphere diffusion
Mood: Awe, isolation, quiet grandeur
Style: Photorealistic sci-fi cinematography, IMAX-scale
Audio: Breathing inside helmet, faint radio static, low rumble
Negative: No text, no HUD overlay, no lens flare
```
