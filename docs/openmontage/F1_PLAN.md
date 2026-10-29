# F1 — Read-only inventory and weekly plan

**Date:** 2026-10-23
**Author:** OpenCode, inline (not independent)
**Mode:** read-only. No commits, no installs, no deletes, no paid routes.
**Secrets:** no `.env`, token file, `kaggle.json`, `client_secret*` was opened or printed.
Presence is reported by name only.
**Environment observed:** `git branch` = `kilo/mega-100`; `/workspaces` 3.4 GB free (89 % used);
CPU only (`nvidia-smi` absent); `KAGGLE_API_TOKEN` present (env var, value not read).

Status legend:

| Status | Meaning |
|---|---|
| **VERIFIED** | observed in this session with the command shown in §7 |
| **RECORDED** | asserted by a repo doc and not re-run now |
| **UNVERIFIED** | no evidence; must be proven before it is counted |
| **MISSING** | does not exist in this environment |

---

## 1. Inventory

### 1.1 Rules, agent configs, skills, MCP

| Item | Purpose | Stage | Status |
|---|---|---|---|
| `AGENTS.md` (146 lines) | factory roster, permissions, waiting rule, rights/publishing hard rules | all | **VERIFIED** (read) |
| `AGENT_GUIDE.md` (720 lines) | routing: first action per request type | all | **RECORDED** (not re-read this session) |
| `docs/openmontage/RUN_RULES.md` | owned paths, git rules, test-first, $0, fail-closed QC, reporting | all | **VERIFIED** (read) |
| `.kilo/agents/{editor,qa-reviewer,evidence-checker,footage-scout}.md` | 4 subagents, explicit permission maps, write scopes | edit / QC / evidence / footage | **VERIFIED** (listed; `editor.md` read) |
| `.opencode/agent/niche-researcher.md` | research subagent bound to the `niche-finder` MCP | niche research | **VERIFIED** (read head) |
| `.opencode/skill/youtube-niche-research/SKILL.md` | niche method + quota discipline | niche research | **VERIFIED** (listed) |
| `skills/{core,creative,meta,pipelines}/` | 91 Layer-3 skills (tool usage knowledge) | all | **VERIFIED** (count) |
| `.kilo/skills/` | 20 project skills (`yt-package`, `yt-chapters`, `yt-seo`, `yt-shorts`, `youtube-quality-gate`, `edl-edit`, `cutting-rhythm`, `audio-edit`, `video-pipeline-ffmpeg`, `licensed-footage-audit`, …) | script → package | **VERIFIED** (count + `yt-package` read) |
| `.agents/skills/` | 91 vendor-style skills (ffmpeg, hyperframes, remotion, TTS, music…) | all | **VERIFIED** (count) |
| `.claude/commands/` (3), `.codex/prompts/`, `.cursor/{commands,rules}/`, `.windsurfrules` | alternate-agent entry points | all | **VERIFIED** (listed) |
| `opencode.json` | MCP config: **one** server, `niche-finder` (local `youtube-niche-finder/scripts/mcp-host.sh`) | niche research | **VERIFIED** (read) |
| `pipeline_defs/*.yaml` (10) | pipeline stage graphs (`business-documentary`, `documentary-montage`, …) | orchestration | **VERIFIED** (listed) |

No YouTube, Kaggle, filesystem or database MCP is configured. The only MCP is niche research.

### 1.2 CLI tools

