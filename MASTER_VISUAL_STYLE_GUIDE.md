# OPENMONTAGE — MASTER VISUAL STYLE & NANO BANANA PRODUCTION PLAN

**Document type:** Master creative direction + image-generation specification + production blueprint  
**Version:** 1.0  
**Research date:** 2 November 2026  
**Primary image route:** Google Flow through `gflow-cli`, using Nano Banana 2.1 when the installed CLI/Flow account exposes it  
**Target format:** English-language animated science documentary, 20–25 minutes, 16:9  
**Immutable production rule:** **ONE SCRIPT SENTENCE = ONE UNIQUE IMAGE PROMPT = ONE UNIQUE FINAL IMAGE**

---

## 0. How this document must be used

This file is the creative and technical source of truth for OpenMontage's visual identity and AI-image workflow. Read it before creating a new visual pipeline, writing image prompts, preparing a reference pack, or generating assets for a video.

It is a production specification, not permission to spend credits. Any real Google Flow generation must still pass the existing Flow Job Manager approval gate and the project's safety controls. Do not remove `--no-spend`, the MCP Security Proxy, or the READY_FOR_APPROVAL / APPROVED workflow.

The references in this document are **creative references, not assets to copy**. The channel must develop its own character, palette, shapes, compositions, sound identity, and recurring visual metaphors. Do not reproduce another channel's characters, logos, signature creatures, exact compositions, scene designs, scripts, or music.

### Priority order when requirements conflict

1. Scientific and factual correctness.
2. The meaning of the current script sentence.
3. The established original channel style and character identity.
4. Composition clarity and readability on a 1080p YouTube screen.
5. Decorative detail.

Never sacrifice scientific correctness or sentence meaning to preserve a pretty composition.

---

# PART I — CHANNEL IDENTITY

## 1. Creative positioning

### 1.1 Format

Build an **Animated Science Documentary** channel: long-form, story-led science films that explain one compelling question through a continuous illustrated world. The viewer should feel that they are watching a short animated documentary, not a lecture with a slideshow and not a collection of unrelated AI pictures.

The channel's core promise:

> We take a fascinating scientific question, follow the evidence, and make the invisible, distant, ancient, or complicated visible through beautiful animated explanations.

### 1.2 Audience experience

The viewer should experience five things:

- **Curiosity:** the opening creates a precise question or mystery.
- **Clarity:** every visual makes a difficult idea easier to understand.
- **Wonder:** scale, detail, colour, and transitions make the subject feel remarkable.
- **Trust:** claims are researched, qualified, and distinguish estimates from known facts.
- **Continuity:** a consistent visual identity makes every episode recognisably part of the same channel.

The tone is intelligent, accessible, cinematic, warm, and occasionally playful. Avoid childish classroom graphics, meme-heavy pacing, fake drama, or overconfident claims.

## 2. Reference-channel analysis: what to learn, not copy

Use the following channels as production references for broad principles:

| Reference | Learn from it | Do not copy |
|---|---|---|
| Kurzgesagt – In a Nutshell | Cohesive visual worlds, bold colour, clear metaphors, memorable shapes, cinematic scale changes, polished motion design | Its birds, exact palette combinations, proprietary compositions, characters, iconography, or distinctive scene designs |
| TED-Ed | Story structure, visual surprise, purposeful scene changes, rich animated sequences, visual explanations | Specific lesson artwork, recurring visual motifs, or a recognisable episode's compositions |
| MinuteEarth | Clear scientific storytelling, simple visual metaphors, approachable explanations | Its exact character designs, drawn line language, or branded layouts |
| TierZoo | An original framing device for ecology/evolution, consistent explanatory rules, memorable comparisons | Its game-interface concept, stats presentation, or specific visual jokes |
| AsapSCIENCE | Human, energetic delivery and accessible explanations | Its signature whiteboard/marker look or exact character designs |

**Our synthesis:** the cinematic visual world-building of an animated science documentary + the narrative clarity of an educational lesson + our own recurring researcher character + evidence-led science scripts.

## 3. Original brand concept

### 3.1 Brand name and logo

The brand name and logo are not defined by this document. Do not invent a final name or logo. Leave a clean, consistent title-card system for a later branding pass. Avoid generated logos and generated text in scene images.

### 3.2 Visual signature

Create a distinctive system with these traits:

- Clean, bold, vector-like silhouettes with controlled ink accents.
- Layered environments with foreground, middle ground, and background depth.
- Rounded geometric shapes mixed with scientifically recognisable anatomy and structures.
- Rich, controlled colour rather than a permanently dark palette.
- Strong focal hierarchy: one primary subject, one supporting idea, restrained background detail.
- Purposeful gradients and atmospheric lighting, not random glow on every object.
- Scientific cutaways, cross-sections, timelines, scale comparisons, and visual metaphors integrated into the same illustration language.
- Motion-friendly compositions with space for camera movement and editorial overlays.

The artwork may use a subtle paper/ink character, but must not look like a generic children's worksheet, stock vector pack, random flat-icon collage, or inconsistent collection of AI art styles.

---

# PART II — MASTER ART DIRECTION

## 4. Colour system

Use this starting palette as the channel's own design system. Colours may shift for a particular topic, but the image should retain a recognisable overall harmony.

| Token | Hex | Role |
|---|---|---|
| `INK_NAVY` | `#14283B` | Deep outlines, night scenes, high-contrast backgrounds |
| `OCEAN_TEAL` | `#287F83` | Water, biology, technology, secondary environment |
| `SKY_CYAN` | `#72BED0` | Atmosphere, highlights, scientific energy accents |
| `WARM_IVORY` | `#F4EBD8` | Light surfaces, diagrams, soft backgrounds |
| `CORAL` | `#E9785D` | Main accent, warning, focal emphasis |
| `GOLD` | `#E9B94F` | Discovery, warm light, selected highlights |
| `LEAF_GREEN` | `#70A878` | Ecology, organisms, vegetation |
| `VIOLET` | `#756AA2` | Space, deep time, abstract science accents |
| `CHARCOAL` | `#29343B` | Secondary darks, equipment and neutral shadows |

### Palette rules

