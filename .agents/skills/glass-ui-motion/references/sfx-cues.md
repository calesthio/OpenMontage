# SFX cues for UI assembly

Deriving, generating, and placing sound effects for product-motion scenes.
Primary path is **in-composition `<Audio>`** — cues are frame-accurate to the
computed settle frames, which post-mix `start_seconds` can never guarantee.

## Cue taxonomy — element class → sound

| Element class | Cue | sfx_gen prompt sketch | Length |
|---|---|---|---|
| Glass panel / container | low soft whoosh + settle | "soft airy whoosh into a gentle low thump, smooth, subtle" | 0.8–1.2s |
| Form field / card / row | glass tick | "single soft glass tick, short, clean, high and quiet" | 0.5s |
| Button press (focus beat) | tactile click | "satisfying soft tactile click, plastic-glass, single" | 0.5s |
| Toggle / checkbox | snap | "tiny crisp snap, single, bright but quiet" | 0.5s |
| Chart draw / count-up | rising shimmer | "soft rising shimmer sweep, airy, 1 second, gentle" | 0.8–1.5s |
| Success / completion | warm pop | "warm rounded pop with a faint bell tail, single, pleasant" | 0.6–1s |

Rules of thumb: generate **one sound per element class and reuse it** across
the video (consistency reads as design; variety reads as chaos). 4–6 distinct
SFX assets covers a whole video.

## Derivation rules (edit stage)

From each scene's assembly beats (scene_plan) and computed settle frames:

1. Container settle → whoosh cue.
2. Each staggered sibling group: cue the **first and last** sibling's settle,
   not every one — a tick per field in an 8-field form is a typewriter, not a
   product film. Exception: ≤3 siblings may each cue.
3. The focus beat always cues (click/snap).
4. **Density cap: ~1 cue per 0.7s** per scene. Over cap, drop cues in this
   order: middle siblings → chart shimmer → container whoosh. Never drop the
   focus beat.
5. No cue in the first 12 frames of the video (it lands before the viewer is
   oriented) and none inside the final hold.

## Generation (assets stage)

```python
registry._tools["sfx_gen"].execute({
    "prompt": "single soft glass tick, short, clean, high and quiet",
    "duration_seconds": 0.5,
    "prompt_influence": 0.6,   # cue sounds want adherence; textures can go lower
    "output_path": "projects/<id>/assets/audio/sfx_tick.mp3",
})
```

Register each in the asset_manifest as `type: "sfx"` with the generation
prompt. Listen to each effect once before wiring cues — a harsh or long SFX
poisons every cue that reuses it.

## Cue sheet → composition

The edit director writes the cue sheet into the atelier `props.json`:

```json
{
  "sfx_cues": [
    {"scene_id": "form-assembly", "element": "panel", "frame": 18, "asset_id": "sfx_whoosh", "volume": 0.4},
    {"scene_id": "form-assembly", "element": "field-email", "frame": 42, "asset_id": "sfx_tick", "volume": 0.3},
    {"scene_id": "form-assembly", "element": "submit-press", "frame": 96, "asset_id": "sfx_click", "volume": 0.45}
  ]
}
```

Scene components render cues generically:

```tsx
{cues.filter(c => c.scene_id === id).map(c => (
  <Sequence key={`${c.element}-${c.frame}`} from={c.frame} durationInFrames={60}>
    <Audio src={staticFile(`audio/${c.asset_id}.mp3`)} volume={c.volume} />
  </Sequence>
))}
```

## Gain discipline

- Cue volumes 0.3–0.45; the container whoosh may reach 0.5. SFX support the
  narration, they never compete with it.
- Narration + music are mixed in post by `audio_mixer` with loudnorm over the
  **whole** mix — hot in-composition SFX will pump the normalization. When in
  doubt, quieter.
- Fallback: if a run post-mixes SFX instead (no atelier composition), the same
  cue sheet maps to `edit_decisions.audio.sfx[]` (`asset_id`, `start_seconds =
  frame/fps`, `volume`) and `audio_mixer`'s `sfx` track role handles it.
