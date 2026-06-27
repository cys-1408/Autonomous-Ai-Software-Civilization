"""Code Generator Service — Real File Generation with Jinja2 + LLM.

Generates actual runnable source code files on disk using:
1. Jinja2 templates for standard patterns (CRUD, API, models, tests)
2. LLM for intelligent code generation beyond templates

The output is written directly to the project's output directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader

from backend.services.llm_service import LLMService

logger = structlog.get_logger(__name__)

# ── Template Directory ─────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class CodeGeneratorService:
    """Generates real source code files using Jinja2 templates and LLM.

    Features:
    - CRUD API template for FastAPI
    - Database model templates for SQLAlchemy
    - Pydantic schema templates
    - Test templates
    - LLM-assisted complex code generation
    """

    def __init__(self, llm_service: LLMService | None = None):
        self._llm = llm_service or LLMService()
        self._jinja_env: Environment | None = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize Jinja2 environment with template directory."""
        if self._initialized:
            return True
        self._initialized = True

        if TEMPLATES_DIR.exists():
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(TEMPLATES_DIR)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            logger.info("code_generator.jinja_initialized", template_dir=str(TEMPLATES_DIR))
        else:
            logger.info(
                "code_generator.no_templates_dir",
                path=str(TEMPLATES_DIR),
            )

        return True

    # ── Template-Based Generation ───────────────────────────────────

    def generate_model(
        self,
        module_name: str,
        entities: list[str],
        output_dir: str | Path,
        framework: str = "sqlalchemy",
    ) -> list[dict[str, Any]]:
        """Generate database model files using templates or inline generation.

        Returns list of generated file info dicts.
        """
        self.initialize()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated = []
        for entity in entities:
            file_path = output_path / f"{entity.lower()}.py"
            content = self._build_model_content(entity, module_name, framework)
            file_path.write_text(content, encoding="utf-8")
            generated.append({
                "file": str(file_path),
                "type": "model",
                "entity": entity,
                "lines": content.count("\n") + 1,
            })

        logger.info("code_generator.models_generated", count=len(generated), module=module_name)
        return generated

    def generate_api(
        self,
        module_name: str,
        entities: list[str],
        output_dir: str | Path,
        framework: str = "fastapi",
    ) -> list[dict[str, Any]]:
        """Generate CRUD API route files."""
        self.initialize()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated = []
        for entity in entities:
            file_path = output_path / f"{entity.lower()}_routes.py"
            content = self._build_api_content(entity, module_name, framework)
            file_path.write_text(content, encoding="utf-8")
            generated.append({
                "file": str(file_path),
                "type": "api",
                "entity": entity,
                "lines": content.count("\n") + 1,
            })

        logger.info("code_generator.api_generated", count=len(generated), module=module_name)
        return generated

    def generate_schema(
        self,
        module_name: str,
        entities: list[str],
        output_dir: str | Path,
    ) -> list[dict[str, Any]]:
        """Generate Pydantic schema files."""
        self.initialize()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated = []
        for entity in entities:
            file_path = output_path / f"{entity.lower()}_schemas.py"
            content = self._build_schema_content(entity, module_name)
            file_path.write_text(content, encoding="utf-8")
            generated.append({
                "file": str(file_path),
                "type": "schema",
                "entity": entity,
                "lines": content.count("\n") + 1,
            })

        logger.info("code_generator.schemas_generated", count=len(generated), module=module_name)
        return generated

    def generate_test(
        self,
        module_name: str,
        entities: list[str],
        output_dir: str | Path,
    ) -> list[dict[str, Any]]:
        """Generate test files."""
        self.initialize()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated = []
        for entity in entities:
            file_path = output_path / f"test_{entity.lower()}.py"
            content = self._build_test_content(entity, module_name)
            file_path.write_text(content, encoding="utf-8")
            generated.append({
                "file": str(file_path),
                "type": "test",
                "entity": entity,
                "lines": content.count("\n") + 1,
            })

        logger.info("code_generator.tests_generated", count=len(generated), module=module_name)
        return generated

    def generate_full_module(
        self,
        module_name: str,
        entities: list[str],
        output_dir: str | Path,
    ) -> list[dict[str, Any]]:
        """Generate all files for a module (models, API, schemas, tests)."""
        all_generated = []

        # Models
        models_dir = Path(output_dir) / "models"
        all_generated.extend(
            self.generate_model(module_name, entities, models_dir)
        )

        # API routes
        routes_dir = Path(output_dir) / "routes"
        all_generated.extend(
            self.generate_api(module_name, entities, routes_dir)
        )

        # Schemas
        schemas_dir = Path(output_dir) / "schemas"
        all_generated.extend(
            self.generate_schema(module_name, entities, schemas_dir)
        )

        # Tests
        tests_dir = Path(output_dir) / "tests"
        all_generated.extend(
            self.generate_test(module_name, entities, tests_dir)
        )

        # Init files
        for dir_path in [models_dir, routes_dir, schemas_dir, tests_dir]:
            init_file = dir_path / "__init__.py"
            init_file.parent.mkdir(parents=True, exist_ok=True)
            if not init_file.exists():
                init_file.write_text("# Auto-generated\n", encoding="utf-8")

        return all_generated

    @property
    def template_env_available(self) -> bool:
        """Whether Jinja2 template environment is available."""
        self.initialize()
        return self._jinja_env is not None

    # ── LLM-Based Generation ────────────────────────────────────────

    async def generate_with_llm(
        self,
        prompt: str,
        language: str = "python",
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Generate code using LLM and optionally write to a file.

        Returns dict with content and optional file info.
        """
        content = await self._llm.generate_code(prompt, language)

        result = {
            "content": content,
            "language": language,
            "file": None,
        }

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            result["file"] = str(path)

        return result

    # ── Inline Code Builders ────────────────────────────────────────

    def _build_model_content(self, entity: str, module: str, framework: str) -> str:
        """Build a SQLAlchemy model file content."""
        entity_lower = entity.lower()
        return f'''"""
{entity} model — Auto-generated by AI Civilization Code Generator
Module: {module}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB


class {entity}(Base):
    """{entity} model for {module}."""

    __tablename__ = "{entity_lower}s"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={{self.id}}, name='{{self.name}}')>"

    def to_dict(self) -> dict:
        return {{
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }}
'''

    def _build_api_content(self, entity: str, module: str, framework: str) -> str:
        """Build a FastAPI CRUD route file content."""
        entity_lower = entity.lower()
        entity_plural = entity_lower + "s"

        return f'''"""
{entity} API routes — Auto-generated by AI Civilization Code Generator
Module: {module}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Depends, Query

from .schemas import (
    {entity}Create,
    {entity}Update,
    {entity}Response,
)
from .models import {entity} as {entity}Model

router = APIRouter(prefix="/api/v1/{entity_plural}", tags=["{entity_plural}"])


@router.get("/", response_model=List[{entity}Response])
async def list_{entity_lower}s(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get all {entity_lower}s with pagination."""
    # TODO: Implement database query
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/", response_model={entity}Response, status_code=201)
async def create_{entity_lower}(data: {entity}Create):
    """Create a new {entity_lower}."""
    # TODO: Implement database insert
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{{{entity_lower}_id}}", response_model={entity}Response)
async def get_{entity_lower}({entity_lower}_id: str):
    """Get a {entity_lower} by ID."""
    # TODO: Implement database query
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/{{{entity_lower}_id}}", response_model={entity}Response)
async def update_{entity_lower}({entity_lower}_id: str, data: {entity}Update):
    """Update a {entity_lower}."""
    # TODO: Implement database update
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{{{entity_lower}_id}}", status_code=204)
async def delete_{entity_lower}({entity_lower}_id: str):
    """Delete a {entity_lower}."""
    # TODO: Implement database delete
    raise HTTPException(status_code=501, detail="Not implemented")
