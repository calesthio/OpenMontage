# Lessons

Record only useful, evidence-backed lessons. Do not include secrets or personal data.

## Entry template
- Date / task:
- Observed failure and evidence:
- Confirmed cause / uncertainty:
- Fix or proposed rule:
- Regression test:
- Result:

## Entries

- Date / task: 2026-10-17 / M1 preflight & rights gate (C3)
- Observed failure and evidence: Rights gate rejected a clip that the written rule appeared to allow; the applied gate was stricter than RIGHTS_MODEL.md's `source_policy_us_gov` conditions (third-party credit present in metadata caused `unknown` → REJECT despite NASA producer).
- Confirmed cause / uncertainty: Implementation followed fail-closed rule exactly (`rights_basis` unknown => NOT USABLE); written rule's exceptions were not encoded as usable paths. Cause: rule text and code diverged on third-party-credit handling.
- Fix or proposed rule: Align RIGHTS_MODEL.md text with fail-closed implementation; document that any third-party credit forces `unknown`/REJECT unless explicit license exists. No code change needed.
- Regression test: footage-scout classifies a NASA clip with third-party credit as `unknown`/REJECT; a clean NASA clip as `source_policy_us_gov`/USABLE.
- Result: Verified in P5/P6 slice; all 4 CID clips classified `source_policy_us_gov` (no third-party credit).

- Date / task: 2026-10-17 / archive.org download (C5)
- Observed failure and evidence: archive.org retrieval returned a 0-byte file; download appeared to succeed but produced empty output.
- Confirmed cause / certainty: Missing `curl -L` to follow archive.org's redirect; without `-L` curl saved the redirect HTML/empty body as the payload.
- Fix or proposed rule: Always use `curl -L` (follow redirects) for archive.org and similar hosts; validate non-zero size and media header before accepting a download.
- Regression test: re-download a known archive.org asset with `curl -L` and confirm file size > 0 and valid media header.
- Result: Fix applied in P6; 4 CID clips downloaded successfully (non-zero, valid).

- Date / task: 2026-10-17 / subagent roles (M1)
- Observed failure and evidence: Subagent outputs were treated as independent decisions rather than inline proposals; risk of unverified claims being acted on.
- Confirmed cause / certainty: Role framing implied independence; no explicit "inline, not independent" rule in force.
- Fix or proposed rule: State "inline, not independent" for every subagent role; subagent proposes, orchestrator verifies, owner approves. Never claim subagent output as verified fact.
- Regression test: N/A (process rule). Confirmed via M1 preflight notes: roles stated inline.
- Result: Process rule adopted for M1.

- Date / task: 2026-10-17 / NASA NTRS lookup
- Observed failure and evidence: NTRS (NASA Technical Reports Server) unreachable from the sandbox; fact-check source could not be retrieved.
- Confirmed cause / certainty: Network block in sandbox environment; NTRS host not accessible. Not a rights or content issue.
- Fix or proposed rule: Mark NTRS-sourced claims as NOT_CHECKED/BLOCKED; do not retry NTRS; use alternative primary sources (NASA images/media page, archive.org).
- Regression test: N/A (network limitation). Confirmed: NTRS unreachable; alternative sources used.
- Result: Noted as blocker; NTRS not retried.

- Date / task: 2026-10-17 / claim CID-13 (single-source)
- Observed failure and evidence: Claim CID-13 was a single-source load-bearing claim; no independent corroboration.
- Confirmed cause / certainty: Only one source supported the claim; risk of fabrication or error if relied upon alone.
- Fix or proposed rule: Require >=2 independent sources for load-bearing claims; mark single-source claims NEEDS_REVIEW or exclude from final narration.
- Regression test: claim_ids audit flags CID-13 as single-source; verified in P2 claim_ids check (9/9 with claim_id but source diversity not enforced).
- Result: Claim ledger records source count; CID-13 flagged for human review.

- Date / task: 2026-10-17 / Codespace disk (C6)
- Observed failure and evidence: `/workspaces` at 89% used (3.3 GB free) during M1 preflight; torch/caches risk filling disk.
- Confirmed cause / certainty: Python/torch caches and model downloads in Codespace consume disk; no cleanup policy.
- Fix or proposed rule: Set disk stop threshold (< 800 MB free → STOP whole run); download only into gitignored `projects/` or `/tmp`; delete temp files after use; monitor `df -h /workspaces` before large downloads.
- Regression test: `df -h /workspaces` shows 3.3 GB free pre-M1; enforce stop if < 800 MB.
- Result: Disk monitored; no large downloads during M1.

