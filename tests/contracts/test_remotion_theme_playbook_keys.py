"""The Remotion theme must be derived from the playbook's real schema keys.

`VideoCompose._build_theme_from_playbook` says it reads "a playbook's actual
color values [...] not picked from a preset menu", but it read three keys the
playbook schema does not define, so each silently fell back to a hardcoded
default for every playbook:

    typo.get("heading")        schema key is `headings`
    palette.get("muted_text")  schema key is `muted`
    motion.get("pace")         `pace` is an identity field, not a motion one

Expectations come from the playbook YAML rather than a hardcoded table, so a
playbook that changes its typeface keeps this honest.

This is the Remotion counterpart of the HyperFrames style-bridge defect in
issue #306; that bridge lives in lib/hyperframes_style_bridge.py and is not
touched here.
"""

from pathlib import Path

import pytest
import yaml

from styles.playbook_loader import list_playbooks
from tools.video.video_compose import VideoCompose

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLES_DIR = REPO_ROOT / "styles"

PLAYBOOK_NAMES = sorted(list_playbooks())


def _raw(name: str) -> dict:
    return yaml.safe_load((STYLES_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def _theme(name: str) -> dict:
    theme = VideoCompose()._build_theme_from_playbook(name, {})
    if not theme:
        pytest.skip(f"{name} does not currently yield a theme")
    return theme


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_heading_font_comes_from_the_playbook(name: str) -> None:
    """Regression: read from `heading`, so every playbook rendered in Inter."""
    expected = _raw(name)["typography"]["headings"]["font"]
    assert _theme(name)["headingFont"] == expected


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_muted_text_color_comes_from_the_playbook(name: str) -> None:
    """Regression: read from `muted_text`, so this was always #6B7280."""
    palette = _raw(name)["visual_language"]["color_palette"]
    if "muted" not in palette:
        pytest.skip(f"{name} declares no muted color")
    assert _theme(name)["mutedTextColor"] == palette["muted"]


def test_identity_pace_drives_the_motion_feel() -> None:
    """Regression: read `pace` off motion, where the schema has no such key,
    so the spring never left its moderate default."""
    fast = [n for n in PLAYBOOK_NAMES if _raw(n)["identity"]["pace"] == "fast"]
    if not fast:
        pytest.skip("no playbook declares a fast pace")

    moderate_default = {"damping": 20, "stiffness": 120, "mass": 1}
    for name in fast:
        theme = _theme(name)
        assert theme["springConfig"] != moderate_default, (
            f"{name} declares pace=fast but still got the moderate spring"
        )
        assert theme["transitionDuration"] < 0.4


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_derived_theme_only_reads_documented_palette_keys(name: str) -> None:
    """The derived colors must be values the playbook can actually express."""
    palette = _raw(name)["visual_language"]["color_palette"]
    theme = _theme(name)

    primary = palette["primary"]
    accent = palette["accent"]
    assert theme["primaryColor"] == (primary[0] if isinstance(primary, list) else primary)
    assert theme["accentColor"] == (accent[0] if isinstance(accent, list) else accent)
    assert theme["backgroundColor"] == palette["background"]
    assert theme["textColor"] == palette["text"]