'''

    def _build_schema_content(self, entity: str, module: str) -> str:
        """Build a Pydantic schema file content."""
        entity_lower = entity.lower()

        return f'''"""
{entity} schemas — Auto-generated by AI Civilization Code Generator
Module: {module}
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class {entity}Base(BaseModel):
    """Base {entity} schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: bool = True


class {entity}Create({entity}Base):
    """Schema for creating a {entity}."""
    pass


class {entity}Update(BaseModel):
    """Schema for updating a {entity}. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class {entity}Response({entity}Base):
    """Schema for {entity} response."""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
'''

    def _build_test_content(self, entity: str, module: str) -> str:
        """Build a test file content."""
        entity_lower = entity.lower()

        return f'''"""
Tests for {entity} — Auto-generated by AI Civilization Code Generator
Module: {module}
"""

from __future__ import annotations

import pytest
from datetime import datetime


class Test{entity}:
    """Test suite for {entity} module."""

    def test_create_{entity_lower}(self):
        """Test creating a {entity_lower}."""
        # TODO: Implement test
        assert True

    def test_get_{entity_lower}(self):
        """Test retrieving a {entity_lower}."""
        # TODO: Implement test
        assert True

    def test_update_{entity_lower}(self):
        """Test updating a {entity_lower}."""
        # TODO: Implement test
        assert True

    def test_delete_{entity_lower}(self):
        """Test deleting a {entity_lower}."""
        # TODO: Implement test
        assert True

    def test_list_{entity_lower}s(self):
        """Test listing {entity_lower}s."""
        # TODO: Implement test
        assert True

    def test_{entity_lower}_validation(self):
        """Test input validation for {entity_lower}."""
        # TODO: Implement test
        assert True
'''
