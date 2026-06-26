"""Telemetry — Prometheus metrics for the Digital Twin.

Every component sends telemetry: CPU, memory, latency, error rates.
The Digital Twin uses this data to build simulated production environments.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional
from collections import defaultdict

import structlog
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
)

from backend.communication.message_types import TelemetryData

logger = structlog.get_logger(__name__)


class TelemetryCollector:
    """Collects and exposes metrics from all civilization components.

    Provides:
    - Per-component metrics (CPU, memory, latency, errors)
    - Aggregate system metrics
    - Prometheus-compatible export
    - Feeds the Digital Twin simulation
    """

    def __init__(self):
        self._registry = CollectorRegistry()
        self._component_data: dict[str, list[TelemetryData]] = defaultdict(list)
        self._latest: dict[str, TelemetryData] = {}

        # Prometheus metrics
        self.cpu_gauge = Gauge(
            "ai_civ_cpu_percent",
            "CPU usage percentage",
            ["component"],
            registry=self._registry,
        )
        self.memory_gauge = Gauge(
            "ai_civ_memory_percent",
            "Memory usage percentage",
            ["component"],
            registry=self._registry,
        )
        self.latency_histogram = Histogram(
            "ai_civ_latency_ms",
            "Request latency in milliseconds",
            ["component"],
            registry=self._registry,
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
        )
        self.error_counter = Counter(
            "ai_civ_errors_total",
            "Total error count",
            ["component", "error_type"],
            registry=self._registry,
        )
        self.rps_gauge = Gauge(
            "ai_civ_requests_per_second",
            "Current requests per second",
            ["component"],
            registry=self._registry,
        )

        # Agent-specific metrics
        self.agent_credits = Gauge(
            "ai_civ_agent_credits",
            "Agent credit balance",
            ["agent_id"],
            registry=self._registry,
        )
        self.agent_reputation = Gauge(
            "ai_civ_agent_reputation",
            "Agent reputation score",
            ["agent_id"],
            registry=self._registry,
        )
        self.task_counter = Counter(
            "ai_civ_tasks_total",
            "Total tasks processed",
            ["status"],
            registry=self._registry,
        )

    def record(self, data: TelemetryData) -> None:
        """Record telemetry data from a component."""
        component = data.source_component
        self._component_data[component].append(data)
        self._latest[component] = data

        # Update Prometheus gauges
        self.cpu_gauge.labels(component=component).set(data.cpu_percent)
        self.memory_gauge.labels(component=component).set(data.memory_percent)
        self.latency_histogram.labels(component=component).observe(data.latency_ms)
        self.rps_gauge.labels(component=component).set(data.requests_per_second)

        if data.error_rate > 0:
            self.error_counter.labels(
                component=component, error_type="rate"
            ).inc(data.error_rate)

        logger.debug(
            "telemetry.recorded",
            component=component,
            cpu=data.cpu_percent,
            latency=data.latency_ms,
        )

    def record_agent_metrics(
        self,
        agent_id: str,
        credits: float,
        reputation: float,
    ) -> None:
        """Record agent-specific economic metrics."""
        self.agent_credits.labels(agent_id=agent_id).set(credits)
        self.agent_reputation.labels(agent_id=agent_id).set(reputation)

    def record_task(self, status: str) -> None:
        """Record a task completion event."""
        self.task_counter.labels(status=status).inc()

    def get_latest(self, component: str) -> Optional[TelemetryData]:
        """Get the latest telemetry for a component."""
        return self._latest.get(component)

    def get_history(
        self,
        component: str,
        limit: int = 100,
    ) -> list[TelemetryData]:
        """Get recent telemetry history for a component."""
        return self._component_data.get(component, [])[-limit:]

    def get_all_components(self) -> list[str]:
        """List all components sending telemetry."""
        return list(self._component_data.keys())

    def get_system_summary(self) -> dict:
        """Get aggregate system metrics."""
        if not self._latest:
            return {"status": "no_data"}

        components = list(self._latest.values())
        return {
            "component_count": len(components),
            "avg_cpu": sum(c.cpu_percent for c in components) / len(components),
            "avg_memory": sum(c.memory_percent for c in components) / len(components),
            "avg_latency": sum(c.latency_ms for c in components) / len(components),
            "total_rps": sum(c.requests_per_second for c in components),
            "avg_error_rate": sum(c.error_rate for c in components) / len(components),
        }

    def get_digital_twin_config(self) -> dict:
        """Export current metrics as Digital Twin simulation parameters."""
        summary = self.get_system_summary()
        if summary.get("status") == "no_data":
            return {"status": "no_twin_data"}

        return {
            "simulated_users": 100000,
            "baseline_cpu": summary["avg_cpu"],
            "baseline_memory": summary["avg_memory"],
            "baseline_latency": summary["avg_latency"],
            "baseline_rps": summary["total_rps"],
            "failure_rate": summary["avg_error_rate"],
            "load_multiplier": 10.0,
        }

    def export_prometheus(self) -> bytes:
        """Export all metrics in Prometheus text format."""
        return generate_latest(self._registry)
