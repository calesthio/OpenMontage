# Stickman Video Director — Audit for OpenMontage

Audit of `https://github.com/kaomei/stickman-video-director` (commit `8ced473`, MIT) against the OpenMontage factory architecture (P0–P5) and the style/playbook layer. **No code was ported. No spend, no pilot, no renderer replacement.** This document records capabilities, limits, and risks only.

## 1. Repository identity and license

- Name: `directing-stickman-videos` (Skill + local Autopilot runtime).
- License: **MIT**, Copyright (c) 2026 Stickman Video Director contributors.
- Third-party assets inside the Skill:
  - Lucide/Feather icons — ISC (notice retained in `assets/b1/LUCIDE-LICENSE.txt`).
  - Caveat + Noto Sans fonts — SIL OFL (notices retained).
  - Bundled Gemini Sadaltager/Bodi narration sample — provider media, **not** relicensed by MIT; subject to Google service terms.
  - Website/platform marks shown in evidence frames remain their owners' property.
- Runtime dependency: `@napi-rs/canvas` 0.1.100 (Node ≥20). Tests fail to import it unless `npm ci` is run inside the Skill dir (observed: `ERR_MODULE_NOT_FOUND`).
- No Python; no tests beyond Node `node --test` (6 tests, 4 pass, 2 fail only because node_modules absent).

## 2. What the repository actually is

It is **one Skill with two modes**, not two products:

- **A · Director**: storyboard + standalone ~10 s Gemini Omni Flash clip prompts. Styles 1–5 (minimalist, beanie Zeke, prehistoric, cozy, historical). Owns a 5-stage emotional heartbeat engine and frozen voice profiles.
- **B · Autopilot**: finished local video (narration + captions + illustration + micro-animation + SFX) rendered by a **local Node/FFmpeg renderer**, not a cloud generator. Styles B1 (minimal hand-drawn), B2 (colorful hand-drawn), B3 (retro TV).

OpenMontage relevance is almost entirely in **mode B (Autopilot)**. Mode A is a prompt-authoring contract for Gemini Omni Flash and overlaps with our existing `animated-explainer`/`character-animation` pipelines; it is **not** a renderer and brings no new capability we lack.

## 3. Autopilot runtime — exact capabilities

Source: `skills/directing-stickman-videos/scripts/autopilot-core.mjs`, `autopilot-render.mjs`, `b3-graphics.mjs`, `gemini-media.mjs`, `autopilot.mjs`.

- **Manifest v1** (declarative JSON, validated strictly):
  - `version`, `style` ∈ {B1, B2, B3}, `width/height/fps` (even integers, 256–3840, fps 12–60).
  - `voice`: `{path, lead, tail, contains_sfx}` only. **No `speed` field accepted** — original speech rate is preserved by construction.
  - `captions`: timed cues `{start,end,text}`; text ≤240 chars.
  - `shots`: contiguous, gap/overlap-free, each with `layers`.
  - `sfx`: `{time, kind ∈ {tap,paper,pop,chime,jingle}, gain 0..0.3}`.
  - Optional `music: {path, gain 0..0.2}` (looped), `television` (B3 only), `font`/`captionFont`, `grid`, `captionSize`.
- **Layer types**:
  - B1/B2: `image`, `pose` (B1 only, 3-pose atlas indices 0–2), `text`, `line`, `arrow`, `underline`.
  - B3 adds: `path` (M/L/Q/C/Z commands, fill/stroke, lineWidth), `rect`, `ellipse`, `group` (children, pivotX/pivotY, scaleX/scaleY).
- **Keyframes**: per-layer `keys` with `t, x, y, w, angle, alpha, progress` (+ scaleX/scaleY for B3), smoothstep interpolation, clamped before/after endpoints. Genuine motion requires authored layers; **no inferred limb motion from flat images**.
- **Design plane**: 1280 units wide, height = 1280×outputH/outputW (uniform scale, no stretch). Caption band: bottom 110 units reserved.
- **Media safety**: all paths resolved relative to project.json or absolute local; `@b1/…` addresses bundled assets with path-traversal guard; **remote URLs and executable expressions rejected** (`mediaPath` throws on `http:`/`//`).
- **Rendering**:
  - Per-shot PNG/JPEG rasterization via `@napi-rs/canvas` with registered fonts.
  - Per-shot MP4 encode via FFmpeg libx264 (CRF 20, fast), concat demuxer, audio mux (voice with adelay+apad+atrim, SFX WAV mixed, optional music).
  - SFX are procedural (original tap/paper/pop/chime/jingle) — not borrowed audio.
  - Contact sheet (9 frames), SRT/VTT, `*-report.json`.
