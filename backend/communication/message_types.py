"""Shared message schemas used across all communication patterns.

Every message in the civilization flows through these typed schemas.
Agents serialize/deserialize to these types for interoperability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Event Types ──────────────────────────────────────────────────────────

class EventType(str, Enum):
    """All event types that flow through the Event Bus."""

    # Project lifecycle
    PROJECT_CREATED = "project.created"
    PROJECT_COMPLETED = "project.completed"
    PROJECT_FAILED = "project.failed"

    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # Agent lifecycle
    AGENT_REGISTERED = "agent.registered"
    AGENT_RETIRED = "agent.retired"
    AGENT_DNA_MUTATED = "agent.dna.mutated"
    AGENT_DNA_MERGED = "agent.dna.merged"

    # Security
    VULNERABILITY_FOUND = "vulnerability.found"
    ATTACK_COMPLETED = "attack.completed"
    DEFENSE_DEPLOYED = "defense.deployed"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"

    # Deployment
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"

    # Court
    COURT_CONVENED = "court.convened"
    COURT_VOTE_CAST = "court.vote.cast"
    COURT_RESOLUTION = "court.resolution"

    # Evolution
    AGENT_SPAWNED = "agent.spawned"
    BENCHMARK_EVOLVED = "benchmark.evolved"

    # System
    HEARTBEAT = "system.heartbeat"
    ERROR = "system.error"


# ── Base Message ─────────────────────────────────────────────────────────

class Message(BaseModel):
    """Base message — every communication carries these fields."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    target: str = ""
    topic: str = ""
    correlation_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Event Bus Messages ───────────────────────────────────────────────────

class EventMessage(Message):
    """Message published to the Event Bus (Kafka / Redis Streams)."""

    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Task Market Messages ────────────────────────────────────────────────

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    CANCELLED = "cancelled"


class TaskDefinition(BaseModel):
    """A task available for bidding in the Task Market."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    difficulty: int = Field(ge=1, le=10, default=5)
    priority: TaskPriority = TaskPriority.MEDIUM
    required_specialization: str = ""
    max_bid: int = 100
    deadline_seconds: int = 300
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskBid(Message):
    """A bid submitted by an agent for a task."""

    task_id: str
    bid_amount: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_time_seconds: int = 0
    justification: str = ""


class TaskAssignment(Message):
    """Notification that a task has been assigned to an agent."""

    task: TaskDefinition
    winning_bid: TaskBid | None = None
    runner_up_bids: list[TaskBid] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.UNASSIGNED
    scoring_version: str = "v1"


# ── Agent-to-Agent Messages ─────────────────────────────────────────────

class AgentMessage(Message):
    """Direct agent-to-agent communication (gRPC / REST)."""

    method: str = ""
    request_data: dict[str, Any] = Field(default_factory=dict)
    response_data: dict[str, Any] = Field(default_factory=dict)
    is_response: bool = False


# ── Negotiation Messages ────────────────────────────────────────────────

class NegotiationStance(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class NegotiationMessage(Message):
    """Messages exchanged during Agent Court negotiations."""

    dispute_id: str = ""
    stance: NegotiationStance = NegotiationStance.ABSTAIN
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: str = ""
    vote_weight: float = 1.0


class CourtVerdict(Message):
    """Final verdict from the Agent Court."""

    dispute_id: str
    outcome: NegotiationStance
    votes_for_approval: int = 0
    votes_for_rejection: int = 0
    judge_count: int = 0
    reasoning_summary: str = ""


# ── Telemetry Messages ──────────────────────────────────────────────────

class TelemetryData(BaseModel):
    """Metrics data sent from components to the Digital Twin."""

    source_component: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    latency_ms: float = 0.0
    error_rate: float = 0.0
    requests_per_second: float = 0.0
    custom_metrics: dict[str, Any] = Field(default_factory=dict)


# ── WebSocket Messages ──────────────────────────────────────────────────

class DashboardUpdate(Message):
    """Real-time update pushed to the Command Center via WebSocket."""

    update_type: str = ""  # agent_status, task_progress, alert, metric
    data: dict[str, Any] = Field(default_factory=dict)
    visual_hint: str = ""  # color, icon, animation for the 3D view


# ── Shared Memory Messages ──────────────────────────────────────────────

class FailureRecord(BaseModel):
    """A failure recorded in the Failure Memory Network."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failure_type: str = ""
    root_cause: str = ""
    affected_code: str = ""
    fix_applied: str = ""
    agents_involved: list[str] = Field(default_factory=list)
    severity: int = Field(ge=1, le=10, default=5)
    project_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)


class GenomeRecord(BaseModel):
    """A Software Genome entry."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    architecture_pattern: str = ""
    security_model: str = ""
    database_choice: str = ""
    deployment_target: str = ""
    performance_profile: dict[str, Any] = Field(default_factory=dict)
    success_rating: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
