"""Tests for AdversarialWarEngine — security scanning and vulnerability detection."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.components.adversarial_engine import AdversarialWarEngine, HackTool
from backend.models.security import (
    VulnerabilitySeverity,
    VulnerabilityCategory,
    AttackType,
    FixStatus,
)
from backend.services.security_scanner import SecurityScannerService


@pytest.fixture
def engine():
    """Create an AdversarialWarEngine with mocked scanner."""
    scanner = MagicMock(spec=SecurityScannerService)
    scanner.get_available_tools.return_value = ["bandit", "safety"]
    scanner.run_bandit = AsyncMock(return_value=[])
    scanner.run_safety = AsyncMock(return_value=[])
    scanner.run_secrets_scan = AsyncMock(return_value=[])
    scanner.run_sql_injection_scan = AsyncMock(return_value=[])
    engine = AdversarialWarEngine(scanner=scanner)
    return engine


class TestScanning:
    @pytest.mark.asyncio
    async def test_full_scan_no_vulnerabilities(self, engine):
        result = await engine.run_full_scan(
            target_module="test_module",
            target_file="test.py",
        )
        assert result is not None
        assert result.passed is True
        assert result.vulnerability_count >= 0

    @pytest.mark.asyncio
    async def test_full_scan_with_bandit(self, engine):
        engine._scanner.run_bandit.return_value = [
            {
                "tool": "bandit",
                "type": "B101",
                "title": "Test finding",
                "severity": "HIGH",
                "confidence": "HIGH",
                "description": "Test vulnerability",
                "file_path": "test.py",
                "line_number": 42,
                "fix_suggestion": "Fix it",
            }
        ]
        result = await engine.run_full_scan(
            target_module="test_module",
            target_file="test.py",
        )
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_xss_pattern_scan(self, engine):
        findings = engine._scan_xss_patterns("test_module", "")
        assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_race_condition_scan(self, engine):
        findings = engine._scan_race_conditions("test_module", "")
        assert isinstance(findings, list)

    @pytest.mark.asyncio
    async def test_prompt_injection_scan(self, engine):
        findings = engine._scan_prompt_injection("test_module", "")
        assert isinstance(findings, list)


class TestPatternMatching:
    def test_race_condition_patterns_loaded(self, engine):
        assert len(engine._race_condition_patterns) >= 3

    def test_xss_patterns_loaded(self, engine):
        assert len(engine._xss_patterns) >= 5

    def test_prompt_injection_loaded(self, engine):
        assert len(engine._prompt_injection_patterns) >= 3

    def test_get_source_lines_nonexistent(self, engine):
        lines = engine._get_source_lines("/nonexistent/file.py")
        assert lines == []


class TestVulnerabilityManagement:
    def test_get_vulnerability_nonexistent(self, engine):
        assert engine.get_vulnerability("nonexistent") is None

    def test_get_open_vulnerabilities_empty(self, engine):
        assert engine.get_open_vulnerabilities() == []

    def test_get_scan_results_empty(self, engine):
        assert engine.get_scan_results() == []

    def test_stats_basic(self, engine):
        stats = engine.get_stats()
        assert stats["total_scans"] == 0
        assert stats["total_vulnerabilities"] == 0


class TestFixManagement:
    @pytest.mark.asyncio
    async def test_apply_fix_nonexistent(self, engine):
        fix = await engine.apply_fix("nonexistent")
        assert fix is None

    @pytest.mark.asyncio
    async def test_fix_all_empty(self, engine):
        fixes = await engine.fix_all_vulnerabilities()
        assert fixes == []


class TestPolicyManagement:
    def test_update_policy(self, engine):
        engine.update_policy(auto_fix_enabled=False)
        assert engine._policy.auto_fix_enabled is False

    def test_get_policy(self, engine):
        policy = engine.get_policy()
        assert policy is not None
