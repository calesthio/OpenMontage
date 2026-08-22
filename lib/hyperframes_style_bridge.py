"""Bridge OpenMontage playbooks → HyperFrames-friendly style artifacts.

OpenMontage playbooks are YAML files describing visual_language, typography,
motion, and asset generation guidance. When `render_runtime = "remotion"`
they're translated into a `themeConfig` prop on the React composition
(see `tools/video/video_compose._build_theme_from_playbook`). When
`render_runtime = "hyperframes"` the equivalent translation produces:

- a dict of CSS custom properties to emit on `:root`
- a short DESIGN.md the workspace can ship so humans (and agents) can
  inspect the visual system in plain language

The playbook schema is NOT forked. We read the same fields; we just render
them differently.
"""

from __future__ import annotations

from typing import Any


_FALLBACK_CSS_VARS = {
    "--color-bg": "#0B0F1A",
    "--color-fg": "#F5F5F5",
    "--color-accent": "#F59E0B",
    "--color-primary": "#2563EB",
    "--color-secondary": "#10B981",
    "--color-surface": "#111827",
    "--color-muted": "#6B7280",
    "--font-heading": "Inter",
    "--font-body": "Inter",
    "--font-mono": "JetBrains Mono",
    "--ease-primary": "cubic-bezier(0.65, 0, 0.35, 1)",
    "--ease-entrance": "cubic-bezier(0.33, 1, 0.68, 1)",
    "--ease-exit": "cubic-bezier(0.32, 0, 0.67, 0)",
    "--duration-entrance": "0.6s",
    "--duration-transition": "0.5s",
}


def _first(raw: Any, default: str) -> str:
    """Return the first string value from a palette entry (list or scalar)."""
    if isinstance(raw, list) and raw:
        return str(raw[0])
    if isinstance(raw, str) and raw:
        return raw
    return default


def _font(typo: dict[str, Any], key: str, default: str) -> str:
    """Extract a font family string from a typography block."""
    node = typo.get(key) or {}
    if isinstance(node, dict):
        return str(node.get("font") or node.get("family") or default)
    if isinstance(node, str):
        return node
    return default


_FAST_EASE = "cubic-bezier(0.33, 1, 0.68, 1)"
_SLOW_EASE = "cubic-bezier(0.65, 0, 0.35, 1)"
_MODERATE_EASE = "cubic-bezier(0.5, 0, 0.5, 1)"

# Keyed by the `identity.pace` enum (schema: slow/deliberate/moderate/fast/rapid).
# Every enum value must be covered here — an unmapped-but-valid pace would
# silently collapse to the moderate default.
_PACE_MOTION = {
    "rapid": ("0.3s", _FAST_EASE),
    "fast": ("0.4s", _FAST_EASE),
    "moderate": ("0.6s", _MODERATE_EASE),
    "deliberate": ("0.8s", _SLOW_EASE),
    "slow": ("0.9s", _SLOW_EASE),
}


def _motion_easing(pace: Any) -> tuple[str, str]:
    """Derive (duration, ease) from the playbook's `identity.pace` value."""
    key = pace.lower() if isinstance(pace, str) else "moderate"
    return _PACE_MOTION.get(key, _PACE_MOTION["moderate"])


