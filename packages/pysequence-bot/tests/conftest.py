"""Shared fixtures for the test suite."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_sdk_client() -> MagicMock:
    """Mock SequenceClient for unit tests."""
    return MagicMock()
