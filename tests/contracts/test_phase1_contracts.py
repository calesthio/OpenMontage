"""Phase 1 contract tests — Core Talking-Head Pipeline tools."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolResult, ToolTier, ToolStatus, DependencyError
from tools.tool_registry import ToolRegistry
from lib.pipeline_loader import load_pipeline, get_stage_order, get_required_tools, list_pipelines


# ---- Tool imports ----

from tools.analysis.transcriber import Transcriber
from tools.video.video_trimmer import VideoTrimmer
from tools.subtitle.subtitle_gen import SubtitleGen
from tools.analysis.frame_sampler import FrameSampler
from tools.audio.audio_mixer import AudioMixer
from tools.video.video_compose import VideoCompose


# ---- Contract: every tool inherits BaseTool and has required fields ----

PHASE1_TOOLS = [
    Transcriber,
    VideoTrimmer,
    SubtitleGen,
    FrameSampler,
    AudioMixer,
    VideoCompose,
]


class TestPhase1ToolContracts:
    """Verify all Phase 1 tools satisfy the ToolContract."""

    @pytest.mark.parametrize("tool_cls", PHASE1_TOOLS)
    def test_inherits_base_tool(self, tool_cls):
        assert issubclass(tool_cls, BaseTool)

    @pytest.mark.parametrize("tool_cls", PHASE1_TOOLS)
    def test_has_required_identity(self, tool_cls):
        tool = tool_cls()
        assert tool.name, f"{tool_cls.__name__} must have a non-empty name"
        assert tool.version, f"{tool_cls.__name__} must have a version"
        assert tool.tier in ToolTier
        assert len(tool.capabilities) > 0, f"{tool_cls.__name__} must declare capabilities"

    @pytest.mark.parametrize("tool_cls", PHASE1_TOOLS)
    def test_get_info_returns_valid_dict(self, tool_cls):
        tool = tool_cls()
        info = tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == tool.name
        assert info["tier"] in [t.value for t in ToolTier]
        assert info["status"] in ["available", "unavailable", "degraded"]

    @pytest.mark.parametrize("tool_cls", PHASE1_TOOLS)
    def test_has_input_schema(self, tool_cls):
        tool = tool_cls()
        assert isinstance(tool.input_schema, dict)
        assert "properties" in tool.input_schema or "type" in tool.input_schema

    @pytest.mark.parametrize("tool_cls", PHASE1_TOOLS)
    def test_execute_is_implemented(self, tool_cls):
        """Verify execute() is not the abstract stub."""
        tool = tool_cls()
        # Should not raise TypeError — it's implemented
        assert callable(tool.execute)

    @pytest.mark.parametrize("tool_cls", PHASE1_TOOLS)
    def test_dry_run_returns_dict(self, tool_cls):
        tool = tool_cls()
        result = tool.dry_run({})
        assert isinstance(result, dict)
        assert "tool" in result
        assert result["tool"] == tool.name


# ---- Contract: tools report correct status based on dependencies ----

class TestPhase1ToolStatus:
    def test_subtitle_gen_always_available(self):
        """SubtitleGen has no external dependencies — always available."""
        tool = SubtitleGen()
        assert tool.get_status() == ToolStatus.AVAILABLE

    def test_transcriber_reports_status_correctly(self):
        """Transcriber should report unavailable if faster_whisper not installed."""
        tool = Transcriber()
        status = tool.get_status()
        assert status in (ToolStatus.AVAILABLE, ToolStatus.UNAVAILABLE)

    def test_ffmpeg_tools_report_status(self):
        """FFmpeg-dependent tools should report based on ffmpeg availability."""
        for cls in [VideoTrimmer, FrameSampler, AudioMixer, VideoCompose]:
            tool = cls()
            status = tool.get_status()
            assert status in (ToolStatus.AVAILABLE, ToolStatus.UNAVAILABLE)


# ---- Contract: tool names are unique ----

class TestPhase1ToolNames:
    def test_unique_names(self):
        names = [cls().name for cls in PHASE1_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_expected_names(self):
        names = {cls().name for cls in PHASE1_TOOLS}
        expected = {"transcriber", "video_trimmer", "subtitle_gen", "frame_sampler", "audio_mixer", "video_compose"}
        assert names == expected


# ---- Contract: tools are discoverable via registry ----

class TestPhase1ToolDiscovery:
    def test_all_phase1_tools_discoverable(self):
        """Registry.discover() should find all Phase 1 tools."""
        reg = ToolRegistry()
        discovered = reg.discover("tools")
        for cls in PHASE1_TOOLS:
            name = cls().name
            assert name in discovered or reg.get(name) is not None, (
                f"Tool {name!r} not discovered by registry"
            )

    def test_phase1_tools_are_core_tier(self):
        """All Phase 1 tools should be in the CORE tier."""
        for cls in PHASE1_TOOLS:
            tool = cls()
            assert tool.tier == ToolTier.CORE, f"{tool.name} should be CORE tier"


# ---- Contract: SubtitleGen produces valid output without FFmpeg ----

class TestSubtitleGenUnit:
    def test_srt_generation(self):
        segments = [
            {
                "text": "Hello world",
                "start": 0.0,
                "end": 1.5,
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "world", "start": 0.6, "end": 1.5},
                ],
            },
            {
                "text": "This is a test",
                "start": 2.0,
                "end": 4.0,
                "words": [
                    {"word": "This", "start": 2.0, "end": 2.3},
                    {"word": "is", "start": 2.4, "end": 2.5},
                    {"word": "a", "start": 2.6, "end": 2.7},
                    {"word": "test", "start": 2.8, "end": 4.0},
                ],
            },
        ]
        tool = SubtitleGen()
        result = tool.execute({
            "segments": segments,
            "format": "srt",
            "output_path": "test_output.srt",
        })
        assert result.success
        assert len(result.artifacts) == 1

        content = Path(result.artifacts[0]).read_text()
        assert "-->" in content
        assert "Hello world" in content
        # Cleanup
        Path(result.artifacts[0]).unlink(missing_ok=True)

    def test_vtt_generation(self):
        segments = [
            {
                "text": "Test cue",
                "start": 1.0,
                "end": 3.0,
                "words": [
                    {"word": "Test", "start": 1.0, "end": 1.5},
                    {"word": "cue", "start": 1.6, "end": 3.0},
                ],
            },
        ]
        tool = SubtitleGen()
        result = tool.execute({
            "segments": segments,
            "format": "vtt",
            "output_path": "test_output.vtt",
        })
        assert result.success
        content = Path(result.artifacts[0]).read_text()
        assert content.startswith("WEBVTT")
        Path(result.artifacts[0]).unlink(missing_ok=True)

    def test_json_generation(self):
        segments = [
            {
                "text": "JSON test",
                "start": 0.0,
                "end": 2.0,
                "words": [
                    {"word": "JSON", "start": 0.0, "end": 0.8},
                    {"word": "test", "start": 0.9, "end": 2.0},
                ],
            },
        ]
        tool = SubtitleGen()
        result = tool.execute({
            "segments": segments,
            "format": "json",
            "output_path": "test_output.caption.json",
        })
        assert result.success
        data = json.loads(Path(result.artifacts[0]).read_text())
        assert "cues" in data
        assert len(data["cues"]) >= 1
        Path(result.artifacts[0]).unlink(missing_ok=True)

    def test_word_grouping_respects_max_words(self):
        words = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(20)]
        segments = [{"text": " ".join(w["word"] for w in words), "start": 0.0, "end": 10.0, "words": words}]

        tool = SubtitleGen()
        result = tool.execute({
            "segments": segments,
            "format": "json",
            "max_words_per_cue": 4,
            "output_path": "test_grouping.caption.json",
        })
        assert result.success
        data = json.loads(Path(result.artifacts[0]).read_text())
        for cue in data["cues"]:
            assert len(cue["words"]) <= 4
        Path(result.artifacts[0]).unlink(missing_ok=True)

    def test_segment_fallback_without_words(self):
        """Segments without word-level timestamps use segment-level timing."""
        segments = [
            {"text": "No word data", "start": 0.0, "end": 2.0},
        ]
        tool = SubtitleGen()
        result = tool.execute({
            "segments": segments,
            "format": "srt",
            "output_path": "test_fallback.srt",
        })
        assert result.success
        content = Path(result.artifacts[0]).read_text()
        assert "No word data" in content
        Path(result.artifacts[0]).unlink(missing_ok=True)


# ---- Contract: missing input file returns error, not crash ----

class TestPhase1ErrorHandling:
    def test_transcriber_missing_file(self):
        tool = Transcriber()
        result = tool.execute({"input_path": "/nonexistent/file.mp4"})
        assert not result.success
        assert "not found" in result.error.lower() or "not installed" in result.error.lower()

    def test_video_trimmer_missing_file(self):
        tool = VideoTrimmer()
        result = tool.execute({
            "operation": "cut",
            "input_path": "/nonexistent/file.mp4",
        })
        assert not result.success

    def test_video_trimmer_missing_operation_returns_clean_error(self):
        """Confirmed live: a call missing 'operation' must fail with a clear
        ToolResult error, not a bare KeyError('operation')."""
        tool = VideoTrimmer()
        result = tool.execute({
            "input_path": "/nonexistent/file.mp4",
            "start_seconds": 0,
            "end_seconds": 3.5,
        })
        assert not result.success
        assert "operation" in result.error.lower()

    def test_frame_sampler_missing_file(self):
        tool = FrameSampler()
        result = tool.execute({
            "input_path": "/nonexistent/file.mp4",
            "strategy": "interval",
        })
        assert not result.success

    def test_audio_mixer_missing_tracks(self):
        tool = AudioMixer()
        result = tool.execute({"operation": "mix", "tracks": []})
        assert not result.success

    def test_video_compose_missing_decisions(self):
        tool = VideoCompose()
        result = tool.execute({"operation": "compose"})
        assert not result.success


# ---- Contract: talking-head pipeline manifest ----

class TestTalkingHeadManifest:
    def test_manifest_loads(self):
        manifest = load_pipeline("talking-head")
        assert manifest["name"] == "talking-head"
        assert manifest["category"] == "talking_head"

    def test_manifest_has_all_stages(self):
        manifest = load_pipeline("talking-head")
        stages = get_stage_order(manifest)
        assert stages == ["idea", "script", "scene_plan", "assets", "edit", "compose", "publish"]

    def test_manifest_references_phase1_tools(self):
        manifest = load_pipeline("talking-head")
        tools = get_required_tools(manifest)
        phase1_tools = {"transcriber", "video_trimmer", "subtitle_gen", "frame_sampler", "audio_mixer", "video_compose"}
        # At least some Phase 1 tools should be referenced
        assert len(tools & phase1_tools) > 0

    def test_manifest_listed(self):
        assert "talking-head" in list_pipelines()

    def test_manifest_has_required_skills(self):
        manifest = load_pipeline("talking-head")
        skills = manifest.get("required_skills", [])
        # Instruction-driven architecture: skills are stage director + meta skills
        assert any("talking-head" in s for s in skills)
        assert any("reviewer" in s for s in skills)
        assert any("checkpoint-protocol" in s for s in skills)

    def test_idea_and_publish_require_approval(self):
        manifest = load_pipeline("talking-head")
        for stage in manifest["stages"]:
            if stage["name"] in ("idea", "publish"):
                assert stage.get("human_approval_default") is True


# ---- Contract: skill files exist ----

class TestPhase1Skills:
    @pytest.mark.parametrize("skill_path", [
        "skills/core/ffmpeg.md",
        "skills/core/whisperx.md",
        "skills/core/subtitle-sync.md",
        "skills/creative/video-editing.md",
        "skills/creative/enhancement-strategy.md",
    ])
    def test_skill_file_exists(self, skill_path):
        full_path = PROJECT_ROOT / skill_path
        assert full_path.exists(), f"Skill file missing: {skill_path}"

    @pytest.mark.parametrize("skill_path", [
        "skills/core/ffmpeg.md",
        "skills/core/whisperx.md",
        "skills/core/subtitle-sync.md",
        "skills/creative/video-editing.md",
        "skills/creative/enhancement-strategy.md",
    ])
    def test_skill_has_content(self, skill_path):
        full_path = PROJECT_ROOT / skill_path
        content = full_path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Skill file too short: {skill_path}"
        assert "## When to Use" in content, f"Skill missing 'When to Use' section: {skill_path}"
        assert "## Quality Checklist" in content, f"Skill missing 'Quality Checklist' section: {skill_path}"
