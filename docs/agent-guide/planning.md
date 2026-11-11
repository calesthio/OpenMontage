# Agent Guide — Planning, Music and Style

Part of [`AGENT_GUIDE.md`](../../AGENT_GUIDE.md), which states every rule in brief and says when to read this.
**Read this in full before presenting concepts, the production plan, the music plan or a style playbook.**

## User-Facing Planning Protocol

### Music Plan (Mandatory)

Music is a critical part of any video. **Surface the music situation to the user at proposal/idea time** — do not silently defer it to the asset stage where a failure becomes expensive.

Check music availability in this order and present the options:

1. **User music library:** Check `registry.get_by_capability("music_library")` and inspect `music_library/`. If tracks exist, list durations and let the user pick one.
2. **Royalty-free search:** Check `registry.get_by_capability("music_search")` for configured search/download tools. Report licensing constraints and whether a key is required.
3. **Music generation APIs:** Check `registry.get_by_capability("music_generation")`. Report status, quota, cost, and quality tradeoffs honestly.
4. **Bring your own:** Note that the user can provide a track (for example from YouTube Audio Library or Jamendo) through the `music_library/` drop path.

**Always present the user with explicit choices:**
- Use a track from their library (which one?)
- Provide a different track (drop it in `music_library/`)
- Generate one via API (if available — name the provider and cost)
- Proceed without music

**If no music source is available:** Tell the user explicitly. Do NOT let this surface as a surprise at the asset stage.

Record the music decision in the proposal/brief artifact so the asset director knows what to do.

## Music Library

Users can place royalty-free music tracks in `music_library/` (gitignored). The asset director will check this folder before falling back to API-based music generation.

```
music_library/
├── ambient_track.mp3
├── cinematic_epic.mp3
└── ...
```

If the folder has tracks, the proposal and asset stages should present them as options alongside generated music. See the proposal-director and asset-director skills for details.

## Pipeline Asset Expectations

Each pipeline manifest's `tools_available` field declares what tools a stage can use. Use selectors for multi-provider capabilities — the selector handles routing to whatever is available. Read the pipeline manifest for the authoritative list per stage.

## Style Playbooks

| Playbook | Best For |
|----------|----------|
| `clean-professional` | Corporate, educational, SaaS |
| `premium-minimalist` | Investor updates, expert explainers, product narratives |
| `flat-motion-graphics` | Social media, TikTok, startups |
| `minimalist-diagram` | Technical deep-dives, architecture |
| `anime-ghibli` | Narrative animations, nature-themed stories, emotional storytelling, fantasy visuals |
| `ink-sketch` (Ink Theater) | Hand-drawn ink-on-white doodle animation; a character that draws itself, walks, dances; contraption explainers. **Style id, not a YAML playbook** — there is no `styles/ink-sketch.yaml`; route through `skills/creative/ink-theater.md` |

The YAML playbooks are the files in `styles/`; `list_playbooks()` in `styles/playbook_loader.py` is the authoritative list.

For custom, atelier, brand, launch, or hero work, read `skills/meta/taste-direction.md` before choosing a playbook. Carry its `taste_profile` into the proposal so later stages can preserve the design read, visual variance, motion intensity, information density, reference strategy, and anti-patterns.

For physical-product ads, launch films, or promos with generated shots of a specific SKU, also read `skills/creative/commercial-product-video.md` for product references, shot controls, continuity, and final-cut review within the selected pipeline.

### Hand-drawn "doodle" animation → Ink Theater / Ink Puppet

For any brief that wants a **hand-drawn ink doodle** look — "a sketch that comes to life", "a pencil / stick figure that walks or dances", "a little character that acts out the idea", whiteboard-doodle explainers — use the **Ink Theater** engine + **Ink Puppet** mocap system (`skills/creative/ink-theater.md`, `ink-theater/README.md`). It is a **style + reusable engine, not a new pipeline**: illustration / contraption pieces run on the `animation` pipeline; a mocap character (draws itself → walks / dances / waves via `InkPuppet.choreograph([...])`) runs on `character-animation`. Cross-tool entry points: **`/ink-art`** (create a vector doodle from scratch) and **`/animated-drawing`** (animate a *supplied* drawing with mocap — raster; `skills/creative/animated-drawing.md`). Never hand-tune character motion — the agent only chooses named mocap clips.