| Tool | Version observed | Used for | Status |
|---|---|---|---|
| `ffmpeg` / `ffprobe` | 6.1.1-3ubuntu5 | render, mux, loudness, QC probes | **VERIFIED** |
| `python3` | 3.14.2 | all pipeline code | **VERIFIED** |
| `kaggle` | 2.2.4 (CLI warns 2.2.5 available) | kernel push/status/fetch | **VERIFIED**: `kaggle kernels list --mine` → exit 0, 3 kernels |
| `espeak-ng` | 1.51 | only local TTS present | **VERIFIED** (P0 run) |
| `node` / `npm` | 24.21.0 / 11.19.0 | Remotion/HyperFrames **not installed** (`remotion-composer/node_modules` absent) | **VERIFIED** |
| `git`, `curl`, `jq` | 2.55.0, 8.5.0, 1.7 | code, downloads, JSON | **VERIFIED** |
| ImageMagick (`convert`/`magick`) | — | contact sheets, thumbnails | **MISSING** |
| `nvidia-smi` / CUDA | — | local GPU | **MISSING** (CPU only) |

### 1.3 Python environment

Present: `numpy 2.5.4`, `pillow 13.0.0`, `soundfile 0.14.0`, `requests 2.34.2`,
`pydantic 2.14.1`, `jsonschema 4.26.0`, `pytest 9.1.1`, `google-auth 2.62.0`.

Missing and material: `torch`, `onnxruntime`, `kokoro`, `piper`, `cv2`, `imagehash`,
`scipy`, `googleapiclient` (YouTube upload), `google_auth_oauthlib`, `yt_dlp`.
No new package may be installed under F1.

### 1.4 Tool registry — 141 tools, 41 available

`registry.discover()` → `tools total: 141 available: 41`.

| Stage | Available (VERIFIED by registry) | Unavailable / missing |
|---|---|---|
| Script / evidence | `claim_ids_resolve` inside `qc`; ledgers + `_parse_script_rows` in `run_episode.py` | no storyboard-from-assets tool |
| TTS | **none** (all 14 TTS tools `unavailable`; no piper binary/voice, no kokoro) | `piper_tts`, `tts_kaggle` (Kokoro via Kaggle) needs bridge run |
| Images | `kaggle_bridge`; `local_diffusion` **unavailable**; no local GPU | `image_gen`, all 23 image providers, `comfyui_image` |
| Image QC | `illustration_qc` module (`qc_image`, `qc_batch`), `visual_qa`, `frame_sampler` | no 12-tile sheet mode (pack is 6/sheet) |
| Edit | `video_compose`, `video_stitch`, `video_trimmer`, `silence_cutter`, `hyperframes_compose`, `showcase_card`, `motion` lint module | Remotion runtime absent |
| Subtitles | `subtitle_gen`, `remotion_caption_burn` | burn-in not used for long-form (by spec) |
| Music | `pixabay_music` (scraper, no key), `music_library` **unavailable** (`music_library/` missing) | no licensed local bed; no licence evidence path exercised |
| Thumbnail | `showcase_card` (title card render only) | **no thumbnail generator** (1280×720 + text-safe area) |
| QC | `qc` (15 checks), `release_gate` | — |
| Package | `export_bundle` (local), `tools/packaging/package_builder.py` | no YouTube publisher |
| Upload | **none** | `youtube-publishing-analytics` is a doc stub only |
| Analytics | `analytics_import` | never ran on a published video |

### 1.5 Scripts that matter

| Script | Purpose | Status |
|---|---|---|
| `scripts/run_episode.py` | 10 stage commands: claim ledger → script → rights → narration → subtitles → EDL → render → finish_audio → QC → package → gates | **RECORDED** (540 s QC test suite passes per F1FIX; not re-run now) |
| `scripts/p0_smoke_run.py` | P0 end-to-end smoke (TTS → stills zoompan → SRT → mux) | **VERIFIED** (§7.4) |
| `scripts/s15_checks.py`, `s15_blind_pack.py`, `s15_tally.py` | objective image flags, blind sheets, owner tally | **RECORDED** (S15 run artifacts exist) |
| `scripts/image_engine.py` | model select/swap from `config/image_engine.json` | **RECORDED** |
| `scripts/review_pack.py`, `scripts/ci_fast_suite.py` | review bundle, 10-file CI | **RECORDED** |
| `tools/kaggle_bridge/kaggle_bridge.py` + `s15_style_lock_run.py` | submit/poll/fetch/verify Kaggle kernels | **VERIFIED** (auth) / run **RECORDED** |

