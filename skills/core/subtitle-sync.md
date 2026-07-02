# Subtitle Sync Skill

## When to Use

Use the `subtitle_gen` tool to convert transcript data (from `transcriber`)
into properly timed subtitle files. This skill covers timing strategy,
formatting, and readability for both vertical and horizontal video.

## Tool

| Tool | Capability |
|------|-----------|
| `subtitle_gen` | Generate SRT, VTT, or caption JSON from word-level timestamps |

## Output Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| SRT | `.srt` | Universal — works with FFmpeg, players, YouTube upload |
| VTT | `.vtt` | Web-native — HTML5 video, browser playback |
| Caption JSON | `.caption.json` | Programmatic — word-level data for custom renderers |

## Cue Length by Format

### Vertical Short-form (TikTok, Reels, Shorts)

- **Max 3-4 words per cue** — screen is narrow, text must be large enough to read
- **Max 20 characters per line** — prevents wrapping on narrow screens
- Subtitles are **mandatory** (most viewers watch muted)

### Horizontal Standard (YouTube, web)

- **Max 6-8 words per cue** — wider screen accommodates more text
- **Max 42 characters per line** — standard broadcast limit

### General Rules

- Average viewer reads ~15 characters/second
- Minimum display time: 0.5 seconds per cue
- Maximum display time: 5 seconds per cue

## Styling for Burn-in (ASS force_style)

When burning subtitles via `video_compose`, these parameters are passed as ASS
`force_style`. Use the correct ASS color format: `&HAABBGGRR` (not hex RGB).

### Vertical Video (1080x1920)

```
font: Arial
font_size: 18
bold: true
primary_color: &H00FFFFFF      # white (ASS format: alpha=00, BGR=FFFFFF)
outline_color: &H00000000      # black
outline_width: 3               # thick outline for readability on varied backgrounds
shadow: 2
margin_v: 50                   # pixels from bottom edge
alignment: 2                   # bottom center
```

### Horizontal Video (1920x1080)

```
font: Arial
font_size: 22
bold: true
primary_color: &H00FFFFFF
outline_color: &H00000000
outline_width: 2
shadow: 1
margin_v: 40
alignment: 2
```

### Common Mistakes

- **Wrong color format:** `&HFFFFFF` breaks positioning. Always use full 8-char `&H00FFFFFF`.
- **Font too large on vertical:** `font_size: 28` fills the center of a 9:16 frame. Use 18 max.
- **Too many words per cue on vertical:** 5+ words creates multi-line blocks that cover the face.
- **MarginV too large:** Values over 200 push text off-screen. Stay under 100 for most cases.

## Timing Best Practices

### Alignment with Speech

- Cue start must match word onset (not before the speaker starts)
- Cue end should extend ~200ms past the last word for comfortable reading
- Never let a cue linger into the next speaker's turn

### Word Boundary Grouping

The `subtitle_gen` tool groups words respecting `max_words_per_cue` and
`max_chars_per_line`. When word timestamps are unavailable, it falls back
to segment-level timing with even distribution.

When using `remotion_caption_burn` with Chinese TTS providers that may emit
character-level timestamps, pass `protected_terms` for product names, skill
names, acronyms, and other phrases that should stay intact. The Remotion caption
burner also protects common terms and Chinese phrases found inside `「...」` or
`『...』` in the source segment text, so names such as `系统提交发布助手` are not
split across caption tokens.

## Quality Checklist

- [ ] Every spoken word appears in a subtitle cue
- [ ] No cue exceeds the character limit for the target format
- [ ] Subtitles are in the bottom 20% of frame — never covering the face
- [ ] Text is readable on mobile at native resolution
- [ ] Timing matches speech — no early or late cues
- [ ] Cues don't overlap each other
- [ ] Outline/shadow provides sufficient contrast against all backgrounds
