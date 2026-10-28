from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.video.auto_reframe import AutoReframe


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class AutoReframeExplicitSizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.make_video("source.mp4", "48x64")
        self.tracking = self.root / "tracking.json"
        self.tracking.write_text('{"faces": []}')

    def make_video(self, name, size):
        path = self.root / name
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            f"testsrc2=size={size}:rate=10:duration=1", "-f", "lavfi", "-i",
            "sine=frequency=440:duration=1", "-c:v", "libx264", "-c:a", "aac",
            "-shortest", str(path),
        ], check=True, capture_output=True)
        return path

    def assert_render(self, width, height, output=None):
        args = {
            "input_path": str(self.source), "target_width": width,
            "target_height": height, "face_tracking_json": str(self.tracking),
        }
        if output is not None:
            args["output_path"] = str(output)
        result = AutoReframe().execute(args)
        self.assertTrue(result.success, result.error)
        actual = Path(result.data["output"])
        self.assertNotEqual(actual, self.source)
        self.assertTrue(actual.is_file())
        if output is not None:
            self.assertEqual(actual, output)
        info = json.loads(subprocess.run([
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(actual),
        ], check=True, text=True, capture_output=True).stdout)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        self.assertEqual((video["width"], video["height"]), (width, height))
        self.assertTrue(any(s["codec_type"] == "audio" for s in info["streams"]))
        self.assertEqual(result.artifacts, [str(actual)])

    def test_same_aspect_upscale_creates_requested_output(self):
        self.assert_render(96, 128, self.root / "upscaled.mp4")

    def test_same_aspect_downscale_creates_requested_output(self):
        self.assert_render(24, 32, self.root / "downscaled.mp4")

    def test_same_aspect_resize_uses_default_output_filename(self):
        self.assert_render(96, 128)

    def test_exact_explicit_resolution_keeps_passthrough(self):
        result = AutoReframe().execute({
            "input_path": str(self.source), "target_width": 48, "target_height": 64,
        })
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data["output"], str(self.source))

    def test_matching_preset_without_explicit_size_keeps_passthrough(self):
        portrait = self.make_video("portrait.mp4", "36x64")
        result = AutoReframe().execute({"input_path": str(portrait)})
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data["output"], str(portrait))

    def test_different_aspect_still_crops_and_scales(self):
        self.assert_render(32, 32, self.root / "square.mp4")


if __name__ == "__main__":
    unittest.main()
