"""Authenticated gRPC transport for direct agent-to-agent requests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections.abc import Awaitable, Callable

import grpc
import structlog

from backend.communication.message_types import AgentMessage

logger = structlog.get_logger(__name__)
AgentHandler = Callable[[AgentMessage], Awaitable[AgentMessage]]
_RPC_PATH = "/ai.civilization.communication.AgentService/Send"


class DirectComm:
    """Hosts local agents and routes remote calls through generic gRPC.

    Generic byte handlers keep the wire contract versioned by the Pydantic
    envelope while avoiding generated-code drift between independently
    deployed agents.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        shared_secret: str | None = None,
        max_message_bytes: int = 4 * 1024 * 1024,
    ):
        self._host = host
        self._port = port
        self._secret = shared_secret.encode() if shared_secret else None
        self._max_message_bytes = max_message_bytes
        self._agents: dict[str, AgentHandler] = {}
        self._endpoints: dict[str, str] = {}
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = grpc.aio.server(
            options=[
                ("grpc.max_receive_message_length", self._max_message_bytes),
                ("grpc.max_send_message_length", self._max_message_bytes),
            ]
        )
        method = grpc.unary_unary_rpc_method_handler(
            self._receive,
            request_deserializer=lambda value: value,
            response_serializer=lambda value: value,
        )
        service = grpc.method_handlers_generic_handler(
            "ai.civilization.communication.AgentService", {"Send": method}
        )
        self._server.add_generic_rpc_handlers((service,))
        bound_port = self._server.add_insecure_port(f"{self._host}:{self._port}")
        if bound_port == 0:
            raise RuntimeError(f"Unable to bind gRPC server to {self._host}:{self._port}")
        await self._server.start()
        logger.info("direct_comm.started", host=self._host, port=bound_port)

    async def stop(self, grace_seconds: float = 5.0) -> None:
        if self._server is not None:
            await self._server.stop(grace_seconds)
            self._server = None

    def register_agent(
        self, agent_id: str, handler: AgentHandler, endpoint: str | None = None
    ) -> None:
        if not agent_id:
            raise ValueError("agent_id is required")
        self._agents[agent_id] = handler
        if endpoint:
            self._endpoints[agent_id] = endpoint

    def register_remote_agent(self, agent_id: str, endpoint: str) -> None:
        if not agent_id or not endpoint:
            raise ValueError("agent_id and endpoint are required")
        self._endpoints[agent_id] = endpoint

    def unregister_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._endpoints.pop(agent_id, None)

    async def send(
        self,
        source: str,
        target: str,
        method: str,
        data: dict,
        timeout: float = 30.0,
        correlation_id: str = "",
    ) -> AgentMessage:
        message = AgentMessage(
            source=source,
            target=target,
            method=method,
            request_data=data,
            correlation_id=correlation_id,
        )
        if target in self._agents:
            return await asyncio.wait_for(self._dispatch(message), timeout)

        endpoint = self._endpoints.get(target)
        if not endpoint:
            raise LookupError(f"No endpoint registered for agent {target!r}")
        payload = message.model_dump_json().encode()
        metadata = self._auth_metadata(payload)
        async with grpc.aio.insecure_channel(
            endpoint,
            options=[
                ("grpc.max_receive_message_length", self._max_message_bytes),
                ("grpc.max_send_message_length", self._max_message_bytes),
            ],
        ) as channel:
            call = channel.unary_unary(
                _RPC_PATH,
                request_serializer=lambda value: value,
                response_deserializer=lambda value: value,
            )
            response = await call(payload, timeout=timeout, metadata=metadata)
        return AgentMessage.model_validate_json(response)

    async def _receive(self, payload: bytes, context) -> bytes:
        if len(payload) > self._max_message_bytes:
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "message too large")
        if not self._verify_auth(payload, context.invocation_metadata()):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid signature")
        try:
            response = await self._dispatch(AgentMessage.model_validate_json(payload))
            return response.model_dump_json().encode()
        except LookupError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except Exception:
            logger.exception("direct_comm.handler_failed")
            await context.abort(grpc.StatusCode.INTERNAL, "agent handler failed")
        raise RuntimeError("unreachable")

    async def _dispatch(self, message: AgentMessage) -> AgentMessage:
        handler = self._agents.get(message.target)
        if handler is None:
            raise LookupError(f"Agent {message.target!r} is not hosted here")
        response = await handler(message)
        if not response.is_response:
            raise ValueError("Agent handlers must return an is_response=True message")
        if response.correlation_id and message.correlation_id:
            if response.correlation_id != message.correlation_id:
                raise ValueError("Response correlation_id does not match request")
        return response

    def _auth_metadata(self, payload: bytes) -> tuple[tuple[str, str], ...]:
        if self._secret is None:
            return ()
        timestamp = str(int(time.time()))
        digest = hmac.new(
            self._secret, timestamp.encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        return (("x-ai-timestamp", timestamp), ("x-ai-signature", digest))

    def _verify_auth(self, payload: bytes, metadata) -> bool:
        if self._secret is None:
            return True
        values = dict(metadata)
        timestamp = values.get("x-ai-timestamp", "")
        signature = values.get("x-ai-signature", "")
        try:
            if abs(time.time() - int(timestamp)) > 60:
                return False
        except ValueError:
            return False
        expected = hmac.new(
            self._secret, timestamp.encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def get_registered_agents(self) -> list[str]:
        return sorted(set(self._agents) | set(self._endpoints))
