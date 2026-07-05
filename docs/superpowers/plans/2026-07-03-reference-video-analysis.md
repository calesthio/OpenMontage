# Reference Video Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an analysis-only pipeline that turns a Douyin URL or local video into a human-editable replication package with transcript, scenes, keyframes, rewrite draft, and production strategy.

**Architecture:** Add a focused `reference-video-analysis` pipeline with director skills and a small `reference_video_package` tool. The tool normalizes upstream ingest/analyze/transcribe artifacts into JSON and Markdown, while existing tools handle download/import, FFmpeg probing, scene detection, frame sampling, and transcription.

**Tech Stack:** Python `BaseTool`, YAML pipeline manifests, Markdown director skills, FFmpeg/ffprobe, pytest contract/unit tests.

---

## File Structure

- Create `pipeline_defs/reference-video-analysis.yaml`: focused pipeline manifest with ingest, analyze, transcribe, package, and review stages.
- Create `skills/pipelines/reference-video-analysis/*.md`: stage director instructions for the new pipeline.
- Create `tools/analysis/reference_video_package.py`: deterministic packaging tool that writes JSON and Markdown review artifacts.
- Create `tests/contracts/test_reference_video_analysis_pipeline.py`: manifest and skill contract tests.
- Create `tests/tools/test_reference_video_package.py`: unit tests for package generation and fallback states.
- Modify `docs/PROVIDERS.md`: document the new reference-video analysis workflow and local-file fallback.

---

### Task 1: Pipeline Manifest Contract

**Files:**
- Create: `tests/contracts/test_reference_video_analysis_pipeline.py`
- Create: `pipeline_defs/reference-video-analysis.yaml`
- Create: `skills/pipelines/reference-video-analysis/ingest-director.md`
- Create: `skills/pipelines/reference-video-analysis/analyze-director.md`
- Create: `skills/pipelines/reference-video-analysis/transcribe-director.md`
- Create: `skills/pipelines/reference-video-analysis/package-director.md`
- Create: `skills/pipelines/reference-video-analysis/review-director.md`

- [ ] **Step 1: Write the failing manifest test**

Create `tests/contracts/test_reference_video_analysis_pipeline.py`:

```python
from pathlib import Path

from lib.pipeline_loader import get_required_tools, get_stage_order, list_pipelines, load_pipeline


def test_reference_video_analysis_pipeline_loads_with_expected_stage_order():
    manifest = load_pipeline("reference-video-analysis")

    assert manifest["name"] == "reference-video-analysis"
    assert get_stage_order(manifest) == [
        "ingest",
        "analyze",
        "transcribe",
        "package",
        "review",
    ]


def test_reference_video_analysis_pipeline_is_listed_and_uses_existing_analysis_tools():
    manifest = load_pipeline("reference-video-analysis")
    tools = get_required_tools(manifest)

    assert "reference-video-analysis" in list_pipelines()
    assert "video_downloader" in tools
    assert "custom_asset_import" in tools
    assert "scene_detect" in tools
    assert "frame_sampler" in tools
    assert "transcriber" in tools
    assert "reference_video_package" in tools


def test_reference_video_analysis_required_skills_exist():
    manifest = load_pipeline("reference-video-analysis")
    root = Path(__file__).resolve().parent.parent.parent

    for skill_ref in manifest.get("required_skills", []):
        assert (root / "skills" / f"{skill_ref}.md").is_file(), skill_ref
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/contracts/test_reference_video_analysis_pipeline.py -v
```

Expected: FAIL because `pipeline_defs/reference-video-analysis.yaml` does not exist.

- [ ] **Step 3: Add the pipeline manifest**

Create `pipeline_defs/reference-video-analysis.yaml`:

```yaml
name: reference-video-analysis
version: "0.1"
description: >
  Analysis-only reference video pipeline. Takes a Douyin URL or local video,
  extracts transcript, scene structure, keyframes, pacing, and production
  strategy, then stops for human review before any face replacement or remake.
category: analysis
stability: beta
default_checkpoint_policy: guided

reference_input:
  supported: true
  analysis_depth: standard
  analysis_tools:
    - video_downloader
    - custom_asset_import
    - video_analyzer
    - scene_detect
    - frame_sampler
    - transcriber

required_skills:
  - pipelines/reference-video-analysis/ingest-director
  - pipelines/reference-video-analysis/analyze-director
  - pipelines/reference-video-analysis/transcribe-director
  - pipelines/reference-video-analysis/package-director
  - pipelines/reference-video-analysis/review-director
  - meta/reviewer
  - meta/checkpoint-protocol

orchestration:
  mode: guided-analysis
  skill: pipelines/reference-video-analysis/ingest-director
  budget_default_usd: 0.00
  max_revisions_per_stage: 3
  max_send_backs: 3
  max_wall_time_minutes: 15

stages:
  - name: ingest
    skill: pipelines/reference-video-analysis/ingest-director
    produces:
      - reference_source
    required_tools:
      - video_downloader
      - custom_asset_import
    tools_available:
      - video_downloader
      - custom_asset_import
    checkpoint_required: true
    human_approval_default: false
    review_focus:
      - Douyin link download falls back cleanly to local file input
      - Source URL or local path provenance is preserved
      - No platform access restrictions are bypassed
    success_criteria:
      - reference_source includes local_video_path or structured fallback_reason

  - name: analyze
    skill: pipelines/reference-video-analysis/analyze-director
    required_artifacts_in:
      - reference_source
    produces:
      - reference_analysis
    required_tools:
      - scene_detect
      - frame_sampler
    optional_tools:
      - video_analyzer
    tools_available:
      - scene_detect
      - frame_sampler
      - video_analyzer
    checkpoint_required: false
    human_approval_default: false
    review_focus:
      - Scene timings are usable for human review
      - Keyframes exist for representative moments
      - Visual analysis handles no-audio videos
    success_criteria:
      - reference_analysis includes metadata, scenes, and keyframes

  - name: transcribe
    skill: pipelines/reference-video-analysis/transcribe-director
    required_artifacts_in:
      - reference_source
    produces:
      - reference_transcript
    required_tools:
      - transcriber
    tools_available:
      - transcriber
    checkpoint_required: false
    human_approval_default: false
    review_focus:
      - Transcript text is marked raw and human-editable
      - Missing or unavailable transcription is surfaced as pending_transcription
    success_criteria:
      - reference_transcript includes raw_text or status pending_transcription

  - name: package
    skill: pipelines/reference-video-analysis/package-director
    required_artifacts_in:
      - reference_source
      - reference_analysis
      - reference_transcript
    produces:
      - replication_package
    required_tools:
      - reference_video_package
    tools_available:
      - reference_video_package
    checkpoint_required: true
    human_approval_default: false
    review_focus:
      - JSON package is machine-readable
      - Markdown review file is easy to edit
      - Production mode recommendation is explicit
    success_criteria:
      - replication_package JSON and Markdown artifacts exist
      - approval.status is pending_human_review

  - name: review
    skill: pipelines/reference-video-analysis/review-director
    required_artifacts_in:
      - replication_package
    produces:
      - reference_review_decision
    tools_available: []
    checkpoint_required: true
    human_approval_default: true
    review_focus:
      - Human edits copy and confirms next production mode
      - Team-authorized face or avatar requirement is acknowledged
      - No downstream production starts before approval
    success_criteria:
      - reference_review_decision is approved or approved_with_changes
```

- [ ] **Step 4: Add stage director skills**

Create `skills/pipelines/reference-video-analysis/ingest-director.md`:

```markdown
# Reference Video Analysis — Ingest Director

Resolve the user's Douyin URL or local video path into a local reference video artifact.

Use `video_downloader` first for supported URLs. If the download fails because of login, region, network, platform protection, watermark handling, or unsupported URL structure, stop cleanly and ask for a local file path. Do not bypass platform access controls.

Use `custom_asset_import` for local video files. Preserve the original input, local video path, source type, and any fallback reason in `reference_source`.
```

Create `skills/pipelines/reference-video-analysis/analyze-director.md`:

```markdown
# Reference Video Analysis — Analyze Director

Analyze the local reference video without changing it.

Use FFmpeg-backed tools to probe video duration, dimensions, and frame rate. Use `scene_detect` for scene boundaries and `frame_sampler` for representative keyframes. Use `video_analyzer` when available for richer visual summaries.

If scene detection is unavailable or weak, use fixed-interval segmentation and mark the method as `fixed_interval_fallback`. Output `reference_analysis` with metadata, scenes, keyframe paths, and analysis limitations.
```

Create `skills/pipelines/reference-video-analysis/transcribe-director.md`:

```markdown
# Reference Video Analysis — Transcribe Director

Extract raw speech text from the reference video.

Use `transcriber` when available. Mark the transcript as raw source material that requires human review and rewriting before production. If the video has no audio or transcription is unavailable, output `reference_transcript.status = pending_transcription` with a clear reason.

Do not treat the transcript as automatically publishable copy.
```

Create `skills/pipelines/reference-video-analysis/package-director.md`:

```markdown
# Reference Video Analysis — Package Director

Build the human-editable replication package.

Use `reference_video_package` to combine `reference_source`, `reference_analysis`, and `reference_transcript` into JSON plus Markdown. The package must include transcript, rewrite draft, scene table, keyframes, pacing notes, and a recommended production mode: `direct_face_swap`, `full_remake`, or `hybrid`.

Set `approval.status = pending_human_review`. Do not start face replacement, digital-human generation, Seedance generation, or final composition in this stage.
```

Create `skills/pipelines/reference-video-analysis/review-director.md`:

```markdown
# Reference Video Analysis — Review Director

Guide the human review before downstream production.

Ask the user to edit the rewrite draft, confirm scene notes, choose a production mode, and confirm that any face or avatar asset used later is team-authorized. The review decision can be `approved`, `approved_with_changes`, or `rejected`.

Only approved or approved_with_changes packages can feed direct face replacement, full remake, or hybrid creator-video production.
```

- [ ] **Step 5: Run manifest test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/contracts/test_reference_video_analysis_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/contracts/test_reference_video_analysis_pipeline.py pipeline_defs/reference-video-analysis.yaml skills/pipelines/reference-video-analysis/
git commit -m "feat: add reference video analysis pipeline"
```

---

### Task 2: Replication Package Tool

**Files:**
- Create: `tests/tools/test_reference_video_package.py`
- Create: `tools/analysis/reference_video_package.py`

- [ ] **Step 1: Write failing package tool tests**

Create `tests/tools/test_reference_video_package.py`:

```python
from pathlib import Path

from tools.analysis.reference_video_package import ReferenceVideoPackage
from tools.base_tool import ToolStatus


def test_reference_video_package_writes_json_and_markdown(tmp_path):
    project_dir = tmp_path / "project"
    output_dir = project_dir / "artifacts"

    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(project_dir),
            "reference_source": {
                "input_type": "local_file",
                "input": "source.mp4",
                "local_video_path": str(project_dir / "reference" / "source.mp4"),
                "duration_seconds": 6.0,
                "width": 720,
                "height": 1280,
                "fps": 30,
            },
            "reference_analysis": {
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 3.0,
                        "visual_summary": "人物正面口播，办公室背景",
                        "camera_motion": "固定机位",
                        "keyframes": ["keyframes/s1.jpg"],
                    },
                    {
                        "scene_id": "s2",
                        "start": 3.0,
                        "end": 6.0,
                        "visual_summary": "产品特写和字幕强调",
                        "camera_motion": "轻微推近",
                        "keyframes": ["keyframes/s2.jpg"],
                    },
                ]
            },
            "reference_transcript": {
                "status": "ok",
                "raw_text": "前三秒给出钩子，然后展示产品卖点。",
                "segments": [
                    {"start": 0.0, "end": 3.0, "text": "前三秒给出钩子"},
                    {"start": 3.0, "end": 6.0, "text": "然后展示产品卖点"},
                ],
            },
            "output_dir": str(output_dir),
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["approval"]["status"] == "pending_human_review"
    assert package["rewrite_draft"]["status"] == "needs_human_edit"
    assert package["replication_strategy"]["recommended_mode"] == "hybrid"
    assert len(package["scenes"]) == 2
    assert Path(result.data["json_path"]).is_file()
    assert Path(result.data["markdown_path"]).is_file()
    assert "前三秒给出钩子" in Path(result.data["markdown_path"]).read_text(encoding="utf-8")
    assert result.artifacts == [result.data["json_path"], result.data["markdown_path"]]


