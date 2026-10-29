#!/usr/bin/env python3
"""Tests for scripts/s8_candidates.py (S8-1 licence/fit gate helper)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "s8_candidates", REPO / "scripts" / "s8_candidates.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


SAMPLE = {
    "modelId": "org/model",
    "author": "org",
    "gated": "auto",
    "pipeline_tag": "text-to-image",
    "library_name": "diffusers",
    "tags": ["license:other", "diffusers:SomePipeline", "arxiv:2402.1"],
    "lastModified": "2026-01-01T00:00:00.000Z",
    "downloads": 5,
    "cardData": {"license": "other", "license_name": "x-community-license",
                 "license_link": "https://example/LICENSE.pdf"},
    "safetensors": {"parameters": {"F32": 10, "BF16": 20}, "total": 30},
    "config": {"diffusers": {"_class_name": "SomePipeline"}},
    "siblings": [
        {"rfilename": "README.md", "size": 10},
        {"rfilename": "unet/diffusion_pytorch_model.safetensors", "size": 1000},
        {"rfilename": "vae/diffusion_pytorch_model.fp16.safetensors", "size": 500},
        {"rfilename": "model.safetensors.index.json", "size": 7},
    ],
}


def test_parse_facts_extracts_the_gate_fields():
    f = mod.parse_facts("org/model", SAMPLE)
    assert f["gated"] == "auto"
    assert f["license"] == "other"
    assert f["license_name"] == "x-community-license"
    assert f["license_link"].endswith("LICENSE.pdf")
    assert f["pipeline_class"] == "SomePipeline"
    assert f["parameters_total"] == 30
    assert f["parameters_by_dtype"]["BF16"] == 20
    # only real weight files count, and the total is their sum
    assert f["weight_bytes_total"] == 1500
    assert [w["file"] for w in f["weight_files_top"]] == [
        "unet/diffusion_pytorch_model.safetensors",
        "vae/diffusion_pytorch_model.fp16.safetensors",
    ]


def test_pipeline_class_falls_back_to_the_diffusers_tag():
    meta = dict(SAMPLE)
    meta["config"] = {}
    f = mod.parse_facts("org/model", meta)
    assert f["pipeline_class"] == "SomePipeline"


def test_missing_safetensors_metadata_does_not_crash():
    meta = dict(SAMPLE)
    meta.pop("safetensors")
    f = mod.parse_facts("org/model", meta)
    assert f["parameters_total"] is None  # unknown, not zero
    assert f["weight_bytes_total"] == 1500


def test_card_statements_keep_dtype_and_step_evidence():
    card = ("license: openrail++\n\n"
            "Use torch.float16 for the pipeline.\n\n"
            "Ensure sampler uses trailing timesteps and 8 inference steps "
            "with guidance 0.\n\n"
            "| a | b |\n")
    out = mod.card_statements(card)
    assert any("float16" in s for s in out)
    assert any("trailing" in s for s in out)
    assert not any(s.startswith("|") for s in out)


def test_commercial_clauses_find_licence_sentences():
    text = ("Apache License, Version 2.0. Subject to the terms and conditions "
            "of this License, each Contributor hereby grants to You a "
            "perpetual, worldwide, non-exclusive, no-charge, royalty-free, "
            "irrevocable copyright license to reproduce, prepare Derivative "
            "Works of, publicly display, publicly perform, sublicense, and "
            "distribute the Work and such Derivative Works in Source or "
            "Object form.")
    out = mod.commercial_clauses(text)
    assert any("royalty-free" in s for s in out)
