# Typography for Video Production

> Sources: School of Motion typography guides, legibility.info video text rules, Wave.video font
> pairing research, EBU/SMPTE broadcast standards, Netflix subtitle spec, BBC subtitle guidelines,
> WCAG 2.1 contrast requirements, Easings.net, postplanify.com safe zone data (2026)

## Quick Reference Card

```
TITLE SIZE:       60-90px at 1080p  |  120-180px at 4K
BODY SIZE:        40-60px at 1080p  |  80-120px at 4K
SUBTITLE SIZE:    42px+ at 1080p    |  3-5% of video height
MAX CHARS/LINE:   32-42 (subtitles) |  30 (overlays)
MAX LINES:        2 (subtitles)     |  3 (overlays)
READING SPEED:    21 chars/sec      |  160-200 WPM
TITLE SAFE:       80% of frame (192px margin at 1080p)
ACTION SAFE:      90% of frame (96px margin at 1080p)
FONT FAMILIES:    1-2 per video maximum
CONTRAST:         4.5:1 minimum, 7:1 optimal
FADE DURATION:    0.3s opacity  |  0.5-1.0s slide/scale
```

## Font Selection

### Recommended Video Fonts

| Category | Fonts | Use For |
|----------|-------|---------|
| **Body / Captions** | Inter, Open Sans, Roboto, Source Sans Pro, Lato, DM Sans | All body text, subtitles, captions |
| **Headlines** | Montserrat Bold, Bebas Neue, Oswald Bold, Poppins Bold | Titles, section headers, key stats |
| **Editorial** | Playfair Display, Roboto Slab | Luxury, cinematic, documentary |
| **System Safe** | Helvetica Neue, Arial, Avenir Next | When custom fonts unavailable |

### Font Pairing Rules

- Limit to **1-2 font families** per video — more creates visual noise
- Pair a **display/bold heading** font with a **neutral body** font
- Size difference between title and body: at least **50% larger**
- **Sans-serif** for motion graphics and captions (holds up in motion)
- **Serif** only for cinematic title cards and editorial content
- **Script/decorative** fonts: hero titles only, never body, never in motion

### Proven Pairings

| Heading | Body | Style |
|---------|------|-------|
| Bebas Neue | Open Sans | High-impact, social ads |
| Montserrat Bold | Lato | Clean modern |
| Oswald Bold | Raleway | Strong contrast |
| Playfair Display | Inter | Editorial |
| Poppins Bold | Poppins Light | Single-family hierarchy |

## Text Sizing

### Minimum Readable Sizes

| Element | 1080p (px) | 4K (px) | Notes |
|---------|-----------|---------|-------|
| Title / Hero text | 60-90 | 120-180 | Must be readable as thumbnail |
| Body text | 40-60 | 80-120 | Absolute minimum for readability |
| Subtitles | 42+ | 84+ | Accessibility requirement |
| Lower third name | 48-60 | 96-120 | Bold weight |
| Lower third role | 36-44 | 72-88 | Light/regular weight |
| Thumbnail text | — | — | Must read at 120-160px wide display |

## Safe Zones

### Broadcast Standard

| Zone | Coverage | Margin at 1080p | Purpose |
|------|----------|----------------|---------|
| **Title Safe** | 80% of frame | 192px H, 108px V | All text must stay within |
| **Action Safe** | 90% of frame | 96px H, 54px V | All important content |

At 1920x1080: Title Safe = inner **1536x864px**
At 3840x2160: Title Safe = inner **3072x1728px**

### Platform-Specific Safe Zones (Vertical 1080x1920)

| Platform | Safe Zone | Top Dead | Bottom Dead | Right Dead |
|----------|-----------|----------|-------------|------------|
| **TikTok** | 900x1492 | 108px | 320px | 120px |
| **Instagram Reels** | 996x1400 | 210px | 310px | 84px |
| **YouTube Shorts** | 984x1500 | 120px | 300px | 96px |
| **Facebook Reels** | 1080x1520 | 100px | 300px | 60px |
| **Instagram Stories** | 1080x1620 | 100px | 200px | — |

**Universal cross-platform safe zone: 900x1400px centered** — works on all platforms.

## Text Animation Timing

### Duration on Screen

- Reading speed: **13 characters per second** minimum dwell time
- 30-character line: minimum **2.3 seconds**
- General rule: **3 seconds per 63 characters**
- Title cards: **3-6 seconds**
- After animation completes, hold motionless for **1 second per 13 characters**

### Animation Durations

| Animation Type | Duration | Use Case |
|---------------|----------|----------|
| Fade in/out | 0.3-0.5s | Subtle, universal |
| Slide / scale entrance | 0.5-1.0s | Standard motion graphics |
| Kinetic text entrance | 1.0-2.0s | Bold, energetic |
| Lower third entrance | 1.0-2.0s | Speaker identification |
| Lower third exit | 0.5-1.0s | Quick departure |

