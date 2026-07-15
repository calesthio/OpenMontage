"""Every pipeline manifest must load through the schema-validating loader.

Audit finding BUG-3 (2026-07-15): documentary-montage and screen-demo shipped
with schema violations and were dead-on-arrival at load_pipeline() — nothing
exercised the loader across the full pipeline_defs/ set.
"""

import pytest

from lib.pipeline_loader import list_pipelines, load_pipeline


@pytest.mark.parametrize("name", list_pipelines())
def test_pipeline_manifest_loads_and_validates(name):
    manifest = load_pipeline(name)
    assert manifest["name"] == name
    assert manifest.get("stages"), f"{name} declares no stages"


@pytest.mark.parametrize("name", list_pipelines())
def test_every_stage_declares_produces(name):
    # lib/checkpoint.py derives each stage's canonical artifact from the
    # manifest's first `produces` entry — a stage without one silently loses
    # its completed-checkpoint artifact requirement.
    manifest = load_pipeline(name)
    for stage in manifest["stages"]:
        assert stage.get("produces"), (
            f"{name}:{stage.get('name')} has no `produces` — checkpoint "
            f"artifact validation cannot derive its canonical artifact"
        )
