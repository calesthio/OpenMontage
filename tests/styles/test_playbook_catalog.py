"""Every shipped style playbook must actually load.

`list_playbooks()` advertises a playbook as selectable, `pipeline_defs/*.yaml`
offer them by name, and `lib.checkpoint._validate_style_playbook` fails closed
on anything `load_playbook()` rejects. So a playbook that is listed but does not
validate is not a cosmetic problem — it blocks `init_project()`/`write_checkpoint()`
outright, taking the whole pipeline down for that style.

These tests iterate the catalog rather than a hardcoded list, which is how
`anime-ghibli` and `premium-minimalist` slipped through: the pre-existing
coverage in tests/qa/test_07_playbook_intelligence.py names three playbooks
that were the only ones in the repo when it was written.
"""

import pytest

from lib.checkpoint import init_project
from styles.playbook_loader import list_playbooks, load_playbook

PLAYBOOK_NAMES = sorted(list_playbooks())

# The overlay types remotion-composer actually renders, from the `Overlay`
# union in remotion-composer/src/Explainer.tsx. A playbook must be able to
# style any of them.
RENDERER_OVERLAY_TYPES = (
    "section_title",
    "stat_reveal",
    "hero_title",
    "provider_chip",
)


def test_catalog_is_not_empty() -> None:
    assert PLAYBOOK_NAMES, "list_playbooks() found no playbooks at all"


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_listed_playbook_loads_and_validates(name: str) -> None:
    """A playbook offered by the catalog must pass its own schema."""
    playbook = load_playbook(name)
    assert playbook["identity"]["name"]


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_listed_playbook_is_accepted_by_init_project(name: str, tmp_path) -> None:
    """The checkpoint writer validates style_playbook fail-closed.

    Regression: `anime-ghibli` was listed and offered by pipeline_defs/animation.yaml
    but raised CheckpointValidationError here, so no run using that style could
    write a checkpoint.
    """
    init_project(
        f"catalog-{name}",
        title="Catalog probe",
        pipeline_type="animation",
        pipeline_dir=tmp_path,
        style_playbook=name,
    )


@pytest.mark.parametrize("overlay_type", RENDERER_OVERLAY_TYPES)
def test_schema_allows_every_renderer_overlay_type(overlay_type: str) -> None:
    """The playbook schema's overlay vocabulary must track the renderer's.

    Regression: the schema allowed only stat_card/key_term/code_block — none of
    the four overlay types Explainer renders — so styling `section_title` made
    the whole playbook invalid.
    """
    import json
    from pathlib import Path

    schema_path = (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "styles"
        / "playbook.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    allowed = schema["properties"]["overlays"]["properties"]
    assert overlay_type in allowed
