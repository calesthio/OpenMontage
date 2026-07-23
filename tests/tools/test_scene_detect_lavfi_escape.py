from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.analysis.scene_detect import SceneDetect


class SceneDetectEscapingTests(unittest.TestCase):
    def test_lavfi_movie_path_escapes_filtergraph_metacharacters(self) -> None:
        raw = "/tmp/clip-name,with[bad];chars:01.mov"

        escaped = SceneDetect._escape_lavfi_movie_path(raw)

        self.assertIn("\\,", escaped)
        self.assertIn("\\[", escaped)
        self.assertIn("\\]", escaped)
        self.assertIn("\\;", escaped)
        self.assertIn("\\:", escaped)
        self.assertNotIn("clip-name,with[bad];chars:01", escaped)

    def test_lavfi_movie_path_rejects_single_quote_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "single quotes"):
            SceneDetect._escape_lavfi_movie_path("/tmp/clip'name.mov")


if __name__ == "__main__":
    unittest.main()
