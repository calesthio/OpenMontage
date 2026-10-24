# Commercial Product Video — Production Guidance

## When to Use

Use when a physical-product commercial, launch film, or promo needs generated shots of a specific SKU. Translate the supplied brief into a visual treatment, reference-controlled motion, and an editable sequence that preserves the product through the final cut.

This is cross-stage guidance for the selected pipeline. Start from the supplied message and approved product information; consumer research, media buying, and conversion testing are not prerequisites. For software demonstrations, use the screen-demo guidance instead. For general camera vocabulary, use `skills/creative/video-gen-prompting.md`.

## Prerequisites

| Input | What to establish |
|---|---|
| Brief and product assets | Deliverable duration/aspect ratio, intended message, actual SKU/colorway, supplied product angles, exact logo/label artwork, and any demonstrated operation. Flag missing views before promising them. |
| Selected pipeline and proposal | Read its stage directors. Resolve the available image/video controls through the registry and the selected tools' `agent_skills`; carry the approved motion promise, provider/model, runtime, and budget forward. |
| Art direction | For hero work, read `skills/meta/taste-direction.md`. Set material, environment, lighting, and motion rules that make this product's treatment distinctive. |
| Existing contracts | Use `schemas/artifacts/brief.schema.json`, `proposal_packet.schema.json`, `scene_plan.schema.json`, and `asset_manifest.schema.json` under the same directory. Product-specific notes can live in existing top-level `metadata`. |

## Process

### 1. Define the Product and Visual Treatment

Inventory the references by purpose: product identity, allowed viewing angles, surface finish, actual operation, and visual style. An atmosphere reference does not establish a SKU's geometry. Keep filenames or asset IDs attached to the relevant purpose; never combine similar products into one reference set.

Separate **invariants** from **creative variables**. Invariants usually include silhouette, proportions, colorway, controls, ports, cap/closure, and label layout. Creative variables can include the setting, surrounding effects, camera path, and lighting. Specify where reflections or grading may change perceived color, and retain a neutral reference for comparison.

Write a treatment as an observable visual event: “A broad light reflection travels across the brushed aluminum shell while the dark background stays still.” “Premium cinematic product ad” leaves both the event and the product's material unresolved. A product need not rotate or transform in every shot; choose movement that reveals something the approved treatment needs.

**If** the brief demands a back view, internal mechanism, or open state absent from the references, **then** request that material or propose a treatment using known views. A plausible invented mechanism is insufficient for a literal demonstration. **If** the concept is an expressive fantasy, **then** define its rules and the return to the recognizable product; do not describe imagined internals as engineering evidence.

### 2. Assign Shot Roles Before Generating

Build a sequence with a deliberate visual peak and landing. Choose only the roles the brief needs; this table is not a mandatory five-shot template.

| Intent | Shot type | Lens / framing | Camera motion | Lighting | Control / reference | Avoid |
|---|---|---|---|---|---|---|
| Reveal silhouette | Hero three-quarter | Start around 50–85 mm equivalent; preserve recognizable proportions | Restrained dolly or static camera with moving light | Rim separation plus readable surfaces | Approved hero angle; identity reference or first frame where supported | Wide-angle swelling, unverified full orbit |
| Make material tangible | Detail / insert | Tight crop; focus covers the relevant texture | Short lateral move or controlled focus shift | Reflection shaped for metal/glass; grazing light for texture | Actual finish reference and exact detail location | Turning brushed metal into chrome; unrelated decorative macro |
| Show operation | Use / interaction | Frame hand, contact point, and outcome together | Stable enough to read the mechanism | Clear contact and mechanism visibility | Supplied operation footage, known states, or verified model | Hiding the operation behind speed ramps or occlusion |
| Build an expressive moment | Transformation / environment effect | Composition reserves space for the event | One coherent move supporting the effect | Follows the treatment's material rules | Identity reference plus explicit effect start, evolution, and end | Several simultaneous transformations; invented efficacy |
| Land product and message | Packshot / end card | Readable SKU and exact artwork at delivery size | Settled frame or restrained motion | Legible label and controlled glare | Approved product image/footage; separately composed copy | Generated typography; a landing too short to read |