- **Caching**: each shot cached by content hash including its own media, overlapping captions, fonts, renderer version, timing, style, television settings. Cache hits probed (frame count) before reuse. `output/checkpoint.json` records stage + shot count.
- **Recovery**: rerun same command; do not delete cache or resynthesize audio. Stale lock removed only if recorded PID dead. Lock file guards concurrent renders.
- **Approval**: `approve` records a genuine user sample/full-film approval binding the reviewed sample file, scoped timeline/assets, and global settings (narration track, voice). `render` requires this approval and full coverage. Technical checks never authorize approval.
- **Preview**: `preview --seconds N` renders only the sample range; missing later-shot media does not block it. `--replace` required to overwrite.
- **Validation**: `validate` (default full film; `--seconds N` for sample) checks files, audio duration, shot coverage, cue timing, layers, SFX. `probe` for media streams. `doctor` for deps/fonts/keys (no network, no key values).
- **Optional Gemini adapter** (`gemini-media.mjs`): speech/image, one request, no retries, no key printing, `--allow-network` required, model ID validated, receipt file written, output extension must match native payload. `--direction` rejected (voice is used as-is). No default image model assumed.

## 4. QA contract (Autopilot)

Source: `references/autopilot-production-qa.md` + `b1-production-qa.md`.

- **Scene ledger** (compact, project-local): spoken phrase + word times, idea, focal subject/action/expression, scene text, timed picture events, evidence source/lang/date, caption phrases, SFX event, connection to next shot. Covers body and ending, not just opening.
- **First 30 seconds** dedicated hook pass: concrete line + audience-relevant question/tension/contrast; relevant result/case early; purposeful SFX; no generic greeting/logo hold/article screenshot as entire hook.
- **Meaningful motion**: no principal-picture inactivity > 2.5 s anywhere (preview or film). Subtitle turnover, whole-frame zoom/pan/fade, decorative noise, tiny moving corner do **not** rescue a frozen principal picture. Movement must communicate the current idea.
- **No repeated compositions** to fill time; distant sections reviewed for same pose/layout with replacement text.
- **Clear screenshots** (sharp, cropped/enlarged, readable in final encoded frame; no upscaled blur).
- **Content-matched graphics** (icons/marks/sketches match entity; coherent licensed icon family or original drawings; no generic stand-ins for essential objects).
- **Natural captions** (semantic grouping, not mechanical word-count; preserve spoken order; no stranded prepositions; split at natural boundaries; recheck punctuation/gaps/reading time).
- **Whole-film delivery gate**: same detail standard throughout; chronological contact sheet + full-size frames; inactivity check excluding subtitle band; captions vs approved text; preserve accepted script/audio/assets by fingerprint; record gate results.

## 5. Recovery / caching / approval contract

Source: `autopilot.md`, `autopilot-runtime.md`.

- Project lives **outside** the installed Skill; `project.json` + checkpoint with stage, fingerprints, approvals, completed outputs, pending jobs, next step.
- Reuse valid work after interruptions; inspect uncertain provider jobs before retry.
- **Sample → approval → full film**: deliver ~20 s first (sound, captions, acting, transitions). User reviews actual picture/sound. Only after explicit approval run `approve` (binds reviewed sample file, scoped timeline/assets, global settings). `render` requires this. Technical checks never authorize.
- Changing reviewed content/assets/captions/SFX, narration track or global settings invalidates approval; adding/revising only later shots does not. Whole narration file fingerprinted conservatively.
- Cost: image/TTS are the user's configured tools; check availability and disclose cost before billable calls. Never request pasted API keys (env vars only). Gemini consumer subscription ≠ API quota.
- No publish/upload/GitHub changes unless separately requested.

## 6. Style-specific facts relevant to our concept

- **B1 (minimal hand-drawn)**: near-white warm paper `#FDFDFC`, faint 64px grid (rgba(76,90,105,.036), 0.8px, above y=610), bottom 110px solid paper. Slender stick figure ~4–4.5 heads tall, modest round head, long single-line limbs, small oval hands/feet. Exaggerated but varied expressions. Character shots ~60–70% of direct screen time (not image area, not a hard rule for every story). Default voice: Google Gemini Bodi (English), native 1× speed, no direction. Captions 34px at 1280×720, baseline y=666.
- **B2 (colorful hand-drawn)**: warm paper `#f4f0e5` (no grid), irregular ink contours, muted varied colored props, ordinary round-headed stickmen with dot eyes + short line mouth, no fixed costume. Headings handwritten; captions dark ink on ivory paper label, default 40 at 1280-wide. Default voice: Google Gemini Fola. Scene map required (location/layout/viewpoint/staging + recent composition it differs from) to prevent "same room with substituted props".
- **B3 (retro TV)**: dark field `#111316`, story-specific white/gray artwork, native Gemini Bodi default, clean white uppercase semantic captions, optional television finish (soft bloom, scanlines, vignette, intensity 0–1) applied **once** to scene before clean captions. Layered vector artwork: paths (curves for rounded limbs), rect/ellipse, groups with pivot rotation/scale. Max 8 nesting, 2000 layers, 1000 path commands.

## 7. Limitations and risks (must be respected)

