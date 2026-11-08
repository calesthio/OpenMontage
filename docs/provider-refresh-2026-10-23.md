# Provider refresh — October 23, 2026

Implemented in `codex/provider-refresh-oct23`, based on origin/main `c8066452`.
The original checkout and its uncommitted work were preserved in place.

## Changes

- Google: Omni GA model, Nano Banana 2.1 on Google/fal/Replicate, Vertex-only direct Veo/Imagen routing, explicit Vertex credential precedence.
- ElevenLabs: v4 Text to Dialogue and Turbo WebSocket transports; video-to-music with separate-track ingestion.
- Narration: xAI TTS, HeyGen native and catalog voices, Voxtral 3, MAI Voice 2.1/Flash.
- Conversion/transcription: HeyGen speech-to-speech, Voxtral 3 recorded transcription, MAI streaming transcription.
- Images: FLUX 3 on BFL/fal/Replicate, Fibo 2 on Bria/fal, MAI Image 2.6/Flash.
- Video: FLUX 3 Max and Vidu Q4 on fal, Grok Imagine 1.5/Lite direct.
- Realtime: bounded file runner plus caller-managed session transport for Grok Voice 3, Eleven Realtime Mini/Max, and MAI transcription. No microphone UI or automatic tool execution.
- Host-specific schema fixtures, credentials documentation, agent guidance, and offline regression tests.

Kling 4 and realtime translation are intentionally excluded. Unverified Atlas routes and research-only model candidates were not invented.

## Review

A separate reviewer received the scope, research plan, implementation location, and API evidence. Valid findings were reproduced or checked against implementation, then corrected:

- Complete cache identities and stochastic classification for paid generation.
- Validate output formats before submission; preserve HeyGen catalog responses with their actual codec suffix.
- Preserve structured Grok format settings and normalize MAI selector controls.
- Force Vertex for Imagen when API-key credentials coexist.
- Normalize BFL references and validate paired dimensions; enforce MAI dimension limits.
- Reject incompatible Bria masks before generation.
- Receive realtime events concurrently with input sending, use Eleven bursty pacing for files, and reject tool calls in the finite runner.

The reviewer confirmed all reported fixes and independently passed the then-current 26-test provider suite. Later regression coverage adds explicit Vertex ADC routing and Bria URL edit instruction mapping.

## Validation limits

All generation requests in tests are mocked, and the repository network guard remains enabled. No paid generations, account entitlement checks, voice ownership checks, or subjective media-quality evaluations were performed. Credential presence indicates configuration, not verified service access. New prices require current account-specific quotes.

See [the integration guide](../.agents/skills/provider-refresh-oct23/SKILL.md) for exact model IDs, host coverage, API references, and setup.

## Final checks

- Full repository run: 2,102 passed, 5 skipped, 3 expected failures; five failures were obsolete migration expectations or mock signatures.
- After updating those tests, a final rerun of all affected modules and provider regressions passed: **179 passed** (includes all five previously failing cases and 28 new provider tests).
- Required compilation checks passed; all changed/new Python files compiled. `git diff --check` passed.
- The complete suite was not rerun a second time after the test-fixture updates; the affected modules were rerun in full.

## Integration with latest main

Merged origin/main `0f191f96` and resolved the four overlapping Gemini Omni conflicts by retaining main's stable adapter, stricter request validation, usage-based pricing, download recovery, documentation, and expanded tests. Provider-refresh additions remain intact.

Post-merge validation: **218 passed**, covering Gemini Omni, the new providers, Google/ElevenLabs migrations, cache identity, and phase-three registry contracts. Python compilation and staged diff checks also passed.
