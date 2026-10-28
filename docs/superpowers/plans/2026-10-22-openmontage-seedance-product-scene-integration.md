# OpenMontage × Seedance Product Scene Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Codex-guided product marketing pipeline that uses Volcengine ARK for Seedream images and Seedance videos, uses the active Codex model for copywriting, and delivers 1–3 user-approved product style packages with royalty-free music.

**Architecture:** Keep OpenMontage instruction-driven: Python provides a secure config bridge, an ARK image-generation tool, schemas, and verification; pipeline manifests and stage skills own decisions, approvals, prompting, copywriting, and delivery. Reuse the existing `seedance_ark` video tool and existing FFmpeg/music tools.

**Tech Stack:** Python 3.12, `requests`, `jsonschema`, OpenMontage `BaseTool`, `git`, `pytest`, FFmpeg/ffprobe, Volcengine ARK Seedream/Seedance.

**Spec:** `docs/superpowers/specs/2026-10-22-openmontage-seedance-product-scene-design.md`

## Global Constraints

- The user is a beginner: every prompt uses plain language, one decision at a time, and 3–4 enumerated choices.
- No separate web UI; all interaction happens in Codex.
- ARK is used only for Seedream images and Seedance videos.
- Copywriting uses the active Codex session model; do not add an ARK text model.
- The default is four preview images, followed by user selection of 1–3 complete styles.
- Each selected style produces three scene images, one 8-second 9:16 video, three copy variants, and one approved music track.
- Each selected style uses a three-shot storyboard: product detail, use scene, hero still.
- Video motion adapts to the scene style; do not force one motion language across all styles.
- Final videos have no burned-in title, subtitle, CTA, or logo.
- Music candidates come from Pixabay; three candidates per selected style must be presented before selection.
- Never print or persist a complete ARK API key.
- Never silently switch provider, model, duration, ratio, resolution, or music source.
- Use TDD for production code: failing test, expected RED, minimal GREEN, full relevant suite.
- Do not call a paid ARK generation endpoint during implementation tests unless the user separately approves a live validation.

## Review Focus

- A missing or malformed `~/.seedance/config.json` must produce a beginner-readable setup error and must not expose partial secrets.
- An ARK image response that changes shape from base64 to URL must either download correctly or fail without writing an invalid file.
- A user who selects fewer than three complete styles must not trigger hidden generation for unselected styles.
- A rejected image or video must block its downstream step and preserve paid artifacts for review.
- A music search that returns duplicate or unlicensed tracks must stop before mixing and present alternatives.

---

## Part 1 — Environment and API Key Preparation

**Part gate:** End after Task 3. Show the user the config status, masked key, runtime status, and test evidence. Wait for approval before Part 2.

### Task 1: Secure Seedance Config Bridge

**Files:**
- Create: `lib/seedance_config.py`
- Create: `tests/lib/test_seedance_config.py`

**Interfaces:**
- Consumes: environment variables `SEEDANCE_CONFIG_PATH`, `ARK_API_KEY`, `ARK_BASE_URL`, `ARK_SEEDREAM_MODEL`, `ARK_SEEDANCE_MODEL`
- Produces: `load_seedance_config(config_path: Path | None = None) -> SeedanceConfig`
- Produces: `mask_api_key(value: str) -> str`
- Produces: `SeedanceConfig(api_key, api_base, image_model, video_model, default_duration, default_ratio, source)`

- [ ] **Step 1: Write config tests**

```python
def test_environment_key_overrides_config_file(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"api_key": "ark-file-key"}')
    monkeypatch.setenv("ARK_API_KEY", "ark-env-key")
    assert load_seedance_config(config_file).api_key == "ark-env-key"


def test_missing_key_raises_beginner_readable_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(SeedanceConfigError, match="火山方舟"):
        load_seedance_config(tmp_path / "missing.json")


def test_mask_api_key_never_returns_full_secret():
    masked = mask_api_key("ark-1234567890abcdef")
    assert masked != "ark-1234567890abcdef"
    assert masked.startswith("ark-")
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m pytest tests/lib/test_seedance_config.py -q`

Expected: collection error because `lib.seedance_config` does not exist.

- [ ] **Step 3: Implement the config module**

Use a frozen dataclass and these defaults:

