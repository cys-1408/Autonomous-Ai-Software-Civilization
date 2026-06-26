"""Adversarial War Engine (Component 5).

Continuously attacks generated code to find and fix vulnerabilities.

Hunter Agents:
1. SQL Hunter — finds SQL injection vulnerabilities
2. XSS Hunter — finds cross-site scripting vulnerabilities
3. Prompt Hunter — finds AI prompt injection vulnerabilities
4. Race Hunter — finds race conditions and concurrency issues
5. Supply Chain Hunter — checks dependency vulnerabilities

Workflow:
Code Generated → Hunter Agents Attack → Vulnerability Found → Developer Agents Fix
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    DashboardUpdate,
)
from backend.models.security import (
    Vulnerability,
    VulnerabilitySeverity,
    VulnerabilityCategory,
    AttackResult,
    AttackType,
    FixReport,
    FixStatus,
    SecurityPolicy,
)

logger = structlog.get_logger(__name__)


class HackTool:
    """Represents a security testing tool available to hunter agents."""

    def __init__(
        self,
        name: str,
        attack_type: AttackType,
        description: str,
        effectiveness: float = 0.7,
    ):
        self.name = name
        self.attack_type = attack_type
        self.description = description
        self.effectiveness = effectiveness


class AdversarialWarEngine:
    """The adversarial arena that continuously attacks generated code.

    Hunter agents work in parallel to find vulnerabilities across
    all attack surfaces. When found, developer agents are notified
    to apply fixes. The engine tracks all vulnerabilities and fixes.
    """

    def __init__(self, hub: CommunicationHub | None = None):
        self.hub = hub
        self._policy = SecurityPolicy()
        self._attack_results: list[AttackResult] = []
        self._vulnerabilities: list[Vulnerability] = []
        self._fixes: list[FixReport] = []
        self._running = False
        self._hunter_tasks: list[asyncio.Task] = []

        # Available hacking tools
        self._tools: list[HackTool] = [
            HackTool("SQLMap", AttackType.STATIC_ANALYSIS, "SQL injection scanner", 0.85),
            HackTool("XSStrike", AttackType.STATIC_ANALYSIS, "XSS vulnerability scanner", 0.80),
            HackTool("BurpSuite", AttackType.DYNAMIC_ANALYSIS, "Web application security scanner", 0.75),
            HackTool("AFL++", AttackType.FUZZING, "American Fuzzy Lop fuzzer", 0.65),
            HackTool("Trivy", AttackType.DEPENDENCY_SCAN, "Container and dependency scanner", 0.90),
            HackTool("TruffleHog", AttackType.SECRET_SCAN, "Secret scanner for git repos", 0.85),
            HackTool("Gitleaks", AttackType.SECRET_SCAN, "Git repo secret scanner", 0.80),
            HackTool("RaceDetector", AttackType.RACE_DETECTOR, "Go race condition detector", 0.70),
            HackTool("Semgrep", AttackType.STATIC_ANALYSIS, "Static analysis rule engine", 0.75),
            HackTool("Bandit", AttackType.STATIC_ANALYSIS, "Python security linter", 0.80),
        ]

    # ── Policy Management ───────────────────────────────────────────────

    def update_policy(self, **kwargs) -> None:
        """Update the security policy."""
        for key, value in kwargs.items():
            if hasattr(self._policy, key):
                setattr(self._policy, key, value)

    def get_policy(self) -> SecurityPolicy:
        return self._policy

    # ── Attack Execution ────────────────────────────────────────────────

    async def run_full_scan(
        self,
        target_module: str = "",
        target_file: str = "",
        project_id: str = "",
    ) -> AttackResult:
        """Run all enabled hunter agents against a target.

        Returns a comprehensive AttackResult with all discovered
        vulnerabilities.
        """
        result = AttackResult(
            attack_type=AttackType.PENETRATION,
            target_module=target_module,
            target_file=target_file,
            attacker_agent="adversarial_engine",
            project_id=project_id,
        )

        all_vulns: list[Vulnerability] = []

        # Run each enabled hunter
        for tool in self._tools:
            if tool.attack_type not in self._policy.enabled_hunters:
                continue

            vulns = await self._run_hunter(tool, target_module, target_file)
            all_vulns.extend(vulns)

            if self.hub:
                await self.hub.push_dashboard_update(DashboardUpdate(
                    update_type="alert",
                    data={
                        "alert_type": "adversarial_scan",
                        "tool": tool.name,
                        "vulnerabilities_found": len(vulns),
                        "target": target_module or target_file,
                    },
                    visual_hint="red" if vulns else "green",
                    source="adversarial_engine",
                ))

        result.vulnerabilities = all_vulns
        result.passed = len([v for v in all_vulns if v.severity_score >= 3]) == 0
        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        self._attack_results.append(result)
        self._vulnerabilities.extend(all_vulns)

        # Notify the civilization
        if self.hub and all_vulns:
            critical = result.critical_count
            high = result.high_count
            await self.hub.publish_event(
                EventType.VULNERABILITY_FOUND,
                payload={
                    "target": target_module or target_file,
                    "total": len(all_vulns),
                    "critical": critical,
                    "high": high,
                    "result_id": result.id,
                },
                source="adversarial_engine",
            )

        logger.info(
            "adversarial.scan_completed",
            target=target_module or target_file,
            vulnerabilities=len(all_vulns),
            passed=result.passed,
        )

        return result

    async def _run_hunter(
        self,
        tool: HackTool,
        target_module: str,
        target_file: str,
    ) -> list[Vulnerability]:
        """Simulate a hunter agent running a security tool.

        In a full implementation, this would actually run the tool
        against the target. Here we produce realistic but simulated
        results for demonstration purposes.
        """
        vulnerabilities: list[Vulnerability] = []

        # Simulate finding vulnerabilities based on tool effectiveness
        if random.random() < tool.effectiveness:
            vuln_type = self._map_attack_to_vulnerability(tool.attack_type)
            severity = random.choice(list(VulnerabilitySeverity))
            vuln = Vulnerability(
                category=vuln_type,
                severity=severity,
                title=f"{tool.name} found potential {vuln_type.value}",
                description=f"Detected by {tool.name}: Potential {vuln_type.value.replace('_', ' ')} in {target_file or target_module}",
                affected_component=target_module,
                affected_code=f"{target_file}:{random.randint(10, 200)}",
                discovered_by=f"hunter_{tool.name.lower()}",
                cvss_score=random.uniform(3.0, 9.5),
                fix_suggestion=self._generate_fix_suggestion(vuln_type),
                fix_status=FixStatus.PENDING,
            )
            vulnerabilities.append(vuln)

        return vulnerabilities

    def _map_attack_to_vulnerability(self, attack_type: AttackType) -> VulnerabilityCategory:
        """Map an attack type to its primary vulnerability category."""
        mapping = {
            AttackType.STATIC_ANALYSIS: VulnerabilityCategory.SQL_INJECTION,
            AttackType.DYNAMIC_ANALYSIS: VulnerabilityCategory.XSS,
            AttackType.FUZZING: VulnerabilityCategory.BUFFER_OVERFLOW,
            AttackType.DEPENDENCY_SCAN: VulnerabilityCategory.INSECURE_DEPENDENCY,
            AttackType.SECRET_SCAN: VulnerabilityCategory.EXPOSED_SECRETS,
            AttackType.RACE_DETECTOR: VulnerabilityCategory.RACE_CONDITION,
            AttackType.AI_RED_TEAM: VulnerabilityCategory.PROMPT_INJECTION,
        }
        return mapping.get(attack_type, VulnerabilityCategory.BUSINESS_LOGIC)

    def _generate_fix_suggestion(self, category: VulnerabilityCategory) -> str:
        """Generate a fix suggestion for a vulnerability category."""
        fixes = {
            VulnerabilityCategory.SQL_INJECTION: "Use parameterized queries with prepared statements. Never concatenate user input into SQL strings.",
            VulnerabilityCategory.XSS: "Sanitize all user input. Use Content-Security-Policy headers. Escape HTML output with context-aware encoding.",
            VulnerabilityCategory.CSRF: "Implement CSRF tokens for all state-changing requests. Use SameSite cookie attribute.",
            VulnerabilityCategory.SSRF: "Validate and whitelist allowed URLs. Disable URL schema other than HTTP/HTTPS.",
            VulnerabilityCategory.RCE: "Never execute user input as code. Use safe APIs and sandbox execution environments.",
            VulnerabilityCategory.PATH_TRAVERSAL: "Validate file paths. Use allowlisted directories. Normalize paths before access.",
            VulnerabilityCategory.IDOR: "Implement proper authorization checks. Use indirect object references.",
            VulnerabilityCategory.RACE_CONDITION: "Use atomic operations and proper locking. Implement optimistic concurrency control.",
            VulnerabilityCategory.EXPOSED_SECRETS: "Rotate exposed credentials immediately. Use secrets manager. Never commit secrets to git.",
            VulnerabilityCategory.INSECURE_DEPENDENCY: "Update vulnerable packages. Use dependency scanning in CI/CD pipeline.",
            VulnerabilityCategory.PROMPT_INJECTION: "Implement input validation. Use role-based prompt separation. Sanitize user input before LLM processing.",
            VulnerabilityCategory.BUSINESS_LOGIC: "Review and validate business logic flow. Implement rate limiting and anomaly detection.",
        }
        return fixes.get(category, "Review the affected code and apply security best practices.")

    # ── Fix Management ──────────────────────────────────────────────────

    async def apply_fix(
        self,
        vulnerability_id: str,
        fix_description: str,
        applied_by: str = "developer_agent",
    ) -> FixReport | None:
        """Apply a fix for a vulnerability and verify it."""
        vuln = self.get_vulnerability(vulnerability_id)
        if not vuln:
            return None

        fix = FixReport(
            vulnerability_id=vulnerability_id,
            fix_description=fix_description or vuln.fix_suggestion,
            files_changed=[vuln.affected_code],
            applied_by=applied_by,
            status=FixStatus.APPLIED,
        )

        vuln.fix_status = FixStatus.APPLIED
        self._fixes.append(fix)

        if self.hub:
            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="fix_applied",
                data={
                    "vulnerability_id": vulnerability_id,
                    "fix_id": fix.id,
                    "applied_by": applied_by,
                },
                visual_hint="green",
                source="adversarial_engine",
            ))

        # Verify the fix (re-scan)
        re_scan = await self.run_full_scan(
            target_module=vuln.affected_component,
            target_file=vuln.affected_code.split(":")[0],
        )

        fix.status = FixStatus.VERIFIED if re_scan.passed else FixStatus.FAILED
        fix.verified_at = datetime.now(timezone.utc)
        fix.verified_by = "adversarial_engine"

        if re_scan.passed:
            vuln.fix_status = FixStatus.VERIFIED
        else:
            vuln.fix_status = FixStatus.FAILED

        return fix

    async def fix_all_vulnerabilities(
        self,
        max_retries: int = 3,
    ) -> list[FixReport]:
        """Attempt to fix all open vulnerabilities."""
        pending = [
            v for v in self._vulnerabilities
            if v.fix_status in (FixStatus.PENDING, FixStatus.FAILED)
        ]
        fixes = []

        for attempt in range(max_retries):
            if not pending:
                break

            for vuln in pending[:]:
                fix = await self.apply_fix(
                    vuln.id,
                    vuln.fix_suggestion,
                    applied_by=f"auto_fix_attempt_{attempt + 1}",
                )
                if fix and fix.status == FixStatus.VERIFIED:
                    fixes.append(fix)
                    pending.remove(vuln)

        return fixes

    # ── Queries ─────────────────────────────────────────────────────────

    def get_vulnerability(self, vuln_id: str) -> Vulnerability | None:
        for v in self._vulnerabilities:
            if v.id == vuln_id:
                return v
        return None

    def get_open_vulnerabilities(
        self,
        min_severity: VulnerabilitySeverity = VulnerabilitySeverity.LOW,
    ) -> list[Vulnerability]:
        severity_order = {
            VulnerabilitySeverity.CRITICAL: 4,
            VulnerabilitySeverity.HIGH: 3,
            VulnerabilitySeverity.MEDIUM: 2,
            VulnerabilitySeverity.LOW: 1,
            VulnerabilitySeverity.INFO: 0,
        }
        min_score = severity_order.get(min_severity, 0)
        return [
            v for v in self._vulnerabilities
            if v.fix_status in (FixStatus.PENDING, FixStatus.FAILED)
            and severity_order.get(v.severity, 0) >= min_score
        ]

    def get_scan_results(self, limit: int = 10) -> list[AttackResult]:
        return self._attack_results[-limit:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_scans": len(self._attack_results),
            "total_vulnerabilities": len(self._vulnerabilities),
            "open_vulnerabilities": len(self.get_open_vulnerabilities()),
            "verified_fixes": sum(
                1 for f in self._fixes if f.status == FixStatus.VERIFIED
            ),
            "failed_fixes": sum(
                1 for f in self._fixes if f.status == FixStatus.FAILED
            ),
            "critical_count": sum(
                1 for v in self._vulnerabilities
                if v.severity == VulnerabilitySeverity.CRITICAL
            ),
            "high_count": sum(
                1 for v in self._vulnerabilities
                if v.severity == VulnerabilitySeverity.HIGH
            ),
        }
