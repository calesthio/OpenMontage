"""Contracts for the category vocabulary used by shipped pipelines."""

from lib.pipeline_loader import load_pipeline


def test_documentary_pipeline_uses_a_schema_supported_category() -> None:
    manifest = load_pipeline("documentary-montage")

    assert manifest["category"] == "documentary"