### 1.6 Config

| File | Content | Status |
|---|---|---|
| `config/qc_thresholds.json` | strict JSON; `-14 LUFS ±2`, `-1.5 dBTP`, 2 s freeze, 0.1 silence, `illustration_qc` block | **VERIFIED** (loaded: `source=config/qc_thresholds.json`) |
| `config/voice.json` | voice + licence gate | **RECORDED** |
| `config/image_engine.json` | `klein` OWNER_GATED, `sdxl-lightning` fast fallback, seed policy 3000–3999 | **VERIFIED** (read) |

### 1.7 Secrets — names only

| Name | State |
|---|---|
| `KAGGLE_API_TOKEN` | **present** in env (value never read/printed) |
| `.env.example` | exists (owner-owned; not opened) |
| `~/.kaggle/` | absent |
| `client_secret*`, `kaggle.json`, `*.token`, `token.json` | not found in the repo (max-depth 3 scan) |

---

## 2. Map to an 18-min / ~150-sentence video

18 min = 1080 s; 150 sentences → **7.2 s per sentence/image** on average.
Because one image covers one sentence, the format is a still-led documentary: no B-roll inserts.

| # | Stage | Tool / command | Verified now? | Gap / decision |
|---|---|---|---|---|
| 1 | Topic + demand | `niche-finder` MCP (100 tools) | **UNVERIFIED** (not called in F1) | demand gate still doc-only |
| 2 | Claim ledger | `docs/openmontage/evidence/*_CLAIM_LEDGER.md` + `qc.claim_ids_resolve` | **RECORDED** | 2-source rule needs primary docs reachable |
| 3 | Script 150 rows | `run_episode.py cmd_script_validation` (`B<n>` rows) | **RECORDED** | 150 rows is 3.3× the largest script (46) |
| 4 | Narration | `tts_kaggle.py` (Kokoro-82M on Kaggle) | **UNVERIFIED** (longest recorded 428.6 s ≈ 7 min) | 18 min = **2.5×** longest verified; needs a 1080 s run |
| 5 | Audio finish | `finish_audio` | **VERIFIED** on 12.4 s: PASS in 0.87 s, −21.24 → −16.2 LUFS | output −16.2 is 0.2 LU outside QC band (−16.0); re-run and check |
| 6 | Images ×150 | Kaggle bridge + DreamShaper XL 1.0 / Lightning | **RECORDED** (S15/S12) | 150 images never produced in one job (max 42) |
| 7 | Image QC | `illustration_qc.qc_batch` | **VERIFIED**: existing stills **3/3 fail** a 1920×1080 target (1344×768, blur 49.5, text-like 1) | gate must target the generation bucket, then check the rendered 1080p frame |
| 8 | Blind review | `s15_blind_pack.py` | **RECORDED**, 6 tiles/sheet | need **12 tiles/sheet** → 13 sheets for 150 images (code change) |
| 9 | EDL | `run_episode.py cmd_edl` | **RECORDED**: generic, graphics-only | per-sentence cuts need image asset mapping (F2 scope) |
| 10 | Render | ffmpeg `zoompan` per P0 | **VERIFIED**: 1.143 s per video second | 150 ffmpeg processes ≈ +220 s startup |
| 11 | Subtitles | `subtitle_gen` | **VERIFIED**: 3 cues from measured durations | 150 cues fine; sentence-level only |
| 12 | Music | `pixabay_music` (scraper) | **UNVERIFIED**; `music_library` MISSING | licence evidence + attribution must be stored per track |
| 13 | QC | `qc` | **VERIFIED**: 15 checks, 6 PASS / 1 FAILED / 8 NOT_RUN on the P0 file | ebur128 FAILED because TTS was −21.3 LUFS; finish_audio is mandatory |
| 14 | Package | `package_builder.build_package` | **VERIFIED**: ok, 9 chapters, 46 sentences, 7 Shorts beats | chapters have **no timecodes**; tags are title words only |
| 15 | Export | `export_bundle` | **VERIFIED**: 5 files, `status: exported` | local only |
| 16 | Thumbnail | none | **MISSING** | must add 1280×720 + 3-word rule + safe area |
| 17 | Upload | none | **MISSING** | §4 plan, no implementation |
| 18 | Analytics | `analytics_import` | **UNVERIFIED** | needs a published video |

