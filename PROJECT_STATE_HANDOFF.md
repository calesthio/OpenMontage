# OpenMontage — full project state handoff (consolidated through this chat)

Paste this file into a new chat to continue with full context. Written
as "what's decided / what's in progress / what's blocked" so the next
session doesn't re-litigate settled questions. This supersedes the
previous handoff — section numbers below reflect current state, not
the original document's history.

---

## 1. Niche & positioning (DECIDED — unchanged)

- **Education & Science** positioning, **"science-grounded speculation"**
  differentiator (real evolutionary biology as backbone, "what if"
  extrapolation as the hook). Pilot topic locked: **"What Would Life
  Look Like on an Ocean Planet With No Land?"**, ~20 min, 10-section
  structure.
- Full reasoning/sourcing for this is unchanged from the original
  handoff — see git history of this file if needed, not repeated here.

## 2. Repository & infrastructure (NEW — fully done)

- Repo: `sora73636-stack/OpenMontage` (fork of `calesthio/OpenMontage`),
  branch `kilo/mega-100`, AGPL v3, public.
- **GitHub account migrated twice** during this session due to
  Codespaces free-tier limits: original work happened under a
  collaborator account (`dragongod73584-design`), then moved to
  `rottokshorts37-droid` as a second collaborator. All commits
  transferred cleanly via normal `git push` — ownership of the repo
  never changed, only which account was running the Codespace.
- **A 343.96 MB `models/antelopev2.zip` nearly got committed** (GitHub's
  hard limit is 100 MB) — caught and fixed via `git reset --soft` +
  re-commit before it ever reached `origin`, then permanently added to
  `.gitignore`. This exact failure mode is now what `git-hygiene` (§3)
  exists to prevent automatically.
- `.devcontainer/devcontainer.json` created: auto-runs the pre-push
  hook symlink, Kokoro venv setup, and `pip install -r
  requirements-pinned.txt` on any future Codespace rebuild — written
  because `.git/hooks/` is never versioned by git itself, so without
  this the hook symlink has to be recreated by hand on every new
  Codespace.

## 3. Agent tooling — Phase B (NEW — fully deployed and tested)

Six new subagents live in `.kilo/agents/`, each with an explicit
`permission` YAML block (allow/ask/deny per tool), built specifically
around real failures from this session:

| Agent | Catches |
|---|---|
| `dependency-guard` | Blocks any `pip install` that would silently upgrade `diffusers`/`transformers`/`huggingface_hub`/`torch` past the pinned versions below — this is exactly the bug class that broke the pipeline mid-session before this handoff was written |
| `git-hygiene` | Blocks commits >90MB and known secret patterns (`.env`, `kaggle.json`, API keys) before push — tested live: correctly blocked a 95MB test file |
| `license-checker` | Checks LICENSE files / model cards, flags InsightFace-family dependencies, requires exact project names (not pattern-matched guesses) |
| `kaggle-test-runner` | Standardizes VRAM/consistency testing so each candidate isn't hand-rolled differently |
| `plan-keeper` | Owns `docs/PROJECT_PLAN.md`, writes no code, marks stages `NOT_CHECKED` rather than `PASS` without evidence |
| `code-reviewer` | Python/Remotion review focused on tensor dtype, VRAM patterns, banned imports |
| `niche-researcher` | Migrated from `.opencode/agent/` into `.kilo/agents/`, original left untouched |

- `.kilo/hooks/pre-push.sh` (symlinked from `.git/hooks/pre-push`)
  blocks oversized files and secrets at push time — confirmed working
  in production multiple times this session.
- `.kilo/kilo.jsonc` holds both the `autoApproval` block (global
  YOLO-mode config — this broke once mid-session when a rewrite
  dropped it, since fixed) and the per-agent `permission` schema.
- **Decided, not yet installed:** `Ponytail` (DietrichGebert/ponytail,
  MIT) — a minimal-code-first skill for coding agents. Useful for
  point-fixes in existing code; explicitly NOT expected to help much
  on exploratory/research tasks (new pipeline/model work), per the
  tool's own documented scope. Install prompt was dispatched but
  result not yet confirmed — check this first on resume.
