"""Tests for NegotiationProtocol — Agent Court dispute resolution."""

import pytest

from backend.communication.negotiation import NegotiationProtocol, DisputeStatus
from backend.communication.message_types import (
    NegotiationMessage,
    NegotiationStance,
)


@pytest.fixture
def negotiation():
    protocol = NegotiationProtocol()
    protocol.set_judge_pool(["judge_a", "judge_b", "judge_c", "judge_d", "judge_e"])
    return protocol


class TestNegotiationInitialization:
    def test_init_empty_pool(self):
        protocol = NegotiationProtocol()
        assert protocol._judge_pool == []
        assert protocol._disputes == {}

    def test_set_judge_pool(self):
        protocol = NegotiationProtocol()
        protocol.set_judge_pool(["j1", "j2", "j3"])
        assert len(protocol._judge_pool) == 3

    def test_judge_credits_initialized(self, negotiation):
        for judge in ["judge_a", "judge_b", "judge_c", "judge_d", "judge_e"]:
            assert negotiation._judge_credits[judge] == 0.0


@pytest.mark.asyncio
class TestCourtConvening:
    async def test_convene_creates_dispute(self, negotiation):
        dispute = await negotiation.convene(
            dispute_id="dispute-001",
            topic="Deployment blocked",
            parties=["security_agent", "performance_agent"],
        )
        assert dispute.dispute_id == "dispute-001"
        assert dispute.topic == "Deployment blocked"
        assert len(dispute.judges) == 5
        assert dispute.status == DisputeStatus.EVIDENCE_COLLECTION

    async def test_convene_excludes_parties(self, negotiation):
        dispute = await negotiation.convene(
            dispute_id="dispute-002",
            topic="Test",
            parties=["judge_a", "judge_b"],
        )
        assert "judge_a" not in dispute.judges
        assert "judge_b" not in dispute.judges

    async def test_get_active_disputes(self, negotiation):
        await negotiation.convene("d1", "Topic 1", ["p1", "p2"])
        await negotiation.convene("d2", "Topic 2", ["p3", "p4"])
        active = negotiation.get_active_disputes()
        assert len(active) == 2


@pytest.mark.asyncio
class TestEvidence:
    async def test_submit_evidence_success(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        result = await negotiation.submit_evidence(
            "d1",
            NegotiationMessage(
                source="p1",
                dispute_id="d1",
                stance=NegotiationStance.REJECT,
                evidence=[{"type": "test"}],
            ),
        )
        assert result is True

    async def test_submit_evidence_wrong_status(self, negotiation):
        dispute = await negotiation.convene("d1", "Test", ["p1", "p2"])
        dispute.status = DisputeStatus.VOTING
        result = await negotiation.submit_evidence(
            "d1",
            NegotiationMessage(source="p1", dispute_id="d1", stance=NegotiationStance.REJECT),
        )
        assert result is False

    async def test_submit_evidence_nonexistent_dispute(self, negotiation):
        result = await negotiation.submit_evidence(
            "nonexistent",
            NegotiationMessage(source="p1", dispute_id="nonexistent", stance=NegotiationStance.REJECT),
        )
        assert result is False


@pytest.mark.asyncio
class TestVoting:
    async def test_cast_vote_success(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        dispute = negotiation.get_dispute("d1")
        for judge in dispute.judges[:3]:
            result = await negotiation.cast_vote(
                "d1",
                NegotiationMessage(
                    source=judge, dispute_id="d1",
                    stance=NegotiationStance.APPROVE,
                ),
            )
            assert result is True

    async def test_cast_vote_not_a_judge(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        result = await negotiation.cast_vote(
            "d1",
            NegotiationMessage(source="outsider", dispute_id="d1", stance=NegotiationStance.APPROVE),
        )
        assert result is False

    async def test_no_double_voting(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        dispute = negotiation.get_dispute("d1")
        judge = dispute.judges[0]
        await negotiation.cast_vote(
            "d1",
            NegotiationMessage(source=judge, dispute_id="d1", stance=NegotiationStance.APPROVE),
        )
        result = await negotiation.cast_vote(
            "d1",
            NegotiationMessage(source=judge, dispute_id="d1", stance=NegotiationStance.REJECT),
        )
        assert result is False

    async def test_majority_vote_wins(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        dispute = negotiation.get_dispute("d1")
        # 3 approve, 2 reject
        for i, judge in enumerate(dispute.judges):
            stance = NegotiationStance.APPROVE if i < 3 else NegotiationStance.REJECT
            await negotiation.cast_vote(
                "d1",
                NegotiationMessage(source=judge, dispute_id="d1", stance=stance),
            )
        verdict = negotiation._disputes.get("d1")
        # After all votes, dispute should be resolved
        assert dispute.verdict is not None
        assert dispute.verdict.outcome == NegotiationStance.APPROVE

    async def test_judges_get_credits(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        dispute = negotiation.get_dispute("d1")
        for judge in dispute.judges:
            await negotiation.cast_vote(
                "d1",
                NegotiationMessage(source=judge, dispute_id="d1", stance=NegotiationStance.APPROVE),
            )
        credits = negotiation.get_judge_credits()
        for judge in dispute.judges:
            assert credits[judge] > 0.0


class TestHumanAppeal:
    @pytest.mark.asyncio
    async def test_appeal_overrides(self, negotiation):
        await negotiation.convene("d1", "Test", ["p1", "p2"])
        dispute = negotiation.get_dispute("d1")
        for judge in dispute.judges:
            await negotiation.cast_vote(
                "d1",
                NegotiationMessage(source=judge, dispute_id="d1", stance=NegotiationStance.REJECT),
            )
        verdict = await negotiation.appeal("d1", "Manual override")
        assert verdict is not None
        assert verdict.outcome == NegotiationStance.APPROVE
        assert verdict.source == "human_appeal"

    async def test_appeal_nonexistent_dispute(self, negotiation):
        verdict = await negotiation.appeal("nonexistent", "Override")
        assert verdict is None
