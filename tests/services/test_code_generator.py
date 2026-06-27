"""Tests for CodeGeneratorService — real file generation."""

import pytest
import tempfile
from pathlib import Path

from backend.services.code_generator import CodeGeneratorService


@pytest.fixture
def generator():
    return CodeGeneratorService()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestCodeGeneratorInitialization:
    def test_init(self, generator):
        assert generator._initialized is False

    def test_initialize(self, generator):
        result = generator.initialize()
        assert result is True
        assert generator._initialized is True


class TestModelGeneration:
    def test_generate_model_creates_file(self, generator, temp_dir):
        files = generator.generate_model(
            module_name="TestModule",
            entities=["Patient", "Doctor"],
            output_dir=temp_dir / "models",
        )
        assert len(files) == 2
        assert (temp_dir / "models" / "patient.py").exists()
        assert (temp_dir / "models" / "doctor.py").exists()
        # Verify content has proper class definitions
        content = (temp_dir / "models" / "patient.py").read_text()
        assert "class Patient(Base):" in content
        assert "to_dict" in content
        assert "get_by_id" in content

    def test_generate_model_has_correct_entity(self, generator, temp_dir):
        files = generator.generate_model(
            module_name="Hospital",
            entities=["Appointment"],
            output_dir=temp_dir / "models",
        )
        content = (temp_dir / "models" / "appointment.py").read_text()
        assert "class Appointment(Base):" in content
        assert "__tablename__ = \"appointments\"" in content


class TestAPIGeneration:
    def test_generate_api_creates_file(self, generator, temp_dir):
        files = generator.generate_api(
            module_name="TestModule",
            entities=["Patient"],
            output_dir=temp_dir / "routes",
        )
        assert len(files) == 1
        assert (temp_dir / "routes" / "patient_routes.py").exists()
        content = (temp_dir / "routes" / "patient_routes.py").read_text()
        # Should not have 501 stubs anymore
        assert "status_code=501" not in content
        assert "status_code=500" in content or "APIRouter" in content

    def test_generate_api_has_list_endpoint(self, generator, temp_dir):
        files = generator.generate_api("Test", ["Product"], temp_dir / "routes")
        content = (temp_dir / "routes" / "product_routes.py").read_text()
        assert "list_products" in content
        assert "APIRouter" in content


class TestSchemaGeneration:
    def test_generate_schema_creates_file(self, generator, temp_dir):
        files = generator.generate_schema(
            module_name="TestModule",
            entities=["Patient"],
            output_dir=temp_dir / "schemas",
        )
        assert len(files) == 1
        assert (temp_dir / "schemas" / "patient_schemas.py").exists()
        content = (temp_dir / "schemas" / "patient_schemas.py").read_text()
        assert "PatientCreate" in content
        assert "PatientUpdate" in content
        assert "PatientResponse" in content
        assert "PatientListResponse" in content

    def test_schema_has_validation(self, generator, temp_dir):
        files = generator.generate_schema("Test", ["Item"], temp_dir / "schemas")
        content = (temp_dir / "schemas" / "item_schemas.py").read_text()
        assert "extra=\"forbid\"" in content
        assert "ConfigDict" in content


class TestTestGeneration:
    def test_generate_test_creates_file(self, generator, temp_dir):
        files = generator.generate_test(
            module_name="TestModule",
            entities=["Patient"],
            output_dir=temp_dir / "tests",
        )
        assert len(files) == 1
        assert (temp_dir / "tests" / "test_patient.py").exists()
        content = (temp_dir / "tests" / "test_patient.py").read_text()
        assert "TestPatient" in content
        assert "pytest" in content

    def test_tests_have_async_tests(self, generator, temp_dir):
        files = generator.generate_test("Test", ["Order"], temp_dir / "tests")
        content = (temp_dir / "tests" / "test_order.py").read_text()
        assert "pytest.mark.asyncio" in content
        assert "async def" in content


class TestFullModuleGeneration:
    def test_generate_full_module_creates_all_files(self, generator, temp_dir):
        files = generator.generate_full_module(
            module_name="Hospital",
            entities=["Patient", "Doctor"],
            output_dir=temp_dir,
        )
        assert len(files) >= 8  # 2 entities × 4 file types = 8 files
        assert (temp_dir / "models" / "patient.py").exists()
        assert (temp_dir / "routes" / "patient_routes.py").exists()
        assert (temp_dir / "schemas" / "patient_schemas.py").exists()
        assert (temp_dir / "tests" / "test_patient.py").exists()

    def test_generate_full_module_creates_init_files(self, generator, temp_dir):
        generator.generate_full_module("Test", ["Entity"], temp_dir)
        assert (temp_dir / "models" / "__init__.py").exists()
        assert (temp_dir / "routes" / "__init__.py").exists()
        assert (temp_dir / "schemas" / "__init__.py").exists()
        assert (temp_dir / "tests" / "__init__.py").exists()
