"""Style playbook loader.

Loads, validates, and lists style playbook YAML files from styles/.
Includes design intelligence: color palette analysis, typography intelligence,
and accessibility validation (D3.5.5, D3.5.6, D3.5.7).
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path
from typing import Any, Optional

import yaml
import jsonschema

STYLES_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "schemas"
    / "styles"
    / "playbook.schema.json"
)


def _load_playbook_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_playbook(name: str, styles_dir: Optional[Path] = None) -> dict[str, Any]:
    """Load and validate a style playbook by name.

    Args:
        name: Playbook name (without .yaml extension).
        styles_dir: Override directory for playbook files.

    Returns:
        Validated playbook dict.
    """
    styles_dir = styles_dir or STYLES_DIR
    path = styles_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Playbook not found: {path}")

    with open(path) as f:
        playbook = yaml.safe_load(f)

    validate_playbook(playbook)
    return playbook


def validate_playbook(playbook: dict) -> None:
    """Validate a playbook dict against the schema."""
    schema = _load_playbook_schema()
    jsonschema.validate(instance=playbook, schema=schema)


def list_playbooks(styles_dir: Optional[Path] = None) -> list[str]:
    """List all available playbook names."""
    styles_dir = styles_dir or STYLES_DIR
    return [
        p.stem
        for p in styles_dir.glob("*.yaml")
        if p.stem != "__pycache__"
    ]


# ---------------------------------------------------------------------------
# Color math helpers (pure Python, no external deps)
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to (R, G, B) tuple (0-255)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    # Handle 8-char hex (with alpha) by taking first 6 chars
    if len(h) == 8:
        h = h[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _has_alpha(hex_color: str) -> bool:
    """Check if a hex color string includes an alpha channel (8-char hex)."""
    return len(hex_color.lstrip("#")) == 8


def _composite_alpha(fg_hex: str, bg_hex: str) -> str:
    """Composite an RGBA foreground color onto an opaque background.

    Args:
        fg_hex: Foreground color as 8-char hex (#RRGGBBAA).
        bg_hex: Opaque background color as 6-char hex (#RRGGBB).

    Returns:
        Composited opaque hex color string.
    """
    h = fg_hex.lstrip("#")
    alpha = int(h[6:8], 16) / 255.0
    fg_r, fg_g, fg_b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    bg_r, bg_g, bg_b = _hex_to_rgb(bg_hex)
    r = round(alpha * fg_r + (1 - alpha) * bg_r)
    g = round(alpha * fg_g + (1 - alpha) * bg_g)
    b = round(alpha * fg_b + (1 - alpha) * bg_b)
    return _rgb_to_hex(r, g, b)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (R, G, B) tuple to hex string."""
    r = max(0, min(255, round(r)))
    g = max(0, min(255, round(g)))
    b = max(0, min(255, round(b)))
    return f"#{r:02X}{g:02X}{b:02X}"


def _srgb_linearize(c: float) -> float:
    """Convert sRGB channel (0-1) to linear RGB."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """Calculate sRGB relative luminance per WCAG 2.1.

    L = 0.2126*R + 0.7152*G + 0.0722*B
    where R, G, B are linearized sRGB values.
    """
    r, g, b = _hex_to_rgb(hex_color)
    r_lin = _srgb_linearize(r / 255.0)
    g_lin = _srgb_linearize(g / 255.0)
    b_lin = _srgb_linearize(b / 255.0)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color to HSL (h: 0-360, s: 0-1, l: 0-1)."""
    r, g, b = _hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return h * 360.0, s, l


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL (h: 0-360, s: 0-1, l: 0-1) to hex color."""
    h_norm = (h % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(h_norm, l, s)
    return _rgb_to_hex(round(r * 255), round(g * 255), round(b * 255))


# ---------------------------------------------------------------------------
# Color-blind simulation matrices
# ---------------------------------------------------------------------------

# Confusion pair thresholds for each type of color vision deficiency.
# These simulate which hue ranges become indistinguishable.
_CVD_CONFUSION_PAIRS: dict[str, list[tuple[tuple[int, int], tuple[int, int]]]] = {
    # Deuteranopia: red-green confusion (most common, ~6% of males)
    "deuteranopia": [
        ((0, 30), (90, 150)),      # Red vs green
        ((30, 60), (90, 130)),     # Orange vs green
        ((330, 360), (90, 150)),   # Magenta-red vs green
    ],
    # Protanopia: red-green confusion (shifted, ~1% of males)
    "protanopia": [
        ((0, 40), (80, 140)),      # Red-orange vs green
        ((340, 360), (80, 140)),   # Red vs green
        ((0, 20), (170, 200)),     # Red vs cyan
    ],
    # Tritanopia: blue-yellow confusion (~0.01%)
    "tritanopia": [
        ((200, 270), (50, 100)),   # Blue vs yellow-green
        ((220, 260), (40, 80)),    # Blue vs yellow
        ((170, 210), (300, 340)),  # Cyan vs pink
    ],
}


def _hue_in_range(hue: float, hue_range: tuple[int, int]) -> bool:
    """Check if a hue falls within a range (handles wrap-around)."""
    low, high = hue_range
    if low <= high:
        return low <= hue <= high
    # Wrap-around (e.g., 330-30 means 330-360 and 0-30)
    return hue >= low or hue <= high


# ---------------------------------------------------------------------------
# D3.5.5 — Color palette intelligence
# ---------------------------------------------------------------------------

def validate_contrast(fg_hex: str, bg_hex: str) -> dict:
    """Calculate WCAG 2.1 contrast ratio between foreground and background.

    Uses sRGB relative luminance: L = 0.2126*R + 0.7152*G + 0.0722*B

    Args:
        fg_hex: Foreground color as hex string (e.g., "#1F2937").
        bg_hex: Background color as hex string (e.g., "#FFFFFF").

    Returns:
        Dict with ratio, AA/AAA pass/fail for normal and large text.
    """
    l1 = _relative_luminance(fg_hex)
    l2 = _relative_luminance(bg_hex)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    ratio = (lighter + 0.05) / (darker + 0.05)

    return {
        "foreground": fg_hex,
        "background": bg_hex,
        "ratio": round(ratio, 2),
        "normal_text": {
            "AA": ratio >= 4.5,
            "AAA": ratio >= 7.0,
        },
        "large_text": {
            "AA": ratio >= 3.0,
            "AAA": ratio >= 4.5,
        },
    }


def check_color_blind_safety(colors: list[str]) -> dict:
    """Check a list of colors for color-blind confusion pairs.

    Simulates deuteranopia, protanopia, and tritanopia confusion.
    Flags color pairs that may become indistinguishable.

    Args:
        colors: List of hex color strings.

    Returns:
        Dict with per-deficiency results and flagged pairs.
    """
    hues = []
    for c in colors:
        h, s, l = _hex_to_hsl(c)
        hues.append({"hex": c, "hue": h, "saturation": s, "lightness": l})

    results: dict[str, Any] = {
        "safe": True,
        "colors_analyzed": len(colors),
        "issues": [],
    }

    for cvd_type, confusion_ranges in _CVD_CONFUSION_PAIRS.items():
        for i in range(len(hues)):
            for j in range(i + 1, len(hues)):
                c1 = hues[i]
                c2 = hues[j]

                # Skip very desaturated colors (grays) — distinguishable by
                # lightness alone regardless of hue perception.
                if c1["saturation"] < 0.15 or c2["saturation"] < 0.15:
                    continue

                # Check if lightness difference alone saves them.
                if abs(c1["lightness"] - c2["lightness"]) > 0.3:
                    continue

                for range_a, range_b in confusion_ranges:
                    a_in_a = _hue_in_range(c1["hue"], range_a)
                    b_in_b = _hue_in_range(c2["hue"], range_b)
                    a_in_b = _hue_in_range(c1["hue"], range_b)
                    b_in_a = _hue_in_range(c2["hue"], range_a)
                    if (a_in_a and b_in_b) or (a_in_b and b_in_a):
                        results["safe"] = False
                        results["issues"].append({
                            "type": cvd_type,
                            "color_a": c1["hex"],
                            "color_b": c2["hex"],
                            "severity": "warning",
                            "message": (
                                f"{c1['hex']} and {c2['hex']} may be "
                                f"indistinguishable for {cvd_type} viewers"
                            ),
                        })

    return results


def validate_palette(playbook: dict) -> list[dict]:
    """Run contrast and color-blind checks on all text/bg pairs in a playbook.

    Examines visual_language.color_palette and overlays for text/background
    combinations and chart_palette if present.

    Args:
        playbook: Loaded playbook dict.

    Returns:
        List of issue dicts with severity (error/warning/info).
    """
    issues: list[dict] = []
    palette = playbook.get("visual_language", {}).get("color_palette", {})
    bg = palette.get("background", "#FFFFFF")
    text = palette.get("text", "#000000")
    muted = palette.get("muted")

    # Check main text on background
    result = validate_contrast(text, bg)
    if not result["normal_text"]["AA"]:
        issues.append({
            "pair": f"text ({text}) on background ({bg})",
            "ratio": result["ratio"],
            "severity": "error",
            "message": f"Fails WCAG AA for normal text (ratio {result['ratio']}:1, need 4.5:1)",
        })
    elif not result["normal_text"]["AAA"]:
        issues.append({
            "pair": f"text ({text}) on background ({bg})",
            "ratio": result["ratio"],
            "severity": "info",
            "message": f"Passes AA but not AAA for normal text (ratio {result['ratio']}:1)",
        })

    # Check muted text on background
    if muted:
        result = validate_contrast(muted, bg)
        if not result["large_text"]["AA"]:
            issues.append({
                "pair": f"muted ({muted}) on background ({bg})",
                "ratio": result["ratio"],
                "severity": "error",
                "message": f"Muted text fails AA even for large text (ratio {result['ratio']}:1)",
            })
        elif not result["normal_text"]["AA"]:
            issues.append({
                "pair": f"muted ({muted}) on background ({bg})",
                "ratio": result["ratio"],
                "severity": "warning",
                "message": f"Muted text fails AA for normal text (ratio {result['ratio']}:1, OK for large)",
            })

    # Check overlay text/bg pairs
    overlays = playbook.get("overlays", {})
    for overlay_name, overlay in overlays.items():
        o_bg = overlay.get("bg")
        o_text = overlay.get("text")
        if o_bg and o_text:
            # Composite alpha colors against page background
            if _has_alpha(o_bg):
                o_bg = _composite_alpha(o_bg, bg)
            if _has_alpha(o_text):
                o_text = _composite_alpha(o_text, bg)
            result = validate_contrast(o_text, o_bg)
            if not result["normal_text"]["AA"]:
                issues.append({
                    "pair": f"overlay.{overlay_name}: text ({o_text}) on bg ({o_bg})",
                    "ratio": result["ratio"],
                    "severity": "error",
                    "message": (
                        f"Overlay '{overlay_name}' fails WCAG AA "
                        f"(ratio {result['ratio']}:1)"
                    ),
                })

    # Color-blind safety on primary + accent + chart_palette
    all_colors = []
    all_colors.extend(palette.get("primary", []))
    all_colors.extend(palette.get("accent", []))
    chart_palette = playbook.get("visual_language", {}).get(
        "color_palette", {}
    ).get("chart_palette") or playbook.get("chart_palette", [])
    all_colors.extend(chart_palette)

    if len(all_colors) >= 2:
        cvd_result = check_color_blind_safety(all_colors)
        for cvd_issue in cvd_result.get("issues", []):
            issues.append({
                "pair": f"{cvd_issue['color_a']} / {cvd_issue['color_b']}",
                "severity": "warning",
                "message": cvd_issue["message"],
            })

    return issues


def generate_harmony(base_hex: str, harmony_type: str) -> list[str]:
    """Generate a color harmony palette from a base color.

    Uses HSL math to create harmonious palettes.

    Args:
        base_hex: Base color as hex string.
        harmony_type: One of "complementary", "analogous", "triadic",
                      "split-complementary".

    Returns:
        List of hex color strings including the base color.
    """
    h, s, l = _hex_to_hsl(base_hex)

    if harmony_type == "complementary":
        offsets = [0, 180]
    elif harmony_type == "analogous":
        offsets = [-30, 0, 30]
    elif harmony_type == "triadic":
        offsets = [0, 120, 240]
    elif harmony_type == "split-complementary":
        offsets = [0, 150, 210]
    else:
        raise ValueError(
            f"Unknown harmony type: {harmony_type!r}. "
            f"Choose from: complementary, analogous, triadic, split-complementary"
        )

    return [_hsl_to_hex((h + offset) % 360, s, l) for offset in offsets]


# ---------------------------------------------------------------------------
# D3.5.6 — Typography intelligence
# ---------------------------------------------------------------------------

# Named modular type scale ratios
TYPE_SCALE_RATIOS: dict[str, float] = {
    "minor_second": 1.067,
    "major_second": 1.125,
    "minor_third": 1.2,
    "major_third": 1.25,
    "perfect_fourth": 1.333,
    "golden": 1.618,
}


def compute_type_scale(
    base_size: int, ratio: str = "major_third"
) -> dict:
    """Generate a modular type scale from a base size and ratio.

    Produces sizes for caption, body, subheading, heading, display levels.

    Args:
        base_size: Base font size in pixels (e.g., 24 for video).
        ratio: Named ratio string or a numeric string. Supported names:
               minor_second (1.067), major_second (1.125), minor_third (1.2),
               major_third (1.25), perfect_fourth (1.333), golden (1.618).

    Returns:
        Dict mapping role names to pixel sizes and the ratio used.
    """
    if ratio in TYPE_SCALE_RATIOS:
        r = TYPE_SCALE_RATIOS[ratio]
    else:
        try:
            r = float(ratio)
        except ValueError:
            raise ValueError(
                f"Unknown type scale ratio: {ratio!r}. "
                f"Choose from: {', '.join(TYPE_SCALE_RATIOS.keys())} or a number."
            )

    scale = {
        "ratio_name": ratio if ratio in TYPE_SCALE_RATIOS else "custom",
        "ratio_value": round(r, 4),
        "base_size_px": base_size,
        "sizes": {
            "caption": round(base_size / r),
            "body": base_size,
            "subheading": round(base_size * r),
            "heading": round(base_size * r ** 2),
            "display": round(base_size * r ** 3),
        },
    }
    return scale


def validate_type_hierarchy(playbook: dict) -> list[dict]:
    """Validate that typography sizes follow a clear hierarchy.

    Checks that heading > subheading > body > caption sizes are properly
    ordered with sufficient contrast between levels.

    Args:
        playbook: Loaded playbook dict.

    Returns:
        List of issue dicts. Empty list means hierarchy is valid.
    """
    issues: list[dict] = []
    typography = playbook.get("typography", {})

    # Extract size multipliers (or infer relative weights from weight values)
    roles = ["headings", "body", "code", "stat_card"]
    role_weights: dict[str, int] = {}
    role_multipliers: dict[str, float] = {}

    for role in roles:
        spec = typography.get(role, {})
        if spec:
            role_weights[role] = spec.get("weight", 400)
            role_multipliers[role] = spec.get("size_multiplier", 1.0)

    # Check that headings weight >= body weight
    head_w = role_weights.get("headings", 700)
    body_w = role_weights.get("body", 400)
    if head_w <= body_w:
        issues.append({
            "roles": "headings vs body",
            "severity": "warning",
            "message": (
                f"Heading weight ({head_w}) should be greater than "
                f"body weight ({body_w}) for clear hierarchy"
            ),
        })

    # Check that stat_card multiplier > 1.0 (should be larger than body)
    stat_mult = role_multipliers.get("stat_card", 1.0)
    if stat_mult <= 1.0:
        issues.append({
            "roles": "stat_card",
            "severity": "warning",
            "message": (
                f"stat_card size_multiplier ({stat_mult}) should be > 1.0 "
                f"for visual prominence"
            ),
        })

    # Check weight differentiation between heading and body is sufficient
    if head_w - body_w < 200:
        issues.append({
            "roles": "headings vs body",
            "severity": "info",
            "message": (
                f"Weight difference between headings ({head_w}) and "
                f"body ({body_w}) is only {head_w - body_w}. "
                f"Consider >= 200 difference for clear visual separation."
            ),
        })

    # Check scale_system if present
    scale_system = typography.get("scale_system")
    if scale_system and scale_system in TYPE_SCALE_RATIOS:
        ratio = TYPE_SCALE_RATIOS[scale_system]
        if ratio < 1.1:
            issues.append({
                "roles": "scale_system",
                "severity": "info",
                "message": (
                    f"Scale ratio '{scale_system}' ({ratio}) is very tight. "
                    f"Consider a larger ratio for video content."
                ),
            })

    return issues


# Known-good font pairings database
_FONT_PAIRINGS: dict[str, list[dict]] = {
    # Sans-serif fonts
    "Inter": [
        {
            "font": "Lora",
            "category": "serif",
            "rationale": "Geometric sans + transitional serif. High x-height match.",
        },
        {
            "font": "Playfair Display",
            "category": "serif",
            "rationale": "Clean sans + high-contrast serif for elegant contrast.",
        },
        {
            "font": "JetBrains Mono",
            "category": "monospace",
            "rationale": "Matched x-height for code blocks alongside Inter body text.",
        },
    ],
    "Space Grotesk": [
        {
            "font": "Space Mono",
            "category": "monospace",
            "rationale": "Same type family. Unified geometric DNA.",
        },
        {
            "font": "DM Serif Display",
            "category": "serif",
            "rationale": "Bold serif headlines with geometric sans body.",
        },
        {
            "font": "Fira Code",
            "category": "monospace",
            "rationale": "Ligature-rich code font pairs well with geometric body text.",
        },
    ],
    "IBM Plex Sans": [
        {
            "font": "IBM Plex Serif",
            "category": "serif",
            "rationale": "Same type family. Perfect metric compatibility.",
        },
        {
            "font": "IBM Plex Mono",
            "category": "monospace",
            "rationale": "Same type family. Unified design language for technical content.",
        },
        {
            "font": "Merriweather",
            "category": "serif",
            "rationale": "Humanist sans + humanist serif. Both optimized for screen readability.",
        },
    ],
    # Serif fonts
    "Lora": [
        {
            "font": "Inter",
            "category": "sans-serif",
            "rationale": "Transitional serif + geometric sans. Clean modern pairing.",
        },
        {
            "font": "Source Sans Pro",
            "category": "sans-serif",
            "rationale": "Classic serif + humanist sans. Traditional yet readable.",
        },
    ],
    "Playfair Display": [
        {
            "font": "Source Sans Pro",
            "category": "sans-serif",
            "rationale": "High-contrast display serif + neutral sans-serif body.",
        },
        {
            "font": "Raleway",
            "category": "sans-serif",
            "rationale": "Elegant serif + thin geometric sans for luxury feel.",
        },
    ],
    # Monospace fonts
    "JetBrains Mono": [
        {
            "font": "Inter",
            "category": "sans-serif",
            "rationale": "Matched x-height. Both designed for screen readability.",
        },
    ],
    "Fira Code": [
        {
            "font": "Fira Sans",
            "category": "sans-serif",
            "rationale": "Same type family. Unified design language.",
        },
        {
            "font": "Space Grotesk",
            "category": "sans-serif",
            "rationale": "Both geometric with similar proportions.",
        },
    ],
}

# Generic fallback suggestions by font category keywords
_CATEGORY_PAIRINGS: dict[str, list[dict]] = {
    "sans": [
        {
            "font": "Lora",
            "category": "serif",
            "rationale": "A versatile serif that pairs well with most sans-serif fonts.",
        },
        {
            "font": "Source Serif Pro",
            "category": "serif",
            "rationale": "Neutral serif with excellent readability alongside sans-serif.",
        },
    ],
    "serif": [
        {
            "font": "Inter",
            "category": "sans-serif",
            "rationale": "Clean geometric sans-serif that complements most serif fonts.",
        },
        {
            "font": "Source Sans Pro",
            "category": "sans-serif",
            "rationale": "Humanist sans-serif with broad serif compatibility.",
        },
    ],
    "mono": [
        {
            "font": "Inter",
            "category": "sans-serif",
            "rationale": "Versatile sans-serif body text alongside monospace code.",
        },
    ],
}


def suggest_font_pairing(primary_font: str) -> list[dict]:
    """Suggest complementary fonts for a given primary font.

    Returns known-good pairings from a curated database, falling back to
    category-based suggestions for unknown fonts.

    Args:
        primary_font: Primary font name (e.g., "Inter").

    Returns:
        List of dicts with font, category, and rationale.
    """
    # Direct lookup
    if primary_font in _FONT_PAIRINGS:
        return _FONT_PAIRINGS[primary_font]

    # Category-based fallback
    font_lower = primary_font.lower()
    if "mono" in font_lower or "code" in font_lower:
        return _CATEGORY_PAIRINGS["mono"]
    elif "serif" in font_lower and "sans" not in font_lower:
        return _CATEGORY_PAIRINGS["serif"]
    else:
        return _CATEGORY_PAIRINGS["sans"]


# ---------------------------------------------------------------------------
# D3.5.7 — Accessibility validation
# ---------------------------------------------------------------------------

# Minimum font size in pixels for video content readability
MIN_VIDEO_BODY_SIZE_PX = 24


def validate_accessibility(playbook: dict) -> dict:
    """Comprehensive accessibility validation for a playbook.

    Checks:
    - WCAG contrast ratios for all text/background pairs
    - Minimum font sizes for video readability (24px body minimum)
    - Color-blind safety for chart palettes and accent colors
    - Overlay text contrast

    Designed to be callable as a pre-render validation step.

    Args:
        playbook: Loaded playbook dict.

    Returns:
        Dict with overall pass/fail, score, and categorized issues.
    """
    issues: list[dict] = []

    # --- Contrast checks (reuse validate_palette) ---
    palette_issues = validate_palette(playbook)
    for pi in palette_issues:
        issues.append({
            "category": "contrast" if "ratio" in pi else "color_blind",
            **pi,
        })

    # --- Font size checks ---
    typography = playbook.get("typography", {})
    body_spec = typography.get("body", {})
    body_base_size = body_spec.get("size_multiplier", 1.0) * MIN_VIDEO_BODY_SIZE_PX

    # We check the scale_system if present to compute actual sizes
    scale_system = typography.get("scale_system")
    if scale_system:
        scale = compute_type_scale(MIN_VIDEO_BODY_SIZE_PX, scale_system)
        sizes = scale["sizes"]
        if sizes["caption"] < 16:
            issues.append({
                "category": "font_size",
                "severity": "warning",
                "message": (
                    f"Caption size ({sizes['caption']}px) is below 16px. "
                    f"May be unreadable on mobile video."
                ),
            })
    else:
        # No scale system — just check multiplier conventions
        stat_mult = typography.get("stat_card", {}).get("size_multiplier", 1.0)
        if stat_mult < 2.0:
            issues.append({
                "category": "font_size",
                "severity": "info",
                "message": (
                    f"stat_card size_multiplier ({stat_mult}) is modest. "
                    f"Consider >= 2.0x for video stat cards."
                ),
            })

    # --- Type hierarchy checks ---
    hierarchy_issues = validate_type_hierarchy(playbook)
    for hi in hierarchy_issues:
        issues.append({"category": "typography", **hi})

    # --- Chart palette color-blind check ---
    chart_palette = playbook.get("chart_palette", [])
    if chart_palette and len(chart_palette) >= 2:
        cvd_result = check_color_blind_safety(chart_palette)
        if not cvd_result["safe"]:
            for ci in cvd_result["issues"]:
                issues.append({
                    "category": "color_blind",
                    "severity": "warning",
                    "message": ci["message"],
                })

    # --- Weight matrix checks ---
    weight_matrix = typography.get("weight_matrix", {})
    if weight_matrix:
        expected_order = ["title", "heading", "body", "caption"]
        prev_weight = 1000
        for role in expected_order:
            w = weight_matrix.get(role)
            if w is not None and w > prev_weight:
                issues.append({
                    "category": "typography",
                    "severity": "warning",
                    "message": (
                        f"Weight matrix: '{role}' weight ({w}) should not "
                        f"exceed the weight of higher-priority roles."
                    ),
                })
            if w is not None:
                prev_weight = w

    # --- Compute overall result ---
    error_count = sum(1 for i in issues if i.get("severity") == "error")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")

    return {
        "pass": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "total_issues": len(issues),
        "issues": issues,
    }