Lens values describe perspective intent, not guaranteed model parameters. Encode the selected framing in `shot_language` and the five-aspect spec; inspect the result rather than treating a focal-length phrase as calibration. Preserve space for approved copy in the target aspect ratio before generating the master image.

### 3. Choose the Generation Path Per Shot

- **If exact identity is essential and suitable product imagery exists**, prefer a reference-conditioned or image-to-video path supported by the selected tool. Establish a satisfactory product frame before spending on motion. Describe the action and camera relative to that frame rather than repeatedly redesigning the object in text.
- **If a shot must enter and leave specific states**, use first/last-frame control when available and compatible with the approved path. Endpoints constrain the boundary images; inspect the intervening motion for geometry drift, disappearing parts, and implausible state changes.
- **If the shot needs geometry beyond the supplied views**, obtain more references or use a verified asset/recorded shot. A generated 3D asset also needs identity review; selecting 3D does not establish accuracy.
- **If exact packaging text or a logo must remain readable**, favor approved imagery or controlled compositing. A flat logo overlay on a turning, reflective container is not a repair unless tracking, occlusion, and surface integration work throughout the shot.
- **If human contact, pouring, or mechanical action repeatedly fails**, reduce the simultaneous events, split the operation at a natural cut, or propose supplied footage for the critical action. Keep generated atmosphere around it if that preserves the approved treatment.

Reuse `skills/creative/image-gen-usage.md`, `image-provider-usage.md`, and `video-gen-prompting.md` in this directory, then the selected provider's guidance. Do not assume every wrapper exposes every model control. Follow `AGENT_GUIDE.md` when a proposed repair changes an approved provider/model, motion promise, runtime, or creative direction.

### 4. Hand Off a Shot Contract Through Existing Artifacts

At proposal, describe the visual treatment, source/generation split, motion promise, and cost. At scene planning, use ordinary scene fields for timing, intent, camera, and required assets. Keep supplementary product controls in **top-level** `scene_plan.metadata`, keyed by scene ID; the scene schema does not accept arbitrary per-scene fields. These notes guide the agent, not a new parser or artifact type.

The following is a minimal scene-plan example for one shot within a longer film. The reference files must actually be supplied and registered before generation.

```json
{
  "version": "1.0",
  "scenes": [{
    "id": "bottle_reveal",
    "type": "generated",
    "description": "Amber perfume bottle on a dark plinth; a broad reflection crosses the glass.",
    "start_seconds": 0,
    "end_seconds": 4,
    "shot_intent": "Reveal the bottle silhouette and amber glass finish.",
    "narrative_role": "introduce_subject",
    "hero_moment": true,
    "shot_language": {
      "shot_size": "close_up",
      "camera_movement": "static",
      "lens_mm": 85,
      "lighting_key": "rim_lit",
      "depth_of_field": "medium"
    },
    "required_assets": [{
      "type": "image",
      "description": "Approved amber-bottle hero image with closed black cap",
      "source": "provided"
    }]
  }],
  "metadata": {
    "commercial_product": {
      "sku": "Amber bottle / black cap",
      "identity_references": ["assets/provided/bottle-hero.png"],
      "invariants": ["rectangular shoulder", "black cap closed", "label layout"],
      "shots": [{
        "scene_id": "bottle_reveal",
        "depiction": "expressive",
        "control": "image_to_video",
        "start_state": "Closed bottle, approved three-quarter view",
        "end_state": "Same closed bottle and view; reflection settles",
        "allowed_change": "Lighting reflection only; no liquid or cap movement",
        "acceptance": ["continuous silhouette", "unchanged closure", "legible final label"]
      }]
    }
  }
}
```

Adapt the metadata to the shot; retain reference IDs, invariant features, start/end states, the supported control, allowed changes, and acceptance checks. Use `depiction` to distinguish literal operation from expressive treatment. At assets, register the actual files in `asset_manifest`; downstream stages must consume the accepted asset, not a rejected generation. Keep paths project-relative and verify them on disk. At edit, carry usable in/out points, product state, copy placement, and the landing into `edit_decisions`.

