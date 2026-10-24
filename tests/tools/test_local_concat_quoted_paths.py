from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.video.silence_cutter import SilenceCutter
from tools.video.video_stitch import VideoStitch


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class LocalConcatQuotedPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            "testsrc2=size=32x32:rate=20:duration=4", "-f", "lavfi", "-i",
            "aevalsrc=if(between(t\\,1\\,3)\\,0\\,0.3*sin(2*PI*440*t)):s=48000:d=4",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(self.source),
        ], check=True, capture_output=True)

    def assert_output(self, result, path, expected_duration):
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data["output"], str(path))
        self.assertTrue(path.is_file())
        info = json.loads(subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
            "-of", "json", str(path),
        ], check=True, capture_output=True, text=True).stdout)
        self.assertEqual({s["codec_type"] for s in info["streams"]}, {"video", "audio"})
        self.assertAlmostEqual(float(info["format"]["duration"]), expected_duration, delta=0.2)

    def cut(self, directory, mode="remove"):
        output = self.root / directory / "output.mp4"
        result = SilenceCutter().execute({
            "input_path": str(self.source), "output_path": str(output),
            "mode": mode, "padding_seconds": 0, "silence_speed_factor": 2,
        })
        self.assert_output(result, output, 2 if mode == "remove" else 3)

    def stitch(self, directory, normalize=False):
        folder = self.root / directory
        folder.mkdir()
        clip = folder / "speaker's clip.mp4" if "'" in directory else folder / "clip.mp4"
        shutil.copyfile(self.source, clip)
        output = folder / "joined.mp4"
        result = VideoStitch().execute({
            "operation": "stitch", "clips": [str(clip), str(clip)],
            "output_path": str(output), "transition": "cut",
            "auto_normalize": normalize, "target_resolution": "32x32", "target_fps": 20,
        })
        self.assert_output(result, output, 8)

    def test_remove_silence_in_apostrophe_output_directory(self):
        self.cut("Rudy's edits")

    def test_speed_up_silence_in_apostrophe_output_directory(self):
        self.cut("Rudy's edits", "speed_up")

    def test_stitch_apostrophe_input_paths(self):
        self.stitch("Rudy's clips")

    def test_stitch_normalized_clips_in_apostrophe_output_directory(self):
        self.stitch("Rudy's clips", normalize=True)

    def test_remove_silence_preserves_spaces_and_filter_characters(self):
        self.cut("edits #1 [draft]")

    def test_stitch_plain_paths_still_works(self):
        self.stitch("plain clips")


if __name__ == "__main__":
    unittest.main()