### Easing Curves

| Easing | Cubic Bezier | Use For |
|--------|-------------|---------|
| **easeOutCubic** | `(0.33, 1, 0.68, 1)` | Text entrances (decelerates into place) — **default choice** |
| **easeOutQuart** | `(0.25, 1, 0.5, 1)` | Snappier entrance, kinetic type |
| **easeInOutQuad** | `(0.45, 0, 0.55, 1)` | Smooth position transitions |
| **easeInOutCubic** | `(0.65, 0, 0.35, 1)` | Scale and opacity changes |
| **easeInCubic** | `(0.32, 0, 0.67, 0)` | Exits (accelerates out) |

**Never use linear easing** for text animations — it feels robotic.

### Reveal Techniques

| Technique | Feel | Best For |
|-----------|------|----------|
| Mask reveal | Cinematic | Title cards, premium content |
| Scale pop | Energetic | Social media, short-form |
| Character stagger | Natural flow | Kinetic typography |
| Word-by-word sync | Engaging | Talking-head captions, TikTok |
| Fade | Subtle | Professional, corporate |

## Subtitle & Caption Typography

### Specifications

| Parameter | Value | Source |
|-----------|-------|--------|
| Font size | 42px+ at 1080p | Accessibility standard |
| Max characters per line | 32-42 | Platform dependent (see below) |
| Max lines | 2 per block | Universal standard |
| Line spacing | 1.3x | Readability standard |
| Background | Semi-transparent black, 70-80% opacity | Contrast requirement |
| Alternative style | White text + 2-4px dark stroke | No-box style |
| Minimum contrast | 4.5:1 (white on black = 21:1) | WCAG AA |
| Bottom margin | 60px from edge minimum | Mobile gesture clearance |
| Within frame width | 90% maximum | Title safe compliance |

### Character Limits by Platform

| Platform | Max Chars/Line |
|----------|---------------|
| YouTube | 42 |
| Netflix | 42 |
| BBC | 37 |
| TV broadcast | 37-42 |
| Cinema | 40-45 |

### Caption Timing

| Parameter | Value |
|-----------|-------|
| Minimum duration | 1 second |
| Maximum duration | 6-7 seconds |
| Reading speed | 21 characters/second |
| Fade-in transition | 0.3 seconds |
| Gap between captions | 2 frames |
| Sync tolerance | 3 frames of audio |

### Reading Speed by Platform

| Platform | WPM |
|----------|-----|
| TikTok / Instagram Reels | 180-200 |
| YouTube | 160-180 |
| LinkedIn | 140-160 |
| Educational content | 120-140 |

## Lower Thirds

### Standard Specs (1080p)

- Overlay region: **1920x360px** (bottom third)
- Sans-serif fonts (Helvetica, Open Sans, Roboto)
- White text with drop shadow or semi-transparent background bar
- Name: bold, larger weight
- Role/subtitle: lighter weight, smaller

### Timing

| Phase | Duration |
|-------|----------|
| Entrance animation | 1-2 seconds |
| Display | 3-6 seconds |
| Exit animation | 0.5-1 second |

## Contrast & Readability

### WCAG Requirements

| Element | Min Ratio | Standard |
|---------|----------|----------|
| Body text | 4.5:1 | WCAG AA |
| Large text (>18pt) | 3:1 | WCAG AA |
| Enhanced body | 7:1 | WCAG AAA |
| UI components | 3:1 | WCAG 2.1 |

### Text-Over-Video Techniques

1. **Semi-transparent box** — 70-80% black opacity behind text (most reliable)
2. **Text stroke** — 2-4px dark outline around light text
3. **Drop shadow** — subtle shadow for depth (less reliable on busy backgrounds)
4. **Darkened region** — gradient overlay behind text area
5. **Full-screen overlay** — 30-50% dark overlay for text-heavy screens

## Applying to Balamonis Studio

When generating text for video in the compose/asset stages:

1. **Font selection** — use the recommended video fonts above; prefer Inter or Open Sans for body, Montserrat Bold for titles
2. **Size check** — never go below 40px at 1080p for any text element
3. **Safe zones** — all text within 80% title-safe area; for vertical/short-form, use the 900x1400px universal safe zone
4. **Subtitle styling** — 42px+, max 2 lines, max 42 chars/line, semi-transparent background at 75% opacity
5. **Animation** — use easeOutCubic for entrances, hold text for at least 1 second per 13 characters after animation
6. **Contrast** — verify 4.5:1 minimum on a representative graded frame; prefer white-on-dark-background (21:1)
7. **Platform targeting** — check the platform safe zone table above and adjust text placement accordingly
8. **Remotion rendering** — all font families must be loaded via `@import` or `fontFamily` in the component; test that fonts render in the Docker/Lambda environment
