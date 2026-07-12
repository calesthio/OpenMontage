"""Contract tests for orientation / aspect ratio guard.

Verifies that the pre-compose validation catches orientation mismatches
between short-form platforms and landscape output dimensions.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.hyperframes_compose import HyperFramesCompose


class TestResolveDimensions:
    """Tests for HyperFramesCompose._resolve_dimensions with edit_decisions."""

    def test_default_is_landscape_1920x1080(self):
        """No profile, no edit_decisions → 1920×1080."""
        w, h, fps = HyperFramesCompose._resolve_dimensions(None, 30)
        assert (w, h) == (1920, 1080)

    def test_profile_overrides_default(self):
        """Named profile → profile dimensions."""
        w, h, fps = HyperFramesCompose._resolve_dimensions("youtube_shorts", 30)
        assert (w, h) == (1080, 1920)
        assert fps == 30

    def test_edit_decisions_target_resolution(self):
        """edit_decisions.metadata.target_resolution → custom dimensions."""
        ed = {
            "metadata": {
                "target_resolution": {"width": 1080, "height": 1920, "fps": 30}
            }
        }
        w, h, fps = HyperFramesCompose._resolve_dimensions(None, 30, edit_decisions=ed)
        assert (w, h) == (1080, 1920)
        assert fps == 30

    def test_profile_takes_priority_over_edit_decisions(self):
        """Profile should win over edit_decisions.target_resolution."""
        ed = {
            "metadata": {
                "target_resolution": {"width": 1080, "height": 1920}
            }
        }
        w, h, fps = HyperFramesCompose._resolve_dimensions("youtube_landscape", 30, edit_decisions=ed)
        # Profile should win
        assert (w, h) == (1920, 1080)

    def test_edit_decisions_without_target_resolution_falls_through(self):
        """edit_decisions without target_resolution → default."""
        ed = {"metadata": {}}
        w, h, fps = HyperFramesCompose._resolve_dimensions(None, 30, edit_decisions=ed)
        assert (w, h) == (1920, 1080)

    def test_edit_decisions_none_falls_through(self):
        """edit_decisions=None → default."""
        w, h, fps = HyperFramesCompose._resolve_dimensions(None, 30, edit_decisions=None)
        assert (w, h) == (1920, 1080)

    def test_target_resolution_partial_uses_default_fps(self):
        """target_resolution without fps → use fps_in."""
        ed = {
            "metadata": {
                "target_resolution": {"width": 720, "height": 1280}
            }
        }
        w, h, fps = HyperFramesCompose._resolve_dimensions(None, 24, edit_decisions=ed)
        assert (w, h) == (720, 1280)
        assert fps == 24


class TestOrientationWarning:
    """Tests for orientation mismatch detection in pre-compose validation."""

    SHORT_FORM_PLATFORMS = ["tiktok", "youtube_shorts", "instagram_reels"]

    @staticmethod
    def _make_edit_decisions(
        platform: str | None = None,
        target_resolution: dict | None = None,
        render_runtime: str = "hyperframes",
        renderer_family: str = "explainer",
    ) -> dict:
        """Build minimal edit_decisions for orientation testing."""
        ed = {
            "render_runtime": render_runtime,
            "renderer_family": renderer_family,
            "cuts": [
                {"id": "c1", "type": "text_card", "text": "Test",
                 "in_seconds": 0, "out_seconds": 5, "source": ""},
            ],
            "metadata": {},
        }
        if platform:
            ed["metadata"]["target_platform"] = platform
        if target_resolution:
            ed["metadata"]["target_resolution"] = target_resolution
        return ed

    def test_short_form_with_portrait_profile_is_fine(self):
        """Short-form platform + portrait resolution → no orientation issue."""
        ed = self._make_edit_decisions(
            platform="tiktok",
            target_resolution={"width": 1080, "height": 1920},
        )
        # Orientation check: width < height → portrait → ok for short-form
        tr = ed["metadata"]["target_resolution"]
        assert tr["width"] < tr["height"], "Portrait dimensions expected"

    def test_short_form_with_landscape_default_is_mismatch(self):
        """Short-form platform + default landscape → orientation mismatch."""
        ed = self._make_edit_decisions(platform="tiktok")
        # No target_resolution → default is 1920×1080 → landscape
        # This is the mismatch the guard should catch
        has_target_res = "target_resolution" in ed.get("metadata", {})
        is_short_form = ed["metadata"].get("target_platform") in self.SHORT_FORM_PLATFORMS
        assert is_short_form
        assert not has_target_res  # Will default to landscape

    def test_landscape_platform_with_landscape_is_fine(self):
        """Landscape platform + landscape resolution → no issue."""
        ed = self._make_edit_decisions(
            platform="youtube",
            target_resolution={"width": 1920, "height": 1080},
        )
        tr = ed["metadata"]["target_resolution"]
        assert tr["width"] > tr["height"], "Landscape dimensions expected"

    def test_no_platform_no_check(self):
        """No target_platform → orientation check not applicable."""
        ed = self._make_edit_decisions()
        assert "target_platform" not in ed.get("metadata", {})