- Use 3–5 dominant colours in one scene, plus neutrals. Do not force all palette colours into every frame.
- Use `CORAL` and `GOLD` sparingly so they retain emphasis.
- Use `INK_NAVY` for readable outlines and depth, not as a compulsory full-frame background.
- For serious or uncertain scientific topics, prefer restrained colours and clear evidence visuals over spectacle.
- Make the subject separable from the background at thumbnail size.
- Maintain sufficient luminance contrast for mobile viewing.

## 5. Shape language and line work

- Main forms: clean geometric masses, readable silhouettes, slightly softened corners.
- Organic subjects: natural asymmetry and correct anatomy; avoid mechanically perfect symmetry unless scientifically intended.
- Outlines: consistent dark ink contours, generally medium weight; stronger around the principal subject, lighter for distant detail.
- Detail density: high where it explains the science, low where it competes with the focal point.
- Avoid tiny decorative marks that become noise after 1080p scaling.
- Avoid random sketchiness, inconsistent stroke widths, plastic 3D surfaces, glossy photorealism, and unrelated rendering techniques in the same episode.

## 6. Lighting, depth, and atmosphere

Each scene should specify a lighting logic:

- Key light direction and warmth/coolness.
- Separation light or rim light only where it improves silhouette clarity.
- Atmospheric perspective: distant layers lower in contrast and detail.
- Contact shadows that make objects sit in the environment.
- Underwater, microscopic, cosmic, and ancient scenes each need a distinct but consistent atmospheric treatment.

Use three-layer depth where appropriate:

1. **Foreground:** silhouettes, particles, plants, objects, or framing elements; keep them from obscuring the subject.
2. **Midground:** the principal scientific event or subject.
3. **Background:** environment, scale cues, distant forms, or a gradient field.

Do not add particles, stars, bubbles, dust, or glows merely to fill empty space. Every decorative element needs a compositional purpose.

## 7. Composition rules

Every image prompt must define the intended shot and primary focal point.

Supported shot families:

- Extreme wide / establishing shot — environment, scale, geography, or context.
- Wide shot — full subject and meaningful environment.
- Medium shot — character or organism performing an action.
- Close-up — a feature that carries the sentence's meaning.
- Macro / microscopic — cells, tissues, structures, particles, mechanisms.
- Cross-section / cutaway — hidden internal structure.
- Top-down / isometric — systems, processes, maps, spatial explanation.
- Side-by-side comparison — differences across species, time, size, or conditions.
- Sequential visual — a process or causal chain; use a single coherent image, not a fake multi-panel layout unless the sentence explicitly calls for a comparison.
- Abstract metaphor — only when it clarifies a real scientific concept; do not let the metaphor imply a false mechanism.

### Composition quality gates

- One dominant focal point per image.
- Clear foreground/background separation.
- No accidental tangencies or confusing overlaps.
- Leave safe space for later editor-added labels when a diagram requires them.
- Keep key content away from the extreme edges so gentle zoom/pan does not crop it.
- Use deliberate variety in shot scale, camera angle, and subject placement across consecutive sentences.
- Never repeat the same composition just because the sentence is short.

## 8. Motion-ready art

Generated images are source plates for OpenMontage, not finished video frames. Design them so the editor can add motion:

- Place the main subject with enough surrounding space for a 3–8% push-in or pull-back.
- Use visible depth layers where possible; do not make every scene a flat centered poster.
- Prefer separable foreground objects and a readable background for 2.5D/parallax treatment.
- Avoid placing essential text inside generated art.
- For diagrams, generate the correct visual structure and add labels, arrows, numbers, and legends as editable SVG/graphics during post-production.
- Do not ask the image model to create an entire timeline or complex labelled diagram if the labels must be exact. Create a clean diagram plate, then build precise overlays in the editor.

---

# PART III — RECURRING HOST CHARACTER

## 9. Character role

The host is a **curious young science researcher**, not an all-knowing teacher. He guides the viewer through difficult topics, reacts to discoveries, demonstrates scale, and occasionally appears inside the scientific environment.

The host is a brand mascot and narrative guide. He must not appear in every frame. The subject of the science should remain the visual star.

## 10. Canonical appearance lock

Use the currently approved character-sheet image as the initial design reference, subject to the following canonical traits:

- Young adult appearance, approximately 20–25 years old.
- Tousled dark-brown hair with a recognisable silhouette.
- Round glasses; this is the primary identity anchor.
- Light/cream shirt, usually rolled sleeves.
- Dark navy/charcoal trousers.
- Practical shoes; optional dark backpack and science notebook.
- Friendly, curious, observant expression; expressive but not exaggerated into a babyish cartoon.
- Consistent head-to-body proportions, facial construction, hairline, glasses shape, shirt design, and palette.

Do not casually change age, gender presentation, hair colour, glasses, clothing, body proportions, or face structure between scenes. Costumes may change only when the story requires a historically or scientifically appropriate protective outfit; preserve the face, hair silhouette, and glasses where physically plausible.

## 11. Character reference pack

Create and store a canonical reference pack in the repository. Recommended structure:

```text
assets/reference/host/
  host_master_sheet.png
  host_front_full_body.png
  host_three_quarter.png
  host_profile.png
  host_back_view.png
  host_face_neutral.png
  host_expressions.png
  host_pose_library.png
  HOST_REFERENCE_NOTES.md
```

If the current reference sheet is a multi-panel collage, do not blindly feed the entire collage into every scene. Crop/select clean individual references for the specific purpose. A collage can cause the model to reproduce panel borders, multiple views, or sheet layouts in a final scene.

### Reference-use strategy

- For a host scene, use the canonical face/full-body reference best suited to the requested framing.
- For an action pose, include one appropriate pose reference if available.
- For scenes where the host is not required, do not attach the character reference; this saves input complexity and avoids unwanted character appearances.
- If the Flow frontend supports a reusable named Character, create it once and use the documented character mechanism (for example, `@Name`) only after checking the installed CLI help.
- The Gemini Nano Banana 2.1 API documentation describes up to 4 character reference images and up to 10 high-fidelity object references in one workflow, within an overall limit of 14 reference images. This is an API capability statement, not a guarantee that every Flow UI/CLI route exposes the same reference slots.

## 12. Character appearance schedule

Use the host intentionally:

