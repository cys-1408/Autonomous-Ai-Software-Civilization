"""Tests for the EventBus communication pattern."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.communication.event_bus import EventBus
from backend.communication.message_types import EventMessage, EventType


@pytest.fixture
def event_bus():
    """Create an EventBus instance for testing."""
    bus = EventBus(redis_url="redis://localhost:6379/0")
    bus._redis = AsyncMock()
    bus._running = True
    return bus


class TestEventBusInitialization:
    """Test EventBus creation and config."""

    def test_init_sets_defaults(self):
        bus = EventBus(redis_url="redis://localhost:6379/0")
        assert bus._redis_url == "redis://localhost:6379/0"
        assert bus._max_connections == 50
        assert bus._stream_max_length == 100_000
        assert bus._delivery_attempts == 5

    def test_init_custom_params(self):
        bus = EventBus(
            redis_url="redis://custom:6380/1",
            max_connections=10,
            stream_max_length=1000,
            delivery_attempts=3,
        )
        assert bus._redis_url == "redis://custom:6380/1"
        assert bus._max_connections == 10
        assert bus._stream_max_length == 1000
        assert bus._delivery_attempts == 3


class TestEventBusPublishing:
    """Test event publishing functionality."""

    @pytest.mark.asyncio
    async def test_publish_returns_message_id(self, event_bus):
        event_bus._redis.xadd.return_value = b"12345-0"
        event = EventMessage(event_type=EventType.PROJECT_CREATED, payload={"test": True})
        msg_id = await event_bus.publish(event)
        assert msg_id == b"12345-0"
        event_bus._redis.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_raises_if_not_connected(self):
        bus = EventBus(redis_url="redis://localhost:6379/0")
        with pytest.raises(RuntimeError, match="not connected"):
            await bus.publish(EventMessage(event_type=EventType.PROJECT_CREATED))


class TestEventBusStreamKey:
    """Test stream key generation."""

    def test_stream_key_format(self):
        key = EventBus._stream_key("test.topic")
        assert key == "events:test.topic"

    def test_group_name_format(self):
        group = EventBus._group_name("agent_123")
        assert group.startswith("subscriber:")
        assert len(group) > len("subscriber:")


class TestEventBusSubscribe:
    """Test subscribing to topics."""

    @pytest.mark.asyncio
    async def test_subscribe_validates_params(self, event_bus):
        with pytest.raises(ValueError):
            await event_bus.subscribe("", AsyncMock(), subscriber_id="test")
        with pytest.raises(ValueError):
            await event_bus.subscribe("topic", AsyncMock(), subscriber_id="")

    @pytest.mark.asyncio
    async def test_subscribe_creates_consumer(self, event_bus):
        handler = AsyncMock()
        await event_bus.subscribe("test.topic", handler, subscriber_id="test_agent")
        assert len(event_bus._consumer_tasks) == 1
        assert event_bus._consumer_tasks[0].get_name() == "events:test.topic:test_agent"


class TestEventBusHistory:
    """Test event history retrieval."""

    @pytest.mark.asyncio
    async def test_get_history_empty(self, event_bus):
        event_bus._redis.xrevrange.return_value = []
        events = await event_bus.get_history("test.topic")
        assert events == []

    @pytest.mark.asyncio
    async def test_get_history_returns_events(self, event_bus):
        valid_event = EventMessage(
            event_type=EventType.PROJECT_CREATED,
            payload={"project": "test"},
        ).model_dump_json()
        event_bus._redis.xrevrange.return_value = [
            (b"1-0", {"envelope": valid_event})
        ]
        events = await event_bus.get_history("test.topic", count=10)
        assert len(events) == 1
        assert events[0].event_type == EventType.PROJECT_CREATED
