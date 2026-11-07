# FACTORY 100% SPEC — what "finished" means for the OpenMontage faceless-video factory

Audience: the coding agents (Kilo, OpenCode) and the owner. Language: English for agents; owner summary in Russian right below.
Status of this file: TARGET DESIGN. Everything under "Current state" is taken from agent reports and has NOT been independently verified. Agents must re-verify from the repository before relying on it.

## 0. Кратко по-русски (для владельца)
Фабрика на 100% = одна команда превращает проверенную тему в готовое к ручной публикации видео: исследование с источниками, сценарий где каждое утверждение привязано к источнику, озвучка, картинки/кадры с подтверждёнными правами, монтаж, автоматическая проверка качества, упаковка (название, описание, обложка, кредиты), пакет для вашего просмотра, и разбор метрик YouTube после выхода. Публикацию делаете вы вручную. Человеческие решения (голос, права, слепая оценка картинок, публикация) остаются за вами, агенты их не принимают.

## 1. Mission and hard rules (never relax)
1. Faceless English long-form YouTube documentaries/explainers. Target length ladder: 3-4 min -> 8-10 -> 15-20 -> 40-50, a step up only after the owner reports YouTube Studio metrics (no invented thresholds).
2. Budget $0: free/open tools only, no paid APIs or footage, no paid fallbacks. Unknown price = forbidden until verified.
3. Zero secrets in v1 code and docs. Tokens only as Codespaces secrets; never printed, logged, committed or sent to chat. Exception: KAGGLE_API_TOKEN (name only is ever shown).
4. Rights are fail-closed: every visual asset has a record (rights_basis, source URL, credit, sha256). unknown = not usable. Third-party credit, NC/ND licenses, emblem-as-main-picture = REJECT even if the owner reviews it.
5. Every factual sentence in a script carries a claim_id that resolves in the claim ledger. Load-bearing claims need TWO independent sources; otherwise flagged SINGLE_SOURCE and blocked from publication until resolved.
6. AI-generated images: always labelled, never presented as real footage or real events, never real people/brands/logos/emblems, no text rendered inside images (labels/maps/numbers are drawn in the editor).
7. Publishing is manual in YouTube Studio only. No OAuth to YouTube, no auto-upload, no comment posting. Synthetic voice/content disclosure follows the current OFFICIAL YouTube help pages (agents cite URL + access date, paraphrase).
8. Agents report only what they observed. Never claim a test, commit, push, download, Kaggle run or subagent run that did not happen. Roles executed by one agent are labelled "inline, not independent". Quality of images/audio is judged by the OWNER, not by agents.
9. Fail-closed QC: a check that cannot run is BLOCKED or NOT_RUN, never PASS.
10. Resumable and bounded: state files, checkpoint after every phase, max retry counts, stop if free disk < 800 MB.

