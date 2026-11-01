# WorldClaw principles adapted for OpenMontage

Source: [WorldClaw: Agentic 3D Open-World Generation at Scale](https://arxiv.org/html/2608.05248v1), Guo et al., arXiv:2608.05248v1 (2026).

WorldClaw's public repository currently contains the paper and assets, not the executable generation stack. OpenMontage therefore adopts the architectural ideas, not private code or model weights.

## Transferable architecture

1. **Intent extraction precedes completion.** Keep user-stated facts separate from inferred construction parameters.
2. **Shared structured intermediates coordinate agents.** A world spec carries regions, terrain, objects, appearance, and spatial relations across stages.
3. **Global constraints precede local detail.** Establish semantic layout, scale, terrain, atmosphere, and major relationships once.
4. **Terrain is the spatial contract.** Use the same region weights for height, palette, scattering, and later placement.
5. **Reusable environmental prototypes differ from functional landmarks.** Scatter rocks, vegetation, and crystals globally; place named structures explicitly.
6. **Local development is selective.** Spend detail and iteration on regions that matter to the camera path or delivery promise.
7. **Objects stay independent.** Stable IDs and transforms preserve editability and replacement.
8. **Placement is contact-aware.** Sample terrain height and slope, reject implausible candidates, align instances, and diagnose floating or penetration.
9. **Refinement is render-guided and bounded.** Use global, regional, walk, semantic, and wireframe views; change the narrowest responsible parameters.
10. **Executable representations improve reuse.** Code-native terrain, materials, placement, and camera paths remain parameterized and animatable.

## Local mapping

| WorldClaw concept | OpenMontage implementation |
|---|---|
| Structured scene specification | `world_spec` JSON and tool schema |
| Semantic layout map | Continuous normalized region-weight field |
| Region-aware height field | Weighted procedural landform operators |
| Terrain materials | Blockout: vertex colors. Production: catalogued PBR texture layers |
| Reusable terrain assets | Blockout: primitives. Production: licensed textured GLTF/GLB palettes |
| Regional objects | Stable explicit scene nodes; production forbids primitive landmark fallback |
| Blender refinement agents | HyperFrames snapshots plus agent issue queue |
| Free-viewpoint render | Deterministic Three.js camera path responding to `hf-seek` |
| Editable textured meshes | Editable code-native geometry, materials, regions, and transforms |

## Deliberate scope differences

- No single-view object reconstruction, segmentation, or generated PBR texture maps.
- No Blender or Unreal dependency in the current runnable path; this limits reconstruction and offline-render fidelity.
- No claim of photoreal asset diversity comparable to large generative 3D models.
- Stronger portability and determinism for browser-rendered OpenMontage video work.
