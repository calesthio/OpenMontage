# Sora 2 — Prompting Guide

> Source: [OpenAI Sora 2 Cookbook](https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide)
> For universal vocabulary, see: `skills/creative/video-gen-prompting.md`

**Word count:** Sora 2 plateaus around 100–250 words. Past 250, additional detail rarely improves output.

## Sora-Specific Prompt Template

Sora responds best to a structured format with prose + cinematography block + action beats:

```
[Prose scene description — characters, costumes, scenery, weather, details.
 Be as descriptive as possible to match your vision.]

Cinematography:
Camera shot: [framing and angle]
Lens: [focal length, type]
Lighting: [key, fill, rim, practical sources with color temp]
Mood: [overall tone]

Actions:
- [Beat 1: specific gesture or movement]
- [Beat 2: another distinct beat]
- [Beat 3: reaction or dialogue]

Dialogue:
[Short natural lines, kept brief for clip length]
```

## Advanced Optional Fields

Sora uniquely responds to these production-level details that most models ignore:

| Field | Example |
|-------|---------|
| **Lens spec** | "40mm spherical", "85mm", "Anamorphic 2.0x" |
| **Filtration** | "Black Pro-Mist 1/4", "slight CPL rotation" |
| **Grade / palette** | "Warm Kodak-inspired grade", "teal-and-orange LUT" |
| **Film stock emulation** | "16mm black-and-white", "35mm photochemical contrast" |
| **Diegetic sound** | "faint rail screech, rain patters window, clock ticks" |
| **Wardrobe** | "navy coat, sleeves rolled, suspenders loose" |
| **Finishing** | "fine-grain overlay, mild halation, gate weave, soft vignette" |
| **Shutter** | "180° shutter angle" |
| **Playback speed** | "speed ramp from 1x to 0.25x mid-shot", "stop-motion staccato", "time-reversed exhale" |
| **Lens distortion** | "fisheye barrel distortion at the edges", "subtle barrel curvature on straight lines" |
| **Focus mode** | "rack focus from foreground bottle to background figure", "deep focus, FG to BG sharp" |

## What Sora Does Differently

- **Prose-first**: Write a rich paragraph, then add technical blocks. Don't lead with camera specs.
- **Character references**: Can lock onto up to 2 uploaded character IDs via API.
- **Dialogue sync**: Short lines work. Complex multi-character dialogue does not.
- **Edit commands**: "Same shot, switch to 85mm" or "Same lighting, new palette: teal, sand, rust" — Sora supports iterative refinement on existing generations.
- **Creative freedom**: Shorter prompts → more creative latitude. Longer → more control.

## Color Palette Technique

Name 3-5 anchor colors instead of vague "warm tones":
- "Amber, cream, walnut brown" (vintage warmth)
- "Teal, sand, rust" (coastal desert)
- "Cool blues with warm tungsten accents" (noir)

## Sora API Parameters (cannot be set in prompt)

- `model`: `sora-2` or `sora-2-pro`
- `size`: 720x1280, 1280x720, 1080x1920, 1920x1080, 1024x1792, 1792x1024
- `seconds`: 4, 8, 12, 16, 20

## Example

```
Style: Hand-painted 2D/3D hybrid animation with soft brush textures,
warm tungsten lighting, tactile stop-motion feel. Subtle watercolor wash;
warm-cool balance; filmic motion blur.

Inside a cluttered workshop, shelves overflow with gears and yellowing
blueprints. Small round robot sits on wooden bench, dented body patched
with mismatched plates. Large glowing blue eyes flicker as it fiddles
with a humming light bulb.

Cinematography:
Camera: medium close-up, slow push-in with gentle parallax from hanging tools
Lens: 35mm virtual; shallow depth of field
Lighting: warm key from overhead practical; cool spill from window
Mood: gentle, whimsical, touch of suspense

Actions:
- Robot taps bulb; sparks crackle
- Flinches, dropping bulb, eyes widening
- Bulb tumbles in slow motion; catches it just in time
- Puff of steam escapes chest — relief and pride

Background Sound:
Rain, ticking clock, soft mechanical hum, faint bulb sizzle
```