- Opening: briefly introduces the question or appears as a scale guide.
- Chapter transitions: reappears when a new concept needs framing.
- Difficult explanation: points to, examines, or demonstrates a mechanism.
- Emotional beat: reacts to a surprising discovery, without replacing evidence.
- Ending: returns to close the narrative loop.

A starting planning target is around 10–20% of images containing the host. This is a creative starting range, not a rule from competitor analytics. Adjust by topic and pacing. Some episodes may use the host less; others may need more.

---

# PART IV — NANO BANANA RESEARCH AND OPERATING MODEL

## 13. What Nano Banana is

Nano Banana is Google's name for Gemini's native image-generation and image-editing capabilities. It is not a synonym for every image model available in Google Flow, and it is not automatically the same interface as the Gemini API.

As of the research date, Google's Gemini API documentation lists **Nano Banana 2.1** (`gemini-nano-banana-2.1`) as its latest high-efficiency image generation and conversational editing model. Google's model page was updated on 29 October 2026.

### Model family (official Gemini API names)

| Product name | API model ID | Intended role in this plan |
|---|---|---|
| Nano Banana 2.1 | `gemini-nano-banana-2.1` | Main workhorse for image generation and conversational edits |
| Nano Banana 2 Lite | `gemini-3.1-flash-lite-image` | Fast/low-cost volume where multiple references and multi-turn character editing are not central |
| Nano Banana 2 | `gemini-3.1-flash-image` | Previous generation; use only when a project/account requires it |
| Nano Banana Pro | `gemini-3-pro-image` | Premium-quality complex assets, detailed composition and controlled creative work |
| Original Nano Banana | `gemini-2.5-flash-image` | Legacy model; do not choose for a new pipeline unless required by compatibility |

**Important naming boundary:** these are official Gemini API model IDs. The `gflow-cli` command uses Flow model aliases, not necessarily these API IDs. The current upstream `gflow-cli` README documents `--model nano2` for Nano Banana 2.1 in Flow. Always verify the installed version's `gflow image t2i --help` before using an alias. Do not paste a Gemini API model ID into `gflow-cli` unless the installed CLI explicitly accepts it.

## 14. Nano Banana 2.1 capabilities relevant to this channel

Google's current official documentation describes these capabilities for Nano Banana 2.1 through the Gemini API:

- Text-to-image generation.
- Image input and image editing; text and reference images can be combined.
- Conversational, multi-turn editing, allowing a generated image to be refined while preserving unchanged elements.
- 1K, 2K, and 4K output sizes.
- Configurable output aspect ratio, including 16:9.
- Up to 14 total reference images in a workflow, including up to 4 character-reference images and up to 10 high-fidelity object-reference images.
- Improved prompt adherence, visual quality, text rendering, and multi-turn character consistency compared with the previous workhorse generation.
- Thinking levels (`minimal`, `medium`, `high`) in the Gemini API.
- Google Search/Image Search grounding in supported API workflows.
- Batch API support for image generation.

**Flow limitation:** a capability in the Gemini API does not mean it is exposed in Google Flow or `gflow-cli`. Flow's interface, account rollout, model picker, and installed CLI determine what is actually available. Do not invent `--thinking`, `--image-size`, `--seed`, `--reference-style`, `--batch-api`, or any other flag without local `--help` or source-code evidence.

## 15. Nano Banana 2.1 image dimensions and 16:9 choice

The official Gemini API table specifies these 16:9 sizes for Nano Banana 2.1:

| Requested API size | Dimensions |
|---|---:|
| 1K | 1376 × 768 |
| 2K | 2752 × 1536 |
| 4K | 5504 × 3072 |

The first Flow test image in this project was 1376 × 768, which is an appropriate 16:9 1K frame. For a 1080p YouTube documentary:

- Use 1K for initial tests and large-scale draft runs if visual quality is acceptable.
- Consider 2K for final image plates when the Flow account and CLI expose it and the quality gain justifies storage/time.
- Reserve 4K for selected hero assets, thumbnails, or crops that genuinely need it; do not assume every sentence frame requires 4K.
- Always request/verify 16:9. The Gemini API may default to a square if no ratio is supplied; Flow must be checked separately.

The current upstream `gflow-cli` Flow documentation reports five measured aspect ratios on its host: `16:9`, `4:3`, `1:1`, `3:4`, and `9:16`. It documents image counts of 1–4. This is narrower than the full Gemini API matrix and may vary by Flow frontend/account.

## 16. Nano Banana reference-image strategy

For high visual continuity, use reference images deliberately rather than attaching a large pile to every prompt.

### Reference hierarchy

1. **Character identity reference:** host face or full-body canonical view, only if the host is in the scene.
2. **Style reference:** use the approved original channel style board as a visual guide where supported. Do not assume Nano Banana 2.1 exposes a dedicated style-reference slot in Flow. In the Gemini API reference table, the explicit “up to 3 style references” category is listed for Nano Banana Pro, not Nano Banana 2.1.
3. **Object reference:** a recurring object, scientific instrument, specimen, or prop when exact appearance matters.
4. **Previous frame/reference:** only when the next frame must preserve a specific subject or continue/edit an existing image.

### Avoid reference overload

- Use the smallest number of references that accomplishes the task.
- Do not send a full multi-panel character sheet if a single clean character reference is enough.
- Do not attach the previous image merely because it exists; use it when continuity is actually required.
- Do not allow reference photos to override the scientifically correct scene requested by the sentence.
- Do not combine unrelated visual references with conflicting styles.

### Flow-specific reference constraints

The upstream `gflow-cli` README states that an image `--ref <uuid>` is resolved through the same Flow project/catalog, and that a reusable character can be tagged with `@Name`. Verify this in the installed version and the active Flow frontend before building a production job. The current README also states an existing Flow project is required at the transport boundary for the Nano Banana 2.1 image route described there.

---

# PART V — PROMPT ENGINEERING FOR NANO BANANA

## 17. Prompt philosophy

Nano Banana is a multimodal instruction-following model, not a classic diffusion model that must be prompted as a bag of weighted keywords. Prefer clear natural-language direction with enough context to explain:

- why the image exists in the story;
- what exact scientific idea it must communicate;
- what is visible and what is not;
- the subject's action/state;
- environment and period/scale;
- camera and composition;
- lighting, colour, and visual medium;
- which identity/reference must remain unchanged.

