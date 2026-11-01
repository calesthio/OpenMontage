---
name: threejs-world-generation
description: Build deterministic, editable, free-viewpoint Three.js worlds from text or structured briefs. Use for cinematic 3D terrain, semantic regions, procedural biomes, explicit landmarks, environmental scattering, camera fly-throughs, world diagnostics, or requests for a real 3D environment rather than generated 2D footage. Integrates OpenMontage's threejs_world tool with HyperFrames; do not use for a single isolated 3D object or a flat parallax scene.
---

# Three.js World Generation

For production meshes and Blender assembly, also read `3d-asset-generation`.
Three.js remains the semantic interactive/blockout renderer; Blender is the
production renderer when the brief calls for dense reference-grade scenery.

The production handoff must include target dimensions for imported assets,
semantic scatter exclusion zones, terrain-following water/path geometry,
landmark visibility policy, camera clearance, and global/regional/walk review
frames. These are world-spec contracts, not manual Blender cleanup notes.

Create a persistent scene graph, not a sequence of unrelated 2D shots. Preserve the user's explicit constraints, infer missing construction details separately, establish the global terrain first, and refine selected regions without disturbing the world-wide spatial contract.

## Choose the fidelity tier explicitly

- `blockout`: procedural primitives, vertex colors, semantic/layout validation, fast iteration. Never call this production-quality, reference-grade, or visually equivalent to WorldClaw.
- `production`: licensed local GLTF/GLB catalogs, a minimum eight-model palette across four semantic categories, three PBR terrain layers, asset provenance, walk-level repetition review, and no primitive landmark fallback.

For a hero video or any reference showing populated textured environments, use `production`. If its catalog/material/provider requirements cannot be met, stop at preflight or the asset gate. Do not render a blockout as the final deliverable.

## Read first

- Read [references/worldclaw-principles.md](references/worldclaw-principles.md) when planning or explaining the coarse-to-fine method.
- Read [references/world-spec.md](references/world-spec.md) before authoring a `world_spec` or calling `threejs_world`.
- Read `hyperframes-core`, `hyperframes-animation`, and `hyperframes-animation/adapters/three.md` before editing the emitted workspace.
- Read `threejs-loaders`, `threejs-materials`, `threejs-textures`, `threejs-lighting`, and `threejs-postprocessing` for production-tier work.

## Route the request

- Use the `animation` pipeline for design-led, explanatory, abstract, or music-led world films.
- Use the `cinematic` pipeline for trailer-like mood, dramatic reveals, or source-plus-world edits.
- Choose HyperFrames when the deliverable is the code-native Three.js world. Choose Blender for reference-grade hero rendering and FFmpeg only to package Blender's numbered frames and approved audio. Record that choice at proposal; do not silently switch after approval.
- Keep this as a capability inside existing pipelines. Do not create a new pipeline merely because a scene is 3D.

## Workflow

### 1. Separate intent from completion

Record two lists before planning:

- `explicit_constraints`: only facts the user supplied.
- `inferred_details`: scale, region coverage, terrain operators, densities, palette refinements, and camera details added to make the world executable.

Never smuggle an inferred landmark, biome, or story beat into the explicit list.

### 2. Plan globally

Author one shared `world_spec` containing:

- world scale, terrain resolution, elevation range, and seed;
- semantic regions with normalized centers, radii, landform operators, palette, and scatter recipes;
- atmosphere and lighting shared across all regions;
- explicit landmarks with stable IDs and world-space placement;
- a complete camera path with time, position, target, and field of view.

Prefer 3-7 regions. Each region must contribute a distinct silhouette, surface read, or functional role.

### 3. Build the terrain foundation

For production, first call `threejs_asset_catalog` to install rights-safe catalogs under `projects/<id>/assets/3d/catalogs/<catalog-id>/`. Record source, license, archive hash, model inventory, and every selected model in the asset manifest. Then call `threejs_world` with `quality_tier: "production"` and the installed catalog paths.

```python
from tools.graphics.threejs_world import ThreeJSWorld

result = ThreeJSWorld().execute({
    "operation": "build",
    "world_spec": world_spec,
    "output_path": "projects/<id>/hyperframes",
    "duration_seconds": 60,
    "render_mode": "cinematic",
    "quality_tier": "production",
    "asset_catalog_paths": ["projects/<id>/assets/3d/catalogs/kenney-nature-kit"],
})
```

Treat `world.json`, `world-spec.js`, `world-runtime.js`, and `world-report.json` as editable assets. Do not flatten them into a video until the assets gate is approved.

### 4. Inspect regionally

Build a second pass with `render_mode: "semantic"` or `"wireframe"` when spatial problems are hard to see in the cinematic material pass. Inspect snapshots from global, regional, and walk-level viewpoints.

Maintain an issue queue with stable subjects:

- terrain transition or silhouette;
- landmark scale, pose, or contact;
- scatter density, slope rejection, or repetition;
- material contrast and atmosphere;
- camera clearance, clipping, or weak framing.

Fix only the affected region or object when possible. Preserve the seed, region IDs, camera times, and unrelated parameters.

### 5. Refine with bounded loops

Run at most three render-guided refinement rounds:

1. build the workspace;
2. run the unified HyperFrames `check` gate and snapshot representative times;
3. inspect frames and update the issue queue;
4. change the narrowest relevant spec fields;
5. rebuild with the same seed and compare.

Stop when no substantial issue remains or the iteration budget is reached. Report residual limitations rather than disguising them with overlays.

### 6. Compose without overwriting

For browser-native delivery, set `render_runtime: "hyperframes"` and `composition_mode: "atelier"`; `video_compose` must preserve the authored workspace. For reference-grade video, render a Blender PNG sequence with `resume: true`, then set `render_runtime: "ffmpeg"` for packaging. Preserve the world spec and `.blend` as the editable source of truth.

## Quality gates

- Terrain is continuous and region boundaries blend without obvious seams.
- Every landmark touches its support surface and remains inside world bounds.
- Scatter respects region affinity, slope limits, and deterministic seed behavior.
- Global, regional, and walk-level frames all read as the same continuous world.
- Camera paths remain above terrain, avoid clipping, and provide at least one scale-establishing reveal.
- World source remains editable after render: regions, landmarks, camera keys, and palette have stable IDs or fields.
- HyperFrames `check` and post-render review pass before delivery. Use the legacy `validate` or `inspect` operations only when supporting an older runtime.
- Production beauty frames contain textured assets at foreground, midground, and background depths; no dominant object may read as an untextured box, cone, octahedron, or dodecahedron.
- Production requires at least four semantic asset categories, eight distinct models, three PBR terrain layers, one regional composition review per camera-critical region, and explicit repetition/contact findings.

## Boundaries

- The production catalog path materially improves geometry and surface richness, but it still does not reproduce WorldClaw's GPT-Image-2, SAM3, SAM3D, Hunyuan3D, BlenderMCP, or four-H20 implementation.
- Do not claim articulated assets, game physics, navigation meshes, or interaction logic unless another tool explicitly adds them.
- Do not use unseeded randomness, wall-clock animation, remote models, or render-time asset fetches.
- Do not delete the lower-level `threejs-*` skills. They are the subsystem references used when extending this runtime.