```python
DEFAULT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_IMAGE_MODEL = "doubao-seedream-5-0-pro-260628"
DEFAULT_VIDEO_MODEL = "doubao-seedance-2-5-260628"
DEFAULT_DURATION = 8
DEFAULT_RATIO = "9:16"
```

Read JSON with UTF-8, validate required types, apply environment overrides, and never include the key in exception messages.

- [ ] **Step 4: Run the focused tests**

Run: `.venv/bin/python -m pytest tests/lib/test_seedance_config.py -q`

Expected: all config tests pass.

- [ ] **Step 5: Commit**

```bash
git add lib/seedance_config.py tests/lib/test_seedance_config.py
git commit -m "feat: add secure seedance config bridge"
```

### Task 2: Reuse the Config Bridge in Seedance Video

**Files:**
- Modify: `tools/video/seedance_ark.py`
- Modify: `tests/contracts/test_seedance_ark_video.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `load_seedance_config`
- Produces: `SeedanceArkVideo` remains named `seedance_ark` and keeps its current `execute(inputs) -> ToolResult` contract
- Produces: status is available when either `ARK_API_KEY` or a valid local Seedance config exists

- [ ] **Step 1: Add failing fallback tests**

Add tests that:

- temporarily set `SEEDANCE_CONFIG_PATH` to a valid config;
- remove `ARK_API_KEY`;
- assert `SeedanceArkVideo().get_status() == ToolStatus.AVAILABLE`;
- assert `_get_api_key()` returns the config key;
- assert an error from a malformed config never contains the key body.

- [ ] **Step 2: Run the focused test**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedance_ark_video.py -q`

Expected: new config-fallback test fails.

- [ ] **Step 3: Update `SeedanceArkVideo`**

Use `load_seedance_config()` in `_get_api_key()` and base-URL resolution. Override `get_status()` so config-backed credentials count as available. Keep `dependencies = ["env:ARK_API_KEY"]` for backward-compatible metadata and explain the config-file fallback in `install_instructions`.

- [ ] **Step 4: Update environment documentation**

Add `SEEDANCE_CONFIG_PATH` to `.env.example` with a comment that it is optional and defaults to `~/.seedance/config.json`.

