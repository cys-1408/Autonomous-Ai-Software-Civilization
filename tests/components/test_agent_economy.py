"""Tests for AgentEconomy — stock-market task allocation."""

import pytest
from backend.components.agent_economy import AgentEconomy
from backend.models.agent import AgentProfile, AgentDNA, Specialization, AgentState, ReasoningStyle, RiskTolerance
from backend.communication.message_types import TaskDefinition, TaskBid, TaskPriority


@pytest.fixture
def economy():
    return AgentEconomy()


@pytest.fixture
def sample_agent():
    dna = AgentDNA(
        specializations=[Specialization.DATABASE_DESIGN],
        reasoning_style=ReasoningStyle.ANALYTICAL,
        risk_tolerance=RiskTolerance.LOW,
    )
    return AgentProfile(
        id="agent-001", name="Test Agent", dna=dna,
        state=AgentState.IDLE, credits=100.0, reputation=50.0,
    )


class TestAgentRegistration:
    def test_register_agent(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        assert economy.get_agent("agent-001") is not None
        assert economy.get_agent("agent-001").credits == 50.0  # base stipend

    def test_register_duplicate(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        economy.register_agent(sample_agent)
        assert len(economy.get_all_agents()) == 1

    def test_unregister_agent(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        economy.unregister_agent("agent-001")
        assert economy.get_agent("agent-001") is None

    def test_get_nonexistent_agent(self, economy):
        assert economy.get_agent("nonexistent") is None


class TestCredits:
    def test_get_credits(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        assert economy.get_credits("agent-001") == 50.0

    def test_add_credits(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        result = economy.add_credits("agent-001", 30.0, "Task reward")
        assert result is True
        assert economy.get_credits("agent-001") == 80.0

    def test_deduct_credits_success(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        result = economy.deduct_credits("agent-001", 20.0, "Cost")
        assert result is True
        assert economy.get_credits("agent-001") == 30.0

    def test_deduct_credits_insufficient(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        result = economy.deduct_credits("agent-001", 200.0, "Too expensive")
        assert result is False

    def test_transfer_credits(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        agent2 = AgentProfile(id="agent-002", name="Agent 2")
        economy.register_agent(agent2)
        result = economy.transfer_credits("agent-001", "agent-002", 20.0, "Payment")
        assert result is True
        assert economy.get_credits("agent-001") == 30.0
        assert economy.get_credits("agent-002") == 70.0


class TestReputation:
    def test_initial_reputation(self, economy):
        assert economy.get_reputation("unknown") == 0.0

    def test_update_reputation(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        economy.update_reputation("agent-001", 10.0, "Good work")
        assert economy.get_reputation("agent-001") == 60.0

    def test_update_reputation_clamps(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        economy.update_reputation("agent-001", 100.0, "Max")
        assert economy.get_reputation("agent-001") == 100.0
        economy.update_reputation("agent-001", -200.0, "Min")
        assert economy.get_reputation("agent-001") == 0.0

    def test_reward_task_completion(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        task = TaskDefinition(name="Test", difficulty=5)
        economy.reward_task_completion("agent-001", task)
        assert economy.get_credits("agent-001") > 50.0
        assert economy.get_reputation("agent-001") > 50.0

    def test_penalize_task_failure(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        task = TaskDefinition(name="Test", difficulty=5)
        economy.penalize_task_failure("agent-001", task)
        assert economy.get_credits("agent-001") < 50.0
        assert economy.get_reputation("agent-001") < 50.0


class TestBidScoring:
    def test_score_bid_high_reputation_wins(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        economy.update_reputation("agent-001", 40.0, "Boost")

        low_rep_agent = AgentProfile(id="agent-002", name="Low Rep")
        low_rep_agent.reputation = 10.0
        economy.register_agent(low_rep_agent)

        task = TaskDefinition(name="Test", difficulty=5, max_bid=50, required_specialization="database_design")

        high_bid = TaskBid(source="agent-001", task_id=task.id, bid_amount=20, confidence=0.9,
                           metadata={"specializations": ["database_design"]})
        low_bid = TaskBid(source="agent-002", task_id=task.id, bid_amount=10, confidence=0.5,
                          metadata={"specializations": ["database_design"]})

        score_high = economy.score_bid(high_bid, task)
        score_low = economy.score_bid(low_bid, task)
        assert score_high > score_low


class TestLeaderboard:
    def test_leaderboard_order(self, economy):
        for i in range(3):
            agent = AgentProfile(id=f"agent-{i}", name=f"Agent {i}")
            agent.reputation = 80.0 - (i * 20)
            economy.register_agent(agent)
        lb = economy.get_leaderboard(top_n=10)
        assert len(lb) == 3
        assert lb[0]["reputation"] >= lb[1]["reputation"]

    def test_leaderboard_limited(self, economy):
        for i in range(20):
            agent = AgentProfile(id=f"agent-{i}", name=f"Agent {i}")
            economy.register_agent(agent)
        lb = economy.get_leaderboard(top_n=5)
        assert len(lb) == 5


class TestMarketSummary:
    def test_market_summary_no_agents(self, economy):
        summary = economy.get_market_summary()
        assert summary["status"] == "no_agents"

    def test_market_summary_with_agents(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        summary = economy.get_market_summary()
        assert summary["total_agents"] == 1
        assert summary["total_credits_in_circulation"] == 50.0

    def test_transaction_history(self, economy, sample_agent):
        economy.register_agent(sample_agent)
        economy.add_credits("agent-001", 20.0, "Reward")
        history = economy.get_transaction_history("agent-001")
        assert len(history) >= 1
        assert history[-1]["reason"] == "Reward"
