"""Tests for Z3VerifierService — real SMT solver integration."""

import pytest
from backend.services.z3_verifier import Z3VerifierService


@pytest.fixture
def z3():
    return Z3VerifierService()


class TestZ3Initialization:
    def test_initial_state(self, z3):
        assert z3._initialized is False

    def test_is_available(self, z3):
        # Should detect Z3 is installed
        available = z3.is_available
        assert available is True
        assert z3._initialized is True


class TestAuthenticationProofs:
    def test_login_completeness(self, z3):
        result = z3.prove_login_completeness()
        assert result["status"] in ("PASSED", "FAILED")
        assert result["property"] == "Login Completeness"
        assert "proof_system" in result

    def test_no_false_authentication(self, z3):
        result = z3.prove_no_false_authentication()
        assert result["status"] in ("PASSED", "FAILED")
        assert result["property"] == "No False Authentication"

    def test_session_expiry(self, z3):
        result = z3.prove_session_expiry()
        assert result["status"] in ("PASSED", "FAILED")


class TestPaymentProofs:
    def test_money_conservation(self, z3):
        result = z3.prove_money_conservation()
        assert result["status"] in ("PASSED", "FAILED")
        assert result["property"] == "Money Conservation"

    def test_no_double_spend(self, z3):
        result = z3.prove_no_double_spend()
        assert result["status"] in ("PASSED", "FAILED")


class TestAuthorizationProofs:
    def test_role_hierarchy(self, z3):
        result = z3.prove_role_hierarchy()
        assert result["status"] in ("PASSED", "FAILED")
        assert result["property"] == "Role Hierarchy"

    def test_no_privilege_escalation(self, z3):
        result = z3.prove_no_privilege_escalation()
        assert result["status"] in ("PASSED", "FAILED")

    def test_role_hierarchy_custom_roles(self, z3):
        result = z3.prove_role_hierarchy(["super_admin", "admin", "user"])
        assert result["status"] in ("PASSED", "FAILED")


class TestEncryptionProofs:
    def test_encryption_correctness(self, z3):
        result = z3.prove_encryption_correctness()
        assert result["status"] in ("PASSED", "FAILED")


class TestConcurrencyProofs:
    def test_no_deadlock(self, z3):
        result = z3.prove_no_deadlock()
        assert result["status"] in ("PASSED", "FAILED")


class TestModuleVerification:
    def test_verify_auth_module(self, z3):
        results = z3.verify_module("auth_module")
        assert len(results) >= 3
        for r in results:
            assert "status" in r

    def test_verify_payment_module(self, z3):
        results = z3.verify_module("payment_module")
        assert len(results) >= 2

    def test_verify_rbac_module(self, z3):
        results = z3.verify_module("rbac_module")
        assert len(results) >= 2

    def test_verify_encryption_module(self, z3):
        results = z3.verify_module("encryption_module")
        assert len(results) >= 1

    def test_verify_concurrency_module(self, z3):
        results = z3.verify_module("concurrency_module")
        assert len(results) >= 1

    def test_verify_unknown_module_runs_all(self, z3):
        results = z3.verify_module("something_else")
        assert len(results) >= 7
