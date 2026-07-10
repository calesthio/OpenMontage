# Screen Recording Pipeline

> Sources: OBS Studio documentation, Loom production guidelines, Fireship production
> methodology, Kevin Powell CSS tutorial techniques, Theo Browne dev content guides

## Quick Reference Card

```
RESOLUTION:       1920x1080 at 2x display (record at 3840x2160, deliver at 1080p)
FRAME RATE:       60fps for UI/scrolling, 30fps for static code
CURSOR:           Enlarged (1.5-2x), highlighted with ring or glow
ZOOM:             1.5-2x for code focus, 0.8s ease-in-out transition
SPEED RAMP:       1.5x for navigation, 2x for repetitive actions, 1.0x for key moments
DEAD AIR:         Remove pauses > 1.5 seconds
FONT SIZE (IDE):  18-22px minimum for readability at 1080p delivery
```

## Recording Settings

### Resolution Strategy

| Approach | Record At | Deliver At | Why |
|----------|----------|-----------|-----|
| **Recommended** | 3840x2160 (4K) | 1920x1080 | Enables 2x zoom into code without quality loss |
| Budget | 1920x1080 | 1920x1080 | Direct capture, limited zoom headroom |
| Vertical | 2160x3840 | 1080x1920 | Short-form screen recording |

### Frame Rate

| Content Type | FPS | Why |
|-------------|-----|-----|
| Code editing (mostly static) | 30 | Smaller file size, no visible difference |
| UI interaction, scrolling | 60 | Smooth scrolling and cursor movement |
| Animation/demo with motion | 60 | Motion clarity |
| Terminal output | 30 | Text updates don't need 60fps |

### IDE/Editor Setup

- **Font size:** 18-22px minimum (must be readable at 1080p delivery)
- **Theme:** Dark theme preferred (easier on eyes, looks better in video)
- **Line numbers:** ON (helps viewers follow along)
- **Minimap:** OFF (wastes screen space, distracting)
- **Sidebar:** Collapsed unless showing file structure is the point
- **Status bar:** Consider hiding (clutters bottom of frame)
- **Zoom level:** 150-175% for readability

## Cursor Management

### Visibility

| Setting | Value |
|---------|-------|
| Cursor size | 1.5-2x default system size |
| Highlight | Yellow or white ring/glow (50px radius) |
| Click indicator | Brief flash or ripple on click |
| Smoothing | Light smoothing to reduce jitter |

### Cursor Behavior

- **Move deliberately** — no random wandering
- **Pause on target** for 0.5s before clicking
- **Avoid circling** — don't circle the cursor around what you're talking about
- **Hide cursor** when it's not needed (during code explanation)

## Zoom and Pan

### Zoom Levels

| Context | Zoom | Duration of Transition |
|---------|------|----------------------|
| Full screen overview | 1.0x (100%) | — |
| Code focus | 1.5-2.0x | 0.8s ease-in-out |
| Terminal focus | 1.5x | 0.6s ease-in-out |
| UI element highlight | 2.0-2.5x | 0.8s ease-in-out |
| Return to overview | 1.0x | 0.6s ease-in-out |

### Pan Rules

- Pan to follow the active area — don't make viewers search
- Smooth pan (ease-in-out), not instant jump
- Hold position for at least **3 seconds** before next pan
- Announce what you're zooming into: "Let's look at this function..."

## Post-Processing

### Speed Ramping

| Action | Speed | Notes |
|--------|-------|-------|
| Typing boilerplate | 2-3x | Viewers don't need to watch you type imports |
| File navigation | 1.5-2x | Opening files, switching tabs |
| Package install / build | 2-4x or cut | Show start + end, skip the wait |
| Key code writing | 1.0x | Important moments at real speed |
| Debugging / thinking | 1.0x with cuts | Remove dead pauses, keep the reasoning |

### Dead Air Removal

- Remove **all pauses > 1.5 seconds** unless deliberate
- Remove "um", "uh", typing mistakes and backspaces (when possible)
- Jump cuts are acceptable and expected in screen recording content
- Add a subtle **zoom shift** (1.0x → 1.02x) at each jump cut to mask the edit

### Audio Enhancement

- Apply `clean_speech` preset from `audio_enhance`
- HPF at 80Hz to remove keyboard/desk rumble
- Compress at 3:1 to even out speaking volume
- Target -16 LUFS for screen recording content (slightly quieter than -14, more comfortable for long viewing)

## Applying to Balamonis Studio

When processing screen recordings in the talking-head pipeline:

1. **Record at 4K** if possible — enables quality zoom in post
2. **Set IDE font to 20px+** before recording
3. **Use `scene_detect`** with threshold 30, min_scene_length 2.0s to find natural segments
4. **Apply zoom/pan** in compose stage — 1.5-2x on code, 0.8s transitions
5. **Speed ramp navigation** to 1.5-2x, keep key moments at 1.0x
6. **Remove dead air** > 1.5s with `video_trimmer`
7. **Add cursor highlight** in post if not captured in recording
8. **Target -16 LUFS** (slightly below YouTube standard for comfortable viewing)
9. **Subtitles recommended** — use `subtitle_gen` for accessibility
10. **Dark theme** looks best in video — recommend to users before recording
