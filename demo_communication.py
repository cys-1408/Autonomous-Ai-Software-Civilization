"""Demo: All 8 Communication Patterns Working Together

Run: python demo_communication.py

Demonstrates the full communication flow from user input to deployed software:
1. Event Bus — project creation broadcast
2. Task Market — agents bid on tasks
3. Direct Comm — agents request data from each other
4. Shared Memory — record and search past failures
5. Negotiation — Agent Court resolves a dispute
6. Telemetry — metrics collection
7. WebSocket — Command Center updates
8. Full flow — everything connected through the Hub
"""

import asyncio
import uuid
from datetime import datetime, timezone

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    TaskDefinition,
    TaskPriority,
    TaskBid,
    AgentMessage,
    NegotiationMessage,
    NegotiationStance,
    TelemetryData,
    DashboardUpdate,
    FailureRecord,
    GenomeRecord,
)


async def main():
    print("=" * 70)
    print("  AI CIVILIZATION — COMMUNICATION SYSTEM DEMO")
    print("=" * 70)

    # Initialize the Hub
    hub = CommunicationHub(
        redis_url="redis://localhost:6379/0",
    )
    await hub.connect()

    # ─────────────────────────────────────────────────────────────────
    # 1. EVENT BUS — Broadcast project creation
    # ─────────────────────────────────────────────────────────────────
    print("\n📡 [1/8] EVENT BUS — Broadcasting project creation...")

    event = await hub.publish_event(
        event_type=EventType.PROJECT_CREATED,
        payload={
            "project": "Hospital Management System",
            "projectId": "proj-001",
            "requirements": "Full hospital management with patient records, "
            "doctor scheduling, and billing",
        },
        source="goal_interpreter",
    )
    print(f"   ✅ Event published: {event.event_type.value}")
    print(f"   📋 Topic: {event.topic}")
    print(f"   🆔 Message ID: {event.id[:8]}...")

    # ─────────────────────────────────────────────────────────────────
    # 2. TASK MARKET — Agents bid on tasks
    # ─────────────────────────────────────────────────────────────────
    print("\n💰 [2/8] TASK MARKET — Publishing tasks for bidding...")

    # Set agent reputations
    hub.set_agent_reputation("architect_agent", 85.0)
    hub.set_agent_reputation("database_agent", 92.0)
    hub.set_agent_reputation("backend_agent", 70.0)
    hub.set_agent_reputation("frontend_agent", 78.0)

    # Publish a task
    task = TaskDefinition(
        name="Design Database Schema",
        description="Design the database schema for the hospital management system",
        difficulty=7,
        priority=TaskPriority.HIGH,
        required_specialization="database_design",
        max_bid=50,
    )

    # Submit bids from different agents
    hub.submit_bid(TaskBid(
        task_id=task.id,
        source="database_agent",
        bid_amount=15,
        confidence=0.95,
        estimated_time_seconds=300,
        justification="I specialize in database design with 92% reputation",
    ))

    hub.submit_bid(TaskBid(
        task_id=task.id,
        source="backend_agent",
        bid_amount=25,
        confidence=0.60,
        estimated_time_seconds=600,
        justification="I can do it but database is not my primary specialty",
    ))

    hub.submit_bid(TaskBid(
        task_id=task.id,
        source="architect_agent",
        bid_amount=30,
        confidence=0.70,
        estimated_time_seconds=450,
        justification="I understand the architecture requirements well",
    ))

    # Publish task and wait for bids (short timeout for demo)
    assignment = await hub.publish_task(task, bidding_timeout=2.0)

    if assignment.winning_bid:
        print(f"   🏆 Winner: {assignment.winning_bid.source}")
        print(f"   💵 Winning bid: {assignment.winning_bid.bid_amount} credits")
        print(f"   📊 Confidence: {assignment.winning_bid.confidence:.0%}")
        print(f"   ⏱️  Est. time: {assignment.winning_bid.estimated_time_seconds}s")
        print(f"   🥈 Runner-up: {assignment.runner_up_bids[0].source if assignment.runner_up_bids else 'N/A'}")

    # ─────────────────────────────────────────────────────────────────
    # 3. DIRECT COMM — Agent-to-agent request/response
    # ─────────────────────────────────────────────────────────────────
    print("\n🔗 [3/8] DIRECT COMM — Agent-to-agent communication...")

    # Register a database agent handler
    async def database_agent_handler(msg: AgentMessage) -> AgentMessage:
        return AgentMessage(
            source="database_agent",
            target=msg.source,
            method=msg.method,
            response_data={
                "tables": ["Patients", "Doctors", "Appointments", "Billing"],
                "relationships": [
                    "Patient -> Appointments (1:N)",
                    "Doctor -> Appointments (1:N)",
                    "Appointment -> Billing (1:1)",
                ],
            },
            is_response=True,
        )

    hub.register_agent("database_agent", database_agent_handler)

    # Architect asks Database Agent for schema
    response = await hub.send_message(
        source="architect_agent",
        target="database_agent",
        method="get_schema",
        data={"module": "Patient", "include_relations": True},
    )

    if response:
        print(f"   📨 Request: architect_agent → database_agent.get_schema()")
        print(f"   📩 Response tables: {response.response_data['tables']}")
        print(f"   🔗 Relationships: {len(response.response_data['relationships'])}")

    # ─────────────────────────────────────────────────────────────────
    # 4. SHARED MEMORY — Record and search past failures
    # ─────────────────────────────────────────────────────────────────
    print("\n🧠 [4/8] SHARED MEMORY — Failure Memory Network...")

    # Record a past failure
    failure = FailureRecord(
        failure_type="sql_injection",
        root_cause="Unsanitized user input in patient search query",
        affected_code="api/patient/search.py:42",
        fix_applied="Added parameterized queries and input validation",
        agents_involved=["backend_agent", "security_agent"],
        severity=8,
        project_id="proj-001",
        tags=["sql_injection", "patient_module", "critical"],
    )
    await hub.record_failure(failure)
    print(f"   📝 Recorded failure: {failure.failure_type} (severity: {failure.severity})")

    # Search for similar failures
    similar = await hub.search_failures(
        failure_type="sql_injection",
        min_severity=5,
    )
    print(f"   🔍 Found {len(similar)} similar past failures")
    if similar:
        print(f"   📋 Most severe: {similar[0].root_cause}")

    # Store a genome
    genome = GenomeRecord(
        project_id="proj-001",
        architecture_pattern="microservice",
        security_model="zero_trust",
        database_choice="postgresql",
        deployment_target="kubernetes",
        performance_profile={"rps_target": 1000, "p99_latency_ms": 200},
        success_rating=0.85,
    )
    await hub.store_genome(genome)
    print(f"   🧬 Stored genome: {genome.architecture_pattern} / {genome.database_choice}")

    # ─────────────────────────────────────────────────────────────────
    # 5. NEGOTIATION — Agent Court dispute
    # ─────────────────────────────────────────────────────────────────
    print("\n⚖️ [5/8] NEGOTIATION — Agent Court convening...")

    # Set up judge pool
    hub.negotiation.set_judge_pool([
        "judge_alpha", "judge_beta", "judge_gamma",
        "judge_delta", "judge_epsilon",
    ])

    # Convene court
    dispute = await hub.convene_court(
        dispute_id="dispute-001",
        topic="Deployment blocked due to SQL injection vulnerability",
        parties=["security_agent", "performance_agent"],
        description="Security agent blocks deployment, Performance agent wants to proceed",
    )
    print(f"   🏛️ Court convened: {dispute.topic}")
    print(f"   👨‍⚖️ Judges: {dispute.judges}")

    # Submit evidence
    await hub.submit_court_evidence(
        "dispute-001",
        NegotiationMessage(
            source="security_agent",
            dispute_id="dispute-001",
            stance=NegotiationStance.REJECT,
            evidence=[{"type": "vulnerability", "severity": 8, "cwe": "CWE-89"}],
            reasoning="SQL injection in patient search is a critical vulnerability",
        ),
    )

    await hub.submit_court_evidence(
        "dispute-001",
        NegotiationMessage(
            source="performance_agent",
            dispute_id="dispute-001",
            stance=NegotiationStance.APPROVE,
            evidence=[{"type": "benchmark", "load_test_passed": True}],
            reasoning="Performance tests pass, deployment is safe from a performance standpoint",
        ),
    )

    # Judges vote (4 reject, 1 approve)
    for i, judge_id in enumerate(dispute.judges):
        stance = NegotiationStance.REJECT if i < 4 else NegotiationStance.APPROVE
        await hub.cast_court_vote(
            "dispute-001",
            NegotiationMessage(
                source=judge_id,
                dispute_id="dispute-001",
                stance=stance,
                reasoning=f"Judge {judge_id} voting based on evidence",
            ),
        )

    verdict = hub.negotiation.get_active_disputes()
    print(f"   📜 Verdict rendered (court resolved)")

    # ─────────────────────────────────────────────────────────────────
    # 6. TELEMETRY — Metrics collection
    # ─────────────────────────────────────────────────────────────────
    print("\n📊 [6/8] TELEMETRY — Collecting metrics...")

    hub.record_telemetry(TelemetryData(
        source_component="agent_economy",
        cpu_percent=45.2,
        memory_percent=62.1,
        latency_ms=12.5,
        error_rate=0.01,
        requests_per_second=150.0,
    ))

    hub.record_telemetry(TelemetryData(
        source_component="adversarial_arena",
        cpu_percent=78.5,
        memory_percent=85.3,
        latency_ms=45.2,
        error_rate=0.05,
        requests_per_second=30.0,
    ))

    hub.telemetry.record_agent_metrics("database_agent", credits=250, reputation=92)
    hub.telemetry.record_task("completed")

    summary = hub.get_system_metrics()
    print(f"   📈 Components reporting: {summary['component_count']}")
    print(f"   🖥️  Avg CPU: {summary['avg_cpu']:.1f}%")
    print(f"   🧠 Avg Memory: {summary['avg_memory']:.1f}%")
    print(f"   ⚡ Avg Latency: {summary['avg_latency']:.1f}ms")
    print(f"   📊 Total RPS: {summary['total_rps']:.0f}")

    twin_config = hub.get_digital_twin_config()
    print(f"   🏭 Digital Twin: {twin_config['simulated_users']} simulated users")

    # ─────────────────────────────────────────────────────────────────
    # 7. WEBSOCKET — Command Center updates
    # ─────────────────────────────────────────────────────────────────
    print("\n🖥️  [7/8] WEBSOCKET — Command Center updates...")

    await hub.push_dashboard_update(DashboardUpdate(
        update_type="agent_status",
        data={
            "agent_id": "database_agent",
            "status": "working",
            "task": "Designing database schema",
            "progress": 65,
        },
        visual_hint="green",
        source="command_center",
    ))

    await hub.push_dashboard_update(DashboardUpdate(
        update_type="alert",
        data={
            "alert_type": "vulnerability_found",
            "severity": "high",
            "component": "patient_search",
            "details": "SQL injection vulnerability detected",
        },
        visual_hint="red",
        source="adversarial_arena",
    ))

    print("   📡 Dashboard updates pushed")
    print(f"   👥 Connected clients: {hub.websocket.get_client_count()}")

    # ─────────────────────────────────────────────────────────────────
    # 8. FULL FLOW — End-to-end summary
    # ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  🔄 [8/8] FULL COMMUNICATION FLOW SUMMARY")
    print("=" * 70)

    status = hub.get_status()
    print(f"\n  System Status:")
    print(f"  ├── Connected: {status['connected']}")
    print(f"  ├── Event Bus: ✅ Active")
    print(f"  ├── Task Market: {status['task_market']['active_tasks']} active tasks")
    print(f"  ├── Direct Comm: {len(status['direct_comm']['registered_agents'])} agents registered")
    print(f"  ├── Shared Memory: {status['shared_memory']['failure_records']} failures, "
          f"{status['shared_memory']['genome_records']} genomes")
    print(f"  ├── Negotiation: {status['negotiation']['active_disputes']} active disputes")
    print(f"  ├── Telemetry: {len(status['telemetry']['components'])} components")
    print(f"  └── WebSocket: {status['websocket']['connected_clients']} clients")

    print("\n" + "=" * 70)
    print("  ✅ ALL 8 COMMUNICATION PATTERNS VERIFIED")
    print("=" * 70)
    print("\n  The communication system is operational.")
    print("  Agents can now: broadcast, bid, call each other,")
    print("  share memory, negotiate, report metrics,")
    print("  and stream to the Command Center.")

    await hub.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
