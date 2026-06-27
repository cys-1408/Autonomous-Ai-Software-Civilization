"""LLM Service — Real AI Integration Layer.

Supports OpenAI and Anthropic/Claude via LangChain.
Automatically falls back to rule-based heuristics if no API key is configured.

Usage:
    llm = LLMService()
    result = await llm.interpret_goal("Build a Hospital Management System")
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import structlog
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger(__name__)


class LLMService:
    """LLM integration using LangChain with OpenAI/Anthropic.

    Configure via environment variables:
      LLM_PROVIDER=openai|anthropic
      OPENAI_API_KEY=sk-...
      ANTHROPIC_API_KEY=sk-ant-...
      LLM_MODEL=gpt-4o|claude-sonnet-4-20250514  (optional, defaults to best model)
    """

    def __init__(self):
        self._provider: str | None = None
        self._model: str | None = None
        self._llm: Any = None
        self._available = False
        self._init_error: str | None = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the LLM connection. Returns True if successful, False if fallback needed."""
        if self._initialized:
            return self._available

        self._initialized = True
        provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        model = os.getenv("LLM_MODEL", "").strip()

        if not provider:
            openai_key = os.getenv("OPENAI_API_KEY", "").strip()
            anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

            if openai_key:
                provider = "openai"
            elif anthropic_key:
                provider = "anthropic"

        if not provider:
            self._init_error = (
                "No LLM provider configured. Set LLM_PROVIDER, OPENAI_API_KEY, "
                "or ANTHROPIC_API_KEY in .env"
            )
            logger.warning("llm_service.not_configured")
            return False

        try:
            if provider == "openai":
                from langchain_openai import ChatOpenAI

                self._llm = ChatOpenAI(
                    model=model or "gpt-4o",
                    temperature=0.1,
                    max_retries=2,
                    timeout=30,
                )
                self._provider = "openai"
                self._model = model or "gpt-4o"

            elif provider == "anthropic":
                from langchain_anthropic import ChatAnthropic

                self._llm = ChatAnthropic(
                    model=model or "claude-sonnet-4-20250514",
                    temperature=0.1,
                    max_retries=2,
                    timeout=30,
                )
                self._provider = "anthropic"
                self._model = model or "claude-sonnet-4-20250514"

            else:
                self._init_error = f"Unknown LLM provider: {provider}"
                return False

            # Quick validation - run a simple test
            self._available = True
            logger.info(
                "llm_service.initialized",
                provider=self._provider,
                model=self._model,
            )
            return True

        except Exception as exc:
            self._init_error = f"Failed to initialize {provider}: {exc}"
            logger.error("llm_service.init_failed", error=str(exc))
            return False

    @property
    def is_available(self) -> bool:
        if not self._initialized:
            self.initialize()
        return self._available

    @property
    def provider_name(self) -> str:
        return self._provider or "fallback (rule-based)"

    async def interpret_goal(self, raw_input: str) -> dict[str, Any]:
        """Use LLM to parse a user's software request into a structured spec.

        Returns a dict with keys: project_type, title, modules, constraints, tech_stack
        Falls back to rule-based parsing if LLM unavailable.
        """
        if not self._initialized:
            self.initialize()

        if not self._available:
            return self._fallback_interpret(raw_input)

        prompt = f"""You are an expert software architect. Convert this user request into a structured project specification.

User request: "{raw_input}"

Return a JSON object with EXACTLY these keys:
- "project_type": one of: hospital, ecommerce, saas, social, fintech, crm, erp, blog, game, general
- "title": a clean, professional project title
- "modules": array of {{"name": str, "entities": [str], "priority": int 1-10}} — the main functional modules
- "constraints": array of {{"category": str, "description": str, "priority": str("must"/"should"/"could")}} — security, scalability, performance etc.
- "tech_stack": {{"language": str, "framework": str, "database": str, "cache": str or null, "additional": {{str: str}} }}

Be thorough. Extract every meaningful feature mentioned. Output ONLY valid JSON, no explanation."""

        try:
            from langchain_core.messages import HumanMessage

            response = await self._llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # Extract JSON from potential markdown wrapping
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

            result = json.loads(content)

            # Validate required fields
            required = ["project_type", "modules"]
            for field in required:
                if field not in result:
                    return self._fallback_interpret(raw_input)

            logger.info("llm_service.goal_interpreted", project_type=result.get("project_type"))
            return result

        except Exception as exc:
            logger.error("llm_service.interpret_error", error=str(exc))
            return self._fallback_interpret(raw_input)

    async def generate_code(
        self,
        prompt: str,
        language: str = "python",
        max_tokens: int = 2000,
    ) -> str:
        """Generate code using the LLM.

        Args:
            prompt: Description of the code to generate
            language: Target language (python, typescript, sql, etc.)
            max_tokens: Maximum tokens in response

        Returns:
            Generated code as a string
        """
        if not self._initialized:
            self.initialize()

        if not self._available:
            return f"# Code generation requires an LLM API key.\n# Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env\n# Request was: {prompt[:100]}..."

        full_prompt = f"""Generate {language} code for the following specification.
Return ONLY the {language} code, no explanation, no markdown wrapping.

{prompt}"""

        try:
            from langchain_core.messages import HumanMessage

            response = await self._llm.ainvoke([HumanMessage(content=full_prompt)])
            content = response.content.strip()

            # Strip markdown code fences if present
            code_match = re.search(
                r"```(?:\w+)?\s*\n?(.*?)\n?```", content, re.DOTALL
            )
            if code_match:
                content = code_match.group(1)

            return content

        except Exception as exc:
            logger.error("llm_service.codegen_error", error=str(exc))
            return f"# Error generating code: {exc}\n# Request: {prompt[:100]}..."

    def _fallback_interpret(self, raw_input: str) -> dict[str, Any]:
        """Rule-based fallback when LLM is not available."""
        text_lower = raw_input.lower()

        # Detect project type
        type_scores = {
            "hospital": ["hospital", "medical", "clinic", "healthcare", "patient", "doctor"],
            "ecommerce": ["ecommerce", "shop", "store", "retail", "marketplace", "product", "catalog"],
            "saas": ["saas", "subscription", "tenant", "multi.?tenant"],
            "social": ["social", "feed", "profile", "messaging", "chat", "forum", "community"],
            "fintech": ["fintech", "banking", "payment", "wallet", "finance", "trading", "crypto"],
        }

        best_type = "general"
        best_score = 0
        for ptype, keywords in type_scores.items():
            score = sum(1 for kw in keywords if re.search(kw, text_lower))
            if score > best_score:
                best_score = score
                best_type = ptype

        # Generate title
        title_match = re.search(r"(?:build|create|make|develop)\s+(?:a|an|the)?\s*(.+)", raw_input, re.IGNORECASE)
        title = title_match.group(1).strip().rstrip(".!") if title_match else raw_input[:80]

        # Generate modules based on project type
        module_templates = {
            "hospital": [
                {"name": "Patient Management", "entities": ["Patient", "MedicalRecord"], "priority": 10},
                {"name": "Doctor Management", "entities": ["Doctor", "Schedule"], "priority": 9},
                {"name": "Appointment Scheduling", "entities": ["Appointment", "Availability"], "priority": 9},
                {"name": "Billing & Invoicing", "entities": ["Invoice", "Payment"], "priority": 8},
            ],
            "ecommerce": [
                {"name": "Product Catalog", "entities": ["Product", "Category", "Inventory"], "priority": 10},
                {"name": "Shopping Cart", "entities": ["Cart", "CartItem"], "priority": 9},
                {"name": "Order Management", "entities": ["Order", "OrderItem", "Shipment"], "priority": 9},
            ],
            "saas": [
                {"name": "Tenant Management", "entities": ["Tenant", "Subscription"], "priority": 10},
                {"name": "User Management", "entities": ["User", "Team", "Invitation"], "priority": 9},
            ],
            "social": [
                {"name": "User Profiles", "entities": ["Profile", "Settings"], "priority": 10},
                {"name": "Content Feed", "entities": ["Post", "Comment", "Reaction"], "priority": 9},
            ],
            "fintech": [
                {"name": "Accounts & Ledgers", "entities": ["Account", "LedgerEntry"], "priority": 10},
                {"name": "Transactions", "entities": ["Transaction", "Transfer"], "priority": 10},
            ],
            "general": [
                {"name": "Core", "entities": ["Entity"], "priority": 5},
            ],
        }

        modules = module_templates.get(best_type, module_templates["general"])

        # Detect constraints
        constraints = []
        constraint_patterns = [
            ("security", r"\b(secure|security|safe|encrypt|auth)\b", "must"),
            ("scalability", r"\b(scale|scalable|million|growth)\b", "should"),
            ("performance", r"\b(fast|performance|latency|realtime)\b", "should"),
            ("mobile", r"\b(mobile|ios|android|responsive)\b", "should"),
            ("cloud", r"\b(cloud|aws|azure|gcp|kubernetes)\b", "could"),
            ("compliance", r"\b(hipaa|gdpr|pci|sox|compliance)\b", "must"),
        ]
        for cat, pattern, priority in constraint_patterns:
            if re.search(pattern, text_lower):
                constraints.append({"category": cat, "description": f"System must support {cat.replace('_', ' ')}", "priority": priority})

        return {
            "project_type": best_type,
            "title": title,
            "modules": modules,
            "constraints": constraints,
            "tech_stack": {
                "language": "python",
                "framework": "fastapi",
                "database": "postgresql",
                "cache": "redis",
                "additional": {},
            },
        }
