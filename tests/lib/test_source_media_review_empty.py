"""Regression test for source_media_review empty-files artifact validity.

review_source_media deliberately returns an artifact with files:[] when no user
media was supplied (or none could be reviewed) — a valid "fully generated
production" state. The schema declared files.minItems: 1, so that intended
artifact failed its own schema validation.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.source_media_review import review_source_media  # noqa: E402
from schemas.artifacts import validate_artifact  # noqa: E402


def test_no_source_media_produces_schema_valid_artifact(tmp_path):
    art = review_source_media([tmp_path / "does-not-exist.mp4"], {})
    assert art["files"] == []
    # Must not raise — this is a legitimate no-source-media artifact.
    validate_artifact("source_media_review", art)


def test_no_files_at_all_is_schema_valid():
    art = review_source_media([], {})
    assert art["files"] == []
    validate_artifact("source_media_review", art)
