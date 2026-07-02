# Grok Prompting

Use this when the chosen provider is `grok_image` or `grok_video`.

## When Grok Is The Right Pick

- You need to edit an existing image instead of generating from scratch
- You need to merge multiple source images into one output
- You need a short video influenced by reference images without locking the first frame
- You want one provider for both image and video generation with similar prompt language

## Grok Image

### Best Prompt Shape

```
[subject] + [action or change] + [setting] + [one style anchor] + [lighting]
```

### Edit Prompts

For image edits, describe the intended transformation directly:

- "Render this as a pencil sketch with detailed shading."
- "Replace the plain t-shirt with a dark green bomber jacket."
- "Combine these two people into the same sunny park scene."

Do not over-specify every unchanged detail unless preservation is critical.

### Multi-Image Composites

Tell Grok how to combine the inputs:

- who comes from which source
- what should stay separate
- where the final scene takes place

Example:

```
Place the person from image 1 and the person from image 2 on the same subway platform at dusk,
standing shoulder to shoulder, cinematic sodium-vapor lighting, realistic photography.
```

## Grok Video

### Best Prompt Shape

```
[shot] + [camera movement] + [subject] + [main motion beat] + [environment] + [lighting] + [tone]
```

### Reference-Image Video

Grok supports prompts that refer to source images with placeholders like `<IMAGE_1>`.
Use that when you need identity, wardrobe, or product consistency.

Example:

```
Medium full shot, slow push-in. The model from <IMAGE_1> walks onto a clean white runway wearing
the jacket from <IMAGE_2>. Soft studio lighting, premium fashion campaign, confident expression.
```

### Image-to-Video vs Reference-to-Video

- Use image-to-video when the source image should act like the opening frame.
- Use reference-to-video when the source images should influence the content but not freeze the composition.

## Common Mistakes

- Treating Grok reference images like strict storyboards. They are influence inputs, not exact frame locks.
- Writing multiple scene changes into one clip request.
- Combining too many style labels with too little scene information.
- Using vague edit prompts like "make it better" instead of naming the change.

## Balamonis Studio Guidance

- For image edits or compositing, prefer `grok_image` over the selector's default workhorse tools.
- For reference-conditioned video, prefer `grok_video` when the brief depends on carrying people, clothing, or products from input images into motion.
- If the deliverable is pure cinematic motion without reference constraints, compare Grok against Runway, Veo, and Kling before locking the provider.