## 2. Roles and ownership (no two agents write the same file)
- Owner: decisions (niche, voice acceptance, rights flags, blind image scoring, emblem policy, parent/AdSense, publishing), reviews contact sheets and final video.
- Kilo (factory lane): docs/ tools/ scripts/ tests/ .kilo/ (except OpenCode-owned paths). Builds pipeline, bridge, QC, audio, render, packaging.
- OpenCode (research lane): youtube-niche-finder/ (never committed to this repo; reports copied by the owner into docs/openmontage/audit/demand/), plus tools/prompting/, scripts/score_rubric.py, niches/*/creatures/, evidence/spec_evo/ and OPENCODE_REQUESTS.md. Requests for changes elsewhere go to docs/openmontage/OPENCODE_REQUESTS.md.
- Independent reviewer: a fresh read-only session fed only docs/openmontage/REVIEW_PACK.md files (no chat history). Required before any publication.
- Git: commit own paths only (never `git add -A`), `git pull --rebase`, push non-force, never commit media/secrets. Large media lives in gitignored projects/; small artifacts (manifests, edit_decisions, subtitles, credits, qa_report) are committed under docs/openmontage/<episode>/artifacts/.

## 3. Target architecture (ten layers; each has acceptance criteria)

### L1 Niche and topic intelligence
- Niche profiles as config (YAML): allowed sources, visual-mix limits, claim rules, >=3 episode templates, excluded content.
- Demand measurement with YouTube Data API using uploads playlists (cheap) and a hard cap on search.list calls (~50/day); outlier = views / median of the channel's last 20 long uploads (excluding the video and uploads younger than 7 days); replication = >=3 distinct channels <50k subs with multiple >=5. n<5 = NOISE; never recommend without measured numbers. Quota exhausted = NOT_MEASURED, not zero.
- Topic viability gate (stage 0): enough legal visuals for the planned length AND >=3 primary sources (or, for speculative niches, >=2 sources per real-science claim) BEFORE scripting.
- Done when: `scripts/measure_niche.py` (or OpenCode equivalent) + reports reproducible from cached data; viability gate is a tested function.

### L2 Evidence and scripting
- Claim ledger per episode (markdown or YAML): claim_id, paraphrase, source URL + section, status TWO_SOURCES | SINGLE_SOURCE | OCR_UNVERIFIED | SPECULATION, KNOWN/INFERENCE/SPECULATION tag for speculative niches, contradictions field. No facts from memory; only retrieved pages.
- Script: one sentence per line with claim_ids, hook, chapters, 3 truthful titles (no clickbait lies), chapter list for the description.
- Footage-aware scripting: storyboard consults the asset inventory before narration is final; slots without valid assets are rewritten or BLOCKED.
- QC gate: claim_ids resolve against the ledger (not just present); unknown id = FAIL.
- Done when: an episode script passes `claim_ids_resolve`, every SINGLE_SOURCE sentence is listed in a "needs second source" table.

### L3 Visual sources and rights
- Source registry (docs/openmontage/footage/SOURCE_REGISTRY.md + yaml): per source rights page URL, default rights_basis, attribution, keyless search method, adapter present/missing.
- Adapters (keyless): NASA Image & Video Library, Internet Archive (curl -L; use the REAL file list from metadata, never guessed names), Wikimedia Commons, Library of Congress, NARA, DVIDS, Met Open Access, Smithsonian Open Access, Rijksmuseum, National Gallery of Art. Each adapter: transport errors surface (never "0 clips success"), rights check, asset_record with sha256, credit, URL, license text.
- asset_record fields: asset_id, kind (video|still|ai_illustration|graphic), source_url, file_url, creator/credit, license text + URL, rights_basis (explicit_license | source_policy_us_gov | ai_generated_illustration | unknown), flags (identifiable_persons, logo_visible, third_party_credit, nc_nd), resolution, duration, sha256, access date, owner_review {reviewer, date, scope}.
- Resolution rule: video below the niche minimum (default 720p) may be used only as framed inserts (integer 2x scale, centered on dark background with thin frame, source card), never stretched; no AI upscaling of footage.
- Done when: 3 adapters tested with recorded fixtures (no network in tests) and the rights classifier has regression tests for: third-party credit => REJECT, missing rights field => unknown, NC/ND => REJECT.

### L4 AI illustration engine (Kaggle GPU bridge)
- tools/kaggle_bridge: submit, poll with backoff and total timeout, fetch, verify (job_id, sha256, bytes), fail-closed; GPU T4, internet on, one model per kernel run; manifest records exact library versions (pin released diffusers/transformers/huggingface_hub; avoid git main), seeds, prompts, params.
- Rules: fp16 only on T4 (no bf16), no bitsandbytes, no CPU fallback, non-zero exit if images < prompts, full tracebacks saved, a failed attempt must change something before retrying.
- Model selection by the owner's BLIND scoring (see L9), not by agents. Candidates: SDXL Base + style LoRA, FLUX.2 klein 4B, Z-Image Turbo (Apache-2.0 each; verify each license from the official card). Others only after an official-card check (license, gating, size, dtype, released-diffusers pipeline).
- Prompt builder (tools/prompting): per-model prompt rules (SDXL structured + negative; Z-Image prose, style first, no negative prompt; klein prose, subject/anatomy first, no negative). Rules are tested and cite sources, vendor-official vs blog claims labelled.
- Style system per niche: STYLE_BIBLE.md (palette, line style, prompt template, camera vocabulary), written anatomy spec per creature (limb/eye/horn counts, 2-3 dominant features), canonical silhouette reused across shots; consistency via fixed seeds + LoRA/reference images/img2img.
- Image QC (flags only): Laplacian blur, text-like artifacts, pHash duplicates, aspect/size. Anatomy/beauty = owner.
- Done when: one command produces N labelled illustrations for an episode from creature/scene YAML specs, with verified manifest, and the owner has picked the model by blind scoring.

### L5 Voice and audio
- TTS: Kokoro-82M via kokoro-onnx (Apache-2.0 weights; residual risk: provenance of part of the training data; the owner accepted by listening, parent sign-off pending). Piper en_US-lessac voices are REFUSED in code. License gate in the TTS tool: unknown/blocked license = refuse.
- Word timestamps -> subtitles (<=2 lines, drift check). Narration >= 90% of runtime.
- finish_audio: voice-first mix, two-pass loudnorm, limiter; target configured in config (starting I=-14..-16 LUFS narration-only, TP<=-1.5 dBTP; secondary-source guesses, owner confirms); loudness verified on the FINAL MP4 after AAC encode.
- Music: none unless license evidence is stored (source URL, license text, author, date, sha256). Content ID risk is UNKNOWN.
- Done when: narration for a 10-minute script synthesizes unattended, passes QC, and the owner confirms the voice on listening.

### L6 Editing and render
- EDL (edit_decisions.json): every cut has a written rationale; static cards declared static_by_design; segment metadata for pan/zoom type, easing, source card, claim_id.
- Motion variety lint: no two identical moves in a row; shot-length variation; J/L split edits where applicable; still-only sequence <= configured limit.
- Render: ffmpeg is the base assembler (1920x1080 30fps H.264/AAC; draft mode lower res); HyperFrames/HTML-to-video only for original graphic layers after measured stability; Remotion not used. Original graphics: animated diagrams (energy flow, food web, timeline, map), key-number cards with claim_ids, chapter cards, source cards, credit roll.
- Chapter mode for long-form: <=6 min per chapter, per-chapter QC/checkpoint/resume, crossfade concat, final loudness pass, disk check before each chapter.
- Done when: `scripts/run_episode.py <episode_id>` runs all stages with checkpoint/resume/idempotency and logs wall time + disk per stage.

### L7 Quality gates (tools/qa/qc.py -> qa_report.json)
Required checks: ffprobe stream facts; full decode errors; blackdetect; freezedetect (declared static_by_design exempt with REVIEW + reason); silencedetect; ebur128 loudness + true peak; duration vs script; subtitle sync/overlap; claim_ids resolve; rights_basis known for every asset; credits.txt complete; added-value metrics (narration share, original graphics per 90 s, no unannotated archive clip > 20 s, still-only <= 15 s unless motion-lint passes); AI illustration gate (label present, share of runtime within niche limit, never as real footage); speculative-label gate for speculative niches. Statuses: PASS | REVIEW | BLOCKED | FAILED | NOT_RUN. Release verdict treats NOT_RUN/BLOCKED as not passed. Threshold changes only by owner decision, documented with reason; tools never loosen thresholds silently.

### L8 Packaging
- Titles (truthful), thumbnail candidates (1280x720, own graphics/NASA stills/illustrations, no emblems, no people, large readable text), description with chapters, credits/attribution block from rights records, synthetic-content disclosure checklist (official YouTube pages cited), Shorts plan (<=45 s, each sentence with claim_id).
- Done when: package draft is generated from the episode artifacts with zero manual copy-paste of credits.

### L9 Owner review and independent verification
- Review pack (scripts/review_pack.py): contact sheets, blind image sheets (neutral IDs, shuffled, mapping in a separate file), CSV templates, tally script that prints winners only from the OWNER's scores and flags agent-vs-owner disagreement, "INSUFFICIENT" below the minimum sample.
- Independent read-only reviewer session using only REVIEW_PACK.md files. Required before publication.
- Owner checklist per episode: people in frame? logos/emblems? third-party credit? voice OK? S-lines with SINGLE_SOURCE resolved? disclosure answered?

### L10 Operations and learning loop
- State files per milestone, resume instructions, CHANGELOG, LESSONS (observation -> evidence -> cause -> change), EVALS.md fixed tasks (qc fails a bad MP4; finish_audio hits loudness/true peak; TTS refuses Piper lessac; claim_ids fails on unknown id; third-party-credit clip classifies REJECT; rebuild script fails on hash mismatch).
- CI-style fast test script; portability: scripts/rebuild_slice_assets.sh must fail closed and print "verified N/N assets"; manifests (URLs, sha256, rights) committed; media gitignored.
- Disk discipline: delete caches/old renders you created, keep >= 800 MB free; downloads capped per milestone.
- Analytics loop (after publication): owner exports YouTube Studio CSV -> scripts import, per-chapter retention drops, CTR/AVD/first-30s tables, go/no-go summary; no OAuth.
- Codespaces hygiene: stop the codespace when idle; Codespaces usage is limited, one account per person (no extra accounts to bypass limits).

## 4. Directory layout (target)
```
docs/openmontage/
  FACTORY_100_SPEC.md (this file), RIGHTS_MODEL.md, QA_SPEC.md, EDITING_DOCTRINE.md, VOICE_DECISION.md
  niches/<niche>/{profile.yaml, STYLE_BIBLE.md, creatures/*.yaml}
  evidence/<episode>/CLAIM_LEDGER.md
  <episode>/{script.md, artifacts/{edit_decisions.json, subtitles.srt, credits.txt, rights_records.json, qa_report.json}}
  footage/SOURCE_REGISTRY.md, image_gen/{PROMPTING_FACTS.md, LICENSE_EVIDENCE.md, AI_IMAGE_POLICY.md, BAKEOFF_*.md}
  audit/demand/*  (reports copied from OpenCode by the owner)
  package/<episode>/  analytics/
tools/{kaggle_bridge,qa,audio,illustration,prompting,adapters}/  scripts/run_episode.py review_pack.py rebuild_slice_assets.sh  tests/
projects/  (gitignored media)   .kilo/{agents,skills}
```

## 5. Current state (agent-reported, UNVERIFIED by the owner/Claude; re-verify first)
Built and reportedly tested: qc.py + qa_report schema, claim_ids resolve check, finish_audio, TTS tool with license gate (Kokoro ONNX), Kaggle bridge (GPU, internet, multi-image manifest), run_episode.py (10 stages on fakes), chapter mode + LONGFORM_SPEC, SDXL-Lightning generation (10 images, owner saw many artifacts), speculative-illustration gate, prompt builder (19 tests), rubric scorer (9 tests), museum adapters/motion variety/packaging/analytics import modules (fixtures only, never run on a real episode).
Drafts (all NOT_PUBLISHABLE): CID (320x240 archive), Apollo 9 (insufficient legal footage), ISS (HD, single main clip).
Failed/blocked: G2 image bake-off (dependency and memory failures), Z-Image on Kaggle (diffusers/transformers import conflict), niche demand measurement for the speculative niches (YouTube search quota exhausted).
Open owner decisions: niche confirmation (speculative evolution / alien ecosystems proposed; art-history and ISS tracks as alternatives), blind image-model choice, voice-risk sign-off with a guardian, emblem policy, AdSense/guardian (deferred), disclosure wording.

## 6. Build order (milestones; each resumable, bounded, 12-line final report)
1. **F0 Reality audit (read-only)**: git status, tests, disk, state files, list what truly exists vs this spec; write docs/openmontage/FACTORY_GAP_AUDIT.md with PASS/FAIL/NOT_CHECKED per layer. No code changes.
2. **F1 Image engine decision**: finish the 3-model bake-off (S7), tally the owner's blind scores, record the chosen model + prompt rules.
3. **F2 Episode vertical slice, niche A**: 10-12 min speculative-evolution pilot ("How could life survive beneath a frozen alien ocean?") end to end via run_episode.py: ledger (two sources per real-science claim), ~80-100 illustrations, animated diagrams, narration, EDL with motion variety, QC all inputs, package draft. NOT_PUBLISHABLE until owner review.
4. **F3 Real-footage track (ISS/space)**: upgrade the ISS episode (more clips, cropped watermark/emblems, diagrams in timeline, credits burned in, 6-8 min).
5. **F4 Adapter hardening**: museum + NASA + Internet Archive adapters on recorded fixtures, rights classifier regressions.
6. **F5 Review and verification**: independent read-only reviewer, owner checklists, EVALS run, CI script green, portability rebuild N/N.
7. **F6 Analytics loop** after the first manual upload: CSV import, retention-by-chapter report, ladder decision proposal (owner decides).
8. **F7 Scale**: only after >=3 published episodes and measured retention: longer formats via chapter mode, series plan, Shorts pipeline.

## 7. Definition of "100% done"
- One command builds an episode from a approved topic to a publish-ready package, resumable after interruption, with unattended runtime logged.
- All hard rules in section 1 are enforced by code/tests, not by prose.
- QC gates pass on a real 8-10 minute episode with all inputs supplied (no NOT_RUN), thresholds unchanged.
- Owner-approved: voice, image model (blind scored), rights flags, disclosure answer.
- Independent read-only review returned PASS/REVIEW with evidence and every REVIEW item resolved.
- Two further episodes built with <= 1 manual fix each, proving repeatability.
- Rebuild on a clean account from the repo + manifests verifies N/N assets and re-renders the same episode.
- At least one episode manually uploaded by the owner and its Studio metrics imported (CTR, first-30 s retention, AVD, returning viewers) — this measures the BUSINESS, which the factory alone cannot prove.

## 8. Non-goals and known unknowns
- No automatic publishing, no monetization automation, no voice cloning, no music generation until a license policy exists, no photoreal fake imagery, no news, no health/finance/legal advice content, no true crime, no celebrity content.
- Unknown until measured: audience demand and competition for the chosen niche, viewer tolerance of AI stills, Content ID behavior, real T4 speed per model, YouTube's treatment of a new AI-illustrated channel, AdSense eligibility for the owner. The factory must make these cheap to test, not assume them.
- Policy and model landscapes change every few weeks: agents re-read official pages/cards before relying on any stored claim and record URL + access date.

## 9. Standing instructions for agents using this file
Read this file, then docs/openmontage/*_STATE.md and OPENCODE_REQUESTS.md. Start with F0 unless a later milestone is already DONE in the state files. Do not redo completed work. Do not edit this file; propose changes in docs/openmontage/SPEC_CHANGE_REQUESTS.md. Final report format (max 12 lines): Status, Commit, Done, Failed/NOT_CHECKED, Owner decision, Next action.
