from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.analysis.frame_sampler import FrameSampler


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class FrameSamplerCurrentRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / "source.mp4"
        subprocess.run([
            "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
            "testsrc2=size=32x32:rate=10:duration=2", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", str(self.video),
        ], check=True, capture_output=True)
        self.frames = self.root / "frames"
        self.tool = FrameSampler()

    def sample(self, strategy, **kwargs):
        result = self.tool.execute({
            "input_path": str(self.video), "output_dir": str(self.frames),
            "strategy": strategy, "format": "png", **kwargs,
        })
        self.assertTrue(result.success, result.error)
        for frame in result.data["frames"]:
            image = Path(frame["path"])
            self.assertEqual(image.parent, self.frames)
            self.assertTrue(image.is_file())
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                "-of", "json", str(image),
            ], check=True, capture_output=True, text=True)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual((stream["width"], stream["height"]), (32, 32))
        self.assertEqual(list(self.frames.glob(".frame-sampler-*")), [])
        return result.data

    def test_count_rerun_returns_only_requested_frames(self):
        self.assertEqual(self.sample("count", count=3)["frame_count"], 3)
        self.assertEqual(self.sample("count", count=1)["frame_count"], 1)

    def test_interval_rerun_does_not_collect_old_frames(self):
        self.assertEqual(self.sample("interval", interval_seconds=0.5)["frame_count"], 4)
        self.assertEqual(self.sample("interval", interval_seconds=2)["frame_count"], 1)

    def test_timestamp_beyond_end_cannot_relabel_an_old_frame(self):
        self.assertEqual(self.sample("timestamps", timestamps=[0])["frame_count"], 1)
        self.assertEqual(self.sample("timestamps", timestamps=[5])["frames"], [])

    def test_scene_guided_beyond_end_cannot_relabel_an_old_frame(self):
        self.assertEqual(self.sample("scene_guided", scene_boundaries=[
            {"start_seconds": 0, "end_seconds": 1},
        ])["frame_count"], 1)
        self.assertEqual(self.sample("scene_guided", scene_boundaries=[
            {"start_seconds": 5, "end_seconds": 6},
        ])["frames"], [])

    def test_preexisting_files_are_not_reported_or_deleted(self):
        self.frames.mkdir()
        sentinel = self.frames / "frame_9999.png"
        sentinel.write_bytes(b"user-owned file")
        result = self.sample("count", count=1)
        self.assertEqual(result["frame_count"], 1)
        self.assertEqual(sentinel.read_bytes(), b"user-owned file")

    def test_timestamp_metadata_and_empty_request_are_preserved(self):
        result = self.sample("timestamps", timestamps=[0.2, 1.2])
        self.assertEqual([f["timestamp_seconds"] for f in result["frames"]], [0.2, 1.2])
        self.assertEqual([f["index"] for f in result["frames"]], [0, 1])
        self.assertEqual(self.sample("timestamps", timestamps=[])["frames"], [])

    def test_failed_extraction_cleans_scratch_without_deleting_existing_files(self):
        self.frames.mkdir()
        sentinel = self.frames / "notes.txt"
        sentinel.write_text("keep")
        invalid = self.root / "invalid.mp4"
        invalid.write_bytes(b"not a video")
        result = self.tool.execute({
            "input_path": str(invalid), "output_dir": str(self.frames),
            "strategy": "timestamps", "timestamps": [0],
        })
        self.assertFalse(result.success)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual(list(self.frames.glob(".frame-sampler-*")), [])


if __name__ == "__main__":
    unittest.main()
