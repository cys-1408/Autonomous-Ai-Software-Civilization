"""Tests for CommunicationHub — unified communication interface."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    TaskDefinition,
    TaskPriority,
    TaskBid,
    DashboardUpdate,
    FailureRecord,
    GenomeRecord,
)


@pytest.fixture
def hub():
    """Create a CommunicationHub with mocked sub-systems."""
    h = CommunicationHub(
        redis_url="redis://test:6379/0",
        postgres_url="postgresql+asyncpg://test:test@localhost:5432/test",
        ws_host="localhost",
        ws_port=8765,
    )
    # Mock all sub-transports
    h.event_bus = AsyncMock()
    h.event_bus.publish = AsyncMock()
    h.task_market = MagicMock()
    h.direct_comm = MagicMock()
    h.shared_memory = AsyncMock()
    h.shared_memory.record_failure = AsyncMock()
    h.shared_memory.search_failures = AsyncMock()
    h.shared_memory.store_genome = AsyncMock()
    h.shared_memory.set_state = AsyncMock()
    h.shared_memory.get_state = AsyncMock()
    h.negotiation = MagicMock()
    h.negotiation.convene = AsyncMock()
    h.negotiation.submit_evidence = AsyncMock()
    h.negotiation.cast_vote = AsyncMock()
    h.telemetry = MagicMock()
    h.websocket = MagicMock()
    h.websocket.broadcast = AsyncMock()
    h.websocket.send_to_topic = AsyncMock()
    return h


class TestHubLifecycle:
    @pytest.mark.asyncio
    async def test_connect(self, hub):
        hub.event_bus.connect = AsyncMock()
        hub.shared_memory.connect = AsyncMock()
        await hub.connect()
        assert hub._connected is True
        hub.event_bus.connect.assert_called_once()
        hub.shared_memory.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, hub):
        hub._connected = True
        hub.event_bus.disconnect = AsyncMock()
        hub.shared_memory.disconnect = AsyncMock()
        hub.websocket.stop = AsyncMock()
        await hub.disconnect()
        assert hub._connected is False


class TestHubEventBus:
    @pytest.mark.asyncio
    async def test_publish_event(self, hub):
        event = await hub.publish_event(
            EventType.PROJECT_CREATED,
            payload={"project": "test"},
            source="test_agent",
        )
        assert event.event_type == EventType.PROJECT_CREATED

    @pytest.mark.asyncio
    async def test_subscribe(self, hub):
        handler = AsyncMock()
        await hub.subscribe_to_events("test.topic", handler, group="test")
        hub.event_bus.subscribe.assert_called_once()


class TestHubTaskMarket:
    @pytest.mark.asyncio
    async def test_publish_task(self, hub):
        hub.task_market.publish_task = AsyncMock()
        task = TaskDefinition(name="Test Task", difficulty=5)
        await hub.publish_task(task, bidding_timeout=1.0)
        hub.task_market.publish_task.assert_called_once_with(task, 1.0)

    def test_submit_bid(self, hub):
        hub.task_market.submit_bid.return_value = True
        bid = TaskBid(source="agent", task_id="t1", bid_amount=10, confidence=0.9)
        result = hub.submit_bid(bid)
        assert result is True

    def test_set_agent_reputation(self, hub):
        hub.set_agent_reputation("agent_1", 85.0)
        hub.task_market.set_reputation.assert_called_once_with("agent_1", 85.0)


class TestHubDirectComm:
    def test_register_agent(self, hub):
        handler = MagicMock()
        hub.register_agent("test_agent", handler)
        hub.direct_comm.register_agent.assert_called_once_with("test_agent", handler)

    @pytest.mark.asyncio
    async def test_send_message(self, hub):
        hub.direct_comm.send = AsyncMock()
        await hub.send_message("src", "target", "method", {"key": "value"})
        hub.direct_comm.send.assert_called_once()


class TestHubSharedMemory:
    @pytest.mark.asyncio
    async def test_record_failure(self, hub):
        failure = FailureRecord(
            failure_type="sql_injection",
            root_cause="test",
            affected_code="file.py:1",
            fix_applied="fixed",
            severity=8,
            project_id="test",
        )
        await hub.record_failure(failure)
        hub.shared_memory.record_failure.assert_called_once_with(failure)

    @pytest.mark.asyncio
    async def test_search_failures(self, hub):
        hub.shared_memory.search_failures.return_value = []
        results = await hub.search_failures(failure_type="sql_injection")
        assert results == []

    @pytest.mark.asyncio
    async def test_store_genome(self, hub):
        genome = GenomeRecord(
            project_id="p1",
            architecture_pattern="microservice",
            security_model="zero_trust",
            database_choice="postgresql",
            deployment_target="kubernetes",
            success_rating=0.85,
        )
        await hub.store_genome(genome)
        hub.shared_memory.store_genome.assert_called_once_with(genome)

    @pytest.mark.asyncio
    async def test_shared_state(self, hub):
        hub.shared_memory.set_state.return_value = None
        hub.shared_memory.get_state.return_value = "value"
        await hub.set_shared_state("key", "value")
        hub.shared_memory.set_state.assert_called_once_with("key", "value")
        result = await hub.get_shared_state("key")
        assert result == "value"


class TestHubNegotiation:
    @pytest.mark.asyncio
    async def test_convene_court(self, hub):
        hub.negotiation.convene.return_value = MagicMock()
        dispute = await hub.convene_court("d1", "Test", ["p1", "p2"])
        assert dispute is not None

    @pytest.mark.asyncio
    async def test_court_evidence_and_vote(self, hub):
        hub.negotiation.submit_evidence = AsyncMock(return_value=True)
        hub.negotiation.cast_vote = AsyncMock(return_value=True)
        msg = MagicMock()
        assert await hub.submit_court_evidence("d1", msg) is True
        assert await hub.cast_court_vote("d1", msg) is True


class TestHubTelemetry:
    def test_record_telemetry(self, hub):
        from backend.communication.message_types import TelemetryData
        data = TelemetryData(source_component="test", cpu_percent=50.0)
        hub.record_telemetry(data)
        hub.telemetry.record.assert_called_once_with(data)

    def test_system_metrics(self, hub):
        hub.telemetry.get_system_summary.return_value = {"component_count": 3}
        summary = hub.get_system_metrics()
        assert summary["component_count"] == 3

    def test_digital_twin_config(self, hub):
        hub.telemetry.get_digital_twin_config.return_value = {"simulated_users": 100000}
        config = hub.get_digital_twin_config()
        assert config["simulated_users"] == 100000


class TestHubWebSocket:
    @pytest.mark.asyncio
    async def test_push_dashboard_update(self, hub):
        update = DashboardUpdate(update_type="test", data={"msg": "hello"})
        await hub.push_dashboard_update(update)
        hub.websocket.broadcast.assert_called_once_with(update)

    @pytest.mark.asyncio
    async def test_push_to_topic(self, hub):
        update = DashboardUpdate(update_type="test", data={"msg": "hello"})
        await hub.push_to_topic("agents", update)
        hub.websocket.send_to_topic.assert_called_once_with("agents", update)


class TestHubStatus:
    def test_get_status_basic(self, hub):
        hub._connected = True
        hub.task_market._active_tasks = {}
        hub.task_market.get_leaderboard.return_value = []
        hub.direct_comm.get_registered_agents.return_value = []
        hub.shared_memory.get_stats = MagicMock(return_value={"failure_records": 0, "genome_records": 0})
        hub.negotiation.get_active_disputes.return_value = []
        hub.telemetry.get_all_components.return_value = []
        hub.telemetry.get_system_summary.return_value = {}
        hub.websocket.get_client_count.return_value = 0

        status = hub.get_status()
        assert status["connected"] is True
        assert "event_bus" in status
        assert "task_market" in status
        assert "direct_comm" in status
        assert "shared_memory" in status
        assert "negotiation" in status
        assert "telemetry" in status
        assert "websocket" in status
