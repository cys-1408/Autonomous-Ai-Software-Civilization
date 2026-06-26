"""Digital Twin simulation models for Component 7 — Digital Twin World.

Creates virtual production environments that simulate:
- 100,000 virtual users with realistic behavior
- Network conditions (latency, packet loss, bandwidth)
- Database stress (slow queries, deadlocks, connection pool exhaustion)
- Server failures (crash, restart, scaling events)
- Chaos Monkey random failure injection
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoadPattern(str, Enum):
    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    STEP = "step"
    SINUSOIDAL = "sinusoidal"
    REALISTIC = "realistic"
    STRESS = "stress"
    SOAK = "soak"


class ChaosAction(str, Enum):
    KILL_POD = "kill_pod"
    NETWORK_DELAY = "network_delay"
    NETWORK_PARTITION = "network_partition"
    CPU_STORM = "cpu_storm"
    MEMORY_STORM = "memory_storm"
    DISK_FILL = "disk_fill"
    DNS_FAILURE = "dns_failure"
    CERTIFICATE_EXPIRY = "certificate_expiry"
    DB_CONNECTION_KILL = "db_connection_kill"
    RATE_LIMIT_TRIGGER = "rate_limit_trigger"
    DEPENDENCY_FAILURE = "dependency_failure"


class NetworkCondition(BaseModel):
    """Network simulation parameters."""

    latency_ms: float = 0.0
    latency_jitter_ms: float = 0.0
    packet_loss_percent: float = 0.0
    bandwidth_kbps: float = 100_000.0
    reorder_percent: float = 0.0


class UserBehavior(BaseModel):
    """Simulated user behavior profile."""

    think_time_seconds: tuple[float, float] = (1.0, 5.0)
    session_duration_minutes: tuple[float, float] = (5.0, 30.0)
    actions_per_session: tuple[int, int] = (10, 50)
    error_tolerance: float = 0.1  # % of errors before user leaves
    repeat_visit_probability: float = 0.3


class LoadProfile(BaseModel):
    """Load generation profile."""

    pattern: LoadPattern = LoadPattern.RAMP_UP
    min_users: int = 100
    max_users: int = 100_000
    ramp_up_minutes: float = 5.0
    sustain_minutes: float = 10.0
    cooldown_minutes: float = 5.0
    requests_per_user_per_minute: float = 5.0


class ChaosEvent(BaseModel):
    """A chaos event to inject into the simulation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: ChaosAction = ChaosAction.KILL_POD
    target: str = ""  # service name or pod selector
    probability: float = 0.0
    schedule_seconds: float = 0.0  # when to inject during simulation
    duration_seconds: float = 30.0
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class SimulationConfig(BaseModel):
    """Full Digital Twin simulation configuration."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    name: str = ""
    description: str = ""
    target_services: list[str] = Field(default_factory=list)
    load_profile: LoadProfile = Field(default_factory=LoadProfile)
    network_conditions: NetworkCondition = Field(default_factory=NetworkCondition)
    user_behavior: UserBehavior = Field(default_factory=UserBehavior)
    chaos_events: list[ChaosEvent] = Field(default_factory=list)
    duration_minutes: float = 30.0
    metrics_collection_interval_seconds: int = 5
    auto_recover: bool = True
    failure_tolerance: float = 0.01  # max acceptable failure rate
    status: SimulationStatus = SimulationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricPoint(BaseModel):
    """A single data point from the simulation."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    requests_per_second: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate: float = 0.0
    active_users: int = 0
    active_chaos_events: int = 0
    custom_metrics: dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    """Complete results from a Digital Twin simulation run."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config_id: str = ""
    status: SimulationStatus = SimulationStatus.COMPLETED
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime | None = None
    metrics: list[MetricPoint] = Field(default_factory=list)
    total_requests: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_rps: float = 0.0
    peak_cpu: float = 0.0
    peak_memory: float = 0.0
    surviving_services: int = 0
    failing_services: list[str] = Field(default_factory=list)
    chaos_events_triggered: int = 0
    chaos_events_survived: int = 0
    bottlenecks: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str = ""
    passed: bool = False
    summary: str = ""

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    @property
    def survival_rate(self) -> float:
        if self.chaos_events_triggered == 0:
            return 1.0
        return self.chaos_events_survived / self.chaos_events_triggered
