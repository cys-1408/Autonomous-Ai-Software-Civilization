"""AI Civilization — Backend package.

A fully autonomous AI-powered software engineering civilization.

Components:
- communication: 8 communication patterns (Event Bus, Task Market, Direct Comm, etc.)
- components: 12 major subsystems (Goal Interpreter, Agent Economy, etc.)
- agents: Agent runtime system with DNA evolution and factory
- models: Domain models for all subsystems
- config: Configuration management
- web: FastAPI Command Center with dashboard UI
"""

from backend import communication
from backend import components
from backend import agents
from backend import models
from backend import config

__all__ = [
    "communication",
    "components",
    "agents",
    "models",
    "config",
]
