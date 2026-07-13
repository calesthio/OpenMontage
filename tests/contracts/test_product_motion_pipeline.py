"""Contract tests for the product-motion pipeline.

Covers: manifest validity against the pipeline schema, skill-file existence,
produces/artifact-name integrity, checkpoint wiring for the new repo_analysis
stage, golden + invalid fixtures for the design_system and ui_inventory
artifacts, and the asset_manifest provenance extension.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.checkpoint import (
    ALL_KNOWN_STAGES,
    CANONICAL_STAGE_ARTIFACTS,
    SUPPLEMENTARY_ARTIFACTS,
    CheckpointValidationError,
    write_checkpoint,
)
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact

MANIFEST_PATH = ROOT / "pipeline_defs" / "product-motion.yaml"
SCHEMA_PATH = ROOT / "schemas" / "pipelines" / "pipeline_manifest.schema.json"


@pytest.fixture(scope="module")
def manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---- Golden fixtures ----

GOLDEN_DESIGN_SYSTEM = {
    "version": "1.0",
    "source": {
        "repo_path": "/work/acme-app",
        "framework": "next",
        "styling_systems": ["tailwind", "css-variables"],
        "git_commit": "abc1234",
    },
    "tokens": {
        "colors": [
            {"name": "primary", "value": "#6366f1", "role": "primary",
             "provenance": {"file": "app/globals.css", "line": 12, "key": "--primary"}},
        ],
        "typography": {
            "fonts": [
                {"family": "Inter", "role": "body", "weights": [400, 600],
                 "provenance": {"file": "app/layout.tsx", "line": 3}},
            ],
            "scale": [
                {"name": "h1", "size": "36px", "weight": "600", "line_height": "1.1",
                 "provenance": {"file": "app/page.tsx", "line": 22}},
            ],
        },
        "radii": [
            {"name": "card", "value": "12px",
             "provenance": {"file": "tailwind.config.ts", "key": "theme.extend.borderRadius.lg"}},
        ],
        "glass": {
            "derived": True,
            "background": "rgba(99,102,241,0.08)",
            "backdrop_blur": "24px",
            "border": "1px solid rgba(255,255,255,0.12)",
            "rationale": "composed from --primary at low alpha; product has no frosted surfaces",
        },
    },
    "component_styles": {
        "buttons": [
            {"variant": "primary button",
             "css_summary": "bg --primary, white text, rounded-lg (8px), px-4 py-2, text-sm font-medium",
             "provenance": {"file": "components/ui/button.tsx", "line": 20}},
        ],
    },
    "gaps": [
        {"token": "glass", "how_inferred": "derived from palette (no glass in product)"},
    ],
    "summary": "Indigo-primary minimal SaaS, Inter throughout, 8-12px radii, dark-first.",
}

GOLDEN_UI_INVENTORY = {
    "version": "1.0",
    "repo_path": "/work/acme-app",
    "screens": [
        {
            "id": "dashboard",
            "name": "Dashboard",
            "route": "/",
            "source_files": ["app/page.tsx", "components/stat-card.tsx"],
            "purpose": "usage overview with stat cards and a request chart",
            "ui_elements": [
                {"type": "card", "label": "Monthly active users",
                 "source_file": "components/stat-card.tsx"},
                {"type": "chart", "label": "requests over time (area chart)",
                 "source_file": "app/page.tsx"},
            ],
            "flagship_notes": "hero surface — richest animatable layout",
            "reviewed": True,
        }
    ],
    "components": [
        {"id": "stat-card", "name": "StatCard", "source_file": "components/stat-card.tsx",
         "kind": "stat card", "used_by_screens": ["dashboard"]},
    ],
    "flagship_recommendations": [
        {"screen_id": "dashboard", "why": "shows the product's core promise at a glance"},
    ],
    "summary": "Single dashboard app: stat cards, one chart, settings form.",
    "planning_implications": [
        "Hero scene should assemble the stat-card grid, then draw the chart.",
    ],
}


# ---- Manifest ----

class TestManifest:
    def test_validates_against_pipeline_schema(self, manifest):
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        jsonschema.validate(manifest, schema)

    def test_stage_order(self, manifest):
        names = [s["name"] for s in manifest["stages"]]
        assert names == [
            "repo_analysis", "proposal", "script", "scene_plan",
            "assets", "edit", "compose", "publish",
        ]

    def test_all_required_skill_files_exist(self, manifest):
        for ref in manifest["required_skills"]:
            path = ROOT / "skills" / f"{ref}.md"
            assert path.is_file(), f"required_skills references missing file: {path}"

    def test_all_stage_skill_files_exist(self, manifest):
        for stage in manifest["stages"]:
            path = ROOT / "skills" / f"{stage['skill']}.md"
            assert path.is_file(), f"stage {stage['name']} skill missing: {path}"

    def test_produces_are_known_artifacts(self, manifest):
        for stage in manifest["stages"]:
            for produced in stage.get("produces", []):
                assert produced in ARTIFACT_NAMES, (
                    f"stage {stage['name']} produces unknown artifact {produced!r}"
                )

    def test_repo_analysis_and_assets_are_gated(self, manifest):
        gates = {s["name"]: s["human_approval_default"] for s in manifest["stages"]}
        assert gates["repo_analysis"] is True
        assert gates["assets"] is True, "assets is the fidelity gate — must be gated"
        assert gates["proposal"] is True

    def test_layer3_skills_exist(self):
        for name in ("repo-design-extraction", "glass-ui-motion"):
            assert (ROOT / ".agents" / "skills" / name / "SKILL.md").is_file()
            assert (ROOT / ".claude" / "skills" / name / "SKILL.md").is_file()


# ---- Checkpoint wiring ----

class TestCheckpointWiring:
    def test_stage_registered(self):
        assert "repo_analysis" in ALL_KNOWN_STAGES
        assert CANONICAL_STAGE_ARTIFACTS["repo_analysis"] == "design_system"
        assert "ui_inventory" in SUPPLEMENTARY_ARTIFACTS

    def test_repo_analysis_checkpoint_roundtrip(self, tmp_path):
        path = write_checkpoint(
            tmp_path, "proj", "repo_analysis", "awaiting_human",
            artifacts={
                "design_system": GOLDEN_DESIGN_SYSTEM,
                "ui_inventory": GOLDEN_UI_INVENTORY,
            },
            pipeline_type="product-motion",
            human_approval_required=True,
        )
        assert path.exists()

    def test_repo_analysis_requires_design_system(self, tmp_path):
        with pytest.raises(CheckpointValidationError):
            write_checkpoint(
                tmp_path, "proj", "repo_analysis", "awaiting_human",
                artifacts={"ui_inventory": GOLDEN_UI_INVENTORY},
                pipeline_type="product-motion",
                human_approval_required=True,
            )

    def test_repo_analysis_gate_enforced(self, tmp_path):
        """Gated stage cannot be completed without human approval."""
        with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
            write_checkpoint(
                tmp_path, "proj", "repo_analysis", "completed",
                artifacts={"design_system": GOLDEN_DESIGN_SYSTEM},
                pipeline_type="product-motion",
            )


# ---- Artifact schemas ----

class TestDesignSystemSchema:
    def test_golden_validates(self):
        validate_artifact("design_system", GOLDEN_DESIGN_SYSTEM)

    def test_token_without_provenance_rejected(self):
        bad = copy.deepcopy(GOLDEN_DESIGN_SYSTEM)
        del bad["tokens"]["colors"][0]["provenance"]
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("design_system", bad)

    def test_glass_requires_derived_flag(self):
        bad = copy.deepcopy(GOLDEN_DESIGN_SYSTEM)
        del bad["tokens"]["glass"]["derived"]
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("design_system", bad)

    def test_unknown_framework_rejected(self):
        bad = copy.deepcopy(GOLDEN_DESIGN_SYSTEM)
        bad["source"]["framework"] = "flutter"
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("design_system", bad)


class TestUiInventorySchema:
    def test_golden_validates(self):
        validate_artifact("ui_inventory", GOLDEN_UI_INVENTORY)

    def test_unreviewed_screen_rejected(self):
        bad = copy.deepcopy(GOLDEN_UI_INVENTORY)
        bad["screens"][0]["reviewed"] = False
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("ui_inventory", bad)

    def test_screen_without_sources_rejected(self):
        bad = copy.deepcopy(GOLDEN_UI_INVENTORY)
        bad["screens"][0]["source_files"] = []
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("ui_inventory", bad)

    def test_planning_implications_required(self):
        bad = copy.deepcopy(GOLDEN_UI_INVENTORY)
        bad["planning_implications"] = []
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("ui_inventory", bad)


class TestAssetManifestProvenance:
    def test_snapshot_with_provenance_validates(self):
        validate_artifact("asset_manifest", {
            "version": "1.0",
            "assets": [{
                "id": "snap-dashboard",
                "type": "image",
                "subtype": "scene_snapshot",
                "path": "assets/images/dashboard.png",
                "source_tool": "atelier_snapshots",
                "scene_id": "scene-dashboard",
                "provenance": {
                    "source_files": ["app/page.tsx", "components/stat-card.tsx"],
                    "design_tokens": ["primary", "card"],
                    "notes": "sidebar omitted (not in scene)",
                },
            }],
        })

    def test_provenance_rejects_unknown_fields(self):
        with pytest.raises(jsonschema.ValidationError):
            validate_artifact("asset_manifest", {
                "version": "1.0",
                "assets": [{
                    "id": "a", "type": "image", "path": "x.png",
                    "source_tool": "t", "scene_id": "s",
                    "provenance": {"invented_field": True},
                }],
            })
