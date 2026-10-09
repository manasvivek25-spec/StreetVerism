"""Pytest fixtures and configuration."""

import os
from backend.app.config import get_settings

# Ensure test environment default is set during pytest module discovery
os.environ.setdefault("AUTHORITY_KEY", "test-env-authority-key")
os.environ.setdefault("MOCK", "1")

import pytest


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set required test environment variables before each test runs."""
    monkeypatch.setenv("AUTHORITY_KEY", "test-env-authority-key")
    monkeypatch.setenv("MOCK", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
