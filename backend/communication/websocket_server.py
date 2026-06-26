"""Authenticated WebSocket server for Command Center updates."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog

from backend.communication.message_types import DashboardUpdate

logger = structlog.get_logger(__name__)


class WebSocketServer:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        auth_token: str | None = None,
        ping_interval: int = 20,
        ping_timeout: int = 20,
    ):
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._clients: dict[str, dict[str, Any]] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._server = None
        self._lock = asyncio.Lock()

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def start(self) -> None:
        if self._server is not None:
            return
        from websockets.asyncio.server import serve

        self._server = await serve(
            self._handler,
            self._host,
            self._port,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
            max_size=1024 * 1024,
        )
        logger.info("websocket.started", host=self._host, port=self._port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        async with self._lock:
            self._clients.clear()
            self._subscriptions.clear()

    async def _handler(self, websocket) -> None:
        client_id: str | None = None
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            registration = json.loads(raw)
            if registration.get("type") != "register":
                await websocket.close(code=1008, reason="registration required")
                return
            if self._auth_token and registration.get("token") != self._auth_token:
                await websocket.close(code=1008, reason="authentication failed")
                return
            client_id = registration.get("client_id")
            if not isinstance(client_id, str) or not client_id.strip():
                await websocket.close(code=1008, reason="client_id required")
                return
            async with self._lock:
                old = self._clients.get(client_id)
                if old:
                    await old["websocket"].close(code=1000, reason="replaced")
                self._clients[client_id] = {
                    "websocket": websocket,
                    "connected_at": time.time(),
                    "subscriptions": set(),
                }
            await websocket.send(json.dumps({"type": "registered", "client_id": client_id}))

            async for raw_message in websocket:
                message = json.loads(raw_message)
                topic = message.get("topic")
                if not isinstance(topic, str) or not topic:
                    continue
                async with self._lock:
                    if message.get("type") == "subscribe":
                        self._subscriptions.setdefault(topic, set()).add(client_id)
                        self._clients[client_id]["subscriptions"].add(topic)
                    elif message.get("type") == "unsubscribe":
                        self._subscriptions.get(topic, set()).discard(client_id)
                        self._clients[client_id]["subscriptions"].discard(topic)
        except Exception:
            logger.debug("websocket.client_closed", client_id=client_id)
        finally:
            if client_id:
                await self._remove_client(client_id)

    async def broadcast(self, update: DashboardUpdate) -> None:
        await self._send_to_clients(set(self._clients), self._serialize(update))

    async def send_to_topic(self, topic: str, update: DashboardUpdate) -> None:
        await self._send_to_clients(
            set(self._subscriptions.get(topic, set())),
            self._serialize(update, topic),
        )

    async def _send_to_clients(self, client_ids: set[str], message: str) -> None:
        failed: list[str] = []
        for client_id in client_ids:
            client = self._clients.get(client_id)
            if client is None:
                continue
            try:
                await client["websocket"].send(message)
            except Exception:
                failed.append(client_id)
        for client_id in failed:
            await self._remove_client(client_id)

    async def _remove_client(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
            for subscribers in self._subscriptions.values():
                subscribers.discard(client_id)

    @staticmethod
    def _serialize(update: DashboardUpdate, topic: str | None = None) -> str:
        payload = {
            "type": "update",
            "update_type": update.update_type,
            "data": update.data,
            "visual_hint": update.visual_hint,
            "timestamp": update.timestamp.isoformat(),
            "source": update.source,
        }
        if topic:
            payload["topic"] = topic
        return json.dumps(payload, separators=(",", ":"))

    def get_connected_clients(self) -> list[str]:
        return sorted(self._clients)

    def get_client_count(self) -> int:
        return len(self._clients)

    def get_topic_subscribers(self, topic: str) -> list[str]:
        return sorted(self._subscriptions.get(topic, set()))
