# Ray M2 Assets Adapter

M2 keeps the existing proposal and asset-review gates, but changes paid clip
generation to route through OpenMontage's real `video_selector` instead of
calling provider tools directly.

Implemented behavior:

- Asset generation calls `video_selector` with the selected provider constrained
  by the approved request (`kling`, `grok`, `veo`, or `seedance`).
- Reference-conditioned jobs still run sample-first: the first clip is generated
  and the assets stage waits for human review before spending on the rest.
- After each generated clip, Ray extracts the last frame with ffmpeg and stores
  it under `assets/chaining/`.
- Subsequent scenes use that prior last frame as the start/reference input.
  - Veo uses `first_last_frame_to_video` when references are available.
  - Seedance uses `image_to_video` with `end_image_url`.
  - Grok and Kling use `image_to_video` from the previous last frame.
- The asset manifest records `metadata.generation_adapter`,
  `metadata.generation_runs`, and `metadata.chain_frames` for board/MCP review.
- Uploaded/generated assets continue to be uploaded through the existing R2 path.

Still M3, not M2:

- Final composition remains the existing hosted compose path until the M3
  Remotion/HyperFrames/audio migration.
- Provider output quality is still gated by human asset review before compose.
