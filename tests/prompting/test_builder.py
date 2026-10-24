"""Tests for the speculative-evolution prompt builder (tools/prompting).

stdlib + PyYAML only. No network.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.prompting import (  # noqa: E402
    AnatomySpec,
    CreatureSpec,
    PromptBuilder,
)

SPEC = CreatureSpec(
    subject="vent grazer",
    anatomy=AnatomySpec(
        limb_count=6, eye_count=2, horn_count=0,
        dominant_features=["long neck", "spade-like forelimbs"],
    ),
    environment="on a hydrothermal vent chimney in a frozen alien ocean",
    light="bioluminescent vent glow and faint bioluminescent lime",
    style="flat-vector field-guide plate",
    palette={"deep teal": "#14455C", "bioluminescent lime": "#A8E06F"},
    camera="rule-of-thirds, copy space",
    constraints={"no_text": True, "no_people": True, "no_logos": True,
                 "not_photorealistic": True, "silhouette_first": True},
)


def _build(target, variant, negation_style=False):
    return PromptBuilder(seed=4000).build(target, variant, SPEC, negation_style)


# ---- determinism ----
def test_determinism_same_inputs_same_output():
    a = _build("sdxl", "A")
    b = _build("sdxl", "A")
    assert a == b
    assert a["prompt"] == b["prompt"]
    assert a["negative_prompt"] == b["negative_prompt"]


def test_determinism_across_targets_stable():
    outs = [_build(t, "B") for t in ("sdxl", "zimage", "klein")]
    outs2 = [_build(t, "B") for t in ("sdxl", "zimage", "klein")]
    assert outs == outs2


# ---- variants ----
def test_variants_a_b_c_distinct():
    pa = _build("klein", "A")["prompt"]
    pb = _build("klein", "B")["prompt"]
    pc = _build("klein", "C")["prompt"]
    assert pa != pb != pc


# ---- anatomy counts always present ----
def test_anatomy_counts_present_all_targets_variants():
    for target in ("sdxl", "zimage", "klein"):
        for variant in ("A", "B", "C"):
            prompt = _build(target, variant)["prompt"]
            assert "6 limbs" in prompt, (target, variant, prompt)
            assert "2 eyes" in prompt, (target, variant, prompt)
            assert "0 horns" in prompt, (target, variant, prompt)


# ---- word order: anatomy first in C ----
def test_klein_c_anatomy_in_first_sentence():
    prompt = _build("klein", "C")["prompt"]
    first_sentence = prompt.split(". ")[0]
    assert "6 limbs" in first_sentence, first_sentence
    assert "2 eyes" in first_sentence, first_sentence


def test_sdxl_c_anatomy_first():
    prompt = _build("sdxl", "C")["prompt"]
    counts = SPEC.anatomy.counts_line()  # "6 limbs, 2 eyes, 0 horns"
    assert prompt.startswith(counts + ";"), prompt


# ---- no negative_prompt for zimage/klein ----
def test_zimage_no_negative_prompt():
    out = _build("zimage", "B")
    assert out["negative_prompt"] is None
    assert out["guidance_scale"] == 0.0
    assert out["steps"] == 9


def test_klein_no_negative_prompt():
    out = _build("klein", "B")
    assert out["negative_prompt"] is None
    assert out["steps"] == 4


# ---- sdxl has separate negative prompt ----
def test_sdxl_negative_prompt_present():
    out = _build("sdxl", "A")
    assert out["negative_prompt"] is not None
    for term in ("extra limbs", "fused legs", "duplicate subject", "text",
                 "watermark", "photorealism"):
        assert term in out["negative_prompt"], out["negative_prompt"]
    assert out["guidance_scale"] == 7.5
    assert out["steps"] == 50


# ---- style stated first for zimage ----
def test_zimage_style_first():
    prompt = _build("zimage", "B")["prompt"]
    assert prompt.startswith("A flat-vector field-guide plate"), prompt


# ---- no real people / brands / logos allowed ----
def test_subject_with_real_person_rejected():
    bad = CreatureSpec(
        subject="Elon Musk vent grazer",
        anatomy=AnatomySpec(limb_count=6, eye_count=2, horn_count=0),
        environment="vent", light="glow", style="flat-vector",
    )
    try:
        PromptBuilder().build("sdxl", "A", bad)
    except ValueError as e:
        assert "elon musk" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for real person in subject")


def test_subject_with_brand_rejected():
    bad = CreatureSpec(
        subject="nike vent grazer",
        anatomy=AnatomySpec(limb_count=6, eye_count=2, horn_count=0),
        environment="vent", light="glow", style="flat-vector",
    )
    try:
        PromptBuilder().build("sdxl", "A", bad)
    except ValueError as e:
        assert "nike" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for brand in subject")


def test_rendered_prompt_excludes_deny_terms():
    out = _build("sdxl", "A")
    for term in ("elon musk", "nike", "disney", "coca-cola"):
        assert term not in out["prompt"].lower(), out["prompt"]
    assert term not in (out["negative_prompt"] or "").lower()


# ---- negation vs positive switch for "no text" ----
def test_negation_style_uses_exclusions():
    out = _build("klein", "B", negation_style=True)
    assert "no text" in out["prompt"]
    assert "no watermark" in out["prompt"]
    assert "clean image without text" not in out["prompt"]


def test_positive_style_uses_inclusions():
    out = _build("klein", "B", negation_style=False)
    assert "clean image without text" in out["prompt"]
    assert "text-free" in out["prompt"]


# ---- output length bounds ----
def test_output_length_bounds():
    for target in ("sdxl", "zimage", "klein"):
        for variant in ("A", "B", "C"):
            prompt = _build(target, variant)["prompt"]
            assert PromptBuilder.MIN_PROMPT_LEN <= len(prompt) <= PromptBuilder.MAX_PROMPT_LEN, (
                target, variant, len(prompt), prompt)


# ---- unknown target / variant rejected ----
def test_unknown_target_rejected():
    try:
        PromptBuilder().build("notamodel", "A", SPEC)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown target")


def test_unknown_variant_rejected():
    try:
        PromptBuilder().build("sdxl", "Z", SPEC)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown variant")


# ---- YAML loading ----
def test_from_yaml_roundtrip():
    yaml_text = (
        "subject: ice burrower\n"
        "anatomy:\n"
        "  limb_count: 0\n"
        "  eye_count: 0\n"
        "  horn_count: 0\n"
        "  dominant_features: [tapered head, segmented body]\n"
        "environment: deep ocean sediment\n"
        "light: dim bioluminescence\n"
        "style: flat-vector field-guide plate\n"
    )
    spec = CreatureSpec.from_yaml(yaml_text)
    assert spec.subject == "ice burrower"
    assert spec.anatomy.limb_count == 0
    assert spec.anatomy.dominant_features == ["tapered head", "segmented body"]
    out = PromptBuilder().build("klein", "A", spec)
    assert "0 limbs" in out["prompt"]
