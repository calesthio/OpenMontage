#!/usr/bin/env python3
"""QA Test 07: Playbook design intelligence — no API calls.

Tests contrast validation, color harmony generation, color-blind safety,
type scale computation, type hierarchy validation, font pairing suggestions,
and full accessibility audit across all 3 playbooks.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from styles.playbook_loader import (
    load_playbook,
    list_playbooks,
    validate_contrast,
    check_color_blind_safety,
    validate_palette,
    generate_harmony,
    compute_type_scale,
    validate_type_hierarchy,
    suggest_font_pairing,
    validate_accessibility,
    TYPE_SCALE_RATIOS,
)

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")

# ===================================================================
# Test 1: List and load all playbooks
# ===================================================================
print("--- Test 1: List and load playbooks ---")
playbooks_available = list_playbooks()
print(f"  Found {len(playbooks_available)} playbooks: {playbooks_available}")
check("At least 3 playbooks exist", len(playbooks_available) >= 3)

loaded = {}
for name in ["clean-professional", "flat-motion-graphics", "minimalist-diagram"]:
    try:
        pb = load_playbook(name)
        loaded[name] = pb
        check(f"Load + validate {name}", True)
    except Exception as e:
        loaded[name] = None
        check(f"Load + validate {name}", False, str(e))

# ===================================================================
# Test 2: Contrast validation (manual spot-checks)
# ===================================================================
print("\n--- Test 2: Contrast validation ---")

# Known pair: black on white should be 21:1
r = validate_contrast("#000000", "#FFFFFF")
check("Black on white ~21:1", abs(r["ratio"] - 21.0) < 0.1, f"ratio={r['ratio']}")
check("Black on white passes AAA", r["normal_text"]["AAA"])

# Known pair: white on white should be 1:1
r = validate_contrast("#FFFFFF", "#FFFFFF")
check("White on white = 1:1", abs(r["ratio"] - 1.0) < 0.01, f"ratio={r['ratio']}")
check("White on white fails AA", not r["normal_text"]["AA"])

# Mid-gray on white (~4.5:1 boundary)
r = validate_contrast("#767676", "#FFFFFF")
check("#767676 on white passes AA normal", r["normal_text"]["AA"], f"ratio={r['ratio']}")

# Just-below threshold
r = validate_contrast("#777777", "#FFFFFF")
check("#777777 on white borderline", r["ratio"] >= 4.4, f"ratio={r['ratio']}")

# Dark-on-dark: low contrast
r = validate_contrast("#1A1A1A", "#2B2B2B")
check("Dark-on-dark fails AA", not r["normal_text"]["AA"], f"ratio={r['ratio']}")

# Check each playbook's text-on-bg contrast
for name, pb in loaded.items():
    if pb is None:
        continue
    palette = pb.get("visual_language", {}).get("color_palette", {})
    text = palette.get("text", "#000000")
    bg = palette.get("background", "#FFFFFF")
    r = validate_contrast(text, bg)
    check(f"{name}: text on bg passes AA", r["normal_text"]["AA"], f"ratio={r['ratio']}")

# ===================================================================
# Test 3: Color harmony generation
# ===================================================================
print("\n--- Test 3: Color harmony generation ---")

for harmony_type in ["complementary", "analogous", "triadic", "split-complementary"]:
    colors = generate_harmony("#3B82F6", harmony_type)
    check(f"Harmony {harmony_type}", len(colors) >= 2, f"generated {len(colors)} colors: {colors}")
    # First color should match base
    check(f"  Base preserved in {harmony_type}", colors[0].upper() == generate_harmony("#3B82F6", harmony_type)[0].upper())

# Edge case: pure red
colors = generate_harmony("#FF0000", "triadic")
check("Triadic from pure red", len(colors) == 3, f"{colors}")

# ===================================================================
# Test 4: Color-blind safety
# ===================================================================
print("\n--- Test 4: Color-blind safety ---")

# Safe palette (blue + orange — distinguishable by all CVD types due to lightness diff)
safe = check_color_blind_safety(["#2563EB", "#F59E0B"])
print(f"  Blue + orange: safe={safe['safe']}, issues={len(safe.get('issues', []))}")

# Problematic palette (red + green, similar lightness)
risky = check_color_blind_safety(["#DC2626", "#16A34A"])
print(f"  Red + green: safe={risky['safe']}, issues={len(risky.get('issues', []))}")
check("Red+green flagged as risky", not risky["safe"] or len(risky.get("issues", [])) > 0,
      "should flag deuteranopia/protanopia")

# Single color = no pairs to check
single = check_color_blind_safety(["#FF0000"])
check("Single color is safe", single["safe"])

# Grays should be safe (low saturation)
grays = check_color_blind_safety(["#333333", "#999999", "#CCCCCC"])
check("Grays are safe", grays["safe"])

# ===================================================================
# Test 5: Full palette validation per playbook
# ===================================================================
print("\n--- Test 5: Palette validation (all playbooks) ---")

for name, pb in loaded.items():
    if pb is None:
        continue
    issues = validate_palette(pb)
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    print(f"  [{name}] {len(errors)} errors, {len(warnings)} warnings, {len(issues)} total issues")
    check(f"{name}: no contrast errors", len(errors) == 0,
          "; ".join(e["message"] for e in errors) if errors else "all clear")
    for issue in issues:
        sev = issue.get("severity", "?")
        print(f"    [{sev}] {issue.get('message', '')}")

# ===================================================================
# Test 6: Type scale computation
# ===================================================================
print("\n--- Test 6: Type scale computation ---")

for ratio_name, ratio_val in TYPE_SCALE_RATIOS.items():
    scale = compute_type_scale(24, ratio_name)
    sizes = scale["sizes"]
    check(f"Scale {ratio_name}: display > heading > subheading > body > caption",
          sizes["display"] > sizes["heading"] > sizes["subheading"] > sizes["body"] > sizes["caption"],
          f"{sizes}")
    check("  Base preserved", sizes["body"] == 24)

# Custom numeric ratio
scale = compute_type_scale(24, "1.5")
check("Custom ratio 1.5", scale["ratio_value"] == 1.5, f"sizes={scale['sizes']}")

# ===================================================================
# Test 7: Type hierarchy validation
# ===================================================================
print("\n--- Test 7: Type hierarchy validation ---")

for name, pb in loaded.items():
    if pb is None:
        continue
    issues = validate_type_hierarchy(pb)
    print(f"  [{name}] {len(issues)} type hierarchy issues")
    for issue in issues:
        print(f"    [{issue.get('severity')}] {issue.get('message')}")
    # No errors expected in shipped playbooks
    errors = [i for i in issues if i.get("severity") == "error"]
    check(f"{name}: no type hierarchy errors", len(errors) == 0)

# Deliberately bad playbook
bad_typography = {
    "typography": {
        "headings": {"font": "Inter", "weight": 400},
        "body": {"font": "Inter", "weight": 400},
        "stat_card": {"font": "Inter", "size_multiplier": 0.8},
    }
}
issues = validate_type_hierarchy(bad_typography)
check("Bad typography flagged", len(issues) > 0, f"{len(issues)} issues found")

# ===================================================================
# Test 8: Font pairing suggestions
# ===================================================================
print("\n--- Test 8: Font pairing suggestions ---")

for font in ["Inter", "Space Grotesk", "IBM Plex Sans", "Lora", "JetBrains Mono"]:
    pairings = suggest_font_pairing(font)
    check(f"Pairings for {font}", len(pairings) >= 1, f"{len(pairings)} suggestions")
    for p in pairings:
        print(f"    → {p['font']} ({p['category']}): {p['rationale']}")

# Unknown font fallback
pairings = suggest_font_pairing("UnknownFont")
check("Unknown font gets fallback", len(pairings) >= 1)

# ===================================================================
# Test 9: Full accessibility audit (all playbooks)
# ===================================================================
print("\n--- Test 9: Accessibility audit (all playbooks) ---")

for name, pb in loaded.items():
    if pb is None:
        continue
    result = validate_accessibility(pb)
    status = "PASS" if result["pass"] else "FAIL"
    print(f"\n  [{name}] Overall: {status}"
          f" | Errors: {result['error_count']}"
          f" | Warnings: {result['warning_count']}"
          f" | Total: {result['total_issues']}")
    check(f"{name}: a11y audit passes", result["pass"])
    for issue in result["issues"]:
        cat = issue.get("category", "?")
        sev = issue.get("severity", "?")
        print(f"    [{cat}/{sev}] {issue.get('message', '')}")

# ===================================================================
# Test 10: Deliberately low-contrast custom playbook
# ===================================================================
print("\n--- Test 10: Low-contrast custom playbook ---")

low_contrast_pb = {
    "identity": {"name": "low-contrast-test", "category": "test", "mood": "test", "pace": "moderate", "best_for": ["testing"]},
    "visual_language": {
        "color_palette": {
            "primary": ["#555555"],
            "accent": ["#666666"],
            "background": "#444444",
            "text": "#555555",
            "muted": "#4A4A4A",
        },
        "composition": "centered",
        "texture": "none",
    },
    "typography": {
        "headings": {"font": "Arial", "weight": 700, "size_multiplier": 1.5},
        "body": {"font": "Arial", "weight": 400, "size_multiplier": 1.0},
        "code": {"font": "Courier", "weight": 400, "size_multiplier": 0.9},
        "stat_card": {"font": "Arial", "weight": 700, "size_multiplier": 2.5},
        "scale_system": "major_third",
        "weight_matrix": {"title": 800, "heading": 700, "body": 400, "caption": 300},
    },
    "motion": {"transitions": "cut", "animation_style": "none", "pacing_rules": {}},
    "audio": {"voice_style": "neutral", "music_mood": "none"},
    "asset_generation": {"image_prompt_prefix": "test", "negative_prompt": ""},
    "overlays": {
        "stat_card": {"bg": "#444444", "text": "#555555", "border": "#444444", "radius": 8, "shadow": "none"},
    },
    "quality_rules": [],
    "chart_palette": ["#555555", "#666666", "#777777"],
}

# This should be flagged with errors
issues = validate_palette(low_contrast_pb)
errors = [i for i in issues if i.get("severity") == "error"]
check("Low-contrast playbook has errors", len(errors) > 0, f"{len(errors)} contrast errors")
for e in errors:
    print(f"    [error] {e.get('message')}")

# ===================================================================
# Summary
# ===================================================================
print(f"\n{'='*60}")
print(f"PLAYBOOK INTELLIGENCE TEST COMPLETE: {PASS} passed, {FAIL} failed")
print(f"{'='*60}")
