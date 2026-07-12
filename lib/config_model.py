"""Runtime configuration model for OpenMontage.

Loads config.yaml and provides typed access via pydantic models.

NOTE — test-fixture only: outside of ``BudgetMode`` (consumed by
``tools/cost_tracker.py`` and ``server/app/runner/stage_runner.py``), nothing
in this module or in config.yaml is read by production code. The
orchestration state machine (pipeline manifests + stage director skills) does
not merge in ``OpenMontageConfig``'s budget/checkpoint/output/paths knobs;
editing config.yaml today only affects the contract tests that exercise
``OpenMontageConfig.load()``. Treat this as a fixture/spec for a config
surface that hasn't been wired into the runner, not a live control panel.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


class BudgetMode(str, Enum):
    OBSERVE = "observe"
    WARN = "warn"
    CAP = "cap"


class CheckpointPolicy(str, Enum):
    """Declared checkpoint-gating strategies.

    Not currently read by any gating code (``lib/checkpoint.py`` and the
    Backlot board both key off each pipeline stage's own
    ``human_approval_default``). ``CheckpointConfig.policy`` and manifests'
    ``default_checkpoint_policy`` field carry this value but nothing consumes
    it yet — it does not control real gating behavior.
    """

    GUIDED = "guided"
    MANUAL_ALL = "manual_all"
    AUTO_NONCREATIVE = "auto_noncreative"


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "anthropic"
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class BudgetConfig(BaseModel):
    """Budget defaults.

    NOTE — not the only copy of these numbers: ``tools/cost_tracker.py``'s
    ``CostTracker.__init__`` re-literals this same set of defaults instead of
    building them from this model, and ``server/app/runner/stage_runner.py``
    separately hardcodes its own effectively-unlimited (1e12) sentinels. All
    three can drift independently. Collapsing ``CostTracker``'s defaults onto
    ``BudgetConfig.model_fields`` (or accepting a ``BudgetConfig`` instance)
    would fix this but requires editing tools/cost_tracker.py, which is
    outside this module's scope — flagged here as recommended follow-up.
    """

    model_config = ConfigDict(extra="forbid")

    mode: BudgetMode = BudgetMode.WARN
    total_usd: float = 10.0
    reserve_pct: float = 0.10
    single_action_approval_usd: float = 0.50
    require_approval_for_new_paid_tool: bool = True


class CheckpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: CheckpointPolicy = CheckpointPolicy.GUIDED
    storage_dir: str = "pipeline"


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_format: str = "mp4"
    default_codec: str = "libx264"
    default_audio_codec: str = "aac"
    default_resolution: str = "1920x1080"
    default_fps: int = 30
    default_crf: int = 23


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_dir: str = "pipeline"
    library_dir: str = "library"
    styles_dir: str = "styles"
    skills_dir: str = "skills"
    output_dir: str = "output"


class OpenMontageConfig(BaseModel):
    """Top-level runtime configuration.

    See module docstring: this is currently a test-fixture surface, not a
    live production config loaded by the runner.
    """

    model_config = ConfigDict(extra="forbid")

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
