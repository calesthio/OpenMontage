"""Performance metrics collection for OpenMontage tools.

Collects and tracks execution time, cost, success rate, and other metrics
for tool executions to support monitoring and optimization.
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class MetricType(Enum):
    """Type of metric being recorded."""
    EXECUTION_TIME = "execution_time"
    COST = "cost"
    SUCCESS = "success"
    RETRY = "retry"


@dataclass
class Metric:
    """Single metric record."""
    tool_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collector for tool performance metrics."""
    
    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.metrics: list[Metric] = []
        self.storage_path = storage_path
    
    def record(self, metric: Metric) -> None:
        """Record a single metric.
        
        Args:
            metric: The metric to record
        """
        self.metrics.append(metric)
        if self.storage_path:
            self._persist()
    
    def record_execution(
        self,
        tool_name: str,
        duration_seconds: float,
        success: bool,
        cost_usd: float = 0.0,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """Record a complete tool execution with multiple metrics.
        
        Args:
            tool_name: Name of the tool
            duration_seconds: Execution time in seconds
            success: Whether the execution succeeded
            cost_usd: Cost in USD (optional)
            metadata: Additional metadata (optional)
        """
        meta = metadata or {}
        
        # Record execution time
        self.record(Metric(
            tool_name=tool_name,
            metric_type=MetricType.EXECUTION_TIME,
            value=duration_seconds,
            metadata=meta.copy()
        ))
        
        # Record success
        self.record(Metric(
            tool_name=tool_name,
            metric_type=MetricType.SUCCESS,
            value=1.0 if success else 0.0,
            metadata=meta.copy()
        ))
        
        # Record cost if applicable
        if cost_usd > 0:
            self.record(Metric(
                tool_name=tool_name,
                metric_type=MetricType.COST,
                value=cost_usd,
                metadata=meta.copy()
            ))
    
    def get_summary(self, tool_name: Optional[str] = None) -> dict[str, Any]:
        """Get a summary of metrics.
        
        Args:
            tool_name: Filter by tool name (optional)
            
        Returns:
            Summary dictionary with aggregate metrics
        """
        metrics = self.metrics
        if tool_name:
            metrics = [m for m in metrics if m.tool_name == tool_name]
        
        # Calculate aggregates
        total_executions = len([m for m in metrics if m.metric_type == MetricType.SUCCESS])
        total_cost = sum(m.value for m in metrics if m.metric_type == MetricType.COST)
        
        success_metrics = [m for m in metrics if m.metric_type == MetricType.SUCCESS]
        success_rate = sum(m.value for m in success_metrics) / max(1, len(success_metrics)) if success_metrics else 0.0
        
        time_metrics = [m for m in metrics if m.metric_type == MetricType.EXECUTION_TIME]
        avg_execution_time = sum(m.value for m in time_metrics) / max(1, len(time_metrics)) if time_metrics else 0.0
        max_execution_time = max(m.value for m in time_metrics) if time_metrics else 0.0
        min_execution_time = min(m.value for m in time_metrics) if time_metrics else 0.0
        
        return {
            "total_executions": total_executions,
            "total_cost": total_cost,
            "success_rate": success_rate,
            "avg_execution_time": avg_execution_time,
            "max_execution_time": max_execution_time,
            "min_execution_time": min_execution_time,
            "metrics_count": len(metrics),
        }
    
    def _persist(self) -> None:
        """Persist metrics to storage file."""
        if not self.storage_path:
            return
        
        data = []
        for metric in self.metrics:
            data.append({
                "tool_name": metric.tool_name,
                "metric_type": metric.metric_type.value,
                "value": metric.value,
                "timestamp": metric.timestamp.isoformat(),
                "metadata": metric.metadata,
            })
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    
    def clear(self) -> None:
        """Clear all collected metrics."""
        self.metrics = []


# Global collector instance
_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get or create the global metrics collector.
    
    Returns:
        The global MetricsCollector instance
    """
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def set_storage_path(path: Path) -> None:
    """Set the storage path for the global collector.
    
    Args:
        path: Path to store metrics
    """
    collector = get_collector()
    collector.storage_path = path