- [ ] **Step 5: Verify the ARK suite**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedance_ark_video.py tests/lib/test_seedance_config.py -q`

Expected: all tests pass and no HTTP call is attempted by unit tests.

- [ ] **Step 6: Commit**

```bash
git add tools/video/seedance_ark.py tests/contracts/test_seedance_ark_video.py .env.example
git commit -m "feat: reuse seedance config in ark video tool"
```

### Task 3: Part 1 Verification and User Approval

**Files:**
- No source changes.

- [ ] **Step 1: Run preflight with the local config**

Run:

```bash
PATH=.runtime/bin:$PATH NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 .venv/bin/python -c 'from tools.tool_registry import registry; registry.discover(); print(registry.get("seedance_ark").get_status())'
```

Expected: `ToolStatus.AVAILABLE`.

- [ ] **Step 2: Show masked configuration**

Read only non-secret fields and print `mask_api_key(...)`, model IDs, base URL, duration, and ratio. Do not print the full key.

- [ ] **Step 3: Run Part 1 regression tests**

Run: `PATH=.runtime/bin:$PATH NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 .venv/bin/python -m pytest tests/contracts/test_seedance_ark_video.py tests/lib/test_seedance_config.py -q`

Expected: all tests pass.

- [ ] **Step 4: Stop for Part 1 approval**

Present the masked config, runtime versions, test count, and any warnings. Ask whether to proceed to Part 2. Do not begin the analysis deliverable before approval.

---

## Part 2 — Analyze Both Implementations

**Part gate:** End after Task 5. Present the reuse/gap decisions and wait for approval before Part 3.

### Task 4: Write the Side-by-Side Implementation Analysis

**Files:**
- Create: `docs/seedance-product-scene-integration-analysis.md`
- Read: `~/.codex/skills/seedance-product-scene/SKILL.md`
- Read: `~/.codex/skills/seedance-product-scene/scripts/seedance_client.py`
- Read: `tools/video/seedance_ark.py`
- Read: `tools/graphics/seedream_image.py`
- Read: `tools/graphics/image_selector.py`
- Read: `tools/audio/pixabay_music.py`
- Read: `tools/audio/audio_mixer.py`
- Read: `tools/video/video_compose.py`

**Interfaces:**
- Consumes: current source files and registry output
- Produces: a decision table with columns `Capability`, `Skill implementation`, `OpenMontage implementation`, `Reuse decision`, `Gap`, `Owner task`

- [ ] **Step 1: Collect exact registry status**

Run:

```bash
PATH=.runtime/bin:$PATH .venv/bin/python -c 'from tools.tool_registry import registry; import json; registry.discover(); names=["seedance_ark","pixabay_music","audio_mixer","video_compose"]; print(json.dumps({n: registry.get(n).get_info() for n in names}, indent=2, default=str))'
```

Expected: all four tools are discovered; `seedance_ark` reports whether credentials are available.

- [ ] **Step 2: Document the comparison**

The analysis must explicitly answer:

- whether the image API should wrap the skill client or become a native `BaseTool`;
- whether video should reuse `seedance_ark` or create a second client;
- how image paths, prompts, task IDs, and downloads map into project artifacts;
- how Codex-generated copy differs from the skill's static templates;
- how three music candidates are produced with the existing experimental Pixabay search tool;
- which decisions are creative approvals and which are technical implementation details.

- [ ] **Step 3: Verify the analysis covers every required row**

Run: `rg -n "Seedream|Seedance|文案|音乐|分镜|审批|复用|新增" docs/seedance-product-scene-integration-analysis.md`

Expected: each required topic appears at least once.

- [ ] **Step 4: Commit**

```bash
git add docs/seedance-product-scene-integration-analysis.md
git commit -m "docs: analyze seedance and openmontage integration"
```

### Task 5: Part 2 Decision Review

**Files:**
- No source changes.

- [ ] **Step 1: Present the reuse/gap summary**

Explain which code is reused, which code is new, and which behavior comes from skills instead of Python.

- [ ] **Step 2: Present any uncertainty as 3–4 options**

If the analysis finds an unsupported API shape, a music-search limitation, or a conflict with OpenMontage contracts, stop and give 3–4 mutually exclusive options with tradeoffs and a recommendation.

- [ ] **Step 3: Stop for Part 2 approval**

Ask whether to proceed with the proposed reuse/gap decisions. Do not write integration code before approval.

---

## Part 3 — Integrate and Verify

**Part gate:** Implementation begins only after Part 2 approval. Every creative production choice remains a runtime gate with 3–4 options.

### Task 6: Direct ARK Seedream Image Tool

**Files:**
- Create: `tools/graphics/seedream_ark_image.py`
- Create: `schemas/tools/seedream_ark_image.schema.json`
- Create: `tests/contracts/test_seedream_ark_image.py`

**Interfaces:**
- Consumes: `load_seedance_config()`
- Produces: `SeedreamArkImage.execute(inputs: dict[str, Any]) -> ToolResult`
- Input fields: `prompt`, `source_image_path`, `scene_preset`, `product_name`, `model`, `size`, `count`, `output_dir`, `watermark`
- Output fields: `style_preview_id`, `scene_preset`, `model`, `prompt`, `outputs`, `provider`, `duration_seconds`

- [ ] **Step 1: Write failing contract tests**

Test identity, status, local product image encoding, three stable output paths, URL downloads, base64 responses, malformed responses, 401/403/429 errors, and missing-key behavior. HTTP must be mocked.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedream_ark_image.py -q`

Expected: import failure because the tool does not exist.

- [ ] **Step 3: Implement the minimal tool**

Call `POST {api_base}/images/generations` with Bearer authentication and the exact request shape from the skill. Reject count outside 1–3 for this pipeline. Save each response under a deterministic style/scene filename. Never log Authorization headers.

- [ ] **Step 4: Run GREEN**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedream_ark_image.py -q`

Expected: all image-tool tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/graphics/seedream_ark_image.py schemas/tools/seedream_ark_image.schema.json tests/contracts/test_seedream_ark_image.py
git commit -m "feat: add ark seedream image tool"
```

### Task 7: Image Selector Discovery

**Files:**
- Modify: `tests/tools/test_image_selector_routing.py`
- No source change expected

**Interfaces:**
- Consumes: `SeedreamArkImage` with `capability = "image_generation"` and `provider = "ark"`
- Produces: `image_selector` lists and routes to `seedream_ark_image`

- [ ] **Step 1: Add selector characterization test**

Register a real `SeedreamArkImage` and assert it appears in selector candidates and routes when `preferred_tool="seedream_ark_image"`.

