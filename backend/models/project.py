"""Project-related domain models for the Goal Interpreter."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    INTERPRETED = "interpreted"
    ARCHITECTED = "architected"
    DEVELOPED = "developed"
    TESTED = "tested"
    SECURED = "secured"
    VERIFIED = "verified"
    SIMULATED = "simulated"
    DEPLOYED = "deployed"
    FAILED = "failed"


class Constraint(BaseModel):
    """A non-functional requirement or constraint."""

    category: str = ""
    description: str = ""
    priority: str = "must"  # must, should, could
    measurable: bool = False
    target: str = ""


class Module(BaseModel):
    """A functional module identified by the Goal Interpreter."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    entities: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    apis: list[str] = Field(default_factory=list)
    priority: int = Field(ge=1, le=10, default=5)
    dependencies: list[str] = Field(default_factory=list)


class TechStack(BaseModel):
    """Technology choices for the project."""

    language: str = "python"
    framework: str = "fastapi"
    frontend_framework: str = "react"
    database: str = "postgresql"
    cache: str = "redis"
    message_queue: str = "kafka"
    containerization: str = "docker"
    orchestration: str = "kubernetes"
    monitoring: str = "prometheus"
    logging: str = "elasticsearch"
    ci_cd: str = "github-actions"
    testing: str = "pytest"
    additional: dict[str, str] = Field(default_factory=dict)


class ProjectGoal(BaseModel):
    """Raw user input before interpretation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_input: str = ""
    user_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectSpec(BaseModel):
    """Structured output from the Goal Interpreter.

    This is the machine-understandable representation of the user's request
    that drives the entire development pipeline.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    project_type: str = ""
    title: str = ""
    description: str = ""
    modules: list[Module] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    tech_stack: TechStack = Field(default_factory=TechStack)
    user_roles: list[str] = Field(default_factory=list)
    data_entities: list[str] = Field(default_factory=list)
    external_integrations: list[str] = Field(default_factory=list)
    security_requirements: list[str] = Field(default_factory=list)
    scalability_requirements: list[str] = Field(default_factory=list)
    compliance: list[str] = Field(default_factory=list)
    status: ProjectStatus = ProjectStatus.INTERPRETED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def estimated_complexity(self) -> int:
        """Rough complexity estimate 1-10 based on modules and constraints."""
        base = len(self.modules) * 0.5
        base += len(self.constraints) * 0.3
        base += len(self.security_requirements) * 0.4
        base += len(self.compliance) * 0.5
        return min(10, max(1, int(base)))
