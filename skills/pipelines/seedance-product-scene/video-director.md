# Video Director — Seedance Product Video

## Inputs

Required: `scene_plan` and the approved `asset_manifest`.

## Announcement

Before each paid call state: `seedance_ark`, provider `ark`, model
`doubao-seedance-2-5-260628`, one clip per style, 8 seconds, 9:16, 720p, and
whether pricing is confirmed.

Seedance 2.5 requires the current ARK console 报价 in CNY per million
completion tokens. Ask the user to confirm that quote before the first paid
video. If no quote is available, 停止. Offer 3 choices: obtain the console
quote, request an approved model/provider change, or stop. Never invent a price.

## Generation

For each selected style call `seedance_ark` once:

```json
{
  "operation": "image_to_video",
  "reference_image_path": "<approved image>",
  "prompt": "<three-shot prompt>",
  "model_variant": "2.5",
  "custom_price_cny_per_million_tokens": "<user-confirmed ARK quote>",
  "duration": 8,
  "aspect_ratio": "9:16",
  "resolution": "720p",
  "generate_audio": false,
  "output_path": "assets/video/<style>/seedance-source.mp4"
}
```

Use the approved image only. Preserve task IDs. Download immediately and run
ffprobe. If a task fails, stop; do not submit a duplicate.

## Review

Play each video and check the three shots, product continuity, camera motion,
and absence of unwanted text. Present 4 choices:

1. Approve this video.
2. Regenerate the same style.
3. Adjust motion or a shot detail.
4. Return to image selection.

停止并等待用户审批，不要进入文案或音乐阶段。
