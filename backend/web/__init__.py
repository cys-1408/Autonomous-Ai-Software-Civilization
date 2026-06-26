"""Command Center Web Interface.

Provides:
- FastAPI REST API for system control and monitoring
- WebSocket for real-time dashboard updates
- Static frontend for visualization
"""

from backend.web.app import create_app, CivilizationController

__all__ = [
    "create_app",
    "CivilizationController",
]
