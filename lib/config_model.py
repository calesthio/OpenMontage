"""Runtime configuration model for OpenMontage.

Loads config.yaml, merges with env overrides, and provides typed access.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class BudgetMode(str, Enum):
    OBSERVE = "observe"
    WARN = "warn"
    CAP = "cap"


class CheckpointPolicy(str, Enum):
    GUIDED = "guided"
    MANUAL_ALL = "manual_all"
    AUTO_NONCREATIVE = "auto_noncreative"


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class BudgetConfig(BaseModel):
    mode: BudgetMode = BudgetMode.WARN
    total_usd: float = 10.0
    reserve_pct: float = 0.10
    single_action_approval_usd: float = 0.50
    require_approval_for_new_paid_tool: bool = True


class CheckpointConfig(BaseModel):
    # Read by lib.checkpoint.resolve_checkpoint_policy. Checkpoints themselves
    # always live under lib.paths.PROJECTS_DIR/<project_id>/.
    policy: CheckpointPolicy = CheckpointPolicy.GUIDED


class OutputConfig(BaseModel):
    default_format: str = "mp4"
    default_codec: str = "libx264"
    default_audio_codec: str = "aac"
    default_resolution: str = "1920x1080"
    default_fps: int = 30
    default_crf: int = 23


class OpenMontageConfig(BaseModel):
    """Top-level runtime configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "OpenMontageConfig":
        """Load config from YAML file. Falls back to defaults if file missing."""
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config.yaml"

        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return cls.model_validate(raw)

        return cls()
