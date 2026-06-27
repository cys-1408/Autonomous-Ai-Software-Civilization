"""FastAPI-based Command Center that gives visibility into the civilization.

Provides:
- REST API for controlling the civilization
- WebSocket endpoint for real-time streaming
- Dashboard serving static files
- Metrics export (Prometheus)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.communication.hub import CommunicationHub
from backend.components.goal_interpreter import GoalInterpreter
from backend.components.agent_economy import AgentEconomy
from backend.components.development_civilization import DevelopmentCivilization
from backend.components.adversarial_engine import AdversarialWarEngine
from backend.components.formal_verification import FormalVerificationEngine
from backend.components.digital_twin import DigitalTwinWorld
from backend.components.cloud_architect import AutonomousCloudArchitect
from backend.agents.agent_factory import AgentFactory, AgentTemplate
from backend.models.agent import Specialization, AgentDNA

logger = structlog.get_logger(__name__)


class CivilizationController:
    """Central controller that wires all 12 components together."""

    def __init__(self, hub: CommunicationHub | None = None):
        self.hub = hub or CommunicationHub()
        self.goal_interpreter = GoalInterpreter(hub=self.hub)
        self.agent_economy = AgentEconomy(hub=self.hub)
        self.development_civilization = DevelopmentCivilization(hub=self.hub)
        self.adversarial_engine = AdversarialWarEngine(hub=self.hub)
        self.verification_engine = FormalVerificationEngine(hub=self.hub)
        self.digital_twin = DigitalTwinWorld(hub=self.hub)
        self.cloud_architect = AutonomousCloudArchitect(hub=self.hub)
        self.agent_factory = AgentFactory(hub=self.hub)

        self._running = False
        self._projects: dict[str, Any] = {}

    async def start(self) -> None:
        """Start the hub and all components."""
        await self.hub.connect()
        await self.agent_factory.start(hub=self.hub)
        self._running = True
        logger.info("civilization.started")

    async def stop(self) -> None:
        """Gracefully shut down all components."""
        await self.agent_factory.stop()
        await self.hub.disconnect()
        self._running = False
        logger.info("civilization.stopped")

    async def submit_goal(self, raw_input: str) -> dict[str, Any]:
        """Submit a user goal and run through the entire pipeline."""
        # Step 1: Interpret the goal
        spec = await self.goal_interpreter.interpret(raw_input)

        # Step 2: Register initial agents for development
        for module in spec.modules:
            template_name = f"auto_{module.name.lower().replace(' ', '_')}"
            template = AgentTemplate(
                name=template_name,
                specialization=Specialization.BACKEND,
                description=f"Agent for {module.name}",
            )
            self.agent_factory.register_template(template)
            agent = self.agent_factory.spawn_agent(template_name)
            if agent:
                self.agent_economy.register_agent(agent.profile)

        # Step 3: Run the development pipeline
        dev_result = await self.development_civilization.run_pipeline(spec)

        # Step 4: Run adversarial security scan
        for module in spec.modules:
            scan = await self.adversarial_engine.run_full_scan(
                target_module=module.name,
                project_id=spec.id,
            )

        # Step 5: Run formal verification
        verification = await self.verification_engine.verify_module(
            module_name=spec.title,
            code_path=f"projects/{spec.id}",
            project_id=spec.id,
        )

        # Step 6: Run Digital Twin simulation
        config = self.digital_twin.create_config(
            name=f"DT_{spec.title}",
            project_id=spec.id,
            duration_minutes=30.0,
        )
        simulation = await self.digital_twin.run_simulation(config)

        # Step 7: Generate deployment plan
        evaluations = self.cloud_architect.evaluate_providers()
        best_provider = evaluations[0].provider if evaluations else None
        infra = self.cloud_architect.generate_infrastructure(
            project_id=spec.id,
            services=[],
            provider=best_provider or "aws",
        )
        deployment = await self.cloud_architect.create_deployment_plan(
            project_id=spec.id,
            infrastructure=infra,
        )

        result = {
            "project_spec": spec.model_dump(mode="json"),
            "development": dev_result,
            "adversarial_scan": {
                "scans": len(self.adversarial_engine._attack_results),
                "vulnerabilities": len(self.adversarial_engine._vulnerabilities),
                "open": len(self.adversarial_engine.get_open_vulnerabilities()),
            },
            "verification": verification.model_dump(mode="json"),
            "simulation": {
                "passed": simulation.passed,
                "total_requests": simulation.total_requests,
                "error_rate": simulation.error_rate,
                "p99_latency": simulation.p99_latency_ms,
                "chaos_survival_rate": simulation.survival_rate,
            },
            "deployment": {
                "plan_id": deployment.id,
                "status": deployment.status.value,
                "estimated_cost": infra.estimated_monthly_cost,
            },
            "recommendation": simulation.recommendation,
        }

        self._projects[spec.id] = result
        return result


def create_app(controller: CivilizationController) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Civilization — Command Center",
        description="Autonomous AI Software Engineering Civilization",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST API Endpoints ──────────────────────────────────────────

    @app.get("/")
    async def root():
        return {
            "name": "AI Civilization",
            "version": "1.0.0",
            "status": "operational" if controller._running else "stopped",
        }

    @app.post("/api/goal")
    async def submit_goal(request: Request):
        """Submit a software development goal to the civilization."""
        body = await request.json()
        raw_input = body.get("input", "")
        if not raw_input:
            return JSONResponse(
                status_code=400,
                content={"error": "input is required"},
            )

        result = await controller.submit_goal(raw_input)
        return result

    @app.get("/api/status")
    async def system_status():
        """Get the status of all civilization components."""
        return {
            "hub": controller.hub.get_status(),
            "economy": controller.agent_economy.get_market_summary(),
            "agents": controller.agent_factory.get_stats(),
            "security": controller.adversarial_engine.get_stats(),
            "verification": controller.verification_engine.get_stats(),
            "simulation": controller.digital_twin.get_stats(),
            "deployment": controller.cloud_architect.get_stats(),
        }

    @app.get("/api/agents")
    async def list_agents():
        """List all agents in the civilization."""
        return {
            "agents": controller.agent_factory.list_agents(),
            "economy_leaderboard": controller.agent_economy.get_leaderboard(),
        }

    @app.get("/api/projects")
    async def list_projects():
        """List all projects and their results."""
        return {
            "projects": list(controller._projects.values()),
        }

    @app.get("/api/metrics")
    async def get_metrics():
        """Get Prometheus-format metrics."""
        from backend.communication.telemetry import TelemetryCollector
        from prometheus_client import generate_latest

        if hasattr(controller.hub, "telemetry"):
            return Response(
                content=controller.hub.telemetry.export_prometheus(),
                media_type="text/plain",
            )
        return {"error": "telemetry not available"}

    @app.get("/api/verify")
    async def run_verification(module: str = "auth", domain: str = "authentication"):
        """Run formal verification on a module."""
        from backend.models.verification import VerificationDomain

        try:
            vdomain = VerificationDomain(domain)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid domain: {domain}"},
            )

        result = await controller.verification_engine.verify_module(
            module_name=module,
            domain=vdomain,
        )
        return result.model_dump(mode="json")

    @app.post("/api/attack")
    async def run_adversarial_scan(request: Request):
        """Run an adversarial security scan."""
        body = await request.json()
        result = await controller.adversarial_engine.run_full_scan(
            target_module=body.get("module", ""),
            target_file=body.get("file", ""),
            project_id=body.get("project_id", ""),
        )
        return result.model_dump(mode="json")

    @app.post("/api/simulate")
    async def run_simulation(request: Request):
        """Run a Digital Twin simulation."""
        body = await request.json()
        config = controller.digital_twin.create_config(
            name=body.get("name", "api_simulation"),
            project_id=body.get("project_id", ""),
            duration_minutes=body.get("duration", 10),
            chaos_scenario=body.get("chaos_scenario", "basic_resilience"),
        )
        result = await controller.digital_twin.run_simulation(config)
        return result.model_dump(mode="json")

    @app.post("/api/deploy")
    async def deploy(request: Request):
        """Deploy a project to the cloud."""
        body = await request.json()
        evaluations = controller.cloud_architect.evaluate_providers(
            project_region=body.get("region", "us-east-1"),
            compliance_reqs=body.get("compliance", []),
        )
        return {
            "recommendations": [e.model_dump(mode="json") for e in evaluations],
        }

    @app.get("/api/economy")
    async def get_economy():
        """Get the state of the agent economy."""
        return {
            "leaderboard": controller.agent_economy.get_leaderboard(20),
            "market_summary": controller.agent_economy.get_market_summary(),
        }

    # ── WebSocket Endpoint ────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        client_id = f"dashboard_{id(websocket)}"

        # Register with the hub's WebSocket server
        controller.hub.websocket._clients[client_id] = {
            "websocket": websocket,
            "connected_at": __import__("time").time(),
            "subscriptions": set(),
        }

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong"})
                    )

        except WebSocketDisconnect:
            pass
        finally:
            controller.hub.websocket._clients.pop(client_id, None)

    # ── Static Dashboard ──────────────────────────────────────────

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        """Serve the Command Center dashboard UI."""
        return HTMLResponse(content=get_dashboard_html())

    return app


def get_dashboard_html() -> str:
    """Return the HTML for the Command Center dashboard.

    A professional, animated dashboard with:
    - Particle network background
    - Real-time WebSocket updates
    - Agent topology visualization
    - Multi-chart metrics
    - Pipeline timeline view
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Civilization — Command Center</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#05080f;--surface:#0b1120;--surface2:#101828;--border:#1a2a4a;--primary:#4fc3f7;--success:#00e676;--warn:#ffc400;--danger:#ff1744;--purple:#ce93d8;--text:#e0e6f0;--muted:#5a6a8a;--radius:12px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
/* Animated particle background */
#particles-canvas{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:0.4}
/* Scrollbar */
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
/* Header */
.header{position:relative;z-index:10;background:linear-gradient(180deg,rgba(11,17,32,0.98),rgba(11,17,32,0.85));border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(20px)}
.header-left{display:flex;align-items:center;gap:12px}
.header-logo{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,var(--primary),var(--success));display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:var(--bg)}
.header h1{font-size:18px;font-weight:700;background:linear-gradient(90deg,#4fc3f7,#00e676,#ce93d8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-size:200% auto;animation:gradientShift 4s ease infinite}
@keyframes gradientShift{0%,100%{background-position:0 center}50%{background-position:200% center}}
.header-status{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--muted)}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--success);animation:pulse 2s ease-in-out infinite;box-shadow:0 0 12px rgba(0,230,118,0.4)}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.5;transform:scale(0.8)}}
/* Container */
.container{position:relative;z-index:1;padding:20px 24px;max-width:1440px;margin:0 auto}
/* Input section */
.hero{background:linear-gradient(135deg,var(--surface),var(--surface2));border:1px solid var(--border);border-radius:16px;padding:28px;margin-bottom:24px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-50%;right:-20%;width:300px;height:300px;background:radial-gradient(circle,rgba(79,195,247,0.08),transparent 70%);pointer-events:none}
.hero h2{font-size:16px;font-weight:600;margin-bottom:4px;color:var(--primary)}
.hero p{font-size:13px;color:var(--muted);margin-bottom:16px}
.hero-input-row{display:flex;gap:12px}
.hero textarea{flex:1;padding:14px 16px;background:rgba(5,8,15,0.7);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;font-family:inherit;resize:vertical;min-height:60px;transition:border-color 0.3s}
.hero textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 20px rgba(79,195,247,0.1)}
.hero textarea::placeholder{color:#3a4a6a}
.btn-primary{padding:14px 32px;background:linear-gradient(135deg,var(--primary),#00bcd4);border:none;border-radius:10px;color:var(--bg);font-weight:700;font-size:14px;cursor:pointer;transition:all 0.3s;white-space:nowrap;align-self:flex-end}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(79,195,247,0.3)}
.btn-primary:disabled{opacity:0.4;cursor:not-allowed;transform:none;box-shadow:none}
.btn-sm{padding:8px 16px;font-size:12px;border-radius:6px}
/* Metric cards grid */
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:24px}
.card{background:linear-gradient(135deg,var(--surface),var(--surface2));border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;transition:all 0.3s;position:relative;overflow:hidden}
.card:hover{border-color:var(--primary);transform:translateY(-2px);box-shadow:0 8px 30px rgba(79,195,247,0.08)}
.card .icon{font-size:20px;margin-bottom:8px}
.card .value{font-size:28px;font-weight:800;letter-spacing:-0.5px;margin-bottom:2px}
.card .label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
.card .trend{font-size:11px;margin-top:6px;display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:4px}
.trend-up{background:rgba(0,230,118,0.12);color:var(--success)}
.trend-down{background:rgba(255,23,68,0.12);color:var(--danger)}
/* Cards with accent borders */
.card-accent-blue{border-left:3px solid var(--primary)}
.card-accent-green{border-left:3px solid var(--success)}
.card-accent-red{border-left:3px solid var(--danger)}
.card-accent-yellow{border-left:3px solid var(--warn)}
.card-accent-purple{border-left:3px solid var(--purple)}
/* Badges */
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-pass{background:rgba(0,230,118,0.15);color:var(--success)}
.badge-fail{background:rgba(255,23,68,0.15);color:var(--danger)}
.badge-warn{background:rgba(255,196,0,0.15);color:var(--warn)}
.badge-info{background:rgba(79,195,247,0.15);color:var(--primary)}
/* Tabs */
.tabs{display:flex;gap:2px;margin-bottom:16px;border-bottom:1px solid rgba(26,42,74,0.5);padding-bottom:0}
.tab{padding:10px 18px;border-radius:8px 8px 0 0;font-size:13px;cursor:pointer;color:var(--muted);border:1px solid transparent;border-bottom:none;transition:all 0.3s;font-weight:500}
.tab:hover{color:var(--text);background:rgba(79,195,247,0.05)}
.tab.active{color:var(--primary);border-color:var(--border);background:rgba(79,195,247,0.08)}
/* Panels */
.panel{background:linear-gradient(135deg,var(--surface),var(--surface2));border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:16px;min-height:200px}
.panel-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.panel-header h3{font-size:14px;font-weight:600;color:var(--primary)}
.panel-header .badge{font-size:10px}
.chart-container{height:240px;margin-top:8px}
.chart-container-sm{height:120px;margin-top:8px}
/* Agent items */
.agent-list{display:flex;flex-direction:column;gap:2px}
.agent-item{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;padding:10px 14px;border-radius:8px;transition:all 0.2s;font-size:13px}
.agent-item:hover{background:rgba(79,195,247,0.05)}
.agent-item .name{font-weight:500;color:var(--text)}
.agent-item .spec{font-size:11px;color:var(--muted)}
.agent-item .stats{display:flex;gap:12px;font-size:12px;color:var(--muted)}
.agent-item .stat-val{font-weight:600;color:var(--text)}
/* Progress bars */
.progress-bar{height:4px;background:rgba(26,42,74,0.5);border-radius:2px;overflow:hidden;margin-top:4px}
.progress-fill{height:100%;border-radius:2px;transition:width 1s ease}
.progress-blue{background:linear-gradient(90deg,var(--primary),#00bcd4)}
.progress-green{background:linear-gradient(90deg,var(--success),#00e676)}
.progress-red{background:linear-gradient(90deg,var(--danger),#ff1744)}
/* Pipeline stages */
.pipeline{display:flex;gap:8px;margin:12px 0;flex-wrap:wrap}
.pipeline-step{flex:1;min-width:120px;padding:12px;border-radius:8px;border:1px solid var(--border);text-align:center;font-size:11px;transition:all 0.3s}
.pipeline-step.done{border-color:var(--success);background:rgba(0,230,118,0.06)}
.pipeline-step.active{border-color:var(--primary);background:rgba(79,195,247,0.08);animation:pulse 2s infinite}
.pipeline-step.pending{border-color:var(--border);opacity:0.5}
.pipeline-step .step-icon{font-size:18px;margin-bottom:4px}
.pipeline-step .step-label{color:var(--muted)}
/* Topology network */
.topology{position:relative;width:100%;height:240px;border-radius:8px;overflow:hidden}
.topology svg{width:100%;height:100%}
.topology text{fill:var(--muted);font-size:10px}
/* Grid for results */
.result-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.result-card{padding:14px;border-radius:8px;border:1px solid var(--border);background:rgba(5,8,15,0.4)}
.result-card h4{font-size:12px;font-weight:600;margin-bottom:6px;color:var(--primary)}
.result-card .rval{font-size:20px;font-weight:700}
.result-card .rsub{font-size:11px;color:var(--muted);margin-top:2px}
/* Modal */
.modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:100;display:none;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
.modal-overlay.show{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px;width:90%;max-width:800px;max-height:80vh;overflow-y:auto}
.modal h3{font-size:16px;margin-bottom:12px;color:var(--primary)}
.modal pre{background:rgba(5,8,15,0.6);padding:16px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.6;color:var(--muted);max-height:400px;overflow-y:auto}
.modal-close{float:right;background:none;border:none;color:var(--muted);font-size:20px;cursor:pointer;padding:4px 8px}
.modal-close:hover{color:var(--text)}
/* Responsive */
@media(max-width:768px){.container{padding:12px}.grid{grid-template-columns:1fr 1fr}.hero-input-row{flex-direction:column}.hero-input-row .btn-primary{width:100%}.tabs{overflow-x:auto;flex-wrap:nowrap}.tab{white-space:nowrap}.result-grid{grid-template-columns:1fr}}
@media(max-width:480px){.grid{grid-template-columns:1fr}.header{padding:10px 16px}.header h1{font-size:15px}}
</style>
</head>
<body>
<canvas id="particles-canvas"></canvas>

<!-- Header -->
<header class="header">
  <div class="header-left">
    <div class="header-logo">⚡</div>
    <h1>AI Civilization — Command Center</h1>
  </div>
  <div class="header-status">
    <span class="status-dot" id="statusDot"></span>
    <span id="statusText">Connecting...</span>
    <span style="opacity:0.3">|</span>
    <span id="uptimeText">v1.0</span>
  </div>
</header>

<div class="container">
  <!-- Hero / Submit -->
  <div class="hero">
    <h2>🚀 Submit Software Goal</h2>
    <p>Describe any software system and the civilization will build, test, verify, and deploy it.</p>
    <div class="hero-input-row">
      <textarea id="goalInput" placeholder='e.g., "Build a Hospital Management System with patient records, doctor scheduling, online billing, and pharmacy"'></textarea>
      <button class="btn-primary" id="submitBtn" onclick="submitGoal()">Build It →</button>
    </div>
  </div>

  <!-- Metric Cards -->
  <div class="grid" id="metricsGrid">
    <div class="card card-accent-blue">
      <div class="icon">🤖</div>
      <div class="value" id="agentCount">0</div>
      <div class="label">Active Agents</div>
      <div class="trend trend-up" id="agentTrend">+0 this session</div>
    </div>
    <div class="card card-accent-green">
      <div class="icon">💰</div>
      <div class="value" id="totalCredits">0</div>
      <div class="label">Credits in Circulation</div>
      <div class="trend trend-up" id="creditTrend">Economy active</div>
    </div>
    <div class="card card-accent-red">
      <div class="icon">🛡️</div>
      <div class="value" id="vulnCount">—</div>
      <div class="label" id="vulnDetail">Unresolved Vulnerabilities</div>
      <div class="trend" id="vulnTrend">Awaiting scan</div>
    </div>
    <div class="card card-accent-green">
      <div class="icon">✅</div>
      <div class="value" id="verificationPassed">—</div>
      <div class="label" id="verificationDetail">Verification Runs</div>
      <div class="trend trend-up" id="verificationTrend">Z3 Solver ready</div>
    </div>
    <div class="card card-accent-yellow">
      <div class="icon">🎯</div>
      <div class="value" id="simPassed">—</div>
      <div class="label" id="simDetail">Simulation Results</div>
      <div class="trend" id="simTrend">Ready to simulate</div>
    </div>
    <div class="card card-accent-purple">
      <div class="icon">☁️</div>
      <div class="value" id="deployCount">0</div>
      <div class="label">Deployment Plans</div>
      <div class="trend" id="deployTrend">Cloud architect ready</div>
    </div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" onclick="switchTab('results',this)">📋 Results</div>
    <div class="tab" onclick="switchTab('agents',this)">👥 Agents</div>
    <div class="tab" onclick="switchTab('metrics',this)">📊 Analysis</div>
    <div class="tab" onclick="switchTab('topology',this)">🌐 Topology</div>
    <div class="tab" onclick="switchTab('pipeline',this)">⚙️ Pipeline</div>
    <div class="tab" onclick="switchTab('economy',this)">💰 Economy</div>
  </div>

  <!-- Results Tab -->
  <div id="resultsTab" class="panel">
    <div class="panel-header">
      <h3>📋 Latest Build Results</h3>
      <span class="badge badge-info" id="resultStatus">Waiting for input</span>
    </div>
    <div id="resultsContent" style="color:var(--muted);font-size:14px;">
      <div style="text-align:center;padding:40px 0;opacity:0.5">
        <div style="font-size:48px;margin-bottom:12px">🚀</div>
        <div>Submit a software goal above to see results here.</div>
        <div style="font-size:12px;margin-top:8px">The civilization will interpret, build, test, verify, and simulate your project.</div>
      </div>
    </div>
  </div>

  <!-- Agents Tab -->
  <div id="agentsTab" class="panel" style="display:none">
    <div class="panel-header">
      <h3>👥 Agent Registry</h3>
      <span class="badge badge-info" id="agentCountBadge">0 agents</span>
    </div>
    <div id="agentsContent" class="agent-list" style="color:var(--muted)">
      <div style="text-align:center;padding:20px;opacity:0.5">Loading agent data...</div>
    </div>
  </div>

  <!-- Analysis Tab -->
  <div id="metricsTab" class="panel" style="display:none">
    <div class="panel-header">
      <h3>📊 System Performance</h3>
      <span class="badge badge-info">Live metrics</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="chart-container"><canvas id="metricsChart"></canvas></div>
      </div>
      <div>
        <div class="chart-container"><canvas id="timelineChart"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Topology Tab -->
  <div id="topologyTab" class="panel" style="display:none">
    <div class="panel-header">
      <h3>🌐 System Topology</h3>
      <span class="badge badge-info">Agent network</span>
    </div>
    <div class="topology" id="topologyContainer">
      <svg viewBox="0 0 800 240">
        <defs>
          <radialGradient id="nodeGlow"><stop offset="0%" stop-color="rgba(79,195,247,0.3)"/><stop offset="100%" stop-color="rgba(79,195,247,0)"/></radialGradient>
          <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="rgba(79,195,247,0.1)"/><stop offset="50%" stop-color="rgba(79,195,247,0.4)"/><stop offset="100%" stop-color="rgba(0,230,118,0.1)"/>
          </linearGradient>
        </defs>
        <!-- Connection lines -->
        <line x1="120" y1="120" x2="280" y2="60" stroke="var(--border)" stroke-width="1" opacity="0.5"/>
        <line x1="120" y1="120" x2="280" y2="180" stroke="var(--border)" stroke-width="1" opacity="0.5"/>
        <line x1="120" y1="120" x2="400" y2="120" stroke="url(#lineGrad)" stroke-width="1.5"/>
        <line x1="400" y1="120" x2="550" y2="60" stroke="var(--border)" stroke-width="1" opacity="0.5"/>
        <line x1="400" y1="120" x2="550" y2="180" stroke="var(--border)" stroke-width="1" opacity="0.5"/>
        <line x1="550" y1="60" x2="700" y2="120" stroke="var(--border)" stroke-width="1" opacity="0.5"/>
        <line x1="550" y1="180" x2="700" y2="120" stroke="var(--border)" stroke-width="1" opacity="0.5"/>
        <!-- Nodes -->
        <circle cx="120" cy="120" r="28" fill="var(--surface2)" stroke="var(--primary)" stroke-width="2"/>
        <circle cx="120" cy="120" r="36" fill="url(#nodeGlow)"/>
        <text x="120" y="118" text-anchor="middle" fill="var(--text)" font-size="9" font-weight="600">GOAL</text>
        <text x="120" y="132" text-anchor="middle" fill="var(--muted)" font-size="8">Interpreter</text>
        <circle cx="280" cy="60" r="18" fill="var(--surface2)" stroke="var(--success)" stroke-width="2"/>
        <text x="280" y="64" text-anchor="middle" fill="var(--text)" font-size="8">DEV</text>
        <circle cx="280" cy="180" r="18" fill="var(--surface2)" stroke="var(--warn)" stroke-width="2"/>
        <text x="280" y="184" text-anchor="middle" fill="var(--text)" font-size="8">SEC</text>
        <circle cx="400" cy="120" r="22" fill="var(--surface2)" stroke="var(--purple)" stroke-width="2"/>
        <text x="400" y="118" text-anchor="middle" fill="var(--text)" font-size="9" font-weight="600">MARKET</text>
        <text x="400" y="132" text-anchor="middle" fill="var(--muted)" font-size="8">Economy</text>
        <circle cx="550" cy="60" r="18" fill="var(--surface2)" stroke="var(--success)" stroke-width="2"/>
        <text x="550" y="64" text-anchor="middle" fill="var(--text)" font-size="8">VERIFY</text>
        <circle cx="550" cy="180" r="18" fill="var(--surface2)" stroke="var(--primary)" stroke-width="2"/>
        <text x="550" y="184" text-anchor="middle" fill="var(--text)" font-size="8">TWIN</text>
        <circle cx="700" cy="120" r="24" fill="var(--surface2)" stroke="var(--success)" stroke-width="2.5"/>
        <circle cx="700" cy="120" r="32" fill="url(#nodeGlow)"/>
        <text x="700" y="118" text-anchor="middle" fill="var(--text)" font-size="9" font-weight="600">CLOUD</text>
        <text x="700" y="132" text-anchor="middle" fill="var(--muted)" font-size="8">Deploy</text>
      </svg>
    </div>
  </div>

  <!-- Pipeline Tab -->
  <div id="pipelineTab" class="panel" style="display:none">
    <div class="panel-header">
      <h3>⚙️ Development Pipeline</h3>
      <span class="badge badge-info" id="pipelineStatus">Idle</span>
    </div>
    <div class="pipeline" id="pipelineSteps">
      <div class="pipeline-step pending"><div class="step-icon">📋</div><div class="step-label">Requirements</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🏗️</div><div class="step-label">Architecture</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🗄️</div><div class="step-label">Database</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🔧</div><div class="step-label">Backend</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🎨</div><div class="step-label">Frontend</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🧪</div><div class="step-label">Tests</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🛡️</div><div class="step-label">Security</div></div>
      <div class="pipeline-step pending"><div class="step-icon">✅</div><div class="step-label">Verify</div></div>
      <div class="pipeline-step pending"><div class="step-icon">🎯</div><div class="step-label">Simulate</div></div>
      <div class="pipeline-step pending"><div class="step-icon">☁️</div><div class="step-label">Deploy</div></div>
    </div>
    <div id="pipelineDetail" style="font-size:12px;color:var(--muted);margin-top:12px">Submit a project to start the pipeline.</div>
  </div>

  <!-- Economy Tab -->
  <div id="economyTab" class="panel" style="display:none">
    <div class="panel-header">
      <h3>💰 Agent Economy</h3>
      <span class="badge badge-info" id="economyStatus">Market open</span>
    </div>
    <div id="economyContent" style="color:var(--muted)">
      <div style="text-align:center;padding:20px;opacity:0.5">Loading economy data...</div>
    </div>
  </div>
</div>

<!-- JSON Modal -->
<div class="modal-overlay" id="jsonModal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <h3 id="modalTitle">Raw JSON</h3>
    <pre id="modalContent"></pre>
  </div>
</div>

<script>
// Particle network background
const canvas = document.getElementById('particles-canvas');
const ctx = canvas.getContext('2d');
let particles = [];
function resizeCanvas(){canvas.width=window.innerWidth;canvas.height=window.innerHeight}
window.addEventListener('resize',resizeCanvas);
resizeCanvas();
class Particle{constructor(){this.reset();this.y=Math.random()*canvas.height}
reset(){this.x=Math.random()*canvas.width;this.y=this.y||Math.random()*canvas.height;this.size=Math.random()*2+0.5;this.speedX=(Math.random()-0.5)*0.3;this.speedY=(Math.random()-0.5)*0.3;this.opacity=Math.random()*0.5+0.1}
update(){this.x+=this.speedX;this.y+=this.speedY;if(this.x<0||this.x>canvas.width||this.y<0||this.y>canvas.height)this.reset()}
draw(){ctx.beginPath();ctx.arc(this.x,this.y,this.size,0,Math.PI*2);ctx.fillStyle=`rgba(79,195,247,${this.opacity})`;ctx.fill()}}
for(let i=0;i<80;i++)particles.push(new Particle());
let mouse={x:null,y:null};
document.addEventListener('mousemove',e=>{mouse.x=e.clientX;mouse.y=e.clientY});
function animateParticles(){ctx.clearRect(0,0,canvas.width,canvas.height);for(let p of particles){p.update();p.draw();for(let p2 of particles){const dx=p.x-p2.x,dy=p.y-p2.y,dist=Math.sqrt(dx*dx+dy*dy);if(dist<150){ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(p2.x,p2.y);ctx.strokeStyle=`rgba(79,195,247,${0.06*(1-dist/150)})`;ctx.strokeWidth=0.5;ctx.stroke()}}}
requestAnimationFrame(animateParticles)}
animateParticles();

// State
let metricsChart=null,timelineChart=null,ws=null,chartHistory=[];
const MAX_HISTORY=20;

// WebSocket
function connectWebSocket(){const p=window.location.protocol==='https:'?'wss:':'ws:';
ws=new WebSocket(p+'//'+window.location.host+'/ws');
ws.onopen=()=>{document.getElementById('statusText').textContent='Connected';document.getElementById('statusDot').style.background='var(--success)'};
ws.onclose=()=>{document.getElementById('statusText').textContent='Disconnected';document.getElementById('statusDot').style.background='var(--danger)';setTimeout(connectWebSocket,3000)};
ws.onmessage=e=>{try{const d=JSON.parse(e.data);if(d.type==='update')refreshDashboard()}catch(e){}}}

// Submit Goal
async function submitGoal(){const input=document.getElementById('goalInput').value.trim();if(!input)return;
const btn=document.getElementById('submitBtn');btn.disabled=true;btn.textContent='⚙️ Building...';
document.getElementById('resultsContent').innerHTML='<div style="text-align:center;padding:40px"><div style="font-size:32px;margin-bottom:12px">⚙️</div><div>Building your software...</div><div class="progress-bar" style="margin:16px auto;max-width:300px"><div class="progress-fill progress-blue" style="width:60%"></div></div></div>';
try{const r=await fetch('/api/goal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input})});const result=await r.json();displayResults(result);switchTab('results',document.querySelector('.tab'))}catch(err){document.getElementById('resultsContent').innerHTML='<div style="text-align:center;padding:40px;color:var(--danger)">Error: '+err.message+'</div>'}finally{btn.disabled=false;btn.textContent='Build It →'}
refreshDashboard()}

// Display Results
function displayResults(r){const p=r.project_spec||{},dev=r.development||{},sim=r.simulation||{},verify=r.verification||{},scan=r.adversarial_scan||{};
document.getElementById('resultStatus').textContent='Build completed';
let html='<div class="result-grid">';
html+=`<div class="result-card"><h4>📋 Project</h4><div class="rval">${p.title||'N/A'}</div><div class="rsub">Type: ${p.project_type||'N/A'} · Complexity: ${p.estimated_complexity||'?'}/10 · ${p.module_count||0} modules</div></div>`;
html+=`<div class="result-card"><h4>🛡️ Security</h4><div class="rval" style="color:${scan.vulnerabilities>0?'var(--danger)':'var(--success)'}">${scan.vulnerabilities||0}</div><div class="rsub">Vulnerabilities · ${scan.open||0} open</div></div>`;
html+=`<div class="result-card"><h4>✅ Verification</h4><div class="rval" style="color:${verify.status==='passed'?'var(--success)':'var(--danger)'}">${verify.status||'N/A'}</div><div class="rsub">${verify.passed_count||0} passed · ${verify.failed_count||0} failed</div></div>`;
html+=`<div class="result-card"><h4>🎯 Simulation</h4><div class="rval" style="color:${sim.passed?'var(--success)':'var(--danger)'}">${sim.passed?'PASSED':'FAILED'}</div><div class="rsub">${(sim.total_requests||0).toLocaleString()} req · ${((sim.error_rate||0)*100).toFixed(2)}% err · ${(sim.p99_latency||0).toFixed(0)}ms p99</div></div>`;
html+=`<div class="result-card"><h4>☁️ Deployment</h4><div class="rval">${result.deployment?.status||'N/A'}</div><div class="rsub">Est. $${result.deployment?.estimated_cost||0}/mo</div></div>`;
html+=`<div class="result-card"><h4>💡 Recommendation</h4><div class="rsub" style="margin-top:4px">${sim.recommendation||'System ready for production'}</div></div>`;
html+='</div><div style="margin-top:12px"><button class="btn-primary btn-sm" onclick="showJSON(\''+btoa(unescape(encodeURIComponent(JSON.stringify(r,null,2))))+'\',\'Build Result JSON\')">View Raw JSON</button></div>';
document.getElementById('resultsContent').innerHTML=html;
// Update pipeline steps
const steps=document.querySelectorAll('.pipeline-step');const labels=['Requirements','Architecture','Database','Backend','Frontend','Tests','Security','Verify','Simulate','Deploy'];
// Mark as done up through what was executed
const doneCount=6;steps.forEach((s,i)=>{s.className='pipeline-step '+(i<doneCount?'done':'pending')});
document.getElementById('pipelineDetail').innerHTML='Project built successfully. '+((dev.files_generated||[]).length||(dev.modules||[]).length||0)+' files generated.'}

// Tab Switching
function switchTab(tabId,el){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));el.classList.add('active');document.querySelectorAll('.panel').forEach(p=>p.style.display='none');document.getElementById(tabId+'Tab').style.display='block';
if(tabId==='agents')loadAgents();if(tabId==='economy')loadEconomy();if(tabId==='metrics')loadMetrics()}

// Modal
function showJSON(data,title){try{const decoded=decodeURIComponent(escape(atob(data)));document.getElementById('modalContent').textContent=decoded}catch(e){document.getElementById('modalContent').textContent=data}
document.getElementById('modalTitle').textContent=title||'Raw JSON';document.getElementById('jsonModal').classList.add('show')}
function closeModal(){document.getElementById('jsonModal').classList.remove('show')}

// Load Agents
async function loadAgents(){try{const r=await fetch('/api/agents');const d=await r.json();const agents=d.agents||[];
document.getElementById('agentCountBadge').textContent=agents.length+' agents';
let html='';agents.forEach(a=>{html+='<div class="agent-item"><div><div class="name">'+a.name+'</div><div class="spec">'+a.specialization+' · G'+(a.generation||1)+'</div></div><div class="stats"><span>💰<span class="stat-val">'+(a.credits||0)+'</span></span><span>⭐<span class="stat-val">'+(a.reputation||0).toFixed(0)+'</span></span><span>✅<span class="stat-val">'+(a.tasks_completed||0)+'</span></span></div><span class="badge '+(a.state==='working'?'badge-warn':a.state==='idle'?'badge-info':'badge-pass')+'">'+a.state+'</span></div>'});
document.getElementById('agentsContent').innerHTML=agents.length?html:'<div style="text-align:center;padding:30px;opacity:0.5">No agents spawned yet. Submit a project to create agents.</div>'}catch(e){document.getElementById('agentsContent').innerHTML='Error loading agents'}}

// Load Economy
async function loadEconomy(){try{const r=await fetch('/api/economy');const d=await r.json();const lb=d.leaderboard||[],summary=d.market_summary||{};
document.getElementById('economyStatus').textContent=(summary.total_agents||0)+' agents · '+(summary.total_transactions||0)+' txns';
let html='<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">';
html+=`<div class="result-card"><h4>Total Agents</h4><div class="rval">${summary.total_agents||0}</div></div>`;
html+=`<div class="result-card"><h4>Avg Reputation</h4><div class="rval">${summary.average_reputation||'N/A'}</div></div>`;
html+=`<div class="result-card"><h4>Success Rate</h4><div class="rval" style="color:var(--success)">${((summary.overall_success_rate||0)*100).toFixed(1)}%</div></div></div>`;
html+='<h4 style="color:var(--primary);font-size:13px;margin-bottom:8px">🏆 Leaderboard</h4><div class="agent-list">';
lb.forEach((a,i)=>{html+='<div class="agent-item"><div><div class="name">#'+(i+1)+' '+(a.name||a.agent_id?.slice(0,8))+'</div><div class="spec">'+(a.specialization||['general']).join(', ')+'</div></div><div class="stats"><span>💰<span class="stat-val">'+(a.credits||0)+'</span></span><span>⭐<span class="stat-val">'+(a.reputation||0).toFixed(0)+'</span></span><span>✅<span class="stat-val">'+(a.tasks_completed||0)+'</span></span></div><span class="badge badge-info">'+(a.combined_score||0).toFixed(1)+'</span></div>'});
html+='</div>';document.getElementById('economyContent').innerHTML=html}catch(e){document.getElementById('economyContent').innerHTML='Error loading economy'}}

// Load Metrics Charts
async function loadMetrics(){try{const r=await fetch('/api/status');const d=await r.json();const summary=d.hub?.telemetry?.summary||{};
// Radar chart
if(metricsChart)metricsChart.destroy();
const ctx1=document.getElementById('metricsChart').getContext('2d');
metricsChart=new Chart(ctx1,{type:'radar',data:{labels:['CPU','Memory','Latency','RPS','Stability'],datasets:[{label:'System Health',data:[summary.avg_cpu||0,summary.avg_memory||0,Math.min(100,(summary.avg_latency||0)/10),Math.min(100,(summary.total_rps||0)/100),100-Math.min(100,(summary.avg_error_rate||0)*100)],backgroundColor:'rgba(79,195,247,0.15)',borderColor:'#4fc3f7',borderWidth:2,pointBackgroundColor:'#4fc3f7',pointRadius:4}]},options:{responsive:true,maintainAspectRatio:false,scales:{r:{beginAtZero:true,max:100,grid:{color:'rgba(26,42,74,0.3)'},angleLines:{color:'rgba(26,42,74,0.3)'},pointLabels:{color:'#5a6a8a',font:{size:11}},ticks:{color:'#5a6a8a',backdropColor:'transparent',stepSize:20}}},plugins:{legend:{labels:{color:'#5a6a8a',font:{size:12}}}}}});
// Timeline bar chart (component metrics)
chartHistory.push(summary);if(chartHistory.length>MAX_HISTORY)chartHistory.shift();
if(timelineChart)timelineChart.destroy();
const ctx2=document.getElementById('timelineChart').getContext('2d');
timelineChart=new Chart(ctx2,{type:'bar',data:{labels:['CPU','Memory','Latency','RPS','Error Rate'],datasets:[{label:'Current Metrics',data:[summary.avg_cpu||0,summary.avg_memory||0,summary.avg_latency||0,summary.total_rps||0,(summary.avg_error_rate||0)*100||0],backgroundColor:['rgba(79,195,247,0.6)','rgba(0,230,118,0.6)','rgba(255,196,0,0.6)','rgba(206,147,216,0.6)','rgba(255,23,68,0.6)'],borderColor:['#4fc3f7','#00e676','#ffc400','#ce93d8','#ff1744'],borderWidth:1,borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'rgba(26,42,74,0.2)'},ticks:{color:'#5a6a8a'}},y:{beginAtZero:true,grid:{color:'rgba(26,42,74,0.2)'},ticks:{color:'#5a6a8a'}}}}})}catch(e){}}

// Refresh Dashboard
async function refreshDashboard(){try{const r=await fetch('/api/status');const d=await r.json();
const agents=d.agents||{},economy=d.economy||{},security=d.security||{},verification=d.verification||{},simulation=d.simulation||{},deployment=d.deployment||{};
document.getElementById('agentCount').textContent=agents.active_agents||0;
document.getElementById('totalCredits').textContent=(economy.total_credits_in_circulation||0).toFixed(0);
document.getElementById('vulnCount').textContent=security.open_vulnerabilities||(security.total_vulnerabilities||'—');
document.getElementById('vulnDetail').innerHTML=(security.total_scans||0)+' scans · <span class="badge '+(security.critical_count>0?'badge-fail':'badge-pass')+'">'+(security.critical_count||0)+' critical</span>';
document.getElementById('vulnTrend').textContent='🔧 '+(security.verified_fixes||0)+' fixes verified';
document.getElementById('verificationPassed').textContent=verification.passed||0;
document.getElementById('verificationDetail').innerHTML=(verification.total_runs||0)+' runs · '+((verification.total_properties_verified||0))+' props';
document.getElementById('verificationTrend').textContent=verification.z3_available?'Z3 Solver: Active':'Z3: Fallback';
document.getElementById('simPassed').textContent=simulation.passed||0;
document.getElementById('simDetail').innerHTML=(simulation.simulations_run||0)+' runs';
const dockerAvail=simulation.docker_available;
document.getElementById('simTrend').textContent=dockerAvail?'Docker: Ready':'Docker: Simulated';
document.getElementById('deployCount').textContent=deployment.total_deployments||0;
document.getElementById('deployTrend').textContent='$'+(deployment.total_monthly_cost||0).toFixed(0)+'/mo total';
}catch(e){}}

// Initialize
connectWebSocket();refreshDashboard();setInterval(refreshDashboard,5000);
</script>
</body>
</html>"""