- [ ] **Step 2: Run the characterization test**

Run: `.venv/bin/python -m pytest tests/tools/test_image_selector_routing.py -q`

Expected: PASS immediately because the selector auto-discovers `tools/graphics/` providers. This task adds evidence for existing behavior and should not invent a failing production path.

- [ ] **Step 3: Fix registration only if discovery fails**

If the module is already under `tools/graphics/`, no registry source change is expected. If discovery fails, fix the narrow import issue rather than hardcoding the provider into the selector.

- [ ] **Step 4: Run the focused suite**

Run: `.venv/bin/python -m pytest tests/tools/test_image_selector_routing.py tests/contracts/test_seedream_ark_image.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/tools/test_image_selector_routing.py tools/graphics/seedream_ark_image.py
git commit -m "test: cover ark image selector routing"
```

### Task 8: Product Copy and Delivery Schemas

**Files:**
- Create: `schemas/artifacts/product_copy.schema.json`
- Create: `schemas/artifacts/product_delivery.schema.json`
- Modify: `schemas/artifacts/__init__.py`
- Create: `tests/contracts/test_product_scene_artifacts.py`

**Interfaces:**
- Produces: schema `product_copy` with `variants.grassroots`, `variants.premium`, `variants.conversion`
- Produces: schema `product_delivery` with style packages, images, video, music, copy, cost, approvals, and output paths

- [ ] **Step 1: Write failing schema tests**

Use one valid fixture for three copy variants and one valid delivery fixture. Add invalid cases for a missing product name, unlicensed music, a video without a selected image, and an unknown copy variant.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/contracts/test_product_scene_artifacts.py -q`

Expected: schema loading fails.

- [ ] **Step 3: Implement schemas and register names**

Add both names to `ARTIFACT_NAMES`. Keep fields explicit; do not allow free-form replacement for sources, approvals, or output paths.

- [ ] **Step 4: Run GREEN**

Run: `.venv/bin/python -m pytest tests/contracts/test_product_scene_artifacts.py -q`

Expected: all artifact schema tests pass.

- [ ] **Step 5: Commit**

```bash
git add schemas/artifacts/product_copy.schema.json schemas/artifacts/product_delivery.schema.json schemas/artifacts/__init__.py tests/contracts/test_product_scene_artifacts.py
git commit -m "feat: add product scene artifacts"
```

### Task 9: Product Scene Pipeline Manifest

**Files:**
- Create: `pipeline_defs/seedance-product-scene.yaml`
- Create: `tests/contracts/test_seedance_product_scene_pipeline.py`

**Interfaces:**
- Consumes: `seedream_ark_image`, `seedance_ark`, `pixabay_music`, `audio_mixer`, `video_compose`
- Produces: stages `idea`, `proposal`, `style_preview`, `scene_plan`, `assets`, `video_assets`, `copy`, `music`, `compose`, `publish`

- [ ] **Step 1: Write failing manifest tests**

Assert schema validity, exact stage order, approval gates on `idea`, `proposal`, `style_preview`, `scene_plan`, `assets`, `video_assets`, `copy`, `music`, and `publish`, and `motion_required: true` guidance in the proposal criteria.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedance_product_scene_pipeline.py -q`

Expected: manifest-not-found failure.

- [ ] **Step 3: Implement the manifest**

Declare each stage’s `skill`, artifacts, required tools, review focus, and human gate. Do not put creative orchestration logic in Python.

- [ ] **Step 4: Run GREEN**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedance_product_scene_pipeline.py -q`

Expected: manifest tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline_defs/seedance-product-scene.yaml tests/contracts/test_seedance_product_scene_pipeline.py
git commit -m "feat: add seedance product scene pipeline"
```

### Task 10: Stage Skills and Approval UX

**Files:**
- Create: `.agents/skills/seedance-product-scene/SKILL.md`
- Create: `skills/pipelines/seedance-product-scene/executive-producer.md`
- Create: `skills/pipelines/seedance-product-scene/idea-director.md`
- Create: `skills/pipelines/seedance-product-scene/proposal-director.md`
- Create: `skills/pipelines/seedance-product-scene/scene-director.md`
- Create: `skills/pipelines/seedance-product-scene/asset-director.md`
- Create: `skills/pipelines/seedance-product-scene/video-director.md`
- Create: `skills/pipelines/seedance-product-scene/copy-director.md`
- Create: `skills/pipelines/seedance-product-scene/music-director.md`
- Create: `skills/pipelines/seedance-product-scene/compose-director.md`
- Create: `skills/pipelines/seedance-product-scene/publish-director.md`
- Modify: `skills/INDEX.md`