Be specific about the scene, but do not create a paragraph of mutually competing visual adjectives. A prompt should have one dominant visual task.

## 18. Standard prompt structure

Every production prompt should be built from the following fields in this order:

1. **Story purpose:** what this frame explains in the episode.
2. **Sentence meaning:** the exact idea from the narration, restated visually.
3. **Main subject:** one dominant organism/object/process.
4. **Action/state:** what the subject is doing or what is happening.
5. **Scientific environment:** habitat, scale, era, or physical context.
6. **Shot and camera:** wide/medium/close/macro, angle, perspective, movement-safe framing.
7. **Composition:** focal point, foreground/midground/background, negative space.
8. **Channel art direction:** original clean vector-like forms, controlled ink outlines, colour and light system.
9. **Continuity requirements:** character/reference traits that must be preserved, when applicable.
10. **Output constraints:** 16:9, one cohesive frame, no embedded captions or labels.

### Prompt skeleton

```text
Create one finished 16:9 frame for an original animated science documentary.

STORY PURPOSE: [what the viewer should understand from this frame].
SENTENCE MEANING: [faithful visual interpretation of this exact sentence].
MAIN SUBJECT: [one clearly defined subject].
ACTION / STATE: [what is happening].
ENVIRONMENT: [place, era, scale, scientific context].
SHOT: [wide / medium / close-up / macro / cross-section / isometric], [camera angle and perspective].
COMPOSITION: [single focal point, foreground, midground, background, safe margins].
ART DIRECTION: original clean vector-like science-documentary illustration; bold controlled ink contours; geometric yet organic shapes; layered depth; coherent channel palette; crisp readable silhouettes; polished cinematic lighting; detailed only where it explains the subject.
CONTINUITY: [exact approved character/object traits, or "no host character in this frame"].
OUTPUT: one coherent image, landscape 16:9, no panels, no captions, no letters, no labels, no logo, no watermark. Leave any required label areas clean for editor-added graphics.
```

## 19. Prompting rules specific to Nano Banana

- Describe the purpose and context, not only the object. “A cell” is too broad; explain what biological process this sentence is teaching.
- State the intended visual result positively. Prefer “an empty, undisturbed ocean floor” over a long list of prohibited objects.
- Use explicit camera terms such as wide-angle view, overhead view, macro close-up, low-angle perspective, or cross-sectional view.
- For complex scenes, give an ordered sequence of spatial instructions: background first, then main subject, then foreground details.
- When editing an existing image, state what must change and what must remain unchanged. Example: “Keep the character's face, glasses, hairstyle, clothing, lighting and camera angle unchanged; only replace the object in his left hand.”
- Iterate with focused edits, not a completely rewritten prompt, when a successful image needs one correction.
- For a new angle of an existing character, include the prior successful reference and request the angle change only.
- Do not ask the model to produce exact scientific labels inside an image. Add exact wording later as editable graphics.
- Do not rely on the model to obey a requested number of output images. For this project, make one sentence one job and request one image (`count=1`) per job, then verify the returned file count.
- Nano Banana can generate text in images, but the channel's production policy is to keep generated scene art text-free unless a very specific editorial exception is approved.

## 20. Prompt examples by visual type

### 20.1 Host introduction

```text
Create one 16:9 frame for an original animated science documentary. Show our approved young adult science researcher with the exact same dark tousled hair, round glasses, cream shirt and dark trousers as the supplied character reference. He stands on a rocky overlook, holding an open field notebook and looking toward a vast prehistoric landscape. Wide cinematic establishing shot, host placed on the right third, expansive environment visible on the left, strong depth layers, crisp clean silhouette. Original polished vector-like science-documentary illustration, controlled ink contours, warm ivory, teal, navy and restrained coral accents. Preserve the character identity precisely. One cohesive frame; no text, no panels, no labels or logo.
```

### 20.2 Biological mechanism

```text
Create one 16:9 scientific cutaway illustration explaining [specific mechanism from the sentence]. Show [correct structures] in the correct spatial relationship, with [the event/process] as the single focal point. Three-quarter cutaway view, readable silhouette, simplified but scientifically recognisable anatomy, controlled depth, original clean vector-like science-documentary art, ink outlines and the channel palette. Leave clear space for editable labels to be added in post-production. No text or labels inside the generated image.
```

### 20.3 Evolution / deep time

```text
Create one 16:9 cinematic scientific illustration for the sentence: [sentence]. Depict [specific organism or evolutionary feature] in [scientifically grounded environment and time period]. The visual must communicate [the relevant adaptation or ecological relationship] without inventing anatomy or implying an unsupported direct ancestor-descendant relationship. Wide-to-medium composition, layered environment, distinctive silhouette, original vector-like documentary art, controlled outlines, coherent palette, no text.
```

### 20.4 Microscopic / cellular

```text
Create one 16:9 macro scientific illustration showing [specific cell/tissue/process]. The viewer must immediately understand [the sentence's central relationship]. Use a clean cutaway/macro perspective, clearly separated structures, restrained depth of field and high contrast between the key components. Original stylised vector science-documentary art with controlled ink contours and the channel palette. Scientifically plausible proportions and connections; no labels, words or decorative pseudo-scientific symbols.
```

### 20.5 Scale comparison

```text
Create one coherent 16:9 visual comparison of [A] and [B] at a scientifically accurate relative scale. Use a shared baseline and consistent perspective, with enough surrounding space for editor-added scale labels. Make the scale difference instantly readable without adding inaccurate objects or distorted proportions. Original clean vector-documentary art, crisp silhouettes and limited colour accents. No text or numbers.
```

### 20.6 Diagram plate

```text
Create a clean, editable-looking 16:9 scientific diagram plate explaining [process]. Show only these required components: [component list] and their correct relationships: [relationship list]. Use simple but accurate shapes, clear directional flow, high contrast, generous empty label areas, and the channel's vector/ink art direction. Do not generate labels, text, numbers, arrows with letters, legends, or decorative pseudo-data; those will be added by the editor.
```

---

# PART VI — THE ONE-SENTENCE / ONE-IMAGE SYSTEM

## 21. Immutable mapping

For every final narration sentence, create exactly one image record:

```text
S0001 → one final sentence → one unique prompt → one image file
S0002 → one final sentence → one unique prompt → one image file
S0003 → one final sentence → one unique prompt → one image file
```

No image may be reused for two sentence IDs. No sentence may be silently skipped. If one sentence is too abstract to depict literally, create one scientifically faithful metaphorical image for that sentence and document the metaphor.

This rule does not mean the host must appear in every image. It means there must be one new unique visual asset for every final narration sentence.

## 22. Sentence segmentation

- Segment the approved final voice-over script, not an early draft.
- Use a deterministic sentence splitter with protection for abbreviations, citations, decimal numbers, initials, and quoted sentences.
- Preserve the exact narration text and punctuation in the record.
- Do not automatically split one sentence into two image jobs because it is long. If a sentence contains multiple clauses, identify its main visual claim and build one coherent scene around it.
- If a sentence truly contains two independent visual claims, flag it for script revision before generation; do not silently violate the one-sentence/one-image rule.
- Assign stable IDs such as `S0001`, `S0002`, etc. IDs must not change if a later unrelated sentence is added; use a versioned script or stable UUID mapping.

## 23. Per-sentence visual record

Each sentence record must contain at least:

- `sentence_id`
- `script_version`
- `chapter_id`
- `sentence_text`
- `previous_sentence_context`
- `next_sentence_context`
- `scientific_claim_ids`
- `visual_intent`
- `shot_type`
- `composition_plan`
- `host_present` (boolean)
- `character_reference_ids`
- `object_reference_ids`
- `image_model_alias`
- `aspect_ratio` (normally `16:9`)
- `requested_count` (always `1`)
- `prompt_version`
- `prompt_text`
- `generation_status`
- `attempt_number`
- `output_file`
- `file_hash`
- `width`, `height`, `format`
- `qc_status`, `qc_notes`
- `audio_start`, `audio_end`, `duration`
- `editor_motion_preset`

## 24. Example JSON manifest

This is an **OpenMontage internal schema example**, not a claim that the same JSON structure is accepted directly by `gflow-cli`. The adapter must transform it into the exact manifest/CLI arguments confirmed by the installed version.

```json
{
  "project_id": "episode-001",
  "script_version": "v1",
  "rule": "one_sentence_one_image",
  "aspect_ratio": "16:9",
  "sentences": [
    {
      "sentence_id": "S0001",
      "sentence_text": "The ocean covers most of our planet.",
      "visual_intent": "Establish the scale of the global ocean.",
      "shot_type": "extreme_wide",
      "host_present": false,
      "image_model_alias": "nano2",
      "requested_count": 1,
      "prompt_version": 1,
      "prompt_text": "...",
      "generation_status": "DRAFT",
      "output_file": "assets/generated/S0001.png",
      "qc_status": "PENDING"
    },
    {
      "sentence_id": "S0002",
      "sentence_text": "But its deepest regions remain mysterious.",
      "visual_intent": "Reveal the scale and darkness of the deep ocean.",
      "shot_type": "wide",
      "host_present": false,
      "image_model_alias": "nano2",
      "requested_count": 1,
      "prompt_version": 1,
      "prompt_text": "...",
      "generation_status": "DRAFT",
      "output_file": "assets/generated/S0002.png",
      "qc_status": "PENDING"
    }
  ]
}
```

## 25. Uniqueness and duplicate protection

- A separate image job is created for each sentence ID.
- `requested_count` must be `1`.
- Output paths are deterministic by sentence ID and attempt number.
- Store a cryptographic hash (SHA-256) of every output file.
- If two different sentence IDs produce byte-identical images, flag them for review; do not automatically accept both.
- Also run visual similarity detection to find near-duplicates with different file encodings. Similarity detection is a warning, not an automatic rejection, because two related sentences may legitimately share a subject while needing different views.
- A regeneration creates a new attempt record, not a silent overwrite.
- Never mark a record completed until a valid image file exists and passes basic checks.

---

# PART VII — IMAGE GENERATION WORKFLOW

## 26. Production stages

### Stage A — Creative research and script lock

1. Research the episode question and collect reliable sources.
2. Build a claim ledger: measured facts, estimates, hypotheses, and unknowns must be labelled distinctly.
3. Write the full narration and verify every factual claim.
4. Approve the script version.
5. Only then segment into sentences and create visual records.

### Stage B — Visual planning

1. Analyse the script and divide it into narrative chapters.
2. Define the visual idea for every sentence.
3. Assign a shot type and subject.
4. Check shot variety across neighbouring sentences.
5. Decide whether the host appears.
6. Identify any recurring organism, object, environment, or prop requiring a reference.
7. Generate prompt drafts and run prompt QA before any real Flow job is approved.

### Stage C — Reference preparation

1. Load the approved host reference only where needed.
2. Prepare recurring object/organism references.
3. Keep a versioned episode style board.
4. Confirm that supplied references are cropped/clean, relevant, and not contradictory.
5. Check the exact reference mechanism supported by the installed `gflow-cli` and current Flow frontend.

### Stage D — Model and command preflight

Before any generation, inspect the installed environment. Safe checks should include:

```bash
gflow --version
gflow image --help
gflow image t2i --help
gflow image i2i --help
gflow image batch --help
gflow character --help
gflow project --help
gflow credits user
```

Only run commands that exist in the installed version. If a subcommand differs, use `gflow --help` and the installed source/entry points to find its actual form.

The upstream README includes this Nano Banana 2.1 Flow example:

```bash
gflow image t2i "A clean, cinematic 16:9 science-documentary illustration of ..." --aspect 16:9 --model nano2
```

For this project, the adapter must additionally request one output (`--count 1`) only if the installed `gflow image t2i --help` confirms that exact option. If the installed command has no count option, use its documented single-output default and verify that exactly one image was written. Never guess flag spelling or option order.

Confirm all of the following before production:

- Installed version and installation source.
- Whether `--model nano2` is accepted by this installed version.
- Whether Nano Banana 2.1 is selected in the actual Flow host/account, rather than merely assumed from an alias.
- Which aspect ratios are available. Require `16:9` for this project.
- Whether a count argument exists and how its outputs are saved.
- Whether local references, catalog UUID references, and named Characters are supported on this host.
- Which Flow project is required and how to specify it.
- Output directory and file format.
- Current credit/usage display and whether the operation consumes any quota/allowance.
- Whether the active `--no-spend` protection still blocks video-generating actions.

