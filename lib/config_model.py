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
    """Budget governance settings. Enforced by lib/budget_gate.py.

    `mode` governs the aggregate daily total ONLY. The two approval
    safeguards below are independent of it and are evaluated in every mode.
    """

    # observe = record only | warn = flag and proceed | cap = hard stop
    mode: BudgetMode = BudgetMode.WARN
    # Maximum spend per `period`, in the `timezone` below.
    total_usd: float = 10.0
    # Only "daily" is implemented; any other value fails closed rather than
    # silently applying daily semantics.
    period: str = "daily"
    # "system_local" or an IANA name (e.g. "America/New_York"). Defines the
    # midnight boundary between daily buckets; unresolvable values fail closed.
    timezone: str = "system_local"
    # warn-mode planning holdback. cap enforces the true daily total instead,
    # so an exact-cap request is allowed.
    reserve_pct: float = 0.10
    # Independent safeguard: refuse any single call estimated above this.
    # None (or <= 0) disables it. Not coupled to `mode`.
    single_action_approval_usd: Optional[float] = 0.50
    # Independent safeguard: refuse the first paid use of each tool.
    # Not coupled to `mode`.
    require_approval_for_new_paid_tool: bool = True


class CheckpointConfig(BaseModel):
    policy: CheckpointPolicy = CheckpointPolicy.GUIDED
    storage_dir: str = "pipeline"


class OutputConfig(BaseModel):
    default_format: str = "mp4"
    default_codec: str = "libx264"
    default_audio_codec: str = "aac"
    default_resolution: str = "1920x1080"
    default_fps: int = 30
    default_crf: int = 23


class PathsConfig(BaseModel):
    pipeline_dir: str = "pipeline"
    library_dir: str = "library"
    styles_dir: str = "styles"
    skills_dir: str = "skills"
    output_dir: str = "output"


class OpenMontageConfig(BaseModel):
    """Top-level runtime configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "OpenMontageConfig":
        """Load config from YAML file. Falls back to defaults if file missing."""
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config.yaml"

        if config_path.exists():
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
            return cls.model_validate(raw)

        return cls()

    def resolve_path(self, key: str, project_root: Optional[Path] = None) -> Path:
        """Resolve a relative path from PathsConfig against project root."""
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        value = getattr(self.paths, key)
        return (project_root / value).resolve()
