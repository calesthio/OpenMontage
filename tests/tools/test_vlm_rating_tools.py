"""Tests for the VLM clip rating tools.

All Ollama HTTP calls are mocked so the suite runs with no model, no
network, and no GPU. Frame extraction uses tiny synthetic videos generated
with ffmpeg (color bars), so the tools exercise their real code paths.

Covered tools: vlm_clip_rating, vlm_zoom_rating, vlm_editorial_ranking,
vlm_comparative_rank.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.base_tool import ToolResult, ToolStatus  # noqa: E402
from tools.tool_registry import ToolRegistry  # noqa: E402
from tools.video.vlm_clip_rating import VlmClipRating  # noqa: E402
from tools.video.vlm_comparative_rank import VlmComparativeRank  # noqa: E402
from tools.video.vlm_editorial_ranking import VlmEditorialRanking  # noqa: E402
from tools.video.vlm_zoom_rating import VlmZoomRating  # noqa: E402


def make_test_video(path: Path, seconds: float = 2.0) -> None:
    """Generate a tiny synthetic video (color bars + tone) with ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi",
            "-i", f"testsrc=duration={seconds}:size=320x180:rate=10",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def fake_ollama_response(raw: str) -> str:
    """Wrap a raw model response in the Ollama /api/generate envelope."""
    return json.dumps({"model": "test", "response": raw, "done": True})


def mock_generate(monkeypatch_response: str):
    """Patch ollama_generate to return monkeypatch_response."""
    return patch(
        "tools.video.vlm_clip_rating.ollama_generate",
        return_value=monkeypatch_response,
    )


class VlmClipRatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.td = Path(self.tmp.name)
        self.clips = self.td / "clips"
        self.clips.mkdir()
        self.video = self.clips / "test_a.mp4"
        make_test_video(self.video)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_rates_video_and_writes_jsonl(self) -> None:
        out = self.td / "tags.jsonl"
        tool = VlmClipRating()
        raw = json.dumps({
            "overall": {"behavior": "walking_calm", "energy": "calm"},
            "camera": {"stability_score": 0.95},
            "shot": {"type": "medium", "rule_of_thirds_score": 0.8},
            "product": {"subject_visibility": "clear", "subject_quality_score": 0.9},
            "segments": [],
            "highlights": [],
            "quality": {"overall_score": 0.9},
            "notes": "test clip",
        })
        with mock_generate(raw):
            result = tool.execute({
                "input_dir": str(self.clips),
                "output_path": str(out),
            })
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data["rated"], 1)
        records = [json.loads(l) for l in out.read_text().splitlines()]
        self.assertEqual(records[0]["clip"], "test_a.mp4")
        self.assertEqual(records[0]["overall"]["behavior"], "walking_calm")

    def test_resume_skips_rated_clips(self) -> None:
        out = self.td / "tags.jsonl"
        out.write_text(json.dumps({"clip": "test_a.mp4", "done": True}) + "\n")
        tool = VlmClipRating()
        with mock_generate("{}"):
            result = tool.execute({
                "input_dir": str(self.clips),
                "output_path": str(out),
            })
        self.assertTrue(result.success)
        self.assertEqual(result.data["rated"], 0)
        self.assertEqual(result.data["skipped_existing"], 1)

    def test_missing_dir_returns_error(self) -> None:
        tool = VlmClipRating()
        result = tool.execute({
            "input_dir": "/nonexistent",
            "output_path": "/tmp/x.jsonl",
        })
        self.assertFalse(result.success)

    def test_records_failed_clip_without_crashing(self) -> None:
        # Simulate Ollama failure: patch to raise.
        out = self.td / "tags.jsonl"
        tool = VlmClipRating()
        with patch(
            "tools.video.vlm_clip_rating.ollama_generate",
            side_effect=RuntimeError("ollama down"),
        ):
            result = tool.execute({
                "input_dir": str(self.clips),
                "output_path": str(out),
            })
        self.assertTrue(result.success)
        self.assertEqual(result.data["failed"], 1)
        records = [json.loads(l) for l in out.read_text().splitlines()]
        self.assertIn("error", records[0])

    def test_failed_clip_is_retried_on_next_run(self) -> None:
        out = self.td / "tags.jsonl"
        tool = VlmClipRating()
        with patch(
            "tools.video.vlm_clip_rating.ollama_generate",
            side_effect=RuntimeError("temporary outage"),
        ):
            first = tool.execute({
                "input_dir": str(self.clips),
                "output_path": str(out),
            })

        with mock_generate(json.dumps({"quality": {"overall_score": 0.8}})):
            second = tool.execute({
                "input_dir": str(self.clips),
                "output_path": str(out),
            })

        self.assertEqual(first.data["failed"], 1)
        self.assertEqual(second.data["rated"], 1)
        self.assertEqual(second.data["skipped_existing"], 0)
        records = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertIn("error", records[0])
        self.assertNotIn("error", records[1])

    def test_dependency_check_requires_ffmpeg_and_ollama_model(self) -> None:
        tool = VlmClipRating()
        with patch("shutil.which", return_value="/usr/bin/tool"), patch(
            "tools.video.vlm_clip_rating.ollama_model_available", return_value=True
        ):
            self.assertEqual(tool.get_status(), ToolStatus.AVAILABLE)
        with patch("shutil.which", return_value="/usr/bin/tool"), patch(
            "tools.video.vlm_clip_rating.ollama_model_available", return_value=False
        ):
            self.assertEqual(tool.get_status(), ToolStatus.UNAVAILABLE)

    def test_rejects_remote_ollama_endpoint(self) -> None:
        result = VlmClipRating().execute({
            "input_dir": str(self.clips),
            "output_path": str(self.td / "tags.jsonl"),
            "ollama_url": "https://remote.example.com",
        })
        self.assertFalse(result.success)
        self.assertIn("loopback", result.error or "")


class VlmZoomRatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.td = Path(self.tmp.name)
        self.video = self.td / "clip.mp4"
        make_test_video(self.video, 3.0)
        self.ratings = self.td / "tags.jsonl"
        self.ratings.write_text(json.dumps({
            "clip": "clip.mp4",
            "file": str(self.video),
            "duration_s": 3.0,
            "highlights": [{"start_s": 0.0, "end_s": 2.0, "type": "action"}],
            "segments": [],
        }) + "\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_zoom_produces_sub_beats(self) -> None:
        out = self.td / "zooms.jsonl"
        tool = VlmZoomRating()
        raw = json.dumps({
            "sub_beats": [{
                "start_s": 0.0,
                "end_s": 1.2,
                "action": "subject moves",
                "deep_dive": "detailed description",
                "behavior": "trotting",
                "camera_angle": "eye_level",
                "subject_facing": "left",
                "quality_score": 0.9,
                "vibe": "calm",
                "use": "b-roll",
            }],
            "best_moment_s": 0.5,
            "best_moment_desc": "the moment",
            "notes": "ok",
        })
        with patch("tools.video.vlm_zoom_rating.ollama_generate", return_value=raw):
            result = tool.execute({
                "ratings_path": str(self.ratings),
                "output_path": str(out),
            })
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data["zoomed"], 1)
        rec = json.loads(out.read_text().splitlines()[0])
        self.assertEqual(rec["zooms"][0]["sub_beats"][0]["behavior"], "trotting")

    def test_missing_ratings_returns_error(self) -> None:
        tool = VlmZoomRating()
        result = tool.execute({
            "ratings_path": "/nonexistent.jsonl",
            "output_path": "/tmp/x.jsonl",
        })
        self.assertFalse(result.success)

    def test_all_failed_windows_are_retried(self) -> None:
        out = self.td / "zooms.jsonl"
        tool = VlmZoomRating()
        with patch(
            "tools.video.vlm_zoom_rating.ollama_generate",
            side_effect=RuntimeError("temporary outage"),
        ):
            first = tool.execute({
                "ratings_path": str(self.ratings),
                "output_path": str(out),
            })

        with patch(
            "tools.video.vlm_zoom_rating.ollama_generate",
            return_value=json.dumps({"sub_beats": [], "notes": "recovered"}),
        ):
            second = tool.execute({
                "ratings_path": str(self.ratings),
                "output_path": str(out),
            })

        self.assertEqual(first.data["failed"], 1)
        self.assertEqual(second.data["zoomed"], 1)
        records = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(records[0]["error"], "all_windows_failed")
        self.assertNotIn("error", records[1])


class VlmRegistryTests(unittest.TestCase):
    def test_all_tools_are_discoverable_with_honest_status(self) -> None:
        registry = ToolRegistry()
        registry.discover("tools")
        names = {
            "vlm_clip_rating",
            "vlm_zoom_rating",
            "vlm_editorial_ranking",
            "vlm_comparative_rank",
        }
        self.assertTrue(names <= set(registry.list_all()))
        self.assertEqual(
            registry.get("vlm_editorial_ranking").get_status(),
            ToolStatus.AVAILABLE,
        )
        with patch("shutil.which", return_value="/usr/bin/tool"), patch(
            "tools.video.vlm_clip_rating.ollama_model_available", return_value=False
        ), patch(
            "tools.video.vlm_zoom_rating.ollama_model_available", return_value=False
        ), patch(
            "tools.video.vlm_comparative_rank.ollama_model_available", return_value=False
        ):
            for name in names - {"vlm_editorial_ranking"}:
                self.assertEqual(registry.get(name).get_status(), ToolStatus.UNAVAILABLE)


class VlmEditorialRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.td = Path(self.tmp.name)
        self.ratings = self.td / "tags.jsonl"
        rows = [
            {
                "clip": "a.mp4", "file": "/tmp/a.mp4", "duration_s": 5.0,
                "overall": {"behavior": "walking_calm", "energy": "calm"},
                "camera": {"stability_score": 0.9},
                "shot": {"type": "medium", "rule_of_thirds_score": 0.7},
                "product": {"subject_visibility": "featured", "subject_quality_score": 0.9},
                "quality": {"overall_score": 0.8},
                "highlights": [], "segments": [],
            },
            {
                "clip": "b.mp4", "file": "/tmp/b.mp4", "duration_s": 5.0,
                "overall": {"behavior": "sitting", "energy": "neutral"},
                "camera": {"stability_score": 0.5},
                "shot": {"type": "wide", "rule_of_thirds_score": 0.4},
                "product": {"subject_visibility": "not_visible", "subject_quality_score": 0.1},
                "quality": {"overall_score": 0.5},
                "highlights": [], "segments": [],
            },
        ]
        self.ratings.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_leaderboards_and_composite(self) -> None:
        out = self.td / "rankings.json"
        tool = VlmEditorialRanking()
        result = tool.execute({
            "ratings_path": str(self.ratings),
            "output_path": str(out),
        })
        self.assertTrue(result.success, result.error)
        data = json.loads(out.read_text())
        self.assertEqual(data["n_clips"], 2)
        # a.mp4 has featured subject + high stability -> should top overall
        self.assertEqual(data["all_rows"][0]["clip"], "a.mp4")
        self.assertGreater(
            data["all_rows"][0]["composite"], data["all_rows"][1]["composite"]
        )

    def test_invalid_weights_rejected(self) -> None:
        tool = VlmEditorialRanking()
        result = tool.execute({
            "ratings_path": str(self.ratings),
            "output_path": str(self.td / "r.json"),
            "weights": {"stability": 0.9},
        })
        self.assertFalse(result.success)
        self.assertIn("sum to 1.0", result.error or "")

    def test_missing_ratings_returns_error(self) -> None:
        tool = VlmEditorialRanking()
        result = tool.execute({
            "ratings_path": "/nonexistent.jsonl",
            "output_path": "/tmp/x.json",
        })
        self.assertFalse(result.success)


class VlmComparativeRankTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.td = Path(self.tmp.name)
        # Two tiny videos so candidate paths exist.
        self.v1 = self.td / "a.mp4"
        self.v2 = self.td / "b.mp4"
        make_test_video(self.v1)
        make_test_video(self.v2)
        self.rankings = self.td / "rankings.json"
        self.rankings.write_text(json.dumps({
            "leaderboards": {
                "subject_hero": [
                    {"clip": "a.mp4", "composite": 0.9},
                    {"clip": "b.mp4", "composite": 0.8},
                ]
            },
            "all_rows": [
                {"clip": "a.mp4", "file": str(self.v1)},
                {"clip": "b.mp4", "file": str(self.v2)},
            ],
        }) + "\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_comparative_rank_writes_batch(self) -> None:
        out = self.td / "cmp.jsonl"
        tool = VlmComparativeRank()
        raw = json.dumps({
            "ranking": ["A", "B"],
            "scores": {"A": 0.9, "B": 0.7},
            "best_clip": "A",
            "best_reason": "clear subject visibility and stable framing",
            "worst_clip": "B",
            "worst_reason": "subject not visible",
            "notes": "A wins",
        })
        with patch("tools.video.vlm_comparative_rank.ollama_generate", return_value=raw):
            result = tool.execute({
                "rankings_path": str(self.rankings),
                "output_path": str(out),
                "purpose": "subject_hero",
                "batch_size": 2,
            })
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.data["batches"], 1)
        rec = json.loads(out.read_text().splitlines()[0])
        self.assertEqual(rec["best_clip"], "A")
        self.assertIn("a.mp4", rec["_clips"].values())

    def test_missing_rankings_returns_error(self) -> None:
        tool = VlmComparativeRank()
        result = tool.execute({
            "rankings_path": "/nonexistent.json",
            "output_path": "/tmp/x.jsonl",
        })
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