**Chain-level gaps for 150 sentences**

1. No narration run longer than 428.6 s has ever been produced.
2. No image job larger than 42 images has been run.
3. Existing stills are 1344×768 (1.75:1) and fail the 1920×1080 QC target; decide the bucket policy.
4. EDL does not yet map one image per script sentence.
5. Chapters in `metadata.json` are numbered, not timestamped; YouTube chapters require `0:00`-style lines.
6. No thumbnail generator, no uploader.

---

## 3. Weekly budget — 7 long + 14 Shorts

### 3.1 Measured constants (source in §7)

| Constant | Value | Source |
|---|---|---|
| DreamShaper XL 1.0 warm speed | **26.0 s/image** (26.003 median) | S15, 42 images; S12 26.259 |
| DreamShaper XL 1.0 load | **88 s** (87.697 / 84.901) | S12 / S15 |
| Lightning warm speed | **5.0 s/image** (5.121) | S12, 18 images |
| Lightning load | **41.5 s** (41.487) | S12 |
| CPU render ratio | **1.143 s per video second** (14.21 s / 12.432 s) | P0 smoke, 1080p30, CRF 20, veryfast |
| Single 5 s segment incl. process start | 7.69 s (1.54 s/s) | §7.5 |
| Audio finish | 0.87 s for 12.4 s audio (0.07 s/s) | §7.3 |
| QC on 12.4 s clip | ≈ 8–8.5 s (0.65 s/s, 6 full passes) | §7.2 timestamps |
| Final mp4 bitrate | 891 kb/s @1080p30 stills | P0 |
| PNG weight | 2.66 MB avg (S15 1024²); 0.46 MB (se_pilot 1344×768) | §7.6 |

### 3.2 Images needed

| Scenario | Formula | Images |
|---|---|---|
| 1 candidate + 30 % regen | 150 × 1 × 1.3 | **195** |
| 2 candidates + 30 % regen | 150 × 2 × 1.3 | **390** |
| 14 Shorts, 12 fresh images each, 1 cand + 30 % | 14 × 12 × 1.3 | **219** |
| 14 Shorts reusing long-form frames | — | **0 extra** (recommended) |

### 3.3 Kaggle GPU hours

Per 18-min video (images only; load counted once):

| Model | 195 images (1 cand) | 390 images (2 cand) |
|---|---|---|
| DreamShaper XL 1.0 @26 s | 5 158 s = **1.43 GPU-h** | 10 228 s = **2.84 GPU-h** |
| Lightning @5 s | 1 016 s = **0.28 GPU-h** | 1 992 s = **0.55 GPU-h** |

Per week:

| Scenario | 7 long videos | 14 Shorts (fresh 219 img) | **Week total** | Share of 30 h quota¹ |
|---|---|---|---|---|
| DS-XL, 1 cand | 10.03 h | 1.59 h | **11.6 h** | 39 % |
| DS-XL, 2 cand | 19.89 h | 1.59 h | **21.5 h** | 72 % |
| Lightning, 1 cand | 1.98 h | 0.31 h | **2.3 h** | 8 % |
| Lightning, 2 cand | 3.87 h | 0.31 h | **4.2 h** | 14 % |
| DS-XL 2 cand + Shorts reuse frames | 19.89 h | 0.00 h | **19.9 h** | 66 % |

