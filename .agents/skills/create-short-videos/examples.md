# Examples

## Collage + transcript (this repo’s AI short)

**User:** sends a 3×4 poster collage + “cắt thành short, ghép voice nam và nhạc motivate”.

**Agent:**

1. Split → 12 files in `docs/shorts/ai-khong-thay-the-chung-ta/slides/`
2. Tiles ~189px wide → GenerateImage 9:16 per slide
3. `scripts.json` punchy Vietnamese lines (see that folder’s `voice/scripts.json`)
4. `build --voice vi-VN-NamMinhNeural`
5. Outputs: `videos/01-…12.mp4` (6–9s) + `videos/full-short.mp4` (~29s)

## Already-split slides + English VO

**User:** 8 PNGs + English bullet script.

**Agent:** skip grid split; portraits via script (wide enough); `--voice en-US-AndrewNeural`.

## Re-voice only

**User:** “đổi sang giọng nữ, giữ nhạc”.

**Agent:** rewrite/reuse `voice/*.txt`, `build --voice vi-VN-HoaiMyNeural` (script remuxes video from current mp4s + new audio).
