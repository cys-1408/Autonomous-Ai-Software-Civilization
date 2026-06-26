"""AI Civilization — Main Entry Point

Usage:
    # Start the Command Center web server
    python main.py

    # Run the demo communication system
    python demo_communication.py

    # Run a specific component independently
    python -c "from backend.components.goal_interpreter import GoalInterpreter; ..."
"""

import asyncio
import sys

import uvicorn
import structlog

from backend.communication.hub import CommunicationHub
from backend.web.app import create_app, CivilizationController

logger = structlog.get_logger(__name__)


async def main():
    """Initialize and start the AI Civilization."""
    print("=" * 60)
    print("  AI CIVILIZATION — Command Center")
    print("  Autonomous AI Software Engineering System")
    print("=" * 60)

    # Initialize hub and controller
    hub = CommunicationHub()
    controller = CivilizationController(hub=hub)

    # Start the civilization
    await controller.start()

    # Start the web server
    app = create_app(controller)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        ws_max_size=1024 * 1024,
    )
    server = uvicorn.Server(config)

    print("\n  🌐 Command Center: http://localhost:8000/dashboard")
    print("  📡 API:              http://localhost:8000/api/status")
    print("  🔌 WebSocket:        ws://localhost:8000/ws")
    print("  📊 Prometheus:       http://localhost:9091\n")
    print("  Press Ctrl+C to stop\n")

    try:
        await server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        await controller.stop()
        print("\n  👋 Civilization shut down.")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        from demo_communication import main as demo_main
        asyncio.run(demo_main())
    else:
        asyncio.run(main())
