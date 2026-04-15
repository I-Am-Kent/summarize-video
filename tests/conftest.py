"""Shared test fixtures for summarize-video tests."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure servers/ is on the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "servers"))


@pytest.fixture
def mock_ensure_server_ok(monkeypatch):
    """Patches ensure_server to return None (success)."""
    import launcher
    monkeypatch.setattr(launcher, "ensure_server", lambda: None)


@pytest.fixture
def mock_ensure_server_error(monkeypatch):
    """Patches ensure_server to return an error string."""
    import launcher
    monkeypatch.setattr(launcher, "ensure_server", lambda: "ERROR: server not available")
