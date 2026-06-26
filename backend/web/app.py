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
    """Return the HTML for the Command Center dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Civilization — Command Center</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #0a0e17;
            color: #e0e6f0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #0f1729 0%, #1a2332 100%);
            border-bottom: 1px solid #1e3a5f;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 {
            font-size: 20px;
            font-weight: 600;
            background: linear-gradient(90deg, #4fc3f7, #00e676);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header-status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #8892b0;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00e676;
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        .container {
            padding: 24px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .card {
            background: linear-gradient(135deg, #111b2e 0%, #162033 100%);
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 20px;
            transition: border-color 0.3s, transform 0.2s;
        }
        .card:hover {
            border-color: #4fc3f7;
            transform: translateY(-2px);
        }
        .card h3 {
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #4fc3f7;
            margin-bottom: 12px;
        }
        .card .value {
            font-size: 32px;
            font-weight: 700;
            color: #e0e6f0;
            margin-bottom: 4px;
        }
        .card .sub {
            font-size: 13px;
            color: #667;
        }
        .card .label {
            font-size: 12px;
            color: #667;
            margin-top: 4px;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-pass { background: #00e67633; color: #00e676; }
        .badge-fail { background: #ff174433; color: #ff1744; }
        .badge-warn { background: #ffc40033; color: #ffc400; }

        .input-section {
            background: linear-gradient(135deg, #111b2e 0%, #162033 100%);
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }
        .input-section textarea {
            width: 100%;
            padding: 14px;
            background: #0a0e17;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
            color: #e0e6f0;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
            min-height: 80px;
        }
        .input-section textarea:focus {
            outline: none;
            border-color: #4fc3f7;
        }
        .input-section button {
            margin-top: 12px;
            padding: 12px 28px;
            background: linear-gradient(135deg, #4fc3f7, #00bcd4);
            border: none;
            border-radius: 8px;
            color: #0a0e17;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: opacity 0.3s, transform 0.2s;
        }
        .input-section button:hover { opacity: 0.9; transform: translateY(-1px); }
        .input-section button:disabled { opacity: 0.4; cursor: not-allowed; }

        .results-panel {
            background: linear-gradient(135deg, #111b2e 0%, #162033 100%);
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 24px;
            margin-top: 16px;
        }
        .results-panel pre {
            background: #0a0e17;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 12px;
            line-height: 1.6;
            color: #667;
        }
        .chart-container {
            height: 200px;
            margin-top: 12px;
        }

        .agent-list {
            margin-top: 12px;
        }
        .agent-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #1e3a5f33;
            font-size: 13px;
        }
        .agent-item:last-child { border-bottom: none; }
        .agent-name { color: #e0e6f0; }
        .agent-stat { color: #667; font-size: 12px; }

        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 16px;
        }
        .tab {
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            color: #667;
            border: 1px solid transparent;
            transition: all 0.3s;
        }
        .tab:hover { color: #e0e6f0; border-color: #1e3a5f; }
        .tab.active {
            color: #4fc3f7;
            border-color: #4fc3f7;
            background: #4fc3f710;
        }

        @media (max-width: 768px) {
            .container { padding: 12px; }
            .grid { grid-template-columns: 1fr; }
            .card .value { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ AI Civilization — Command Center</h1>
        <div class="header-status">
            <span class="status-dot"></span>
            <span id="statusText">Connected</span>
        </div>
    </div>

    <div class="container">
        <!-- Input Section -->
        <div class="input-section">
            <h3 style="color: #4fc3f7; margin-bottom: 12px;">🚀 Submit Software Goal</h3>
            <textarea id="goalInput" placeholder='e.g., "Build a Hospital Management System" or "Create an E-Commerce Platform with payment integration"...'></textarea>
            <button id="submitBtn" onclick="submitGoal()">Build It →</button>
        </div>

        <!-- Dashboard Grid -->
        <div class="grid">
            <div class="card">
                <h3>🤖 Agents</h3>
                <div class="value" id="agentCount">0</div>
                <div class="label">Active agents in civilization</div>
            </div>
            <div class="card">
                <h3>💰 Economy</h3>
                <div class="value" id="totalCredits">0</div>
                <div class="label">Credits in circulation</div>
            </div>
            <div class="card">
                <h3>🛡️ Security</h3>
                <div class="value" id="vulnCount">—</div>
                <div class="label" id="vulnDetail">Scan to start</div>
            </div>
            <div class="card">
                <h3>✅ Verification</h3>
                <div class="value" id="verificationPassed">—</div>
                <div class="label" id="verificationDetail">Run verification</div>
            </div>
            <div class="card">
                <h3>🎯 Simulation</h3>
                <div class="value" id="simPassed">—</div>
                <div class="label" id="simDetail">Run simulation</div>
            </div>
            <div class="card">
                <h3>☁️ Deployments</h3>
                <div class="value" id="deployCount">0</div>
                <div class="label">Plans generated</div>
            </div>
        </div>

        <!-- Results & Visualization -->
        <div class="tabs">
            <div class="tab active" onclick="switchTab('results', this)">📋 Results</div>
            <div class="tab" onclick="switchTab('agents', this)">👥 Agents</div>
            <div class="tab" onclick="switchTab('metrics', this)">📊 Metrics</div>
            <div class="tab" onclick="switchTab('economy', this)">💰 Economy</div>
        </div>

        <div id="resultsTab" class="results-panel">
            <h3 style="color: #4fc3f7; margin-bottom: 8px;">Latest Build Result</h3>
            <div id="resultsContent" style="color: #667;">Submit a goal to see results here.</div>
        </div>

        <div id="agentsTab" class="results-panel" style="display: none;">
            <h3 style="color: #4fc3f7; margin-bottom: 8px;">Agent Registry</h3>
            <div id="agentsContent" class="agent-list">Loading...</div>
        </div>

        <div id="metricsTab" class="results-panel" style="display: none;">
            <h3 style="color: #4fc3f7; margin-bottom: 8px;">System Metrics</h3>
            <div class="chart-container">
                <canvas id="metricsChart"></canvas>
            </div>
        </div>

        <div id="economyTab" class="results-panel" style="display: none;">
            <h3 style="color: #4fc3f7; margin-bottom: 8px;">Agent Economy</h3>
            <div id="economyContent" class="agent-list">Loading...</div>
        </div>
    </div>

    <script>
        let metricsChart = null;
        let ws = null;

        // Connect WebSocket
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            ws.onopen = () => {
                document.getElementById('statusText').textContent = 'Connected';
            };
            ws.onclose = () => {
                document.getElementById('statusText').textContent = 'Disconnected';
                setTimeout(connectWebSocket, 3000);
            };
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'update') {
                        refreshDashboard();
                    }
                } catch(e) {}
            };
        }

        // Submit Goal
        async function submitGoal() {
            const input = document.getElementById('goalInput').value.trim();
            if (!input) return;

            const btn = document.getElementById('submitBtn');
            btn.disabled = true;
            btn.textContent = '⚙️ Building...';
            document.getElementById('resultsContent').innerHTML = 'Building your software...';

            try {
                const response = await fetch('/api/goal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ input }),
                });
                const result = await response.json();
                displayResults(result);
            } catch (err) {
                document.getElementById('resultsContent').innerHTML = 'Error: ' + err.message;
            } finally {
                btn.disabled = false;
                btn.textContent = 'Build It →';
            }

            refreshDashboard();
        }

        // Display Results
        function displayResults(result) {
            const project = result.project_spec || {};
            const dev = result.development || {};
            const sim = result.simulation || {};
            const verify = result.verification || {};
            const scan = result.adversarial_scan || {};

            let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">';

            // Project Info
            html += '<div><strong style="color: #4fc3f7;">Project</strong><br>';
            html += 'Title: ' + (project.title || 'N/A') + '<br>';
            html += 'Type: ' + (project.project_type || 'N/A') + '<br>';
            html += 'Modules: ' + (project.module_count || 0) + '<br>';
            html += 'Complexity: ' + (project.estimated_complexity || '?') + '/10</div>';

            // Security
            html += '<div><strong style="color: #ff1744;">Security</strong><br>';
            html += 'Vulnerabilities: ' + (scan.vulnerabilities || 0) + '<br>';
            html += 'Open: ' + (scan.open || 0) + '</div>';

            // Verification
            html += '<div><strong style="color: #00e676;">Verification</strong><br>';
            html += 'Status: <span class="status-badge ' + (verify.status === 'passed' ? 'badge-pass' : 'badge-fail') + '">' + (verify.status || 'N/A') + '</span><br>';
            html += 'Passed: ' + (verify.passed_count || 0) + ' / Failed: ' + (verify.failed_count || 0) + '</div>';

            // Simulation
            html += '<div><strong style="color: #ffc400;">Simulation</strong><br>';
            html += 'Result: <span class="status-badge ' + (sim.passed ? 'badge-pass' : 'badge-fail') + '">' + (sim.passed ? 'PASSED' : 'FAILED') + '</span><br>';
            html += 'Requests: ' + (sim.total_requests || 0).toLocaleString() + '<br>';
            html += 'Error Rate: ' + ((sim.error_rate || 0) * 100).toFixed(2) + '%<br>';
            html += 'p99 Latency: ' + (sim.p99_latency || 0).toFixed(0) + 'ms<br>';
            html += 'Chaos Survival: ' + ((sim.chaos_survival_rate || 0) * 100).toFixed(0) + '%</div>';

            // Deployment
            html += '<div><strong style="color: #ce93d8;">Deployment</strong><br>';
            html += 'Status: ' + (result.deployment?.status || 'N/A') + '<br>';
            html += 'Est. Cost: $' + (result.deployment?.estimated_cost || 0) + '/mo</div>';

            // Recommendation
            html += '<div><strong style="color: #4dd0e1;">Recommendation</strong><br>';
            html += (sim.recommendation || 'System ready for production') + '</div>';

            html += '</div>';

            // Full JSON
            html += '<details style="margin-top: 16px;"><summary style="cursor: pointer; color: #667;">View Raw JSON</summary>';
            html += '<pre>' + JSON.stringify(result, null, 2) + '</pre></details>';

            document.getElementById('resultsContent').innerHTML = html;
        }

        // Tab Switching
        function switchTab(tabId, element) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            element.classList.add('active');
            document.querySelectorAll('.results-panel').forEach(p => p.style.display = 'none');
            document.getElementById(tabId + 'Tab').style.display = 'block';

            if (tabId === 'agents') loadAgents();
            if (tabId === 'economy') loadEconomy();
            if (tabId === 'metrics') loadMetrics();
        }

        // Load Agents
        async function loadAgents() {
            try {
                const resp = await fetch('/api/agents');
                const data = await resp.json();
                const agents = data.agents || [];
                let html = '';
                agents.forEach(a => {
                    html += '<div class="agent-item">';
                    html += '<div><span class="agent-name">' + a.name + '</span><br><span class="agent-stat">' + (a.specialization || 'general') + '</span></div>';
                    html += '<div><span class="agent-stat">💰 ' + (a.credits || 0) + ' ⭐ ' + (a.reputation || 0).toFixed(0) + '</span></div>';
                    html += '</div>';
                });
                document.getElementById('agentsContent').innerHTML = agents.length ? html : 'No agents yet.';
            } catch(e) {
                document.getElementById('agentsContent').innerHTML = 'Error loading agents';
            }
        }

        // Load Economy
        async function loadEconomy() {
            try {
                const resp = await fetch('/api/economy');
                const data = await resp.json();
                const lb = data.leaderboard || [];
                const summary = data.market_summary || {};

                let html = '<div style="margin-bottom: 16px;">';
                html += '<strong style="color: #4fc3f7;">Market Summary</strong><br>';
                html += 'Total Agents: ' + (summary.total_agents || 0) + ' | ';
                html += 'Avg Reputation: ' + (summary.average_reputation || '—') + ' | ';
                html += 'Success Rate: ' + ((summary.overall_success_rate || 0) * 100).toFixed(1) + '%';
                html += '</div>';

                html += '<strong style="color: #4fc3f7;">Leaderboard</strong>';
                lb.forEach((a, i) => {
                    html += '<div class="agent-item">';
                    html += '<div>#' + (i+1) + ' <span class="agent-name">' + (a.name || a.agent_id?.slice(0,8)) + '</span></div>';
                    html += '<div><span class="agent-stat">💰 ' + (a.credits || 0) + ' ⭐ ' + (a.reputation || 0).toFixed(0) + ' ✅ ' + (a.tasks_completed || 0) + '</span></div>';
                    html += '</div>';
                });
                document.getElementById('economyContent').innerHTML = html;
            } catch(e) {
                document.getElementById('economyContent').innerHTML = 'Error loading economy';
            }
        }

        // Load Metrics Chart
        async function loadMetrics() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                const summary = data.hub?.telemetry?.summary || {};

                if (metricsChart) metricsChart.destroy();

                const ctx = document.getElementById('metricsChart').getContext('2d');
                metricsChart = new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: ['CPU', 'Memory', 'Latency', 'RPS', 'Error Rate'],
                        datasets: [{
                            label: 'System Metrics',
                            data: [
                                summary.avg_cpu || 0,
                                summary.avg_memory || 0,
                                Math.min(100, (summary.avg_latency || 0) / 10),
                                Math.min(100, (summary.total_rps || 0) / 100),
                                Math.min(100, ((summary.avg_error_rate || 0) * 100)),
                            ],
                            backgroundColor: 'rgba(79, 195, 247, 0.2)',
                            borderColor: '#4fc3f7',
                            borderWidth: 2,
                            pointBackgroundColor: '#4fc3f7',
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            r: {
                                beginAtZero: true,
                                max: 100,
                                grid: { color: '#1e3a5f44' },
                                angleLines: { color: '#1e3a5f44' },
                                pointLabels: { color: '#667' },
                                ticks: { color: '#667', backdropColor: 'transparent' }
                            }
                        },
                        plugins: {
                            legend: { labels: { color: '#667' } }
                        }
                    }
                });
            } catch(e) {}
        }

        // Refresh Dashboard
        async function refreshDashboard() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();

                const agents = data.agents || {};
                const economy = data.economy || {};
                const security = data.security || {};
                const verification = data.verification || {};
                const simulation = data.simulation || {};
                const deployment = data.deployment || {};

                document.getElementById('agentCount').textContent = agents.active_agents || 0;
                document.getElementById('totalCredits').textContent = (economy.total_credits_in_circulation || 0).toFixed(0);
                document.getElementById('vulnCount').textContent = security.open_vulnerabilities || (security.total_vulnerabilities || 0);
                document.getElementById('vulnDetail').textContent = (security.total_scans || 0) + ' scans performed';
                document.getElementById('verificationPassed').textContent = verification.passed || 0;
                document.getElementById('verificationDetail').textContent = (verification.total_runs || 0) + ' runs total';
                document.getElementById('simPassed').textContent = simulation.passed || 0;
                document.getElementById('simDetail').textContent = (simulation.simulations_run || 0) + ' simulations';
                document.getElementById('deployCount').textContent = deployment.total_deployments || 0;
            } catch(e) {}
        }

        // Initialize
        connectWebSocket();
        refreshDashboard();
        setInterval(refreshDashboard, 5000);
    </script>
</body>
</html>"""



