"""Goal Interpreter (Component 1).

Converts free-form user requests into machine-understandable project
specifications.

Example:
    Input: "Build a Hospital Management System"
    Output: Structured ProjectSpec with detected modules,
            requirements, constraints, and technology recommendations.

The interpreter uses:
- NLP pattern matching for module detection
- Heuristic analysis for constraint extraction
- Tech stack recommendation engine
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from backend.communication.hub import CommunicationHub
from backend.communication.message_types import (
    EventType,
    TaskDefinition,
    TaskPriority,
    DashboardUpdate,
)
from backend.models.project import (
    ProjectGoal,
    ProjectSpec,
    ProjectStatus,
    Module,
    Constraint,
    TechStack,
)

logger = structlog.get_logger(__name__)

# Domain knowledge: common project types and their associated modules
PROJECT_MODULES: dict[str, list[dict[str, Any]]] = {
    "hospital": [
        {"name": "Patient Management", "entities": ["Patient", "MedicalRecord"], "priority": 10},
        {"name": "Doctor Management", "entities": ["Doctor", "Schedule"], "priority": 9},
        {"name": "Appointment Scheduling", "entities": ["Appointment", "Availability"], "priority": 9},
        {"name": "Billing & Invoicing", "entities": ["Invoice", "Payment"], "priority": 8},
        {"name": "Pharmacy Management", "entities": ["Medicine", "Prescription"], "priority": 7},
        {"name": "Lab Management", "entities": ["LabTest", "Result"], "priority": 7},
        {"name": "Authentication & RBAC", "entities": ["User", "Role", "Permission"], "priority": 10},
        {"name": "Reporting & Analytics", "entities": ["Report", "Analytics"], "priority": 5},
    ],
    "ecommerce": [
        {"name": "Product Catalog", "entities": ["Product", "Category", "Inventory"], "priority": 10},
        {"name": "Shopping Cart", "entities": ["Cart", "CartItem"], "priority": 9},
        {"name": "Order Management", "entities": ["Order", "OrderItem", "Shipment"], "priority": 9},
        {"name": "Payment Processing", "entities": ["Payment", "Refund"], "priority": 9},
        {"name": "User Accounts", "entities": ["User", "Address", "Wishlist"], "priority": 8},
        {"name": "Reviews & Ratings", "entities": ["Review", "Rating"], "priority": 6},
        {"name": "Search & Discovery", "entities": ["SearchIndex"], "priority": 7},
        {"name": "Admin Dashboard", "entities": ["Dashboard"], "priority": 6},
    ],
    "saas": [
        {"name": "Tenant Management", "entities": ["Tenant", "Subscription"], "priority": 10},
        {"name": "User Management", "entities": ["User", "Team", "Invitation"], "priority": 9},
        {"name": "Billing & Subscriptions", "entities": ["Plan", "Invoice", "PaymentMethod"], "priority": 9},
        {"name": "Feature Flags", "entities": ["Feature", "Flag"], "priority": 7},
        {"name": "API Gateway", "entities": ["APIKey", "RateLimit"], "priority": 8},
        {"name": "Analytics & Usage", "entities": ["Event", "Metric"], "priority": 6},
        {"name": "Notifications", "entities": ["Notification", "Template"], "priority": 7},
        {"name": "Audit Logging", "entities": ["AuditLog"], "priority": 6},
    ],
    "social": [
        {"name": "User Profiles", "entities": ["Profile", "Settings"], "priority": 10},
        {"name": "Content Feed", "entities": ["Post", "Comment", "Reaction"], "priority": 9},
        {"name": "Friend/Follow System", "entities": ["Connection", "Follow"], "priority": 8},
        {"name": "Messaging", "entities": ["Message", "Conversation"], "priority": 8},
        {"name": "Notifications", "entities": ["Notification"], "priority": 7},
        {"name": "Content Moderation", "entities": ["Report", "ModerationAction"], "priority": 7},
        {"name": "Search", "entities": ["SearchIndex"], "priority": 6},
    ],
    "fintech": [
        {"name": "Accounts & Ledgers", "entities": ["Account", "LedgerEntry"], "priority": 10},
        {"name": "Transactions", "entities": ["Transaction", "Transfer"], "priority": 10},
        {"name": "User Verification (KYC)", "entities": ["KYC", "Document"], "priority": 9},
        {"name": "Authentication & MFA", "entities": ["MFADevice", "Session"], "priority": 9},
        {"name": "Compliance & Reporting", "entities": ["ComplianceReport"], "priority": 9},
        {"name": "Notifications & Alerts", "entities": ["Alert"], "priority": 6},
        {"name": "Dashboard & Analytics", "entities": ["Dashboard"], "priority": 6},
    ],
}

SECURITY_KEYWORDS = [
    r"\b(hipaa|gdpr|pci|sox|pii|encryption|audit)\b",
]
SCALABILITY_KEYWORDS = [
    r"\b(million|high.?traffic|scale|load|concurrent|caching|cdn)\b",
]
PERFORMANCE_KEYWORDS = [
    r"\b(performance|latency|realtime|fast|quick|millisecond)\b",
]


class GoalInterpreter:
    """Interprets user goals into structured project specifications.

    This is the entry point for the entire civilization — it converts
    "Build a Hospital Management System" into a machine-readable spec
    that drives all downstream agents.
    """

    def __init__(self, hub: CommunicationHub | None = None):
        self.hub = hub

    async def interpret(
        self,
        raw_input: str,
        user_id: str = "anonymous",
    ) -> ProjectSpec:
        """Convert a natural language request into a ProjectSpec.

        Args:
            raw_input: The user's request (e.g., "Build a Hospital Management System")
            user_id: Optional user identifier

        Returns:
            A structured ProjectSpec ready for downstream processing.
        """
        goal = ProjectGoal(raw_input=raw_input, user_id=user_id)

        logger.info(
            "interpreter.parsing_goal",
            raw_input=raw_input[:100],
        )

        # Detect project type
        project_type = self._detect_project_type(raw_input)

        # Extract module definitions from domain knowledge
        modules = self._build_modules(project_type, raw_input)

        # Detect constraints
        constraints = self._detect_constraints(raw_input)

        # Recommend tech stack
        tech_stack = self._recommend_tech_stack(project_type, constraints)

        # Extract security and scalability requirements
        security_reqs = self._extract_security_requirements(raw_input)
        scalability_reqs = self._extract_scalability_requirements(raw_input)

        spec = ProjectSpec(
            goal_id=goal.id,
            project_type=project_type,
            title=self._generate_title(raw_input, project_type),
            description=raw_input,
            modules=modules,
            constraints=constraints,
            tech_stack=tech_stack,
            status=ProjectStatus.INTERPRETED,
        )

        if security_reqs:
            spec.security_requirements = security_reqs
        if scalability_reqs:
            spec.scalability_requirements = scalability_reqs

        # Notify the civilization
        if self.hub:
            await self.hub.publish_event(
                EventType.PROJECT_CREATED,
                payload={
                    "project_id": spec.id,
                    "project_type": project_type,
                    "module_count": len(modules),
                    "constraint_count": len(constraints),
                    "estimated_complexity": spec.estimated_complexity,
                },
                source="goal_interpreter",
            )

            await self.hub.push_dashboard_update(DashboardUpdate(
                update_type="project_created",
                data={
                    "project_id": spec.id,
                    "title": spec.title,
                    "type": project_type,
                    "modules": [m.name for m in modules],
                },
                visual_hint="blue",
                source="goal_interpreter",
            ))

        logger.info(
            "interpreter.goal_parsed",
            project_type=project_type,
            modules=spec.module_count,
            complexity=spec.estimated_complexity,
        )

        return spec

    def _detect_project_type(self, raw_input: str) -> str:
        """Detect the domain/project type from the text."""
        text_lower = raw_input.lower()

        # Direct type keywords
        type_patterns = {
            "hospital": r"\b(hospital|medical|clinic|healthcare|patient|doctor)\b",
            "ecommerce": r"\b(ecommerce|shop|store|retail|marketplace|product|catalog)\b",
            "saas": r"\b(saas|subscription|tenant|multi.?tenant|billing\s+platform)\b",
            "social": r"\b(social|feed|profile|messaging|chat|forum|community)\b",
            "fintech": r"\b(fintech|banking|payment|wallet|finance|trading|crypto)\b",
            "crm": r"\b(crm|customer|lead|contact|pipeline|sales)\b",
            "erp": r"\b(erp|enterprise|resource|planning|manufacturing)\b",
            "blog": r"\b(blog|cms|content|article|publishing|writer)\b",
            "game": r"\b(game|gaming|multiplayer|leaderboard|matchmaking)\b",
        }

        best_type = "general"
        best_score = 0

        for ptype, pattern in type_patterns.items():
            matches = re.findall(pattern, text_lower)
            score = len(matches)
            if score > best_score:
                best_score = score
                best_type = ptype

        return best_type

    def _build_modules(
        self,
        project_type: str,
        raw_input: str,
    ) -> list[Module]:
        """Build module list from domain knowledge and user input."""
        base_modules = PROJECT_MODULES.get(project_type, [])

        # If user mentioned specific features, try to extract them
        user_mentioned = self._extract_user_mentions(raw_input)
        modules: list[Module] = []
        added_names: set[str] = set()

        # Add base modules
        for mod_data in base_modules:
            module = Module(
                name=mod_data["name"],
                entities=mod_data["entities"],
                priority=mod_data["priority"],
            )
            modules.append(module)
            added_names.add(mod_data["name"].lower())

        # Add user-mentioned modules that aren't in base
        for mention in user_mentioned:
            if mention.lower() not in added_names:
                modules.append(
                    Module(
                        name=mention,
                        entities=[mention.replace(" ", "")],
                        priority=5,
                    )
                )

        if not modules:
            modules.append(
                Module(
                    name="Core",
                    entities=["Entity"],
                    priority=5,
                )
            )

        return modules

    def _detect_constraints(self, raw_input: str) -> list[Constraint]:
        """Extract constraints like security, scalability, performance."""
        text_lower = raw_input.lower()
        constraints: list[Constraint] = []

        constraint_patterns = [
            ("security", r"\b(secure|security|safe|protected|encrypt)\b", "must"),
            ("scalability", r"\b(scale|scalable|million|growth)\b", "should"),
            ("performance", r"\b(fast|performance|latency|realtime)\b", "should"),
            ("mobile", r"\b(mobile|ios|android|responsive)\b", "should"),
            ("cloud", r"\b(cloud|aws|azure|gcp|kubernetes)\b", "could"),
            ("offline", r"\b(offline|off.?line|disconnected)\b", "could"),
            ("multi-language", r"\b(i18n|localization|multi.?language|translation)\b", "could"),
            ("compliance", r"\b(hipaa|gdpr|pci|sox|compliance|regulatory)\b", "must"),
            ("high-availability", r"\b(ha|high.?availability|fault.?tolerant|redundant)\b", "must"),
            ("analytics", r"\b(analytics|dashboard|report|visualization)\b", "could"),
        ]

        for cat, pattern, priority in constraint_patterns:
            if re.search(pattern, text_lower):
                constraints.append(
                    Constraint(
                        category=cat,
                        description=f"System must support {cat.replace('_', ' ')}",
                        priority=priority,
                    )
                )

        return constraints

    def _recommend_tech_stack(
        self,
        project_type: str,
        constraints: list[Constraint],
    ) -> TechStack:
        """Recommend a technology stack based on project type and constraints."""
        is_real_time = any(c.category == "performance" for c in constraints)
        needs_auth = any(c.category == "security" for c in constraints)
        needs_mobile = any(c.category == "mobile" for c in constraints)

        stack = TechStack()

        if project_type in ("fintech", "healthcare"):
            stack.language = "python"
            stack.framework = "fastapi"
            stack.database = "postgresql"
            stack.testing = "pytest"
        elif project_type in ("social", "realtime"):
            stack.language = "typescript"
            stack.framework = "nestjs"
            stack.database = "postgresql"
            stack.cache = "redis"
            if is_real_time:
                stack.additional["websocket"] = "socket.io"
        elif project_type == "game":
            stack.language = "go"
            stack.framework = "fiber"
            stack.database = "postgresql"
            stack.cache = "redis"

        if needs_auth:
            stack.additional["auth"] = "auth0"

        return stack

    def _extract_security_requirements(self, raw_input: str) -> list[str]:
        """Extract security requirements from the input."""
        text_lower = raw_input.lower()
        reqs = []
        for pattern in SECURITY_KEYWORDS:
            if re.search(pattern, text_lower):
                keyword = re.search(pattern, text_lower)
                if keyword:
                    reqs.append(f"Compliance with {keyword.group(0).upper()} required")
        if not reqs:
            reqs.append("Standard security best practices (authentication, authorization, encryption)")
        return reqs

    def _extract_scalability_requirements(self, raw_input: str) -> list[str]:
        """Extract scalability requirements."""
        text_lower = raw_input.lower()
        reqs = []
        for pattern in SCALABILITY_KEYWORDS:
            if re.search(pattern, text_lower):
                keyword = re.search(pattern, text_lower)
                if keyword:
                    reqs.append(f"Scalable for {keyword.group(0)}")
        if not reqs:
            reqs.append("Basic scalability (horizontal scaling support)")
        return reqs

    def _extract_user_mentions(self, raw_input: str) -> list[str]:
        """Extract specific user-mentioned features."""
        text_lower = raw_input.lower()
        mentions = []

        # Look for capitalized phrases that might be feature names
        phrases = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", raw_input)
        for phrase in phrases:
            if phrase.lower() not in ("a", "an", "the", "system", "build", "create"):
                mentions.append(phrase)

        return mentions[:5]  # Limit to 5

    @staticmethod
    def _generate_title(raw_input: str, project_type: str) -> str:
        """Generate a clean title from the raw input."""
        # Try to extract a title from the input
        title_match = re.search(
            r"(?:build|create|make|develop)\s+(?:a|an|the)?\s*(.+)",
            raw_input,
            re.IGNORECASE,
        )
        if title_match:
            title = title_match.group(1).strip().rstrip(".!")
            if title:
                return title

        # Fallback to project type name
        type_names = {
            "hospital": "Hospital Management System",
            "ecommerce": "E-Commerce Platform",
            "saas": "SaaS Application",
            "social": "Social Network",
            "fintech": "FinTech Platform",
            "general": "Software Application",
        }
        return type_names.get(project_type, "Software Application")
