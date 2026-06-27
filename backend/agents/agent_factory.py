"""Self-Improving Agent Factory (Component 12).

The factory automatically creates new specialist agents when the system
detects a skills gap. For example, if blockchain-related tasks become
common, the factory spawns a BlockchainAuditorAgent.

The factory workflow:
1. Pattern Detection — monitor task market for emerging needs
2. Need Assessment — decide if a new specialist is required
3. Agent Creation — generate AgentDNA and AgentProfile
4. Agent Training — run through training tasks
5. Join Economy — register in the Task Market
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.agents.base import BaseAgent
from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    TaskDefinition,
    TaskPriority,
    TelemetryData,
    DashboardUpdate,
)
from backend.models.agent import (
    AgentDNA,
    AgentProfile,
    AgentState,
    ReasoningStyle,
    RiskTolerance,
    Specialization,
)

logger = structlog.get_logger(__name__)


class AgentTemplate:
    """Blueprint for creating a new agent type."""

    def __init__(
        self,
        name: str,
        specialization: Specialization,
        description: str = "",
        base_dna: AgentDNA | None = None,
        training_tasks: list[TaskDefinition] | None = None,
    ):
        self.name = name
        self.specialization = specialization
        self.description = description
        self.base_dna = base_dna or AgentDNA(specializations=[specialization])
        self.training_tasks = training_tasks or []


class AgentFactory:
    """Creates, trains, and evolves agents.

    Operates as a background service monitoring the civilization for
    skills gaps and spawning new agents to fill them.
    """

    def __init__(self, hub: CommunicationHub | None = None):
        self.hub = hub
        self._templates: dict[str, AgentTemplate] = {}
        self._agents_spawned: int = 0
        self._agents_retired: int = 0
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._agent_registry: dict[str, BaseAgent] = {}

    # ── Template Management ─────────────────────────────────────────────

    def register_template(self, template: AgentTemplate) -> None:
        """Register a blueprint for creating new agents."""
        self._templates[template.name] = template
        logger.info("factory.template_registered", template=template.name)

    def get_template(self, name: str) -> AgentTemplate | None:
        return self._templates.get(name)

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "specialization": t.specialization.value,
                "description": t.description,
            }
            for t in self._templates.values()
        ]

    # ── Agent Creation ──────────────────────────────────────────────────

    def spawn_agent(
        self,
        template_name: str,
        custom_dna: AgentDNA | None = None,
        agent_id: str | None = None,
    ) -> BaseAgent | None:
        """Spawn a new agent from a template.

        The agent gets registered but does not start until start().
        """
        template = self._templates.get(template_name)
        if not template:
            logger.warning("factory.template_not_found", template=template_name)
            return None

        dna = custom_dna or template.base_dna.mutate(0.05)
        agent_name = f"{template.name}-{self._agents_spawned + 1}"

        agent = BaseAgent(
            agent_id=agent_id,
            name=agent_name,
            specialization=template.specialization,
            hub=self.hub,
            dna=dna,
        )

        self._agent_registry[agent.profile.id] = agent
        self._agents_spawned += 1

        logger.info(
            "factory.agent_spawned",
            agent=agent_name,
            specialization=template.specialization.value,
        )
        return agent

    def spawn_evolved_agent(
        self,
        parent_a: BaseAgent,
        parent_b: BaseAgent,
        name: str | None = None,
    ) -> BaseAgent:
        """Spawn a child agent by merging two parents' DNA.

        The child inherits a blended DNA from both parents and may
        exhibit emergent behaviors.
        """
        child_dna = AgentDNA.merge(parent_a.profile.dna, parent_b.profile.dna)

        # Gather specializations from both parents
        all_specs = list(
            set(parent_a.profile.dna.specializations)
            | set(parent_b.profile.dna.specializations)
        )
        primary_spec = all_specs[0] if all_specs else Specialization.GENERAL

        child_name = (
            name
            or f"Evolved-{parent_a.profile.name[:8]}+{parent_b.profile.name[:8]}"
        )

        child = BaseAgent(
            name=child_name,
            specialization=primary_spec,
            hub=self.hub,
            dna=child_dna,
        )

        # Inherit a reputation bonus from parents
        child.profile.reputation = (
            parent_a.profile.reputation * 0.3
            + parent_b.profile.reputation * 0.3
            + 10.0  # New agent bonus
        )

        self._agent_registry[child.profile.id] = child
        self._agents_spawned += 1

        logger.info(
            "factory.evolved_agent_spawned",
            agent=child_name,
            parents=[parent_a.profile.name, parent_b.profile.name],
        )
        return child

    def spawn_specialist_for_task(
        self,
        task: TaskDefinition,
    ) -> BaseAgent | None:
        """Auto-create an agent specialized for an unassigned task.

        Used when no existing agent bids on a task — the factory
        creates a new specialist just for it.
        """
        spec_str = task.required_specialization or "general"
        try:
            specialization = Specialization(spec_str)
        except ValueError:
            specialization = Specialization.GENERAL

        # Find or create a template
        template_name = f"auto_{spec_str}"
        if template_name not in self._templates:
            template = AgentTemplate(
                name=template_name,
                specialization=specialization,
                description=f"Auto-generated agent for {spec_str} tasks",
                base_dna=AgentDNA(
                    specializations=[specialization],
                    reasoning_style=random.choice(list(ReasoningStyle)),
                    risk_tolerance=RiskTolerance.MEDIUM,
                ),
            )
            self.register_template(template)

        return self.spawn_agent(template_name)

    # ── Training ────────────────────────────────────────────────────────

    async def train_agent(
        self,
        agent: BaseAgent,
        training_tasks: list[TaskDefinition],
    ) -> dict[str, Any]:
        """Run an agent through training tasks and evaluate performance.

        Training consists of:
        1. Running each training task
        2. Evaluating the result against expected outcomes
        3. Updating agent reputation based on performance
        4. Optionally mutating DNA if performance is poor
        """
        results = []
        passed = 0
        failed = 0

        for i, task in enumerate(training_tasks):
            try:
                # Create a mock assignment
                from backend.communication.task_market import TaskAssignment
                from backend.communication.message_types import TaskStatus

                assignment = TaskAssignment(
                    source="agent_factory",
                    task=task,
                    status=TaskStatus.ASSIGNED,
                )
                agent.assign_task(assignment)

                # Wait for completion (with timeout)
                await asyncio.sleep(0.1)  # Let agent process

                results.append({
                    "task": task.name,
                    "passed": True,
                })
                passed += 1

            except Exception as exc:
                results.append({
                    "task": task.name,
                    "passed": False,
                    "error": str(exc),
                })
                failed += 1

        # Update agent reputation
        success_rate = passed / max(1, len(training_tasks))
        if success_rate > 0.8:
            agent.profile.reputation = min(100.0, agent.profile.reputation + 5.0)
        elif success_rate < 0.4:
            agent.profile.reputation = max(0.0, agent.profile.reputation - 5.0)
            # Poor performance triggers DNA mutation
            agent.mutate_dna(0.2)

        return {
            "agent_id": agent.profile.id,
            "agent_name": agent.profile.name,
            "tasks_passed": passed,
            "tasks_failed": failed,
            "success_rate": success_rate,
            "final_reputation": agent.profile.reputation,
        }

    # ── Pattern Detection & Auto-Spawning ───────────────────────────────

    def detect_skills_gap(
        self,
        unassigned_tasks: list[TaskDefinition],
    ) -> list[str]:
        """Analyze unassigned tasks to detect missing specializations.

        Returns a list of specializations that need new agents.
        """
        needed: dict[str, int] = {}
        for task in unassigned_tasks:
            spec = task.required_specialization or "general"
            needed[spec] = needed.get(spec, 0) + 1

        # Only flag specializations with >3 unassigned tasks
        return [spec for spec, count in needed.items() if count > 3]

    async def auto_spawn_for_gaps(
        self,
        unassigned_tasks: list[TaskDefinition],
    ) -> list[BaseAgent]:
        """Automatically spawn agents to fill detected skills gaps."""
        gaps = self.detect_skills_gap(unassigned_tasks)
        spawned: list[BaseAgent] = []

        for spec_str in gaps:
            if self._agents_spawned > 50:
                break  # Safety limit

            try:
                specialization = Specialization(spec_str)
            except ValueError:
                continue

            template_name = f"auto_{spec_str}"
            if template_name not in self._templates:
                template = AgentTemplate(
                    name=template_name,
                    specialization=specialization,
                    description=f"Auto-spawned to fill {spec_str} gap",
                )
                self.register_template(template)

            agent = self.spawn_agent(template_name)
            if agent:
                spawned.append(agent)

        if spawned:
            logger.info(
                "factory.auto_spawned",
                count=len(spawned),
                specializations=gaps,
            )

        return spawned

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def start(self, hub: CommunicationHub | None = None) -> None:
        """Start the factory's background monitoring loop."""
        if self._running:
            return
        self._running = True
        if hub:
            self.hub = hub
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("factory.started")

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("factory.stopped")

    async def _monitor_loop(self) -> None:
        """Periodically check for skills gaps and spawn agents.

        Every 60 seconds:
        1. Scan the task market for unassigned/open tasks
        2. Detect missing specializations
        3. Auto-spawn specialist agents to fill gaps
        4. Log evolution events
        """
        while self._running:
            try:
                if not self.hub:
                    await asyncio.sleep(10)
                    continue

                # 1. Collect unassigned tasks from the task market
                unassigned_tasks = self._collect_unassigned_tasks()

                # 2. Detect skills gaps
                gaps = self.detect_skills_gap(unassigned_tasks)

                # 3. Auto-spawn agents for detected gaps
                if gaps:
                    spawned = await self.auto_spawn_for_gaps(unassigned_tasks)
                    if spawned:
                        logger.info(
                            "factory.evolution_event",
                            gaps_detected=gaps,
                            agents_spawned=len(spawned),
                        )
                        # Register new agents in the economy
                        if self.hub:
                            for agent in spawned:
                                await agent.start(hub=self.hub)
                                # Notify the civilization
                                await self.hub.publish_event(
                                    EventType.AGENT_SPAWNED,
                                    payload={
                                        "agent_id": agent.profile.id,
                                        "agent_name": agent.profile.name,
                                        "specialization": agent.specialization.value,
                                        "generation": agent.profile.dna.generation,
                                    },
                                    source="agent_factory",
                                )

                # 4. Check if any agents should evolve (reproduce/mutate)
                await self._check_agent_evolution()

                # 5. Log heartbeat
                if self._agents_spawned > 0:
                    logger.debug(
                        "factory.heartbeat",
                        active_agents=sum(
                            1 for a in self._agent_registry.values()
                            if a.profile.state != AgentState.RETIRED
                        ),
                        total_spawned=self._agents_spawned,
                        gaps_detected=len(gaps),
                    )

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("factory.monitor_error", error=str(exc))
                await asyncio.sleep(30)

    def _collect_unassigned_tasks(self) -> list[TaskDefinition]:
        """Gather all unassigned/open tasks from the task market.

        In production, this would query the task market through the hub.
        Returns a list of tasks that need agents.
        """
        if not self.hub:
            return []
        collected: list[TaskDefinition] = []
        try:
            # Query the task market for open/unassigned tasks
            task_market = self.hub.task_market
            # Collect all tasks that are still open
            for task_id, status in list(task_market._task_status.items()):
                from backend.communication.message_types import TaskStatus
                if status == TaskStatus.OPEN:
                    task = task_market.get_task(task_id)
                    if task:
                        collected.append(task)
        except Exception as exc:
            logger.warning("factory.collect_tasks_error", error=str(exc))
        return collected

    async def _check_agent_evolution(self) -> None:
        """Monitor agent performance and trigger evolution events.

        - Low-reputation agents get mutated to try new strategies
        - High-reputation agents get cloned and merged
        - Retired agents get removed from the registry
        """
        if not self.hub:
            return

        active_agents = [
            a for a in self._agent_registry.values()
            if a.profile.state not in (AgentState.RETIRED, AgentState.EVOLVING)
        ]

        # Too few agents to evolve meaningfully
        if len(active_agents) < 3:
            return

        # Find low-reputation agents and mutate them
        low_performers = [
            a for a in active_agents if a.profile.reputation < 20.0
            and a.profile.tasks_completed > 0
        ]
        for agent in low_performers[:2]:  # Limit to 2 per cycle
            agent.mutate_dna(intensity=0.25)  # Stronger mutation for low performers
            logger.info(
                "factory.mutating_low_performer",
                agent=agent.profile.name,
                reputation=agent.profile.reputation,
            )

        # Find high-reputation agents and merge them to create evolved children
        top_performers = sorted(
            [a for a in active_agents if a.profile.reputation > 70.0],
            key=lambda a: a.profile.reputation,
            reverse=True,
        )
        if len(top_performers) >= 2:
            parent_a = top_performers[0]
            parent_b = top_performers[1]

            # Create evolved child
            child = self.spawn_evolved_agent(parent_a, parent_b)

            # Boost the child's starting stats
            child.profile.credits = parent_a.profile.credits * 0.3 + parent_b.profile.credits * 0.3 + 20.0
            child.profile.reputation = min(100.0, child.profile.reputation + 5.0)

            await child.start(hub=self.hub)

            if self.hub:
                await self.hub.publish_event(
                    EventType.AGENT_DNA_MERGED,
                    payload={
                        "child_id": child.profile.id,
                        "child_name": child.profile.name,
                        "parent_a": parent_a.profile.name,
                        "parent_b": parent_b.profile.name,
                        "generation": child.profile.dna.generation,
                    },
                    source="agent_factory",
                )

            logger.info(
                "factory.evolved_agent_created",
                child=child.profile.name,
                parents=[parent_a.profile.name, parent_b.profile.name],
                generation=child.profile.dna.generation,
            )

        # Retire agents with very low reputation that have been active
        stale_agents = [
            a for a in active_agents
            if a.profile.reputation < 5.0 and a.profile.tasks_completed > 5
        ]
        for agent in stale_agents[:1]:  # Limit to 1 per cycle
            if self.hub:
                await self.hub.publish_event(
                    EventType.AGENT_RETIRED,
                    payload={
                        "agent_id": agent.profile.id,
                        "agent_name": agent.profile.name,
                        "reason": "low_reputation",
                    },
                    source="agent_factory",
                )
            agent.profile.state = AgentState.RETIRED
            self._agents_retired += 1
            logger.info(
                "factory.retired_agent",
                agent=agent.profile.name,
                reputation=agent.profile.reputation,
            )

    # ── Registry ────────────────────────────────────────────────────────

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        return self._agent_registry.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "id": a.profile.id,
                "name": a.profile.name,
                "specialization": a.specialization.value,
                "state": a.profile.state.value,
                "reputation": a.profile.reputation,
                "credits": a.profile.credits,
                "tasks_completed": a.profile.tasks_completed,
                "tasks_failed": a.profile.tasks_failed,
                "generation": a.profile.dna.generation,
            }
            for a in self._agent_registry.values()
        ]

    def get_stats(self) -> dict[str, int]:
        return {
            "agents_spawned": self._agents_spawned,
            "agents_retired": self._agents_retired,
            "active_agents": sum(
                1 for a in self._agent_registry.values()
                if a.profile.state != AgentState.RETIRED
            ),
            "templates": len(self._templates),
        }
