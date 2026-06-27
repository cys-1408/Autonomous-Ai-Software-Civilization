"""Shared pytest configuration and fixtures for AASC tests."""

import pytest


def pytest_configure(config):
    """Configure pytest settings."""
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async (run with pytest-asyncio)",
    )
