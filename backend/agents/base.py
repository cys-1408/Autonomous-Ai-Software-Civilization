"""Base agent class that all civilization agents inherit from.

Every agent runs its own async loop, can bid on tasks, communicate
through the Hub, and evolve through DNA mutation.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

import structlog

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    TaskBid,
    TaskDefinition,
    TaskAssignment,
    AgentMessage,
    TelemetryData,
    DashboardUpdate,
)
from backend.models.agent import (
    AgentDNA,
    AgentProfile,
    AgentState,
    Specialization,
)

logger = structlog.get_logger(__name__)


class AgentTask:
    """A task assigned to and being executed by an agent."""

    def __init__(
        self,
        assignment: TaskAssignment,
    ):
        self.assignment = assignment
        self.result: dict[str, Any] = {}
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class AgentStateMachine:
    """Finite state machine for agent lifecycle."""

    _transitions: dict[AgentState, set[AgentState]] = {
        AgentState.IDLE: {AgentState.BIDDING, AgentState.EVOLVING, AgentState.RETIRED},
        AgentState.BIDDING: {AgentState.IDLE, AgentState.WORKING},
        AgentState.WORKING: {AgentState.IDLE, AgentState.WAITING_REVIEW, AgentState.RETIRED},
        AgentState.WAITING_REVIEW: {AgentState.IDLE, AgentState.WORKING, AgentState.RETIRED},
        AgentState.EVOLVING: {AgentState.IDLE, AgentState.RETIRED},
        AgentState.RETIRED: set(),
    }

    @classmethod
    def can_transition(cls, current: AgentState, target: AgentState) -> bool:
        return target in cls._transitions.get(current, set())


class BaseAgent:
    """Foundation class for all agents in the civilization.

    Subclass this to create specific agent types (e.g., SecurityAgent,
    ArchitectAgent, DatabaseAgent).

    Example:
        class DatabaseAgent(BaseAgent):
            async def execute_task(self, task: AgentTask) -> dict:
                return {"schema": "create table..."}
    """

    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "",
        specialization: Specialization = Specialization.GENERAL,
        hub: CommunicationHub | None = None,
        dna: AgentDNA | None = None,
    ):
        self.profile = AgentProfile(
            id=agent_id or str(uuid.uuid4()),
            name=name or f"{specialization.value}_{uuid.uuid4().hex[:8]}",
            dna=dna or AgentDNA(specializations=[specialization]),
            state=AgentState.IDLE,
        )
        self.specialization = specialization
        self.hub = hub
        self._current_task: AgentTask | None = None
        self._running = False
        self._task_queue: asyncio.Queue[TaskAssignment] = asyncio.Queue()
        self._main_task: asyncio.Task | None = None
        self._event_handlers: dict[EventType, Callable] = {}

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def start(self, hub: CommunicationHub | None = None) -> None:
        """Start the agent's main event loop."""
        if self._running:
            return
        self._running = True
        if hub:
            self.hub = hub
        self.profile.state = AgentState.IDLE
        self.profile.last_active = datetime.now(timezone.utc)
        self._main_task = asyncio.create_task(self._run_loop())
        logger.info("agent.started", agent=self.profile.name, specialization=self.specialization.value)

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self._running = False
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        self.profile.state = AgentState.RETIRED
        logger.info("agent.stopped", agent=self.profile.name)

    async def _run_loop(self) -> None:
        """Main event loop — processes tasks and heartbeats."""
        while self._running:
            try:
                # Check for assigned tasks
                if not self._current_task:
                    try:
                        assignment = await asyncio.wait_for(
                            self._task_queue.get(), timeout=1.0
                        )
                        await self._handle_assignment(assignment)
                    except asyncio.TimeoutError:
                        pass

                # Process current task
                if self._current_task:
                    await self._process_current_task()

                # Send heartbeat
                await self._heartbeat()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(
                    "agent.loop_error",
                    agent=self.profile.name,
                    error=str(exc),
                )
                await asyncio.sleep(1)

    # ── Task Handling ───────────────────────────────────────────────────

    async def bid_on_task(self, task: TaskDefinition) -> TaskBid | None:
        """Create and submit a bid for a task.

        Override in subclass to customize bidding strategy.
        """
        base_bid = max(5, task.difficulty * 3)
        confidence = min(
            1.0,
            self.profile.dna.thoroughness * 0.5
            + self.profile.reputation / 100.0 * 0.3
            + 0.2,
        )

        return TaskBid(
            source=self.profile.id,
            task_id=task.id,
            bid_amount=base_bid,
            confidence=confidence,
            estimated_time_seconds=task.difficulty * 60,
            justification=f"I specialize in {self.specialization.value} with "
                          f"{self.profile.reputation:.0f} reputation",
            metadata={
                "specializations": [s.value for s in self.profile.dna.specializations],
                "agent_name": self.profile.name,
            },
        )

    async def execute_task(self, task: AgentTask) -> dict[str, Any]:
        """Execute the assigned task.

        Override this method in subclass with actual implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement execute_task"
        )

    async def _handle_assignment(self, assignment: TaskAssignment) -> None:
        self._current_task = AgentTask(assignment)
        self._current_task.started_at = datetime.now(timezone.utc)
        self.profile.state = AgentState.WORKING
        self.profile.current_task_id = assignment.task.id

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="agent_status",
                data={
                    "agent_id": self.profile.id,
                    "name": self.profile.name,
                    "status": "working",
                    "task": assignment.task.name,
                    "progress": 0,
                },
                visual_hint="yellow",
                source=self.profile.id,
            ))

        logger.info(
            "agent.assigned",
            agent=self.profile.name,
            task=assignment.task.name,
        )

    async def _process_current_task(self) -> None:
        assert self._current_task is not None
        try:
            result = await self.execute_task(self._current_task)
            self._current_task.result = result
            self._current_task.completed_at = datetime.now(timezone.utc)

            self.profile.tasks_completed += 1
            self.profile.state = AgentState.IDLE
            self.profile.current_task_id = None

            # Update running averages
            total_seconds = self._current_task.duration_seconds
            if self.profile.avg_completion_time_seconds == 0:
                self.profile.avg_completion_time_seconds = total_seconds
            else:
                self.profile.avg_completion_time_seconds = (
                    self.profile.avg_completion_time_seconds * 0.7
                    + total_seconds * 0.3
                )

            self.profile.success_rate = (
                self.profile.tasks_completed
                / max(1, self.profile.tasks_completed + self.profile.tasks_failed)
            )

            if self.hub:
                await self.hub.push_dashboard_update(DashboardUpdate(
                    update_type="task_progress",
                    data={
                        "agent_id": self.profile.id,
                        "task_id": self._current_task.assignment.task.id,
                        "status": "completed",
                        "result": result,
                    },
                    visual_hint="green",
                    source=self.profile.id,
                ))

            logger.info(
                "agent.task_completed",
                agent=self.profile.name,
                task=self._current_task.assignment.task.name,
                duration=total_seconds,
            )

        except Exception as exc:
            self._current_task.error = str(exc)
            self._current_task.completed_at = datetime.now(timezone.utc)
            self.profile.tasks_failed += 1
            self.profile.state = AgentState.IDLE
            self.profile.current_task_id = None

            if self.hub:
                await self.hub.push_dashboard_update(DashboardUpdate(
                    update_type="alert",
                    data={
                        "agent_id": self.profile.id,
                        "task_id": self._current_task.assignment.task.id,
                        "error": str(exc),
                    },
                    visual_hint="red",
                    source=self.profile.id,
                ))

            logger.error(
                "agent.task_failed",
                agent=self.profile.name,
                task=self._current_task.assignment.task.name,
                error=str(exc),
            )

        self._current_task = None

    # ── Communication ───────────────────────────────────────────────────

    async def send_message(
        self,
        target: str,
        method: str,
        data: dict[str, Any],
        timeout: float = 30.0,
    ) -> AgentMessage | None:
        """Send a direct message to another agent."""
        if not self.hub:
            return None
        return await self.hub.send_message(
            source=self.profile.id,
            target=target,
            method=method,
            data=data,
            timeout=timeout,
        )

    async def publish_event(
        self,
        event_type: EventType,
        payload: dict[str, Any],
    ) -> None:
        """Publish an event to the civilization event bus."""
        if not self.hub:
            return
        await self.hub.publish_event(
            event_type=event_type,
            payload=payload,
            source=self.profile.id,
        )

    async def record_telemetry(self) -> None:
        """Send current agent telemetry."""
        if not self.hub:
            return
        self.hub.record_telemetry(TelemetryData(
            source_component=self.profile.name,
            cpu_percent=0.0,  # Would be real metrics in production
            memory_percent=0.0,
            latency_ms=0.0,
            error_rate=self.profile.tasks_failed / max(1, self.profile.total_tasks),
            requests_per_second=0.0,
        ))

    async def _heartbeat(self) -> None:
        self.profile.last_active = datetime.now(timezone.utc)
        if self.hub:
            self.hub.record_agent_metrics(
                self.profile.id,
                credits=self.profile.credits,
                reputation=self.profile.reputation,
            )

    # ── Evolution ───────────────────────────────────────────────────────

    def mutate_dna(self, intensity: float = 0.15) -> None:
        """Mutate this agent's DNA."""
        self.profile.dna = self.profile.dna.mutate(intensity)
        self.profile.state = AgentState.EVOLVING
        logger.info("agent.dna_mutated", agent=self.profile.name)

    def merge_dna(self, other: BaseAgent) -> AgentDNA:
        """Merge DNA with another agent to create child DNA."""
        return AgentDNA.merge(self.profile.dna, other.profile.dna)

    # ── Utilities ───────────────────────────────────────────────────────

    def assign_task(self, assignment: TaskAssignment) -> None:
        """Queue a task assignment for this agent."""
        self._task_queue.put_nowait(assignment)

    @property
    def is_busy(self) -> bool:
        return self._current_task is not None

    @property
    def is_idle(self) -> bool:
        return not self._current_task and self.profile.state == AgentState.IDLE
