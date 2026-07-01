---
name: agnes-image
description: |
  Agnes AI image generation with Sapiens AI models. Use when: (1) Generating images via agnes-image-2.0-flash or agnes-image-2.1-flash, (2) Cost-free image generation, (3) High-information-density visuals, (4) Multi-image composition, (5) Image editing and style transfer.
metadata:
  author: Sapiens AI
  version: "1.0.0"
  tags: agnes, sapiens, image-generation, t2i, i2i
---

# Agnes Image Generation

## When to Use

- Cost-free image generation (currently $0/image, standard price $0.003/image)
- High-information-density visuals with complex compositions (use 2.1-flash)
- Multi-image composition (combine characters or elements into one scene)
- Image editing, style transfer, background replacement
- General text-to-image when budget is constrained

## Models

| Model | Best For | Speed |
|-------|----------|-------|
| `agnes-image-2.0-flash` | General T2I/I2I, fast iteration, product staging | Fast |
| `agnes-image-2.1-flash` | High-density details, complex layouts, semantic alignment, composition preservation | Medium |

**Default: `agnes-image-2.1-flash`** — optimized for detail-rich output and better composition preservation during edits. Switch to 2.0-flash when speed is the priority.

## Prompt Structure

### Text-to-Image

```
[Subject] + [Scene/Background] + [Style] + [Lighting] + [Composition] + [Quality]
```

Example:
```
A professional product photo of a wireless headphone on a clean white
background, soft studio lighting, sharp details, commercial photography style
```

### Image-to-Image

Clearly describe what should change and what should remain unchanged:

```
[Change instruction] + [New style/scene] + [Elements to preserve] + [Lighting] + [Quality]
```

Example:
```
Change the background to a futuristic city at night while keeping the
person's face, outfit, and pose unchanged
```

### Multi-Image Composition

Describe the relationship between input images and how they should be combined:

```
Place the person from the first image beside the robot from the second image
in a cinematic sci-fi battle scene
```

## API Notes

- **Base URL**: `https://apihub.agnes-ai.com/v1`
- **Endpoint**: `POST /v1/images/generations`
- **Auth**: `Authorization: Bearer <AGNES_API_KEY>`
- **`response_format`** must go inside `extra_body`, NOT at the top level. Top-level placement causes a 400 error.
- Image-to-image input goes in `extra_body.image` as an array of URLs or Data URI Base64 values.
- Image-to-image does NOT require `tags: ["img2img"]`.
- Client timeout: 60–360s recommended depending on complexity.

## Key Differences from Other Providers

| Aspect | Agnes | OpenAI / FLUX |
|--------|-------|---------------|
| `response_format` placement | Inside `extra_body` | Top-level |
| Image input for I2I | `extra_body.image` (array) | Varies by provider |
| Tags for I2I | Not required | Not applicable |
| Pricing | Currently free | Paid |

## Calling via OpenMontage

Always go through `image_selector`:

```python
from tools.tool_registry import registry
registry.ensure_discovered()
selector = registry.get("image_selector")
result = selector.execute({
    "prompt": "A luminous floating city above a misty canyon at sunrise",
    "preferred_provider": "agnes",
    "size": "1024x768",
    "output_path": "projects/<proj>/assets/images/scene_01.png",
})
```

Direct call to the provider tool:

```python
agnes = registry.get("agnes_image")
result = agnes.execute({
    "prompt": "A product photo of a glass cube on white background",
    "model": "agnes-image-2.1-flash",
    "size": "1024x768",
    "output_path": "output.png",
})
```

## Integration Checklist

- Use `agnes-image-2.1-flash` for complex/detail-rich scenes
- Use `agnes-image-2.0-flash` for fast iteration and general editing
- Place `response_format` inside `extra_body`, not at top level
- For image-to-image, provide input images through `extra_body.image` as an array
- For local images, the tool auto-converts to data URI Base64