**Never infer a model from a filename or marketing phrase.** Record the selected model and host in the job log.

### Stage E — Prompt review

- Validate every prompt against the style and scientific-accuracy rules.
- Ensure each prompt expresses one main visual idea.
- Check the sentence ID, prompt ID, and output path.
- Check that no sentence has an empty prompt.
- Check that no prompt is unintentionally duplicated.
- Check that neighbouring shots do not repeat the same composition.
- Verify all references exist and belong to the intended project.

### Stage F — Controlled generation

- Generate one image per sentence job, with requested count `1`.
- Batch jobs only through the exact supported mechanism in the installed CLI.
- Start with small batches and verify file output before scaling.
- Do not launch many independent browser/Playwright sessions against the same Flow profile.
- Use sequential processing first; only introduce limited concurrency after a measured stability test proves it safe.
- Persist each job before submission.
- Capture the command, model alias, project ID, prompt, timestamp, return code, output path, and result.
- Do not automatically resubmit after an ambiguous timeout; check Flow state and local output first to avoid accidental duplicate work.

### Stage G — Asset validation

For each output:

- File exists and is non-empty.
- Image decodes successfully.
- Width and height are valid.
- Aspect ratio is 16:9 within an accepted tolerance, or an approved crop rule is recorded.
- Output is actually an image, not an HTML/error response saved as `.png`.
- File hash and image ID are recorded.
- The image matches the intended sentence and reference identity.
- No accidental contact sheet, extra panel, UI screenshot, or unwanted text is present.

### Stage H — Human review and approval

For the first episodes, require human review of every generated frame before the final render. Later, automated QC may pre-filter obvious errors, but it must not silently approve scientific inaccuracies or character-identity failures.

---

# PART VIII — BATCHING, COST CONTROL, AND RECOVERY

## 27. Batch strategy

The workflow may contain 150–250+ separate image jobs depending on the final script's sentence count. Do not assume one batch can safely contain all jobs.

- Use the installed CLI's supported batch or manifest workflow.
- Keep each sentence as an independent record even when submitted in a batch.
- Begin with a 5–10 sentence smoke test using a mock provider, then a separately approved small real-image test if authorised.
- Batch size must be set from actual CLI limits and observed stability; it is not hard-coded from a different version or API.
- Save batch manifest and result mapping before and after execution.
- If the batch fails part-way through, reconcile successful outputs against sentence IDs and submit only missing/failed records after checking Flow status.

### Important distinction: two different batch systems

1. **Google Gemini API Batch API:** an official API job mechanism; Google's docs describe higher rate limits with a turnaround that can be up to 24 hours. It is not automatically the same as Flow's batch command.
2. **gflow-cli/Google Flow batching:** a CLI/Flow workflow whose exact manifest syntax, batch size, timing, and result format must be read from the installed package's documentation and help output.

Do not pass a Gemini API batch JSON file directly to `gflow-cli` unless the CLI explicitly documents that format.

## 28. Cost and credit safeguards

- Never assume image generation is permanently free or unlimited.
- Check the live Flow account and the installed CLI documentation before real production.
- The public `gflow-cli` documentation describes image/composition operations as credit-free in one section, while its PyPI description also warns that generations are subject to the account's Flow allowance. Account plans, Flow rollout, and product billing can change. Treat the live account UI and current release behaviour as authoritative for the actual run.
- Veo video generation is a separate, credit-sensitive operation. Do not invoke it as part of an image-only production job.
- Keep `--no-spend` and the MCP Security Proxy active.
- No real job can move from READY_FOR_APPROVAL to APPROVED without the user's explicit approval.
- No hidden retries, no automatic video generation, no test generation outside the approved test plan.

## 29. Recovery rules

- Persist job state before submission.
- Use a stable job ID derived from episode ID + sentence ID + prompt version.
- Store each attempt independently.
- If process exits during generation, inspect the Flow project/library and output folder before retrying.
- Mark a job `UNKNOWN` after an ambiguous result, not `FAILED` or `COMPLETED` until reconciled.
- A resumed run skips only verified completed assets.
- Failed/low-quality assets are regenerated only after the reason is logged and the replacement prompt/version is saved.
- Preserve all successful outputs; never delete a valid image just because a later attempt is better.

---

# PART IX — IMAGE QUALITY CONTROL

## 30. QC rubric

Score each image from 0–5 on each dimension and apply the weights below. The score is a practical internal tool, not a model capability guarantee.

| Dimension | Weight | Review question |
|---|---:|---|
| Sentence meaning | 30% | Does the image clearly represent the exact sentence's central idea? |
| Scientific correctness | 20% | Is anatomy, scale, chronology, physics, and causal implication sound? |
| Style consistency | 15% | Does it match the approved original channel art direction? |
| Composition/readability | 15% | Is there one clear focal point and a readable silhouette at 1080p? |
| Continuity | 10% | Are recurring characters/objects correct and consistent? |
| Motion readiness | 5% | Can the editor animate it without cropping the key idea? |
| Artifact/text cleanliness | 5% | Are there malformed structures, accidental words, watermarks beyond provider marks, or broken details? |

Suggested initial acceptance rule: weighted score of 4.0/5 or higher, with no critical scientific error. A low score can be overridden only by a documented human decision, not silently.

### Hard reject conditions

- Wrong species, anatomy, process direction, or historical period.
- Image communicates the opposite of the sentence.
- Character identity is materially wrong where the host is required.
- Multiple panels/contact sheet when one frame was requested.
- Unrequested typography, logos, random pseudo-labels, or fabricated data.
- Duplicate/near-duplicate composition that adds no new information.
- Image dimensions/format cannot be used by the renderer.

## 31. Visual variety audit

For each episode, produce a contact sheet and report:

- shot-type distribution;
- dominant colour distribution;
- host appearance frequency;
- repeated composition warnings;
- repeated background/environment warnings;
- consecutive frames with near-identical framing;
- frames where the main subject is too small or obscured.

A variety audit should improve storytelling, not force random variation. Repetition is acceptable when the story intentionally compares the same subject across a sequence, but the change must be meaningful and visible.

