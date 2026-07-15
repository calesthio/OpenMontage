"""Every style playbook must load through the schema-validating loader.

Audit finding BUG-3 (2026-07-15): anime-ghibli shipped with 5 schema
violations and raised at load_playbook() while animation.yaml recommended it.
"""

import pytest

from styles.playbook_loader import list_playbooks, load_playbook


@pytest.mark.parametrize("name", list_playbooks())
def test_playbook_loads_and_validates(name):
    playbook = load_playbook(name)
    assert playbook.get("identity"), f"{name} has no identity block"
