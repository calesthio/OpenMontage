# MASTER RUN State — OpenMontage (2026-10-17)

**HEAD at start:** 21903ee (factory/business-documentary-pilot)
**Preflight:** git clean-ish (AGENTS.md modified by user — preserved), disk 3.4 GB free, KAGGLE_API_TOKEN set (length 37), kaggle auth OK (exit 0)

## Phase status
| Phase | Status | Evidence | Commit hash |
|---|---|---|---|
| P1 Voice license evidence | DONE | docs/openmontage/VOICE_BAKEOFF_LICENSES.md (Chatterbox MIT/MIT, Maya1 Apache2/Apache2, Kokoro-82M Apache2/Apache2 all PASS; ASR faster-whisper MIT + openai-whisper MIT; weights not separately licensed) | 94c789d |
| P2 Evidence ledger + script | DONE | docs/openmontage/evidence/CID_CLAIM_LEDGER.md (16 claims), docs/openmontage/slice/CID_SLICE_SCRIPT_v0.md (8 sentences, DRAFT/NOT_PUBLISHABLE, S8 BLOCKED), docs/openmontage/slice/CID_SLICE_CLAIM_IDS.json; QC claim_ids check PASS (9/9 with claim_id); NASA Facts PDF fetched -> FS claims AGENT_VERIFIED_TEXT | 9bf1605 |
| P3 Kaggle voice bake-off | BLOCKED | Kaggle GPU job forts845/of-bridge-runner pushed OK (enable_gpu=true, enable_internet=true) but stayed KernelWorkerStatus.QUEUED for 15+ min poll window, never reached RUNNING/COMPLETE => total-timeout BLOCKED. Blocker: GPU/internet provisioning (GPU quota exhausted or enable_internet requires phone verification). Owner action: verify phone number in Kaggle settings / check GPU quota; 1 retry attempt remains (max 2). | — |
| P4 TTS integration | DONE | tools/audio/tts_kaggle.py (KokoroTTSTool: license gate blocks piper, bridge+BLOCKED→local Kokoro fallback, finish_audio+QC verify), config/voice.json, tests/tools/test_tts_kaggle.py (5 pass); P3 BLOCKED so Kokoro CPU fallback used; py_compile OK | fafc238 |
| P5 Footage source registry | DONE | docs/openmontage/footage/SOURCE_REGISTRY.md (probe results for NASA/IA/Wikimedia/LoC/NARA/DVIDS; MISSING adapters: NASA SVS, DVIDS, Open Beelden, Europeana, Smithsonian, NPS, CDC, Vimeo CC, Videezy); all 16 existing adapters verified via auto-discovery (12 available, 4 key-required unavailable) | 7c41da6 |
| P6 Technical slice ~50s | DONE | 4 CID clips from archive.org NIX (all source_policy_us_gov, no third-party credit per RIGHTS_MODEL.md); final slice 48.93s at 1920x1080 30fps h264/aac in projects/slice_cid_v0/ (gitignored); QC qa_report.json ALL PASS (12/12 checks); EDL with per-cut rationale; credits.txt; subtitles.srt; contact_sheet.jpg; NOT_PUBLISHABLE (unreviewed flags, single-source claims, voice owner sign-off, S8 blocked) | 501585b |
| P7 Global check | DONE | docs/openmontage/GLOBAL_CHECK_2026-10-17.md (all phases, tests, QC summary, repo hygiene, open gates); docs/openmontage/OWNER_ACTIONS.md (numbered owner steps); 32 tests passed | — |
| P7 Global check | PENDING | — | — |

## Rules observed
- KAGGLE_API_TOKEN: never printed/logged/committed/passed on CLI; env check yes/no only
- Network: kaggle CLI/bridge, images-api.nasa.gov, nasa.gov, archive.org (curl -L), official license pages, HF/GitHub/PyPI LICENSE pages. NTRS blocked — do not retry
- Downloads only into gitignored projects/ or /tmp, never committed; delete temp files
- Disk < 800 MB free → write state and STOP whole run
- ERROR/HTTP/EMPTY separate states; fail-closed; unmeasured = BLOCKED or NOT_RUN
- Code test-first (red then green); run new + existing tests; report exact commands/exit codes
- Roles inline; never claim unobserved work
