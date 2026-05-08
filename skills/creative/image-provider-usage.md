# Image Provider Usage for OpenMontage

> How to choose between image generation and stock providers, and how to use each effectively.
> Supplements the existing `image-gen-usage.md` (which covers FLUX prompting in depth).

## Provider Landscape

### Generation Providers (AI creates the image)

| Tool | Provider | Cost | Speed | Best For |
|------|----------|------|-------|----------|
| `flux_image` | FLUX 2 Pro via fal.ai | ~$0.03-0.05 | ~5-10s | Photorealism, general purpose, workhorse |
| `gemini_image` | Gemini 2.5 Flash Image / 3 Pro Image Preview (Google) | ~$0.04 (Flash) / ~$0.10 (3 Pro) | ~5-15s | Iterative variants (Flash); precision text-heavy / brand-fidelity / strict prompt adherence (3 Pro) |
| `google_imagen` | Imagen 4.0 (Google) | varies by tier | ~5-10s | Photorealism via Imagen family (separate from Gemini native image) |
| `grok_image` | Grok Imagine Image (xAI) | $0.02/output + $0.002/input edit image | ~5-15s | Image edits, style transfer, multi-image compositing |
| `openai_image` | GPT Image 1 (OpenAI) | ~$0.01-0.17 | ~5-15s | Complex instructions, text in images, multi-element |
| `recraft_image` | Recraft V4 via fal.ai | ~$0.04-0.25 | ~5-10s | Logos, SVG vectors, brand assets, text rendering (see caveat below) |
| `local_diffusion` | Stable Diffusion (local) | Free | ~30s+ | Offline, privacy, free |
| `image_gen` | Multi (legacy, deprecated) | Varies | Varies | **Deprecated** — use `image_selector` or per-provider tools |

### Stock Providers (search and download existing images)

| Tool | Provider | Cost | Speed | Best For |
|------|----------|------|-------|----------|
| `pexels_image` | Pexels | Free | ~2-5s | High-quality photography, color filtering |
| `pixabay_image` | Pixabay | Free | ~2-5s | Large library, category filtering, illustrations |

### Selector

| Tool | Purpose |
|------|---------|
| `image_selector` | Routes to the best available provider based on preference and availability |

## Provider Selection by Scene Type

| Scene Type | Primary Provider | Why | Fallback |
|-----------|-----------------|-----|----------|
| **Real-world photo** (city, nature, people) | `pexels_image` | Real photos > AI for realism | `pixabay_image` → `flux_image` |
| **Technical diagram** | `diagram_gen` | Structured, editable | `flux_image` with diagram prompt |
| **Abstract/conceptual illustration** | `flux_image` | AI excels at custom concepts | `openai_image` |
| **Style transfer / repaint of an existing image** | `grok_image` | Native edit flow, strong promptable transforms | `openai_image` |
| **Multi-image merge / composite** | `grok_image` | Can combine multiple source images into one scene | `openai_image` |
| **Logo or brand asset** | `recraft_image` | SVG support, text accuracy | `openai_image` |
| **Image with text/labels** | `gemini_image` (model=`gemini-3-pro-image-preview`) | Newest precision text rendering | `openai_image` (GPT Image 1) → `recraft_image` |
| **Complex multi-element composition** | `gemini_image` (model=`gemini-3-pro-image-preview`) | Strict prompt adherence on multi-constraint prompts | `openai_image` → `flux_image` |
| **Fast iterative variants of a brand asset** | `gemini_image` (model=`gemini-2.5-flash-image`, default) | Cheap + fast for "give me 4 takes on this concept" | `flux_image` |
| **Hero image (key visual)** | `flux_image` | Highest visual quality | `openai_image` |
| **Thumbnail** | `flux_image` or `recraft_image` | Needs to be eye-catching | — |
| **Budget/free project** | `pexels_image` or `pixabay_image` | Free, immediate | `local_diffusion` |
| **Offline/air-gapped** | `local_diffusion` | No network needed | — |

## Provider-Specific Caveats