def test_reference_video_package_handles_pending_transcription(tmp_path):
    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(tmp_path),
            "reference_source": {
                "input_type": "local_file",
                "input": "silent.mp4",
                "local_video_path": str(tmp_path / "silent.mp4"),
                "duration_seconds": 4.0,
            },
            "reference_analysis": {
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 4.0,
                        "visual_summary": "无音频产品展示",
                        "keyframes": [],
                    }
                ]
            },
            "reference_transcript": {
                "status": "pending_transcription",
                "reason": "no_audio_stream",
            },
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["transcript"]["status"] == "pending_transcription"
    assert package["rewrite_draft"]["text"] == ""
    assert "no_audio_stream" in Path(result.data["markdown_path"]).read_text(encoding="utf-8")


def test_reference_video_package_tool_is_available_without_external_dependencies():
    assert ReferenceVideoPackage().get_status() == ToolStatus.AVAILABLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/tools/test_reference_video_package.py -v
```

Expected: FAIL because `tools.analysis.reference_video_package` does not exist.

- [ ] **Step 3: Implement the package tool**

Create `tools/analysis/reference_video_package.py`:

```python
"""Build a human-editable reference video replication package."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-video"


def _scene_speech(scene: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    if scene.get("speech"):
        return str(scene["speech"])
    start = float(scene.get("start", 0.0))
    end = float(scene.get("end", start))
    texts = [
        str(segment.get("text", "")).strip()
        for segment in segments
        if float(segment.get("end", 0.0)) > start and float(segment.get("start", 0.0)) < end
    ]
    return " ".join(text for text in texts if text).strip()


def _recommend_mode(scenes: list[dict[str, Any]], transcript_status: str) -> tuple[str, str]:
    has_speech = transcript_status == "ok"
    has_multiple_scenes = len(scenes) > 1
    if has_speech and has_multiple_scenes:
        return "hybrid", "口播适合团队数字人重制，B-roll 或产品镜头可用 Seedance/素材重制。"
    if has_speech:
        return "full_remake", "内容主要依赖口播，适合用团队数字人重新生产。"
    return "full_remake", "未获得可用口播转写，优先基于画面结构重新制作。"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, package: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    transcript = package["transcript"]
    lines = [
        "# Reference Video Replication Package",
        "",
        "## Source",
        "",
        f"- Input type: `{package['source'].get('input_type', 'unknown')}`",
        f"- Input: `{package['source'].get('input', '')}`",
        f"- Local video: `{package['source'].get('local_video_path', '')}`",
        f"- Duration: `{package['source'].get('duration_seconds', '')}` seconds",
        "",
        "## Raw Transcript",
        "",
    ]
    if transcript.get("status") == "pending_transcription":
        lines.extend([
            f"Transcript pending: `{transcript.get('reason', 'unknown')}`",
            "",
        ])
    else:
        lines.extend([
            transcript.get("raw_text", ""),
            "",
        ])
    lines.extend([
        "## Rewrite Draft",
        "",
        package["rewrite_draft"].get("text", ""),
        "",
        "## Scenes",
        "",
        "| Scene | Time | Visual | Speech | Production Hint |",
        "| --- | --- | --- | --- | --- |",
    ])
    for scene in package["scenes"]:
        lines.append(
            "| {scene_id} | {start:.2f}-{end:.2f}s | {visual} | {speech} | {hint} |".format(
                scene_id=scene.get("scene_id", ""),
                start=float(scene.get("start", 0.0)),
                end=float(scene.get("end", 0.0)),
                visual=str(scene.get("visual_summary", "")).replace("|", "\\|"),
                speech=str(scene.get("speech", "")).replace("|", "\\|"),
                hint=str(scene.get("production_hint", "")).replace("|", "\\|"),
            )
        )
    strategy = package["replication_strategy"]
    lines.extend([
        "",
        "## Replication Strategy",
        "",
        f"- Recommended mode: `{strategy['recommended_mode']}`",
        f"- Reason: {strategy['reason']}",
        f"- Alternatives: `{', '.join(strategy['alternatives'])}`",
        "",
        "## Approval",
        "",
        f"- Status: `{package['approval']['status']}`",
        "- Production requires human review and team-authorized face/avatar assets.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


class ReferenceVideoPackage(BaseTool):
    name = "reference_video_package"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "reference_analysis"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies."
    capabilities = ["replication_package", "reference_review_markdown", "strategy_recommendation"]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=50, network_required=False)
    idempotency_key_fields = ["reference_source", "reference_analysis", "reference_transcript"]
    side_effects = ["writes replication package JSON and Markdown files"]

    input_schema = {
        "type": "object",
        "required": ["project_dir", "reference_source", "reference_analysis", "reference_transcript"],
        "properties": {
            "project_dir": {"type": "string"},
            "reference_source": {"type": "object"},
            "reference_analysis": {"type": "object"},
            "reference_transcript": {"type": "object"},
            "output_dir": {"type": "string"},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        project_dir = Path(inputs["project_dir"])
        source = dict(inputs["reference_source"])
        analysis = inputs.get("reference_analysis") or {}
        transcript_input = inputs.get("reference_transcript") or {}
        transcript_status = transcript_input.get("status", "ok")
        segments = transcript_input.get("segments") or []

        scenes: list[dict[str, Any]] = []
        for index, scene in enumerate(analysis.get("scenes") or [], start=1):
            normalized = {
                "scene_id": scene.get("scene_id") or f"s{index}",
                "start": float(scene.get("start", 0.0)),
                "end": float(scene.get("end", scene.get("start", 0.0))),
                "visual_summary": scene.get("visual_summary", ""),
                "speech": _scene_speech(scene, segments),
                "camera_motion": scene.get("camera_motion", ""),
                "pacing": scene.get("pacing", "unknown"),
                "keyframes": scene.get("keyframes", []),
                "production_hint": scene.get("production_hint", "team_digital_human_remake"),
            }
            scenes.append(normalized)

        recommended_mode, reason = _recommend_mode(scenes, transcript_status)
        raw_text = transcript_input.get("raw_text", "") if transcript_status != "pending_transcription" else ""
        package = {
            "version": "1.0",
            "source": source,
            "transcript": {
                "status": transcript_status,
                "raw_text": raw_text,
                "segments": segments,
            },
            "rewrite_draft": {
                "status": "needs_human_edit",
                "text": raw_text,
            },
            "scenes": scenes,
            "replication_strategy": {
                "recommended_mode": recommended_mode,
                "alternatives": ["direct_face_swap", "full_remake", "hybrid"],
                "reason": reason,
            },
            "approval": {
                "status": "pending_human_review",
                "required_before_production": True,
                "requires_team_authorized_face_or_avatar": True,
            },
        }
        if transcript_status == "pending_transcription":
            package["transcript"]["reason"] = transcript_input.get("reason", "transcription_unavailable")

        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts" / "reference-video-analysis")
        source_name = _safe_slug(Path(str(source.get("local_video_path") or source.get("input") or "reference")).stem)
        json_path = output_dir / f"{source_name}-replication-package.json"
        markdown_path = output_dir / f"{source_name}-replication-review.md"

        _write_json(json_path, package)
        _write_markdown(markdown_path, package)

        return ToolResult(
            success=True,
            data={
                "replication_package": package,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
            artifacts=[str(json_path), str(markdown_path)],
        )
```

- [ ] **Step 4: Run package tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/tools/test_reference_video_package.py -v
```

Expected: PASS.

- [ ] **Step 5: Verify registry discovery**

Run:

```bash
.venv/bin/python - <<'PY'
from tools.tool_registry import registry
registry.discover()
tool = registry.get("reference_video_package")
print(bool(tool), tool.get_status() if tool else None)
PY
```

Expected output includes:

```text
True ToolStatus.AVAILABLE
```

- [ ] **Step 6: Commit**

```bash
git add tests/tools/test_reference_video_package.py tools/analysis/reference_video_package.py
git commit -m "feat: add reference video package tool"
```

---

### Task 3: Local Video Smoke Path

**Files:**
- Create: `tests/tools/test_reference_video_local_smoke.py`
- Modify: `docs/PROVIDERS.md`

- [ ] **Step 1: Write a local-file smoke test**

Create `tests/tools/test_reference_video_local_smoke.py`:

```python
from pathlib import Path

from tools.analysis.reference_video_package import ReferenceVideoPackage


def test_reference_video_package_accepts_fixed_interval_scene_data(tmp_path):
    project_dir = tmp_path / "reference-smoke"
    keyframe = project_dir / "keyframes" / "scene-1.jpg"
    keyframe.parent.mkdir(parents=True)
    keyframe.write_bytes(b"fake-jpeg")

    result = ReferenceVideoPackage().execute(
        {
            "project_dir": str(project_dir),
            "reference_source": {
                "input_type": "local_file",
                "input": str(project_dir / "source.mp4"),
                "local_video_path": str(project_dir / "source.mp4"),
                "duration_seconds": 5.0,
                "width": 720,
                "height": 1280,
                "fps": 30,
                "ingest_method": "custom_asset_import",
            },
            "reference_analysis": {
                "method": "fixed_interval_fallback",
                "scenes": [
                    {
                        "scene_id": "s1",
                        "start": 0.0,
                        "end": 5.0,
                        "visual_summary": "单镜头竖屏口播",
                        "camera_motion": "固定机位",
                        "keyframes": [str(keyframe)],
                    }
                ],
            },
            "reference_transcript": {
                "status": "ok",
                "raw_text": "这是一个本地视频解析冒烟测试。",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "这是一个本地视频解析冒烟测试。",
                    }
                ],
            },
        }
    )

    assert result.success
    package = result.data["replication_package"]
    assert package["source"]["ingest_method"] == "custom_asset_import"
    assert package["scenes"][0]["pacing"] == "unknown"
    assert package["scenes"][0]["keyframes"] == [str(keyframe)]
    assert Path(result.data["markdown_path"]).is_file()
```

- [ ] **Step 2: Run smoke test**

Run:

```bash
.venv/bin/python -m pytest tests/tools/test_reference_video_local_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Document the workflow**

Add this section to `docs/PROVIDERS.md` near the analysis/local tools sections:

```markdown
### Reference Video Analysis Package

**Tool:** `reference_video_package`
**Pipeline:** `reference-video-analysis`
**Runtime:** Local, analysis-only

Use this workflow when a creator provides a Douyin link or local video as a reference. The MVP produces a human-editable replication package with transcript, rewrite draft, scene table, keyframes, pacing notes, and a recommended downstream mode (`direct_face_swap`, `full_remake`, or `hybrid`).

The pipeline tries URL ingestion first when a supported downloader can access the link. If Douyin blocks download because of login, region, watermark handling, or platform protection, it stops cleanly and asks for a local file path. It must not bypass platform access controls.

This workflow does not replace faces, call digital-human APIs, generate Seedance clips, or publish outputs. Downstream production requires human review and team-authorized face/avatar assets.
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/contracts/test_reference_video_analysis_pipeline.py tests/tools/test_reference_video_package.py tests/tools/test_reference_video_local_smoke.py -v
```

Expected: PASS.

- [ ] **Step 5: Run broader contract/tool regression**

Run:

```bash
.venv/bin/python -m pytest tests/contracts tests/tools/test_reference_video_package.py tests/tools/test_reference_video_local_smoke.py -v
```

Expected: PASS or same unrelated skips as the current baseline.

- [ ] **Step 6: Commit**

```bash
git add tests/tools/test_reference_video_local_smoke.py docs/PROVIDERS.md
git commit -m "docs: document reference video analysis workflow"
```

---

## Self-Review

- Spec coverage: The plan covers the focused pipeline, local fallback, JSON and Markdown package, pending transcription, strategy recommendation, compliance boundaries, and tests.
- Placeholder scan: No `TBD`, `TODO`, or vague implementation steps are required for MVP1.
- Type consistency: The plan consistently uses `reference_source`, `reference_analysis`, `reference_transcript`, `replication_package`, `reference_video_package`, and `reference-video-analysis`.
