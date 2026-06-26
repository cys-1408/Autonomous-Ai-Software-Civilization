"""Agent-related domain models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReasoningStyle(str, Enum):
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    EXPLORATORY = "exploratory"
    SYSTEMATIC = "systematic"
    INTUITIVE = "intuitive"


class RiskTolerance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Specialization(str, Enum):
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    SYSTEM_ARCHITECTURE = "system_architecture"
    DATABASE_DESIGN = "database_design"
    BACKEND = "backend"
    FRONTEND = "frontend"
    TESTING = "testing"
    SECURITY = "security"
    DEVOPS = "devops"
    CLOUD = "cloud"
    FORMAL_VERIFICATION = "formal_verification"
    CHAOS_ENGINEERING = "chaos_engineering"
    BLOCKCHAIN = "blockchain"
    DATA_SCIENCE = "data_science"
    ML_OPS = "ml_ops"
    GENERAL = "general"


class AgentState(str, Enum):
    IDLE = "idle"
    BIDDING = "bidding"
    WORKING = "working"
    WAITING_REVIEW = "waiting_review"
    EVOLVING = "evolving"
    RETIRED = "retired"


class AgentDNA(BaseModel):
    """Genetic blueprint that defines an agent's behaviour.

    DNA is mutated, merged, and cloned by the Agent DNA System (Component 3)
    to produce evolved specialist agents.
    """

    reasoning_style: ReasoningStyle = ReasoningStyle.ANALYTICAL
    risk_tolerance: RiskTolerance = RiskTolerance.MEDIUM
    specializations: list[Specialization] = Field(default_factory=list)
    tool_preferences: dict[str, float] = Field(
        default_factory=lambda: {"gpt-4": 0.8, "claude-3": 0.7, "local": 0.3}
    )
    temperature: float = Field(ge=0.0, le=2.0, default=0.7)
    max_context_tokens: int = Field(ge=1000, default=128_000)
    preferred_languages: list[str] = Field(
        default_factory=lambda: ["python", "typescript", "sql"]
    )
    creativity_factor: float = Field(ge=0.0, le=1.0, default=0.5)
    thoroughness: float = Field(ge=0.0, le=1.0, default=0.7)
    mutation_rate: float = Field(ge=0.0, le=1.0, default=0.1)
    generation: int = 1
    parent_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mutate(self, intensity: float = 0.15) -> AgentDNA:
        """Return a mutated copy of this DNA."""
        import random

        child = self.model_copy(deep=True)
        child.generation = self.generation + 1
        child.parent_ids = [str(self.__hash__())]

        if random.random() < intensity:
            child.temperature = max(
                0.0, min(2.0, self.temperature + random.uniform(-0.2, 0.2))
            )
        if random.random() < intensity:
            child.creativity_factor = max(
                0.0, min(1.0, self.creativity_factor + random.uniform(-0.15, 0.15))
            )
        if random.random() < intensity:
            child.thoroughness = max(
                0.0, min(1.0, self.thoroughness + random.uniform(-0.15, 0.15))
            )
        if random.random() < intensity * 0.5:
            child.mutation_rate = max(
                0.0, min(1.0, self.mutation_rate + random.uniform(-0.05, 0.05))
            )

        for tool, weight in list(child.tool_preferences.items()):
            if random.random() < intensity * 0.3:
                child.tool_preferences[tool] = max(
                    0.0, min(1.0, weight + random.uniform(-0.1, 0.1))
                )
        return child

    @classmethod
    def merge(cls, parent_a: AgentDNA, parent_b: AgentDNA) -> AgentDNA:
        """Produce child DNA by merging two parents."""
        import random

        child = cls(
            reasoning_style=random.choice(
                [parent_a.reasoning_style, parent_b.reasoning_style]
            ),
            risk_tolerance=random.choice(
                [parent_a.risk_tolerance, parent_b.risk_tolerance]
            ),
            specializations=list(
                set(parent_a.specializations) | set(parent_b.specializations)
            ),
            tool_preferences={
                k: (parent_a.tool_preferences.get(k, 0) + parent_b.tool_preferences.get(k, 0)) / 2
                for k in set(parent_a.tool_preferences) | set(parent_b.tool_preferences)
            },
            temperature=(parent_a.temperature + parent_b.temperature) / 2,
            max_context_tokens=max(parent_a.max_context_tokens, parent_b.max_context_tokens),
            preferred_languages=list(
                set(parent_a.preferred_languages) | set(parent_b.preferred_languages)
            ),
            creativity_factor=(parent_a.creativity_factor + parent_b.creativity_factor) / 2,
            thoroughness=(parent_a.thoroughness + parent_b.thoroughness) / 2,
            mutation_rate=(parent_a.mutation_rate + parent_b.mutation_rate) / 2,
            generation=max(parent_a.generation, parent_b.generation) + 1,
            parent_ids=[str(parent_a.__hash__()), str(parent_b.__hash__())],
        )
        return child


class AgentProfile(BaseModel):
    """Full profile of an agent in the civilization."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dna: AgentDNA = Field(default_factory=AgentDNA)
    state: AgentState = AgentState.IDLE
    credits: float = 100.0
    reputation: float = 50.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    vulnerabilities_found: int = 0
    fixes_applied: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_task_id: str | None = None
    success_rate: float = Field(ge=0.0, le=1.0, default=0.5)
    avg_completion_time_seconds: float = 0.0

    @property
    def total_tasks(self) -> int:
        return self.tasks_completed + self.tasks_failed

    @property
    def is_available(self) -> bool:
        return self.state == AgentState.IDLE and self.current_task_id is None
