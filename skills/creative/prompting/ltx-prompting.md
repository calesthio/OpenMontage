# LTX-2 — Prompting Guide

> Source: [LTX Official Prompting Guide](https://docs.ltx.video/api-documentation/prompting-guide)
> For universal vocabulary, see: `skills/creative/video-gen-prompting.md`

## LTX-Specific 6-Element Structure

LTX-2 uses a clean, focused prompt structure:

1. **Establish the shot** — cinematography terms matching your genre
2. **Set the scene** — lighting, color palette, textures, atmosphere
3. **Describe the action** — natural sequence flowing from beginning to end
4. **Define the character(s)** — physical cues (age, hair, clothes), not abstract labels
5. **Camera movement(s)** — specify how and when; describe what appears AFTER the movement. (LTX honors the translation/rotation/lens distinction: `dolly` ≠ `zoom`, `pan` ≠ `truck`. Pick the right family — translation moves the rig, rotation pivots it, lens-only changes focal length or focal plane without moving the camera.)
6. **Describe the audio** — ambient sound, music, speech, or singing

### Strict-Static-Shot rule

If you write "static camera," the shot must have NO movement, NO focus change, NO zoom. LTX takes "static" literally — adding any motion verb later in the prompt will either be ignored or will produce a glitch where the camera contradicts itself. Pick one: static, OR a single named movement.

## LTX-Specific Tips

### Post-Movement Description
LTX renders camera movements more accurately when you describe the result:
- Instead of: "Camera pans left"
- Write: "Camera pans left to reveal a bustling market square"

### Audio Prompting (Unique to LTX-2)
LTX-2 generates synchronized audio. Use specific descriptors:

| Category | Examples |
|----------|---------|
| **Ambient** | "coffeeshop noise", "wind and rain", "forest with birdsong" |
| **Voice style** | "energetic announcer", "resonant voice with gravitas", "childlike curiosity" |
| **Volume** | "whisper", "mutter", "shout", "scream" |
| **Music** | "soft acoustic guitar", "electronic beat building" |

Dialogue goes in quotes: `The narrator says: "Welcome to the future."`
Specify language/accent: `speaks in British English with a warm tone`

### Style Categories
LTX organizes styles into three families:

**Animation**: stop-motion, 2D animation, 3D animation, claymation, hand-drawn
**Stylized**: comic book, cyberpunk, 8-bit pixel, surreal, minimalist, painterly
**Cinematic**: period drama, film noir, fantasy, thriller, documentary, arthouse

## What to Avoid (LTX-Specific)

| Avoid | Reason |
|-------|--------|
| Internal emotional states ("sad", "confused") | Use visual cues: tears, slumped posture, furrowed brow |
| Readable text and logos | Not reliably rendered |
| Complex physics (explosions, splashing) | Causes artifacts; simple motion is fine |
| Overloaded scenes | Many characters/actions reduces coherence |
| Conflicting lighting descriptions | Pick one setup, commit to it |
| Starting complex | Build up: simple prompt first, add layers |
| Prompts over ~80 words | LTX-2 degrades past that. Pick the most important 5–6 elements. |

## LTX Technical Notes

- **Duration**: ~5-8 seconds per generation
- **Audio**: Generated automatically; describe what you want to hear
- **~30% of outputs have artifacts** — re-run with a different seed
- **Cannot render readable text** — don't include signs or titles
- **Frame count must satisfy** `(n-1) % 8 == 0`: valid counts are 25, 49, 73, 97, 121, 161, 193

## Example

```
A wide establishing shot captures a misty morning harbor.
Weathered fishing boats bob gently, their paint peeling in
patches of red and blue. A grey-haired fisherman in a dark
wool peacoat steps onto the dock, carrying a heavy net over
one shoulder. He pauses, looks out at the fog bank, then
walks toward the nearest boat with steady, deliberate steps.
The camera tracks alongside him at waist height, slowly
pushing in as he reaches the boat and tosses the net aboard.
Soft overcast light with a warm break in the clouds near
the horizon. Ambient sound of water lapping, rope creaking,
and distant foghorn.
```
