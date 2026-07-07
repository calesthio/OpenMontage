---
name: zapcap-captions
description: Add animated, word-synced styled captions to a video with the ZapCap API. Use when the user wants viral/social caption styles (Hormozi, Beast, Devin, ...), word-level highlight captions burned into a video, emoji captions, or translated+captioned variants of the same video. Backs the OpenMontage `zapcap_captions` subtitle provider.
metadata:
  openclaw:
    requires:
      env:
        - ZAPCAP_API_KEY
    primaryEnv: ZAPCAP_API_KEY
---

# ZapCap Captions

ZapCap is a captioning API. You upload a video, choose a styled caption
*template*, and ZapCap transcribes the audio and renders animated, word-synced
subtitles burned into the video — the fastest path to social-ready captions
(TikTok/Reels/Shorts).

This skill backs the `zapcap_captions` tool (`tools/subtitle/zapcap_captions.py`),
capability `subtitle`, provider `zapcap`.

## When to use it (vs. the local subtitle tools)

| Need | Tool |
|------|------|
| Viral styled, animated, word-highlight captions burned in | **`zapcap_captions`** (this) |
| Word-by-word caption burn locally via Remotion | `remotion_caption_burn` |
| Plain SRT/VTT/caption JSON from existing transcript segments | `subtitle_gen` |

ZapCap needs an **audio track with speech** — it transcribes to make captions.
Don't use it for silent/music-only videos. Max video length is **30 minutes**.

## Configuration

```bash
ZAPCAP_API_KEY=...   # required (sent as the x-api-key header)
```

Calls go to `https://api.zapcap.ai`. This matches the `zapcap-mcp` server's env
var, so one `.env` configures both the OpenMontage tool and the MCP.

## The flow (what the tool does on `action="caption"`)

1. **Upload** — `POST /videos` (local file, multipart `file`) or
   `POST /videos/url` (`{url}`) → `videoId`.
2. **Create task** — `POST /videos/{videoId}/task` with `templateId`
   (+ options) → `taskId`. Set `autoApprove: true` so rendering starts without
   a manual transcript-approval step (the tool defaults to this).
3. **Poll** — `GET /videos/{videoId}/task/{taskId}` until `status` is
   `completed`. Statuses: `pending → transcribing → transcriptionCompleted →
   rendering → completed` (or `failed`).
4. **Download** — stream `downloadUrl` from the completed task to `output_path`.

Auth on every call: header `x-api-key: $ZAPCAP_API_KEY`.

## Templates

List them first (names are not stable IDs — always resolve):

```python
from tools.subtitle.zapcap_captions import ZapCapCaptions
tpl = ZapCapCaptions().execute({"action": "list_templates"})
# tpl.data["templates"] -> [{id, name, categories}, ...]
```

Popular templates (categories: `animated`, `highlighted`, `basic`):
`Hormozi 1` (animated+highlighted), `Beast`, `Devin`, `Ella`, `Tracy` (basic),
`Karl`, `Maya`, `Hormozi 2/3/4/5`. The tool accepts either `template_id`
(UUID) or `template_name` (resolved case-insensitively via `/templates`).

## OpenMontage usage

Full caption of a local file (the common case):

```python
from tools.subtitle.zapcap_captions import ZapCapCaptions

res = ZapCapCaptions().execute({
    "action": "caption",                 # default; can omit
    "input_path": "projects/demo/renders/final.mp4",
    "template_name": "Hormozi 1",        # or template_id="a51c5222-..."
    "language": "en",                    # omit to auto-detect
    "auto_approve": True,
    "output_path": "projects/demo/renders/final_captioned.mp4",
    "timeout_seconds": 600,
})
# res.data -> {videoId, taskId, templateId, downloadUrl, transcriptUrl, output, ...}
# res.artifacts -> ["projects/demo/renders/final_captioned.mp4"]
```

Caption a public URL instead: pass `video_url` instead of `input_path`.

## renderOptions (subtitle appearance)

Pass any of these under `render_options`; all optional:

```python
"render_options": {
    "subsOptions": {
        "emoji": True, "emojiAnimation": True,
        "emphasizeKeywords": True,       # highlight key words per template style
        "animation": True, "punctuation": False,
        "displayWords": 4,               # words shown at once (guidance)
    },
    "styleOptions": {
        "top": 40,                       # Y position, % of height (higher = lower)
        "fontUppercase": True, "fontSize": 46, "fontWeight": 900,
        "fontColor": "#ffffff",
        "fontShadow": "l",               # none|s|m|l
        "stroke": "s", "strokeColor": "#000000",
        "fontId": "<uploaded font id>",  # optional, from POST /fonts
    },
    "highlightOptions": {                # colors used for emphasized keywords
        "randomColourOne": "#2bf82a",
        "randomColourTwo": "#fdfa14",
        "randomColourThree": "#f01916",
    },
}
```

## Translation & fan-out (transcribe once, render many)

To caption one video into several languages or templates **without paying to
transcribe N times**, transcribe once and reuse the transcript:

```python
tool = ZapCapCaptions()
# 1. upload + create first task, but only wait for transcription
up = tool.execute({"action": "upload", "input_path": "in.mp4"})
vid = up.data["videoId"]
first = tool.execute({"action": "create_task", "video_id": vid,
                      "template_name": "Hormozi 1", "language": "en"})
# (poll first.data["taskId"] to transcriptionCompleted with get_task)

# 2. fan out: reuse the transcript, translate per target
for lang in ["es", "fr", "de"]:
    tool.execute({"action": "create_task", "video_id": vid,
                  "template_name": "Hormozi 1",
                  "transcript_task_id": first.data["taskId"],
                  "translate_to": lang, "auto_approve": True})
```

The `mcp__zapcap__*` MCP tools (`upload_video_*`, `create_video_task`,
`wait_for_task`) expose the same flow and `wait_for_task` supports
`waitFor="transcriptionCompleted"` for the fan-out barrier.

## Pipelines that benefit

`clip-factory`, `podcast-repurpose`, `talking-head`, and `localization-dub`
all produce speech-driven social clips where styled burned-in captions are the
norm. Offer `zapcap_captions` at the edit/compose stage for those briefs as an
alternative to `remotion_caption_burn` when the user wants ZapCap's template
styles.

## Failure modes

- `401/403` → bad or missing `ZAPCAP_API_KEY`, or no API credits / wrong plan.
- task `status: failed` with an `error` → usually no speech, unsupported codec,
  or >30 min. Re-check the source has an audio track.