### Recraft V4 via fal.ai
- **`style` parameter causes 422 errors** (as of 2026-04). The `style` enum values (`digital_illustration`, `realistic_image`, etc.) are rejected by fal.ai's Recraft V4 endpoint. **Workaround:** encode style direction in the prompt text instead (e.g. "digital illustration of a tooth cross-section" rather than `style="digital_illustration"`). The `image_size` and `colors` parameters work fine.
- **Text rendering is unreliable for exact business names.** Recraft (like all AI image models) may hallucinate wrong text. For any scene where text must be verbatim (CTA screens, business names, phone numbers), use Remotion `text_card` instead of generating an image with text.

### Gemini Image (`gemini_image`, added 2026-05-08)
- **Two-tier model:** default `gemini-2.5-flash-image` (~$0.04/image, fast iteration); upgrade to `gemini-3-pro-image-preview` (~$0.10/image) for text-heavy / strict-composition / brand-fidelity work. Mirrors the OpenSwarm pattern of using Flash for variants and 3 Pro for precision.
- **Aspect ratios:** broader than OpenAI (`1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`).
- **Pair with QC auto-fix loop** — see `image-qc-autofix.md`. The recommended pattern is: generate with `gemini-2.5-flash-image` → run QC → if any check fails, auto-retry once with `gemini-3-pro-image-preview` for the precision pass.
- **Distinct from `google_imagen`** — that tool covers the Imagen 4.0 family (`imagen-4.0-generate-001`, `*-ultra`, `*-fast`); `gemini_image` covers Gemini's native multimodal image generation.

## Cost-Quality Tradeoff

```

PRODUCTION PATH: Premium
├── Hero images: flux_image ($0.05/img)
├── Supporting visuals: flux_image ($0.03/img)
├── Text overlays: openai_image ($0.04/img)
├── B-roll stills: pexels_image ($0.00)
└── Total for 10 images: ~$0.35

PRODUCTION PATH: Standard
├── All generated: flux_image ($0.03/img)
├── B-roll stills: pexels_image ($0.00)
└── Total for 10 images: ~$0.25

PRODUCTION PATH: Budget
├── All stock: pexels_image + pixabay_image ($0.00)
├── Diagrams: diagram_gen ($0.00)
└── Total: $0.00

PRODUCTION PATH: Offline
├── All generated: local_diffusion ($0.00)
├── Diagrams: diagram_gen ($0.00)
└── Total: $0.00 (but slower, lower quality)
```

Use `generation_mode="edit"` when the task starts from an existing image and should route only to edit-capable providers.

## Using the Image Selector

For most cases, use `image_selector` and let it route:

```python
# The selector finds the best available provider
result = image_selector.execute({
    "prompt": "aerial view of a modern data center",
    "preferred_provider": "auto",  # or "flux", "pexels", etc.
    "output_path": "assets/images/scene-3.png"
})
```

Override with `preferred_provider` when you know which provider is best for the scene type.
Use `allowed_providers` to restrict to free or local options:

```python
# Budget mode: only free providers
result = image_selector.execute({
    "prompt": "server room interior",
    "allowed_providers": ["pexels", "pixabay", "local_diffusion"],
    "output_path": "assets/images/scene-3.jpg"
})
```

## Consistency Across Mixed Sources

When mixing stock and generated images in the same video, visual consistency is the challenge.

### Strategy: Color Grade Everything
Apply the playbook's color grading LUT to both stock and generated images in the compose stage.
This unifies the look. The `color_grade` enhancement tool handles this.

### Strategy: Match The Visual Identity, Not A Copied Prefix
When generating images, adapt the playbook's mood, palette, texture, and medium
into a short scene-specific anchor. When searching stock, filter for the same
emotional and visual qualities: color, lighting, environment, composition, era,
and texture. Use the playbook as a consistency source, not a script to paste.

### Strategy: Avoid Mixing Styles Within a Scene
Don't use a stock photo for one element and an AI illustration for another in the same scene.
Keep each scene internally consistent — all stock or all generated.
