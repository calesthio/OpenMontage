# Tooling Decisions — Milestone S (2026-10-16)

Scope: audit which tools the last pilot actually used (from CODE/artifacts, not
memory) + minimal skill install. No paid routes, no model downloads, no
process/lock changes. Kilo CLI installed version: **7.8.12**. Project skill
path per official Kilo docs (`kilo.ai/docs/customize/skills`, "Project Skills
(Workspace-Level)"): **`.kilo/skills/<name>/SKILL.md`** (folder name = skill name).

## 1. What the last pilot actually used (evidence)

Run: `projects/pallets-hidden-business/` (run-2026-10-15-pallets).
Sources: `artifacts/{narration_manifest,render_report,asset_manifest}.json`.

| Stage | Tool (exact) | Version / path | $0 check |
|-------|--------------|----------------|----------|
| narration (TTS) | `piper_tts`, engine **piper**, voice/model `en_US-lessac-medium` | piper-tts **1.8.0** (`pip show`); weights `~/.local/share/piper/voices/en_US-lessac-medium.onnx` (+`.json`); 18 segments, 84.975 s measured, 22050 Hz | local synthesis, `estimate_cost()==0.0`, no network |
| subtitles | `subtitle_gen` segment-level fallback from ffprobe-measured boundaries (word timestamps unavailable — recorded as skipped, not passed) | `assets/subtitles/captions.srt`, 16 cues, burned | local |
| compose (render) | `render_runtime: ffmpeg` (decision d-002; hyperframes recorded available-not-selected; remotion unavailable — empty `node_modules`) | **ffmpeg 6.1.1-3ubuntu5** (`ffmpeg -version`); MP4 h264 1920×1080 30fps + aac 22050 Hz mono, 84.975 s | local |
| footage | `direct_clip_search`, 4 search generations; providers: Wikimedia Commons (5), Wikimedia Commons (Open Beelden) (1); licenses CC BY 4.0 / CC BY-SA 4.0 / CC BY-SA 3.0 nl / CC0 1.0 / CC BY 2.0 / CC BY 3.0 | 6 assets (`AST-SCN-*`) | keyless, $0 |
| music | silence (decision d-003; `pixabay_music` gate-blocked, library empty) | `path: null` | $0 |
| diagram | `DiagramGen` Pillow PNG (P0.4 artifact, 8.5 KB) | local | $0 |

## 2. License check (repo's own LICENSE/README files only)

- Repo itself: **GNU AGPL-3.0** (root `LICENSE`).
- Piper voice `en_US-lessac-medium`: pilot manifest asserts
  `"voice_license": "CC-BY-4.0 (lessac dataset voice)"` — but **no license text
  exists in the repo, README, `tools/audio/piper_tts.py`, or the voice sidecar
  `.onnx.json`** (config keys only). → **UNKNOWN** (manifest assertion only;
  verify against a license text before any commercial use).
- `piper-tts` engine 1.8.0 → **UNKNOWN** from repo files (nothing stated).
- `ffmpeg` 6.1.1 (Ubuntu build) → **UNKNOWN** from repo files (nothing stated).
- Voice model weights (`.onnx`) → **UNKNOWN** (no license in sidecar).
- Installed skills below: **MIT** both repos (LICENSE file headers read).

## 3. Explicitly NOT installed

81-skill OpenMontage pack, `everything-kilo-code`, any ElevenLabs/HeyGen skill,
any YouTube-video downloader. Only the 7 skills in §4 were copied. Upstream
`hooks/`, `index.js`, root scripts of superpowers were NOT installed.

## 4. Installed skills (project level, `.kilo/skills/`)

| Skill (folder = name) | Source URL | Pinned commit | License | Pre-install audit (every SKILL.md + script read) |
|---|---|---|---|---|
| test-driven-development | https://github.com/obra/superpowers | `bb92a77` (v7.0.0, 2026-10-09; matches `ls-remote` HEAD) | MIT | SKILL.md + writing-good-tests.md: guidance only. No network, writes, env, secrets. |
| systematic-debugging | same | same | MIT | SKILL.md + 6 companion .md + .ts example: guidance only. `find-polluter.sh` runs local `npm test` per file (no network/secrets/env; `bash -n` clean). Prose mentions of "token/secrets" are fictional dialogue/diagnostic examples, not code. |
| verification-before-completion | same | same | MIT | SKILL.md only: guidance only. No code at all. |
| yt-script | https://github.com/Jakeschincariol/youtube-agent-skill | `a2feb21` (2026-09-16; matches `ls-remote` HEAD) | MIT | SKILL.md + `hookscore.py` (pure local heuristic scorer, reads `hooks.json`, prints stdout) + `hooks.json` (data). No network/writes/env/secrets. Verified: `py_compile` exit 0; `--hook` run scored locally (output observed). |
| yt-package | same | same | MIT | SKILL.md + `title.py` (local string lint, stdout only). No network/writes/env/secrets. `py_compile` exit 0 (observed). |
| yt-chapters | same | same | MIT | SKILL.md + `chapters.py` (local transcript parser). **Dependency found:** imports `load, parse_ts` from sibling `../yt-edit` (not installed). Fix: vendored `yt-edit/deadair.py` **verbatim** as `yt-chapters/deadair.py` + 4-line try/except import fallback (exact diff in §5). `deadair.py` audited: reads transcript file, prints EDL; no network/writes/env/secrets. Verified end-to-end on a /tmp SRT: 3 valid chapters, exit 0 (observed). |
| yt-seo | same | same | MIT | SKILL.md only, no tools. Guidance only. |

## 5. Local modifications to vendored files (exact)

1. `.kilo/skills/yt-chapters/chapters.py` — import fallback for standalone install:
```diff
-sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yt-edit"))
-from deadair import load, parse_ts  # noqa: E402  (same parser, one implementation)
+try:
+    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yt-edit"))
+    from deadair import load, parse_ts  # noqa: E402  (same parser, one implementation)
+except ImportError:  # OpenMontage local adaptation: standalone install, use vendored copy
+    from deadair import load, parse_ts  # noqa: E402  (vendored from yt-edit/deadair.py, verbatim)
```
2. `.kilo/skills/yt-chapters/deadair.py` — NEW, byte-identical copy of upstream
   `skills/yt-edit/deadair.py` at `a2feb21` (yt-edit skill itself NOT installed).
3. `.kilo/skills/yt-script/ADAPTATION.openmontage.md` — NEW, binding local rules:
   every factual sentence needs a resolving ledger `claim_id`; hook scores are
   heuristics, never forecasts; narration voice comes from `narration_manifest`,
   not `~/.claude/youtube/voice.md`.

## 6. Unknowns

- Voice/engine/ffmpeg/weights licenses (see §2) — must resolve before commercial use.
- Whether Kilo auto-discovers `.kilo/skills/` in THIS repo layout was not
  end-to-end verified (no Kilo session run in this milestone; path taken from
  Kilo's official skills doc, not assumed).
- `yt-script` voice-profile path (`~/.claude/youtube/voice.md`) does not exist
  here — covered by the adaptation (§5.3), not a blocker.

## 7. Rollback

Delete `.kilo/skills/<name>/` (single `rm -rf`; skills are leaf copies, nothing
else references them). Upstream repos untouched (cloned to /tmp, since removed).
`git revert <commit>` restores pre-install state exactly.

## 8. Remaining pipeline stages — tooling audit (not used by the P1 pilot)

Stages the P1 pilot did not touch. One row per remaining stage: existing tool in
repo (exact path) or MISSING, license, $0 check, unknown. Rule: license and $0
check are "n/a — no tool" rather than assumed free when nothing exists; unknowns
are recorded, not guessed.

| # | Stage (pipeline stage) | Existing tool in repo (path) or MISSING | License | $0 check | Unknown |
|---|---|---|---|---|---|
| 1 | Primary-document research (research / stage 2) | MISSING — no research, NTRS, or web-search tool in `tools/`; NTRS usage exists only in a throwaway probe script (`/tmp`, deleted after use) and in `docs/openmontage/audit/VIABILITY_PROBE_2026-10-16.md` | n/a — no tool | n/a — no tool to price; NTRS is a keyless GET but no $0 check can be run on absent tooling | NTRS document fields (id, title, center, date, PDF URL) and rate limits not yet recorded; probe attempted, both direct requests timed out → ERROR, not zero results (§11) |
| 2 | Claim ledger (evidence / stage 3) | MISSING tool; schema exists: `schemas/artifacts/evidence_ledger.schema.json`; cross-artifact ID resolution in `lib/artifact_ids.py` (lib functions, not a registry tool) | n/a for tool; schema files are repo AGPL-3.0 | Local schema validation is $0; no synthesis/download | Stable `evidence_id` derivation (`EV-<slug>` from source + claim) not implemented as a tool; ledger assembly is manual |
| 3 | Storyboard ID validation (storyboard / stage 6) | MISSING tool; schema `schemas/artifacts/scene_plan.schema.json` exists; `scene_id` resolution via `lib/artifact_ids.py` | n/a for tool; schema AGPL-3.0 | n/a — local validation would be $0 | scene_id / dangling-reference validation is a lib function, not a registry tool; no "validate storyboard IDs" entry point |
| 4 | Packaging — title/description/chapters/thumbnail (publish / stage 12) | `tools/publishers/export_bundle.py` (ExportBundle; `publish` capability, local, BETA) | repo AGPL-3.0 | $0 — local filesystem only; `free: True`, `network_required: False`, `supports.uploads: False` | Thumbnail handled as concept JSON unless a real image path is supplied; no thumbnail generation tool |
| 5 | Upload (not a pipeline stage; publish never uploads) | MISSING — `export_bundle` explicitly does not upload (`supports.uploads: False`); no YouTube/uploader tool in `tools/publishers/` | n/a | n/a | none — decision recorded in §9 |
| 6 | Analytics review (not a pipeline stage) | MISSING — no analytics tool anywhere in `tools/` | n/a | n/a | Analytics source undefined; YouTube Studio API would need a key/OAuth, barred by §9 |

Row 4 is the only remaining stage with an existing repo tool. Rows 1–3 and 5–6
have no tool, so nothing was priced, licensed, or assumed.

## 9. Upload decision — YouTube

- Publish path: **manual publish in YouTube Studio by a human**. The pipeline produces
  a reviewable export bundle (`tools/publishers/export_bundle.py`, status
  `"exported"`) plus a schema-valid `publish_package` with an explicit
  `manual_approval.status`. `publish_package.manual_approval.upload_target` stays
  `null` until a human sets it; the artifact never triggers an upload.
  `publish-director`: "The pipeline never uploads." Manifest review focus:
  "No YouTube upload was attempted."
- API upload: **only as a private draft, and only later** — unverified API
  projects are forced private by YouTube. Not part of this milestone.
- **No OAuth setup, no credentials requests, no network upload tool** added or
  planned in this milestone.

## 10. Reference-only: OpenVids (bazodev/open-vids, Apache-2.0)

Reached via GitHub raw/tree only (read-only). **No code copied, no app installed,
no OpenVids service calls.** License read verbatim from `LICENSE`: Apache-2.0,
"Copyright 2026 The OpenVids Authors / HeyGen, Inc. (HyperFrames, the original
work OpenVids is derived from)".

**Trusted-source list** — `packages/studio-server/src/research/sources/builtins.ts`
(`BUILT_IN_SOURCES`, `TrustedSource` type from `@hyperframes/agent-protocol`).
Fields per source record: `id`, `name`, `builtIn`, `enabled`, `connector`,
`domains[]`, `kinds[]` (video / picture / audio), `description`, `licenseNote`,
`homepage`, `apiKey` (null | `{ signupUrl, configured }`). Domain validation in
`domains.ts` (`normalizeDomain`): rejects IP addresses, localhost, and shared
suffixes (e.g. github.io, gitlab.io, pages.dev, vercel.app, netlify.app,
herokuapp.com, wordpress.com); a trusted source must name one organization's
site.

**License-record fields** — `packages/studio/src/research/licenseLabels.ts`:
`LicenseStatus` {clear, attribution, restricted, unknown},
`LicenseConfidence` {high, medium, low, none}, `ProvenanceMediaKind`
{video, picture, audio, font, animation, file}, `AssetProvenance.retrievedBy`
{ agent, model, turnId }.

**Fields worth copying into our `asset_record`** (asset_manifest asset entries /
provenance), field names and semantics only — no code:
- source `id` + `name` + `connector` (which adapter surfaced the asset),
- original URL plus a validated host (same rules as `normalizeDomain`),
- media kind (`video` / `picture` / `audio` / …),
- license status + confidence + human-readable `licenseNote`,
- `homepage` / key sign-up URL for key-gated sources,
- `retrievedBy` provenance (who fetched it: agent / user, model, turn id),
- URL validation rules for trusted sources (no IPs, no localhost, no shared suffixes).

## 11. Milestone B probe item — NTRS client (not implemented)

- Repo check: no NTRS (NASA Technical Reports Server) client in `tools/` — grep
  for ntrs/NTRS hits only docs (`docs/openmontage/NICHE_PROFILE_SPEC.md`,
  `docs/openmontage/audit/VIABILITY_PROBE_2026-10-16.md`). Client **not written**
  (out of scope for this milestone).
- Probe item (Milestone B): test the public NTRS API without a key —
  `GET https://ntrs.nasa.gov/api/citations/search` — record HTTP status codes,
  rate limits (including 429), and the document fields available per record:
  id, title, center, date, PDF URL
  (`https://ntrs.nasa.gov/api/citations/<id>/downloads/<id>.pdf`).
- Execution status this session: direct reachability attempted twice; both
  requests timed out at the network layer (no HTTP response received). Per the
  probe rule, **any failure is ERROR, not zero results** — recorded as ERROR
  (network unreachable), not EMPTY. No status codes, rate limits, or field
  inventory obtained yet; probe remains pending.
- See also §8 row 1 (primary-document research).

## 12. Milestone D1 — audio + editing toolchain audit & decision (2026-10-16)

**Time-box:** 40 min. **Rules:** docs + skills into `.kilo/skills/` + throwaway scripts in
`/tmp` only. No paid routes, no keys, no process/lock changes. Max 2 attempts per blocker,
then record BLOCKED.

### 12.1 Preflight (look only)

- `git status --short` clean; HEAD `b5adfc1` on `factory/business-documentary-pilot`; no
  user processes touched; nothing deleted or reset.
- ffmpeg 6.1.1-3ubuntu5 (`/usr/bin/ffmpeg`). All required filters **present and observed**:
  sidechaincompress, loudnorm, acrossfade, xfade, amix, alimiter, ebur128.
- Python libs observed via `pip list`: numpy 2.5.4, onnxruntime 1.31.0, piper-tts 1.8.0.
  **No** stable-ts / whisper / torch initially installed.

### 12.2 Voice-license table (from each repo's own LICENSE/model-card files, not blogs)

| Engine | Code license | Weights/voice license | Commercial use | Evidence |
|---|---|---|---|---|
| Piper engine | GPL-3.0-or-later | n/a (engine) | permitted (copyleft) | `piper_tts-1.8.0.dist-info/METADATA` (local) |
| Piper voice `en_US-lessac-medium` | n/a | **UNKNOWN** — sidecar has `"dataset": "lessac"`, no license field | UNKNOWN | `~/.local/share/piper/voices/en_US-lessac-medium.onnx.json` (local, read) |
| Piper voice `en_US-lessac-medium` | n/a | **UNKNOWN** — MODEL_CARD has no license field; points to Lessac Blizzard 2013 dataset license (separate URL); manifest asserts CC-BY-4.0 but no license text in repo | UNKNOWN — **blocked for publication** | HF `rhasspy/piper-voices` lessac/medium/MODEL_CARD; local sidecar `.onnx.json` (`"dataset": "lessac"`, no license field) |
| Kokoro-82M (hexgrad) | Apache-2.0 | Apache-2.0 (weights); training data includes CC BY items + synthetic data of UNKNOWN origin → documented caveats | permitted (weights), subject to training-data caveats — **owner sign-off required** | HF `hexgrad/Kokoro-82M` (License: apache-2.0); `hexgrad/kokoro`/`hexgrad/misaki` LICENSE files |
| Chatterbox | **UNKNOWN** — not installed locally | **UNKNOWN** | UNKNOWN | none local |

Kokoro-82M is installed locally (kokoro 0.2.2, torch 2.14.1 CPU, misaki G2P) and was smoke-tested successfully in Milestone V (see `docs/openmontage/VOICE_DECISION.md`). Kokoro is the selected narration voice pending owner sign-off on the training-data caveats; Piper lessac is blocked until its voice license is resolved. Chatterbox remains uninvestigated.

### 12.3 Voice synthesis smoke test (piper — ALLOWED candidate, installed & free)

Same script synthesized on CPU; saved to `/tmp/opencode/d1_60s_piper.wav` (and a duplicate
`_b.wav` for timing). Measured: audio **26.98 s** (text renders shorter than 60 s at this
voice's pace — real duration reported, not claimed), wall **5.74 s** → real-time factor
**0.21** (≈4.7× faster than real-time on CPU). `needs human listening`; technical smoke test
only — voice license UNCONFIRMED, so not a commercial-use approval.

### 12.4 Forced alignment — stable-ts (installed, attempt 2)

`pip install stable-ts` attempt 1 timed out (300 s); attempt 2 succeeded → stable-ts 2.19.1 +
torch + openai-whisper installed into system site-packages (no repo change, no lock change).
Imported as `stable_whisper` (not `stable_ts`).

Test: tiny Whisper model downloaded from HF (72.1 MB — network works), transcribed
`d1_60s_piper.wav` with `word_timestamps=True` → **82 word-timestamps for 80 reference words**
(~100% coverage) in ~7.3 s (RTF ≈ 0.27).

Known-text forced alignment: **no `result.align`/`align_words`/`force_align` method found** on
`WhisperResult` in this stable-ts API (one method-name set tried) — not directly exercised.
Piper segment fallback: **0% word timestamps** (piper emits none). Conclusion: stable-ts gives
word-level timestamps where piper/segment fallback gives none; a clear improvement, but the
install pulled torch and was not integrated into the repo.

### 12.5 Audio finishing prototype (/tmp, no downloaded music)

Voice + synthetic 440 Hz test-tone bed → sidechaincompress (music ducked under voice) → amix →
two-pass loudnorm (`I=-14`, `TP=-1.5`, `LRA=11`; pass-1 measured input_i=-13.12 LUFS,
input_tp=-4.55 dBTP, input_lra=1.20, target_offset=-0.16; pass-2 `linear=true` with measured
values) → `/tmp/opencode/d1_finished.wav`.

**Verification via ebur128:** integrated loudness **-13.8 LUFS** (target -14), true peak **-5.2
dBFS** (target -1.5; good headroom), LRA 1.2 LU. Prototype validated; no downloaded music.

### 12.6 Editing doctrine + pinned skills

Upstream `agamm/video-agent` read read-only (MIT, pinned commit
`cc00d2815869cbf2d708426a5082612f0c3b4dbf`; LICENSE read verbatim). The fork
`rugelees/video-agent` is only a copy and was not consulted. **Not installed.** Did not use
yt-dl, vfx-edit, or Remotion parts.

SKILL.md files read (upstream): `editor`, `edl-edit`, `cutting-rhythm`, `audio-edit`,
`video-transitions`, `captions`. Network/env/write profile: none of the ported skills makes
network calls or requires env vars (optional upstream Grok VFX needs `XAI_API_KEY` — out of
scope). Installed into `.kilo/skills/` (Linux-adapted, no mlx-whisper, no `h264_videotoolbox`,
no `uv run video-agent` CLI): `cutting-rhythm`, `edl-edit`, `audio-edit` — each pinned to the
upstream commit.

Doctrine written: `docs/openmontage/EDITING_DOCTRINE.md` — rules to port (EDL with per-cut
rationale; split edits/J–L cuts; pacing lint: shot-length variation ≥ ~15% INITIAL GUESS,
pause gaps, cut-in-silence, beat-snap; transitions; captions `--clean`; audio ducking; universal
order of operations), mapped to our real timeline schema
`schemas/artifacts/edit_decisions.schema.json` (`cuts[].reason`, `transition_in/out`,
`audio.music.ducking`, `overlays`, `subtitles`, `render_runtime`, `composition_mode`). All
numeric thresholds marked INITIAL GUESSES to tune after human review.

Music policy written: `docs/openmontage/MUSIC_POLICY.md` — pilot uses NO music unless license
evidence is stored; allowed sources; required record fields (source_url, license_text, author,
download_date, sha256, commercial_use_allowed, modification_allowed, attribution, license_url);
Content ID risk noted as UNKNOWN.

### 12.7 Blockers

None hard. stable-ts forced-alignment-with-known-text via `result.align` was not available in
the API (one method-name set tried; not retried — recorded as not exercised, not BLOCKED,
since word-timestamps via transcribe were obtained).

## 13. Milestone D1 summary — observed vs assumed

**Observed:** ffmpeg filters all present; piper-tts 1.8.0 + en_US-lessac-medium installed
(voice license UNKNOWN); stable-ts 2.19.1 installed and tested (word-timestamps ~100%);
audio finishing prototype verified via ebur128 (-13.8 LUFS / -5.2 dBTP); three skills pinned
into `.kilo/skills/`; EDITING_DOCTRINE.md and MUSIC_POLICY.md written.

**Assumed (not verified):** piper voice commercial use (voice license unstated);
stable-ts known-text forced alignment (method absent in API); long-form loudness targets for
our delivery; human listening of the piper sample (not performed).

## 14. Milestone V summary — voice decision (Kokoro-82M)

**Observed:** kokoro 0.2.2 installed locally (binary wheels; `spacy`/`thinc`/`blis` source
build failed on Python 3.14, resolved with `--only-binary=:all:`); Kokoro-82M weights
`kokoro-v1_0.pth` (~313 MB) downloaded to `/tmp/hf-cache` (within 600 MB cap, gitignored,
not committed); CPU synthesis of a public-domain paragraph with 3 voices (af_heart,
af_bella, am_adam) — RTF 1.58–1.75 (slower than real-time on CPU, expected); espeak-ng
not installed → `EspeakFallback` warning only (non-fatal); QC tool on each sample: raw
kokoro output quiet (I=-21.8 to -25.4 LUFS → ebur128 FAILED vs -14±2); `finish_audio` on
af_heart → I=-15.0 LUFS, TP=-4.4 dBFS PASS; native `aac` encoder mux works (FINISHED MP4:
I=-15.0 LUFS, TP=-4.3 dBFS, ebur128 PASS, full_decode PASS).

**Decision:** Kokoro-82M selected for narration (Apache-2.0 weights, clear at the
weights level). Piper `en_US-lessac-medium` blocked (voice license UNKNOWN — MODEL_CARD
has no license field; manifest's CC-BY-4.0 assertion unverified).

**Training-data caveats (owner sign-off required):** Kokoro trained on public domain +
Apache/MIT audio + synthetic data from closed TTS models; CC BY items (Koniwa `tnc` <1h
CC BY 3.0; SIWIS <11h CC BY 4.0) require attribution; synthetic-data origin UNKNOWN.
Voice license gate = NOT PASSED for Piper lessac; Kokoro = provisionally known
(Apache-2.0 weights + documented caveats), owner sign-off required before publication.

**Assumed (not verified):** human listening of kokoro samples (not performed);
long-form loudness targets; attribution discharge for CC BY training items.

