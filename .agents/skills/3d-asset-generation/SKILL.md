---
name: 3d-asset-generation
description: Generate, reconstruct, inspect, and route production 3D assets for OpenMontage worlds using Atlas Cloud, fal.ai, licensed catalogs, and Blender.
---

# 3D Asset Generation

Use this skill when a production needs real meshes rather than primitive stand-ins.
It complements `threejs-world-generation`: that skill owns semantic world planning;
this skill owns how unique and repeated meshes enter the world with provenance.

## Route by asset role

| Need | Tool | Model/path | Why |
|---|---|---|---|
| Repeated vegetation, rocks, generic props | `threejs_asset_catalog` | CC0 Kenney catalog | Free, coherent, instancing-friendly |
| Unique object described in words | `atlas_3d` | `tripo-h3.1/text-to-3d` | Direct textured/PBR GLB with seeds and face limit |
| Object matching a concept image | `fal_3d` | Hunyuan 3D v3.1 Rapid image-to-3D | Better silhouette/style conditioning from one image |
| Several objects extracted from one regional composition | `fal_3d` | SAM 3D Objects | Individual and combined GLBs plus placement metadata |
| Terrain, composition, lighting, camera, final frames | `blender_world` | Blender 4.5 LTS / Eevee Next | Scene-level control; generated-asset APIs are not world renderers |

Never ask a text-to-3D model to generate a whole cinematic world in one mesh.
Generate hero objects, use licensed catalogs for high-volume scatter, and assemble
everything in Blender from a semantic specification.

## Paid-call discipline

Before every first provider call, state the exact provider, model, operation,
estimated unit cost, and number of requested outputs. Generate one sample before
a batch. As of 2026-08-13:

- Atlas Tripo H3.1: $0.22 untextured; $0.33 standard textures; $0.44 HD
  textures; detailed geometry adds $0.22; quad mesh adds $0.055.
- fal Hunyuan 3D v3.1 Rapid: $0.225 per generation; PBR adds $0.15.
- fal SAM 3D Objects: $0.02 per reconstruction.

Pricing changes. Confirm the provider page before quoting or running a batch.

## Asset prompt contract

Each request describes one isolated object, not a shot:

1. Name the object and silhouette.
2. Specify construction materials and visible wear.
3. Specify the project's art style and color constraints.
4. State scale and orientation.
5. Exclude ground plane, backdrop, extra objects, labels, and lighting rigs.

For image-to-3D, use a simple background and make the object occupy more than
half the frame. Request PBR only for assets close enough to benefit from it.

## Mandatory mesh QA

Do not approve from the provider thumbnail alone. Import the downloaded artifact
into Blender and inspect:

- front, rear, and silhouette;
- geometry holes and floating pieces;
- ground contact, scale, and orientation;
- UV seams and missing texture slots;
- base-color, roughness, metallic, and normal response;
- triangle count and whether the intended camera distance justifies it.

Record provider, model id, prompt, seeds, source page, cost, and output path in
the asset provenance manifest. Failed samples remain failed; do not silently
swap provider or spend on another model.

### Assembly normalization is mandatory

Provider and catalog GLBs rarely share units, origins, or up-axis assumptions.
Never compensate with arbitrary scene-level scale guesses. The Blender assembly
spec declares `target_height`; the renderer measures the imported bounding box,
normalizes to that target, and offsets the bounding-box floor to the sampled
terrain height. Review the resulting real-world scale and ground contact.

Repeated scatter must declare semantic `exclusion_zones` around settlements,
roads, rivers, landmark apertures, and hero camera sightlines. Density that
occludes the subject is not production detail. Waterways and paths must use flat
terrain-following ribbons; beveled 3D curves read as pipes from aerial cameras.

Landmarks whose reveal timing matters declare visibility windows in the scene
spec. Camera occlusion remains preferred for natural reveals, but deterministic
visibility keys are the hard guarantee for approved timing.

## World fidelity budget

A reference-grade region needs three simultaneous density layers:

- macro: authored terrain silhouettes, waterways, paths, settlements;
- meso: hero buildings, bridges, cliffs, canopy clusters, props;
- micro: ground cover, rocks, flowers, debris, material breakup.

The asset gate must show global, regional, and walk-height Blender stills. A
wide aerial alone can hide broken contacts; a walk shot alone can hide an empty
world. Primitive-only previews must be labeled `blockout` and cannot pass as a
production-fidelity review.

For a final animation, render a small bounded frame range first and measure the
per-frame time. Choose the full-render resolution from that measurement rather
than intuition, render a numbered PNG sequence, and call `blender_world` with
`resume: true` after interruption so it starts at the first missing frame.
