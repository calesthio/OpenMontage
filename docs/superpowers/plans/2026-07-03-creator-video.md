# Creator Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a creator-video pipeline that supports topic research, script, scene planning, user-supplied assets, Seedance 2.0 video generation, editing, and final composition.

**Architecture:** Keep OpenMontage's agent-first architecture: the new pipeline is a YAML manifest plus director skills, while concrete user asset ingestion is a Python `BaseTool`. Seedance remains a normal `video_generation` provider discovered by `video_selector`; digital-human API integration is intentionally deferred behind the existing `avatar` capability.

**Tech Stack:** Python `BaseTool`, YAML pipeline manifests, Markdown director skills, existing artifact schemas, pytest contract tests.

---

### Task 1: Custom Asset Import Tool

**Files:**
- Create: `tools/assets/__init__.py`
- Create: `tools/assets/custom_asset_import.py`
- Test: `tests/tools/test_custom_asset_import.py`

- [x] **Step 1: Write the failing test**

```python
def test_imports_user_assets_into_project_manifest(tmp_path):
    source = tmp_path / "raw" / "clip.mp4"
    source.parent.mkdir()
    source.write_bytes(b"fake video")

    result = CustomAssetImport().execute({
        "project_dir": str(tmp_path / "project"),
        "assets": [{"path": str(source), "scene_id": "scene-1"}],
    })

    assert result.success
    manifest = result.data["asset_manifest"]
    validate_artifact("asset_manifest", manifest)
    assert manifest["assets"][0]["source_tool"] == "custom_asset_import"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/tools/test_custom_asset_import.py -v`
Expected: FAIL because `tools.assets.custom_asset_import` does not exist.

- [x] **Step 3: Write minimal implementation**

Implement `CustomAssetImport(BaseTool)` with `capability="asset_management"`, copy files into `projects/<slug>/assets/<media-kind>/`, infer media type by extension, and return a schema-valid `asset_manifest`.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/tools/test_custom_asset_import.py -v`
Expected: PASS.

### Task 2: Creator Video Pipeline Contract

**Files:**
- Create: `pipeline_defs/creator-video.yaml`
- Create: `skills/pipelines/creator-video/*-director.md`
- Test: `tests/contracts/test_creator_video_pipeline.py`

- [x] **Step 1: Write the failing test**

```python
def test_creator_video_pipeline_loads_with_expected_stage_order():
    manifest = load_pipeline("creator-video")
    assert get_stage_order(manifest) == [
        "research", "proposal", "script", "scene_plan", "assets", "edit", "compose", "publish"
    ]
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contracts/test_creator_video_pipeline.py -v`
Expected: FAIL because `pipeline_defs/creator-video.yaml` does not exist.

- [x] **Step 3: Write minimal implementation**

Create a valid manifest that uses `custom_asset_import`, `video_selector`, `seedance_video`, `seedance_replicate`, `tts_selector`, `subtitle_gen`, `audio_mixer`, `video_compose`, and `video_stitch` in the relevant stages.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contracts/test_creator_video_pipeline.py -v`
Expected: PASS.

### Task 3: Runtime Governance Compliance

**Files:**
- Modify: `skills/pipelines/creator-video/proposal-director.md`
- Modify: `skills/pipelines/creator-video/compose-director.md`
- Test: `tests/contracts/test_runtime_presentation_contract.py`

- [x] **Step 1: Write the failing test**

Use the existing runtime presentation contract; the new pipeline must pass it without special exclusion.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contracts/test_runtime_presentation_contract.py -v`
Expected: FAIL until creator-video planning and compose skills mention `render_runtime`, `hyperframes`, and `render_runtime_selection`.

- [x] **Step 3: Write minimal implementation**

Add explicit runtime-selection instructions to proposal and compose directors.

- [x] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contracts/test_runtime_presentation_contract.py -v`
Expected: PASS.

### Task 4: Provider Documentation

**Files:**
- Modify: `docs/PROVIDERS.md`
- Modify: `.env.example`

- [x] **Step 1: Verify existing Seedance docs**

Run: `rg -n "Seedance|FAL_KEY|REPLICATE_API_TOKEN" docs/PROVIDERS.md .env.example`
Expected: Seedance 2.0 and `FAL_KEY` are documented; add `REPLICATE_API_TOKEN` only if absent.

- [x] **Step 2: Update docs minimally**

Document that `creator-video` can use Seedance through `FAL_KEY` or `REPLICATE_API_TOKEN`, while custom avatar API is deferred.

- [x] **Step 3: Run focused contract tests**

Run: `python3 -m pytest tests/tools/test_custom_asset_import.py tests/contracts/test_creator_video_pipeline.py tests/contracts/test_runtime_presentation_contract.py -v`
Expected: PASS.
