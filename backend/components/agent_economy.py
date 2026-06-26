"""Agent Economy (Component 2).

Works like a stock market:
- Agents have Credits (internal money), Reputation (trust score), Specialization
- Agents compete for tasks by bidding
- Best agent wins based on reputation, confidence, and cost
- Rewards and penalties adjust agent standing

The economy is self-regulating:
- Successful agents earn credits and reputation
- Failed agents lose reputation and may become uncompetitive
- New agents start with a baseline but must prove themselves
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.agents.base import BaseAgent
from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    TaskDefinition,
    TaskBid,
    TaskAssignment,
    TaskPriority,
    TaskStatus,
    TelemetryData,
    DashboardUpdate,
)
from backend.models.agent import (
    AgentProfile,
    AgentState,
    Specialization,
)

logger = structlog.get_logger(__name__)


class AgentEconomy:
    """Manages the economic life of the agent civilization.

    The economy tracks:
    - Agent credit balances (earned through task completion)
    - Agent reputation scores (earned through quality work)
    - Transaction history (bids, rewards, penalties)
    - Market prices (task difficulty-to-credit mapping)
    - Inflation/deflation controls
    """

    def __init__(self, hub: CommunicationHub | None = None):
        self.hub = hub
        self._agents: dict[str, AgentProfile] = {}
        self._transactions: list[dict[str, Any]] = []
        self._running = False

        # Economy parameters
        self._base_stipend: float = 50.0  # Credits new agents receive
        self._task_base_reward: float = 20.0
        self._reputation_gain_per_task: float = 2.0
        self._reputation_loss_on_failure: float = 5.0
        self._credit_interest_rate: float = 0.001  # % per hour

    # ── Agent Registration ──────────────────────────────────────────────

    def register_agent(self, profile: AgentProfile) -> None:
        """Register an agent in the economy."""
        if profile.id in self._agents:
            return

        profile.credits = self._base_stipend
        self._agents[profile.id] = profile

        logger.info(
            "economy.agent_registered",
            agent=profile.name,
            starting_credits=profile.credits,
        )

    def unregister_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentProfile]:
        return list(self._agents.values())

    # ── Credits ─────────────────────────────────────────────────────────

    def get_credits(self, agent_id: str) -> float:
        agent = self._agents.get(agent_id)
        return agent.credits if agent else 0.0

    def add_credits(self, agent_id: str, amount: float, reason: str = "") -> bool:
        """Add credits to an agent's balance."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.credits += amount
        self._record_transaction(agent_id, amount, reason, "credit")
        return True

    def deduct_credits(self, agent_id: str, amount: float, reason: str = "") -> bool:
        """Deduct credits from an agent's balance."""
        agent = self._agents.get(agent_id)
        if not agent or agent.credits < amount:
            return False
        agent.credits -= amount
        self._record_transaction(agent_id, -amount, reason, "debit")
        return True

    def transfer_credits(
        self,
        from_agent: str,
        to_agent: str,
        amount: float,
        reason: str = "",
    ) -> bool:
        """Transfer credits between agents."""
        if self.deduct_credits(from_agent, amount, reason):
            self.add_credits(to_agent, amount, reason)
            return True
        return False

    # ── Reputation ──────────────────────────────────────────────────────

    def get_reputation(self, agent_id: str) -> float:
        agent = self._agents.get(agent_id)
        return agent.reputation if agent else 0.0

    def update_reputation(self, agent_id: str, delta: float, reason: str = "") -> None:
        """Update an agent's reputation score."""
        agent = self._agents.get(agent_id)
        if not agent:
            return
        agent.reputation = max(0.0, min(100.0, agent.reputation + delta))
        self._record_transaction(agent_id, delta, reason, "reputation")

    def reward_task_completion(self, agent_id: str, task: TaskDefinition) -> None:
        """Reward an agent for successfully completing a task."""
        reward = self._task_base_reward * (1.0 + task.difficulty * 0.15)
        self.add_credits(agent_id, reward, f"Completed: {task.name}")
        self.update_reputation(
            agent_id,
            self._reputation_gain_per_task * (1.0 + task.difficulty * 0.05),
            f"Task success: {task.name}",
        )

    def penalize_task_failure(self, agent_id: str, task: TaskDefinition) -> None:
        """Penalize an agent for failing a task."""
        penalty = self._task_base_reward * 0.5
        self.deduct_credits(agent_id, penalty, f"Failed: {task.name}")
        self.update_reputation(
            agent_id,
            -self._reputation_loss_on_failure,
            f"Task failure: {task.name}",
        )

    # ── Market Scoring ──────────────────────────────────────────────────

    def score_bid(
        self,
        bid: TaskBid,
        task: TaskDefinition,
    ) -> float:
        """Score a bid using the weighted algorithm.

        Score = (reputation_weight × reputation)
              + (confidence_weight × confidence)
              + (cost_weight × (1 - bid/max_bid))
              + (specialization_bonus if match)
        """
        agent = self._agents.get(bid.source)
        if not agent:
            return 0.0

        REPUTATION_WEIGHT = 0.35
        CONFIDENCE_WEIGHT = 0.30
        COST_WEIGHT = 0.20
        SPECIALIZATION_WEIGHT = 0.15

        rep_score = agent.reputation / 100.0
        conf_score = bid.confidence
        cost_score = 1.0 - (bid.bid_amount / max(task.max_bid, 1))

        # Specialization bonus
        spec_score = 0.0
        if task.required_specialization:
            spec_values = [s.value for s in agent.dna.specializations]
            if task.required_specialization in spec_values:
                spec_score = 1.0

        return (
            REPUTATION_WEIGHT * rep_score
            + CONFIDENCE_WEIGHT * conf_score
            + COST_WEIGHT * cost_score
            + SPECIALIZATION_WEIGHT * spec_score
        )

    def select_winner(
        self,
        task: TaskDefinition,
        bids: list[TaskBid],
    ) -> TaskBid | None:
        """Select the winning bid from a set of bids."""
        if not bids:
            return None

        scored = [(self.score_bid(bid, task), bid) for bid in bids]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    # ── Task Lifecycle ──────────────────────────────────────────────────

    def process_task_result(
        self,
        agent_id: str,
        task: TaskDefinition,
        succeeded: bool,
    ) -> dict[str, Any]:
        """Process the economic outcome of a task."""
        if succeeded:
            self.reward_task_completion(agent_id, task)
            return {"reward": True, "credits_changed": True}
        else:
            self.penalize_task_failure(agent_id, task)
            return {"reward": False, "credits_changed": True}

    # ── Agent Rating ────────────────────────────────────────────────────

    def get_leaderboard(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Get the top agents by combined wealth and reputation."""
        scored = []
        for agent in self._agents.values():
            # Combined score: reputation (70%) + normalized credits (30%)
            wealth_score = math.log10(max(1, agent.credits)) / 5.0  # Normalize
            combined = agent.reputation * 0.7 + wealth_score * 100 * 0.3
            scored.append({
                "agent_id": agent.id,
                "name": agent.name,
                "specialization": [s.value for s in agent.dna.specializations],
                "credits": round(agent.credits, 1),
                "reputation": round(agent.reputation, 1),
                "tasks_completed": agent.tasks_completed,
                "success_rate": round(agent.success_rate, 3),
                "combined_score": round(combined, 2),
            })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored[:top_n]

    def get_market_summary(self) -> dict[str, Any]:
        """Get a summary of the current economy state."""
        agents = list(self._agents.values())
        if not agents:
            return {"status": "no_agents"}

        return {
            "total_agents": len(agents),
            "total_credits_in_circulation": round(
                sum(a.credits for a in agents), 1
            ),
            "average_reputation": round(
                sum(a.reputation for a in agents) / len(agents), 1
            ),
            "total_tasks_completed": sum(a.tasks_completed for a in agents),
            "total_tasks_failed": sum(a.tasks_failed for a in agents),
            "overall_success_rate": round(
                sum(a.tasks_completed for a in agents)
                / max(1, sum(a.total_tasks for a in agents)),
                3,
            ),
            "total_transactions": len(self._transactions),
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _record_transaction(
        self,
        agent_id: str,
        amount: float,
        reason: str,
        tx_type: str,
    ) -> None:
        self._transactions.append({
            "agent_id": agent_id,
            "amount": amount,
            "reason": reason,
            "type": tx_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_transaction_history(
        self,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        history = self._transactions
        if agent_id:
            history = [t for t in history if t["agent_id"] == agent_id]
        return history[-limit:]
