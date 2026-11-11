# Agent Guide — Preflight, Capabilities and Tools

Part of [`AGENT_GUIDE.md`](../../AGENT_GUIDE.md), which states every rule in brief and says when to read this.
**Read this in full before running preflight, presenting the capability menu, choosing tools, or planning anything whose promise depends on motion.**

## Mandatory Preflight

Do this before any creative work. **Use `provider_menu_summary()` first — it's the human-ready rollup.** The raw `support_envelope()` dump is a firehose (megabytes of JSON on a well-configured machine); pasting it into chat will bury the user.

```bash
python -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(compact=True), indent=2))
"
```

The summary returns these fields the agent should translate into plain language:

- `composition_runtimes` — booleans for `ffmpeg`, `remotion`, `hyperframes`. This is the source of truth for the "Present Both Composition Runtimes (HARD RULE)" check.
- `capabilities[]` — one entry per capability family with `configured / total` counts and provider lists. Ready-made for the "N of M configured" menu.
- `setup_groups[]` — one entry per credential (`env_vars`), with how many unavailable tools it `unlocks` per capability and the `install_instructions`. Already grouped and ordered by impact: lead with these when offering upgrades ("FAL_KEY unlocks 17 providers").
- `other_setup[]` — unavailable tools that are not a plain env-var fix (local server, install), with a short hint. Call `provider_menu_summary()` without `compact` when you need a tool's full structured `setup_offers[]` entry.
- `runtime_warnings[]` — specific signals like "hyperframes: npm package not resolvable". Surface these to the user verbatim — they're the kind of silent-failure bugs that break the governance contract.

