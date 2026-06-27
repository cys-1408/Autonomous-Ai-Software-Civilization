"""Tests for GoalInterpreter — converts user intent to structured specs."""

import pytest

from backend.components.goal_interpreter import GoalInterpreter


@pytest.fixture
def interpreter():
    return GoalInterpreter()


class TestGoalInterpreterDetection:
    """Test rule-based project type detection."""

    def test_detect_hospital(self, interpreter):
        ptype = interpreter._detect_project_type("Build a Hospital Management System with patient records")
        assert ptype == "hospital"

    def test_detect_ecommerce(self, interpreter):
        ptype = interpreter._detect_project_type("Create an E-Commerce platform with product catalog")
        assert ptype == "ecommerce"

    def test_detect_social(self, interpreter):
        ptype = interpreter._detect_project_type("Build a social network with user profiles and messaging")
        assert ptype == "social"

    def test_detect_saas(self, interpreter):
        ptype = interpreter._detect_project_type("Create a SaaS subscription management platform")
        assert ptype == "saas"

    def test_detect_fintech(self, interpreter):
        ptype = interpreter._detect_project_type("Build a fintech payment processing system")
        assert ptype == "fintech"

    def test_detect_general(self, interpreter):
        ptype = interpreter._detect_project_type("Build something random")
        assert ptype == "general"


class TestGoalInterpreterTitle:
    """Test title generation."""

    def test_title_extraction(self, interpreter):
        title = interpreter._generate_title("Build a Hospital Management System", "hospital")
        assert "Hospital Management System" in title

    def test_title_fallback(self, interpreter):
        title = interpreter._generate_title("Do something cool", "general")
        assert title == "Software Application"


class TestGoalInterpreterModules:
    """Test module generation."""

    def test_hospital_modules(self, interpreter):
        modules = interpreter._build_modules("hospital", "Build a hospital system")
        assert len(modules) > 0
        names = [m.name for m in modules]
        assert "Patient Management" in names
        assert "Doctor Management" in names
        assert "Billing & Invoicing" in names

    def test_ecommerce_modules(self, interpreter):
        modules = interpreter._build_modules("ecommerce", "Build an ecommerce platform")
        names = [m.name for m in modules]
        assert "Product Catalog" in names
        assert "Shopping Cart" in names

    def test_unknown_type_gets_core_module(self, interpreter):
        modules = interpreter._build_modules("unknown", "Do something")
        assert len(modules) == 1
        assert modules[0].name == "Core"


class TestGoalInterpreterConstraints:
    """Test constraint detection."""

    def test_security_constraint(self, interpreter):
        constraints = interpreter._detect_constraints("Build a secure HIPAA compliant system")
        categories = [c.category for c in constraints]
        assert "security" in categories
        assert "compliance" in categories

    def test_scalability_constraint(self, interpreter):
        constraints = interpreter._detect_constraints("Build a scalable system for millions of users")
        categories = [c.category for c in constraints]
        assert "scalability" in categories

    def test_performance_constraint(self, interpreter):
        constraints = interpreter._detect_constraints("Need fast realtime processing")
        categories = [c.category for c in constraints]
        assert "performance" in categories


class TestGoalInterpreterTechStack:
    """Test technology stack recommendations."""

    def test_fintech_stack(self, interpreter):
        from backend.models.project import Constraint
        stack = interpreter._recommend_tech_stack("fintech", [])
        assert stack.language == "python"
        assert stack.framework == "fastapi"
        assert stack.database == "postgresql"

    def test_social_stack(self, interpreter):
        from backend.models.project import Constraint
        stack = interpreter._recommend_tech_stack("social", [])
        assert stack.language == "typescript"

    def test_general_stack(self, interpreter):
        from backend.models.project import Constraint
        stack = interpreter._recommend_tech_stack("general", [])
        assert stack.language == "python"


@pytest.mark.asyncio
class TestGoalInterpreterAsync:
    """Test async goal interpretation (without LLM)."""

    async def test_rule_based_interpret_hospital(self, interpreter):
        spec = await interpreter.interpret("Build a Hospital Management System")
        assert spec is not None
        assert spec.project_type == "hospital"
        assert spec.module_count > 0
        assert spec.title is not None

    async def test_rule_based_interpret_ecommerce(self, interpreter):
        spec = await interpreter.interpret("Build an E-Commerce platform")
        assert spec.project_type == "ecommerce"
        assert spec.module_count > 0

    async def test_interpret_publishes_event_with_hub(self, interpreter):
        from unittest.mock import AsyncMock
        interpreter.hub = AsyncMock()
        interpreter.hub.publish_event = AsyncMock()
        interpreter.hub.push_dashboard_update = AsyncMock()

        spec = await interpreter.interpret("Build a Hospital Management System")
        assert spec is not None
        interpreter.hub.publish_event.assert_called_once()
        interpreter.hub.push_dashboard_update.assert_called_once()
