"""Shared pytest configuration and fixtures for AASC tests."""

import pytest

# Disable plugins that may require system dependencies
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest settings."""
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async (run with pytest-asyncio)",
    )
    # Disable postgresql plugin if present (requires system libpq)
    if hasattr(config, "pluginmanager"):
        for name in list(config.pluginmanager._name2plugin.keys()):
            if "postgresql" in name.lower():
                config.pluginmanager.unregister(name)
