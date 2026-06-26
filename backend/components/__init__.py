"""Component Implementations — the 12 subsystems of the AI Civilization.

Every component is an autonomous service that communicates through the
CommunicationHub to form a distributed software engineering civilization.

Components:
1.  Goal Interpreter      — Converts user intent into machine tasks
2.  Agent Economy         — Stock-market task allocation
3.  Agent DNA System      — (in backend.models.agent) Evolution engine
4.  Development Civilization — Actual code generation pipeline
5.  Adversarial War Engine   — Security attack/defense
6.  Formal Verification     — Mathematical correctness proofs
7.  Digital Twin World      — Production simulation + chaos testing
8.  Software Genome         — (in backend.communication.shared_memory) Pattern DB
9.  Agent Court System      — (in backend.communication.negotiation) Disputes
10. Failure Memory Network  — (in backend.communication.shared_memory) Mistake DB
11. Autonomous Cloud Architect — Auto-deployment
12. Agent Factory           — (in backend.agents.agent_factory) New agent creation
"""

from backend.components.goal_interpreter import GoalInterpreter
from backend.components.agent_economy import AgentEconomy
from backend.components.development_civilization import DevelopmentCivilization
from backend.components.adversarial_engine import AdversarialWarEngine
from backend.components.formal_verification import FormalVerificationEngine
from backend.components.digital_twin import DigitalTwinWorld
from backend.components.cloud_architect import AutonomousCloudArchitect


__all__ = [
    "GoalInterpreter",
    "AgentEconomy",
    "DevelopmentCivilization",
    "AdversarialWarEngine",
    "FormalVerificationEngine",
    "DigitalTwinWorld",
    "AutonomousCloudArchitect",
]
