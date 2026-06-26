"""Reliable Redis Streams event transport with per-subscriber fan-out."""

from __future__ import annotations

import asyncio
import hashlib
import socket
from collections.abc import Awaitable, Callable

import structlog

from backend.communication.message_types import EventMessage

logger = structlog.get_logger(__name__)
EventHandler = Callable[[EventMessage], Awaitable[None]]


class EventBus:
    """Durable event bus.

    Every logical subscriber gets its own Redis consumer group. Instances of
    the same subscriber share that group, which gives fan-out between agents
    and load balancing between replicas of one agent.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        max_connections: int = 50,
        stream_max_length: int = 100_000,
        block_ms: int = 2_000,
        delivery_attempts: int = 5,
    ):
        self._redis_url = redis_url
        self._max_connections = max_connections
        self._stream_max_length = stream_max_length
        self._block_ms = block_ms
        self._delivery_attempts = delivery_attempts
        self._redis = None
        self._running = False
        self._consumer_tasks: list[asyncio.Task] = []

    async def connect(self) -> None:
        import redis.asyncio as aioredis

        if self._redis is not None:
            return
        self._redis = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
            max_connections=self._max_connections,
            health_check_interval=30,
        )
        await self._redis.ping()
        self._running = True
        logger.info("event_bus.connected")

    async def disconnect(self) -> None:
        self._running = False
        for task in self._consumer_tasks:
            task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        self._consumer_tasks.clear()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        logger.info("event_bus.disconnected")

    async def publish(self, event: EventMessage) -> str:
        redis = self._require_connection()
        return await redis.xadd(
            self._stream_key(event.topic),
            {"envelope": event.model_dump_json()},
            maxlen=self._stream_max_length,
            approximate=True,
        )

    async def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        *,
        subscriber_id: str,
        consumer_id: str | None = None,
    ) -> None:
        """Subscribe a logical agent to a topic.

        ``subscriber_id`` must remain stable across restarts. Use the same ID
        for replicas of one agent and different IDs for agents that must each
        receive the event.
        """
        if not topic or not subscriber_id:
            raise ValueError("topic and subscriber_id are required")
        redis = self._require_connection()
        stream = self._stream_key(topic)
        group = self._group_name(subscriber_id)
        consumer = consumer_id or f"{socket.gethostname()}-{id(handler)}"
        try:
            await redis.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        task = asyncio.create_task(
            self._consume(stream, topic, group, consumer, handler),
            name=f"events:{topic}:{subscriber_id}",
        )
        self._consumer_tasks.append(task)

    async def _consume(
        self,
        stream: str,
        topic: str,
        group: str,
        consumer: str,
        handler: EventHandler,
    ) -> None:
        redis = self._require_connection()
        while self._running:
            try:
                entries = await redis.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: ">"},
                    count=20,
                    block=self._block_ms,
                )
                for _, messages in entries:
                    for message_id, fields in messages:
                        await self._deliver(
                            stream, topic, group, message_id, fields, handler
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "event_bus.consume_failed", topic=topic, subscriber=group
                )
                await asyncio.sleep(1)

    async def _deliver(
        self,
        stream: str,
        topic: str,
        group: str,
        message_id: str,
        fields: dict[str, str],
        handler: EventHandler,
    ) -> None:
        redis = self._require_connection()
        try:
            event = EventMessage.model_validate_json(fields["envelope"])
            await handler(event)
            await redis.xack(stream, group, message_id)
        except Exception as exc:
            deliveries = await redis.xpending_range(
                stream, group, min=message_id, max=message_id, count=1
            )
            attempts = deliveries[0]["times_delivered"] if deliveries else 1
            logger.exception(
                "event_bus.delivery_failed",
                topic=topic,
                message_id=message_id,
                attempts=attempts,
            )
            if attempts >= self._delivery_attempts:
                await redis.xadd(
                    f"{stream}:dead-letter",
                    {
                        **fields,
                        "source_message_id": message_id,
                        "error": str(exc),
                    },
                    maxlen=self._stream_max_length,
                    approximate=True,
                )
                await redis.xack(stream, group, message_id)

    async def get_history(self, topic: str, count: int = 100) -> list[EventMessage]:
        redis = self._require_connection()
        entries = await redis.xrevrange(self._stream_key(topic), count=count)
        events: list[EventMessage] = []
        for _, fields in entries:
            try:
                events.append(EventMessage.model_validate_json(fields["envelope"]))
            except Exception:
                logger.warning("event_bus.invalid_history_record", topic=topic)
        return events

    def _require_connection(self):
        if self._redis is None:
            raise RuntimeError("EventBus is not connected")
        return self._redis

    @staticmethod
    def _stream_key(topic: str) -> str:
        return f"events:{topic}"

    @staticmethod
    def _group_name(subscriber_id: str) -> str:
        digest = hashlib.sha256(subscriber_id.encode("utf-8")).hexdigest()[:16]
        return f"subscriber:{digest}"
