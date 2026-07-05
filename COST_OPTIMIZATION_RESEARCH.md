# OpenMontage — Generation Cost Strategy

> **Deep research report: cheaper AI image/video/TTS/music generation without killing quality.**
> Compiled 2026-07-05. Pricing is a July 2026 snapshot — **verify live before committing money.**
> Findings tagged `[verified]` passed 3-vote adversarial verification; `[single-source]` / `[derived]` did not — treat as directional, validate before relying on them.

---

## TL;DR — Bottom line first

**Your architecture already won half this battle.** You have `ltx_video_modal`, `ltx_video_local`, `comfyui_image`, `comfyui_video`, `local_diffusion`, `piper_tts`, and `music_gen` wired behind the `image_selector` / `video_selector` / `tts_selector` pattern. This is a **configuration + routing** problem, **not a rewrite.**

The move is a **3-tier router**:

| Tier | Routes to | Tool to light up | Cost/unit | vs. now |
|---|---|---|---|---|
| **Premium (keep)** | Hero shots, final client-facing motion, lip-sync | `kling_video`, `seedance_video`, `veo_video` (fal) | $0.30/clip | baseline |
| **Self-host open (grow)** | Bulk B-roll, drafts, iterations | `ltx_video_modal` / `comfyui_video` | **~$0.02/clip** | **~15-18× cheaper** |
| **Free local (default now)** | TTS, music, most images | Kokoro/`piper`, ACE-Step/`music_gen`, SDXL | **~$0** marginal | **20-50× cheaper** |

**The single most important verified finding:** the *entire top-15 of the blind human-preference text-to-video leaderboard is proprietary.* The best open video model (LTX-2.3 Fast, Elo 977) trails the #1 closed model (Dreamina Seedance 2.0, Elo 1,222) by **~245 Elo (~80% win-rate for the closed model)**. `[verified]`

➡️ **"Self-host everything" is wrong for video. Tiering is not a compromise — it's the correct answer.**

- **Where cheap wins outright (do first, low risk):** music, TTS, images.
- **Where cheap is a real tradeoff:** video quality.

---

## 1. The money — break-even at your three volumes

**Verified pricing anchors:**
- RunPod RTX 4090 **$0.69/hr** on-demand (Secure Cloud); Community tier ~$0.34/hr `[verified / caveat]`
- Modal serverless A100 80GB **$2.50/hr**, per-second billed `[verified]`
- A100 80GB: ~$0.60/hr spot, ~$1.07/hr on-demand `[verified]`
- LTX throughput on a 4090 ≈ **40 clips/hr** (~90s per 5s clip) `[single-source]`
- Your API baselines: **$0.30/clip, $0.05/image** (from `tools/cost_tracker.py`)

### Video (5-second clips)

| Monthly volume | Current API | Serverless (Modal, pay-per-clip) | On-demand GPU (spin up for batch) | 24/7 rented 4090 | **Cheapest** |
|---|---|---|---|---|---|
| **100 clips** (low) | $30 | ~$6 | impractical | $497 | **Keep API** (ops not worth it) or serverless |
| **2,000 clips** (medium) | $600 | ~$120 | **~$35** (≈50 GPU-hrs) | $497 | **On-demand batch GPU** |
| **20,000 clips** (high) | $6,000 | ~$1,200 | ~$350 | **~$497** | **24/7 rented → then own hardware** |

**Crossover points** `[derived]`:
- A 24/7 rented 4090 (~$497/mo) beats per-call video API once you exceed **~1,650 clips/month**.
- Below that → serverless or spin-up-for-batch.
- Above ~15-20k/mo → **buy a used 3090/4090** (~$700-1,600 capex, amortizes in 1-3 months at these savings).

### Images / TTS / music
- Images are fast (SDXL ~5s, FLUX-schnell <2s on a 4090 → 700-1000/hr) → GPU cost **<$0.002/image vs $0.05 API ≈ 25× cheaper.**
- TTS (Kokoro) and music (ACE-Step) run at **15-30× realtime** → effectively free.
- **No meaningful quality reason to keep these on paid APIs for bulk work.**

---

## 2. Per-capability verdict (with honest quality labels)