---

# PART X — MOTION, EDITING, AND NARRATION SYNC

## 32. Voice-over is the timing master

The final voice-over recording is the timing source. Do not assign equal fixed duration to every image.

1. Generate/approve the final voice-over.
2. Align the audio to the exact sentence text using word/sentence timestamps.
3. Assign each image its sentence's `audio_start` and `audio_end`.
4. Add transitions without making the image mapping ambiguous.
5. If timing changes after audio edits, recompute timestamps and update the edit manifest.

### Sentence-to-image duration

The displayed duration of an image equals the timing interval of its sentence, except for small editorial transition overlaps. The next image must become the active visual at the next sentence boundary. Do not stretch an image over several unrelated sentences just to fill runtime.

## 33. Motion presets

Build a small controlled motion library, not random movement on every frame.

| Preset | Appropriate use |
|---|---|
| `slow_push_in` | Discovery, close detail, growing tension |
| `slow_pull_out` | Reveal scale or context |
| `pan_left` / `pan_right` | Wide environments and long structures |
| `tilt_up` / `tilt_down` | Tall organisms, anatomy, planetary structures |
| `macro_drift` | Microscopic/cellular art, with stable focal point |
| `parallax_2_5d` | Scenes with separable foreground/midground/background layers |
| `static_hold` | Complex diagrams, dense facts, important comparisons |
| `gentle_orbit` | Spatial objects where camera orbit will not distort scientific relationships |

Rules:

- Motion must support the sentence, not distract from narration.
- Use easing at the start/end of moves.
- Avoid constant zoom on every shot; alternate motion with static holds.
- Avoid camera movement that changes the apparent scale relationship in a scientific comparison.
- Do not invent missing details through generative fill unless explicitly approved and visually reviewed.
- Use layer-based parallax only when the source layers can be separated safely.

## 34. Graphics and labels

All exact scientific labels, numbers, units, arrows, legends, titles, captions, and source notes must be added in the editor as editable text/graphics, unless a deliberate one-off exception is approved.

This avoids misspellings, incorrect numbers, and inconsistent typography from the image model. Maintain one typography system and one set of diagram conventions across episodes.

## 35. Sound design

- Use clear, intelligible narration as the dominant audio layer.
- Use restrained documentary music that supports emotional pacing without masking speech.
- Add sound effects to meaningful transitions, discoveries, impacts, or environmental scenes.
- Avoid a sound effect on every image change.
- Maintain consistent loudness, safe peaks, and clean edits.
- Use only music/SFX that the channel has rights to use commercially.

---

# PART XI — RECOMMENDED OPENMONTAGE ARCHITECTURE

## 36. Pipeline map

The expected high-level pipeline is:

```text
RESEARCH + CLAIM LEDGER
        ↓
APPROVED SCRIPT (versioned)
        ↓
SENTENCE SEGMENTATION + STABLE IDs
        ↓
VISUAL STORYBOARD (one record per sentence)
        ↓
STYLE / CHARACTER / SCIENCE VALIDATION
        ↓
NANO BANANA PROMPT BUILDER
        ↓
FLOW JOB MANAGER (DRAFT → VALIDATED → READY_FOR_APPROVAL)
        ↓ explicit user approval
GFlow Adapter → Google Flow / Nano Banana 2.1
        ↓
OUTPUT RECONCILIATION + FILE VALIDATION
        ↓
IMAGE QC + CONTACT SHEET + HUMAN REVIEW
        ↓
FINAL VOICE-OVER + SENTENCE ALIGNMENT
        ↓
MOTION / GRAPHICS / MUSIC / SOUND DESIGN
        ↓
RENDER + TECHNICAL QC
        ↓
FINAL MP4 + PRODUCTION REPORT
```

## 37. Module responsibilities

Use existing OpenMontage modules where possible; do not make duplicate modules simply to match the names in this guide.

| Existing/planned module | Responsibility |
|---|---|
| `script_analyzer.py` | Sentence segmentation, topic/claim mapping, narrative analysis |
| `scene_planner.py` | Visual beat planning, chapter and shot distribution |
| `visual_director.py` | Enforce palette, composition, style, variety and host scheduling |
| `character_consistency_manager.py` | Character references, fixed traits, recurring object identity |
| `prompt_engineer.py` | Build Nano Banana-compatible natural-language prompts from structured visual records |
| `flow_integration.py` / GFlow adapter | Call only verified CLI capabilities, map job IDs to outputs |
| `flow_job_manager.py` | Approval gate, state, deduplication, audit trail, spending safeguards |
| `quality_control.py` | Image validation, scientific/visual checks, contact sheet and reports |
| `audio_sync` | Sentence timestamps mapped to image IDs |
| `render_integration` | Assemble visual frames, motion, audio, graphics and MP4 |

## 38. Suggested output folder structure

```text
projects/<episode_id>/
  research/
    sources.md
    claim_ledger.json
  script/
    narration_v1.md
    sentences_v1.json
  visual/
    storyboard.json
    prompt_manifest.json
    prompt_review.md
    contact_sheets/
  references/
    style_board.png
    host/
    objects/
  assets/
    generated/
      S0001.png
      S0002.png
    attempts/
    approved/
  audio/
    narration.wav
    sentence_alignment.json
    music/
    sfx/
  edit/
    production_manifest.json
    motion_plan.json
    graphics/
  renders/
    preview.mp4
    final.mp4
  reports/
    generation_report.json
    qc_report.md
    render_report.md
```

The implementation may use a different established directory convention, but it must preserve the same traceability and separation of concerns.

---

# PART XII — IMPLEMENTATION AND ACCEPTANCE PLAN

## 39. Phase 0: inspect before changing code

The coding agent must first read:

- `PROJECT_STATE_HANDOFF.md`;
- `docs/GFLOW_CLI_COMPLETE_GUIDE.md`;
- `docs/AUTONOMOUS_VIDEO_PRODUCTION_GUIDE.md`;
- `docs/PROJECT_READINESS_AUDIT.md`;
- the installed `gflow-cli` help and source;
- existing OpenMontage preproduction, Flow, audio, render, QC and test modules.