¹ Kaggle's 30 h/week GPU allowance is **UNVERIFIED** in this repo (`KAGGLE_BRIDGE_DESIGN.md:239`
marks it assumed). The 12 h session cap is also assumed. No GPU quota was consumed in F1.

Narration: keep Kokoro on a **Kaggle CPU kernel** → 0 GPU-hours. Wall time for 1080 s of speech
is **UNVERIFIED** (no narration run > 428.6 s exists).

### 3.4 CPU render time (after P0)

- Long video: 1.143 s/s × 1080 s = **1 234 s (20.6 min)** + 147 extra ffmpeg startups
  (~1.5 s each) ≈ **1 450–1 560 s → 24–26 min per 18-min video**.
- 7 long videos: **2.8–3.0 h** CPU.
- 14 Shorts (60 s each): 840 s × ~1.5 = **21 min**.
- QC: 0.65 s/s × 1080 s ≈ **12 min per video** → 1.4 h/week.
- Audio finishing: 0.07 s/s ≈ **1.3 min per video** → 9 min/week.

**CPU total ≈ 4.5–5 h per week** (render + QC + audio). This fits a Codespace comfortably;
the constraint is Kaggle GPU, not CPU.

### 3.5 Disk

| Item per episode | Size |
|---|---|
| 195 PNG @2.66 MB | 0.52 GB (390 → 1.04 GB) |
| 150 segment mp4 + final mp4 | ≈ 0.12 + 0.12 GB |
| audio + subtitles + package | < 0.02 GB |
| **Per episode** | **0.8–1.4 GB** |
| 7 episodes + Shorts | **5.6–9.8 GB** |

Current free space is **3.4 GB** with an 800 MB floor → a 7-video week is **BLOCKED on disk**
unless intermediates are rotated (keep only final mp4 + SRT + package per episode: 0.14 GB each,
≈ 1 GB/week).

### 3.6 Weekly wall-clock shape (DS-XL, 2 candidates)

| Block | Time |
|---|---|
| GPU image generation | 21.5 h (queue-bound, 7 kernels) |
| Narration (Kaggle CPU) | UNVERIFIED |
| CPU render + QC + audio | ≈ 5 h |
| Owner review / blind scoring | owner-gated, not budgeted |

### 3.7 Budget risks

1. 30 h/week quota is unverified; DS-XL 2-candidate + fresh Shorts uses 72 % with no retry headroom.
2. Disk is the hard blocker before GPU is.
3. Lightning at 5 s/image is 5× cheaper but is a `DRAFT` fallback in `image_engine.json`
   (not owner-approved for publishable frames).
4. 30 % regeneration is an assumption, not a measurement; S15 produced 42/42 without a failure.

---

## 4. YouTube upload plumbing — plan only (everything UNVERIFIED)

No credential was created, read or tested. No implementation was written.

### 4.1 OAuth in a Codespace

1. Google Cloud project → enable **YouTube Data API v3**; configure OAuth consent screen
   (External, Testing, scopes `youtube.upload` + `youtube.readonly`).
2. Preferred for headless: OAuth client type **"TVs and Limited Input devices"** → device-code flow
   (`urn:ietf:params:oauth:grant-type:device_code`); user approves on a phone, no localhost.
   Fallback: **Desktop app** client + loopback redirect on `localhost:8080` (Codespaces forwards it).
3. Uploads from an unverified project are locked to `private` until Google's **API compliance audit**
   passes. Plan for "uploaded-private → owner review → public".
4. Missing libraries: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
   (`google-auth` present, the other two **not installed**). Installing requires owner approval.

### 4.2 Token storage in Codespaces

| Item | Rule |
|---|---|
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | Codespaces **secrets**, never repo, never logs |
| Runtime token cache | `/tmp/…/token.json`, mode `600`, deleted at job end |
| Log hygiene | print only `token_present: true/false`, never the value or its length |
| Rotation | refresh token revoked from the Google account page; re-run device flow |
| Scope check | assert the granted scopes at start; refuse to upload on a broader scope |

