"""Development Civilization (Component 4).

The actual software creation pipeline. It consists of multiple specialized
agents that work together in a production line:

1. Requirement Analyst — creates detailed specifications
2. System Architect — creates architecture design
3. Database Architect — creates database schemas
4. Backend Agent — creates APIs and business logic
5. Frontend Agent — creates user interfaces
6. Test Agent — creates and runs tests

All agents communicate through the CommunicationHub with Kafka/Redis
pub/sub for event-driven orchestration.

The flow:
Architect → Database Agent → Backend Agent → Frontend Agent → Test Agent
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    DashboardUpdate,
)
from backend.models.project import ProjectSpec
from backend.models.architecture import (
    ArchitectureDesign,
    ArchitecturePattern,
    ServiceDefinition,
    DatabaseSchema,
    TableDefinition,
    ColumnDefinition,
    ColumnType,
    APIDefinition,
    APIEndpoint,
    HTTPMethod,
)

logger = structlog.get_logger(__name__)


class DevelopmentPipeline:
    """Manages the end-to-end development pipeline for a project.

    Coordinates the agents to design, implement, and test a project.
    """

    def __init__(self, name: str = "development_pipeline"):
        self.name = name
        self._phases: list[dict[str, Any]] = []
        self._current_phase: int = -1
        self._artifacts: dict[str, Any] = {}

    def add_phase(self, phase_name: str, description: str) -> int:
        """Add a development phase to the pipeline."""
        idx = len(self._phases)
        self._phases.append({
            "name": phase_name,
            "description": description,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "result": None,
        })
        return idx

    @property
    def is_complete(self) -> bool:
        return all(p["status"] == "completed" for p in self._phases)


class DevelopmentCivilization:
    """Orchestrates the full development lifecycle from spec to deployed code.

    This component manages the Development Civilization pipeline where
    specialized agents work together to build software.
    """

    def __init__(self, hub: CommunicationHub | None = None):
        self.hub = hub
        self._pipelines: dict[str, DevelopmentPipeline] = {}

    # ── Pipeline Management ─────────────────────────────────────────────

    def create_pipeline(self, spec: ProjectSpec) -> DevelopmentPipeline:
        """Create a development pipeline for a project.

        The pipeline consists of phases that map to the Development
        Civilization agent production line.
        """
        pipeline = DevelopmentPipeline(name=f"pipeline_{spec.id[:8]}")

        # Requirement Analysis
        pipeline.add_phase(
            "requirement_analysis",
            "Analyze requirements and create detailed specifications"
        )

        # System Architecture
        pipeline.add_phase(
            "system_architecture",
            "Design the system architecture, services, and components"
        )

        # Database Design
        pipeline.add_phase(
            "database_design",
            "Design database schema, tables, and relationships"
        )

        # API Design
        pipeline.add_phase(
            "api_design",
            "Design REST/gRPC API endpoints and contracts"
        )

        # Backend Implementation
        pipeline.add_phase(
            "backend_implementation",
            "Implement backend services, business logic, and APIs"
        )

        # Frontend Implementation
        pipeline.add_phase(
            "frontend_implementation",
            "Implement user interface components and pages"
        )

        # Testing
        pipeline.add_phase(
            "testing",
            "Create and run unit, integration, and e2e tests"
        )

        self._pipelines[spec.id] = pipeline
        return pipeline

    def get_pipeline(self, project_id: str) -> DevelopmentPipeline | None:
        return self._pipelines.get(project_id)

    # ── Architecture Generation ─────────────────────────────────────────

    def design_architecture(
        self,
        spec: ProjectSpec,
    ) -> ArchitectureDesign:
        """Generate an architecture design from a project spec.

        This is what the System Architect agent would produce.
        """
        if spec.module_count > 5:
            pattern = ArchitecturePattern.MICROSERVICES
        else:
            pattern = ArchitecturePattern.LAYERED

        services = []
        for i, module in enumerate(spec.modules[:8]):
            service = ServiceDefinition(
                name=module.name.replace(" ", "_").lower(),
                description=module.description or f"Service for {module.name}",
                port=8000 + i,
                replicas=2,
                owns_database=True,
                api_prefix=f"/api/v1/{module.name.lower().replace(' ', '_')}",
            )
            services.append(service)

        # Create database schema
        tables = []
        for module in spec.modules:
            table = TableDefinition(
                name=module.name.replace(" ", "_").lower(),
                columns=[
                    ColumnDefinition(
                        name="id",
                        column_type=ColumnType.UUID,
                        is_primary_key=True,
                    ),
                    ColumnDefinition(
                        name="created_at",
                        column_type=ColumnType.TIMESTAMP,
                        default="now()",
                    ),
                    ColumnDefinition(
                        name="updated_at",
                        column_type=ColumnType.TIMESTAMP,
                        default="now()",
                    ),
                ],
                description=f"Table for {module.name}",
            )
            for entity in module.entities[:3]:
                table.columns.append(
                    ColumnDefinition(
                        name=entity.lower(),
                        column_type=ColumnType.STRING,
                        nullable=True,
                    )
                )
            tables.append(table)

        database = DatabaseSchema(
            name=f"{spec.project_type}_db",
            tables=tables,
            relationships=[
                {"from": t.name, "to": "projects"}
                for t in tables
            ],
        )

        # Create API definitions
        endpoints = []
        for module in spec.modules:
            base_path = module.name.lower().replace(" ", "_")
            endpoints.extend([
                APIEndpoint(
                    path=f"/{base_path}",
                    method=HTTPMethod.GET,
                    summary=f"List {module.name}",
                    auth_required=True,
                ),
                APIEndpoint(
                    path=f"/{base_path}",
                    method=HTTPMethod.POST,
                    summary=f"Create {module.name}",
                    auth_required=True,
                ),
                APIEndpoint(
                    path=f"/{base_path}/{{id}}",
                    method=HTTPMethod.GET,
                    summary=f"Get {module.name} by ID",
                    auth_required=True,
                ),
                APIEndpoint(
                    path=f"/{base_path}/{{id}}",
                    method=HTTPMethod.PUT,
                    summary=f"Update {module.name}",
                    auth_required=True,
                ),
                APIEndpoint(
                    path=f"/{base_path}/{{id}}",
                    method=HTTPMethod.DELETE,
                    summary=f"Delete {module.name}",
                    auth_required=True,
                ),
            ])

        api = APIDefinition(
            service_name=spec.title,
            endpoints=endpoints,
            auth_method="jwt",
        )

        return ArchitectureDesign(
            project_id=spec.id,
            pattern=pattern,
            services=services,
            database=database,
            api=api,
        )

    # ── Pipeline Execution ──────────────────────────────────────────────

    async def run_pipeline(
        self,
        spec: ProjectSpec,
    ) -> dict[str, Any]:
        """Run the full development pipeline for a project.

        This simulates the agent production line working through
        each phase of development.
        """
        pipeline = self.create_pipeline(spec)
        results: dict[str, Any] = {}

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="pipeline_started",
                data={
                    "project_id": spec.id,
                    "title": spec.title,
                    "phases": len(pipeline._phases),
                },
                visual_hint="blue",
                source="development_civilization",
            ))

        # Phase 1 & 2: Architecture Design
        architecture = self.design_architecture(spec)
        results["architecture"] = architecture.model_dump(mode="json")
        pipeline._phases[0]["status"] = "completed"
        pipeline._phases[1]["status"] = "completed"

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="pipeline_progress",
                data={
                    "project_id": spec.id,
                    "phase": "architecture_design",
                    "services": architecture.service_count,
                    "tables": architecture.database.table_count if architecture.database else 0,
                    "endpoints": architecture.api.endpoint_count if architecture.api else 0,
                },
                visual_hint="green",
                source="development_civilization",
            ))

        # Phases 3-7: For each module, simulate development
        module_results = []
        for i, module in enumerate(spec.modules):
            module_result = await self._develop_module(module, architecture, i)
            module_results.append(module_result)

            if self.hub:
                await self.hub.push_dashboard_update(DashboardUpdate(
                    update_type="module_completed",
                    data={
                        "project_id": spec.id,
                        "module": module.name,
                        "progress": round((i + 1) / spec.module_count * 100),
                    },
                    visual_hint="green",
                    source="development_civilization",
                ))

        results["modules"] = module_results
        pipeline._phases[-1]["status"] = "completed"

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="pipeline_completed",
                data={
                    "project_id": spec.id,
                    "title": spec.title,
                    "modules": spec.module_count,
                    "services": architecture.service_count,
                    "endpoints": architecture.api.endpoint_count if architecture.api else 0,
                },
                visual_hint="green",
                source="development_civilization",
            ))

        return results

    async def _develop_module(
        self,
        module: Module,
        architecture: ArchitectureDesign,
        index: int,
    ) -> dict[str, Any]:
        """Simulate development of a single module."""
        return {
            "module_name": module.name,
            "entities": module.entities,
            "service": architecture.services[index].name
            if index < len(architecture.services)
            else module.name.lower().replace(" ", "_"),
            "status": "generated",
            "files_generated": [
                f"models/{module.name.lower().replace(' ', '_')}.py",
                f"routes/{module.name.lower().replace(' ', '_')}.py",
                f"schemas/{module.name.lower().replace(' ', '_')}.py",
            ],
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "pipelines": len(self._pipelines),
            "active_pipelines": sum(
                1 for p in self._pipelines.values()
                if not p.is_complete
            ),
            "completed_pipelines": sum(
                1 for p in self._pipelines.values()
                if p.is_complete
            ),
        }
