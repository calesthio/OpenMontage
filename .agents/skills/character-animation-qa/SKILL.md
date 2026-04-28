---
name: character-animation-qa
description: Review local character animation with schema checks, Playwright browser previews, frame sampling, and FFmpeg/ffprobe final output checks.
license: MIT
---

# Character Animation QA

Use this skill before presenting a character-animation preview or final render.

## Review Layers

1. Schema validation: character design, rig plan, pose library, action timeline.
2. Static asset checks: referenced parts and backgrounds exist.
3. Browser preview: load the preview, capture screenshots, collect console errors.
4. Motion check: compare sampled frames for non-trivial differences.
5. Final MP4 check: ffprobe metadata, duration, resolution, audio, frame samples.
6. Agent visual review: inspect sampled frames for detached limbs, bad layers,
   off-frame characters, unreadable expressions, broken text.

## Playwright Pattern

```ts
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(previewUrl, { waitUntil: "networkidle" });
await page.screenshot({ path: "preview.png" });
```

## Pass/Revise/Fail

- `pass`: technical checks pass, acting is readable.
- `revise`: fixable rig/timeline issue.
- `fail`: missing assets, blank render, runtime failure, or wrong runtime.

## Sources

- Playwright screenshots:
  https://playwright.dev/docs/screenshots
- Playwright page navigation:
  https://playwright.dev/docs/api/class-page#page-goto
- FFmpeg/ffprobe should be used for final media probing:
  https://ffmpeg.org/ffprobe.html