- Date / task: 2026-10-19 / Z1 voice environment setup
- Observed failure and evidence: kokoro 0.2.2 requires transformers >= 2.6 (torch 2.5.1+cpu failed import); kokoro 0.2.2 requires MToken.prespace removed in misaki 0.9.x. Two failed installs before working combination found.
- Confirmed cause / certainty: Version incompatibilities between kokoro 0.2.2, transformers, and misaki. Not a network or rights issue.
- Fix or proposed rule: Pin kokoro==0.2.2, misaki==0.7.17, torch==2.6.0+cpu in python3.12 venv; document exact versions in docs/openmontage/z1_voice_venv.requirements.txt.
- Regression test: `import kokoro, misaki, torch, soundfile, stable_whisper` succeeds in venv; 10s Kokoro sample synthesizes.
- Result: Z1 DONE — 14.625s sample synthesized, finish_audio PASS, qc.py PASS.

- Date / task: 2026-10-19 / Z1 venv wipe + Kokoro weight re-download
- Observed failure and evidence: /tmp/kilo directory (venv + weights cache) wiped by interrupted tool execution. Re-download of Kokoro-82M weights (~313MB) failed: HF xet CAS server (cas-server.xethub.hf.co) and CDN (us.aws.cdn.hf.co) both unreachable from this network. HF_HUB_DISABLE_XET=1 regular HTTP also stuck at 0 bytes. 4 fix attempts exhausted (hf_hub downgrade, direct curl CDN, hf_hub 2.2.0 reinstall, HF_HUB_DISABLE_XET=1).
- Confirmed cause / certainty: Network-level blocking of Hugging Face xet/CDN infrastructure from this sandbox. Not a code or rights issue.
- Fix or proposed rule: Record Kokoro weights as a restore-from-cache dependency. Owner action: restore /tmp/kilo/z1_venv + /tmp/kilo/hf_cache on a network with HF access, or reinstall kokoro==0.2.2 + misaki==0.7.17 + torch==2.6.0+cpu in python3.12 venv. Z3/Z4 smoke tests blocked until weights restored.
- Regression test: `import kokoro` succeeds in venv; KPipeline(lang_code="a") downloads/loads weights without xet errors.
- Result: Z3/Z4 code+tests complete (fake stages), smoke tests BLOCKED until weights restored.

- Date / task: 2026-10-19 / qc.py claim_ids_resolve multi-claim IDs
- Observed failure and evidence: qc.py claim_ids_resolve treated "ARTEMIS-05, ARTEMIS-07" as a single unknown claim_id instead of splitting comma-separated IDs. Test-first red then green.
- Confirmed cause / certainty: qc.py did not split comma/semicolon-separated claim_id strings before ledger lookup.
- Fix or proposed rule: Split claim_id on [,;] before ledger resolution; check each part independently; SINGLE_SOURCE/UNVERIFIED flag check applies per part.
- Regression test: tests/test_qc_tool.py::test_multi_claim_ids_resolve (PASS).
- Result: qc.py fixed; Artemis claim_ids_resolve PASS (20/20 claims).

- Date / task: 2026-10-19 / Z3 pipeline smoke test
- Observed failure and evidence: Full Z3 smoke test on artemis BLOCKED at narration stage — Kokoro-82M weights unreachable (HF network block). Orchestration logic fully verified with fake stages (6/6 tests pass).
- Confirmed cause / certainty: Same HF xet/CDN network block as Z1 weight re-download.
- Fix or proposed rule: Do not block milestone completion on smoke tests requiring external weight downloads. Mark smoke test BLOCKED with exact blocker + owner action; continue with independent phases.
- Regression test: tests/test_run_episode.py all pass with fake stages.
- Result: Z3 code+tests DONE; smoke test BLOCKED (owner action: restore Kokoro weights).

