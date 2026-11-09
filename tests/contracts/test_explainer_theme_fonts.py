"""Explainer scene components draw headlines in the theme's heading font.

TextCard, StatCard and HeroTitle used to fix Inter / Space Grotesk, so a playbook's heading font
never reached them. Fonts resolve by name, so the stack needs a sans fallback for one that is not
installed. Renders real frames, using only the fonts bundled with the repo so the result does not
depend on the machine. Skipped when Remotion is not installed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")
ImageChops = pytest.importorskip("PIL.ImageChops")

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer"
CUTS = {
    "text_card": {"type": "text_card", "text": "Theme heading font"},
    "stat_card": {"type": "stat_card", "stat": "73%"},
    "hero_title": {"type": "hero_title", "text": "Main Title"},
}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> Path:
    if not (shutil.which("npx") and (COMPOSER / "node_modules").exists()):
        pytest.skip("Remotion is not installed")
    out = tmp_path_factory.mktemp("bundle")
    subprocess.run(
        ["npx", "remotion", "bundle", "src/index.tsx", f"--out-dir={out}", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )
    return out


def _still(bundle: Path, tmp_path: Path, tag: str, cut: dict, **props):
    props_file = tmp_path / f"{tag}.json"
    props_file.write_text(json.dumps({"cuts": [{"id": "c", "in_seconds": 0, "out_seconds": 2, **cut}], **props}))
    png = tmp_path / f"{tag}.png"
    subprocess.run(
        ["npx", "remotion", "still", str(bundle), "Explainer", str(png), f"--props={props_file}", "--frame=45", "--log=error"],
        cwd=COMPOSER, check=True, capture_output=True,
    )
    return Image.open(png).convert("RGB")


def _font_theme(font: str) -> dict:
    return {"themeConfig": {"headingFont": font, "bodyFont": font}}


def _same(a, b) -> bool:
    return ImageChops.difference(a, b).getbbox() is None


@pytest.mark.parametrize("name", CUTS)
def test_the_theme_heading_font_reaches_the_component(bundle, tmp_path, name) -> None:
    playfair = _still(bundle, tmp_path, "playfair", CUTS[name], **_font_theme("Playfair Display"))
    grotesk = _still(bundle, tmp_path, "grotesk", CUTS[name], **_font_theme("Space Grotesk"))
    assert not _same(playfair, grotesk), f"{name} ignores theme.headingFont"


def test_a_font_that_is_not_installed_falls_back_to_the_sans_stack(bundle, tmp_path) -> None:
    missing = _still(bundle, tmp_path, "missing", CUTS["text_card"], **_font_theme("No Such Font"))
    inter = _still(bundle, tmp_path, "inter", CUTS["text_card"], **_font_theme("Inter"))
    assert _same(missing, inter), "a missing font falls through to the browser's default serif"

