"""video_compose: the playbook's chart_palette wins over the palette-derived chart colors.

The playbook schema defines chart_palette at the top level; validate_palette and the
data-visualization skill also read it under visual_language.color_palette (nested
first). The Remotion theme honours both locations, in that same order.
"""

from __future__ import annotations

import styles.playbook_loader as playbook_loader
from tools.video.video_compose import VideoCompose

PALETTE = {"primary": ["#111111"], "accent": ["#222222"], "secondary": "#333333",
           "background": "#000000", "text": "#FFFFFF"}
CHART = ["#AA0000", "#00AA00", "#0000AA", "#AAAA00"]


def _theme(monkeypatch, playbook):
    monkeypatch.setattr(playbook_loader, "load_playbook", lambda name: playbook)
    return VideoCompose._build_theme_from_playbook("x", None)


def test_top_level_chart_palette_wins(monkeypatch):
    theme = _theme(monkeypatch, {"visual_language": {"color_palette": PALETTE},
                                 "chart_palette": CHART})
    assert theme["chartColors"] == CHART


def test_nested_chart_palette_wins(monkeypatch):
    palette = dict(PALETTE, chart_palette=CHART)
    theme = _theme(monkeypatch, {"visual_language": {"color_palette": palette}})
    assert theme["chartColors"] == CHART


def test_nested_takes_precedence_over_top_level(monkeypatch):
    palette = dict(PALETTE, chart_palette=CHART)
    theme = _theme(monkeypatch, {"visual_language": {"color_palette": palette},
                                 "chart_palette": ["#010101", "#020202", "#030303"]})
    assert theme["chartColors"] == CHART


def test_without_chart_palette_derives_from_palette(monkeypatch):
    theme = _theme(monkeypatch, {"visual_language": {"color_palette": PALETTE}})
    assert theme["chartColors"][:3] == ["#111111", "#222222", "#333333"]