### 4.3 Output package (per video)

| File | Content | Exists today? |
|---|---|---|
| `video.mp4` | 1080p, h264 + AAC, `+faststart`, −14 LUFS/−1.5 dBTP after QC PASS | YES (P0 shape) |
| `subtitles.srt` | 150 cues from measured durations | YES (`subtitle_gen`) |
| `thumbnail.png` | 1280×720, ≤3 words, safe margins, no title duplication | **MISSING** |
| `metadata.json` | title, description, tags, category, `ai_disclosure` | YES (`package_builder`) |
| `chapters.txt` | `0:00 Title` lines with measured offsets | **PARTIAL** — builder emits numbers without timecodes |
| `description.txt` | hook + chapters + credits + AI disclosure + sources | YES |
| `tags` | ≤15, keyword-researched, not title words | **PARTIAL** |
| `ai_disclosure` | YouTube "altered or synthetic content" flag | **MISSING** in upload payload (docs checklist only) |
| `publish_log.json` | state machine + hashes | YES (local export only) |

### 4.4 API audit checklist (all UNVERIFIED)

- [ ] Quota cost per video: `videos.insert` 1600 + `thumbnails.set` 50 + `captions.insert` 400 +
      `playlistItems.insert` 50 + `videos.update` 50 ≈ **2 150 units** → ≤4 uploads/day at 10 000/day.
- [ ] Quota cost of `search.list` = 100 units → never used in the upload path.
- [ ] Resumable upload (`MediaFileUpload(..., resumable=True)`), chunk retry, sha256 compare.
- [ ] Upload state machine: `draft → approved → uploaded_private → reviewed → public | failed`.
- [ ] `containsSyntheticMedia` (AI disclosure) field name and placement confirmed against official docs.
- [ ] Category = 27 (Education); default language + localized title/description.
- [ ] No schedule, delete, comment, or channel mutation in v1.
- [ ] Audit trail: request id, video id, quota units, timestamp, manifest sha256.
- [ ] Failure modes: `quotaExceeded`, `uploadLimitExceeded`, `invalidCategoryId`, token expiry.
- [ ] Owner approval recorded before every state transition to `public`.

---

## 5. Image QC gate spec

Two layers: **(A) objective auto-flags** (agent) and **(B) owner blind review** (human).
No agent may pronounce an image "good".

### 5.1 Layer A — per-image gate

| # | Check | Threshold (source) | Verdict on failure |
|---|---|---|---|
| 1 | Black / non-finite | mean luma < 1 and std < 1, or any NaN/Inf pixel | **REJECT** |
| 2 | Resolution / aspect | exact target bucket; aspect tolerance 1 % (`config/qc_thresholds.json`) | **REJECT** |
| 3 | Blur | Laplacian variance < 100 **and** < 0.35 × sheet median (`S15_CHECKS`) | **REJECT** |
| 4 | Duplicate | dHash Hamming ≤ 4 (any pair) or ≤ 6 (same scene) | **REJECT** the later candidate |
| 5 | Corner marks | `corner_fraction 0.14`, `periodic_peak ≥ 0.4`, `fine_energy 0.6–14`, `text_like ≥ 0.6` | **REVIEW** (never auto-reject) |
| 6 | Caption-zone clutter | bottom 20 % band (legacy 28 %): `dark_fraction ≥ 0.35`, `busy_fraction ≤ 0.35`, contrast flag | **REVIEW** → **REJECT** if text would be unreadable |
| 7 | Palette drift | colour distance ≤ 70, coverage ≥ 4 %, off-palette ≤ 92 % | **REVIEW** |

