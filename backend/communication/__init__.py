"""Communication system — the heart of the AI Civilization.

Eight communication patterns:
1. Event Bus      — Kafka/Redis Streams for topic-based broadcasting
2. Task Market    — Agent bidding protocol for task assignment
3. Direct Comm    — gRPC/REST for agent-to-agent calls
4. Shared Memory  — PostgreSQL/Redis for knowledge sharing
5. Negotiation    — Agent Court dispute resolution protocol
6. Telemetry      — Prometheus metrics for Digital Twin
7. WebSocket      — Real-time updates for Command Center
8. Hub            — Unified interface tying all patterns together
"""

from backend.communication.message_types import (
    Message,
    EventType,
    AgentMessage,
    TaskBid,
    NegotiationMessage,
    TelemetryData,
)
from backend.communication.hub import CommunicationHub

__all__ = [
    "Message",
    "EventType",
    "AgentMessage",
    "TaskBid",
    "NegotiationMessage",
    "TelemetryData",
    "CommunicationHub",
]
