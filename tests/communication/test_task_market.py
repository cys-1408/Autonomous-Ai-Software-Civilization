"""Tests for TaskMarket — agent bidding protocol."""

import pytest
from unittest.mock import AsyncMock

from backend.communication.task_market import TaskMarket
from backend.communication.message_types import (
    TaskDefinition,
    TaskBid,
    TaskPriority,
    TaskStatus,
)


@pytest.fixture
def task_market():
    return TaskMarket()


@pytest.fixture
def sample_task():
    return TaskDefinition(
        name="Design Database Schema",
        description="Design the database schema",
        difficulty=7,
        priority=TaskPriority.HIGH,
        required_specialization="database_design",
        max_bid=50,
    )


@pytest.fixture
def sample_bid():
    return TaskBid(
        source="database_agent",
        task_id="test-task",
        bid_amount=15,
        confidence=0.95,
        estimated_time_seconds=300,
        justification="I specialize in database design",
        metadata={"specializations": ["database_design"]},
    )


class TestTaskMarketInitialization:
    def test_init_empty(self, task_market):
        assert task_market._active_tasks == {}
        assert task_market._bids == {}
        assert task_market._assignments == {}

    def test_reputation_default(self, task_market):
        assert task_market.get_reputation("unknown_agent") == 50.0

    def test_set_reputation(self, task_market):
        task_market.set_reputation("agent_1", 85.0)
        assert task_market.get_reputation("agent_1") == 85.0

    def test_set_reputation_clamps(self, task_market):
        task_market.set_reputation("agent_1", 150.0)
        assert task_market.get_reputation("agent_1") == 100.0
        task_market.set_reputation("agent_1", -10.0)
        assert task_market.get_reputation("agent_1") == 0.0


@pytest.mark.asyncio
class TestTaskMarketBidding:
    async def test_publish_task_creates_entry(self, task_market, sample_task):
        task = await task_market.publish_task(sample_task, bidding_timeout=0.1)
        assert task_market.get_task(sample_task.id) is not None
        assert task.status in (TaskStatus.ASSIGNED, TaskStatus.UNASSIGNED)

    async def test_submit_bid_success(self, task_market, sample_task, sample_bid):
        await task_market.publish_task(sample_task, bidding_timeout=1.0)
        result = task_market.submit_bid(sample_bid)
        assert result is True
        bids = task_market.get_bids(sample_task.id)
        assert len(bids) == 1
        assert bids[0].source == "database_agent"

    async def test_submit_bid_rejects_duplicate(self, task_market, sample_task, sample_bid):
        await task_market.publish_task(sample_task, bidding_timeout=1.0)
        task_market.submit_bid(sample_bid)
        result = task_market.submit_bid(sample_bid)
        assert result is False

    async def test_submit_bid_rejects_exceeds_max(self, task_market, sample_task):
        await task_market.publish_task(sample_task, bidding_timeout=1.0)
        big_bid = TaskBid(
            source="expensive_agent",
            task_id=sample_task.id,
            bid_amount=100,
            confidence=0.5,
            metadata={"specializations": ["database_design"]},
        )
        result = task_market.submit_bid(big_bid)
        assert result is False

    async def test_submit_bid_rejects_missing_specialization(self, task_market, sample_task):
        await task_market.publish_task(sample_task, bidding_timeout=1.0)
        wrong_bid = TaskBid(
            source="frontend_agent",
            task_id=sample_task.id,
            bid_amount=10,
            confidence=0.5,
            metadata={"specializations": ["frontend"]},
        )
        result = task_market.submit_bid(wrong_bid)
        assert result is False

    async def test_submit_bid_rejects_nonexistent_task(self, task_market):
        bid = TaskBid(source="agent", task_id="nonexistent", bid_amount=10, confidence=0.5)
        result = task_market.submit_bid(bid)
        assert result is False


class TestTaskMarketScoring:
    def test_select_winner_with_reputation(self, task_market, sample_task):
        task_market.set_reputation("high_rep", 90.0)
        task_market.set_reputation("low_rep", 30.0)

        high_bid = TaskBid(
            source="high_rep", task_id=sample_task.id,
            bid_amount=20, confidence=0.8,
            metadata={"specializations": ["database_design"]},
        )
        low_bid = TaskBid(
            source="low_rep", task_id=sample_task.id,
            bid_amount=10, confidence=0.5,
            metadata={"specializations": ["database_design"]},
        )

        task_market._active_tasks[sample_task.id] = sample_task
        task_market._bids[sample_task.id] = [high_bid, low_bid]

        assignment = task_market._select_winner(sample_task)
        assert assignment.winning_bid is not None
        assert assignment.winning_bid.source == "high_rep"

    def test_no_bids_returns_unassigned(self, task_market, sample_task):
        task_market._active_tasks[sample_task.id] = sample_task
        assignment = task_market._select_winner(sample_task)
        assert assignment.winning_bid is None
        assert assignment.status == TaskStatus.UNASSIGNED


class TestTaskMarketManagement:
    def test_cancel_task(self, task_market, sample_task):
        task_market._active_tasks[sample_task.id] = sample_task
        task_market._task_status[sample_task.id] = TaskStatus.OPEN
        result = task_market.cancel_task(sample_task.id)
        assert result is True
        assert task_market.get_status(sample_task.id) == TaskStatus.CANCELLED

    def test_cancel_nonexistent_task(self, task_market):
        result = task_market.cancel_task("nonexistent")
        assert result is False

    def test_leaderboard_order(self, task_market):
        task_market.set_reputation("agent_a", 95.0)
        task_market.set_reputation("agent_b", 80.0)
        task_market.set_reputation("agent_c", 60.0)
        lb = task_market.get_leaderboard()
        assert lb[0]["agent_id"] == "agent_a"
        assert lb[1]["agent_id"] == "agent_b"
        assert lb[2]["agent_id"] == "agent_c"

    def test_get_task_returns_none(self, task_market):
        assert task_market.get_task("nonexistent") is None

    def test_get_assignment_returns_none(self, task_market):
        assert task_market.get_assignment("nonexistent") is None