Bucket policy: generate at the **exact QC target** (e.g. 1344×768) and check that bucket;
the 1920×1080 frame is checked after render (scale + crop), not the PNG.
Today `size_exact=true` + 1 % aspect makes every 1344×768 still fail a 1920×1080 target
(**VERIFIED**: 3/3 fail).

### 5.2 Layer B — blind sheets

- **12 tiles per sheet**, randomised order, no style/seed/model in file names;
  `mapping.json` sealed until the owner finishes the CSV.
- 150 images → **13 sheets** (12 × 12 + 6).
- Each sheet has a plain variant and a `_captioned` variant with a sample subtitle line in the
  bottom band (caption-zone test at real size).
- Current tool builds **6 tiles/sheet** (`scripts/s15_blind_pack.py`: `SQUARE_PER_SHEET = 6`) →
  a 12-tile mode is a code change (gap G5).
- Owner scores anatomy, composition, style fit, caption space, phone readability.

### 5.3 Reject list

`reject_list.json` per episode: `{image_id, sentence_id, reason_code, metric_value, threshold,
attempt, seed, retry_of}`. Reason codes: `BLACK_NAN`, `RESOLUTION`, `BLUR`, `DUPLICATE`,
`CORNER_MARK`, `CAPTION_CLUTTER`, `PALETTE_DRIFT`, `OWNER_REJECT`.
A rejected image never silently disappears: the sentence it covered is either regenerated or the
render is **BLOCKED** for that sentence (no placeholder art).

### 5.4 Retry policy (fail-closed)

| Attempt | Action | Rule |
|---|---|---|
| 1 | new seed (seed policy 3000–3999, one seed per subject) | log the change |
| 2 | prompt variant + new seed | log the change |
| 3 | prompt variant + style-lock emphasis + new seed | log the change |
| stop | sentence marked **BLOCKED**, owner notified | max 3 attempts; no silent pass |

Regeneration budget is 30 % of the sentence count per episode (≈59 images for 150 sentences);
exceeding it is reported, not hidden. Corrections never change `config/qc_thresholds.json`
without an explicit owner decision.

---

## 6. Gap list (owner-facing, ordered by blocking severity)

| ID | Gap | Blocks | Fix size |
|---|---|---|---|
| G1 | 18-min narration never produced (max 428.6 s) | stage 4 for long-form | Kaggle CPU run + verification |
| G2 | Disk 3.4 GB free vs 5.6–9.8 GB/week | 7-video week | rotation policy / cleanup (owner) |
| G3 | No thumbnail generator | upload package | new tool (1280×720) |
| G4 | Chapters lack timecodes | YouTube chapters | small change in `package_builder` |
| G5 | Blind sheets are 6 tiles, spec needs 12 | owner review at 150 images | small change in `s15_blind_pack.py` |
| G6 | QC target vs generation bucket mismatch | image gate | config decision (owner) |
| G7 | EDL has no per-sentence image mapping | render at scale | F2 scope |
| G8 | No uploader / OAuth / AI-disclosure flag | publishing | §4 plan, new code |
| G9 | Kaggle 30 h/week quota unverified | weekly budget | owner confirms in Kaggle settings |
| G10 | `finish_audio` output −16.2 LUFS vs QC band −16.0 | QC PASS | re-check on a longer clip |

---

## 7. Evidence (commands run in F1, read-only)

### 7.1 Tool registry

```
$ python -c "registry.discover(); print(len(registry.list_all()), len(registry.get_available()))"
141 41
```

### 7.2 QC on a real 1080p render

```
QCTool().execute({input_path: docs/openmontage/smoke/p0_smoke.mp4,
                  subtitle_path: docs/openmontage/smoke/p0_smoke.srt,
                  output_path: /tmp/f1_verify/qa_p0.json})
→ success True, verdict FAILED, 15 checks
ffprobe_streams PASS | full_decode PASS | blackdetect PASS | freezedetect PASS
silencedetect PASS | ebur128 FAILED (I=-21.3 LUFS, target -14±2) | subtitle_sync PASS
duration_vs_script NOT_RUN | credits_complete NOT_RUN | claim_ids NOT_RUN
claim_ids_resolve NOT_RUN | rights_basis NOT_RUN | added_value NOT_RUN
ai_illustration_label NOT_RUN | motion_variety NOT_RUN
thresholds source: /workspaces/OpenMontage/config/qc_thresholds.json (error None)
```

