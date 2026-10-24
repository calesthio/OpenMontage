from lib.source_media_review import review_source_media
from schemas.artifacts import validate_artifact


def test_empty_source_media_review_artifact_validates() -> None:
    artifact = review_source_media([], {})

    validate_artifact("source_media_review", artifact)

    assert artifact["files"] == []
    assert artifact["summary"] == "No user-supplied media files could be reviewed."
    assert "No source media available — production is fully generated." in artifact["planning_implications"]
