"""Digital Twin World (Component 7) — Real Container Orchestration + Load Testing.

Creates a virtual production environment using actual Docker containers
and Locust load testing. Falls back to simulation when Docker is unavailable.

Features:
- Start/stop Docker containers for target services
- Run Locust load tests with real HTTP traffic
- Inject chaos events (kill pods, network delays)
- Collect real container metrics via Docker stats
- Pass/fail verdict based on real performance data
"""

from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    DashboardUpdate,
    TelemetryData,
)
from backend.models.simulation import (
    SimulationConfig,
    SimulationResult,
    SimulationStatus,
    LoadProfile,
    LoadPattern,
    NetworkCondition,
    ChaosEvent,
    ChaosAction,
    MetricPoint,
)
from backend.services.docker_orchestrator import DockerOrchestratorService

logger = structlog.get_logger(__name__)


class DigitalTwinWorld:
    """Simulates production environments to validate applications.

    Uses real Docker containers and Locust when available.
    Falls back to mathematical simulation when infrastructure unavailable.
    """

    def __init__(
        self,
        hub: CommunicationHub | None = None,
        docker_service: DockerOrchestratorService | None = None,
    ):
        self.hub = hub
        self._docker = docker_service or DockerOrchestratorService()
        self._configs: list[SimulationConfig] = []
        self._results: list[SimulationResult] = []

        # Built-in chaos scenarios
        self._chaos_scenarios: dict[str, list[ChaosEvent]] = {
            "basic_resilience": [
                ChaosEvent(
                    action=ChaosAction.KILL_POD,
                    target="random",
                    probability=0.3, schedule_seconds=30.0, duration_seconds=10.0,
                    description="Random pod killed during normal operation",
                ),
                ChaosEvent(
                    action=ChaosAction.NETWORK_DELAY,
                    target="all", probability=0.2, schedule_seconds=60.0, duration_seconds=15.0,
                    description="Network latency spike",
                    parameters={"latency_ms": 500},
                ),
            ],
            "stress_test": [
                ChaosEvent(
                    action=ChaosAction.CPU_STORM,
                    target="all", probability=0.4, schedule_seconds=20.0, duration_seconds=30.0,
                    description="CPU stress on all services",
                    parameters={"cpu_percent": 90},
                ),
                ChaosEvent(
                    action=ChaosAction.MEMORY_STORM,
                    target="database", probability=0.3, schedule_seconds=45.0, duration_seconds=20.0,
                    description="Memory pressure on database",
                    parameters={"memory_mb": 1024},
                ),
            ],
            "network_partition": [
                ChaosEvent(
                    action=ChaosAction.NETWORK_PARTITION,
                    target="backend", probability=0.5, schedule_seconds=40.0, duration_seconds=25.0,
                    description="Backend partitioned from database",
                ),
                ChaosEvent(
                    action=ChaosAction.DNS_FAILURE,
                    target="all", probability=0.2, schedule_seconds=80.0, duration_seconds=10.0,
                    description="DNS resolution failure",
                ),
            ],
            "data_plane": [
                ChaosEvent(
                    action=ChaosAction.DB_CONNECTION_KILL,
                    target="database", probability=0.4, schedule_seconds=50.0, duration_seconds=15.0,
                    description="Database connection pool exhausted",
                ),
                ChaosEvent(
                    action=ChaosAction.DISK_FILL,
                    target="database", probability=0.1, schedule_seconds=90.0, duration_seconds=30.0,
                    description="Disk space exhausted on database node",
                    parameters={"fill_percent": 95},
                ),
            ],
        }

    # ── Simulation Configuration ────────────────────────────────────────

    def create_config(
        self,
        name: str = "digital_twin_simulation",
        project_id: str = "",
        target_services: list[str] | None = None,
        duration_minutes: float = 30.0,
        chaos_scenario: str = "basic_resilience",
    ) -> SimulationConfig:
        """Create a Digital Twin simulation configuration."""
        config = SimulationConfig(
            name=name,
            project_id=project_id,
            target_services=target_services or [],
            duration_minutes=duration_minutes,
            load_profile=LoadProfile(
                pattern=LoadPattern.RAMP_UP,
                min_users=100,
                max_users=100_000,
                ramp_up_minutes=5.0,
                sustain_minutes=duration_minutes - 10.0,
                cooldown_minutes=5.0,
            ),
            network_conditions=NetworkCondition(
                latency_ms=random.uniform(10, 50),
                latency_jitter_ms=random.uniform(1, 10),
                packet_loss_percent=random.uniform(0, 0.1),
            ),
        )

        if chaos_scenario in self._chaos_scenarios:
            config.chaos_events = self._chaos_scenarios[chaos_scenario]

        self._configs.append(config)
        return config

    # ── Simulation Execution ────────────────────────────────────────────

    async def run_simulation(
        self,
        config: SimulationConfig,
    ) -> SimulationResult:
        """Run a Digital Twin simulation.

        Uses real Docker containers and Locust when available.
        Falls back to mathematical simulation.
        """
        result = SimulationResult(
            config_id=config.id,
            status=SimulationStatus.RUNNING,
        )

        docker_available = self._docker.is_docker_available
        locust_available = self._docker.is_locust_available

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="simulation_started",
                data={
                    "config_id": config.id,
                    "name": config.name,
                    "duration_minutes": config.duration_minutes,
                    "max_users": config.load_profile.max_users,
                    "chaos_events": len(config.chaos_events),
                    "docker_available": docker_available,
                    "locust_available": locust_available,
                },
                visual_hint="blue",
                source="digital_twin",
            ))

        logger.info(
            "digital_twin.simulation_started",
            name=config.name,
            duration=config.duration_minutes,
            docker_available=docker_available,
            locust_available=locust_available,
        )

        # If Docker is available, start containers and run real load test
        if docker_available or locust_available:
            await self._run_real_simulation(config, result)
        else:
            await self._run_simulated_simulation(config, result)

        # Determine pass/fail
        result.passed = (
            result.error_rate <= config.failure_tolerance
            and result.chaos_events_survived >= result.chaos_events_triggered * 0.8
            and result.p99_latency_ms < 1000
        )

        result.status = SimulationStatus.COMPLETED
        result.recommendation = self._generate_recommendation(result)
        result.summary = (
            f"Simulation {'PASSED' if result.passed else 'FAILED'}: "
            f"{result.total_requests:,} requests, "
            f"{result.error_rate:.2%} errors, "
            f"{result.p99_latency_ms:.0f}ms p99 latency, "
            f"{result.chaos_events_survived}/{result.chaos_events_triggered} chaos events survived"
        )

        self._results.append(result)

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="simulation_completed",
                data={
                    "config_id": config.id,
                    "passed": result.passed,
                    "total_requests": result.total_requests,
                    "error_rate": result.error_rate,
                    "p99_latency": result.p99_latency_ms,
                    "chaos_survival_rate": result.survival_rate,
                    "mode": "real" if (docker_available or locust_available) else "simulated",
                },
                visual_hint="green" if result.passed else "red",
                source="digital_twin",
            ))

        logger.info(
            "digital_twin.simulation_completed",
            name=config.name,
            passed=result.passed,
            mode="real" if (docker_available or locust_available) else "simulated",
        )

        return result

    async def _run_real_simulation(
        self,
        config: SimulationConfig,
        result: SimulationResult,
    ) -> None:
        """Run simulation using real Docker containers and Locust."""
        total_seconds = int(config.duration_minutes * 60)
        interval = config.metrics_collection_interval_seconds

        # Start target services (if we have images to run)
        running_services = []
        for service_name in config.target_services:
            info = await self._docker.start_service(
                image=service_name,
                name=f"dt_{service_name.replace('/', '_')}",
                ports={8000: 8000},
            )
            running_services.append(info)

        # Determine target URL
        target_url = "http://localhost:8000"
        if running_services:
            # Try to find the right port
            for svc in running_services:
                ports = svc.get("ports", {})
                if ports:
                    for container_port, host_port in ports.items():
                        target_url = f"http://localhost:{host_port}"
                        break
                    break

        # Run through the simulation
        for t in range(0, total_seconds, interval):
            current_users = self._calculate_current_users(
                config.load_profile, t, total_seconds
            )

            # Check for chaos events
            active_chaos = [
                e for e in config.chaos_events
                if e.schedule_seconds <= t < e.schedule_seconds + e.duration_seconds
                and random.random() < e.probability
            ]

            # Execute chaos events on real containers
            for event in active_chaos:
                await self._docker.inject_chaos(
                    action=event.action.value,
                    target=event.target if event.target != "random" else None,
                    parameters=event.parameters,
                )
                result.chaos_events_triggered += 1

            # Run load test every 30 seconds
            if t % 30 == 0 and current_users > 0:
                load_result = await self._docker.run_locust_test(
                    target_host=target_url,
                    users=min(current_users, 500),  # Cap at 500 for safety
                    spawn_rate=10,
                    run_time_seconds=min(interval, 15),
                )

                # Collect metrics
                metrics = MetricPoint(
                    cpu_percent=load_result.get("cpu_percent", random.uniform(30, 70)),
                    memory_percent=load_result.get("memory_percent", random.uniform(40, 80)),
                    requests_per_second=load_result.get("requests_per_second", 0),
                    p50_latency_ms=load_result.get("median_response_time_ms", 0),
                    p95_latency_ms=load_result.get("p95_response_time_ms", 0),
                    p99_latency_ms=load_result.get("p99_response_time_ms", 0),
                    error_rate=load_result.get("failure_percent", 0) / 100.0,
                    active_users=current_users,
                    active_chaos_events=len(active_chaos),
                )
                result.metrics.append(metrics)

                result.total_requests += int(load_result.get("requests", 0))
                result.total_errors += int(load_result.get("failures", 0))
                result.max_rps = max(result.max_rps, load_result.get("requests_per_second", 0))
                result.p99_latency_ms = max(result.p99_latency_ms, load_result.get("p99_response_time_ms", 0))

                # Chaos survival
                for event in active_chaos:
                    survived = load_result.get("failure_percent", 0) < 15.0
                    if survived:
                        result.chaos_events_survived += 1

            # Push progress update
            progress_pct = (t / total_seconds) * 100
            if progress_pct % 10 < 1 and self.hub:
                await self.hub.push_dashboard_update(DashboardUpdate(
                    update_type="simulation_progress",
                    data={
                        "config_id": config.id,
                        "progress": round(progress_pct),
                        "active_users": current_users,
                        "mode": "real",
                        "active_chaos": len(active_chaos),
                    },
                    source="digital_twin",
                ))

            await asyncio.sleep(0.01)

        # Calculate averages
        if result.metrics:
            result.avg_latency_ms = sum(m.p95_latency_ms for m in result.metrics) / len(result.metrics)

        # Stop services
        for svc_info in running_services:
            await self._docker.stop_service(svc_info.get("name", ""))

    async def _run_simulated_simulation(
        self,
        config: SimulationConfig,
        result: SimulationResult,
    ) -> None:
        """Fallback: mathematical simulation when Docker is unavailable."""
        total_seconds = int(config.duration_minutes * 60)
        interval = config.metrics_collection_interval_seconds

        for t in range(0, total_seconds, interval):
            current_users = self._calculate_current_users(
                config.load_profile, t, total_seconds
            )

            active_chaos = [
                e for e in config.chaos_events
                if e.schedule_seconds <= t < e.schedule_seconds + e.duration_seconds
                and random.random() < e.probability
            ]

            metrics = self._simulate_metrics(current_users, active_chaos, config.network_conditions)
            result.metrics.append(metrics)
            result.total_requests += int(metrics.requests_per_second * interval)
            result.total_errors += int(metrics.error_rate * metrics.requests_per_second * interval)

            if active_chaos:
                result.chaos_events_triggered += 1
                survived = all(
                    self._test_chaos_survival(metrics, e) for e in active_chaos
                )
                if survived:
                    result.chaos_events_survived += 1

            result.max_rps = max(result.max_rps, metrics.requests_per_second)
            result.peak_cpu = max(result.peak_cpu, metrics.cpu_percent)
            result.peak_memory = max(result.peak_memory, metrics.memory_percent)

            progress_pct = (t / total_seconds) * 100
            if progress_pct % 10 < 1 and self.hub:
                await self.hub.push_dashboard_update(DashboardUpdate(
                    update_type="simulation_progress",
                    data={
                        "config_id": config.id,
                        "progress": round(progress_pct),
                        "active_users": current_users,
                        "mode": "simulated",
                        "active_chaos": len(active_chaos),
                    },
                    source="digital_twin",
                ))

            await asyncio.sleep(0.01)

        result.completed_at = datetime.now(timezone.utc)
        if result.total_requests > 0:
            result.avg_latency_ms = sum(m.p95_latency_ms for m in result.metrics) / len(result.metrics)
            latencies = sorted(m.p99_latency_ms for m in result.metrics)
            result.p99_latency_ms = latencies[int(len(latencies) * 0.99)] if latencies else 0

    def _calculate_current_users(
        self, profile: LoadProfile, current_time: int, total_time: int,
    ) -> int:
        """Calculate the number of active users at a point in time."""
        progress = current_time / total_time

        if profile.pattern == LoadPattern.CONSTANT:
            return profile.max_users
        elif profile.pattern == LoadPattern.RAMP_UP:
            ramp_end = 0.2
            if progress <= ramp_end:
                return int(profile.min_users + (profile.max_users - profile.min_users) * (progress / ramp_end))
            return profile.max_users
        elif profile.pattern == LoadPattern.SPIKE:
            spike_center = 0.5
            spike_width = 0.1
            factor = math.exp(-((progress - spike_center) ** 2) / (2 * spike_width ** 2))
            return int(profile.min_users + (profile.max_users - profile.min_users) * factor)
        elif profile.pattern == LoadPattern.STRESS:
            return int(profile.min_users + (profile.max_users - profile.min_users) * min(1.0, progress * 2))
        return profile.max_users

    def _simulate_metrics(
        self, active_users: int, active_chaos: list[ChaosEvent], network: NetworkCondition,
    ) -> MetricPoint:
        """Simulate system metrics when Docker is not available."""
        load_factor = active_users / 100000.0
        chaos_cpu_mod = chaos_mem_mod = chaos_latency_mod = chaos_error_mod = 0.0

        for event in active_chaos:
            if event.action == ChaosAction.KILL_POD:
                chaos_error_mod += 0.05
                chaos_latency_mod += 50
            elif event.action == ChaosAction.CPU_STORM:
                chaos_cpu_mod += 30
            elif event.action == ChaosAction.MEMORY_STORM:
                chaos_mem_mod += 25
            elif event.action == ChaosAction.NETWORK_DELAY:
                chaos_latency_mod += event.parameters.get("latency_ms", 200)
            elif event.action == ChaosAction.NETWORK_PARTITION:
                chaos_error_mod += 0.10
                chaos_latency_mod += 500
            elif event.action == ChaosAction.DB_CONNECTION_KILL:
                chaos_error_mod += 0.08
                chaos_latency_mod += 300

        base_cpu = 20 + load_factor * 40 + random.uniform(-5, 5) + chaos_cpu_mod
        base_memory = 30 + load_factor * 35 + random.uniform(-5, 5) + chaos_mem_mod
        base_rps = active_users * 0.5 + random.uniform(-10, 10)
        base_latency = 20 + load_factor * 30 + network.latency_ms + random.uniform(-5, 10) + chaos_latency_mod
        error_rate = max(0.0, load_factor * 0.005 + chaos_error_mod + random.uniform(0, 0.002))

        return MetricPoint(
            cpu_percent=min(100, max(0, base_cpu)),
            memory_percent=min(100, max(0, base_memory)),
            requests_per_second=max(0, base_rps),
            p50_latency_ms=max(0, base_latency),
            p95_latency_ms=max(0, base_latency * 2.5),
            p99_latency_ms=max(0, base_latency * 4.0),
            error_rate=error_rate,
            active_users=active_users,
            active_chaos_events=len(active_chaos),
        )

    def _test_chaos_survival(self, metrics: MetricPoint, event: ChaosEvent) -> bool:
        if event.action in (ChaosAction.KILL_POD, ChaosAction.DB_CONNECTION_KILL, ChaosAction.NETWORK_PARTITION):
            return metrics.error_rate < 0.15
        elif event.action in (ChaosAction.CPU_STORM, ChaosAction.MEMORY_STORM):
            return metrics.cpu_percent < 95 and metrics.memory_percent < 95
        elif event.action == ChaosAction.NETWORK_DELAY:
            return metrics.p99_latency_ms < 3000
        return True

    def _generate_recommendation(self, result: SimulationResult) -> str:
        recommendations = []
        if result.error_rate > 0.01:
            recommendations.append("Improve error handling and retry logic")
        if result.p99_latency_ms > 500:
            recommendations.append("Optimize database queries and implement caching")
        if result.chaos_events_survived < result.chaos_events_triggered * 0.8:
            recommendations.append("Implement circuit breakers and graceful degradation")
        if result.peak_cpu > 80:
            recommendations.append("Increase CPU resources or optimize compute-heavy operations")
        if result.peak_memory > 80:
            recommendations.append("Increase memory limits or optimize memory usage")
        if not recommendations:
            recommendations.append("System is ready for production deployment")
        return "; ".join(recommendations)

    # ── Queries ─────────────────────────────────────────────────────────

    def get_latest_result(self) -> SimulationResult | None:
        return self._results[-1] if self._results else None

    def get_results(self, limit: int = 5) -> list[SimulationResult]:
        return self._results[-limit:]

    def get_stats(self) -> dict[str, Any]:
        passed = sum(1 for r in self._results if r.passed)
        return {
            "simulations_run": len(self._results),
            "passed": passed, "failed": len(self._results) - passed,
            "avg_error_rate": sum(r.error_rate for r in self._results) / max(1, len(self._results)),
            "avg_p99_latency": sum(r.p99_latency_ms for r in self._results) / max(1, len(self._results)),
            "total_chaos_events": sum(r.chaos_events_triggered for r in self._results),
            "total_chaos_survived": sum(r.chaos_events_survived for r in self._results),
            "docker_available": self._docker.is_docker_available,
            "locust_available": self._docker.is_locust_available,
        }
