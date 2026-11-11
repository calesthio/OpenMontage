"""`cmd:ffmpeg` on PATH is not the same as "this FFmpeg can do the job".

Found while comparing the failing tests with origin/main (2026-11-11): the
stock Homebrew build has no `drawtext`, no `subtitles` (libass) and no
`libvorbis`. `showcase_card` draws every line of text with `drawtext`, declared
only `cmd:ffmpeg`, reported AVAILABLE, and failed at render time with "Filter
not found". Preflight said nothing.
"""

import pytest

from tools import ffmpeg_capabilities as caps
from tools.base_tool import BaseTool, DependencyError, ToolResult, ToolStatus
from tools.tool_registry import ToolRegistry, registry

FILTERS = """Filters:
  T.. = Timeline support
  .S. = Slice threading
 ... abuffer           |->A       Buffer audio frames.
 T.. drawbox           V->V       Draw a colored box on the input video.
 TSC scale             V->V       Scale the input video size.
"""

ENCODERS = """Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264 / AVC (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)
"""


@pytest.fixture
def minimal_build(monkeypatch):
    """An FFmpeg that has scale/drawbox/libx264/aac and nothing fancier."""
    class Done:
        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        return Done(FILTERS if cmd[-1] == "-filters" else ENCODERS)

    monkeypatch.setattr(caps.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(caps.subprocess, "run", fake_run)
    caps._listing.cache_clear()
    yield
    caps._listing.cache_clear()


def test_listing_parser_reads_names_and_skips_legends(minimal_build):
    assert caps._listing("filters") == {"abuffer", "drawbox", "scale"}
    assert caps._listing("encoders") == {"libx264", "aac"}
    assert caps.has_filter("scale") and not caps.has_filter("drawtext")
    assert caps.has_encoder("libx264") and not caps.has_encoder("libvorbis")


def test_dependency_on_a_missing_filter_or_encoder_makes_a_tool_unavailable(minimal_build):
    class NeedsText(BaseTool):
        name = "needs_text"
        dependencies = ["cmd:ffmpeg", "ffmpeg_filter:drawtext"]

        def execute(self, inputs):
            return ToolResult(success=True)

    class NeedsVorbis(NeedsText):
        name = "needs_vorbis"
        dependencies = ["ffmpeg_encoder:libvorbis"]

    class NeedsScale(NeedsText):
        name = "needs_scale"
        dependencies = ["ffmpeg_filter:scale", "ffmpeg_encoder:aac"]

    assert NeedsText().get_status() == ToolStatus.UNAVAILABLE
    assert NeedsVorbis().get_status() == ToolStatus.UNAVAILABLE
    assert NeedsScale().get_status() == ToolStatus.AVAILABLE
    with pytest.raises(DependencyError, match="drawtext"):
        NeedsText().check_dependencies()


def test_preflight_warns_about_what_the_build_cannot_do(minimal_build):
    warnings = caps.capability_warnings()
    joined = "\n".join(warnings)
    for feature in ("drawtext", "subtitles", "libvorbis"):
        assert f"`{feature}`" in joined
    assert "remotion_caption_burn" in joined           # says what to use instead
    assert warnings[-1].startswith("ffmpeg: Install an FFmpeg build")

    reg = ToolRegistry()
    reg._discovered_packages.add("tools")
    assert any("drawtext" in w for w in reg.provider_menu_summary(compact=True)["runtime_warnings"])


def test_a_full_build_and_a_missing_binary_produce_no_warnings(monkeypatch):
    monkeypatch.setattr(caps, "has_feature", lambda kind, name: True)
    monkeypatch.setattr(caps, "_listing", lambda kind: frozenset({"scale"}))
    monkeypatch.setattr(caps.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert caps.capability_warnings() == []
    monkeypatch.setattr(caps.shutil, "which", lambda name: None)
    assert caps.capability_warnings() == []


def test_showcase_card_declares_the_filter_it_cannot_work_without():
    registry.discover()
    tool = registry.get("showcase_card")
    assert "ffmpeg_filter:drawtext" in tool.dependencies
    expected = ToolStatus.AVAILABLE if caps.has_filter("drawtext") else ToolStatus.UNAVAILABLE
    assert tool.get_status() == expected