def style_bridge(
    playbook: dict[str, Any] | None,
    edit_decisions: dict[str, Any] | None = None,
) -> tuple[dict[str, str], str]:
    """Translate a playbook into (css_vars, design_md).

    Both outputs are safe to write into a HyperFrames workspace:
    - `css_vars` → `:root { … }` block in index.html
    - `design_md` → `DESIGN.md` at the workspace root

    When `playbook` is empty or partial, missing fields fall back to
    `_FALLBACK_CSS_VARS` so the emitted HTML is always renderable.
    """
    css: dict[str, str] = dict(_FALLBACK_CSS_VARS)
    source_note = "built-in fallback palette"
    playbook_name = ""

    if playbook:
        playbook_name = str(
            playbook.get("name")
            or playbook.get("id")
            or playbook.get("display_name")
            or ""
        )
        vl = playbook.get("visual_language", {}) or {}
        palette = vl.get("color_palette", {}) or {}
        typo = playbook.get("typography", {}) or {}
        identity = playbook.get("identity", {}) or {}
        motion = playbook.get("motion", {}) or {}

        bg = _first(palette.get("background"), css["--color-bg"])
        fg = _first(palette.get("text"), css["--color-fg"])
        accent = _first(palette.get("accent"), css["--color-accent"])
        primary = _first(palette.get("primary"), css["--color-primary"])
        secondary = _first(palette.get("secondary"), css["--color-secondary"])
        surface = _first(palette.get("surface"), css["--color-surface"])
        muted = _first(palette.get("muted_text"), css["--color-muted"])

        # Pace lives under `identity` in the current schema; older/custom
        # playbooks placed it under `motion`. Prefer the schema key, fall back
        # to the legacy location so existing callers keep working.
        duration, ease = _motion_easing(identity.get("pace") or motion.get("pace"))

        css.update(
            {
                "--color-bg": bg,
                "--color-fg": fg,
                "--color-accent": accent,
                "--color-primary": primary,
                "--color-secondary": secondary,
                "--color-surface": surface,
                "--color-muted": muted,
                # Schema key is `headings` (plural); legacy/custom playbooks used
                # `heading` (singular). Prefer the schema key, fall back to legacy.
                "--font-heading": _font(
                    typo, "headings", _font(typo, "heading", css["--font-heading"])
                ),
                "--font-body": _font(typo, "body", css["--font-body"]),
                "--font-mono": _font(typo, "code", css["--font-mono"]),
                "--ease-primary": ease,
                "--duration-entrance": duration,
            }
        )

        source_note = f"playbook `{playbook_name}`" if playbook_name else "loaded playbook"

    # Edit-decisions may override colors per-production (rare but legal).
    if edit_decisions:
        meta = edit_decisions.get("metadata", {}) or {}
        if meta.get("primary_color"):
            css["--color-primary"] = str(meta["primary_color"])
        if meta.get("accent_color"):
            css["--color-accent"] = str(meta["accent_color"])
        if meta.get("background_color"):
            css["--color-bg"] = str(meta["background_color"])
        if meta.get("text_color"):
            css["--color-fg"] = str(meta["text_color"])

    design_md = _render_design_md(css, source_note, playbook_name)
    return css, design_md


def _render_design_md(
    css: dict[str, str], source_note: str, playbook_name: str
) -> str:
    title = f"# DESIGN — {playbook_name}" if playbook_name else "# DESIGN"
    lines = [
        title,
        "",
        f"> Generated by OpenMontage HyperFrames style bridge (source: {source_note}).",
        "",
        "## Colors",
        "",
        f"- Background: `{css['--color-bg']}`",
        f"- Foreground: `{css['--color-fg']}`",
        f"- Primary: `{css['--color-primary']}`",
        f"- Accent: `{css['--color-accent']}`",
        f"- Secondary: `{css['--color-secondary']}`",
        f"- Surface: `{css['--color-surface']}`",
        f"- Muted text: `{css['--color-muted']}`",
        "",
        "## Typography",
        "",
        f"- Heading: `{css['--font-heading']}`",
        f"- Body: `{css['--font-body']}`",
        f"- Mono: `{css['--font-mono']}`",
        "",
        "## Motion",
        "",
        f"- Primary ease: `{css['--ease-primary']}`",
        f"- Entrance duration: `{css['--duration-entrance']}`",
        "",
        "## How to use in compositions",
        "",
        "Reference these tokens via `var(...)` instead of hard-coding hex",
        "values or font names:",
        "",
        "```css",
        ".scene-content h1 {",
        "  font-family: var(--font-heading);",
        "  color: var(--color-fg);",
        "}",
        ".scene-content .accent {",
        "  color: var(--color-accent);",
        "}",
        "```",
        "",
        "When adjusting a composition's look, edit the `:root` block in",
        "`index.html` (or this bridge for cross-project changes), not the",
        "individual scene styles.",
        "",
    ]
    return "\n".join(lines)
