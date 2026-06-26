"""Task Market — Agent bidding protocol for task assignment.

When a task is published, agents submit bids based on their specialization
and confidence. The market selects the best bidder using reputation,
bid amount, and confidence scoring.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from backend.communication.message_types import (
    TaskDefinition,
    TaskBid,
    TaskAssignment,
    TaskStatus,
)

logger = structlog.get_logger(__name__)


class TaskMarket:
    """Internal marketplace where agents compete for tasks.

    The market manages the bidding lifecycle:
    1. Task is published
    2. Bidding window opens (configurable timeout)
    3. Agents submit bids
    4. Winner is selected by scoring algorithm
    5. Assignment is broadcast
    """

    def __init__(self):
        self._active_tasks: dict[str, TaskDefinition] = {}
        self._bids: dict[str, list[TaskBid]] = {}  # task_id -> bids
        self._assignments: dict[str, TaskAssignment] = {}
        self._agent_reputations: dict[str, float] = {}  # agent_id -> rep (0-100)
        self._task_status: dict[str, TaskStatus] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def set_reputation(self, agent_id: str, reputation: float) -> None:
        """Update an agent's reputation score (0-100)."""
        self._agent_reputations[agent_id] = max(0.0, min(100.0, reputation))

    def get_reputation(self, agent_id: str) -> float:
        """Get an agent's current reputation."""
        return self._agent_reputations.get(agent_id, 50.0)

    async def publish_task(
        self,
        task: TaskDefinition,
        bidding_timeout: float = 30.0,
    ) -> TaskAssignment:
        """Publish a task and collect bids, then assign to the best bidder.

        Args:
            task: The task to be bid on.
            bidding_timeout: Seconds to wait for bids before auto-assigning.

        Returns:
            TaskAssignment with the winning bidder.
        """
        async with self._locks.setdefault(task.id, asyncio.Lock()):
            if task.id in self._active_tasks:
                raise ValueError(f"Task {task.id} has already been published")
            self._active_tasks[task.id] = task
            self._bids[task.id] = []
            self._task_status[task.id] = TaskStatus.OPEN

        logger.info(
            "task_market.published",
            task_id=task.id,
            name=task.name,
            difficulty=task.difficulty,
            priority=task.priority,
            bidding_timeout=bidding_timeout,
        )

        # Wait for bids
        await asyncio.sleep(bidding_timeout)

        # Select winner
        async with self._locks[task.id]:
            assignment = self._select_winner(task)
            self._assignments[task.id] = assignment
            self._task_status[task.id] = assignment.status

        if assignment.winning_bid:
            logger.info(
                "task_market.assigned",
                task_id=task.id,
                winner=assignment.winning_bid.source,
                bid=assignment.winning_bid.bid_amount,
            )
        else:
            logger.warning("task_market.no_bids", task_id=task.id, name=task.name)

        return assignment

    def submit_bid(self, bid: TaskBid) -> bool:
        """Submit a bid for an active task.

        Returns True if the bid was accepted, False if task doesn't exist
        or bidding is closed.
        """
        if bid.task_id not in self._active_tasks:
            logger.warning(
                "task_market.bid_rejected",
                reason="task_not_found",
                task_id=bid.task_id,
            )
            return False
        if self._task_status.get(bid.task_id) != TaskStatus.OPEN:
            logger.warning(
                "task_market.bid_rejected",
                reason="bidding_closed",
                task_id=bid.task_id,
            )
            return False

        task = self._active_tasks[bid.task_id]

        # Validate bid constraints
        if bid.bid_amount > task.max_bid:
            logger.warning(
                "task_market.bid_rejected",
                reason="exceeds_max_bid",
                bid=bid.bid_amount,
                max=task.max_bid,
            )
            return False
        if task.required_specialization:
            specializations = bid.metadata.get("specializations", [])
            if task.required_specialization not in specializations:
                logger.warning(
                    "task_market.bid_rejected",
                    reason="missing_specialization",
                    task_id=bid.task_id,
                    required=task.required_specialization,
                )
                return False
        if any(existing.source == bid.source for existing in self._bids[bid.task_id]):
            logger.warning(
                "task_market.bid_rejected",
                reason="duplicate_agent_bid",
                task_id=bid.task_id,
                agent=bid.source,
            )
            return False

        self._bids[bid.task_id].append(bid)

        logger.info(
            "task_market.bid_received",
            task_id=bid.task_id,
            agent=bid.source,
            amount=bid.bid_amount,
            confidence=bid.confidence,
        )
        return True

    def _select_winner(self, task: TaskDefinition) -> TaskAssignment:
        """Select the winning bid using a weighted scoring algorithm.

        Score = (reputation_weight * reputation)
              + (confidence_weight * confidence)
              + (cost_weight * (1 - bid_amount / max_bid))

        Higher score wins. This rewards:
        - High reputation agents
        - High confidence bids
        - Lower cost bids
        """
        bids = self._bids.get(task.id, [])

        if not bids:
            return TaskAssignment(
                task=task,
                winning_bid=None,
                source="task_market",
                status=TaskStatus.UNASSIGNED,
            )

        # Scoring weights
        REPUTATION_WEIGHT = 0.4
        CONFIDENCE_WEIGHT = 0.35
        COST_WEIGHT = 0.25

        scored_bids = []
        for bid in bids:
            reputation = self.get_reputation(bid.source)
            cost_score = 1.0 - (bid.bid_amount / max(task.max_bid, 1))

            score = (
                REPUTATION_WEIGHT * (reputation / 100.0)
                + CONFIDENCE_WEIGHT * bid.confidence
                + COST_WEIGHT * cost_score
            )
            scored_bids.append((score, bid))

        scored_bids.sort(key=lambda x: x[0], reverse=True)

        winning_bid = scored_bids[0][1]
        runner_ups = [bid for _, bid in scored_bids[1:]]

        return TaskAssignment(
            task=task,
            winning_bid=winning_bid,
            runner_up_bids=runner_ups,
            source="task_market",
            status=TaskStatus.ASSIGNED,
        )

    def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        """Get a task by ID."""
        return self._active_tasks.get(task_id)

    def get_bids(self, task_id: str) -> list[TaskBid]:
        """Get all bids for a task."""
        return self._bids.get(task_id, [])

    def get_assignment(self, task_id: str) -> Optional[TaskAssignment]:
        """Get the assignment result for a task."""
        return self._assignments.get(task_id)

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """Return the task's bidding/assignment state."""
        return self._task_status.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Close bidding for a task without assigning it."""
        if self._task_status.get(task_id) != TaskStatus.OPEN:
            return False
        self._task_status[task_id] = TaskStatus.CANCELLED
        return True

    def get_leaderboard(self) -> list[dict]:
        """Get agents ranked by reputation."""
        return sorted(
            [
                {"agent_id": aid, "reputation": rep}
                for aid, rep in self._agent_reputations.items()
            ],
            key=lambda x: x["reputation"],
            reverse=True,
        )
