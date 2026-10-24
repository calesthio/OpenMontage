#!/usr/bin/env python3
"""Red/green tests for scripts/image_engine.py (P1).

The CLI is how the owner re-locks the model once they have filled the blind
pack. It must never guess: no filled CSV -> the advisory pick stays, a TIE ->
nothing is written, a filled CSV -> the owner's winner is locked as
OWNER_CONFIRMED.

No network, no Kaggle, no secrets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import image_engine  # noqa: E402

CONFIG_PATH = ROOT / "config" / "image_engine.json"


def _config_copy(tmp_path, **overrides):
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    doc.update(overrides)
    p = tmp_path / "image_engine.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def _pack(tmp_path, rows):
    pack = tmp_path / "projects" / "s8_blind"
    pack.mkdir(parents=True)
    (pack / "mapping.json").write_text(json.dumps({
        "scenes": {
            "s01": {"A": "sdxl-lightning", "B": "klein"},
            "s02": {"A": "sdxl-lightning", "B": "klein"},
        },
    }), encoding="utf-8")
    (pack / "results.csv").write_text(
        "scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,comment\n"
        + rows, encoding="utf-8")
    return tmp_path


def test_status_prints_the_lock(capsys):
    assert image_engine.cmd_status(_args(config=str(CONFIG_PATH))) == 0
    out = capsys.readouterr().out
    assert "model       : klein" in out
    assert "status      : OWNER_GATED" in out
    assert "sdxl-lightning" in out


def test_project_prints_the_gpu_minutes(capsys):
    assert image_engine.cmd_project(_args(config=str(CONFIG_PATH), count=100)) == 0
    out = capsys.readouterr().out
    assert "41.15" in out   # klein: 24.691 s/image x 100
    assert "6.57" in out    # sdxl-lightning: 3.943 s/image x 100
    assert "8.52" in out    # dreamshaper: 5.112 s/image x 100
    assert "69.0" in out    # sdxl: 41.4 s/image x 100


def test_select_without_a_filled_csv_leaves_the_config_alone(tmp_path, capsys):
    cfg = _config_copy(tmp_path)
    before = cfg.read_text(encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "projects" / "s8_blind").mkdir(parents=True)
    (repo / "projects" / "s8_blind" / "results.csv").write_text(
        "scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,comment\n"
        "s01,,,,,\n", encoding="utf-8")
    assert image_engine.cmd_select(_args(config=str(cfg),
                                          repo_root=str(repo))) == 0
    out = capsys.readouterr().out
    assert "OWNER_GATED" in out
    assert cfg.read_text(encoding="utf-8") == before


def test_select_writes_the_owners_winner(tmp_path, capsys):
    cfg = _config_copy(tmp_path)
    repo = _pack(tmp_path, "s01,A,B,yes,no,x\ns02,A,B,yes,no,y\n")
    assert image_engine.cmd_select(_args(config=str(cfg), repo_root=str(repo),
                                          write=True)) == 0
    out = capsys.readouterr().out
    assert "OWNER_CONFIRMED" in out
    doc = json.loads(cfg.read_text(encoding="utf-8"))
    assert doc["model"] == "sdxl-lightning"
    assert doc["status"] == "OWNER_CONFIRMED"
    # the lock fields follow the new model
    assert doc["steps"] == 8
    assert doc["guidance"] == 0.0
    assert doc["prompt_variant"] == "A"


def test_select_refuses_to_resolve_a_tie(tmp_path, capsys):
    cfg = _config_copy(tmp_path)
    before = cfg.read_text(encoding="utf-8")
    repo = _pack(tmp_path, "s01,A,B,yes,no,x\ns02,B,A,no,yes,y\n")
    assert image_engine.cmd_select(_args(config=str(cfg), repo_root=str(repo),
                                          write=True)) == 0
    out = capsys.readouterr().out
    assert "TIE" in out
    assert cfg.read_text(encoding="utf-8") == before


def _args(**kwargs):
    import argparse
    ns = argparse.Namespace(config=str(CONFIG_PATH), repo_root=str(ROOT),
                             count=100, write=False)
    for key, value in kwargs.items():
        setattr(ns, key, value)
    return ns
