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

- Date / task: 2026-10-21 / S5 Z-Image-Turbo on a 16 GB T4 (Kilo)
- Observed failure and evidence: (1) fp16 + `pipe.to("cuda")` OOMs at load
  (`torch.OutOfMemoryError ... 14.19 GiB allocated`) because the 6B weights do not
  fit; (2) after `enable_model_cpu_offload()` + `low_cpu_mem_usage=False` the
  pipeline returned 13/13 **pure black** frames (min=max=0) with no exception and
  a 50.7 s/img steady state. The vendor card specifies bfloat16.
- Confirmed cause / certainty: certain about the symptom and the precision
  mismatch (fp16 vs vendor bfloat16); the exact mechanism (VAE decode in fp16
  under offload vs. guidance 0) is NOT isolated — one bf16 run would tell.
- Fix or proposed rule: treat "pipeline runs, returns black" as a first-class
  failure. Always compute a black-frame count per image (max pixel < 8) and put it
  in the manifest *and* the objective-check report; never infer success from
  "no exception" or from file size. When a model's card says bf16 and the run
  mandates fp16, expect this and budget the one bf16 test up front.
- Regression test: scripts/s5_checks.py black_flag + tests/test_s5_checks.py::
  test_black_frame_flagged_and_excluded_from_median; the blind pack drops
  black-flagged panels (tests/test_s5_blind_pack.py::
  test_black_model_is_dropped_and_sheet_falls_back_to_two_panels).
- Result: Z-Image-Turbo marked BLOCKED for S5 after 2 attempts; blind pack built
  from SDXL + klein only; the one-line bf16 retest is written down for the owner.

- Date / task: 2026-10-21 / S7 3-model bake-off on Kaggle (Kilo)
- Observed failure and evidence: (1) diffusers 0.41.0 could not be installed with
  transformers 4.57.6 (`ResolutionImpossible`: 0.41.0 needs huggingface-hub>=1.32,
  transformers 4.x pins hub<1.0) and with transformers 5.20.2 the import failed
  (`cannot import name 'FqnToConfig' from 'torchao.quantization'`); diffusers 0.36.0
  and 0.37.0 installed and worked. (2) Z-Image-Turbo OOM'd at load in fp16 with
  `low_cpu_mem_usage=False` on the 14.56 GiB T4; with `enable_model_cpu_offload()` it
  ran but every frame was pure black - the kernel log showed
  `diffusers/image_processor.py:142: RuntimeWarning: invalid value encountered in cast`.
  `vae.config.force_upcast=True` changed nothing (ZImagePipeline never calls
  `upcast_vae()`) and casting the VAE to fp32 changed nothing either, which places the
  NaN before the VAE - inside the fp16 DiT/text-encoder path. (3) The Kaggle runner
  keeps only the output of its LATEST kernel version: `kaggle kernels output
  owner/kernel/<version>` returns the latest output for every version, so a later push
  silently destroys the previous run's images. (4) The sandbox was restarted mid-milestone
  and `/tmp` was wiped, deleting fetched PNGs that could not be re-downloaded.
- Confirmed cause / certainty: (1) a released-stack compatibility matrix, not a model
  problem; (2) fp16 numerical overflow in Z-Image-Turbo, whose vendor card specifies
  bfloat16 - the S7 brief mandates fp16, so this is an owner decision, not an agent fix;
  (3)+(4) infrastructure, both avoidable in the harness.
- Fix or proposed rule: (a) pin a *released* diffusers first (0.37.0 ships both
  Flux2KleinPipeline and ZImagePipeline) and never let a 0.41.0 stack be rung 1;
  (b) for a 6B model on a 16 GB card, enable CPU offload AND treat an all-black output
  as a NUMERICS failure - try the vendor's dtype before declaring the model dead; (c)
  fetch + verify + copy every run's output to a durable path (gitignored
  `output/s7_cache/`) immediately after the run, and never push the next model before
  the current one's output is fetched; (d) keep the ladder's working rung when the
  failure was NOT caused by the stack, and record the real change (the runner gained
  `--load-config` and `--ladder` for this).
- Regression test: tests/test_s7_runner.py (ladder shape, torchao pin on every live
  0.41.0 rung, force_upcast option), tests/test_s7_push_bakeoff.py (load-config and
  ladder overrides are embedded), tests/test_s7_stage_pack_root.py (every cached image
  is re-verified against the kernel manifest sha256), tests/test_s7_blind_pack.py +
  tests/test_s7_tally.py (a blocked model must not become an empty panel).
- Result: SDXL DONE (41.4 s/img, 9169.58 MB, 10/10 verify PASS, and a re-run
  reproduced run 1 bit-for-bit on all 10 sha256), klein DONE (24.691 s/img,
  7995.02 MB, 10/10 verify PASS), Z-Image-Turbo BLOCKED after the 4-attempt cap with
  0 usable images. Agent advisory ranking: klein > SDXL; the owner's blind CSV decides.

