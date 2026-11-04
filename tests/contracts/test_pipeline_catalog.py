"""Every shipped pipeline manifest must actually load.

`lib.checkpoint` degrades gracefully when a manifest cannot be parsed:
`get_pipeline_stages()` falls back to the canonical STAGES list and
`_stage_requires_approval()` returns None so the caller's own flag wins. That
is the right behaviour for a corrupt user manifest, but it means a manifest
shipped *in this repo* that fails its schema is silently ignored rather than
loudly rejected — the pipeline then runs against the wrong stage order and
without its declared approval gates.

Existing manifest coverage names individual pipelines (talking-head,
framework-smoke, animated-explainer, documentary-montage), so a manifest that
no test happens to name is never loaded. These tests iterate the directory.
"""

from pathlib import Path

import pytest
import yaml

from lib.checkpoint import _stage_requires_approval, get_pipeline_stages
from lib.pipeline_loader import load_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DEFS = REPO_ROOT / "pipeline_defs"

PIPELINE_NAMES = sorted(p.stem for p in PIPELINE_DEFS.glob("*.yaml"))


def _declared_stages(name: str) -> list[str]:
    raw = yaml.safe_load((PIPELINE_DEFS / f"{name}.yaml").read_text(encoding="utf-8"))
    return [stage["name"] for stage in raw["stages"]]


def test_catalog_is_not_empty() -> None:
    assert PIPELINE_NAMES, "no pipeline manifests found"


@pytest.mark.parametrize("name", PIPELINE_NAMES)
def test_shipped_manifest_validates(name: str) -> None:
    """Regression: screen-demo.yaml carried a `production_modes` block the
    manifest schema did not allow, so the whole manifest failed to load."""
    manifest = load_pipeline(name)
    assert manifest["stages"]


@pytest.mark.parametrize("name", PIPELINE_NAMES)
def test_effective_stage_order_is_the_declared_one(name: str) -> None:
    """A manifest that silently falls back gets the canonical stage list.

    For screen-demo that inserted `research` and `proposal` ahead of its real
    first stage, so the prerequisite check rejected the opening checkpoint of
    every run with PREREQUISITE VIOLATION.
    """
    assert get_pipeline_stages(name) == _declared_stages(name)


@pytest.mark.parametrize("name", PIPELINE_NAMES)
def test_declared_approval_gates_are_enforceable(name: str) -> None:
    """AGENT_GUIDE.md: the manifest's human_approval_default is binding.

    `_stage_requires_approval` returning None means the caller's own flag wins,
    which is exactly the fail-open the gate is supposed to prevent.
    """
    raw = yaml.safe_load((PIPELINE_DEFS / f"{name}.yaml").read_text(encoding="utf-8"))

    for stage in raw["stages"]:
        if "human_approval_default" not in stage:
            continue
        resolved = _stage_requires_approval(name, stage["name"])
        assert resolved == stage["human_approval_default"], (
            f"{name}.{stage['name']}: manifest declares "
            f"{stage['human_approval_default']} but the checkpoint writer "
            f"resolves {resolved}"
        )
