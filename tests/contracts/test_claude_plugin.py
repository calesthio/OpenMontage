"""The Claude Code plugin must point at files that exist.

`.claude-plugin/marketplace.json` makes the repository installable with
`/plugin install openmontage --marketplace calesthio/OpenMontage`. Its skill
recognises a checkout by `AGENT_GUIDE.md` and `pipeline_defs/`, sets one up
with `make setup` or the README's "No `make`?" commands, then hands over to
AGENT_GUIDE.md. Renaming any of those breaks the plugin while it still installs.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "plugins" / "openmontage" / "skills" / "make-video" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_marketplace_plugin_sources_exist() -> None:
    marketplace = json.loads(_read(REPO_ROOT / ".claude-plugin" / "marketplace.json"))
    for plugin in marketplace["plugins"]:
        assert (REPO_ROOT / plugin["source"]).is_dir(), plugin["source"]


def test_skill_names_files_that_exist() -> None:
    skill = _read(SKILL)
    for marker in ("AGENT_GUIDE.md", "pipeline_defs/"):
        assert f"`{marker}`" in skill
        assert (REPO_ROOT / marker).exists(), marker
    assert "make setup" in skill and "\nsetup:" in _read(REPO_ROOT / "Makefile")
    assert "No `make`?" in skill and "No `make`?" in _read(REPO_ROOT / "README.md")
