# CID Full Draft — Internal Draft Status (NOT_PUBLISHABLE)

**Milestone I5 (Kilo).** Scope: factory only (docs/, tools/, scripts/, tests/, .kilo/). No media committed; artifacts live in docs/openmontage/slice/artifacts/.

**Status:** NOT_PUBLISHABLE. Narration synthesis was NOT performed in this session.

## 1. Why narration synthesis was not performed

- Kokoro-82M (the cleared voice, weights/code Apache-2.0 per config/voice.json and VOICE_DECISION.md) is **not installed** in this environment; installing it would require the ~313 MB model wheel plus runtime dependencies (kokoro, misaki, torch CPU) — a new dependency set not added per the no-new-dependencies guidance.
- Piper `en_US-lessac-medium` is **BLOCKED** (license UNKNOWN) per config/voice.json.
- All other TTS tools (ElevenLabs, Azure, Cartesia, etc.) require API keys/secrets, which are out of scope (no secrets, no new credentials).
- Therefore no Kokoro narration audio was synthesized, finish_audio was not run on narration, and qc.py was not run with all media inputs (ffprobe_streams/full_decode/blackdetect/freezedetect/silencedetect/ebur128/duration_vs_script/subtitle_sync need a rendered video + audio).

## 2. EDL plan (per-cut rationale, static cards declared static_by_design)

Source beats map to CID_FULL_SCRIPT_v0.md (6 beats, 40 sentences, claim_ids on every sentence; see CID_FULL_CLAIM_IDS.json).

| Beat | Narration source | Planned visuals | Cut rationale | Static by design? |
|---|---|---|---|---|
| B1 Preparation | sentences B1-1..B1-9 | NIX-EM-0004-01 flight montage insert + EC84-3167-A practice-run still + "Flight Path & Timeline" card | Establish program scope, aircraft, FM-9 additive | Timeline card: yes |
| B2 Remote piloting | sentences B2-1..B2-8 | NIX-EM-0004-01 + EC84-3167-A | Remote-piloting commitment, 150 ft decision point | no |
| B3 Approach | sentences B3-1..B3-6 | NIX-LV-1998-00090 (pt 1 approach) + EC84-31805 pre-impact skid still | Impact geometry, 3.8 deg glide slope, centerline commitment | no |
| B4 Impact | sentences B4-1..B4-4 | NIX-LV-1998-00090 (impact) + NIX-LV-1998-00092 (fireball) + ECN-31803 / EC84-31809 | Cutter strike, right inboard engine, fireball | no |
| B5 Fire | sentences B5-1..B5-7 | NIX-LV-1998-00092 (fireball) + NIX-LV-1998-00098 + ECN-31808 + EC84-31809 + ECN-28307 dummies | Fire behavior, interior damage, cabin cameras | no |
| B6 Aftermath / lessons | sentences B6-1..B6-6 | ECN-28307 dummies still + "Key Numbers" card + "Lessons Learned" card | FAA cancellation, fuel ineffectiveness, contradictions | Both cards: yes |

**Archive clips (8, all source_policy_us_gov, 320x240 h.264):** NIX-EM-0004-01, NIX-EM-0004-02, NIX-LV-1998-00090/91/92/93/96/98. Best-verified decodable: NIX-EM-0004-01, NIX-LV-1998-00090, NIX-LV-1998-00092, NIX-LV-1998-00098.

**Stills (5 NASA Armstrong, source_policy_us_gov, up to 1040x832):** ECN-31803, ECN-31808, EC84-3167-A, EC84-31809, ECN-28307.

**Graphics cards (2 original):** Flight Path & Timeline (B1), Key Numbers (B6); B6 additionally a Lessons Learned card.

## 3. Subtitles / credits

- Subtitles (SRT) would be derived from the 40 script sentences with sentence timestamps once narration exists. Not generated (no audio).
- Credits template: title "Controlled Impact Demonstration — CID Technical Slice", production OpenMontage Factory, source NASA Armstrong / NASA Dryden / NASA Langley / FAA (DOT/FAA/CT-87/10), rights source_policy_us_gov, no third-party credit, no NASA emblem/logo use, synthetic-voice disclosure placeholder (owner decision pending).

## 4. NOT_PUBLISHABLE reasons

1. **Narration not synthesized:** Kokoro-82M not installed in this environment; no cleared alternative TTS available without secrets.
2. **Voice license gate:** Kokoro-82M weights/code Apache-2.0 clear, but UNKNOWN only the provenance of part of the training data (synthetic data) — residual risk; owner sign-off required (VOICE_DECISION.md §4).
3. **No full-clip frame review:** archive clip flags (identifiable_persons, logo_visible/insignia) unreviewed at frame level; owner frame review pending.
4. **NASA insignia clearance:** undecided whether incidental insignia in CID footage requires separate clearance per NASA Media Usage Guidelines.
5. **Synthetic-voice disclosure:** not evaluated against current YouTube synthetic/altered-content rules.
6. **B6 aftermath gap:** no aftermath motion footage; B6 covered by graphics cards + dummies still only (graphics-only, per CID_BEAT_COVERAGE.md §5).
7. **Single-source claims:** 28 of 40 sentences rely on a single source (flagged in script); CID-06/CID-10/CID-15 upgraded to TWO_SOURCES via FAA/CT-87/10 this session.
8. **qc.py not run with all media inputs:** no rendered video+audio exists, so ffprobe/full_decode/blackdetect/freezedetect/silencedetect/ebur128/duration_vs_script/subtitle_sync could not execute. claim_ids + claim_ids_resolve checks PASS on CID_FULL_CLAIM_IDS.json (52/52).

## 5. Next smallest step (owner decision)

Owner to: (a) sign off on Kokoro-82M voice license residual risk or select another cleared voice; (b) install kokoro + synthesize narration (or approve a cleared TTS path); (c) complete frame review + insignia clearance; (d) then render, run qc.py with all inputs, and re-assess publishability.