Verify facts in the running environment. The public upstream repository may have changed since the installed build. Never assume the latest upstream README exactly matches the installed package.

## 40. Phase 1: visual system prototype (no external generation)

Create ten mock sentence records and ten mock prompts. Check:

- all prompts follow the standard structure;
- exactly one prompt exists per sentence;
- shot types vary intentionally;
- host appears only where storyboard requires it;
- prompts do not contain conflicting style instructions;
- diagram text is reserved for post-production;
- the episode contact sheet has a coherent palette and composition rhythm.

Use mock images or locally available test fixtures only. Do not call Google Flow.

## 41. Phase 2: approved single-image qualification test

Only after user approval, run one real generation for one test sentence. It must:

- select and log the Nano Banana model actually shown by Flow;
- use 16:9;
- request one output;
- use the exact supported CLI syntax;
- save one result with its sentence ID;
- verify the file and dimensions;
- record actual quota/credit behaviour;
- verify that `--no-spend` and approval protections remain intact.

Do not run a batch until this single-image test passes visual and technical QC.

## 42. Phase 3: 10-sentence pilot

After a separate explicit approval, use 10 sentences to verify:

- 10 independent sentence IDs;
- 10 unique prompt records;
- 10 separate generation jobs, each requesting one image;
- 10 validated, distinct image files;
- reference identity on host scenes;
- no accidental panel/sheet results;
- successful resume after a mock interruption;
- valid voice-over alignment and a short MP4 preview.

## 43. Phase 4: full episode

Only after the pilot passes:

- approve the full visual manifest;
- generate in verified batches;
- QC every output;
- regenerate only failed records;
- synchronise with final voice-over;
- render a low-resolution preview;
- inspect pacing, transitions, image changes and sound;
- render the final MP4;
- archive manifests, prompts, source ledger, outputs and reports.

## 44. Definition of done

An episode is complete only when all conditions are true:

- Every final narration sentence has one stable sentence ID.
- Every sentence ID has exactly one approved unique final image.
- No sentence is missing an image; no image is assigned to multiple sentences.
- All outputs are valid 16:9 assets at approved dimensions.
- Character identity is consistent in all host appearances.
- Scientific visuals have been checked against the claim ledger.
- All exact labels/numbers are editor-created and verified.
- Each image's display interval matches its sentence's audio interval.
- Motion and transitions are smooth and do not distort scientific relationships.
- Audio mix passes QC.
- Final MP4 has the intended 20–25-minute duration and 16:9 format.
- Generation, retry, model, prompt, credit and QC logs are archived.
- All user approval and Flow safety gates were respected.

---

# PART XIII — IMPORTANT CAPABILITY BOUNDARIES

## 45. Do not mix up these three systems

### A. Gemini API

Official Google API with official model IDs, documented image sizes, response formats, reference-image input, multi-turn editing, search grounding and Batch API. It may require a separately configured API key and billing/quota arrangement. This project must not silently start using it as a fallback.

### B. Google Flow

The Google product/interface where the user's account is authenticated. Its available model choices, project requirements, output ratios, reference handling and account quota depend on the current Flow host and account rollout.

### C. gflow-cli

An unofficial, alpha command-line automation project that controls Google Flow through browser automation and internal/undocumented Flow interfaces. It is not an official Google API SDK. Its commands and exposed model aliases are version- and host-dependent.

**Never assume a capability documented for A is exposed by B or C.** The adapter must detect supported features and fail closed when unsupported.

## 46. Known current upstream gflow-cli facts to verify locally

The current public upstream README (research date 2 November 2026) reports:

- Nano Banana 2.1 support through the Flow model alias `nano2`, plus 2 Lite and Pro options;
- five measured image aspect ratios on the described Flow host: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`;
- image count range 1–4;
- T2I, I2I, upload, upscale and batch image operations;
- reusable Characters and character tagging via `@Name`;
- a Flow project requirement at the transport boundary for the described image route;
- `--ref <uuid>` resolution when the image is present in the same Flow project/catalog;
- different capabilities on different Flow frontends/accounts.

These are upstream facts, not a substitute for checking the user's installed `0.92.0` environment. The installed package's `--help`, local code and a deliberate approved qualification test are the authority for what can actually run in this Codespace.

## 47. Explicit non-goals

- Do not reproduce Kurzgesagt or any other channel's protected visual assets.
- Do not put generated words, subtitles, labels, numbers, logos, or watermarks into normal scene images.
- Do not use Veo for every sentence; the main design is still-image plates plus OpenMontage motion.
- Do not assume image-generation credits are free forever.
- Do not call Gemini API as an unapproved fallback to Flow.
- Do not generate all images in one giant uncontrolled browser session.
- Do not reuse a single image across multiple sentences.
- Do not use the host as a compulsory subject in every frame.
- Do not approve images solely because they look attractive; they must explain the science.

---

# PART XIV — REFERENCE SOURCES

The following primary sources were checked on **2 November 2026**. Re-check them before implementation because model names, feature flags, Flow rollouts, and billing can change.

1. Google AI for Developers — [Nano Banana image generation documentation](https://ai.google.dev/gemini-api/docs/image-generation). Official model list, prompt guidance, multi-turn editing, image/reference inputs, batching, image-size and aspect-ratio tables, and limitations.
2. Google AI for Developers — [Gemini Nano Banana 2.1 model page](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1). Official model ID, capabilities, supported inputs/outputs, Batch API support and 29 October 2026 update timestamp.
3. Google Blog — [Image editing in Gemini gets a major upgrade](https://blog.google/products-and-platforms/products/gemini/updated-image-editing-model/). Background on conversational editing and identity consistency in the Nano Banana family.
4. gflow-cli upstream — [GitHub repository and README](https://github.com/ffroliva/gflow-cli). Unofficial Flow CLI, supported commands, model alias, Flow-host limitations and alpha status.
5. gflow-cli package — [PyPI gflow-cli 0.92.0](https://pypi.org/project/gflow-cli/0.92.0/). Installed/released package description and release metadata; still verify the actual Codespace executable.

---

## Final operating principle

**The script determines what the image must communicate. The art direction determines how it should look. Nano Banana produces the image. OpenMontage makes it move and synchronises it to narration. The QC system decides whether it is good enough.**

No stage may silently replace the purpose of another stage.
