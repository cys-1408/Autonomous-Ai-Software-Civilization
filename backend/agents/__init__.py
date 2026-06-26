"""Agent Runtime System — the executable soul of the AI Civilization.

Each agent is an autonomous worker that:
- Communicates through the CommunicationHub
- Competes in the Task Market
- Evolves through DNA mutation and merging
- Learns from the Failure Memory Network
- Gets spawned and trained by the Agent Factory

The Agent Factory (Component 12) creates new agent types on demand
when it detects a gap in the civilization's capabilities.
"""

from backend.agents.base import BaseAgent, AgentStateMachine
from backend.agents.agent_factory import AgentFactory, AgentTemplate

__all__ = [
    "BaseAgent",
    "AgentStateMachine",
    "AgentFactory",
    "AgentTemplate",
]
