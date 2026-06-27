"""Tests for FormalVerificationEngine — mathematical correctness proofs."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.components.formal_verification import FormalVerificationEngine, DOMAIN_PROPERTIES
from backend.models.verification import VerificationDomain, VerificationStatus, ProofSystem
from backend.services.z3_verifier import Z3VerifierService


@pytest.fixture
def engine():
    z3 = MagicMock(spec=Z3VerifierService)
    z3.is_available = False
    return FormalVerificationEngine(z3_service=z3)


class TestDomainProperties:
    def test_auth_domain_has_properties(self):
        props = DOMAIN_PROPERTIES.get(VerificationDomain.AUTHENTICATION)
        assert props is not None
        assert len(props) > 0
        names = [p["name"] for p in props]
        assert "Login Completeness" in names
        assert "No False Authentication" in names
        assert "Session Management" in names

    def test_payment_domain_has_properties(self):
        props = DOMAIN_PROPERTIES.get(VerificationDomain.PAYMENT)
        assert props is not None
        assert len(props) > 0
        names = [p["name"] for p in props]
        assert "Money Conservation" in names
        assert "No Double Spend" in names

    def test_authorization_domain_has_properties(self):
        props = DOMAIN_PROPERTIES.get(VerificationDomain.AUTHORIZATION)
        assert props is not None
        names = [p["name"] for p in props]
        assert "Role Hierarchy" in names
        assert "No Privilege Escalation" in names

    def test_encryption_domain(self):
        props = DOMAIN_PROPERTIES.get(VerificationDomain.ENCRYPTION)
        assert props is not None
        assert len(props) > 0

    def test_concurrency_domain(self):
        props = DOMAIN_PROPERTIES.get(VerificationDomain.CONCURRENCY)
        assert props is not None
        assert len(props) > 0


@pytest.mark.asyncio
class TestVerificationRuns:
    async def test_verify_module_auth(self, engine):
        run = await engine.verify_module(
            module_name="auth_module",
            domain=VerificationDomain.AUTHENTICATION,
        )
        assert run is not None
        assert run.module_name == "auth_module"
        assert run.domain == VerificationDomain.AUTHENTICATION
        assert run.status in (VerificationStatus.PASSED, VerificationStatus.FAILED, VerificationStatus.INCONCLUSIVE)
        assert run.total_properties > 0
        assert run.passed_count + run.failed_count + run.inconclusive_count == run.total_properties

    async def test_verify_module_payment(self, engine):
        run = await engine.verify_module(
            module_name="payment_module",
            domain=VerificationDomain.PAYMENT,
        )
        assert run is not None
        assert run.total_properties >= 2

    async def test_verify_module_with_project_id(self, engine):
        run = await engine.verify_module(
            module_name="test_module",
            domain=VerificationDomain.AUTHENTICATION,
            project_id="proj-001",
        )
        assert run.project_id == "proj-001"


class TestEngineStats:
    def test_stats_initial(self, engine):
        stats = engine.get_stats()
        assert stats["total_runs"] == 0
        assert stats["total_proofs"] == 0
        assert stats["passed"] == 0
        assert stats["z3_available"] is False

    def test_get_run_nonexistent(self, engine):
        assert engine.get_run("nonexistent") is None

    def test_get_runs_for_module_empty(self, engine):
        assert engine.get_runs_for_module("nonexistent") == []


class TestProofGeneration:
    def test_generate_proof_script_z3(self, engine):
        from backend.models.verification import VerificationProperty, PropertyType
        prop = VerificationProperty(
            name="Test Property",
            description="Test",
            property_type=PropertyType.SAFETY,
            formal_specification="true",
        )
        script = engine._generate_proof_script(ProofSystem.Z3, prop)
        assert script is not None
        assert "Z3 proof" in script or "check-sat" in script

    def test_generate_proof_script_tla(self, engine):
        from backend.models.verification import VerificationProperty, PropertyType
        prop = VerificationProperty(
            name="Test Property",
            description="Test",
            property_type=PropertyType.LIVENESS,
            formal_specification="Spec => []Property",
        )
        script = engine._generate_proof_script(ProofSystem.TLA_PLUS, prop)
        assert "TLA+ proof" in script or "THEOREM" in script
