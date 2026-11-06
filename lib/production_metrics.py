"""Production metrics collector for OpenMontage factory runs.

Records operational metrics (counts, durations, sizes, cost when explicitly
provided). Never invents prices: cost fields default to None and are only
populated from real cost-ledger data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ProductionMetrics:
    version: str = "1.0"
    project_id: str = ""
    run_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    production_duration_s: float | None = None
    image_count: int = 0
    regeneration_count: int = 0
    sentence_count: int = 0
    render_duration_s: float | None = None
    output_file_size_bytes: int | None = None
    output_duration_s: float | None = None
    cost_usd: float | None = None
    cost_per_finished_minute_usd: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def finalize(self, *, finished_at: str | None = None) -> None:
        self.finished_at = finished_at or datetime.now(timezone.utc).isoformat()
        if self.started_at:
            try:
                s = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
                f = datetime.fromisoformat(self.finished_at.replace("Z", "+00:00"))
                self.production_duration_s = (f - s).total_seconds()
            except Exception:  # noqa: BLE001
                pass
        if self.cost_usd is not None and self.output_duration_s and self.output_duration_s > 0:
            self.cost_per_finished_minute_usd = self.cost_usd / (self.output_duration_s / 60.0)


class MetricsCollector:
    """Collect metrics incrementally; write JSON at the end."""

    def __init__(self, project_id: str = "", run_id: str = "") -> None:
        self.metrics = ProductionMetrics(project_id=project_id, run_id=run_id)

    def start(self) -> None:
        self.metrics.started_at = datetime.now(timezone.utc).isoformat()

    def record_images(self, count: int, regenerations: int = 0) -> None:
        self.metrics.image_count = int(count)
        self.metrics.regeneration_count = int(regenerations)

    def record_sentences(self, count: int) -> None:
        self.metrics.sentence_count = int(count)

    def record_render(self, *, duration_s: float | None, file_size_bytes: int | None,
                      output_duration_s: float | None) -> None:
        self.metrics.render_duration_s = duration_s
        self.metrics.output_file_size_bytes = file_size_bytes
        self.metrics.output_duration_s = output_duration_s

    def record_cost(self, cost_usd: float | None) -> None:
        # Never invent: only set when a real value is provided.
        self.metrics.cost_usd = cost_usd

    def finalize(self) -> ProductionMetrics:
        self.metrics.finalize()
        return self.metrics

    def save(self, path: str | Path) -> None:
        import json
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.metrics.to_dict(), indent=2) + "\n", encoding="utf-8")