- Date / task: 2026-10-21 / S4 model bakeoff on Kaggle (Kilo)
- Observed failure and evidence: Z-Image-Turbo job failed 5x on `forts845/openmontage-runner`: (1) job.json not copied by Kaggle (only run.py -> script.py) -> fixed by embedding JOB_EMBEDDED in runner; (2) diffusers-from-source pulled transformers 5.x which requires huggingface-hub<2.0 but kernel had hub 2.2.0 -> ResolutionImpossible; (3) hub 1.x + transformers 4.x still conflicted with diffusers main; (4) hub 1.x + transformers 5.x loaded but `diffusers.loaders.single_file` import failed (transformers 5.x vs git-main diffusers incompatibility); SDXL job failed once on `cannot import name 'FqnToConfig' from 'torchao.quantization'` (torchao vs diffusers main mismatch).
- Confirmed cause / certainty: git-main diffusers is not version-compatible with the Kaggle kernel's pre-installed torchao/transformers/huggingface_hub. Not a code, rights, or model-card issue. Each fix attempt changed only the pip install stack; the runner code itself is stable (tests pass).
- Fix or proposed rule: Install one mutually-compatible pinned stack in the kernel with --force-reinstall to clear stale copies: huggingface-hub>=1.32.0,<2.0.0 + transformers>=5.0.0,<6.0.0 + torchao>=0.11,<0.14 + git+https://github.com/huggingface/diffusers. Record exact versions (diffusers commit hash, transformers, huggingface_hub, torch) in the manifest. Max 2 fix attempts per model; after that mark BLOCKED with exact error, versions, and traceback path; do not chase dependency conflicts for hours.
- Regression test: tests/tools/test_s1_z_image_turbo_run.py (manifest records versions + diffusers_commit); tests/tools/test_s4_* (runner compiles, manifest has version fields).
- Result: SDXL resubmitted with torchao pin and is RUNNING; Z-Image-Turbo marked BLOCKED (max attempts reached); FLUX.2-klein-4B pending.


- Date / task: 2026-10-21 / S5 bake-off Kaggle harness (Kilo)
- Observed failure and evidence: three kernel runs died before any GPU work.
  (1) S4's last run: the runner imported ZImagePipeline/SDXL/Flux in one `from
  diffusers import (...)` for every model, so the SDXL job crashed on
  `ImportError: cannot import name 'ZImagePipeline'` (released diffusers lacks it)
  and produced 0 images.
  (2) S5 SDXL run 1: `SyntaxError: name 'OUT' is used prior to global declaration`
  (the function used OUT at the top, `global OUT` came later).
  (3) S5 SDXL run 2: `NameError: name 'null' is not defined` — the job was embedded
  with plain json.dumps, and JSON `null/true/false` are not Python literals.
- Confirmed cause / certainty: harness bugs in the runner/push script, not model,
  network, or rights issues. Each is deterministic and cheap to test locally.
- Fix or proposed rule: (a) import only the pipeline class the job needs and name
  the class in the job payload; (b) declare `global` before first use; (c) embed a
  job as a JSON *string* and `json.loads` it at runtime (`JOB_EMBEDDED =
  json.loads("{...}")`); (d) never push a runner whose embedded payload has not
  been exec'd locally for every model.
- Regression test: tests/test_s5_runner.py (global-before-use AST check, compile,
  probe classes, no bitsandbytes/git-main) and tests/test_s5_push_bakeoff.py
  (exec the exact pushed runner text for sdxl/zimage/klein; asserts None stays
  None). Both pass locally before every push.
- Result: SDXL run 3 reached RUNNING with the same runner text that passed those
  tests; the S4 zero-image failure cannot recur because each job now imports one class.

- Date / task: 2026-10-21 / F1-fix chapter mode + config wiring (Kilo)
- Observed failure and evidence: two `tests/test_run_chapters.py` tests were red at
  HEAD. `_write_chapter_script()` writes rows as `| B<chapter>-<sentence> | ... |`,
  but both parsers (`cmd_script_validation`, `split_script_into_chapters`) accepted
  only `B<digits>` (`cells[0][1:].isdigit()`). The test helper reproduced the real
  writer format, so `--chapters` would have produced zero-sentence chapter scripts.
  Separately, `config/qc_thresholds.json` was not valid JSON (leading `#` comment
  lines), and `qc.py` only read a config when passed explicitly, so the pipeline
  silently used code defaults.
- Confirmed cause / certainty: parser/format mismatch between writer and reader
  (deterministic); config file format and loader default (deterministic, both
  reproduced by tests before the fix).
- Fix or proposed rule: one shared `_parse_script_rows()` accepts `B<n>` and
  `B<n>-<m>`; QC loads `config/qc_thresholds.json` by default and fails closed on
  missing/malformed config; config files are strict JSON (comments live in docs).
  Rule: whenever a writer and a reader share a format, add a round-trip test with
  the writer's exact output, not a hand-written sample.
- Regression test: tests/test_run_chapters.py (5 pass), tests/test_edl_generic.py
  (5 pass), tests/tools/test_qc_tool.py thresholds tests (4) + mixed-ID claim tests (4).
- Result: 24 impacted tests pass, qc file 22 pass, CI fast suite result recorded in
  docs/openmontage/F1FIX_STATE.md.
