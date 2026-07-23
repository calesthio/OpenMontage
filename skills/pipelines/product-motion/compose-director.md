# Compose Director — Product-Motion Pipeline

## When to Use

Seventh stage (auto-proceeds). `edit_decisions` is locked. You render the
final video, post-mix the audio, run the final review, and produce
`render_report` + `final_review`.

## Process

1. **Route by `render_runtime`** — read it from `edit_decisions`; it must
   match `proposal_packet.production_plan.render_runtime`. `video_compose`
   dispatches automatically: `render_runtime="remotion"` +
   `composition_mode="atelier"` → `_render_via_atelier`;
   `render_runtime="hyperframes"` → `hyperframes_compose` /
   `_render_via_hyperframes`. **A mismatch or silent swap is a CRITICAL
   governance violation** — if the locked runtime is unavailable at compose
   time (Node missing, HyperFrames doctor fails), STOP and escalate per the
   blocker protocol; do not render on the other runtime without user approval
   and a re-logged `render_runtime_selection` decision.
2. **Render.** The atelier path stages sources, runs the stock-import
   guardrail (a violation fails the render with `re_author` — fix the scene,
   don't bypass), renders via `npx remotion render`, and runs the built-in
   final review probes.
3. **Post-mix** narration + music over the rendered video via `audio_mixer`
   (ducking + loudnorm). SFX are already inside the composition — do not add
   them again as post-mix tracks.
4. **Final review** (`final_review` artifact), beyond the technical probes:
   - **Provenance spot-check**: for each scene, pick one token visible in the
     final frames and verify it against the design_system's cited repo
     file+line. A drift here is a fidelity defect → send back to assets.
   - SFX land on settle frames (scrub the cue frames); mix is narration-led.
   - Nothing moving at any cut; fonts are the product's real fonts.
   - Distinctness: could this be any other product's video? It must not be.
5. **ffprobe** the output (resolution, duration, both audio characteristics),
   write `render_report` with encoding profile + verification notes,
   checkpoint, and present the deliverable with the final_review summary.
