# Color Grading for Video Production

> Sources: BBC Academy color standards, Filmmaker IQ color science series, DaVinci Resolve
> color theory (Blackmagic documentation), WCAG 2.1 contrast guidelines, FFmpeg filter
> documentation, Adobe color accessibility research, Wong (2011) colorblind-safe palette

## Quick Reference Card

```
PROFILES:       cinematic_warm | cinematic_cool | moody_dark | bright_clean | vintage_film | high_contrast | neutral
LUT FORMAT:     .cube (3D LUT) — industry standard, FFmpeg lut3d filter
INTENSITY:      0.6-0.85 for subtle grades, 1.0 for full effect
SKIN TONE:      Vectorscope should fall on the "skin tone line" (~123° on I-line)
COLOR SPACE:    BT.709 for web delivery, BT.2020 for HDR only
BIT DEPTH:      Grade in 10-bit when possible, deliver in 8-bit for web
```

## FFmpeg Filter Reference

The `color_grade` tool uses these FFmpeg filters. Understanding them helps you craft `custom_vf` chains.

### Core Filters

| Filter | Purpose | Key Parameters |
|--------|---------|----------------|
| `eq` | Brightness, contrast, saturation, gamma | `contrast=1.0:saturation=1.0:brightness=0.0:gamma=1.0` |
| `colorbalance` | RGB adjustments in shadows/mids/highlights | `rs/gs/bs` (shadows), `rm/gm/bm` (mids), `rh/gh/bh` (highlights) — range -1.0 to 1.0 |
| `curves` | Tone curves per channel | `all='0/0 0.5/0.5 1/1'` or per-channel `red=`, `green=`, `blue=` |
| `colortemperature` | White balance shift | `temperature=6500` (neutral) — lower = cooler, higher = warmer |
| `lut3d` | Apply external .cube LUT | `lut3d='path/to/file.cube'` |
| `hue` | Hue rotation and saturation | `h=0:s=1` — h in degrees, s as multiplier |
| `normalize` | Auto-stretch histogram to full range | `blackpt=black:whitept=white:smoothing=0` |

### Filter Chain Order

Apply filters in this order for predictable results:

```
1. normalize          (auto-levels if source is flat/log)
2. colortemperature   (white balance correction)
3. colorbalance       (shadow/mid/highlight color shifts)
4. curves             (contrast and tone shaping)
5. eq                 (final contrast/saturation/brightness tweak)
6. lut3d              (creative LUT — applied LAST, on corrected footage)
```

## Profile Selection by Content Type

| Content Type | Recommended Profile | Intensity | Why |
|-------------|-------------------|-----------|-----|
| Corporate / SaaS explainer | `bright_clean` | 0.8 | Clean, professional, approachable |
| Science / educational | `neutral` | 1.0 | Accurate color representation matters |
| Storytelling / narrative | `cinematic_warm` | 0.85 | Warmth builds emotional connection |
| Tech / dark theme | `cinematic_cool` | 0.7 | Complements dark UI screenshots |
| Drama / serious topic | `moody_dark` | 0.6-0.7 | Atmosphere without crushing detail |
| Lifestyle / social media | `high_contrast` | 0.8 | Punchy, attention-grabbing on mobile |
| Retro / nostalgic | `vintage_film` | 0.7 | Subtle faded look, not overdone |

## Mood-Specific Parameter Recipes

When the built-in profiles don't match, use these as starting points for `custom_vf`:

### Warm / Inviting
```
colorbalance=rs=0.06:gs=0.02:bs=-0.04:rh=0.05:gh=0.01:bh=-0.03,
eq=contrast=1.05:saturation=1.08:brightness=0.01
```

### Cool / Technical
```
colorbalance=rs=-0.03:gs=-0.01:bs=0.06:rh=-0.02:gh=0.01:bh=0.04,
eq=contrast=1.06:saturation=0.95
```

### High Energy
```
curves=all='0/0 0.15/0.08 0.5/0.52 0.85/0.92 1/1',
eq=contrast=1.15:saturation=1.2
```

