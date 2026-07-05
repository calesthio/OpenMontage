# OpenMontage — Hero-Tier Quality Strategy

> **Deep research: the best-quality way to produce images, video, voice, and music — and the
> refinement stack to bolt on.** Compiled 2026-07-05. The companion to `COST_OPTIMIZATION_RESEARCH.md`:
> cost decides where cheap models run; this decides how the *hero* shots become excellent.
> Findings tagged `[verified]` passed 3-vote adversarial verification; `[gap]` did not survive — treat as open.

---

## TL;DR — the thesis

**Hero quality is not one better model. It's an orchestrated stack applied only to shots that are seen.**
Route the shots viewers judge to the current arena winners, run a short refinement chain on those,
and **stop before diminishing returns** — the research is blunt that most "more quality" beyond a
low-denoise refine + a proper audio master is placebo. This composes exactly with the
`quality_tier="hero"` router from PR #299: `hero` triggers the full chain, `draft` skips it.

**Two honest gaps up front:** zero verified evidence survived on **voice** (ElevenLabs v3 / Cartesia / Hume)
or **music** (Suno / Udio) models — those recommendations need their own research pass. And the *numeric*
"how much better" for upscalers was refuted — the gain is directionally real, not quantified.

---

## 1. SOTA hero models (2026, blind human-preference)

### 🖼️ Image — a clear winner `[verified]`
**GPT Image 2 (high) is the decisive #1.** Artificial Analysis Elo **1340** (13k+ blind votes),
+59 over #2 Reve 2.0; llm-stats ranks it #1 by a **>350-point** margin. Specifically best for
**text-in-image and prompt adherence** — surpasses FLUX.2 [max], Seedream 4.0, Nano Banana 2.
- **Exception:** Ideogram 4.0 still edges it for *stylized/decorative typography*.
- **Action:** route hero images (esp. anything with text or precise prompts) to **GPT Image 2** via
  your `openai_image` tool. Keep FLUX for cheap/bulk.

### 🎬 Video — no single champion; route by axis `[verified]`
The two authoritative blind arenas name **different** winners — pick by what the shot needs:

| Need | Winner | Why |
|---|---|---|
| Multi-shot control, consistency, audio | **Seedance 2.0** | #1 on AA with-audio i2v (Elo 1189, +77). Unique **@-reference system** (tag up to 9 images / 3 videos / **3 audio files**) → best compositional + identity control. |
| Motion physics / realism | **Kling v3** | #1 on llm-stats (TrueSkill 2035) for motion physics & object permanence. |

- **Native synced audio is now table stakes** — Seedance 2.0, Sora 2, Kling 3, Veo 3.1 all ship it. The
  differentiator is *control*: only Seedance accepts audio-file references.
- **Action:** hero video → **Seedance** for controlled/narrative/consistent shots, **Kling** for
  motion-showcase shots. Both already wired via `video_selector`.

### 🗣️ Voice — the default is *not* #1 `[verified]`
On the Artificial Analysis blind **Speech Arena** (2026), ElevenLabs is **outside the top 5**. The top
cluster is a near-tie: **Gemini 3.1 Flash TTS (~1215) #1** and **Cartesia Sonic 3.5 (~1209) #2** (±16 Elo).
- **But** the arena measures only *short-sample naturalness* — **not** voice-cloning fidelity or long-form
  stability, where ElevenLabs stays strong; and >58% of listeners can't tell top synthetic voices from real,
  so the naturalness gap is largely closed.
- **Action (additive):** add **Gemini 3.1 Flash TTS** as the hero-naturalness voice (shipped: `gemini_tts`,
  reuses your Google key). Keep **ElevenLabs** for cloning / brand voice / long-form / emotion-tags, and
  **Kokoro** for bulk. Cartesia Sonic 3.5 is the runner-up (and the latency king, ~82ms).

### 🎵 Music — the default is validated `[verified]`
On the AA blind **Instrumental Music Arena**, **Suno V5.5 is #1 (~1193)** and holds three of the top five.
**Keep Suno as the hero-music default — no change needed.**
- **Runner-up:** **Google Lyria 3 Pro** — best *song structure* (definable sections) and "safe", Content-ID-clear,
  licensed-data output for branded/background/loop music. Prefer it when you need structural control or
  guaranteed commercial/Content-ID safety over raw acoustic depth.
- **Licensing:** Suno commercial rights require a **paid plan** (not retroactive). **Avoid Udio** — post-UMG
  settlement it became a stream-only walled garden (no download/export), a poor fit for a video product.

**Unverified gaps:** no API-availability or per-unit **cost** data survived for the voice/music winners —
confirm pricing/quotas before high-volume hero use. The Gemini TTS model id and audio schema are marked
calibration knobs in `gemini_tts` (confirm against the live API on first run).

---

## 2. The refinement stack — what to ADD / UPGRADE

Mapped to what you already have (`upscale`=RealESRGAN, `face_restore`=CodeFormer/GFPGAN,
`face_enhance`/`color_grade`=FFmpeg, `audio_enhance`=FFmpeg loudnorm).