1. **It is a renderer, not a generator.** It renders authored declarative JSON to MP4. It does not write scripts, research, or invent facts. Our factory still owns research/script/scene plan.
2. **It brings its own renderer.** Node + `@napi-rs/canvas` + FFmpeg. We must **not** adopt it as a second production runtime without justification; our Remotion/HyperFrames/FFmpeg stack already covers rendering. The useful parts are the **contract and QA rules**, not the engine.
3. **No character rig.** B1 uses a 3-pose atlas (demo reference, not a fixed library); B2/B3 use authored layered PNGs/SVG paths. There is no reusable skeletal rig with joints — motion is per-layer keyframes. We must build our own SVG rig; this repo provides principles, not a rig.
4. **Node ≥20 + npm ci required.** Not currently installed in the workspace (no `@napi-rs/canvas`). Adopting the runtime would add a Node dependency and a second font pipeline.
5. **Gemini adapter is optional and network-gated.** It is not a replacement for our `gflow-cli`/Nano Banana path and must not change our generator. Our zero-cost gate and `--no-spend` remain authoritative.
6. **Voice policy differs.** Autopilot uses a named voice with no direction fields; our factory uses Kokoro `af_heart` (P3) and a frozen voice profile for Director mode. Do not import A's detailed voice block into B; and do not import B's voice defaults into our factory narration.
7. **License notices must follow any ported code.** MIT notice + Lucide ISC + OFL font notices. Provider media (Gemini voices) and third-party marks are not relicensed.
8. **Tests are shallow.** 6 Node tests, 2 fail without node_modules. No Python tests, no QC automation beyond the runtime's own checks. Our P5 QC is stricter.
9. **No MASTER_VISUAL_STYLE_GUIDE.md equivalent.** Its style rules are embedded in references and approved sample media; fidelity is evidenced by sample MP4s/contact sheets, not a machine-readable spec.

## 8. Mapping to OpenMontage P0–P5

| Stickman Director concept | OpenMontage equivalent | Status |
|---|---|---|
| Scene ledger | `production_manifest` + `edit_decisions` | Exists (P2–P4); adopt ledger *fields* (idea, focal action, evidence source/date, connection to next shot) as optional metadata |
| First 30 s hook pass | `script_analyzer` / hook rules in playbooks | Exists; add explicit 30 s review gate in `preview_system`/`final_qc` |
| Meaningful motion / 2.5 s inactivity | `motion_variety.lint_variation`, `preview_system` checks | Exists partially; add principal-picture inactivity check (not just pixel freeze) |
| No repeated compositions | `visual_director` variety score | Exists; extend with distant-section repetition check |
| Content-matched graphics | `quality_control` 9 criteria | Exists; add icon/entity match criterion |
| Natural captions (semantic) | `subtitle_gen` + alignment | Exists; add semantic grouping review step |
| Scene ledger → shot cache identity | `asset_cache` / `render_engine` | Exists; add rig-state to cache key |
| Checkpoint + SHA-256 + resume | `checkpoint.py`, `recovery_manager`, `asset_cache` | Exists and stronger |
| Preview approval gate | `checkpoint` awaiting_human, `preview_system` | Exists |
| Content-addressed caching | `asset_cache`, shot cache in render | Exists |
| Recovery workflow | `recovery_manager` | Exists |
| Character consistency | `character_consistency_manager` | Exists; needs rig profile extension |
| Pivot/layered animation | `motion_engine` (camera only) | **Gap**: no limb rig; build new |
| Television finish | none | Optional B3-only polish; not needed for our style |

## 9. Bottom line

The repo's **best and transferable** value is its **production discipline**, not its code: scene ledger, meaningful-motion 2.5 s rule, first-30 s hook pass, no repeated compositions, content-matched graphics, semantic caption grouping, preview-approval binding, content-addressed shot caching, SHA-256 checkpointing, and fail-closed QA. All of these are expressible as extensions to modules we already have. Its **renderer and 3-pose atlas are not** worth importing: we keep Remotion/HyperFrames/FFmpeg and build our own SVG rig. Its **Gemini adapter must not** replace `gflow-cli` or change our generator.

## 10. Audit sources read

- `SKILL.md`
- `references/autopilot.md`
- `references/autopilot-runtime.md`
- `references/autopilot-production-qa.md`
- `references/b1-minimal-handdrawn.md`
- `references/b2-colorful-handdrawn.md`
- `scripts/autopilot-core.mjs`
- `scripts/autopilot-render.mjs`
- `scripts/b3-graphics.mjs`
- `scripts/gemini-media.mjs`
- `package.json`
- `LICENSE`, `assets/b1/ATTRIBUTION.md`, `assets/b1/LUCIDE-LICENSE.txt`
- `tests/runtime.test.mjs`, `tests/b3-runtime.test.mjs`, `tests/b3-reference-pack.test.mjs`
- `docs/superpowers/specs/2026-08-03-stickman-video-director-design.md` (skimmed for scope)
