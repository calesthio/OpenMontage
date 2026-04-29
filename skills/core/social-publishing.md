# Social Publishing via Upload-Post

## When To Use

When the pipeline's publish stage needs to distribute the final video (or photos/text) to one or more social media platforms. Upload-Post replaces manual export-and-upload workflows with a single API call.

## Tool

`uploadpost_publisher` — registered in `tools/publishers/uploadpost_publisher.py`

| Field | Value |
|-------|-------|
| Tier | publish |
| Capability | `social_publishing` |
| Runtime | API |
| Env var | `UPLOADPOST_API_KEY` |

## Supported Platforms

Instagram, TikTok, YouTube, LinkedIn, Facebook, X (Twitter), Threads, Pinterest, Bluesky, Reddit, Google Business Profile.

## How It Works

1. The user connects social accounts through the Upload-Post dashboard (two clicks per account — no app creation, no developer tokens, no OAuth flows to build).
2. A single API key handles all connected platforms.
3. The tool sends the rendered video (or photos) to `POST /api/upload_videos` (or `/upload_photos`, `/upload_text`) with the target platforms in one request.
4. Upload-Post handles platform-specific formatting, aspect ratios, and API requirements.

## Integration With The Publish Stage

During the `publish` pipeline step:

```python
from tools.publishers.uploadpost_publisher import UploadPostPublisher

publisher = UploadPostPublisher()
result = publisher.execute({
    "video_path": "pipeline/compose/final.mp4",
    "platforms": ["youtube", "tiktok", "instagram"],
    "profile_username": "my_profile",
    "title": "My OpenMontage Video",
    "description": "Created with OpenMontage",
})
```

The returned `ToolResult.data` maps directly to `publish_log` schema entries:

| ToolResult field | publish_log field |
|------------------|-------------------|
| `results[].platform` | `entries[].platform` |
| `results[].post_url` | `entries[].url` |
| `results[].platform_post_id` | `entries[].video_id` |

## Scheduling & Queue

- Set `scheduled_date` (ISO-8601) to schedule for a specific time.
- Set `add_to_queue: true` to auto-schedule to the next available queue slot.
- Queue slots are configurable per-profile in the Upload-Post dashboard.

## Cost

Free tier: 10 uploads/month across all platforms. No credit card required.

## Common Pitfalls

- Forgetting to set `profile_username` — this identifies which connected accounts to use.
- Not including `title` for YouTube or Reddit uploads (required by those platforms).
- Sending a vertical video to platforms that expect landscape without setting aspect ratio metadata in the render stage.