- Date / task: 2026-10-22 / G2+G3+G6 episode vertical slice (Kilo, inline)
- Observed failure and evidence: (1) `cmd_qc` fell back to the legacy
  `shared_assets()` when the per-episode artifact dir had no assets, so an empty
  episode inherited another episode's assets and produced an OK verdict; (2)
  `tools/illustration/illustration_qc.qc_batch` returns the key `results`, not
  `images`, so a loop over `data["images"]` silently inspected zero renders; (3)
  `run_illustrations.py status` takes `--kernel-slug`, not `--job-json`, and the
  kernel ref (`owner/kernel`) differs from the `job_id` — passing `job_id` returns
  `Permission 'kernels.get' was denied`, which reads like an auth problem; (4) a
  background torch TTS run was killed by a sandbox restart and left no WAV, while
  the log tail still looked healthy; (5) `cmd | tail -8; echo EXIT=$?` prints the
  exit code of `tail`, not of the command under test.
- Confirmed cause / certainty: (1) legacy-first fallback ordering; (2) untyped dict
  shape in an internal helper; (3) CLI surface differs from the job manifest; (4)
  process lifetime is not an artifact; (5) shell pipeline semantics. All four are
  harness/contract defects, not model quality.
- Fix or proposed rule: (a) release/QC gates prefer `episode_dir` artifacts and only
  consult the legacy QA report when `episode_dir` is unset; (b) assert the helper's
  own key name in a test before looping over its output; (c) status calls take the
  kernel ref from the constant, confirm `KernelWorkerStatus`, never the job id; (d)
  prove long jobs by the artifact (open the WAV, check frames/duration), not by the
  exit echo; (e) run shells with `set -o pipefail` and no `tail` in the measured path.
- Regression test: tests/test_run_episode_gates.py (episode-dir artifacts win, draft
  BLOCKED without script/artifacts), tests/test_episode_batch.py (qc_batch key shape),
  tests/test_render_kenburns_lavfi.py (a real ffmpeg render at 1280x720 with audio).
- Result: pilot narration produced 46 sentences / 299.775 s at 24 kHz mono (torch
  KPipeline path, ONNX weights absent); 84-render klein episode job still RUNNING at
  the time of writing, so no image was claimed as fetched.

- Date / task: 2026-10-22 / S8 5-model image bake-off (Kilo)
- Observed failure and evidence: (1) the Kaggle runner is uploaded as ONE
  self-contained `run.py`, and appending the S8 additions to the S7 engine made
  the additions' `def main()` shadow the engine's `main()` -> `RecursionError:
  maximum recursion depth exceeded` before any model was touched (log:
  `docs/openmontage/image_gen/logs/s8-sdxl-lightning-1/kernel.log`); (2) the
  blind-sheet builder drew only `"ABC"[:len(order)]` panels, so a 4-model pack
  silently dropped the fourth model while the mapping still listed it - the
  owner would have scored a 3-model comparison; (3) the pack-root staging
  matched manifests with a plain glob, so model `sdxl` picked up
  `s7-sdxl-lightning-2/manifest.json`; (4) the review-sheet writer used a
  fixed header and dropped the new `style_fit` column; (5) SANA-Sprint 1.6B
  in fp16 produced 10/10 black frames with
  `diffusers/image_processor.py: RuntimeWarning: invalid value encountered in
  cast` - the same NaN signature as S7's Z-Image-Turbo - and the diffusers
  SCMScheduler refuses any step count other than 2
  (`ValueError: Intermediate timesteps for SCM is not supported when
  num_inference_steps != 2.`).
- Confirmed cause / certainty: (1) name collision in a concatenated module;
  (2) a fixed 3-panel limit in a pack builder that already claimed to support
  N models; (3) glob ambiguity between model names that share a prefix; (4) a
  hard-coded column list; (5) fp16 overflow in a bf16-native model - high
  confidence for the black frames, high confidence for the scheduler error, and
  the transformer-vs-VAE split is narrowed but not proven (the VAE fp32 and the
  fp32 text encoder were both eliminated).
- Fix or proposed rule: (a) when composing a single-file runner, capture the
  engine entry point under a new name before defining your own, and test the
  composed file with `exec` against a fake module; (b) derive the panel count
  and the panel size from the number of models and assert that every model in
  the mapping has a drawn panel; (c) match manifest folders with a strict
  `<prefix>-<model>-<digits>` regex; (d) let the sheet keep its own header;
  (e) treat "all frames black" as a numerics failure first: check the kernel
  log for a cast warning, try an fp32 VAE and an fp32 text encoder, and only
  then blame the model - and check the scheduler's supported step count before
  changing it.
- Regression test: tests/test_s8_bakeoff.py (composed runner registers the
  models, captures the engine `main`, embeds the job), tests/test_s7_blind_pack.py
  (4- and 5-panel sheets draw every model and stay under 1600 px),
  tests/test_s7_stage_pack_root.py (S8 job manifests, strict model matching),
  tests/test_s7_review_write.py (the sheet keeps its own columns).
- Result: SDXL-Lightning 8-step DONE (3.943 s/image, 12.51 usable img/min,
  9168.6 MB, 10/10 verify PASS), DreamShaper XL Lightning DONE (5.112 s/image,
  10.12 img/min, 9968.01 MB, 10/10 verify PASS), SDXL Base and
  FLUX.2-klein-4B reused from S7 (sha256 verified), SANA-Sprint 1.6B BLOCKED
  after the 4-attempt cap with 0 usable frames. Agent advisory ranking:
  klein > SDXL-Lightning > SDXL > DreamShaper XL; the owner's blind CSV decides.
