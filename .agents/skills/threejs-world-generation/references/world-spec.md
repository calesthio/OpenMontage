# `threejs_world` specification

Use normalized region coordinates in `[-1, 1]`; the tool converts them to world space. Positions for landmarks and cameras are world-space `[x, y, z]` values.

## Minimal shape

```json
{
  "version": "1.0",
  "title": "The Luminous Divide",
  "seed": 2048,
  "explicit_constraints": ["a volcanic rift divides a living valley"],
  "inferred_details": ["three semantic regions", "dawn atmosphere"],
  "world": {
    "size": 120,
    "resolution": 160,
    "elevation_scale": 18,
    "water_level": -1.5
  },
  "atmosphere": {
    "sky_color": "#07111f",
    "fog_color": "#13263a",
    "fog_density": 0.009,
    "sun_color": "#ffd7a3",
    "sun_intensity": 3.2,
    "sun_position": [45, 70, 20]
  },
  "terrain_materials": [
    {
      "id": "mossy-ground",
      "regions": ["ember-rift"],
      "base_color": "assets/materials/mossy-ground/diffuse.jpg",
      "normal": "assets/materials/mossy-ground/normal.jpg",
      "roughness": "assets/materials/mossy-ground/roughness.jpg",
      "meters_per_repeat": 7
    }
  ],
  "asset_palette": [
    {
      "id": "rift-tree-a",
      "catalog_id": "kenney-nature-kit",
      "model_id": "tree-pine-a",
      "category": "tree",
      "region_id": "ember-rift",
      "count": 80,
      "scale_range": [0.8, 1.5]
    }
  ],
  "regions": [
    {
      "id": "ember-rift",
      "label": "Ember Rift",
      "center": [-0.35, 0.12],
      "radius": 0.58,
      "base_elevation": 0.3,
      "amplitude": 1.0,
      "frequency": 1.4,
      "landform": "ridge",
      "blend_width": 0.2,
      "color": "#5b271f",
      "accent_color": "#ff6b2c",
      "scatter": {"rock": 90, "crystal": 22, "tree": 0}
    }
  ],
  "landmarks": [
    {
      "id": "rift-gate",
      "type": "arch",
      "region_id": "ember-rift",
      "position": [-24, 0, 8],
      "scale": 5.5,
      "color": "#2a2020",
      "accent_color": "#ff7a35"
    }
  ],
  "camera_path": [
    {"time": 0, "position": [72, 42, 72], "target": [0, 3, 0], "fov": 46},
    {"time": 60, "position": [-54, 13, -32], "target": [-12, 4, 5], "fov": 40}
  ]
}
```

## Regions

Required: `id`, `center`, `radius`, `color`.

Useful fields:

- `label`: human-facing diagnostic label.
- `base_elevation`: normalized vertical offset before `elevation_scale`.
- `amplitude`: relief contribution.
- `frequency`: macro noise frequency.
- `landform`: `plain`, `peak`, `ridge`, `dune`, `terrace`, `basin`, or `canyon`.
- `blend_width`: softness of the semantic boundary.
- `accent_color`: used by semantic and environmental details.
- `scatter`: counts for `tree`, `rock`, and `crystal` prototypes.
- `slope_limit`: maximum accepted slope proxy for scattered instances.

Region weights are normalized at every terrain sample. The fallback region must still cover the full domain, so avoid tiny isolated regions with no broad neighbor.

## Landmarks

Supported procedural types: `monolith`, `arch`, `tower`, `ruin`, `crystal`, `settlement`, and `ring`.

Each landmark is placed at sampled terrain height. `position[1]` is an additional vertical offset, not an absolute Y coordinate. Keep IDs stable through refinement so review notes remain addressable.

## Camera path

- Provide at least two keys.
- First key time must be `0`; last key should match the requested duration.
- Keep keys ordered and inside the duration.
- The runtime interpolates position, target, and FOV with smoothstep easing.
- Add higher keys for regional and walk-level passes; do not attempt to encode cuts with teleporting adjacent keys.
- Keep the camera at least `2` world units above sampled terrain unless a deliberate ground skim is reviewed.

## Render modes

- `cinematic`: PBR vertex colors, fog, water, shadows, overlays.
- `semantic`: saturated region colors and labels for layout diagnosis.
- `wireframe`: terrain topology and explicit scene nodes for geometry diagnosis.

## Tool outputs

`operation: "build"` writes:

- `index.html`: HyperFrames composition root.
- `world.json`: normalized editable specification.
- `world-spec.js`: browser-loadable specification.
- `world-runtime.js`: deterministic Three.js scene construction.
- `world.css`: full-frame canvas and production overlays.
- `world-report.json`: validation, performance estimate, and warnings.
- `hyperframes.json`: local registry configuration.

Production builds additionally write `asset-catalog-index.json` and `asset-catalog.js`, and copy the selected catalogs into `assets/models/` so rendering never depends on a remote model fetch.

`operation: "validate"` performs specification checks without writing a workspace.