### 5. Review Motion, Then Repair the Smallest Failure

Review the clip in motion and inspect frames at its start/end, peak action, hand contact, occlusion, and transition points. Compare these with the product references. Frame sampling can help find defects but cannot prove their absence between samples; use `skills/creative/video-understand-usage.md` for its tool limitations.

Check silhouette and feature count, closure state, reflections/material behavior, hand/product contact, liquid continuity, and whether the intended event is actually readable. A stable first frame does not rescue a product that changes shape mid-shot. A beautiful clip with the wrong SKU is not an accepted product shot.

**If** only a short edge of the clip fails and a clean trim preserves the shot's role and timing, **then** trim it. **If** the defect affects the action or identity, **then** revise the reference, action complexity, or control that caused it. Repeating “perfect consistency” adds no new constraint. **If** exact text fails, **then** replace it through a feasible approved-asset/compositing route rather than accepting invented lettering.

Set a shot attempt/cost ceiling within the approved production budget before paid retries. Stop at that ceiling or when the same defect persists without a meaningful change to the inputs. Record accepted/rejected takes and the specific defect in existing asset notes/decision records. Present a simpler executable shot or the missing input needed to continue; preserve the existing checkpoint and reviewer protocol.

### 6. Evaluate the Finished Cut and Persist

Judge the exported aspect ratio, not just the uncropped source. Product identity must survive crop, grade, transitions, overlays, and compression. Check that adjacent shots join with compatible cap/open states, hand positions, movement direction, and product scale where continuity is intended. Use deliberate cuts when changing state or geography.

Let sound reinforce the physical event: a clasp click belongs at visible closure; a stylized reveal can have an expressive sound. Do not add operational sounds that suggest a mechanism the product lacks. Allow the visual peak and final packshot enough screen time for their actual content; avoid fixed pacing rules detached from the treatment.

| Dimension | 1 — Fail | 3 — Revise | 5 — Ready |
|---|---|---|---|
| Product identity | Wrong SKU or changing geometry | Minor drift visible at delivery size | Approved features remain recognizable throughout |
| Motion / operation | Broken contact or impossible literal action | Action obscured or awkward | Intended event reads with coherent state changes |
| Art direction | Generic effects overwhelm product | Attractive shots without a shared treatment | Material, light, environment, and motion express one treatment |
| Edit / landing | Key product detail or final copy unreadable | Inconsistent joins or rushed landing | Sequence, crop, sound, and copy support the intended reveal |

Treat identity and literal-operation failures as blocking defects; high style scores do not offset them. Use the existing reviewer to assess the full piece and retain its revision limits. Persist outputs through the selected pipeline's canonical artifacts and project assets, with schema validation and approved runtime unchanged.

## Good / Bad Examples

**Good — fragrance launch:** An approved bottle frame drives a restrained reflection reveal; a generated abstract amber environment supplies the expressive insert; the final packshot uses exact supplied artwork. The cap stays closed throughout. Each shot has a clear motion event and identity check.

**Bad:** “Luxury perfume, 360-degree orbit, cap explodes, label writes itself, liquid pours, elegant hands.” One clip must invent unseen geometry, typography, contact, and several state changes. “Luxury” resolves none of those constraints.

**Good — folding device demo:** Supplied footage establishes the actual hinge motion. Generated detail shots show the verified closed device and finish; a clean cut joins the states. A fantasy transformation is offered only as an expressive alternative to the literal demo.

**Bad:** Generate a plausible folding motion from a single closed-device photograph and present it as the product's demonstrated operation.

## Common Pitfalls

- Mixing product identity references with style references without assigning their roles.
- Rejecting all expressive motion in pursuit of fidelity, or using expression to excuse an unrecognizable product.
- Generating a full orbit from one view and trusting matching endpoints to validate the middle.
- Fixing label distortion with an untracked sticker that slides across the product.
- Substituting a moving still for an approved generated-motion shot without surfacing the delivery change.
