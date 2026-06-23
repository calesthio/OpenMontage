"""Phase 2 contract tests — Enhancement Layer tools."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolResult, ToolTier, ToolStatus  # noqa: E402
from tools.tool_registry import ToolRegistry  # noqa: E402

from tools.enhancement.face_enhance import FaceEnhance, PRESETS as FACE_PRESETS  # noqa: E402
from tools.analysis.scene_detect import SceneDetect  # noqa: E402
from tools.enhancement.color_grade import ColorGrade, PROFILES as COLOR_PROFILES  # noqa: E402
from tools.audio.audio_enhance import AudioEnhance, PRESETS as AUDIO_PRESETS  # noqa: E402
from tools.graphics.image_selector import ImageSelector  # noqa: E402
from tools.graphics.code_snippet import CodeSnippet, THEMES as CODE_THEMES  # noqa: E402
from tools.graphics.diagram_gen import DiagramGen  # noqa: E402


PHASE2_TOOLS = [
    FaceEnhance,
    SceneDetect,
    ColorGrade,
    AudioEnhance,
    ImageSelector,
    CodeSnippet,
    DiagramGen,
]


# ---- Contract: every tool inherits BaseTool and has required fields ----

class TestPhase2ToolContracts:
    @pytest.mark.parametrize("tool_cls", PHASE2_TOOLS)
    def test_inherits_base_tool(self, tool_cls):
        assert issubclass(tool_cls, BaseTool)

    @pytest.mark.parametrize("tool_cls", PHASE2_TOOLS)
    def test_has_required_identity(self, tool_cls):
        tool = tool_cls()
        assert tool.name
        assert tool.version
        assert tool.tier in ToolTier
        assert len(tool.capabilities) > 0

    @pytest.mark.parametrize("tool_cls", PHASE2_TOOLS)
    def test_get_info_returns_valid_dict(self, tool_cls):
        tool = tool_cls()
        info = tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == tool.name
        assert info["status"] in ["available", "unavailable", "degraded"]

    @pytest.mark.parametrize("tool_cls", PHASE2_TOOLS)
    def test_execute_is_implemented(self, tool_cls):
        tool = tool_cls()
        assert callable(tool.execute)

    @pytest.mark.parametrize("tool_cls", PHASE2_TOOLS)
    def test_dry_run_returns_dict(self, tool_cls):
        tool = tool_cls()
        result = tool.dry_run({})
        assert isinstance(result, dict)
        assert result["tool"] == tool.name


# ---- Contract: unique names, all CORE tier ----

class TestPhase2ToolNames:
    def test_unique_names(self):
        names = [cls().name for cls in PHASE2_TOOLS]
        assert len(names) == len(set(names))

    def test_expected_names(self):
        names = {cls().name for cls in PHASE2_TOOLS}
        expected = {
            "face_enhance", "scene_detect", "color_grade", "audio_enhance",
            "image_selector", "code_snippet", "diagram_gen",
        }
        assert names == expected

    def test_expected_tiers(self):
        for cls in PHASE2_TOOLS:
            tool = cls()
            if tool.name == "image_selector":
                assert tool.tier == ToolTier.GENERATE
            else:
                assert tool.tier == ToolTier.CORE, f"{tool.name} should be CORE"


# ---- Contract: discoverable via registry ----

class TestPhase2ToolDiscovery:
    def test_all_phase2_tools_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        for cls in PHASE2_TOOLS:
            name = cls().name
            assert reg.get(name) is not None, f"{name} not discovered"


# ---- Contract: presets/profiles are well-formed ----

class TestPresets:
    def test_face_presets_have_vf(self):
        for name, preset in FACE_PRESETS.items():
            assert "vf" in preset, f"Face preset {name} missing 'vf'"
            assert "description" in preset

    def test_color_profiles_have_vf(self):
        for name, profile in COLOR_PROFILES.items():
            assert "vf" in profile, f"Color profile {name} missing 'vf'"
            assert "description" in profile

    def test_audio_presets_have_af(self):
        for name, preset in AUDIO_PRESETS.items():
            assert "af" in preset, f"Audio preset {name} missing 'af'"
            assert "description" in preset

    def test_code_themes_have_required_fields(self):
        for name, theme in CODE_THEMES.items():
            assert "pygments_style" in theme
            assert "bg_color" in theme
            assert "text_color" in theme

    def test_face_list_presets(self):
        presets = FaceEnhance.list_presets()
        assert len(presets) >= 8
        assert "talking_head_standard" in presets

    def test_color_list_profiles(self):
        profiles = ColorGrade.list_profiles()
        assert len(profiles) >= 7
        assert "cinematic_warm" in profiles

    def test_audio_list_presets(self):
        presets = AudioEnhance.list_presets()
        assert len(presets) >= 5
        assert "clean_speech" in presets


# ---- Contract: error handling for missing inputs ----

class TestPhase2ErrorHandling:
    def test_face_enhance_missing_file(self):
        tool = FaceEnhance()
        r = tool.execute({"input_path": "/nonexistent.mp4"})
        assert not r.success

    def test_scene_detect_missing_file(self):
        tool = SceneDetect()
        r = tool.execute({"input_path": "/nonexistent.mp4"})
        assert not r.success

    def test_color_grade_missing_file(self):
        tool = ColorGrade()
        r = tool.execute({"input_path": "/nonexistent.mp4"})
        assert not r.success

    def test_audio_enhance_missing_file(self):
        tool = AudioEnhance()
        r = tool.execute({"input_path": "/nonexistent.mp4"})
        assert not r.success

    def test_image_selector_no_provider(self):
        tool = ImageSelector()
        # Will fail if no API key or local model
        r = tool.execute({"prompt": "test"})
        # Either succeeds (provider available) or fails gracefully
        assert isinstance(r, ToolResult)

    def test_diagram_gen_empty_boxes(self):
        tool = DiagramGen()
        if tool.get_status() == ToolStatus.AVAILABLE:
            r = tool.execute({"diagram_type": "boxes", "boxes": []})
            assert isinstance(r, ToolResult)


# ---- Contract: code_snippet renders valid images ----

class TestCodeSnippetUnit:
    @pytest.fixture
    def has_deps(self):
        tool = CodeSnippet()
        if tool.get_status() != ToolStatus.AVAILABLE:
            pytest.skip("Pygments/Pillow not installed")

    def test_render_python(self, has_deps, tmp_path):
        tool = CodeSnippet()
        r = tool.execute({
            "code": "def hello():\n    print('Hello, world!')\n",
            "language": "python",
            "theme": "monokai",
            "output_path": str(tmp_path / "test.png"),
        })
        assert r.success
        assert Path(r.data["output"]).exists()
        assert r.data["line_count"] == 3

    def test_render_with_title(self, has_deps, tmp_path):
        tool = CodeSnippet()
        r = tool.execute({
            "code": "console.log('test');",
            "language": "javascript",
            "theme": "dracula",
            "title": "example.js",
            "output_path": str(tmp_path / "titled.png"),
        })
        assert r.success

    def test_render_different_themes(self, has_deps, tmp_path):
        tool = CodeSnippet()
        for theme_name in ["monokai", "github_dark", "light"]:
            r = tool.execute({
                "code": "x = 42",
                "language": "python",
                "theme": theme_name,
                "output_path": str(tmp_path / f"{theme_name}.png"),
            })
            assert r.success, f"Theme {theme_name} failed"


# ---- Contract: diagram_gen renders valid images ----

class TestDiagramGenUnit:
    @pytest.fixture
    def has_deps(self):
        tool = DiagramGen()
        if tool.get_status() != ToolStatus.AVAILABLE:
            pytest.skip("No diagram renderer available")

    def test_render_box_diagram(self, has_deps, tmp_path):
        tool = DiagramGen()
        r = tool.execute({
            "diagram_type": "boxes",
            "title": "Test Flow",
            "boxes": [
                {"label": "Input", "color": "#2563eb"},
                {"label": "Process", "color": "#7c3aed"},
                {"label": "Output", "color": "#059669"},
            ],
            "connections": [
                {"from": 0, "to": 1, "label": "data"},
                {"from": 1, "to": 2, "label": "result"},
            ],
            "theme": "dark",
            "output_path": str(tmp_path / "boxes.png"),
        })
        assert r.success
        assert Path(r.data["output"]).exists()
        assert r.data["box_count"] == 3

    def test_render_mermaid_fallback(self, has_deps, tmp_path):
        """If mmdc not installed, falls back to text card."""
        tool = DiagramGen()
        r = tool.execute({
            "diagram_type": "mermaid",
            "definition": "graph TD\n  A[Start] --> B[End]",
            "output_path": str(tmp_path / "mermaid.png"),
        })
        assert r.success
