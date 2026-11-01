# 3D World Generation

Use this Layer 2 skill when an animation or cinematic project needs a real, continuous Three.js environment rather than a stack of stills or generated video clips.

## Capability route

1. Query the registry for `3d_world_generation`, `3d_asset_acquisition`, `3d_asset_generation`, and `3d_world_rendering`.
2. Read the selected tools' `agent_skills`; production work requires both `.agents/skills/threejs-world-generation` and `.agents/skills/3d-asset-generation`.
3. Choose the delivery path at proposal. Use `render_runtime="hyperframes"` and `composition_mode="atelier"` for an editable browser-native Three.js deliverable. Use `render_runtime="ffmpeg"` for a Blender-rendered PNG sequence plus governed audio/video mux. The latter is still real 3D motion; FFmpeg only packages Blender's frames.
4. Use either the `animation` or `cinematic` pipeline. A 3D world is a reusable production capability, not a separate pipeline.
5. Lock a fidelity tier. `blockout` is only for semantic layout and camera iteration. Hero/reference-led output requires `production`, licensed catalogs for repeated assets, Atlas/fal for unique assets when useful, and `blender_world` for scene assembly/rendering.

## Artifact mapping

| Stage | Contract |
|---|---|
| proposal | Record world promise, explicit-vs-inferred policy, fidelity tier, and either the browser-native Three.js/HyperFrames route or production Blender/FFmpeg route. |
| script | Use beats or sparse titles; narration is optional. |
| scene_plan | Define global, regional, and walk-level camera beats in one continuous coordinate system. |
| assets | Install/inventory repeated assets with `threejs_asset_catalog`; sample unique hero assets with `atlas_3d` or `fal_3d`; assemble and render global/regional/walk stills with `blender_world`; register meshes as `type="3d_asset"` and the editable world spec/`.blend` as `type="3d_world"`. |
| assets review | Produce semantic/wireframe diagnostics and representative snapshots; log bounded refinement issues. |
| edit | Carry camera times without changing region IDs or seed. |
| compose | Browser-native: call `video_compose` on the authored HyperFrames workspace. Production Blender: render a numbered PNG sequence with resume enabled, then let `video_compose`/FFmpeg package frames and audio without pretending FFmpeg generated the motion. |

## Required asset metadata

Record:

- `source_tool: "threejs_world"`;
- `provider: "threejs"`;
- `quality_tier`, `seed`, and the returned model identifier;
- catalog IDs, source URLs, licenses, archive hashes, selected model IDs, and PBR material maps;
- workspace path and `world.json` path;
- region, landmark, instance, and terrain-triangle counts;
- diagnostic warnings and refinement rounds;
- `layer3_skills_read: ["threejs-world-generation"]`.

## Review focus

- The terrain is continuous and establishes the large-scale silhouette.
- Region color, relief, scatter, and landmarks agree with one semantic layout.
- Environmental instances respect slope and contact constraints.
- Global, regional, and walk-level frames remain spatially coherent.
- The camera never tunnels through terrain or clips the far plane.
- The final render preserves editability: world, regions, landmarks, and camera keys remain structured files.
- Production frames use textured authored models at foreground, midground, and background depth; dominant primitives or untextured flat ground are asset-gate failures.

Do not use this path for isolated product spins, a CSS parallax landscape, or an AI-generated fly-through with no explicit scene graph.
