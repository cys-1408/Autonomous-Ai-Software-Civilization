"""Shared domain models for the AI Civilization.

These models extend the communication schemas with richer domain types
used by agents, the economy, the development pipeline, and the
adversarial / verification subsystems.
"""

from backend.models.agent import (
    AgentProfile,
    AgentDNA,
    AgentState,
    ReasoningStyle,
    RiskTolerance,
    Specialization,
)
from backend.models.project import (
    ProjectGoal,
    ProjectSpec,
    Module,
    Constraint,
    TechStack,
    ProjectStatus,
)
from backend.models.architecture import (
    ArchitectureDesign,
    ServiceDefinition,
    DatabaseSchema,
    TableDefinition,
    ColumnDefinition,
    APIDefinition,
    APIEndpoint,
    UILayout,
)
from backend.models.security import (
    Vulnerability,
    VulnerabilitySeverity,
    AttackResult,
    FixReport,
)
from backend.models.verification import (
    VerificationProof,
    VerificationStatus,
    ProofSystem,
)
from backend.models.simulation import (
    SimulationConfig,
    SimulationResult,
    ChaosEvent,
)
from backend.models.deployment import (
    DeploymentPlan,
    CloudProvider,
    InfrastructureSpec,
)

__all__ = [
    # Agent
    "AgentProfile",
    "AgentDNA",
    "AgentState",
    "ReasoningStyle",
    "RiskTolerance",
    "Specialization",
    # Project
    "ProjectGoal",
    "ProjectSpec",
    "Module",
    "Constraint",
    "TechStack",
    "ProjectStatus",
    # Architecture
    "ArchitectureDesign",
    "ServiceDefinition",
    "DatabaseSchema",
    "TableDefinition",
    "ColumnDefinition",
    "APIDefinition",
    "APIEndpoint",
    "UILayout",
    # Security
    "Vulnerability",
    "VulnerabilitySeverity",
    "AttackResult",
    "FixReport",
    # Verification
    "VerificationProof",
    "VerificationStatus",
    "ProofSystem",
    # Simulation
    "SimulationConfig",
    "SimulationResult",
    "ChaosEvent",
    # Deployment
    "DeploymentPlan",
    "CloudProvider",
    "InfrastructureSpec",
]