| Step | You have | Add / upgrade | Verdict |
|---|---|---|---|
| **Image refine/upscale** | RealESRGAN (feed-forward) | **Clarity / SUPIR** diffusion refiner at **low denoise ~0.35** | ✅ **shipped this PR** (`clarity_upscale`). Real detail on hero stills; keep RealESRGAN for text/architecture/bulk. |
| **Face** | CodeFormer + GFPGAN | — | Keep. Already SOTA-adjacent. |
| **Video super-res** | *(none)* | **SeedVR2** (Apache-2.0, one-step) or **FlashVSR** (Apache-2.0) | 🔜 build-next. Fills a real gap; open-weight, self-hostable. |
| **Frame interpolation** | *(none)* | **Topaz Chronos/Aion** or open **RIFE/FILM** → 60fps | 🔜 build-next, **hero-only + opt-in** (soap-opera-effect risk; viewer value unproven). |
| **Audio master** | FFmpeg `loudnorm` (-16 LUFS presets) | two-pass loudnorm + per-platform targets | ⚠️ mostly done. Minor upgrade: two-pass accuracy. Don't hardcode -14 LUFS (refuted). |
| **Color/finish** | FFmpeg color_grade | LUTs / film grain | `[gap]` — unverified as a pro/amateur separator; skip until evidenced. |

### Consistency across shots `[verified, inferred]`
The 2026 winner is **multi-reference single-generation** (Seedance's @-reference), **not** per-shot
LoRA/IP-Adapter stitching. Identity/style is increasingly solved *at generation time*. Lean on Seedance
references for multi-scene coherence rather than a downstream consistency pass.

---

## 3. The orchestrated hero-tier stack

Run this chain **only on `quality_tier="hero"`** assets; draft/bulk skip it entirely.

```
IMAGE  GPT Image 2 → Clarity refine (denoise 0.35) → CodeFormer (faces only) → grade
VIDEO  Seedance 2.0 / Kling v3 → SeedVR2 super-res → [RIFE 60fps, opt-in] → grade
AUDIO  ElevenLabs/Suno → loudnorm master (-16 LUFS, -1 dBTP) → duck under VO
```

**Order matters:** refine/restore *before* upscale; upscale *before* interpolate; grade + master last.

---

## 4. Real vs. placebo (be honest)

**Confident, evidence-backed wins:**
- Routing hero shots to the actual arena #1 (GPT Image 2; Seedance/Kling).
- A **low-denoise** diffusion refine on hero stills.
- A proper **loudness master** (you already have it).

**Diminishing returns / unproven — don't oversell:**
- **Upscaler magnitude** — the "SUPIR 4.2 vs RealESRGAN 3.6 MOS" numbers were **refuted**. The gain is real in
  direction, not size. High denoise **hallucinates** (text, faces, architecture) — that's why default is 0.35.
- **60fps interpolation** — whether viewers *prefer* interpolated cinematic AI shots is **unresolved**
  (soap-opera effect). Ship it opt-in, not default.
- **LUTs / grain / "cinematic" post** — no surviving evidence it separates pro from amateur. Skip until proven.
- **-14 LUFS "social standard"** — **refuted.** Targets differ by platform; keep it configurable.

---

## 5. Per-hero-shot cost (so it's deliberate)

Hero refinement is cheap *because it's rare*: Clarity refine ~$0.05/image, hero video model ~$0.30–0.50/clip,
SeedVR2 self-hosted ~cents. The whole point of the `hero`/`draft` split is that this only touches the
handful of shots that carry the piece.

---

## 6. Open questions (need their own research pass)

- **Voice** #1 by blind preference (ElevenLabs v3 vs Cartesia Sonic vs Hume Octave) — unverified here.
- **Music** #1 (Suno v5 vs Udio vs Riffusion) — unverified here.
- **Upscaler perceptual delta** over RealESRGAN — magnitude unproven.
- **Interpolation viewer preference** for cinematic content — unresolved.
- **Correct 2026 per-platform LUFS/true-peak targets** (TikTok / Reels / YouTube).
- **Composition finishing** (LUTs/grain/camera motion) as pro separators — no evidence yet.

---

## Sources

- Image leaderboard — https://artificialanalysis.ai/image/leaderboard/text-to-image · https://llm-stats.com/leaderboards/best-ai-for-image-generation
- Video leaderboard — https://artificialanalysis.ai/video/leaderboard/image-to-video · https://llm-stats.com/leaderboards/best-ai-for-video-generation
- Upscalers — https://blog.finegrain.ai/posts/reproducing-clarity-upscaler/ · SUPIR arXiv:2401.13627 · NTIRE 2025 face-restoration challenge
- Video SR/interp — https://upsampler.com/blog/seedvr-vs-flashvsr-ai-video-super-resolution-2026 (SeedVR2 arXiv:2506.05301) · https://unifab.ai/resource/topaz-video-ai-frame-interpolation
- Loudness — EBU R128 (tech.ebu.ch/docs/r/r128.pdf; ITU-R BS.1770) · https://www.criticallisteninglab.com/en/learn/loudness

*Method: 5 search angles → 24 sources → 25 claims → 3-vote adversarial verification (15 confirmed, 10 refuted). 110 agents.*