**Interfaces:**
- Consumes: manifest stage names and tool interfaces from Tasks 6–9
- Produces: exact user-facing workflow, prompts, option sets, approval rules, error copy, and artifact creation steps

- [ ] **Step 1: Write the stage skills**

Each director must state its prerequisite artifacts, exact tool calls, review criteria, approval message, and stop conditions. Creative decisions use 3–4 enumerated choices. Copy variants are generated by Codex from supplied facts only. Music candidates must be listened to and selected by the user.

- [ ] **Step 2: Verify every manifest skill resolves**

Run:

```bash
.venv/bin/python -c 'from lib.pipeline_loader import load_pipeline; from pathlib import Path; m=load_pipeline("seedance-product-scene"); missing=[s["skill"] for s in m["stages"] if not (Path("skills")/(s["skill"]+".md")).exists()]; print(missing); raise SystemExit(bool(missing))'
```

Expected: prints `[]` and exits 0.

- [ ] **Step 3: Verify approval language**

Run: `rg -n "3–4|审批|不要继续|停止" skills/pipelines/seedance-product-scene`

Expected: every creative stage contains a clear approval/stop instruction.

- [ ] **Step 4: Commit**

```bash
git add .agents/skills/seedance-product-scene skills/pipelines/seedance-product-scene skills/INDEX.md
git commit -m "feat: add seedance product scene skills"
```

### Task 11: Music, Copy, Compose, and Delivery Flow

**Files:**
- Modify: `tools/audio/pixabay_music.py`
- Create: `tests/contracts/test_pixabay_music_candidates.py`
- Modify: `tests/contracts/test_seedance_product_scene_pipeline.py`
- Modify: `skills/pipelines/seedance-product-scene/music-director.md`
- Modify: `skills/pipelines/seedance-product-scene/compose-director.md`
- Modify: `skills/pipelines/seedance-product-scene/publish-director.md`

**Interfaces:**
- Consumes: `pixabay_music`, `audio_mixer`, `video_compose`
- Produces: `pixabay_music.operation="search"` with up to three candidates and no file download
- Produces: `pixabay_music.operation="download"` for the one user-approved Pixabay candidate
- Produces: one approved music file, a muxed video, and a `product_delivery` artifact

- [ ] **Step 1: Write failing candidate-search tests**

Mock Pixabay HTML/bootstrap data. Assert:

- `operation="search"` returns three ordered candidates;
- no output file is written;
- each candidate exposes title, artist, duration, license, and a Pixabay-owned download URL;
- `operation="download"` writes exactly the selected candidate;
- non-Pixabay download URLs are rejected before network access;
- legacy `search_and_download` still downloads the first result.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/contracts/test_pixabay_music_candidates.py -q`

Expected: unsupported operation or missing candidate fields.

- [ ] **Step 3: Implement candidate search and selected download**

Extend the input schema without removing existing fields. Restrict `download_url` to HTTPS hosts under `pixabay.com`, and preserve the current output and metadata contract for the legacy path.

- [ ] **Step 4: Run music tests GREEN**

Run: `.venv/bin/python -m pytest tests/contracts/test_pixabay_music_candidates.py -q`

Expected: all candidate tests pass without real network access.

- [ ] **Step 5: Add failing flow assertions**

Assert the manifest requires `pixabay_music` in `music`, `audio_mixer` and `video_compose` in `compose`, and `video_compose` in `compose` emits `render_report` plus `final_review`.

- [ ] **Step 6: Run flow RED**

Run: `.venv/bin/python -m pytest tests/contracts/test_seedance_product_scene_pipeline.py -q`

Expected: assertions fail until task names and tool lists are complete.

- [ ] **Step 7: Complete the skills and manifest dependencies**

Each scene calls candidate search once for up to three results, presents all candidates, never auto-selects, then downloads only the approved track. Use `audio_mixer`/`video_compose` with `audio_path` and verify with ffprobe. Product copy uses the active Codex model and records `agent_generated`.

- [ ] **Step 8: Run combined GREEN**

Run: `.venv/bin/python -m pytest tests/contracts/test_pixabay_music_candidates.py tests/contracts/test_seedance_product_scene_pipeline.py tests/contracts/test_product_scene_artifacts.py -q`

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add tools/audio/pixabay_music.py tests/contracts/test_pixabay_music_candidates.py pipeline_defs/seedance-product-scene.yaml skills/pipelines/seedance-product-scene tests/contracts/test_seedance_product_scene_pipeline.py
git commit -m "feat: add music candidate selection workflow"
```