### 7.3 Audio finishing

```
FinishAudioTool → success True, 0.87 s
input I=-21.24 LUFS, LRA 0.8, TP=-2.18 dBTP
output measured with ebur128: I=-16.2 LUFS
```

### 7.4 P0 render ratio

```
14.21 s wall / 12.432 s video = 1.143 s per video second
1920x1080, h264 30 fps, AAC 48 kHz stereo, 1 384 868 B, 891 kb/s
```

### 7.5 One 5 s segment (process-start cost)

```
ffmpeg -loop 1 -framerate 30 -i filter_drifter_r0001.png -vf scale=3840:2160…zoompan…d=150
  -frames:v 150 -c:v libx264 -preset veryfast -crf 20 → 7.69 s
```

### 7.6 Illustration QC on existing stills

```
qc_batch(3 × projects/se_pilot/assets/illustrations/*.png, 1920, 1080)
→ total 3, passed 0, failed 3
filter_drifter_r0001: blur 314.29, size [1344,768], text_like False
frozen_ocean_food_web_r0025: blur 134.71, size [1344,768], text_like True
ice_burrower_r0033: blur 49.54, size [1344,768], text_like False
```

### 7.7 Packaging + export

```
build_package(projects/se_pilot, /tmp/f1_verify/package, ai_illustration=True)
→ ok True, DRAFT_NOT_PUBLISHABLE, chapters 9, sentences 46, shorts_beats 7
metadata.json keys: title, description, tags, credits, category, ai_disclosure, created_utc
   description has "## Chapters" but no "0:00" timestamps → chapters_in_desc False
ExportBundle → success True, files: output.mp4, subtitles.srt, metadata.json,
   description.txt, chapters.txt, publish_log status "exported"
```

### 7.8 Tests / compile

```
python -m py_compile tools/qa/qc.py tools/audio/finish_audio.py \
  tools/illustration/illustration_qc.py tools/publishers/export_bundle.py \
  tools/packaging/package_builder.py tools/kaggle_bridge/kaggle_bridge.py \
  scripts/run_episode.py            → exit 0
pytest tests/test_edl_generic.py tests/test_run_chapters.py -q → 10 passed in 0.12 s
```

### 7.9 Kaggle

```
$ kaggle kernels list --mine --page-size 3
→ exit 0; forts845/of-bridge-runner (2026-10-23 05:27), openmontage-runner (03:40),
  openmontage-s5-runner (2026-10-21 12:40)
```

### 7.10 Sources for the measured image/render constants

- `docs/openmontage/image_gen/S15_STATS.json` — 42/42, 26.003 s/img, load 84.901 s, 0 black/NaN/OOM.
- `docs/openmontage/image_gen/S12_STATS.json` — DS-XL 26.259 s/img load 87.697 s;
  Lightning 5.121 s/img load 41.487 s; klein 25.995 s/img load 121.371 s.
- `docs/openmontage/smoke/p0_smoke_report.json` — 1.143 s per video second, 1080p30.

---

## 8. What F1 did not do

- No commit, no install, no delete, no Kaggle job, no network download.
- No YouTube/OAuth call; no credential created or read.
- No full test suite (the 2 491-test figure is **RECORDED** from `F1FIX_STATE.md`, not re-run).
- No image generation, no narration run, no 12-tile sheet built.
- Budget numbers in §3 are arithmetic over the measured constants in §3.1; only the render,
  audio-finish and QC ratios are measured end-to-end in this environment.