### 🎬 Video — tier it, don't replace it `[verified]`
- Open models trail closed by ~245 Elo. Real artifacts: **temporal flicker, weaker prompt adherence, less coherent motion.**
- **LTX is your bulk workhorse** — verified throughput leader (~40 clips/hr on a 4090 vs ~14 for Wan 2.2, ~10 for HunyuanVideo, ~7.5 for Mochi-1). You already have `ltx_video_modal` + `ltx_video_local`.
- **Route:** drafts / iterations / background B-roll → LTX self-host. Final hero shots the viewer judges → keep Kling/Seedance/Veo.
- VRAM: A100 80GB fits all major open video models (Wan 2.2 14B FP16 ~54-65GB, or FP8/GGUF at 22-26GB). A 4090 (24GB) runs the quantized variants. `[verified/medium]`
- License: Wan/Hunyuan/LTX are generally permissive — **verify each before commercial use.**

### 🖼️ Images — big win, one license landmine `[single-source, verify]`
- On a 4090: FLUX.1-dev ~12s/img, SDXL ~5s.
- **⚠️ FLUX.1-dev and FLUX.2-dev are NON-COMMERCIAL license only.** For commercial use route to **FLUX.1-schnell (Apache), SDXL, SD3.5, or Qwen-Image.**
- VRAM: FLUX.1-dev ~33GB FP16 / ~12GB GGUF-Q4; SDXL ~8GB; SD3.5-Large ~18GB.
- Your `tools/graphics/local_diffusion.py` currently defaults to `stabilityai/stable-diffusion-2-1-base` — **dated.** Repoint to SDXL / FLUX-schnell, or wire `comfyui_image`.
- Quality gap to FLUX-pro/Imagen exists but is **much smaller than video's** — SDXL/schnell are production-usable for most B-roll and backgrounds.

### 🗣️ TTS — go local now, keep ElevenLabs for hero VO `[single-source, verify]`
- **Kokoro-82M** (Apache 2.0): RTF ~0.03 on GPU, runs on **CPU**, <0.3s/clip. Effectively free, no GPU needed. Quality: clean, less emotional range than ElevenLabs.
- **Chatterbox** (MIT): a *vendor-run* blind test claims 65% preference over ElevenLabs Turbo — **treat with salt**, but a credible expressive option, 4-16GB VRAM.
- You already have `tools/audio/piper_tts.py` (the robotic floor). **Add a Kokoro tool** (one `BaseTool`; auto-registers via `tts_selector`). Keep ElevenLabs only for narration the audience scrutinizes.
- Break-even to justify a *dedicated GPU* for TTS is ~4-5M chars/mo — but Kokoro-on-CPU sidesteps that entirely.

### 🎵 Music — the cleanest win of all `[verified]`
- **ACE-Step** (Apache 2.0): renders **4 min of music in ~20s on an A100**, **15.6× realtime on a consumer 4090**, ~8GB VRAM. No license gotcha. **This environment ships an `acestep` skill**, and you already have `tools/audio/music_gen.py` (MusicGen).
- Caveat: quality-vs-Suno parity is **not proven** (the "between Suno v3 and v3.5" claim was **refuted**). But for background beds it's more than good enough.
- **Route bulk music → ACE-Step / MusicGen. Keep `suno_music` for hero tracks only.**
- Other open options: MusicGen (~12GB), Stable Audio Open (~12GB), YuE (~16GB).

---

## 3. Infrastructure — which host, when

| Option | Best when | Notes |
|---|---|---|
| **Serverless (Modal)** — pay-per-second, scales to zero | Low / bursty volume where a dedicated GPU would idle | Your `ltx_video_modal` is exactly this. ⚠️ Cold-start latency is **real but unquantified** — budget for model-load overhead, measure it. |
| **On-demand rented (RunPod / Vast)** — spin up, batch a queue, spin down | Medium volume | RunPod Community 4090 ~$0.34/hr; Vast.ai **spot ~50%+ cheaper** for fault-tolerant batch (needs checkpoint/retry for preemption). |
| **24/7 rented → owned hardware** | High sustained volume (>~1,650 clips/mo) | Used 3090/4090 amortizes in 1-3 months at these savings. |

**Egress matters `[verified/medium]`:** RunPod / Lambda / Salad / Voltage Park charge **$0 egress**; hyperscalers charge $0.087-0.12/GB (AWS $0.09, Azure $0.087, GCP $0.12). Serving large video off AWS quietly taxes you — **stay on GPU-specialist hosts.**