- External tool candidates researched and explicitly rejected with
  reasons on file in `docs/AGENT_BUILD_PROPOSAL.md`: gitleaks,
  pre-commit, husky (redundant with the custom hook above), GitHub MCP
  Server (too broad), Spec Kit (real Kilo integration exists but is
  IDE-only, not CLI, and its `init` mutates a non-empty repo — risky),
  OpenHands (a whole separate agent runtime, not a plugin).

## 4. Environment — all blockers closed (NEW)

All of these were open blockers earlier this session, now resolved and
verified with real command output (not just claimed):

- `pytest` 9.1.1 — present.
- `kaggle` CLI — installed, **authenticated** (account `FORTS_FACTORY`,
  confirmed via `kaggle kernels list --mine`), API token supplied via
  environment variable, not a committed `kaggle.json`.
- `ffmpeg`/`ffprobe` 6.1.1 — installed with `--enable-gpl` confirmed.
- Kokoro TTS venv at `/tmp/kilo/z1_venv` — Python **3.12.3** (not the
  system's 3.14.2, which is incompatible with `kokoro`), `kokoro==0.2.2`,
  `misaki==0.7.4`, voice `af_heart` confirmed working.
- **Remotion license** — confirmed Free License applies (solo project,
  one person, under the "≤3 employees" threshold); Company License not
  needed. `node_modules` installed in `remotion-composer/`.
- Pinned, locked versions (do not change without an explicit owner
  decision — `dependency-guard` enforces this):
  `diffusers==0.37.0`, `transformers==4.57.6`, `huggingface_hub==0.36.2`.

## 5. Image model — RESOLVED this session (supersedes §5 of the old handoff)

**Final answer: FLUX.2 Klein 4B (black-forest-labs, Apache-2.0),
generating directly, no adapter needed.** DreamShaper XL is NOT used
(its own commercial license was never confirmed against an official
source — treated as unresolved, dropped rather than risked).

What got here, in order:
- IP-Adapter Plus / Plus Face failed **5 separate times** across a full
  day of testing (tensor-format guessing: 3D, 2D, tuples, [neg,pos]
  concatenation — all failed). **Root cause, found late:** the code was
  manually constructing `ip_adapter_image_embeds` by hand instead of
  calling the official `pipe.load_ip_adapter()` + `ip_adapter_image=
  <PIL.Image>` API — this exact mistake was flagged as the likely
  cause in the *original* handoff before this one and never actually
  fixed until near the end of this session. **Lesson for next time:**
  when official API docs exist, use them first; don't reconstruct
  internals by hand and iterate on format guesses.
- A real, clean baseline test (SDXL Base 1.0, no adapter, 768×768, fp16,
  VAE slicing/tiling, CPU offload) passed 45/45 at 4 independent reruns,
  peak VRAM only 5.2GB — proving VRAM was never actually the blocker;
  the adapter integration code was.
- **FLUX.2 Klein 4B** was initially (wrongly) marked incompatible with
  pinned `diffusers==0.37.0` — that conclusion was based on an error
  thrown by the wrong pipeline class (`FluxPipeline`, for FLUX.1, not
  `Flux2KleinPipeline`). Diffusers 0.37.0 release notes confirm
  Flux2Klein support was added in that release. **No diffusers upgrade
  was needed — this was a code bug, not a version blocker.**
- Official Klein 4B settings confirmed from Black Forest Labs docs: 4
  inference steps, `guidance_scale=1.0` (CFG is distilled out — write
  prompts positively only, no negative prompts), sizes multiple of 16,
  **up to 4 reference images for native multi-reference consistency**
  (no IP-Adapter needed at all), narrative/detailed prompting (no
  prompt-upsampling built in).
- **FLUX 3 Image Klein** (released ~2 weeks before this session,
  5.6B params) was investigated and explicitly excluded: official BFL
  technical docs put minimum VRAM at 25GB even quantized (NVFP4) — the
  T4 has 14.56GB usable. Press articles claiming "8GB" were about a
  different, unrelated community build, not the official release —
  don't re-trust that figure without re-verifying against BFL's own
  docs.
- **Real Kaggle measurement for Klein 4B: 11.15GB peak VRAM, `bfloat16`
  worked directly (no float16 fallback needed), ~90s/frame.** 78 pilot
  frames generated across 3 Kaggle kernels (~117 min total GPU time),
  all COMPLETE, zero NaN/black frames.

## 6. Pilot production status (NEW — in progress)

- **78 frames generated** via FLUX.2 Klein 4B at 1280×720, saved to
  `tools/kaggle_bridge/jobs/pilot-render/frames_klein/`. Contact sheets
  (7 files, 4×3 grid, numbered) await owner review — **not yet
  approved**.
- **Host character reference not yet chosen.** 8 candidate master
  references exist at
  `tools/kaggle_bridge/jobs/consistency-ab-test/contact_sheet_master.jpg`
  — owner has not picked one yet. A v2 regeneration with a more
  explicit style prompt (thick bold outer contour, chibi proportions,
  large expressive eyes, worn-clothing texture — matching a reference
  style the owner liked) may also be in progress; check `RUN_STATE.md`
  for whether v2 exists yet.
- **10 narration audio files** generated via Kokoro (`af_heart`),
  total 18:20 — about 10% shorter than the ~20-21 min target (TTS pace
  vs. assumed 150 wpm human pace). Not yet decided whether to adjust
  TTS speed or accept the shorter runtime.
- **A full draft assembly exists** (`pilot-final.mp4`, via ffmpeg, NOT
  Remotion — a background Remotion render was abandoned at ~3% after
  a multi-hour ETA estimate). This draft used the OLD SDXL frames (only
  10, not 78) and had two confirmed problems, since partially fixed in
  a later pass — **verify the latest state rather than assuming either
  version**:
  - Audio was too quiet (−25.6 LUFS vs. YouTube's ~−14 target) — a
    mastering chain (acompressor + alimiter + loudnorm) was applied in
    a later pass, measured result −15.7 LUFS / −1.5 dBTP, within target.
  - Subtitles were one giant unreadable block per section (whole
    paragraph, ~60px, clipped at the top) — reworked into proper
    per-line SRT timing (2-5s chunks, ≤42 chars/line) in the same later
    pass; spot-checked, not fully reviewed by the owner.
  - Only 9 cuts in 18 minutes (one frame held 48-149 seconds) — this is
    why the 78-frame Klein regeneration happened; the OLD assembly has
    not yet been rebuilt with the new frame count.
- **No music bed yet** — `assets/music/` is empty. Owner needs to
  manually source a track from YouTube Audio Library; this is not
  something an agent can do.
- **Competitor research (new pipeline-quality step) is BLOCKED**,
  waiting on the owner to supply 3-5 links to specific competitor
  videos in the science-grounded-speculation niche, so an agent can
  pull transcripts (via `yt-dlp`, confirmed as the chosen tool — a
  `youtube-watch-mcp` tool was found but only does new-upload
  notifications, not transcript/content analysis) and measure pacing
  (words/min, average scene-block length) against the pilot's current
  9-cuts-in-18-minutes pacing.

## 7. Open decisions for the owner (not assumed by anyone)

- **Pick the host character's master reference** (1 of 8, or from a v2
  regeneration) — nothing downstream of character consistency can be
  finalized without this.
- **Review and approve the 78 pilot frames** (or flag specific numbers
  for regeneration).
- **Source the music bed** from YouTube Audio Library, drop into
  `assets/music/`.
- **Supply 3-5 competitor video links** to unblock pacing research.
- Host character's name — still not chosen.
- Whether the host "speaks" with Kokoro's `af_heart` voice or is a
  silent on-screen figure with a separate narrator voice — still not
  decided.
- Whether to adjust TTS pacing to hit ~20-21 min, or accept 18:20 as
  final runtime.
- Whether to proceed with `Ponytail` installation (research dispatched,
  not yet confirmed done).

## 8. Immediate next step when resuming

1. Check whether the Ponytail install prompt completed, and whether a
   v2 master-reference contact sheet exists.
2. Get the three owner decisions in §7 that are pure blockers (master
   reference number, frame approval, music file) — nothing else can
   finish without them.
3. Once a master reference is picked: rebuild `pilot-final.mp4` using
   all 78 Klein frames (not the old 10 SDXL ones), with the
   already-fixed subtitle timing and audio mastering carried over.
4. Competitor pacing research stays blocked until links are supplied —
   don't let an agent pick channels on its own.
