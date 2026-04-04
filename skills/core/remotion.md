# Remotion Skill

## When to Use

Use Remotion for advanced video composition from Phase 3 onward — anywhere that requires
React-based scene assembly, parametric templates, animated overlays, transitions, or
data-driven batch rendering. For simple cuts, burns, and encodes, prefer FFmpeg directly.

## Relationship to Remotion Agent Skills

The **installed agent skills** (`.agents/skills/remotion-best-practices/`) teach correct
Remotion API usage — imports, timing, animation constraints, code patterns.
**This file** teaches how OpenMontage uses Remotion — which compositions map to pipeline
stages, how artifacts flow in, and how renders are triggered.

## Remotion-First Routing

**Remotion is the DEFAULT composition engine for ALL final renders when available.**
It handles video clips (via `<OffthreadVideo>`), still images, animated scenes,
component types, transitions, and mixed content — all in a single React-based
render pass.

FFmpeg is the **fallback** — used only when Remotion is unavailable, or for
simple standalone operations that don't benefit from React rendering.

| Use Case | Backend | Why |
|----------|---------|-----|
| Final video render (any content type) | **Remotion** | Default for all compositions |
| Video clips + animated stills + text cards | **Remotion** | Mixed content in one pass |
| Video-only cuts with transitions | **Remotion** | Native `<OffthreadVideo>` + transitions |
| Animated diagrams/text cards | **Remotion** | Frame-by-frame control |
| Data-driven batch videos | **Remotion** | Zod props + parametric renders |
| Simple trim, concat (no composition) | FFmpeg | Instant, no Node dependency |
| Subtitle burn-in (standalone) | FFmpeg | Proven, fast |
| Face enhance, color grade | FFmpeg | Filter-based, deterministic |
| Remotion unavailable | FFmpeg | Automatic fallback |

**Note:** The `render` operation auto-routes to Remotion by default. FFmpeg is
only selected when Remotion is not installed or the agent explicitly calls
`operation='compose'` for standalone operations. The agent can also write custom
Remotion compositions on the fly via the capability-extension protocol when no
existing composition covers the layout (e.g., custom PiP, split-screen).

## Supported Scene Types (Cut Types)

The Explainer composition supports the following cut types:

| Type | Props Required | Best For |
|------|---------------|----------|
| `text_card` | `text` | Statements, titles, closing messages |
| `stat_card` | `stat`, optional `subtitle`, `accentColor` | Big numbers, impactful metrics |
| `hero_title` | `text`, optional `heroSubtitle` | Opening titles, dramatic reveals |
| `callout` | `text`, optional `title`, `callout_type` (info/warning/tip/quote) | Tips, quotes, important notes |
| `comparison` | `leftLabel`, `rightLabel`, `leftValue`, `rightValue` | Before/after, A/B, versus |
| `bar_chart` | `chartData` [{label, value}], optional `title`, `chartAnimation` | Category comparisons, rankings |
| `line_chart` | `chartSeries` [{label, data: [{x,y}]}], optional `title` | Trends, time series, growth |
| `pie_chart` | `chartData` [{label, value}], optional `donut`, `centerLabel` | Proportions, breakdowns |
| `kpi_grid` | `chartData` [{label, value, prefix, suffix, change, icon}] | Dashboards, traction metrics |
| `progress_bar` | `progress` (0-100), optional `progressSegments` | Journey viz, completion, stacked metrics |
| `anime_scene` | `images` (1-4 paths), optional `animation`, `particles`, `particleColor`, `particleCount`, `particleIntensity`, `vignette`, `lightingFrom`, `lightingTo` | Anime/Ghibli-style scenes with multi-image crossfade, camera motion, particle overlays |

**Chart animations:** `grow-up`, `slide-in`, `pop` (bar), `draw`, `fade-in` (line), `spin`, `expand`, `sequential` (pie), `count-up`, `pop`, `cascade` (kpi)

### Anime Scene — Multi-Image Crossfade + Particles

The `anime_scene` type renders 1-4 images with smooth crossfade transitions, cinematic camera motion, and animated particle overlays. This creates the illusion of animation from still images.

