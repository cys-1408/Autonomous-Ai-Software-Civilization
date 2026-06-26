"""Negotiation Protocol — Agent Court dispute resolution.

When agents deadlock on a decision, the Court convenes:
- 5-7 randomly selected judge agents (excluding disputants)
- Structured evidence submission
- Independent deliberation
- Majority vote determines outcome
"""

from __future__ import annotations

import asyncio
import random
from typing import Optional
from enum import Enum

import structlog

from backend.communication.message_types import (
    NegotiationMessage,
    NegotiationStance,
    CourtVerdict,
)

logger = structlog.get_logger(__name__)


class DisputeStatus(str, Enum):
    OPEN = "open"
    EVIDENCE_COLLECTION = "evidence_collection"
    DELIBERATION = "deliberation"
    VOTING = "voting"
    RESOLVED = "resolved"


class Dispute:
    """A dispute between agents that requires court resolution."""

    def __init__(
        self,
        dispute_id: str,
        topic: str,
        parties: list[str],
        description: str = "",
    ):
        self.dispute_id = dispute_id
        self.topic = topic
        self.parties = parties
        self.description = description
        self.status = DisputeStatus.OPEN
        self.judges: list[str] = []
        self.evidence: list[NegotiationMessage] = []
        self.votes: list[NegotiationMessage] = []
        self.verdict: Optional[CourtVerdict] = None


class NegotiationProtocol:
    """Agent Court system for democratic dispute resolution.

    Prevents any single agent from controlling the system by requiring
    majority vote from an independent judge panel.
    """

    def __init__(self, judge_pool: Optional[list[str]] = None):
        self._judge_pool = judge_pool or []
        self._disputes: dict[str, Dispute] = {}
        self._completed_disputes: list[Dispute] = []
        self._judge_credits: dict[str, float] = {}

    def set_judge_pool(self, agent_ids: list[str]) -> None:
        """Set the pool of agents eligible to serve as judges."""
        self._judge_pool = agent_ids
        for agent_id in agent_ids:
            self._judge_credits.setdefault(agent_id, 0.0)

    async def convene(
        self,
        dispute_id: str,
        topic: str,
        parties: list[str],
        description: str = "",
        judge_count: int = 5,
    ) -> Dispute:
        """Convene the court for a new dispute.

        Selects random judges from the pool, excluding all parties involved.
        """
        # Select judges (exclude disputants)
        eligible_judges = [
            j for j in self._judge_pool if j not in parties
        ]
        selected_judges = random.sample(
            eligible_judges,
            min(judge_count, len(eligible_judges)),
        )

        dispute = Dispute(
            dispute_id=dispute_id,
            topic=topic,
            parties=parties,
            description=description,
        )
        dispute.judges = selected_judges
        dispute.status = DisputeStatus.EVIDENCE_COLLECTION

        self._disputes[dispute_id] = dispute

        logger.info(
            "negotiation.convened",
            dispute_id=dispute_id,
            topic=topic,
            parties=parties,
            judges=selected_judges,
        )
        return dispute

    async def submit_evidence(
        self,
        dispute_id: str,
        message: NegotiationMessage,
    ) -> bool:
        """Submit evidence from a party or external source."""
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            logger.warning(
                "negotiation.dispute_not_found",
                dispute_id=dispute_id,
            )
            return False

        if dispute.status != DisputeStatus.EVIDENCE_COLLECTION:
            logger.warning(
                "negotiation.wrong_status",
                dispute_id=dispute_id,
                status=dispute.status,
            )
            return False

        dispute.evidence.append(message)
        logger.info(
            "negotiation.evidence_submitted",
            dispute_id=dispute_id,
            source=message.source,
            stance=message.stance,
        )
        return True

    async def cast_vote(
        self,
        dispute_id: str,
        vote: NegotiationMessage,
    ) -> bool:
        """A judge casts their vote."""
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return False

        if vote.source not in dispute.judges:
            logger.warning(
                "negotiation.not_a_judge",
                dispute_id=dispute_id,
                voter=vote.source,
            )
            return False

        # Check if judge already voted
        existing_votes = [v for v in dispute.votes if v.source == vote.source]
        if existing_votes:
            logger.warning(
                "negotiation.already_voted",
                dispute_id=dispute_id,
                judge=vote.source,
            )
            return False

        dispute.votes.append(vote)
        logger.info(
            "negotiation.vote_cast",
            dispute_id=dispute_id,
            judge=vote.source,
            stance=vote.stance,
        )

        # Check if all judges have voted
        if len(dispute.votes) >= len(dispute.judges):
            await self._resolve(dispute)

        return True

    async def _resolve(self, dispute: Dispute) -> CourtVerdict:
        """Tally votes and produce a verdict."""
        approve_count = sum(
            1 for v in dispute.votes
            if v.stance == NegotiationStance.APPROVE
        )
        reject_count = sum(
            1 for v in dispute.votes
            if v.stance == NegotiationStance.REJECT
        )

        outcome = (
            NegotiationStance.APPROVE
            if approve_count > reject_count
            else NegotiationStance.REJECT
        )

        verdict = CourtVerdict(
            dispute_id=dispute.dispute_id,
            outcome=outcome,
            votes_for_approval=approve_count,
            votes_for_rejection=reject_count,
            judge_count=len(dispute.judges),
            reasoning_summary=f"Vote: {approve_count} approve, {reject_count} reject",
            source="agent_court",
        )

        dispute.verdict = verdict
        dispute.status = DisputeStatus.RESOLVED

        # Award credits to participating judges
        for judge_id in dispute.judges:
            self._judge_credits[judge_id] = (
                self._judge_credits.get(judge_id, 0.0) + 5.0
            )

        self._completed_disputes.append(dispute)
        del self._disputes[dispute.dispute_id]

        logger.info(
            "negotiation.resolved",
            dispute_id=dispute.dispute_id,
            outcome=outcome,
            approve=approve_count,
            reject=reject_count,
        )
        return verdict

    async def appeal(
        self,
        dispute_id: str,
        human_reasoning: str,
    ) -> Optional[CourtVerdict]:
        """Human appeal — override court verdict with documented justification."""
        # Find in completed disputes
        for dispute in self._completed_disputes:
            if dispute.dispute_id == dispute_id:
                verdict = CourtVerdict(
                    dispute_id=dispute_id,
                    outcome=NegotiationStance.APPROVE,
                    judge_count=0,
                    reasoning_summary=f"Human appeal: {human_reasoning}",
                    source="human_appeal",
                )
                logger.info(
                    "negotiation.human_appeal",
                    dispute_id=dispute_id,
                    reasoning=human_reasoning,
                )
                return verdict
        return None

    def get_dispute(self, dispute_id: str) -> Optional[Dispute]:
        """Get a dispute by ID."""
        return self._disputes.get(dispute_id)

    def get_active_disputes(self) -> list[Dispute]:
        """Get all currently active disputes."""
        return list(self._disputes.values())

    def get_judge_credits(self) -> dict[str, float]:
        """Get credits earned by judges."""
        return dict(self._judge_credits)
