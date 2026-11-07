"""Prompt builder package for the speculative-evolution niche (AI stills only).

Public API:
  - CreatureSpec, AnatomySpec   (spec model; construct from dict or YAML)
  - PromptBuilder               (render to sdxl / zimage / klein prompts)
"""
from __future__ import annotations

from .builder import AnatomySpec, CreatureSpec, PromptBuilder

__all__ = ["AnatomySpec", "CreatureSpec", "PromptBuilder"]
