# Compose Director — Mux and Validate

## Inputs

Required: approved videos, `product_copy`, and `product_delivery`.

## Runtime

The approved output has no burned text. Keep `render_runtime="ffmpeg"` from the
proposal for music muxing. HyperFrames and Remotion are not used unless the user
reopens the proposal to add text or motion graphics. If that happens, Present
both Remotion and HyperFrames is required before a runtime change. Never switch
`render_runtime` silently.

## Process

1. Trim or fade music to 8 seconds with `audio_mixer`.
2. Mux the approved audio using `video_compose` with `audio_path`.
3. Write `renders/<style>/final.mp4`.
4. Verify video stream, audio stream, duration, 9:16 framing, and file readability.
5. Write `render_report` and `final_review`.

If muxing or ffprobe fails, preserve the original video and audio, stop, and
present 3 recovery options.