**Camera motion types:** `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `ken-burns`, `drift-up`, `drift-down`, `parallax`, `static`

**Particle types:** `fireflies` (floating golden orbs), `petals` (falling cherry blossoms), `sparkles` (twinkling stars), `mist` (drifting fog layers), `light-rays` (crepuscular rays)

**Key prop:** `sceneDurationSeconds` is automatically passed by `SceneRenderer` — this fixes a critical Remotion pitfall where `useVideoConfig().durationInFrames` returns the full composition duration, not the scene's Sequence duration.

**Multi-image crossfade math:** Each image owns an equal time segment. Fade-out of image N and fade-in of image N+1 OVERLAP by `crossfadeDur` (~1.2s) so there's never a dead frame. Generate 2-3 images per scene from the same visual system, but vary the shot, subject, and lighting per beat. Nearby seeds help create subtle motion without flattening the whole sequence into one repeated prompt.

**Reference composition:** `remotion-composer/public/demo-props/mori-no-seishin.json` — 6 anime scenes, 30 seconds, with particles, lighting, overlays, and ambient music.

**Style playbook:** `styles/anime-ghibli.yaml` — Ghibli-inspired aesthetic with color palette, typography, motion parameters, and FLUX prompt prefix.

**Zero-key video strategy:** When no image or video generation is available, build
entire videos from these component types. A well-composed sequence of hero_title →
kpi_grid → bar_chart → comparison → stat_card → text_card produces a polished,
professional video with zero external dependencies.

### The Proven Formula for Zero-Key Videos

These rules were discovered through systematic render testing and produce cinematic results:

**1. Commit to one background family per video.** Use a coherent background treatment derived from the playbook or custom identity instead of forcing every sequence into the same dark dashboard look.
This prevents jarring white↔dark flash transitions and makes chart colors pop dramatically.
The goal is visual cohesion, not a mandatory dark theme.

**2. Flat props format.** All scene properties go at the TOP LEVEL of the cut object
(e.g., `cut.text`, `cut.chartData`), NOT nested under a `props` key.

**3. KPI Grid data rules:**
- `value` must be a small, human-readable number. The component auto-formats ≥1M→"XM", ≥1K→"XK".
  For "8.1 Billion" use `value: 8.1, suffix: " Billion"`. Never use raw huge numbers with a suffix.
- `change` must be a NUMBER (e.g., `3.2`), not a string (e.g., NOT `"+3.2%"`).

**4. Comparison and Callout theming:**
- `comparison` accepts `backgroundColor` and `color` (text color) for dark themes.
- `callout` accepts `backgroundColor` which sets both the container and card background.

**5. Overlays add polish.**
- `section_title` overlays group scenes narratively ("THE CRISIS", "THE DATA").
- `stat_reveal` overlays float dramatic numbers over chart scenes (e.g., "10x" in corner).

**6. Scene pacing:** 4-6 seconds per scene, 8-10 scenes for a 45-50s video. Give chart
animations at least 4 seconds to complete. Hero title needs only 4 seconds.

**7. Color palette cohesion.** Pick 4-5 accent colors that relate to the topic and use
them consistently across charts, overlays, and accents. Use the same chartColors array
across bar/pie/line scenes for visual unity.

**Reference compositions:** See `remotion-composer/public/demo-props/climate-dashboard.json`
as the gold standard, and other demo files for additional patterns.

### Pre-Render Validation (mandatory)

**Always run `composition_validator` before rendering.** It catches:
- Missing asset files (images, audio) that would cause render failures
- Narration audio longer than video duration (audio gets cut off)
- Music shorter than video (silence at end)
- Invalid cut timings (out ≤ in)

```python
from tools.analysis.composition_validator import CompositionValidator
result = CompositionValidator().execute({
    "composition_path": "path/to/composition.json",
    "assets_root": "remotion-composer/public",
})
# result.data["valid"] must be True before rendering
```

**Audio duration alignment:**
- After generating TTS narration, the tool returns `audio_duration_seconds`.
- If narration exceeds video duration: shorten script and regenerate, OR extend the last scene.
- Use `tools.analysis.audio_probe.probe_duration(path)` to check any audio file's duration.
- Music should be ≥ video duration; the player handles fade-out via `fadeOutSeconds`.

## Architecture

```
remotion-composer/
├── src/
│   ├── Root.tsx              # Composition registry
│   ├── compositions/         # One file per pipeline type
│   │   ├── Explainer.tsx     # Generated explainer composition
│   │   ├── AnimatedScene.tsx # Individual animated scene
│   │   └── TitleCard.tsx     # Standalone title card
│   ├── components/           # Reusable visual building blocks
│   │   ├── Caption.tsx       # Subtitle/caption renderer
│   │   ├── DiagramOverlay.tsx
│   │   ├── ProgressBar.tsx
│   │   └── TransitionWrapper.tsx
│   └── styles/               # Tailwind + playbook-derived styles
├── public/                   # Static assets (fonts, LUTs)
├── package.json
├── remotion.config.ts
└── tsconfig.json
```

## Pipeline Integration

### How Artifacts Map to Remotion Props

| OpenMontage Artifact | Remotion Prop | Maps To |
|---------------------|---------------|---------|
| `scene_plan.json` → `scenes[]` | `scenes` prop | `<TransitionSeries>` children |
| `scene.type` | Component selector | `talking_head` → `<Video>`, `diagram` → `<DiagramOverlay>`, etc. |
| `scene.start_seconds` / `end_seconds` | `from` / `durationInFrames` | `fps * seconds` conversion |
| `scene.transition_in` / `transition_out` | `<TransitionSeries.Transition>` | `fade`, `slide`, `wipe` |
| `asset_manifest.json` → assets | `assets` prop | `staticFile()` or absolute paths |
| `style_playbook` | `theme` prop | Colors, fonts, animation curves |
| `edit_decisions.json` → cuts | `cuts` prop | `<Series>` with trimmed `<Video>` segments |
| `media_profile` | Composition dimensions | `width`, `height`, `fps` from profile |

### Render Invocation

The orchestrator calls Remotion renders via CLI:

```bash
# Standard render (composition name is "Explainer", no entry point needed)
npx remotion render Explainer \
  --props="public/demo-props/my-video.json" \
  --output=output/final.mp4 \
  --codec=h264 --crf=18