### Task 12: Offline End-to-End Test

**Files:**
- Create: `tests/pipelines/test_seedance_product_scene_e2e.py`

**Interfaces:**
- Consumes: all new tools, manifests, schemas, and skills
- Produces: an offline test proving preview → style selection → scene images → video → copy → music → compose → delivery

- [ ] **Step 1: Write the failing E2E test**

Mock ARK image/video responses and Pixabay responses. Generate the product image fixture at test time with Pillow and create a tiny ffprobe-safe MP4 with FFmpeg in `tmp_path`. Assert no real network or cost occurs.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest tests/pipelines/test_seedance_product_scene_e2e.py -q`

Expected: import or fixture failure before the integration is complete.

- [ ] **Step 3: Implement only the missing glue**

Add schema registration or minimal helper code revealed by the failing test. Do not move orchestration into Python.

- [ ] **Step 4: Run GREEN**

Run: `.venv/bin/python -m pytest tests/pipelines/test_seedance_product_scene_e2e.py -q`

Expected: E2E test passes offline.

- [ ] **Step 5: Commit**

```bash
git add tests/pipelines/test_seedance_product_scene_e2e.py
git commit -m "test: cover product scene workflow offline"
```

### Task 13: Documentation and Full Verification

**Files:**
- Create: `docs/seedance-product-scene.md`
- Modify: `README.md`
- Modify: `README_zh-CN.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `PROJECT_CONTEXT.md`
- Modify: `AGENT_GUIDE.md`

**Interfaces:**
- Consumes: completed implementation
- Produces: beginner usage guide, environment setup, cost warnings, approval map, troubleshooting, and provider documentation

- [ ] **Step 1: Write the beginner guide**

Explain only what a user needs: where the key file is, how to upload a product image, what happens at each confirmation, how to preview music, and where deliverables live. Include one complete example dialogue.

- [ ] **Step 2: Run the full impacted suite**

Run: `PATH=.runtime/bin:$PATH NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 .venv/bin/python -m pytest tests/contracts tests/lib tests/tools tests/pipelines -q`

Expected: all tests pass; record the exact count.

- [ ] **Step 3: Run preflight**

Run: `PATH=.runtime/bin:$PATH .venv/bin/python -c 'from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))'`

Expected: `seedream_ark_image` is available when config is valid, `seedance_ark` is available, and composition runtimes report their actual availability.

- [ ] **Step 4: Review the diff**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; only intended files are modified.

- [ ] **Step 5: Commit**

```bash
git add docs/seedance-product-scene.md README.md README_zh-CN.md docs/PROVIDERS.md PROJECT_CONTEXT.md AGENT_GUIDE.md
git commit -m "docs: explain seedance product scene workflow"
```

- [ ] **Step 6: Stop before live paid generation**

Present test evidence, tool status, exact model IDs, and the smallest live validation plan. Ask the user to approve any real ARK image or video request separately.

---

## Approval Map

| Point | User decision | Options |
|---|---|---|
| Part 1 end | Proceed to implementation analysis | 1. Continue 2. Change credentials 3. Stop |
| Part 2 end | Accept reuse/gap decisions | 1–3 options based on findings, with recommendation |
| Production proposal | Number of complete styles | 1, 2, or 3 |
| Production style | Scene families | luxury, nature, tech, office |
| Production storyboard | Structure | single take, three shots, montage |
| Production video | Duration and ratio | 8s 9:16, 10s 16:9, 8s 1:1, dual output |
| Image gate | Main scene image | candidate 1, 2, 3, or regenerate |
| Video gate | Final video | accept, regenerate, adjust, change parameters |
| Copy gate | Copy variants | keep all, revise one, rewrite all |
| Music gate | Track | candidate 1, 2, 3, or user upload |
| Live validation | Paid ARK generation | yes with stated budget, or stop |

