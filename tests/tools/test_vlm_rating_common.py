"""Tests for vlm_rating_common: shared plumbing for the VLM rating family.

Covers: defensive JSON parsing, safe float coercion, drift normalization,
JSONL resume, and prompt building. No network or model needed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.video.vlm_rating_common import (  # noqa: E402
    append_record,
    build_behavior_taxonomy,
    load_rated_ids,
    normalize_drift,
    ollama_model_available,
    parse_vlm_json,
    safe_float,
    validate_local_ollama_url,
)


class ParseVlmJsonTests(unittest.TestCase):
    def test_strict_json_parses(self) -> None:
        raw = '{"behavior": "walking_calm", "confidence": 0.9}'
        result = parse_vlm_json(raw)
        self.assertEqual(result["behavior"], "walking_calm")

    def test_prose_wrapped_json_extracted(self) -> None:
        raw = 'Sure! Here is my analysis:\n{"behavior": "pulling", "ok": true}\nHope that helps.'
        result = parse_vlm_json(raw)
        self.assertEqual(result["behavior"], "pulling")

    def test_malformed_json_returns_error_dict(self) -> None:
        raw = "not json at all {{{"
        result = parse_vlm_json(raw)
        self.assertIn("error", result)
        self.assertIn("raw", result)

    def test_empty_response_returns_error(self) -> None:
        result = parse_vlm_json("")
        self.assertIn("error", result)

    def test_non_dict_json_returns_error(self) -> None:
        result = parse_vlm_json("[1, 2, 3]")
        self.assertIn("error", result)


class SafeFloatTests(unittest.TestCase):
    def test_plain_number(self) -> None:
        self.assertEqual(safe_float(0.75), 0.75)

    def test_numeric_string(self) -> None:
        self.assertEqual(safe_float("0.5"), 0.5)

    def test_garbage_string(self) -> None:
        self.assertEqual(safe_float(": 6.25, "), 0.0)

    def test_none_uses_default(self) -> None:
        self.assertEqual(safe_float(None, 1.0), 1.0)


class NormalizeDriftTests(unittest.TestCase):
    def test_canonical_name_wins(self) -> None:
        rec = {"subject_visibility": "clear"}
        normalize_drift(rec, {"collar_visibility": ["product_visibility"]})
        self.assertEqual(rec["subject_visibility"], "clear")

    def test_alias_folded_to_canonical(self) -> None:
        rec = {"product_visibility": "featured"}
        normalize_drift(rec, {"collar_visibility": ["product_visibility"]})
        self.assertIn("collar_visibility", rec)
        self.assertEqual(rec["collar_visibility"], "featured")

    def test_first_present_alias_used(self) -> None:
        rec = {"purpose": "lifestyle"}
        normalize_drift(rec, {"shot_purpose": ["purpose", "intent"]})
        self.assertEqual(rec["shot_purpose"], "lifestyle")


class JsonlIOTests(unittest.TestCase):
    def test_append_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "out.jsonl")
            append_record(path, {"clip": "a.mp4", "behavior": "walking"})
            append_record(path, {"clip": "b.mp4", "behavior": "sitting"})
            rated = load_rated_ids(path)
            self.assertEqual(rated, {"a.mp4", "b.mp4"})

    def test_load_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(load_rated_ids(str(Path(td) / "nope.jsonl")), set())

    def test_load_skips_bad_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.jsonl"
            path.write_text('{"clip": "a.mp4"}\nnot-json\n{"clip": "b.mp4"}\n')
            self.assertEqual(load_rated_ids(str(path)), {"a.mp4", "b.mp4"})

    def test_load_does_not_mark_error_records_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.jsonl"
            path.write_text(
                '{"clip": "retry.mp4", "error": "ollama down"}\n'
                '{"clip": "done.mp4", "quality": {"overall_score": 0.8}}\n'
            )
            self.assertEqual(load_rated_ids(str(path)), {"done.mp4"})


class OllamaRuntimeTests(unittest.TestCase):
    def test_local_url_validation_accepts_loopback(self) -> None:
        self.assertEqual(
            validate_local_ollama_url("http://localhost:11434/"),
            "http://localhost:11434",
        )
        self.assertEqual(
            validate_local_ollama_url("http://[::1]:11434"),
            "http://[::1]:11434",
        )

    def test_local_url_validation_rejects_remote_hosts(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            validate_local_ollama_url("https://ollama.example.com")

    def test_model_status_checks_installed_tags(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"models": [{"name": "gemma4:12b"}]}'

        with patch("urllib.request.urlopen", return_value=Response()):
            self.assertTrue(ollama_model_available(model="gemma4:12b"))
            self.assertFalse(ollama_model_available(model="missing:1b"))


class BehaviorTaxonomyTests(unittest.TestCase):
    def test_default_taxonomy(self) -> None:
        tax = build_behavior_taxonomy()
        self.assertIn("walking_calm", tax)
        self.assertIn("other", tax)

    def test_custom_labels_appended(self) -> None:
        tax = build_behavior_taxonomy("chasing,drinking")
        self.assertIn("chasing", tax)
        self.assertIn("drinking", tax)
        self.assertIn("walking_calm", tax)


if __name__ == "__main__":
    unittest.main()