### Subdued / Serious
```
curves=all='0/0.04 0.25/0.22 0.5/0.47 0.75/0.73 1/0.94',
eq=contrast=1.03:saturation=0.75:brightness=-0.02
```

## LUT Workflow

### When to Use LUTs
- Matching footage across different cameras/sources
- Applying a specific film stock emulation
- Maintaining brand consistency across multiple videos
- Converting from LOG/flat camera profiles to display color

### LUT Application Best Practices
1. **Always correct before grading** — normalize/white-balance the footage first, then apply creative LUT
2. **Use intensity < 1.0** — a LUT at full strength usually looks overdone; 0.6-0.8 is typical
3. **Test on skin tones first** — if people appear in the video, skin must look natural
4. **One LUT per project** — switching LUTs between scenes creates visual inconsistency
5. **LUT file location** — store in `assets/luts/` relative to the project, reference with `lut_path`

### FFmpeg LUT Application
```bash
# Apply LUT at 70% intensity (blend with original)
ffmpeg -i input.mp4 -vf "split[a][b];[b]lut3d='my_lut.cube'[graded];[a][graded]blend=all_mode=normal:all_opacity=0.7" output.mp4
```

## Skin Tone Protection

Skin tones are the most critical element in color grading — viewers instantly notice unnatural skin.

**The Skin Tone Line:**
- On a vectorscope, healthy skin (all ethnicities) falls on a narrow line at approximately 123 degrees (between red and yellow)
- If your grade pushes skin away from this line, reduce saturation or adjust hue

**Rules:**
- Never push saturation above 1.2 on footage with people
- After grading, check a frame with visible skin — if it looks orange, green, or magenta, pull back
- The `cinematic_warm` profile at intensity 0.85 is pre-tuned to keep skin natural
- For `moody_dark`, keep intensity at 0.6-0.7 to avoid making skin look grey

## Accessibility

### Colorblind-Safe Design (Wong Palette)

When generating graphics, overlays, or diagrams that accompany graded video, use this palette verified safe for all common types of color vision deficiency:

| Color | Hex | Use For |
|-------|-----|---------|
| Black | `#000000` | Text, outlines |
| Orange | `#E69F00` | Primary accent |
| Sky Blue | `#56B4E9` | Secondary accent |
| Bluish Green | `#009E73` | Positive/success |
| Yellow | `#F0E442` | Highlight/warning |
| Blue | `#0072B2` | Links, info |
| Vermillion | `#D55E00` | Error/danger |
| Reddish Purple | `#CC79A7` | Tertiary accent |

### WCAG Contrast Requirements

| Element | Minimum Ratio | Standard |
|---------|--------------|----------|
| Body text on background | 4.5:1 | WCAG AA |
| Large text (>18pt) on background | 3:1 | WCAG AA |
| Body text (enhanced) | 7:1 | WCAG AAA |
| UI components / graphical objects | 3:1 | WCAG 2.1 |

**Practical rule:** After color grading, any text overlays or subtitles burned into the video must still meet 4.5:1 contrast against the graded background. Test with a contrast checker on a representative frame.

## Applying to Balamonis Studio

When using the `color_grade` tool:

1. **Select profile by content type** using the table above — don't default to `cinematic_warm` for everything
2. **Set intensity to 0.8** as a starting point, not 1.0 — subtlety reads better on mobile screens
3. **Test on a single frame first** before grading the full video — saves render time
4. **Grade after face enhancement** — the enhancement chain order in `skills/creative/enhancement-strategy.md` is: subtitle → face → color → audio → final
5. **Use the same profile across all clips in a video** — visual consistency is critical
6. **For generated visuals** (image_selector, math_animate), apply a lighter grade (0.5-0.6) since they're already stylized
7. **Use the Wong palette** for any generated graphics (diagrams, code snippets, overlays) to ensure colorblind accessibility
8. **For custom grades**, follow the filter chain order above and keep parameter changes small — ±0.05 per adjustment, then review