Then, for deeper inspection (only when the summary isn't enough):

```bash
# Full menu — grouped available/unavailable per capability.
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"

# Raw envelope — every tool's full contract. Slow/firehose; use for debugging only.
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
```

Then:

1. Read the selected manifest in `pipeline_defs/`.
2. For each stage, pass `get_stage_tools(manifest, stage)` to
   `registry.capability_coverage(...)`; this includes optional selectors whose
   concrete providers would otherwise be invisible to a required-tools-only check.
3. Report every family from `registry.uncovered_capabilities(...)`. Treat it as
   `degraded` when the treatment can proceed without that family, or `blocked`
   when the approved delivery promise depends on it (especially motion, voice,
   avatar, or music).
4. Check every `required_tools` entry and its `fallback_tools` against the registry.
5. Report one of: `passed`, `degraded`, or `blocked`.
6. Do not start production until the user understands the real capability envelope.

### Provider Menu (Mandatory at Preflight)

Already fetched via `provider_menu_summary()` above. Read that output and **present it to the user as a capability menu**, not as a flat tool list. Use `provider_menu()` directly only when you need the per-tool detail the summary collapses.

**How to present:**

```
YOUR CAPABILITIES

  Video Generation:  0/13 configured
  Image Generation:  1/7 configured
  Text-to-Speech:    1/3 configured
  Music Generation:  1/1 configured
  Composition:       3/3 configured (FFmpeg, video_stitch, video_trimmer)

  You can produce videos now with images + TTS + FFmpeg.
  Quick upgrades available — see below.
```

For EACH capability with unavailable providers, read the `install_instructions` field from the menu output and present setup options grouped by effort:

```
QUICK SETUP OPTIONS (1-minute each — set an env var in .env)

  Video Generation (0/13 -> unlock the biggest upgrade):
    Each unavailable provider lists its own install_instructions.
    Read them from the provider_menu output and present grouped by env var.
    Example: if 3 tools need FAL_KEY, group them: "FAL_KEY unlocks 3 providers"

  Image Generation (1/7 -> more style options):
    Same pattern — read install_instructions from each unavailable tool.

  Text-to-Speech (1/3):
    Same pattern.

LOCAL OPTIONS (free, needs hardware):
  Tools with runtime=LOCAL or runtime=LOCAL_GPU — read from the menu.

Already Available:
  List what's working. The user should feel good about what they have.
```

**Rules:**
- Do NOT hardcode provider names, API key names, or setup URLs in your prompts.
  Read them from the registry's `install_instructions` field on each tool.
- Always show the ratio: "X of Y configured" — this makes breadth visible.
- Group by capability, not by individual tool.
- Show what they CAN do now, then what they COULD unlock.
- If the user declines setup, proceed with the best available path — no nagging.
- If a tool shares an env var with others, group them (read from `dependencies` field).

### Setup Offer Protocol

When tools are `UNAVAILABLE` but can be fixed with simple configuration, **offer the user setup help instead of silently working around the limitation.** Many tools are one env var away from working.

| Fix Complexity | Action |
|----------------|--------|
| **1-minute fix** (env var) | Offer to help configure now — read `install_instructions` from the tool |
| **5-minute fix** (install) | Explain what to install and why — read `install_instructions` from the tool |
| **Complex fix** (GPU, model download) | Note the limitation, explain what it would unlock, move on |

**Rules:**
- Always tell the user what they're missing AND what they'd gain
- Show the cost difference (free local vs. paid API)
- If the user declines setup, proceed with the best available path — no nagging
- Group related fixes (tools sharing the same env var dependency)

### Composition Runtimes (Inside video_compose)

`video_compose` has **three** render engines / runtimes. They are parallel, not ranked — the choice is made at proposal and locked in `edit_decisions.render_runtime`. Check which are available:

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
info = registry._tools['video_compose'].get_info()
print('Render engines:', info.get('render_engines'))
print('Remotion note:', info.get('remotion_note'))
print('HyperFrames note:', info.get('hyperframes_note'))
"
```

| Engine | Used For | Requires |
|--------|----------|----------|
| **FFmpeg** | Video-only cuts, concat, trim, subtitle burn | `ffmpeg` binary (always available) |
| **Remotion** | React-based composition: still images → animated video, text cards, stat cards, charts, callouts, comparisons, transitions with spring physics, word-level caption burn, TalkingHead avatar | Node.js (`npx`) + `remotion-composer/` + `node_modules` |
| **HyperFrames** | HTML/CSS/GSAP composition: kinetic typography, product promos, launch reels, website-to-video, registry-block-driven scenes, SVG character rigs | Node.js ≥ 22 + FFmpeg + `npx` (consumed via `npx hyperframes`) |

`render_runtime` is **locked at proposal** (`proposal_packet.production_plan.render_runtime`) and **carried through edit_decisions unchanged**. `video_compose` routes based on this field; silent runtime swaps are forbidden. If the chosen runtime becomes unavailable at compose time, surface a structured blocker per "Escalate Blockers Explicitly" in `AGENT_GUIDE.md`. See `skills/core/hyperframes.md` for the Remotion-vs-HyperFrames decision matrix.

### Critical Rule: Motion-Required Requests

For any request where the deliverable inherently depends on motion rather than static coverage, treat motion as a hard requirement. Examples:

- sci-fi trailers,
- cinematic teasers built from generated clips,
- hype edits,
- avatar or agent videos,
- any brief whose promise depends on moving shots rather than still frames.

For these requests:

- The `render_runtime` chosen at proposal (Remotion, HyperFrames, or FFmpeg) must be confirmed available up front if the planned visual treatment depends on it.
- Still-image fallback is forbidden. Do not quietly convert the job into a Ken Burns teaser, animatic, or slide-based video.
- FFmpeg-only fallback is forbidden when it changes the approved deliverable from motion-led video to still-led video.
- **Silent runtime swap is forbidden.** If `render_runtime="hyperframes"` was locked and HyperFrames is unavailable, do NOT route to Remotion instead. Surface the blocker, propose options, get user approval, log a `render_runtime_selection` decision — then proceed.
- Bubble critical issues immediately. If the chosen runtime is unavailable, fails to render, or provider clip generation fails in a way that blocks the approved treatment, stop and tell the user before proceeding.
- Do not spend more tokens or time on downgraded output unless the user explicitly approves the downgrade as an animatic or proof-of-concept.

**When Remotion is available**, the agent should design production plans around it:
- Explainer videos with `flat-motion-graphics` playbook -> Remotion animated scenes, not Ken Burns
- Data-driven videos -> Remotion stat cards and charts, not static image screenshots
- Any pipeline using still images -> Remotion spring animations, not FFmpeg pan-and-zoom
- **Screen demos of a CLI/terminal/install flow -> `TerminalScene` (synthetic screen recording), not OS-level capture.** See `.agents/skills/synthetic-screen-recording/SKILL.md`. Faster, deterministic, privacy-safe. Use real capture (`screen_recorder`, `cap_recorder`, `playwright-recording`) only when the demo is a real app UI or requires unpredictable live behavior.

### Remotion scene types available in `remotion-composer/`

See `remotion-composer/SCENE_TYPES.md` for the authoritative list and their cut schemas. Current scene types usable via `cut.type`:
`text_card`, `stat_card`, `callout`, `comparison`, `hero_title`, `terminal_scene`, `anime_scene`, `bar_chart`, `line_chart`, `pie_chart`, `kpi_grid`, `progress_bar`. Overlay types include `section_title`, `stat_reveal`, `hero_title`, `provider_chip`.

These stock scene-types are the **templated** path — fast and reliable, but they are why videos look alike. For **hero work, prefer atelier mode** (hand-authored composition) over this catalog; read those types as a *mechanics codex*, not a menu to assemble. See "Composition Authoring Mode" in `docs/agent-guide/decisions.md` and `skills/meta/bespoke-composition.md`.

**When Remotion is NOT available** and `render_runtime="remotion"` was NOT locked, `video_compose` may use FFmpeg Ken Burns motion on still images. This still works but produces less engaging visuals. Mention this tradeoff in the proposal. When `render_runtime="remotion"` IS locked and Remotion is unavailable, that's a blocker — escalate, don't silently swap.

When `render_runtime="hyperframes"` is locked and HyperFrames is unavailable (Node < 22, missing `ffmpeg`/`npx`, or `hyperframes doctor` reports issues), that's also a blocker. Do not substitute Remotion or FFmpeg without user approval + a logged `render_runtime_selection` decision.

Routing is automatic — `video_compose` reads `edit_decisions.render_runtime` and dispatches to the matching engine (`_render_via_hyperframes`, `_remotion_render`, or `_render_via_ffmpeg`). But the **agent must know both Remotion and HyperFrames exist at proposal time** so it can design the visual approach intentionally. Don't default to Remotion for motion-graphics-heavy concepts that HTML/GSAP would express more naturally, and don't default to HyperFrames for briefs that reuse the existing React scene stack.

## Capability Discovery

OpenMontage uses two layers for capability choice:

- selector tools: capability-level routing such as `tts_selector` and `video_selector`
- provider tools: concrete tools discovered via the registry that call a specific backend

Always inspect the registry first:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_catalog(), indent=2))"
```

For finalist tools inspect:

- `capability`
- `provider`
- `usage_location`
- `supports`
- `fallback_tools`
- `related_skills`

Do not rely on memory or old docs when the registry can answer it.

## Tool Families

**Do not maintain hardcoded tool lists.** Always query the registry at runtime:

```bash
# See all tools grouped by capability (TTS, video_generation, image_generation, etc.)
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"

# See all tools grouped by provider (elevenlabs, openai, ffmpeg, etc.)
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_catalog(), indent=2))"
```

Key capability families to look for in the output:

- **tts** — Text-to-speech providers. Route via `tts_selector`.
- **video_generation** — Video generation providers (cloud, local GPU, stock). Route via `video_selector`.
- **image_generation** — Image generation providers (cloud, local GPU, stock). Route via `image_selector`.
- **music_generation** — Music and sound effect generation.
- **video_post** — Composition, stitching, trimming (FFmpeg-based, always local).
- **audio_processing** — Mixing, enhancement (FFmpeg-based, always local).
- **analysis** — Transcription, scene detection, frame sampling.
- **avatar** — Talking head and lip sync generation.
- **character_animation** — Local character specs, SVG rigs, pose libraries, action timelines, previews, and QA.
- **3d_world_generation** — Local semantic terrain, procedural biome scattering, explicit landmarks, diagnostic passes, and deterministic HyperFrames/Three.js camera fly-throughs. Route through `threejs_world` and read `skills/creative/3d-world-generation.md` plus `.agents/skills/threejs-world-generation/SKILL.md`.
- **3d_asset_acquisition** — Rights-safe GLTF/GLB catalogs for production-tier Three.js worlds. Route through `threejs_asset_catalog`; never substitute blockout primitives for a requested detailed or reference-grade environment.
- **3d_asset_generation** — Unique textured/PBR meshes from text or concept images. Route text-described hero assets through `atlas_3d`, image-conditioned assets and regional object extraction through `fal_3d`, and read `.agents/skills/3d-asset-generation/SKILL.md`. Announce provider/model/unit cost before every first paid call and sample before batching.
- **3d_world_rendering** — Production assembly, terrain, lighting, materials, camera, and image-sequence rendering in Blender. Route through `blender_world`; use Three.js for interactive/blockout review, not as a substitute for Blender when reference-grade scene density is requested.
- **enhancement** — Upscale, background removal, face enhance, color grading.

Each tool in the registry declares `best_for`, `install_instructions`, `runtime` (LOCAL, API, LOCAL_GPU, HYBRID), and `status`. Read these fields — do not assume tool strengths from memory.

### Tool Class Naming Convention

All tool classes use **PascalCase without a "Tool" suffix**. When importing tools in Python:

| Module | Class Name | NOT |
|--------|-----------|-----|
| `tools.audio.music_gen` | `MusicGen` | ~~MusicGenTool~~ |
| `tools.video.video_compose` | `VideoCompose` | ~~VideoComposeTool~~ |
| `tools.audio.audio_mixer` | `AudioMixer` | ~~AudioMixerTool~~ |
| `tools.audio.elevenlabs_tts` | `ElevenLabsTTS` | ~~ElevenLabsTTSTool~~ |
| `tools.analysis.transcriber` | `Transcriber` | ~~TranscriberTool~~ |
| `tools.subtitle.subtitle_gen` | `SubtitleGen` | ~~SubtitleGenTool~~ |

When in doubt, check: `grep "^class " tools/<path>.py`

All tools call via `.execute(params_dict)` (returns `ToolResult` with `.success`, `.data`, `.error`), NOT `.run()`.

### Selector Pattern

Three selector tools abstract multi-provider capabilities. **Selectors auto-discover providers from the registry.** Adding a new provider tool automatically makes it available through the selector — no selector code changes needed.

| Selector | Routes to | How it discovers |
|----------|-----------|-----------------|
| `tts_selector` | All tools with `capability="tts"` (ElevenLabs, Google TTS, OpenAI, Piper, Azure, fish.audio) | `registry.get_by_capability("tts")` |
| `image_selector` | All tools with `capability="image_generation"` (FLUX, Google Imagen, GPT Image, Recraft, etc.) | `registry.get_by_capability("image_generation")` |
| `video_selector` | All tools with `capability="video_generation"` | `registry.get_by_capability("video_generation")` |

Selectors route based on: user preference > availability > discovery order. They adapt input schemas between providers transparently.
