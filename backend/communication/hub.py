"""Communication Hub — Unified interface for all communication patterns.

This is the single entry point that agents use to communicate.
It internally delegates to the appropriate transport:

1. Event Bus       → topic broadcasting (Redis Streams)
2. Task Market     → bidding and assignment
3. Direct Comm     → 1:1 agent messages
4. Shared Memory   → knowledge persistence
5. Negotiation     → Court dispute resolution
6. Telemetry       → metrics collection
7. WebSocket       → Command Center updates
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

import structlog

from backend.communication.event_bus import EventBus
from backend.communication.task_market import TaskMarket
from backend.communication.direct_comm import DirectComm
from backend.communication.shared_memory import SharedMemory
from backend.communication.negotiation import NegotiationProtocol
from backend.communication.telemetry import TelemetryCollector
from backend.communication.websocket_server import WebSocketServer
from backend.communication.message_types import (
    EventMessage,
    EventType,
    TaskDefinition,
    TaskBid,
    AgentMessage,
    NegotiationMessage,
    NegotiationStance,
    TelemetryData,
    DashboardUpdate,
)

logger = structlog.get_logger(__name__)


class CommunicationHub:
    """Unified communication interface for the AI Civilization.

    Usage:
        hub = CommunicationHub()
        await hub.connect()

        # Publish events
        await hub.publish_event(EventType.PROJECT_CREATED, payload={...})

        # Register and send direct messages
        hub.register_agent("architect", my_handler)
        response = await hub.send_message("architect", "database", "get_schema", {...})

        # Submit task bids
        assignment = await hub.publish_task(task)
        hub.submit_bid(bid)

        # Record failures
        await hub.record_failure(record)

        # Push dashboard updates
        await hub.push_dashboard_update(update)

        await hub.disconnect()
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_civilization",
        ws_host: str = "0.0.0.0",
        ws_port: int = 8765,
    ):
        # Sub-systems
        self.event_bus = EventBus(redis_url=redis_url)
        self.task_market = TaskMarket()
        self.direct_comm = DirectComm()
        self.shared_memory = SharedMemory(
            redis_url=redis_url,
            postgres_url=postgres_url,
        )
        self.negotiation = NegotiationProtocol()
        self.telemetry = TelemetryCollector()
        self.websocket = WebSocketServer(host=ws_host, port=ws_port)

        self._connected = False

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialize all communication sub-systems."""
        if self._connected:
            return

        await self.event_bus.connect()
        await self.shared_memory.connect()
        self._connected = True
        logger.info("hub.connected")

    async def disconnect(self) -> None:
        """Shut down all communication sub-systems."""
        await self.event_bus.disconnect()
        await self.shared_memory.disconnect()
        await self.websocket.stop()
        self._connected = False
        logger.info("hub.disconnected")

    # ── 1. Event Bus ────────────────────────────────────────────────────

    async def publish_event(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        source: str = "",
        topic: str = "",
    ) -> EventMessage:
        """Publish an event to the civilization-wide event bus."""
        event = EventMessage(
            event_type=event_type,
            payload=payload,
            source=source,
            topic=topic or event_type.value,
        )
        await self.event_bus.publish(event)

        # Also push to Command Center
        await self.push_dashboard_update(
            DashboardUpdate(
                update_type="event",
                data={
                    "event_type": event_type.value,
                    **payload,
                },
                source=source,
                visual_hint="blue",
            )
        )
        return event

    async def subscribe_to_events(
        self,
        topic: str,
        handler,
        group: str = "default",
    ) -> None:
        """Subscribe to events on a topic."""
        await self.event_bus.subscribe(topic, handler, group)

    # ── 2. Task Market ──────────────────────────────────────────────────

    async def publish_task(
        self,
        task: TaskDefinition,
        bidding_timeout: float = 30.0,
    ):
        """Publish a task for agents to bid on."""
        await self.publish_event(
            EventType.TASK_CREATED,
            payload={"task_id": task.id, "name": task.name},
            source="task_market",
        )
        return await self.task_market.publish_task(task, bidding_timeout)

    def submit_bid(self, bid: TaskBid) -> bool:
        """Submit a bid for an active task."""
        return self.task_market.submit_bid(bid)

    def set_agent_reputation(self, agent_id: str, reputation: float) -> None:
        """Update an agent's reputation in the Task Market."""
        self.task_market.set_reputation(agent_id, reputation)

    # ── 3. Direct Agent-to-Agent ────────────────────────────────────────

    def register_agent(self, agent_id: str, handler) -> None:
        """Register an agent for direct messaging."""
        self.direct_comm.register_agent(agent_id, handler)

    async def send_message(
        self,
        source: str,
        target: str,
        method: str,
        data: dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """Send a direct message between agents."""
        return await self.direct_comm.send(source, target, method, data, timeout)

    # ── 4. Shared Memory ────────────────────────────────────────────────

    async def record_failure(self, record) -> None:
        """Record a failure in the Failure Memory Network."""
        await self.shared_memory.record_failure(record)

    async def search_failures(self, **kwargs):
        """Search past failures."""
        return await self.shared_memory.search_failures(**kwargs)

    async def store_genome(self, genome) -> None:
        """Store a Software Genome."""
        await self.shared_memory.store_genome(genome)

    async def set_shared_state(self, key: str, value: Any) -> None:
        """Write to shared state."""
        await self.shared_memory.set_state(key, value)

    async def get_shared_state(self, key: str) -> Optional[Any]:
        """Read from shared state."""
        return await self.shared_memory.get_state(key)

    # ── 5. Negotiation ──────────────────────────────────────────────────

    async def convene_court(
        self,
        dispute_id: str,
        topic: str,
        parties: list[str],
        description: str = "",
        judge_count: int = 5,
    ):
        """Convene the Agent Court for a dispute."""
        dispute = await self.negotiation.convene(
            dispute_id, topic, parties, description, judge_count
        )
        await self.publish_event(
            EventType.COURT_CONVENED,
            payload={"dispute_id": dispute_id, "topic": topic},
            source="agent_court",
        )
        return dispute

    async def submit_court_evidence(
        self,
        dispute_id: str,
        message: NegotiationMessage,
    ) -> bool:
        """Submit evidence to the court."""
        return await self.negotiation.submit_evidence(dispute_id, message)

    async def cast_court_vote(
        self,
        dispute_id: str,
        vote: NegotiationMessage,
    ) -> bool:
        """Cast a judge's vote."""
        return await self.negotiation.cast_vote(dispute_id, vote)

    # ── 6. Telemetry ────────────────────────────────────────────────────

    def record_telemetry(self, data: TelemetryData) -> None:
        """Record telemetry from a component."""
        self.telemetry.record(data)

    def get_system_metrics(self) -> dict:
        """Get aggregate system metrics."""
        return self.telemetry.get_system_summary()

    def get_digital_twin_config(self) -> dict:
        """Get Digital Twin simulation parameters."""
        return self.telemetry.get_digital_twin_config()

    # ── 7. WebSocket / Command Center ───────────────────────────────────

    async def push_dashboard_update(self, update: DashboardUpdate) -> None:
        """Push a real-time update to all Command Center clients."""
        await self.websocket.broadcast(update)

    async def push_to_topic(self, topic: str, update: DashboardUpdate) -> None:
        """Push an update to clients subscribed to a specific topic."""
        await self.websocket.send_to_topic(topic, update)

    # ── Utilities ───────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get the status of all communication sub-systems."""
        return {
            "connected": self._connected,
            "event_bus": self.event_bus is not None,
            "task_market": {
                "active_tasks": len(self.task_market._active_tasks),
                "leaderboard": self.task_market.get_leaderboard()[:5],
            },
            "direct_comm": {
                "registered_agents": self.direct_comm.get_registered_agents(),
            },
            "shared_memory": self.shared_memory.get_stats(),
            "negotiation": {
                "active_disputes": len(self.negotiation.get_active_disputes()),
            },
            "telemetry": {
                "components": self.telemetry.get_all_components(),
                "summary": self.telemetry.get_system_summary(),
            },
            "websocket": {
                "connected_clients": self.websocket.get_client_count(),
            },
        }
