"""Phase 1 golden scenario test — validates the talking-head pipeline
manifest and skill architecture are in place.

The old test ran the Python orchestrator pipeline end-to-end. That layer
has been removed in favor of instruction-driven architecture: the agent
reads pipeline manifests + stage director skills and drives the pipeline
itself.  These tests verify the infrastructure is correctly wired.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_loader import (  # noqa: E402
    load_pipeline,
    get_stage_order,
    list_pipelines,
)


class TestTalkingHeadManifest:
    """Verify the talking-head pipeline manifest is well-formed."""

    def test_manifest_loads(self):
        manifest = load_pipeline("talking-head")
        assert manifest["name"] == "talking-head"

    def test_all_stages_present(self):
        manifest = load_pipeline("talking-head")
        stage_names = get_stage_order(manifest)
        expected = ["idea", "script", "scene_plan", "assets", "edit", "compose", "publish"]
        assert stage_names == expected

    def test_manifest_listed(self):
        assert "talking-head" in list_pipelines()


class TestGoldenScenarioArtifacts:
    """Validate golden scenario artifact samples against schemas."""

    GOLDEN_PATH = PROJECT_ROOT / "eval" / "golden_scenarios" / "talking_head_basic.json"

    @pytest.fixture
    def golden(self):
        if not self.GOLDEN_PATH.exists():
            pytest.skip("Golden scenario file not found")
        return json.loads(self.GOLDEN_PATH.read_text())

    def test_golden_file_structure(self, golden):
        assert "inputs" in golden
        assert "expected_artifacts" in golden
