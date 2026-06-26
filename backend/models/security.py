"""Security models for the Adversarial War Engine (Component 5).

The adversarial arena continuously attacks generated code with:
- SQL Hunter — finds SQL injection
- XSS Hunter — finds XSS vulnerabilities
- Prompt Hunter — finds AI prompt injection
- Race Hunter — finds race conditions
- Supply Chain Hunter — checks dependency vulnerabilities
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VulnerabilitySeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityCategory(str, Enum):
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    SSRF = "ssrf"
    RCE = "remote_code_execution"
    PATH_TRAVERSAL = "path_traversal"
    IDOR = "idor"
    AUTH_BYPASS = "auth_bypass"
    RACE_CONDITION = "race_condition"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    PROMPT_INJECTION = "prompt_injection"
    SUPPLY_CHAIN = "supply_chain"
    MISCONFIGURATION = "misconfiguration"
    EXPOSED_SECRETS = "exposed_secrets"
    DOS = "denial_of_service"
    BUFFER_OVERFLOW = "buffer_overflow"
    CRYPTO_WEAKNESS = "crypto_weakness"
    BUSINESS_LOGIC = "business_logic"
    INFORMATION_DISCLOSURE = "information_disclosure"
    INSECURE_DEPENDENCY = "insecure_dependency"


class AttackType(str, Enum):
    STATIC_ANALYSIS = "static_analysis"
    DYNAMIC_ANALYSIS = "dynamic_analysis"
    FUZZING = "fuzzing"
    PENETRATION = "penetration"
    DEPENDENCY_SCAN = "dependency_scan"
    SECRET_SCAN = "secret_scan"
    AI_RED_TEAM = "ai_red_team"
    RACE_DETECTOR = "race_detector"
    LOGIC_BOMB = "logic_bomb"
    SIDE_CHANNEL = "side_channel"


class FixStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    VERIFIED = "verified"
    FAILED = "failed"
    WONT_FIX = "wont_fix"


class Vulnerability(BaseModel):
    """A security vulnerability discovered by an Adversarial Hunter agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: VulnerabilityCategory = VulnerabilityCategory.BUSINESS_LOGIC
    severity: VulnerabilitySeverity = VulnerabilitySeverity.MEDIUM
    title: str = ""
    description: str = ""
    affected_component: str = ""
    affected_code: str = ""  # file:line range
    attack_vector: str = ""
    impact: str = ""
    proof_of_concept: str = ""
    cwe_id: str = ""  # CWE identifier
    cve_id: str = ""  # CVE identifier if known
    cvss_score: float = Field(ge=0.0, le=10.0, default=5.0)
    discovered_by: str = ""  # hunter agent id
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    fix_suggestion: str = ""
    fix_status: FixStatus = FixStatus.PENDING
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def severity_score(self) -> int:
        mapping = {
            VulnerabilitySeverity.CRITICAL: 4,
            VulnerabilitySeverity.HIGH: 3,
            VulnerabilitySeverity.MEDIUM: 2,
            VulnerabilitySeverity.LOW: 1,
            VulnerabilitySeverity.INFO: 0,
        }
        return mapping.get(self.severity, 0)


class AttackResult(BaseModel):
    """The result of an adversarial attack on a code module."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attack_type: AttackType = AttackType.STATIC_ANALYSIS
    target_module: str = ""
    target_file: str = ""
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    passed: bool = True
    false_positives: int = 0
    notes: str = ""
    attacker_agent: str = ""
    project_id: str = ""

    @property
    def vulnerability_count(self) -> int:
        return len(self.vulnerabilities)

    @property
    def critical_count(self) -> int:
        return sum(
            1
            for v in self.vulnerabilities
            if v.severity == VulnerabilitySeverity.CRITICAL
        )

    @property
    def high_count(self) -> int:
        return sum(
            1
            for v in self.vulnerabilities
            if v.severity == VulnerabilitySeverity.HIGH
        )


class FixReport(BaseModel):
    """Report of a fix applied by a Developer Agent after a vulnerability."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vulnerability_id: str = ""
    fix_description: str = ""
    files_changed: list[str] = Field(default_factory=list)
    diff: str = ""
    applied_by: str = ""  # developer agent id
    applied_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: FixStatus = FixStatus.PENDING
    verified_by: str = ""  # hunter agent that re-tested
    verified_at: datetime | None = None
    regression_test_passed: bool = False
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityPolicy(BaseModel):
    """Security policy that the Adversarial War Engine enforces."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    enabled_hunters: list[AttackType] = Field(
        default_factory=lambda: list(AttackType)
    )
    min_severity_to_block: VulnerabilitySeverity = VulnerabilitySeverity.HIGH
    require_fix_before_deploy: bool = True
    auto_fix_enabled: bool = True
    re_scan_on_fix: bool = True
    max_retries: int = 3
    notify_on_vulnerability: bool = True
    tags: list[str] = Field(default_factory=list)