# With specific media profile
npx remotion render Explainer \
  --width=1080 --height=1920 --fps=30 \
  --props="public/demo-props/my-video.json" \
  --output=output.mp4
```

**Note:** Do NOT specify `src/index.ts` as entry point — Remotion auto-discovers compositions. The composition name is `Explainer` (not `ExplainerVideo`).

In Python, invoke via `subprocess` from `video_compose.py` when `backend="remotion"`.

### Media Profile Mapping

| OpenMontage Profile | Remotion Config |
|--------------------|-----------------|
| `youtube_landscape` | `width: 1920, height: 1080, fps: 30` |
| `youtube_shorts` | `width: 1080, height: 1920, fps: 30` |
| `tiktok_vertical` | `width: 1080, height: 1920, fps: 30` |
| `instagram_reels` | `width: 1080, height: 1920, fps: 30` |
| `instagram_square` | `width: 1080, height: 1080, fps: 30` |
| `cinematic_wide` | `width: 2560, height: 1080, fps: 24` |

## Key Patterns

### Scene Plan to Composition

Each scene in `scene_plan.json` becomes a child of `<TransitionSeries>`:

```tsx
// Pseudocode — actual component in remotion-composer/src/compositions/Explainer.tsx
const Explainer: React.FC<ExplainerProps> = ({ scenes, theme, assets }) => {
  return (
    <TransitionSeries>
      {scenes.map((scene, i) => (
        <React.Fragment key={scene.id}>
          {scene.transition_in && (
            <TransitionSeries.Transition
              presentation={mapTransition(scene.transition_in)}
              timing={timing({ durationInFrames: 15 })}
            />
          )}
          <TransitionSeries.Sequence durationInFrames={secondsToFrames(scene)}>
            <SceneRenderer scene={scene} theme={theme} assets={assets} />
          </TransitionSeries.Sequence>
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};
```

### Dynamic Duration with calculateMetadata

When TTS audio determines video length (generated explainers), use `calculateMetadata`:

```tsx
export const ExplainerVideo = {
  component: Explainer,
  calculateMetadata: async ({ props }) => {
    const totalDuration = props.scenes.reduce(
      (sum, s) => sum + (s.end_seconds - s.start_seconds), 0
    );
    return {
      durationInFrames: Math.ceil(totalDuration * props.fps),
      fps: props.fps,
      width: props.width,
      height: props.height,
    };
  },
};
```

### Style Playbook to Theme

Style playbooks (`skills/styles/`) define visual parameters. Map them to Remotion themes:

```tsx
// Derived from the style playbook YAML
const cleanProfessional = {
  background: "#FFFFFF",
  text: "#1A1A1A",
  accent: "#2563EB",
  fontFamily: "Inter",
  headingWeight: 600,
  transitionType: "fade",
  transitionDuration: 15, // frames
  animationEasing: "easeInOutCubic",
};
```

### Audio Layering

Narration + background music + SFX as parallel `<Audio>` components.

**Music offset and looping:** The `audio.music` config supports:
- `offsetSeconds` — skip quiet intros, start from the energetic part of the track. Use `tools/analysis/audio_energy.py` to find the optimal offset automatically.
- `loop` — loop the music if it's shorter than the video. Remotion handles this natively.
- `fadeInSeconds` / `fadeOutSeconds` — smooth volume ramps at start/end.

```json
"audio": {
  "music": {
    "src": "project/music.mp3",
    "volume": 0.15,
    "offsetSeconds": 55,
    "loop": false,
    "fadeInSeconds": 2,
    "fadeOutSeconds": 3
  }
}
```

```tsx
<AbsoluteFill>
  <Audio src={narrationUrl} />
  <Audio src={musicUrl} volume={0.06} startFrom={offsetFrames} loop />
  {sfxCues.map(cue => (
    <Sequence key={cue.id} from={secondsToFrames(cue.time)}>
      <Audio src={cue.url} volume={cue.volume} />
    </Sequence>
  ))}
  {/* Visual layers */}
</AbsoluteFill>
```

### Cost Tracking

Remotion renders are CPU-intensive but $0 API cost. Track via cost_tracker:
- `estimate`: based on composition duration × resolution tier
- `reserve`: 0 (no API spend)
- `reconcile`: wall-clock render time for benchmarking

## Critical Constraints

- **No CSS animations or transitions** — they don't render correctly. Use `useCurrentFrame()` + `interpolate()` for all motion.
- **No Tailwind animation classes** — `animate-*` classes break frame-based rendering. Static Tailwind utilities are fine.
- **Always clamp interpolate()** — use `extrapolateLeft: 'clamp', extrapolateRight: 'clamp'` to prevent values shooting past endpoints.
- **`useVideoConfig().durationInFrames` returns COMPOSITION duration, not Sequence duration** — This is the #1 Remotion footgun. If your composition is 31s (930 frames) and a scene's `<Sequence>` is 5s (150 frames), `durationInFrames` still returns 930 inside that scene. Any crossfade, camera motion, or timing logic that uses `durationInFrames` directly will be wildly wrong. **Fix:** Pass `sceneDurationSeconds` as a prop from the parent and compute `effectiveDuration = Math.round(sceneDurationSeconds * fps)` inside the component. The `AnimeScene` component implements this pattern.
- **Node.js 18+ required** — listed as optional in minimum system, required in recommended.
- **Render in series, not parallel** — unless the machine has enough RAM. Each render spawns a Chromium instance.

## Quality Checklist

- [ ] Composition duration matches sum of scene durations minus transition overlaps
- [ ] All `staticFile()` references resolve to existing assets
- [ ] Transitions don't cut off content (account for overlap in timing)
- [ ] Audio layers are in sync with visual scenes
- [ ] Theme colors match the active style playbook
- [ ] Output resolution and FPS match the target media profile
- [ ] Render completes without Chromium timeout errors
- [ ] Final output plays correctly on target platform
