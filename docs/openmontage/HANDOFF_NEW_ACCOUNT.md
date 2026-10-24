# Handoff to New Account — OpenMontage CID Slice (Milestone G1)

**Purpose:** Enable the owner to continue the CID slice in another account (e.g. a fresh Codespace) after this ~100-minute session ends. Media is gitignored and regenerated from the committed manifest via `scripts/rebuild_slice_assets.sh`.

**Status:** docs only. No media committed.

---

## 1. Branch, clone, and resume

- **Branch:** `factory/business-documentary-pilot`
- **Clone:** `git clone <repo-url> && git checkout factory/business-documentary-pilot`
- **Resume state:** Read `docs/openmontage/MASTER_RUN_STATE.md` — it records HEAD, completed milestones (M1, F1-F5, G1 in progress), next actions, and rollback instructions (`git revert <commit>`).
- **Milestone git log hashes (committed):**
  - M1 selective merge: `528b9fe`
  - F1 fix slice footage: `313e9ee`
  - F2 redo footage quality: `a854e10`
  - F3 still-image-led slice: `550f3e9`
  - F4 Kokoro narration + qc.py static_by_design: `f819d38`
  - F5 moving footage + owner review: `cb4ea57`
  - G1 portability: `<this session's commit>`

---

## 2. Non-git dependencies to reinstall

The new account must install these before running the slice:

| Dependency | Version / source | Purpose |
|---|---|---|
| `curl` | system package | Download assets (uses `-L` for archive.org redirects) |
| `sha256sum` | coreutils | Verify downloaded asset integrity |
| `ffmpeg` / `ffprobe` | 6.1.1 (Ubuntu build) | Slice rebuild: scale, pad, zoompan, concat, mix narration; probe duration/resolution/fps |
| `python3` | 3.14.2 | Kokoro TTS, finish_audio, qc.py, manifest parsing |
| `kokoro` | latest (PyPI) | Local TTS synthesis (CPU fallback) |
| `misaki` | latest (PyPI) | Kokoro text frontend dependency |
| `espeak-ng` | system package | Kokoro text fallback (texts with out-of-dictionary words skipped without it) |
| Kokoro weights | ~313 MB from Hugging Face (`hexgrad/Kokoro-82M`) | Voice model for narration |
| `kaggle` CLI | 2.2.4 | (P3 only, BLOCKED) GPU voice bake-off — not needed for slice rebuild |

Install notes:
- `kokoro` and `misaki` install via `pip install kokoro misaki`.
- Kokoro weights (~313 MB) download on first run from Hugging Face (`hexgrad/Kokoro-82M`).
- `espeak-ng` installs via the system package manager (`apt-get install espeak-ng` on Ubuntu/Codespaces).
- ffmpeg/ffprobe install via system package manager.

---

## 3. Secrets the new account must recreate (name only, never values)

| Secret | Where | Notes |
|---|---|---|
| `KAGGLE_API_TOKEN` | Codespaces secret (repository or account settings) | Name only. Value never printed/logged/committed. Needed only for P3 Kaggle GPU bake-off (BLOCKED), not for slice rebuild. |

No other secrets are required. No OAuth, no YouTube credentials, no API keys are needed for the slice rebuild.

---

## 4. Exact rebuild steps (new account)

1. `git clone <repo-url>`
2. `cd OpenMontage && git checkout factory/business-documentary-pilot`
3. Install dependencies: `curl`, `sha256sum`, `ffmpeg`, `ffprobe`, `python3`, `espeak-ng`
4. `pip install kokoro misaki` (Kokoro weights ~313 MB download on first run)
5. Set `KAGGLE_API_TOKEN` Codespaces secret (name only) if P3 bake-off is retried
6. `bash scripts/rebuild_slice_assets.sh` — downloads + sha256-verifies all 8 assets (still 5 + archive 3) into `projects/slice_cid_v0/`
7. Re-run narration (Kokoro CPU), `finish_audio`, and `tools/qa/qc.py` per `MASTER_RUN_STATE.md` F4/F5 state

---

## 5. Manifest (committed, drives the rebuild)

`docs/openmontage/assets/CID_SLICE_MANIFEST.json` — tracked JSON with, per asset: `asset_id`, `role`, `clip`, `source`, `source_url`, `download_url`, `file_name`, `resolution`, `size_bytes`, `sha256`, `rights_basis`, `center`, `caption`, `third_party_credit`, `identifiable_persons`, `logo_visible`, plus `used_segment`/`archive_item` for archive inserts.

This is the single source of truth for what to download and verify. Media files themselves are never committed (gitignored `projects/`).

---

## 6. Dry-run result (this session)

`scripts/rebuild_slice_assets.sh` was dry-run against one small file (EC84-3167-A still, 72,637 bytes): download with `curl -L` + sha256 verify = PASS. See milestone G1 notes in `MASTER_RUN_STATE.md`.

---

## 7. What is NOT needed for rebuild

- No YouTube OAuth, no publishing credentials, no music library.
- No AI upscaling (not installed, not used).
- No Kaggle GPU/internet (P3 BLOCKED; only needed for voice bake-off retry).
- No paid routes.