**Provider price snapshot `[verified where noted]`:**
- **RunPod on-demand:** RTX 3090 $0.46, RTX 4090 $0.69, RTX 5090 $0.99, L40S $0.99, A100-80GB $1.39-1.49, H100 $2.89-3.29, H200 $4.39 (per hr). Community tier cheaper.
- **Modal serverless (per-sec → /hr):** L40S $1.95, A100-40GB $2.10, A100-80GB $2.50, H100 $3.95, H200 $4.54.
- **Lambda on-demand:** A100-80GB $1.99, H100 SXM $4.29 (pricier for single GPUs — use as stable free-egress baseline, not cost floor).
- **Vast.ai spot:** ~50%+ below on-demand; variable auction, not a guaranteed floor.

---

## 4. Where "cheap" actually loses (be honest)

1. **Video quality** — the 245-Elo gap is real and visible. Don't downgrade hero shots.
2. **Cold starts** — serverless first-request latency is unquantified; can add minutes with model-load. Bad for interactive, fine for queued batch.
3. **Ops burden** — self-hosting adds a GPU/queue/retry surface your per-call APIs hide. Real engineering time.
4. **Spot preemption** — cheapest tier, but jobs die mid-render. Needs idempotent retry.
5. **Licenses** — FLUX-dev non-commercial is the trap. Audit every open weight before commercial use.

---

## 5. Concrete next steps — mapped to your repo

| # | Step | Effort | Payoff |
|---|---|---|---|
| 1 | **Music (do today):** wire ACE-Step via the `acestep` skill alongside `music_gen`; make `suno_music` hero-only in the asset director | small | zero-risk win |
| 2 | **TTS (this week):** add a Kokoro `BaseTool` (CPU-capable, auto-registers via `tts_selector`); demote ElevenLabs to hero VO | small | ~free TTS |
| 3 | **Images (this week):** repoint `local_diffusion` default SD-2.1 → **SDXL / FLUX-schnell** (commercial-safe), or stand up `comfyui_image` | small | ~25× cheaper images |
| 4 | **Video (the big one):** deploy `ltx_video_modal` to a Modal endpoint (`MODAL_LTX2_ENDPOINT_URL`); add a `quality_tier: draft\|hero` field so `video_selector` routes draft→LTX, hero→Kling/Seedance | medium | ~15× cheaper bulk video |
| 5 | **Router policy:** add `tier → provider` to the selectors; extend `cost_tracker` to log tier so savings are visible | medium | measurable ROI |

**Recommended order:** 1 → 2 → 3 → 4/5. Step 1 is the smallest diff with the clearest payoff.

---

## 6. What this research did NOT establish (don't over-trust)

- **Serverless cold-start latencies** — *every* specific number was refuted in verification. Measure yours.
- **Image / TTS quality parity** — single-source only; validate with your own eval before cutting over hero work.
- **A100/H100 video throughput** — only 4090 clip-times are verified; serverless video pricing is extrapolated.
- **ACE-Step vs Suno quality** — the "between Suno v3/v3.5" claim was **refuted**; open music is fast/cheap/licensable but quality parity is unproven.
- All GPU prices are a **July 2026 snapshot** — RunPod Community + Vast.ai lows push the real floor *below* the quoted numbers.

---

## Sources

**Primary (vendor / leaderboard):**
- Modal pricing — https://modal.com/pricing
- RunPod pricing — https://www.runpod.io/pricing
- Lambda pricing — https://lambda.ai/pricing
- Vast.ai pricing — https://vast.ai/pricing
- Text-to-video Elo leaderboard — https://artificialanalysis.ai/video/leaderboard/text-to-video
- ACE-Step technical report — https://arxiv.org/html/2506.00045v1 · https://ace-step.github.io/

**Secondary / blog (directional):**
- GPU cloud pricing 2026 — https://www.spheron.network/blog/gpu-cloud-pricing-comparison-2026/
- Local AI video generation — https://localaimaster.com/blog/local-ai-video-generation
- Open image models compared — https://willitrunai.com/blog/flux-vs-sdxl-vs-sd35-comparison · https://localaimaster.com/blog/best-local-image-models-compared
- Open TTS on GPU cloud — https://www.spheron.network/blog/deploy-open-source-tts-gpu-cloud-2026/
- Data egress reference — https://gpuperhour.com/reference/data-egress
- ComfyUI self-host vs serverless — https://www.runflow.io/blog/comfyui-deploy-self-host-serverless-managed

*Research method: 5 search angles → 24 sources fetched → 115 claims extracted → 25 verified via 3-vote adversarial check (15 confirmed, 10 refuted).*
