---
name: seedance-product-scene
description: Use when producing beginner-friendly product scene images, product videos, or product marketing copy with Volcengine Ark Seedream and Seedance, especially when a supplied product image must remain recognizable.
---

# Seedance Product Scene

Use this reference through the `seedance-product-scene` OpenMontage pipeline.
The pipeline owns approvals; this file covers provider behavior, prompt locks,
scene presets, results, and errors.

## Provider Boundary

- Images: `seedream_ark_image`, Volcengine Ark `/images/generations`.
- Video: `seedance_ark`, Volcengine Ark asynchronous content tasks.
- Copy: the active Codex session. Do not call an Ark text model.
- Music: `pixabay_music`.
- Configuration: `~/.seedance/config.json`, optionally overridden by
  `SEEDANCE_CONFIG_PATH`; environment variables take precedence.
- Never display or persist the complete API key.

## Product Lock

Every image and video prompt must repeat the same product lock:

```text
保持产品主体、比例、结构、颜色、文字和包装细节不变；只改变背景、灯光、构图和镜头运动。
```

Do not ask the model to redesign packaging. Do not add claims, certifications,
ingredients, or performance promises not supplied by the user.

## Scene Presets

| ID | Name | Visual anchors | Camera behavior |
|---|---|---|---|
| `luxury` | 轻奢生活风 | marble, warm gold light, quiet home | slow push and gentle orbit |
| `nature` | 自然户外风 | plants, dappled sunlight, breeze | slow lateral move and light changes |
| `tech` | 科技未来风 | dark space, blue-violet neon, scan light | controlled rotation and detail scan |
| `office` | 商务办公风 | clean desk, laptop, daylight | stable lateral move |

One style preview is one image. A complete style is three image candidates.

## Three-Shot Video Prompt

Use one continuous 8-second prompt:

```text
GLOBAL STYLE: [style-specific grade and 9:16 framing]
SCENE: [location and mood]
PRODUCT LOCK: [verbatim product lock]
SHOT 1 0–3s: product detail close-up; [camera move]
SHOT 2 3–6s: product in the approved use scene; [camera move]
SHOT 3 6–8s: hero still with the product fully visible; [camera settle]
OPTICS: [lens and framing]
LIGHTING: [motivated light]
PHYSICS: [fabric, liquid, reflection, or other relevant behavior]
AUDIO: no music, no dialogue, no sound effects
```

Do not generate native audio when a separate approved music track will be mixed.

## Tool Contracts

`seedream_ark_image` accepts `prompt`, `source_image_path`, `scene_preset`,
`product_name`, `model`, `size`, `count` (1–3), `output_dir`, and `watermark`.
It validates image bytes before writing output.

`seedance_ark` accepts the approved scene image through
`reference_image_path`, plus `prompt`, `operation="image_to_video"`,
`model_variant="2.5"`, `duration`, `aspect_ratio`, `resolution`,
`generate_audio=False`, and an explicit `output_path`.

## Error Copy

- 401: Key 可能不对或已过期。
- 403: 模型未开通或当前账号没有权限。
- 429: 调用太频繁或额度不足。
- For image drift: stop before video generation.
- For video failure: retain the task ID and do not submit a duplicate task.

## Cost Rules

Show the model, candidate count, video count, duration, resolution, and known
price before paid generation. Unknown image pricing requires a quote. The second
regeneration may add cost; the third requires a concrete correction direction.
